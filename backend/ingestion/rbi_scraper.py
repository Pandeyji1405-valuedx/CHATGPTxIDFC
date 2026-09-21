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

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle

from backend.config import settings
from backend.models import KnowledgeDocument, KnowledgeChunk
from backend.ingestion.chunker import document_chunker
from backend.rag.vector_store import hybrid_vector_store
from backend.cache.redis_cache import redis_cache

logger = logging.getLogger(__name__)

RBI_BASE_URL = "https://www.rbi.org.in"
RBI_INDEX_URL = f"{RBI_BASE_URL}/scripts/BS_CircularIndexDisplay.aspx"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class RBICircularScraper:
    """
    Robust scraper for official Reserve Bank of India (RBI) Circulars Index.
    Extracts circulars, detail pages, downloads authentic official PDFs,
    generates structured PDFs when needed, and ingests them into the RAG vector store.
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

    def _http_get(self, url: str, timeout: int = 25) -> Optional[str]:
        """Performs a safe HTTP GET request with retry logic and standard headers."""
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
        """Downloads a binary file (PDF/Image) directly to disk."""
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    data = response.read()
                    if len(data) > 0:
                        with open(dest_path, "wb") as f:
                            f.write(data)
                        return True
            except Exception as e:
                logger.warning(f"Binary download failed for {url} (attempt {attempt+1}/3): {e}")
                time.sleep(1.5 * (attempt + 1))
        return False

    def parse_circular_table(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parses circular index tables from the RBI index HTML.
        Returns a list of structured circular metadata records.
        """
        if not html_content:
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        circulars: List[Dict[str, Any]] = []

        tables = soup.find_all("table", class_="tablebg")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cols = row.find_all(["td", "th"])
                # Skip header rows
                if not cols or cols[0].name == "th" or "Circular Number" in cols[0].get_text():
                    continue

                if len(cols) >= 4:
                    circ_col = cols[0]
                    link_elem = circ_col.find("a")
                    detail_href = link_elem.get("href", "") if link_elem else ""
                    
                    # Extract circular ID from href (e.g. BS_CircularIndexDisplay.aspx?Id=13704)
                    circ_id = ""
                    if "Id=" in detail_href:
                        circ_id = detail_href.split("Id=")[-1].split("&")[0].strip()

                    full_circ_text = circ_col.get_text(separator="\n").strip()
                    lines = [l.strip() for l in full_circ_text.split("\n") if l.strip()]
                    
                    circ_num = lines[0] if len(lines) > 0 else full_circ_text
                    notif_num = lines[1] if len(lines) > 1 else circ_num

                    issue_date_raw = cols[1].get_text(strip=True)
                    department = cols[2].get_text(strip=True)
                    subject = cols[3].get_text(strip=True)
                    meant_for = cols[4].get_text(strip=True) if len(cols) > 4 else ""

                    # Clean date to standard YYYY-MM-DD
                    clean_date = self._normalize_date(issue_date_raw)

                    detail_full_url = ""
                    if detail_href:
                        if detail_href.startswith("http"):
                            detail_full_url = detail_href
                        else:
                            detail_full_url = f"{RBI_BASE_URL}/scripts/{detail_href.lstrip('/')}"

                    circulars.append({
                        "id": circ_id or hashlib.md5(f"{circ_num}_{subject}".encode()).hexdigest()[:12],
                        "circular_number": circ_num,
                        "notification_number": notif_num,
                        "date_of_issue": clean_date or issue_date_raw,
                        "department": department,
                        "subject": subject,
                        "meant_for": meant_for,
                        "detail_url": detail_full_url,
                        "regulator": "RBI",
                        "source": "RBI"
                    })

        return circulars

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalizes various Indian date formats to YYYY-MM-DD."""
        if not date_str:
            return None
        date_str = date_str.strip()
        formats = ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
        return date_str

    def fetch_circular_details(self, circular_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches the individual circular's detail page and extracts full text content,
        sections, and the official RBI PDF download URL.
        """
        detail_url = circular_info.get("detail_url")
        if not detail_url:
            return circular_info

        html = self._http_get(detail_url)
        if not html:
            logger.warning(f"Could not fetch circular detail from {detail_url}")
            return circular_info

        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Search for official PDF link (rbidocs.rbi.org.in or .PDF in href)
        pdf_url = ""
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "rbidocs.rbi.org.in" in href or href.lower().endswith(".pdf"):
                if href.startswith("http"):
                    pdf_url = href
                else:
                    pdf_url = f"{RBI_BASE_URL}{href}" if href.startswith("/") else f"{RBI_BASE_URL}/scripts/{href}"
                break

        # 2. Extract directive body text
        content_table = soup.find("div", id="pnlDetails") or soup.find("div", id="annual") or soup
        # Remove navigation elements, scripts, and styles from content tree
        for tag in content_table.find_all(["script", "style", "nav", "input"]):
            tag.decompose()

        body_text = content_table.get_text(separator="\n").strip()
        # Clean excessive whitespace
        cleaned_text = re.sub(r"\n{3,}", "\n\n", body_text)

        # 3. Extract Signatory / Department Footer if present
        signatory_match = re.search(r"\(([A-Za-z\s\.\,\-]+)\)\s*\n+\s*([A-Za-z\s\.\,]+)$", cleaned_text)
        signatory = signatory_match.group(1).strip() if signatory_match else ""

        result = dict(circular_info)
        result["pdf_url"] = pdf_url
        result["full_text"] = cleaned_text
        result["signatory"] = signatory
        return result

    def generate_formatted_pdf(self, circular: Dict[str, Any], dest_path: str) -> str:
        """
        Generates a high-fidelity, officially formatted PDF document using ReportLab
        when an authentic standalone PDF is not directly host-accessible.
        """
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
            "RbiTitle",
            parent=styles["Heading1"],
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#1e3a8a"),
            alignment=1, # Center
            spaceAfter=10
        )
        sub_style = ParagraphStyle(
            "RbiSubtitle",
            parent=styles["Normal"],
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#475569"),
            alignment=1,
            spaceAfter=12
        )
        meta_style = ParagraphStyle(
            "RbiMeta",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            "RbiBody",
            parent=styles["Normal"],
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=8
        )

        elements = []

        # Official RBI Header Header
        elements.append(Paragraph("<b>RESERVE BANK OF INDIA</b>", title_style))
        elements.append(Paragraph(f"<b>{circular.get('department', 'Department of Regulation')}</b>", sub_style))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=14))

        # Metadata Table
        meta_data = [
            [
                Paragraph(f"<b>Circular No:</b> {circular.get('circular_number', '')}", meta_style),
                Paragraph(f"<b>Date:</b> {circular.get('date_of_issue', '')}", meta_style)
            ],
            [
                Paragraph(f"<b>Notification:</b> {circular.get('notification_number', '')}", meta_style),
                Paragraph(f"<b>Regulator:</b> RBI", meta_style)
            ]
        ]
        if circular.get("meant_for"):
            meta_data.append([Paragraph(f"<b>Meant For:</b> {circular.get('meant_for')}", meta_style), ""])

        meta_table = Table(meta_data, colWidths=[300, 220])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 14))

        # Subject Headline
        subject_style = ParagraphStyle(
            "RbiSubject",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=12
        )
        elements.append(Paragraph(f"<b>Subject: {circular.get('subject', '')}</b>", subject_style))
        elements.append(Spacer(1, 8))

        # Directive Content Paragraphs
        raw_text = circular.get("full_text", "")
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        for p in paragraphs:
            safe_p = p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            elements.append(Paragraph(safe_p, body_style))

        # Footer Signatory
        if circular.get("signatory"):
            elements.append(Spacer(1, 16))
            elements.append(Paragraph(f"<b>({circular.get('signatory')})</b><br/>Chief General Manager", meta_style))

        doc.build(elements)
        return dest_path

    def save_and_deliver_as_pdf(self, circular: Dict[str, Any]) -> str:
        """
        Ensures the scraped circular is securely saved as a PDF:
        1. If authentic PDF URL exists on rbi.org.in, downloads it.
        2. Otherwise, generates a formatted PDF document.
        Returns the absolute local PDF filepath.
        """
        circ_id = circular.get("id", hashlib.md5(str(circular).encode()).hexdigest()[:10])
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", f"RBI_{circular.get('circular_number', circ_id)}")[:50]
        pdf_path = os.path.join(self.output_dir, f"{safe_name}.pdf")

        pdf_url = circular.get("pdf_url")
        download_success = False

        if pdf_url and pdf_url.startswith("http"):
            logger.info(f"Downloading authentic PDF from RBI: {pdf_url}")
            download_success = self._http_download_binary(pdf_url, pdf_path)

        if not download_success or not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < 100:
            logger.info(f"Generating formatted RBI PDF for {circular.get('circular_number')}")
            self.generate_formatted_pdf(circular, pdf_path)

        # Compute SHA-256 Checksum
        with open(pdf_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        circular["pdf_path"] = pdf_path
        circular["checksum"] = checksum
        circular["file_size_bytes"] = os.path.getsize(pdf_path)
        return pdf_path

    def generate_master_compendium_pdf(self, circulars: List[Dict[str, Any]], output_path: str) -> str:
        """
        Creates a Master Categorized Compendium PDF containing all scraped circulars
        with a Table of Contents, metadata summaries, and full text directives.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "MasterTitle",
            parent=styles["Title"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#1e3a8a"),
            alignment=1,
            spaceAfter=8
        )
        toc_title_style = ParagraphStyle(
            "TOCTitle",
            parent=styles["Heading2"],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=12,
            spaceAfter=8
        )
        toc_item_style = ParagraphStyle(
            "TOCItem",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#334155"),
            spaceAfter=4
        )
        circ_header_style = ParagraphStyle(
            "CircHeader",
            parent=styles["Heading1"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1e3a8a"),
            spaceBefore=16,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            "CircBody",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=6
        )

        elements = []

        # Master Cover Page
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<b>RESERVE BANK OF INDIA</b>", title_style))
        elements.append(Paragraph("<b>Official Circulars Compendium & Regulatory Knowledge Base</b>", ParagraphStyle(
            "CoverSub", parent=styles["Normal"], fontSize=13, leading=16, textColor=colors.HexColor("#475569"), alignment=1, spaceAfter=14
        )))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a8a"), spaceAfter=14))
        elements.append(Paragraph(f"<b>Generated on:</b> {datetime.now().strftime('%B %d, %Y - %H:%M:%S')}", ParagraphStyle(
            "CoverDate", parent=styles["Normal"], fontSize=10, leading=13, alignment=1, textColor=colors.HexColor("#64748b"), spaceAfter=20
        )))
        elements.append(Paragraph(f"<b>Total Scraped Directives:</b> {len(circulars)}", ParagraphStyle(
            "CoverTotal", parent=styles["Normal"], fontSize=11, leading=14, alignment=1, textColor=colors.HexColor("#0f172a"), spaceAfter=25
        )))

        # Table of Contents
        elements.append(Paragraph("<b>Table of Contents / Scraped Index</b>", toc_title_style))
        for idx, c in enumerate(circulars, 1):
            num = c.get("circular_number", f"Circular #{idx}")
            date = c.get("date_of_issue", "")
            subj = c.get("subject", "")
            safe_subj = subj[:75] + "..." if len(subj) > 75 else subj
            elements.append(Paragraph(f"<b>{idx}. [{date}] {num}</b> — {safe_subj}", toc_item_style))

        elements.append(Spacer(1, 20))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94a3b8"), spaceAfter=18))

        # Individual Circular Sections
        for idx, c in enumerate(circulars, 1):
            elements.append(Paragraph(f"<b>{idx}. {c.get('subject', '')}</b>", circ_header_style))
            elements.append(Paragraph(f"<b>Circular No:</b> {c.get('circular_number', '')} &nbsp;|&nbsp; <b>Date:</b> {c.get('date_of_issue', '')} &nbsp;|&nbsp; <b>Dept:</b> {c.get('department', '')}", ParagraphStyle(
                "SubMeta", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#475569"), spaceAfter=8
            )))
            
            # Content
            text = c.get("full_text", "")
            if text:
                paras = [p.strip() for p in text.split("\n\n") if p.strip()]
                for p in paras[:8]: # Keep each circular summary clean
                    safe_p = p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    elements.append(Paragraph(safe_p, body_style))

            elements.append(Spacer(1, 10))
            elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=12))

        doc.build(elements)
        logger.info(f"Master Compendium PDF created successfully at: {output_path}")
        return output_path

    def crawl_and_ingest(self, max_circulars: int = 15, db_session = None) -> Dict[str, Any]:
        """
        Complete end-to-end execution:
        1. Scrapes active circular index table from official RBI website.
        2. Fetches detail pages & authentic PDF download links.
        3. Downloads and generates authentic PDF documents.
        4. Compiles the Master Compendium PDF (`RBI_Circulars_Master_Compendium.pdf`).
        5. Ingests documents and chunks into PostgreSQL & Hybrid Vector Store.
        """
        logger.info(f"Fetching official RBI Circular Index from: {RBI_INDEX_URL}")
        index_html = self._http_get(RBI_INDEX_URL)
        if not index_html:
            raise RuntimeError(f"Failed to fetch index page from {RBI_INDEX_URL}")

        parsed_circulars = self.parse_circular_table(index_html)
        logger.info(f"Found {len(parsed_circulars)} circular entries on RBI Circular Index.")

        if max_circulars and max_circulars > 0:
            parsed_circulars = parsed_circulars[:max_circulars]

        detailed_circulars: List[Dict[str, Any]] = []
        pdf_paths: List[str] = []

        for idx, circ in enumerate(parsed_circulars, 1):
            logger.info(f"Processing ({idx}/{len(parsed_circulars)}): {circ.get('circular_number')} - {circ.get('subject')}")
            detailed = self.fetch_circular_details(circ)
            pdf_path = self.save_and_deliver_as_pdf(detailed)
            pdf_paths.append(pdf_path)
            detailed_circulars.append(detailed)
            time.sleep(0.3) # Rate limit politeness

        # Generate Master Compendium PDF
        master_pdf_path = os.path.join(self.output_dir, "RBI_Circulars_Master_Compendium.pdf")
        self.generate_master_compendium_pdf(detailed_circulars, master_pdf_path)

        # Ingest into PostgreSQL if db_session is provided
        ingested_count = 0
        if db_session:
            for circ in detailed_circulars:
                try:
                    # Check if already in database
                    existing = db_session.query(KnowledgeDocument).filter(
                        (KnowledgeDocument.notification_number == circ.get("notification_number")) |
                        (KnowledgeDocument.title == circ.get("subject"))
                    ).first()

                    if not existing:
                        doc = KnowledgeDocument(
                            title=circ.get("subject", "RBI Circular"),
                            notification_number=circ.get("notification_number", circ.get("circular_number")),
                            publication_date=circ.get("date_of_issue"),
                            effective_date=circ.get("date_of_issue"),
                            effective_from=circ.get("date_of_issue"),
                            regulator="RBI",
                            source="RBI",
                            source_url=circ.get("detail_url") or circ.get("pdf_url") or RBI_INDEX_URL,
                            document_type="pdf",
                            department=circ.get("department") or "Department of Regulation",
                            status="active",
                            file_path=circ.get("pdf_path"),
                            version="1.0",
                            checksum=circ.get("checksum"),
                            processing_status="indexed",
                            page_count=1,
                            is_ocr=False
                        )
                        db_session.add(doc)
                        db_session.commit()
                        db_session.refresh(doc)

                        # Chunk and index
                        text_content = circ.get("full_text") or circ.get("subject")
                        chunks = document_chunker.split_text_into_chunks(text_content, page_number=1)
                        for c in chunks:
                            chunk_obj = KnowledgeChunk(
                                document_id=doc.id,
                                page_number=c.get("page_number", 1),
                                chunk_index=c.get("chunk_index", 0),
                                section=c.get("section", "Main Circular"),
                                chunk_text=c.get("chunk_text"),
                                bounding_box_json=json.dumps({"x": 40, "y": 100, "width": 520, "height": 600}),
                                source_offsets_json=json.dumps({"char_start": 0, "char_end": len(c.get("chunk_text", ""))})
                            )
                            db_session.add(chunk_obj)
                        db_session.commit()
                        ingested_count += 1
                except Exception as e:
                    db_session.rollback()
                    logger.error(f"Error ingesting circular {circ.get('circular_number')}: {e}")

            # Rebuild hybrid vector store from PostgreSQL records
            from backend.ingestion.seed_rbi_kb import seed_database_and_vector_store
            seed_database_and_vector_store()
            redis_cache.flushall()

        return {
            "total_scraped": len(detailed_circulars),
            "ingested_to_db": ingested_count,
            "master_compendium_pdf": master_pdf_path,
            "individual_pdfs_dir": self.output_dir,
            "pdf_files": [os.path.basename(p) for p in pdf_paths],
            "circulars": detailed_circulars
        }

rbi_scraper = RBICircularScraper()
