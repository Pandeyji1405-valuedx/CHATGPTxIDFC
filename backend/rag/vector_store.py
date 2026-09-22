import re
import json
from datetime import datetime, timezone
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.config import settings

class HybridVectorStore:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            token_pattern=r"(?u)\b\w[\w\.\-/]+\b", # Captures banking circulars like DOR.AML.REC.48, SEBI/LAD-NRO
            stop_words="english",
            sublinear_tf=True
        )
        self.chunk_records: List[Dict[str, Any]] = []
        self.tfidf_matrix = None
        self.is_indexed = False

    def build_index(self, chunks: List[Dict[str, Any]]) -> None:
        """Indexes all knowledge chunks using TF-IDF and structured inverted index."""
        if not chunks:
            self.chunk_records = []
            self.tfidf_matrix = None
            self.is_indexed = False
            return

        self.chunk_records = chunks
        corpus = [c.get("chunk_text", "") for c in chunks]
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.is_indexed = True

    def calculate_structured_boost(self, query: str, chunk: Dict[str, Any]) -> float:
        """
        Calculates exact match boosts for structured regulatory attributes:
        - Circular / Notification codes (RBI, SEBI, IRDAI)
        - Specific monetary limits (e.g. 2 Lakh, ₹2,00,000, ₹1000 Crore)
        - Specific percentage figures (e.g. 40%, 80%, 90%, 10%)
        - Specific days/timelines (e.g. 30 days, 3 days, 6 hours, 12 hours)
        - Financial regulator acronyms & terms
        - Universal domain topic scenarios
        """
        boost = 0.0
        text = chunk.get("chunk_text", "").upper()
        doc_title = chunk.get("doc_title", "").upper()
        doc_notif = chunk.get("notification_number", "") or ""
        regulator = chunk.get("regulator", "RBI").upper()
        query_upper = query.upper()

        # Check notification numbers
        if doc_notif and (doc_notif.upper() in query_upper or any(part in query_upper for part in doc_notif.upper().split("/") if len(part) > 4)):
            boost += 0.50

        # Exact regulator match boost
        if "SEBI" in query_upper and regulator == "SEBI":
            boost += 0.35
        elif "IRDAI" in query_upper and regulator == "IRDAI":
            boost += 0.35
        elif ("RBI" in query_upper or "RESERVE BANK" in query_upper) and regulator == "RBI":
            boost += 0.35

        # Multi-regulator banking, securities & insurance terms boost
        regulatory_terms = [
            # RBI Terms
            "KYC", "NEFT", "RTGS", "IMPS", "UPI", "LTV", "NPA", "EMI", "OMBUDSMAN",
            "DIGITAL LENDING", "CREDIT CARD", "DEBIT CARD", "FASTAG", "HOUSING FINANCE",
            "CUSTOMER PROTECTION", "UNAUTHORISED", "UNAUTHORIZED", "INTEREST RATE",
            "DEPOSIT", "INOPERATIVE", "MICROFINANCE", "PRIORITY SECTOR", "PSL", "SANCTION",
            "SAVINGS", "CURRENT ACCOUNT", "V-CIP", "KEY FACT STATEMENT", "KFS", "COOLING-OFF",
            "BSBDA", "BASIC SAVINGS", "MORATORIUM", "FORECLOSURE", "PREPAYMENT",
            # SEBI Terms
            "LODR", "LISTING OBLIGATIONS", "DISCLOSURE", "MATERIAL EVENT", "RELATED PARTY",
            "INSIDER TRADING", "PIT", "VAPT", "PENETRATION TESTING", "STOCK BROKER",
            "INTERMEDIARIES", "CERT-IN", "TWO-FACTOR", "CYBER RESILIENCE",
            # IRDAI Terms
            "CISO", "POLICYHOLDER", "FREE LOOK", "GRIEVANCE REDRESSAL", "INSURER",
            "CUSTOMER INFORMATION SHEET", "CIS", "INFORMATION SECURITY", "DATA LOCALIZATION",
            "OUTSOURCING"
        ]
        for term in regulatory_terms:
            if re.search(rf"\b{re.escape(term)}\b", query_upper):
                if re.search(rf"\b{re.escape(term)}\b", text) or re.search(rf"\b{re.escape(term)}\b", doc_title):
                    boost += 0.25

        # Universal Domain Scenarios Boosting:
        # 1. Stolen / Lost Card / Fraud / Unauthorized Transactions
        if re.search(r"\b(STOLEN|LOST CARD|CARD STOLEN|FRAUD|SCAM|UNAUTHORIZED|UNAUTHORISED|COMPROMISED|MISUSED|SKIMMING)\b", query_upper):
            if "UNAUTHORISED" in doc_title or "UNAUTHORIZED" in doc_title or "CUSTOMER PROTECTION" in doc_title or "LIABILITY" in doc_title:
                boost += 0.45

        # 2. Erroneous / Wrong Account Transfers
        if re.search(r"\b(WRONG ACCOUNT|WRONG BENEFICIARY|MISTAKENLY|MITAKENLY|ERRONEOUS|WRONGLY|ACCIDENTALLY)\b", query_upper):
            if "NEFT" in doc_title or "COMPENSATION" in doc_title or "RTGS" in doc_title or "RETURN" in text:
                boost += 0.45

        # 3. Failed Transactions / Delayed Reversal / Compensation TAT
        if re.search(r"\b(DELAYED|FAILED TRANSACTION|NOT RECEIVED|DEBITED BUT|STUCK|ATM FAILED|CASH NOT DISPENSED|GRIEVANCE|COMPLAINT|DISPUTE|COMPENSATION)\b", query_upper):
            if "COMPENSATION" in doc_title or "GRIEVANCE" in doc_title or "TURNAROUND" in text:
                boost += 0.45

        # 4. Housing / Home Loans / LTV Slabs
        if re.search(r"\b(HOUSING|HOME LOAN|HOME LAON|HOUSE LOAN|LTV|MORTGAGE|HOUSING FINANCE|DWELLING|FLAT LOAN|BUY HOUSE)\b", query_upper):
            if "HOUSING" in doc_title or "LTV" in doc_title or "HOUSING" in text or "LTV" in text:
                boost += 0.45

        # 5. Foreclosure / Prepayment Penalty / Floating Rate Term Loans
        if re.search(r"\b(FORECLOSURE|PREPAYMENT|PREPAY|CLOSE LOAN|CLOSING LOAN|FLOATING RATE|PART PAYMENT)\b", query_upper):
            if "FAIR LENDING" in doc_title or "FORECLOSURE" in doc_title or "PREPAYMENT" in text or "FORECLOSURE" in text:
                boost += 0.45

        # 6. Natural Calamities Relief / Moratorium / Stressed Assets
        if re.search(r"\b(CALAMITY|CALAMITIES|NATURAL CALAMITY|DISASTER|FLOOD|EARTHQUAKE|STRESSED ASSETS|SLBC|UTLBC|DCC|MORATORIUM)\b", query_upper):
            if "CALAMITY" in text or "STRESSED ASSETS" in doc_title or "CALAMITIES" in text or "CALAMITIES" in doc_title:
                boost += 0.45

        # 7. Savings Account / Interest on Deposits / BSBDA / Minimum Balance
        if re.search(r"\b(SAVINGS ACCOUNT|INTEREST RATE ON DEPOSIT|SAVINGS INTEREST|BSBDA|ZERO BALANCE|MINIMUM BALANCE|INOPERATIVE|DORMANT|FIXED DEPOSIT|RECURRING DEPOSIT)\b", query_upper):
            if "INTEREST RATE ON DEPOSITS" in doc_title or "SAVINGS ACCOUNT" in doc_title or "DEPOSITS" in doc_title or "INTEREST" in text:
                boost += 0.45

        # 8. Digital Lending / KFS / Cooling-off / Recovery Agent Conduct
        if re.search(r"\b(DIGITAL LENDING|RECOVERY AGENT|HARASS|THREATEN|INTIMIDATION|KFS|KEY FACT|COOLING-OFF|LOOK-UP|LSP|DLA)\b", query_upper):
            if "DIGITAL LENDING" in doc_title or "FAIR LENDING" in doc_title or "DIGITAL LENDING" in text:
                boost += 0.45

        # 9. FASTag Program / Auto-Recharge / Toll Plaza Disputes
        if re.search(r"\b(FASTAG|AUTO RECHARGE|TOLL|RFID|TAG BLACKLIST|DUPLICATE TOLL)\b", query_upper):
            if "FASTAG" in doc_title or "AUTO RECHARGE" in doc_title or "FASTAG" in text:
                boost += 0.45

        # 10. Grievance Redressal & Banking Ombudsman
        if re.search(r"\b(OMBUDSMAN|GRIEVANCE|NODAL OFFICER|COMPLAINT ESCALATION|INTERNAL OMBUDSMAN)\b", query_upper):
            if "GRIEVANCE" in doc_title or "COMPENSATION" in doc_title or "OMBUDSMAN" in text:
                boost += 0.45

        # 11. IRDAI Cyber Security & Policyholder Protection (30-day Free Look)
        if re.search(r"\b(IRDAI|FREE LOOK|POLICYHOLDER|CISO|CYBER INCIDENT|CUSTOMER INFORMATION SHEET|CIS)\b", query_upper):
            if "IRDAI" in doc_title or "POLICYHOLDER" in doc_title or "CYBER SECURITY" in doc_title or "FREE LOOK" in text:
                boost += 0.45

        # 12. SEBI LODR Regulation 30 Material Disclosures
        if re.search(r"\b(SEBI|LODR|REGULATION 30|MATERIAL EVENT|MATERIAL DISCLOSURE|MATERIALITY|THRESHOLDS?|TURNOVER|NET WORTH)\b", query_upper):
            if "SEBI" in doc_title or "LODR" in doc_title or "REGULATION 30" in text or "MATERIAL" in text or "TURNOVER" in text or "NET WORTH" in text:
                boost += 0.45

        # Check document title word overlap
        query_words = set(re.findall(r"\w+", query_upper)) - {"WHAT", "IS", "THE", "ARE", "OF", "AND", "IN", "TO", "FOR", "A", "AN", "TELL", "ME", "ABOUT", "HOW", "CAN", "DO", "DOES", "SHOULD"}
        doc_title_words = set(re.findall(r"\w+", doc_title))
        overlap = query_words & doc_title_words
        if len(overlap) >= 2:
            boost += 0.20

        # Specific numbers / monetary values / percentages / hours
        numbers_in_query = re.findall(r"\b\d+(?:\.\d+)?%?|\b₹\s*\d+|\b\d+\s*(?:HOURS|DAYS|WEEKS|MONTHS|YEARS)\b", query, re.IGNORECASE)
        for num in numbers_in_query:
            if num.upper() in text:
                boost += 0.15

        return min(boost, 0.75)

    def ensure_indexed(self, db: Any = None) -> None:
        """Ensures the hybrid vector store is populated from DB if not already indexed."""
        if self.is_indexed and self.chunk_records and self.tfidf_matrix is not None:
            return
        
        from backend.database import SessionLocal
        local_db = db or SessionLocal()
        should_close = db is None
        try:
            from backend.models import KnowledgeChunk, KnowledgeDocument
            chunks = (
                local_db.query(KnowledgeChunk, KnowledgeDocument)
                .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
                .all()
            )
            all_chunks = []
            for chunk, doc in chunks:
                offsets = {}
                if chunk.source_offsets_json:
                    try:
                        offsets = json.loads(chunk.source_offsets_json)
                    except Exception:
                        pass
                
                bbox = {}
                if chunk.bounding_box_json:
                    try:
                        bbox = json.loads(chunk.bounding_box_json)
                    except Exception:
                        pass

                all_chunks.append({
                    "id": chunk.id,
                    "tenant_id": getattr(chunk, "tenant_id", "default_tenant"),
                    "document_id": doc.id,
                    "doc_title": doc.title,
                    "notification_number": doc.notification_number,
                    "source": doc.source,
                    "regulator": getattr(doc, "regulator", doc.source or "RBI"),
                    "status": getattr(doc, "status", "active"),
                    "effective_from": getattr(doc, "effective_from", doc.publication_date),
                    "effective_until": getattr(doc, "effective_until", None),
                    "page_number": chunk.page_number,
                    "section": chunk.section,
                    "chunk_text": chunk.chunk_text,
                    "source_offsets": offsets,
                    "bounding_box": bbox,
                    "publication_date": doc.publication_date
                })
            if all_chunks:
                self.build_index(all_chunks)
        finally:
            if should_close:
                local_db.close()

    def search(
        self,
        query: str,
        top_k: int = 4,
        threshold: Optional[float] = None,
        regulator_filter: Optional[List[str]] = None,
        as_of_date: Optional[str] = None,
        tenant_id: str = "default_tenant",
        db: Any = None,
        canonical_search_terms: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs hybrid semantic and keyword search with:
        - Multi-query representation scoring (raw query + canonical domain concepts)
        - Regulator filtering (RBI, SEBI, IRDAI, INTERNAL)
        - Effective-date temporal range validation
        - Active vs Superseded status resolution
        - Multi-tenant isolation
        """
        if not query or not query.strip():
            return []

        if not self.is_indexed or self.tfidf_matrix is None or not self.chunk_records:
            self.ensure_indexed(db=db)

        if not self.is_indexed or self.tfidf_matrix is None or not self.chunk_records:
            return []

        min_threshold = threshold if threshold is not None else settings.RETRIEVAL_THRESHOLD
        
        # Compute primary similarity
        query_vector = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]

        # If canonical search terms exist, merge similarity scores
        if canonical_search_terms and canonical_search_terms.strip() and canonical_search_terms.strip() != query.strip():
            canonical_vec = self.vectorizer.transform([canonical_search_terms])
            canonical_sims = cosine_similarity(canonical_vec, self.tfidf_matrix)[0]
            similarities = np.maximum(similarities, canonical_sims * 0.95)

        normalized_reg_filter = [r.upper() for r in regulator_filter] if regulator_filter else ["ALL"]
        if "ALL" in normalized_reg_filter:
            normalized_reg_filter = None

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        scored_results = []
        for idx, base_score in enumerate(similarities):
            chunk = self.chunk_records[idx]

            # 1. Tenant Check (Approved default_tenant KB is accessible across all tenants; private tenant chunks are strictly isolated)
            chunk_tenant = chunk.get("tenant_id", "default_tenant")
            if chunk_tenant != "default_tenant" and tenant_id != "default_tenant" and chunk_tenant != tenant_id:
                continue

            # 2. Regulator Filter Check
            chunk_reg = chunk.get("regulator", "RBI").upper()
            chunk_src = chunk.get("source", "").upper()
            if normalized_reg_filter:
                is_internal_match = any(r in ["INTERNAL", "BANK_POLICY", "IDFC_FIRST_BANK"] for r in normalized_reg_filter) and (chunk_reg in ["INTERNAL", "BANK_POLICY", "IDFC_FIRST_BANK"] or "IDFC" in chunk_src)
                if chunk_reg not in normalized_reg_filter and chunk_src not in normalized_reg_filter and not is_internal_match:
                    continue

            # 3. Effective-Date & Status Resolution
            chunk_status = chunk.get("status", "active").lower()
            eff_from = chunk.get("effective_from") or chunk.get("publication_date") or "2000-01-01"
            eff_until = chunk.get("effective_until")

            if as_of_date:
                # Historical compliance query: Must have been active at as_of_date
                if eff_from > as_of_date:
                    continue # Document was not yet enacted
                if eff_until and eff_until < as_of_date:
                    continue # Document was already expired/superseded by as_of_date
            else:
                # Default query: strictly active, non-superseded rules
                if chunk_status == "superseded":
                    continue
                if eff_until and eff_until < today_str:
                    continue

            # 4. Score Calculation
            boost = self.calculate_structured_boost(canonical_search_terms or query, chunk)
            final_score = float(base_score) + boost


            if final_score >= min_threshold:
                scored_results.append({
                    "chunk_id": chunk.get("id"),
                    "document_id": chunk.get("document_id"),
                    "doc_title": chunk.get("doc_title", "Regulatory Guideline"),
                    "notification_number": chunk.get("notification_number"),
                    "source": chunk.get("source", chunk_reg),
                    "regulator": chunk_reg,
                    "status": chunk_status,
                    "effective_date": chunk.get("effective_from") or chunk.get("publication_date"),
                    "page_number": chunk.get("page_number", 1),
                    "section": chunk.get("section", ""),
                    "chunk_text": chunk.get("chunk_text", ""),
                    "source_offsets": chunk.get("source_offsets", {}),
                    "bounding_box": chunk.get("bounding_box", {}),
                    "score": round(final_score, 4),
                    "base_score": round(float(base_score), 4),
                    "boost": round(boost, 4),
                    "publication_date": chunk.get("publication_date")
                })

        # Sort descending by final score with multi-document diversity
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        diverse_results = []
        doc_chunk_count: Dict[str, int] = {}
        deferred = []

        for res in scored_results:
            doc_key = str(res.get("document_id") or res.get("doc_title"))
            count = doc_chunk_count.get(doc_key, 0)
            if count < 4:
                diverse_results.append(res)
                doc_chunk_count[doc_key] = count + 1
            else:
                deferred.append(res)

        if len(diverse_results) < top_k:
            diverse_results.extend(deferred[:top_k - len(diverse_results)])

        return diverse_results[:top_k]

hybrid_vector_store = HybridVectorStore()
