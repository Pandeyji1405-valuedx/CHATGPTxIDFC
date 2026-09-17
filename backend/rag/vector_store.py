import re
import json
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from backend.config import settings

class HybridVectorStore:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            token_pattern=r"(?u)\b\w[\w\.\-/]+\b", # Captures banking circulars like DOR.AML.REC.48
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
        corpus = [c["chunk_text"] for c in chunks]
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.is_indexed = True

    def calculate_structured_boost(self, query: str, chunk: Dict[str, Any]) -> float:
        """
        Calculates exact match boosts for structured banking attributes:
        - Circular / Notification codes
        - Specific monetary limits (e.g. 2 Lakh, ₹2,00,000)
        - Specific percentage figures (e.g. 40%, 80%, 90%)
        - Specific days/timelines (e.g. 30 days, 3 days, 24x7)
        - Banking acronyms
        """
        boost = 0.0
        text = chunk["chunk_text"].upper()
        doc_meta = chunk.get("metadata", {})
        doc_title = chunk.get("doc_title", "").upper()
        doc_notif = chunk.get("notification_number", "") or ""
        query_upper = query.upper()

        # Check notification numbers
        if doc_notif and (doc_notif.upper() in query_upper or any(part in query_upper for part in doc_notif.upper().split("/") if len(part) > 4)):
            boost += 0.50

        # Exact banking terms boost
        banking_terms = [
            "KYC", "NEFT", "RTGS", "IMPS", "UPI", "LTV", "NPA", "EMI", "OMBUDSMAN",
            "DIGITAL LENDING", "CREDIT CARD", "DEBIT CARD", "FASTAG", "HOUSING FINANCE",
            "CUSTOMER PROTECTION", "UNAUTHORISED", "UNAUTHORIZED", "INTEREST RATE",
            "DEPOSIT", "INOPERATIVE", "MICROFINANCE", "PRIORITY SECTOR", "PSL", "SANCTION",
            "SAVINGS", "CURRENT ACCOUNT", "INTEREST", "ADVERSARIAL"
        ]
        for term in banking_terms:
            if re.search(rf"\b{re.escape(term)}\b", query_upper):
                if re.search(rf"\b{re.escape(term)}\b", text) or re.search(rf"\b{re.escape(term)}\b", doc_title):
                    boost += 0.25

        # Check document title word overlap
        query_words = set(re.findall(r"\w+", query_upper)) - {"WHAT", "IS", "THE", "ARE", "OF", "AND", "IN", "TO", "FOR", "A", "AN", "TELL", "ME", "ABOUT", "HOW"}
        doc_title_words = set(re.findall(r"\w+", doc_title))
        overlap = query_words & doc_title_words
        if len(overlap) >= 2:
            boost += 0.20

        # Specific numbers / monetary values / percentages
        numbers_in_query = re.findall(r"\b\d+(?:\.\d+)?%?|\b₹\s*\d+", query)
        for num in numbers_in_query:
            if num in chunk["chunk_text"]:
                boost += 0.15

        return min(boost, 0.60)

    def search(
        self,
        query: str,
        top_k: int = 4,
        threshold: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs hybrid semantic and keyword search.
        Returns chunks meeting or exceeding the retrieval threshold.
        """
        if not self.is_indexed or self.tfidf_matrix is None or not self.chunk_records:
            return []

        min_threshold = threshold if threshold is not None else settings.RETRIEVAL_THRESHOLD
        query_vector = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, self.tfidf_matrix)[0]

        scored_results = []
        for idx, base_score in enumerate(similarities):
            chunk = self.chunk_records[idx]
            boost = self.calculate_structured_boost(query, chunk)
            final_score = float(base_score) + boost

            if final_score >= min_threshold:
                scored_results.append({
                    "chunk_id": chunk.get("id"),
                    "document_id": chunk.get("document_id"),
                    "doc_title": chunk.get("doc_title", "RBI Guideline"),
                    "notification_number": chunk.get("notification_number"),
                    "source": chunk.get("source", "RBI"),
                    "page_number": chunk.get("page_number", 1),
                    "section": chunk.get("section", ""),
                    "chunk_text": chunk.get("chunk_text", ""),
                    "score": round(final_score, 4),
                    "base_score": round(float(base_score), 4),
                    "boost": round(boost, 4),
                    "publication_date": chunk.get("publication_date")
                })

        # Sort descending by final score
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

hybrid_vector_store = HybridVectorStore()
