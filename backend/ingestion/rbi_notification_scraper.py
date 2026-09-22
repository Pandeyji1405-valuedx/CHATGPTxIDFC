import os
import re
import time
import json
import hashlib
import logging
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from pypdf import PdfReader

# Selenium Imports for JavaScript Rendering
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle

from backend.config import settings
from backend.database import SessionLocal
from backend.models import KnowledgeDocument, KnowledgeChunk
from backend.ingestion.chunker import document_chunker
from backend.rag.vector_store import hybrid_vector_store
from backend.cache.redis_cache import redis_cache

logger = logging.getLogger(__name__)

RBI_BASE_URL = "https://www.rbi.org.in"
DEFAULT_NOTIFICATION_URL = f"{RBI_BASE_URL}/Scripts/NotificationUser.aspx?Id=13412&Mode=0"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class RBINewWebsiteScraper:
    """
    Dedicated comprehensive web scraper for RBI Notification User portal
    (NotificationUser.aspx) and associated regulatory documents, PDFs,
    internal hyperlinked directives, dynamic JavaScript execution via Selenium,
    and year/month page navigations.
    """

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or os.path.join(settings.KB_DIR, "rbi", "pdfs")
        os.makedirs(self.output_dir, exist_ok=True)
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": RBI_BASE_URL
        }
        self._driver = None

    def get_selenium_driver(self) -> webdriver.Chrome:
        """
        Initializes and returns a headless Selenium WebDriver (Chrome or Edge)
        configured for scraping dynamic JavaScript-heavy websites.
        """
        if self._driver is not None:
            try:
                # Test driver liveness
                _ = self._driver.current_window_handle
                return self._driver
            except Exception:
                self._driver = None

        logger.info("Initializing Selenium Headless Chrome WebDriver...")
        try:
            c_opts = ChromeOptions()
            c_opts.add_argument("--headless=new")
            c_opts.add_argument("--disable-gpu")
            c_opts.add_argument("--no-sandbox")
            c_opts.add_argument("--disable-dev-shm-usage")
            c_opts.add_argument(f"user-agent={DEFAULT_USER_AGENT}")
            c_opts.add_argument("--window-size=1920,1080")
            c_opts.add_argument("--disable-blink-features=AutomationControlled")
            c_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            c_opts.add_experimental_option("useAutomationExtension", False)

            driver = webdriver.Chrome(options=c_opts)
            driver.set_page_load_timeout(30)
            self._driver = driver
            return driver
        except Exception as e:
            logger.warning(f"Failed to start Chrome WebDriver: {e}. Trying Edge WebDriver...")
            try:
                e_opts = EdgeOptions()
                e_opts.add_argument("--headless=new")
                e_opts.add_argument("--disable-gpu")
                e_opts.add_argument("--no-sandbox")
                e_opts.add_argument(f"user-agent={DEFAULT_USER_AGENT}")
                driver = webdriver.Edge(options=e_opts)
                driver.set_page_load_timeout(30)
                self._driver = driver
                return driver
            except Exception as e2:
                logger.error(f"Failed to start Edge WebDriver: {e2}")
                raise RuntimeError(f"Could not initialize Selenium WebDriver: {e} / {e2}")

    def close_selenium_driver(self):
        """Safely closes active Selenium WebDriver."""
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    def fetch_with_selenium(
        self,
        url: str,
        wait_selector: Optional[str] = None,
        execute_js: Optional[str] = None,
        timeout: int = 20
    ) -> Optional[str]:
        """
        Navigates to URL using Selenium, executes client-side JavaScript,
        waits for DOM elements, and returns the fully rendered HTML source.
        """
        logger.info(f"[Selenium] Navigating to: {url}")
        driver = None
        try:
            driver = self.get_selenium_driver()
            driver.get(url)

            # Wait for specific selector or default content container
            target_selector = wait_selector or "#NotificationUser, #pnlDetails, .tablebg, body"
            try:
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, target_selector))
                )
            except Exception:
                logger.warning(f"[Selenium] Timeout waiting for selector: {target_selector}")

            # Execute optional client-side JavaScript
            if execute_js:
                logger.info(f"[Selenium] Executing custom JavaScript: {execute_js[:60]}...")
                driver.execute_script(execute_js)
                time.sleep(1.0)

            # Scroll to trigger any lazy-loaded contents
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
            time.sleep(0.5)

            rendered_html = driver.page_source
            logger.info(f"[Selenium] Successfully fetched rendered HTML ({len(rendered_html)} bytes) for {url}")
            return rendered_html
        except Exception as e:
            logger.error(f"[Selenium] Error fetching {url}: {e}")
            return None

    def _http_get(self, url: str, timeout: int = 25, use_selenium: bool = False) -> Optional[str]:
        """
        Fetches web page content. If use_selenium is True or JavaScript dynamic rendering
        is needed, executes via headless Selenium; otherwise uses safe HTTP GET.
        """
        if use_selenium:
            selenium_html = self.fetch_with_selenium(url, timeout=timeout)
            if selenium_html:
                return selenium_html
            logger.warning(f"Selenium fetch failed for {url}. Falling back to HTTP GET.")

        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    return response.read().decode("utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"HTTP GET failed for {url} (attempt {attempt+1}/3): {e}")
                time.sleep(1.0 * (attempt + 1))
        return None

    def _http_download_binary(self, url: str, dest_path: str, timeout: int = 35) -> bool:
        """Downloads authentic binary PDF directly to local disk."""
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    data = response.read()
                    if len(data) > 0 and data.startswith(b"%PDF-"):
                        with open(dest_path, "wb") as f:
                            f.write(data)
                        return True
                    else:
                        logger.warning(f"Downloaded binary from {url} is not valid PDF (starts with: {data[:15]!r}).")
                        return False
            except Exception as e:
                logger.warning(f"Binary download error for {url} (attempt {attempt+1}/3): {e}")
                time.sleep(1.0 * (attempt + 1))
        return False

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalizes text dates to YYYY-MM-DD."""
        if not date_str:
            return None
        date_str = date_str.strip()
        formats = ["%B %d, %Y", "%b %d, %Y", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return date_str

    def scrape_single_notification_page(self, url: str, use_selenium: bool = False) -> Optional[Dict[str, Any]]:
        """
        Extracts full contents, circular metadata, attached official PDF download link,
        and all internal hyperlink references from a single NotificationUser or directive URL.
        Supports Selenium dynamic JavaScript extraction when use_selenium=True.
        """
        logger.info(f"Scraping notification page (use_selenium={use_selenium}): {url}")
        html = self._http_get(url, use_selenium=use_selenium)
        if not html:
            logger.error(f"Failed to fetch content from {url}")
            return None

        soup = BeautifulSoup(html, "html.parser")
        pnl = soup.find("div", id="pnlDetails") or soup.find("div", id="annual") or soup.find("div", id="NotificationUser") or soup

        # 1. Official PDF Download link
        pdf_url = ""
        for a in pnl.find_all("a", href=True):
            href = a["href"].strip()
            if "rbidocs.rbi.org.in" in href or href.lower().endswith(".pdf"):
                pdf_url = href if href.startswith("http") else f"{RBI_BASE_URL}{href}" if href.startswith("/") else f"{RBI_BASE_URL}/scripts/{href}"
                break

        # 2. Extract Notification Title
        title = ""
        header_td = pnl.find("td", class_="tableheader")
        if header_td and header_td.find_next_sibling("tr"):
            title_td = header_td.find_next_sibling("tr").find("td", class_="tableheader")
            if title_td:
                title = title_td.get_text(strip=True)

        if not title:
            h1 = pnl.find("h1", class_="page_title")
            head_p = pnl.find("p", class_="head")
            if head_p:
                title = head_p.get_text(strip=True)
            elif h1:
                title = h1.get_text(strip=True)
            else:
                title = soup.find("title").get_text(strip=True) if soup.find("title") else "RBI Notification Directive"

        title = re.sub(r"^Notifications\s*-\s*", "", title).strip()

        # 3. Extract Notification Number & Reference Number
        body_text_raw = pnl.get_text(separator="\n").strip()
        circ_num_match = re.search(r"(RBI/\d{4}-\d{2,4}/\d+)", body_text_raw)
        ref_num_match = re.search(r"((?:DOR|DoR|FMRD|DPSS|FIDD|IDMD|DBR)[\w\.\-]+/\d{2,4}\-\d{2,4})", body_text_raw)
        
        circ_num = circ_num_match.group(1) if circ_num_match else ""
        ref_num = ref_num_match.group(1) if ref_num_match else ""
        notif_num = f"{circ_num} {ref_num}".strip() if circ_num and ref_num else (circ_num or ref_num or f"RBI-NOTIF-{hashlib.md5(url.encode()).hexdigest()[:8]}")

        # 4. Extract Date of Issue
        date_match = re.search(r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})", body_text_raw)
        issue_date_raw = date_match.group(1) if date_match else datetime.now().strftime("%B %d, %Y")
        norm_date = self._normalize_date(issue_date_raw)

        # 5. Extract Effective Date
        eff_date_match = re.search(r"(?:come into force with effect from|effective from|with effect from)\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|\d{1,2}[\.\/\-]\d{1,2}[\.\/\-]\d{4})", body_text_raw, re.IGNORECASE)
        eff_date = self._normalize_date(eff_date_match.group(1)) if eff_date_match else norm_date

        # 6. Extract Signatory
        signatory_match = re.search(r"\(([A-Za-z\s\.\,\-]+)\)\s*\n+\s*([A-Za-z\s\.\,]+)$", body_text_raw)
        signatory = f"{signatory_match.group(1).strip()} ({signatory_match.group(2).strip()})" if signatory_match else ""

        # 7. Extract In-Page Hyperlinks & Referenced Policies
        sub_links = []
        for a in pnl.find_all("a", href=True):
            raw_href = a["href"].strip()
            link_text = a.get_text(separator=" ", strip=True)
            if not raw_href or raw_href.startswith("#") or raw_href.startswith("javascript:") or len(link_text) < 3:
                continue
            if any(w in link_text.lower() for w in ["skip to", "home", "print", "disclaimer", "sitemap", "back"]):
                continue

            full_sub_url = raw_href if raw_href.startswith("http") else f"{RBI_BASE_URL}{raw_href}" if raw_href.startswith("/") else f"{RBI_BASE_URL}/scripts/{raw_href}"
            
            if any(k in full_sub_url.lower() for k in ["notificationuser.aspx", "bs_viewmasdirections.aspx", "bs_pressreleasedisplay.aspx", "fs_amendmentdirections.aspx", ".pdf", "rbidocs"]):
                sub_links.append({
                    "title": link_text,
                    "url": full_sub_url,
                    "parent_doc": notif_num
                })

        # 8. Clean text
        for tag in pnl.find_all(["script", "style", "nav", "input"]):
            tag.decompose()

        cleaned_text = re.sub(r"\n{3,}", "\n\n", pnl.get_text(separator="\n").strip())

        # 9. Download Authentic PDF or Generate High-Fidelity Formatted PDF
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"RBI_{notif_num}_{title}")[:60]
        pdf_path = os.path.join(self.output_dir, f"{safe_name}.pdf")
        downloaded = False
        if pdf_url:
            downloaded = self._http_download_binary(pdf_url, pdf_path)

        if not downloaded or not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < 100:
            self.generate_formatted_pdf({
                "subject": title,
                "notification_number": notif_num,
                "date_of_issue": issue_date_raw,
                "full_text": cleaned_text,
                "signatory": signatory
            }, pdf_path)

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
            checksum = hashlib.sha256(pdf_bytes).hexdigest()

        # Extract text directly from PDF if downloaded
        pdf_extracted_text = ""
        try:
            reader = PdfReader(pdf_path)
            pages_texts = [p.extract_text() or "" for p in reader.pages]
            pdf_extracted_text = "\n\n".join([t.strip() for t in pages_texts if t.strip()])
            page_count = len(reader.pages)
        except Exception as e:
            logger.warning(f"Could not read PDF with pypdf: {e}")
            page_count = 1

        final_text = pdf_extracted_text if len(pdf_extracted_text) > 100 else cleaned_text

        return {
            "id": hashlib.md5(f"{url}_{notif_num}".encode()).hexdigest()[:12],
            "title": title,
            "subject": title,
            "notification_number": notif_num,
            "circular_number": circ_num or notif_num,
            "reference_number": ref_num,
            "publication_date": norm_date,
            "effective_date": eff_date or norm_date,
            "effective_from": eff_date or norm_date,
            "department": "Department of Regulation",
            "regulator": "RBI",
            "source": "RBI",
            "source_url": url,
            "pdf_url": pdf_url,
            "pdf_path": pdf_path,
            "checksum": checksum,
            "full_text": final_text,
            "page_count": page_count,
            "signatory": signatory,
            "sub_links": sub_links,
            "scraped_via": "selenium" if use_selenium else "http"
        }

    def generate_formatted_pdf(self, doc_data: Dict[str, Any], dest_path: str) -> str:
        """Generates an official RBI PDF formatted document."""
        doc = SimpleDocTemplate(
            dest_path,
            pagesize=letter,
            rightMargin=45,
            leftMargin=45,
            topMargin=45,
            bottomMargin=45
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "RBITitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1e3a8a"),
            alignment=1,
            spaceAfter=8
        )
        meta_style = ParagraphStyle(
            "RBIMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569"),
            spaceAfter=4
        )
        body_style = ParagraphStyle(
            "RBIBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=6
        )

        elements = []
        elements.append(Paragraph("<b>RESERVE BANK OF INDIA</b>", ParagraphStyle(
            "Header", fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=1, textColor=colors.HexColor("#0f172a"), spaceAfter=4
        )))
        elements.append(Paragraph("www.rbi.org.in", ParagraphStyle(
            "SubHeader", fontName="Helvetica", fontSize=9, leading=12, alignment=1, textColor=colors.HexColor("#64748b"), spaceAfter=10
        )))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=12))

        elements.append(Paragraph(f"<b>{doc_data.get('subject', 'RBI Notification')}</b>", title_style))
        elements.append(Paragraph(f"<b>Notification No:</b> {doc_data.get('notification_number', '')} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Date:</b> {doc_data.get('date_of_issue', '')}", meta_style))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=12))

        text = doc_data.get("full_text", "")
        for block in text.split("\n\n"):
            clean_block = block.strip()
            if clean_block:
                safe_text = clean_block.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                elements.append(Paragraph(safe_text, body_style))

        if doc_data.get("signatory"):
            elements.append(Spacer(1, 14))
            elements.append(Paragraph(f"<b>{doc_data['signatory']}</b>", ParagraphStyle(
                "Signatory", parent=body_style, alignment=2, textColor=colors.HexColor("#0f172a")
            )))

        doc.build(elements)
        return dest_path

    def crawl_with_selenium_interactive(self, year: str = "2026", month: str = "4", max_count: int = 15) -> List[Dict[str, str]]:
        """
        Uses Selenium to interactively execute JavaScript year/month selection,
        wait for client-side JavaScript DOM rendering, and extract dynamic notification links.
        """
        url = f"{RBI_BASE_URL}/Scripts/NotificationUser.aspx"
        logger.info(f"[Selenium Interactive] Navigating to {url} and executing GetYearMonth('{year}', '{month}')...")
        try:
            driver = self.get_selenium_driver()
            driver.get(url)

            # Wait for main page to settle
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "NotificationUser"))
            )

            # Execute the JavaScript function GetYearMonth in the browser context
            js_call = f"if (typeof GetYearMonth === 'function') {{ GetYearMonth('{year}', '{month}'); }} else {{ document.getElementById('hdnYear').value='{year}'; document.getElementById('hdnMonth').value='{month}'; document.getElementById('btn').click(); }}"
            driver.execute_script(js_call)
            time.sleep(2.5)

            # Wait for content refresh
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='NotificationUser.aspx?Id='], .tablebg"))
            )

            # Extract dynamic links from the live DOM
            link_elements = driver.find_elements(By.CSS_SELECTOR, "a[href*='NotificationUser.aspx?Id=']")
            discovered = []
            seen_hrefs = set()

            for elem in link_elements:
                href = elem.get_attribute("href")
                title = elem.text.strip()
                if href and href not in seen_hrefs and len(title) > 3:
                    seen_hrefs.add(href)
                    discovered.append({"url": href, "title": title})

            logger.info(f"[Selenium Interactive] Discovered {len(discovered)} dynamic notifications for {year}/{month}")
            if max_count and max_count > 0:
                discovered = discovered[:max_count]
            return discovered
        except Exception as e:
            logger.error(f"[Selenium Interactive] Error during dynamic navigation: {e}")
            return []

    def crawl_year_month_notifications(self, year: str = "2026", month: str = "4", max_count: int = 15, use_selenium: bool = False) -> List[Dict[str, str]]:
        """
        Navigates ASP.NET NotificationUser.aspx tree via Selenium or form POST for the given year and month.
        """
        if use_selenium:
            return self.crawl_with_selenium_interactive(year=year, month=month, max_count=max_count)

        url = f"{RBI_BASE_URL}/Scripts/NotificationUser.aspx"
        logger.info(f"Navigating Notification tree for Year={year}, Month={month} via HTTP POST...")
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            soup = BeautifulSoup(html, "html.parser")
            vs = soup.find("input", id="__VIEWSTATE")["value"]
            vsg = soup.find("input", id="__VIEWSTATEGENERATOR")["value"]
            ev = soup.find("input", id="__EVENTVALIDATION")["value"] if soup.find("input", id="__EVENTVALIDATION") else ""

            post_data = {
                "__VIEWSTATE": vs,
                "__VIEWSTATEGENERATOR": vsg,
                "__EVENTVALIDATION": ev,
                "hdnYear": str(year),
                "hdnMonth": str(month),
                "UsrFontCntr$txtSearch": "",
                "UsrFontCntr$btn": ""
            }
            encoded = urllib.parse.urlencode(post_data).encode("utf-8")
            req_post = urllib.request.Request(url, data=encoded, headers=self.headers)
            with urllib.request.urlopen(req_post, timeout=25) as resp2:
                res_html = resp2.read().decode("utf-8", errors="ignore")
                soup2 = BeautifulSoup(res_html, "html.parser")

                discovered = []
                seen_hrefs = set()
                for a in soup2.find_all("a", href=True):
                    href = a["href"].strip()
                    title = a.get_text(strip=True)
                    if "NotificationUser.aspx?Id=" in href and href not in seen_hrefs:
                        seen_hrefs.add(href)
                        full_url = href if href.startswith("http") else f"{RBI_BASE_URL}/Scripts/{href.lstrip('/')}"
                        discovered.append({"url": full_url, "title": title})

                logger.info(f"Discovered {len(discovered)} notifications in Year={year}, Month={month}")
                if max_count and max_count > 0:
                    discovered = discovered[:max_count]
                return discovered
        except Exception as e:
            logger.error(f"Error navigating year/month tree {year}/{month}: {e}")
            return []

    def ingest_document_to_db(self, doc_data: Dict[str, Any], db_session) -> bool:
        """
        Saves document record to PostgreSQL KnowledgeDocument and splits into KnowledgeChunks.
        """
        try:
            notif_num = doc_data.get("notification_number")
            title = doc_data.get("title")

            existing = db_session.query(KnowledgeDocument).filter(
                (KnowledgeDocument.notification_number == notif_num) |
                (KnowledgeDocument.title == title)
            ).first()

            if existing:
                logger.info(f"Document already exists: {title[:50]} (ID: {existing.id}). Updating chunks.")
                existing.source_url = doc_data.get("source_url")
                existing.file_path = doc_data.get("pdf_path")
                existing.checksum = doc_data.get("checksum")
                existing.processing_status = "indexed"
                doc = existing
            else:
                doc = KnowledgeDocument(
                    title=title,
                    notification_number=notif_num,
                    publication_date=doc_data.get("publication_date"),
                    effective_date=doc_data.get("effective_date"),
                    effective_from=doc_data.get("effective_from"),
                    regulator="RBI",
                    source="RBI",
                    source_url=doc_data.get("source_url"),
                    document_type="pdf",
                    department=doc_data.get("department", "Department of Regulation"),
                    status="active",
                    file_path=doc_data.get("pdf_path"),
                    version="1.0",
                    checksum=doc_data.get("checksum"),
                    processing_status="indexed",
                    page_count=doc_data.get("page_count", 1),
                    is_ocr=False
                )
                db_session.add(doc)
                db_session.commit()
                db_session.refresh(doc)

            # Chunk document
            full_text = doc_data.get("full_text") or title
            chunks = document_chunker.split_text_into_chunks(full_text, page_number=1)
            
            # Clear old chunks if updating
            db_session.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete()

            for c in chunks:
                chunk_obj = KnowledgeChunk(
                    document_id=doc.id,
                    page_number=c.get("page_number", 1),
                    chunk_index=c.get("chunk_index", 0),
                    section=c.get("section", "Notification Directive"),
                    chunk_text=c.get("chunk_text"),
                    bounding_box_json=json.dumps({"x": 40, "y": 100, "width": 520, "height": 600}),
                    source_offsets_json=json.dumps({"char_start": 0, "char_end": len(c.get("chunk_text", ""))})
                )
                db_session.add(chunk_obj)

            db_session.commit()
            logger.info(f"Successfully ingested '{title[:50]}' with {len(chunks)} chunks.")
            return True
        except Exception as e:
            db_session.rollback()
            logger.error(f"Failed to ingest document '{doc_data.get('title')}': {e}")
            return False

    def execute_complete_scrape(
        self,
        target_url: str = DEFAULT_NOTIFICATION_URL,
        use_selenium: bool = True,
        explore_sublinks: bool = True,
        explore_navigations: bool = True,
        nav_years_months: Optional[List[tuple]] = None,
        max_nav_items: int = 10
    ) -> Dict[str, Any]:
        """
        Comprehensive scraping workflow with Selenium JavaScript support:
        1. Deep scrape of primary target URL via Selenium / HTTP.
        2. Deep scrape of all referenced in-page links, amendment directions, and master directions.
        3. Scrape year/month page navigations with interactive JS execution.
        4. Ingest everything into PostgreSQL Knowledge Base.
        5. Re-index Hybrid Vector Store & flush Redis cache.
        """
        logger.info(f"=== Starting Complete RBI Scraping (Selenium={use_selenium}) for: {target_url} ===")
        all_scraped_docs = []
        visited_urls = set()

        db = SessionLocal()

        try:
            # 1. Scrape Primary Target URL
            primary_doc = self.scrape_single_notification_page(target_url, use_selenium=use_selenium)
            if primary_doc:
                visited_urls.add(target_url)
                all_scraped_docs.append(primary_doc)
                self.ingest_document_to_db(primary_doc, db)

                # 2. Explore In-page Hyperlinks
                if explore_sublinks and primary_doc.get("sub_links"):
                    logger.info(f"Found {len(primary_doc['sub_links'])} referenced sub-links in primary notification.")
                    for link_item in primary_doc["sub_links"]:
                        sub_url = link_item["url"]
                        if sub_url not in visited_urls:
                            visited_urls.add(sub_url)
                            logger.info(f"Exploring referenced sub-link: {sub_url} ({link_item['title'][:40]})")
                            sub_doc = self.scrape_single_notification_page(sub_url, use_selenium=use_selenium)
                            if sub_doc:
                                all_scraped_docs.append(sub_doc)
                                self.ingest_document_to_db(sub_doc, db)
                            time.sleep(0.5)

            # 3. Explore Page Navigations across Years and Months (via Selenium JS execution if enabled)
            if explore_navigations:
                pairs = nav_years_months or [("2026", "4"), ("2026", "0")]
                for year, month in pairs:
                    nav_items = self.crawl_year_month_notifications(
                        year=year,
                        month=month,
                        max_count=max_nav_items,
                        use_selenium=use_selenium
                    )
                    for item in nav_items:
                        item_url = item["url"]
                        if item_url not in visited_urls:
                            visited_urls.add(item_url)
                            logger.info(f"Scraping notification from navigation [{year}/{month}]: {item['title'][:50]}")
                            nav_doc = self.scrape_single_notification_page(item_url, use_selenium=use_selenium)
                            if nav_doc:
                                all_scraped_docs.append(nav_doc)
                                self.ingest_document_to_db(nav_doc, db)
                            time.sleep(0.5)

            # 4. Rebuild Hybrid Vector Store Index from Postgres
            from backend.ingestion.seed_rbi_kb import seed_database_and_vector_store
            seed_database_and_vector_store()
            redis_cache.flushall()

            logger.info(f"=== Completed RBI Scraping. Total documents ingested: {len(all_scraped_docs)} ===")

            return {
                "status": "success",
                "target_url": target_url,
                "used_selenium": use_selenium,
                "total_documents_scraped": len(all_scraped_docs),
                "total_urls_visited": len(visited_urls),
                "documents": [
                    {
                        "title": d["title"],
                        "notification_number": d["notification_number"],
                        "publication_date": d["publication_date"],
                        "effective_date": d["effective_date"],
                        "pdf_path": d["pdf_path"],
                        "source_url": d["source_url"],
                        "page_count": d["page_count"],
                        "scraped_via": d.get("scraped_via", "selenium" if use_selenium else "http")
                    }
                    for d in all_scraped_docs
                ]
            }
        finally:
            self.close_selenium_driver()
            db.close()

rbi_notification_scraper = RBINewWebsiteScraper()
