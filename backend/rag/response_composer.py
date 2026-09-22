import re
from typing import List, Dict, Any, Tuple, Optional

class ResponseComposer:
    """
    Implements Response Composition, Formatting Linting and Anti-Leakage Sanitization
    as mandated by PRD Section 2, 5.2, 8.2 and FR-10.
    """

    # Internal leakage patterns to strip completely
    LEAKAGE_PATTERNS = [
        r"\[?S\d+\]?",                                              # e.g. [S1], S4, (S2)
        r"\bchunk[-_]?(?:id)?\s*=\s*[0-9a-zA-Z\-_]+",             # e.g. chunk_id=123e4567-e89b-12d3...
        r"\(?chunk[-_][0-9a-zA-Z\-_]+\)?",                         # e.g. chunk-42-3, (chunk-1)
        r"\[?score:?\s*\d+(?:\.\d+)?\]?",                          # e.g. [score: 0.985]
        r"\(?similarity\s*=\s*\d+(?:\.\d+)?\)?",                   # e.g. (similarity=0.88)
        r"\b(?:vector|cosine|tfidf)[-_]score:?\s*\d+(?:\.\d+)?\b", # e.g. vector_score: 0.94
        r"\bpgvector\b",
        r"\b(?:system|developer)\s+prompt:?.*?\n",                  # Prompt leakage
        r"\{[\"'](?:chunk_id|score|doc_id)[\"']:\s*.*?\}",         # JSON leakage
        r"Based on provided context\s*(?:S\d+:?)?",                # Context preamble leakage
        r"<!--.*?-->"                                               # HTML comments
    ]

    def sanitize_text(self, text: str) -> str:
        """Removes internal IDs, chunk markers, similarity scores, or raw reasoning."""
        if not text:
            return ""

        sanitized = text
        for pattern in self.LEAKAGE_PATTERNS:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

        # Clean multiple trailing spaces and normalize lines
        sanitized = re.sub(r"[ \t]+", " ", sanitized)
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
        return sanitized.strip()

    def format_verifiable_citation(self, citation: Dict[str, Any]) -> str:
        """
        Formats a citation according to PRD specification:
        'Document Title · Version/Effective Date · Page X'
        """
        title = citation.get("doc_title") or citation.get("document_title") or "Regulatory Guideline"
        notif = citation.get("notification_number")
        eff_date = citation.get("effective_date") or citation.get("publication_date")
        page = citation.get("page_number", 1)
        section = citation.get("section")

        parts = [title]
        if notif:
            parts.append(notif)
        if eff_date:
            parts.append(f"Eff. {eff_date}")
        if page:
            parts.append(f"Page {page}")
        if section and section != "General":
            parts.append(section)

        return " · ".join(parts)

    def compose_structured_response(
        self,
        raw_answer: str,
        citations: List[Dict[str, Any]],
        ambiguity_flags: Optional[List[Dict[str, Any]]] = None,
        query_intent: str = "GENERAL_FACTUAL"
    ) -> str:
        """
        Composes the finalized, polished response enforcing:
        1. Sanitization of all internal markers.
        2. Direct leading answer.
        3. Clean, readable single-idea bullets or tables.
        4. Explicit distinction of OCR ambiguity or uncertain claims.
        """
        sanitized = self.sanitize_text(raw_answer)

        # If the response is an abstention fallback, format cleanly with guidance
        if "couldn't find sufficient verified information" in sanitized or "insufficient verified information" in sanitized:
            return (
                f"{sanitized}\n\n"
                f"> **Guidance**: Please refine your query with specific circular numbers, regulatory topics "
                f"(e.g., *KYC, Digital Lending, SEBI LODR, IRDAI Cyber Security*), or select a specific regulator filter."
            )

        # Strip canned leading greetings and repetitive closing pleasantries on factual queries
        if query_intent != "CHITCHAT":
            sanitized = re.sub(
                r"^(?:hello(?:\s+there)?|hi|hey|greetings)[\s,!👋😊👍]*(?:i\s+(?:can\s+)?(?:certainly\s+)?(?:help|assist|explain|clarify)[^.\n]*[.\n]+)?",
                "",
                sanitized,
                flags=re.IGNORECASE
            ).strip()
            sanitized = re.sub(
                r"\n+(?:i\s+hope\s+this\s+(?:helps|clarifies)[^.\n]*[.\n]*|please\s+let\s+me\s+know\s+if\s+you\s+have\s+any\s+(?:more|further|other)\s+questions[^.\n]*[.\n]*|if\s+you\s+have\s+any\s+(?:other|further|more)\s+questions[,\s]+please\s+feel\s+free\s+to\s+ask[^.\n]*[.\n]*|feel\s+free\s+to\s+ask[^.\n]*[.\n]*)\s*$",
                "",
                sanitized,
                flags=re.IGNORECASE
            ).strip()

        # Append Ambiguity / Human Verification Notice if OCR ambiguities exist
        if ambiguity_flags:
            clean_flags = [
                f for f in ambiguity_flags
                if not re.match(r"^S\d+$|^chunk_|^att-|^[0-9a-f]{8}-", f.get("context_term", ""), re.IGNORECASE)
            ]
            amb_notes = []
            for flag in clean_flags[:3]:
                amb_notes.append(f"• `{flag.get('context_term')}` contains visually similar characters (`{flag.get('character_pair')}`).")
            
            if amb_notes:
                sanitized += (
                    f"\n\n---\n"
                    f"⚠️ **OCR Verification Notice**:\n"
                    + "\n".join(amb_notes) + "\n"
                    f"*Please verify these exact values against the original uploaded regulatory PDF.*"
                )

        return sanitized

    @classmethod
    def compose_response(
        cls,
        raw_answer: str,
        retrieved_chunks: List[Dict[str, Any]],
        requested_depth: str = "standard",
        ambiguity_flags: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Convenience class method returning (sanitized_answer, clean_citations)."""
        instance = cls()
        clean_answer = instance.compose_structured_response(
            raw_answer=raw_answer,
            citations=retrieved_chunks,
            ambiguity_flags=ambiguity_flags
        )
        
        clean_citations = []
        for c in retrieved_chunks:
            clean_citations.append({
                "id": c.get("id"),
                "document_id": c.get("document_id"),
                "doc_title": c.get("doc_title") or c.get("title"),
                "title": c.get("doc_title") or c.get("title"),
                "notification_number": c.get("notification_number"),
                "source": c.get("source") or c.get("regulator", "RBI"),
                "page_number": c.get("page_number", 1),
                "section": c.get("section", "General"),
                "chunk_text": c.get("chunk_text", ""),
                "source_offsets": c.get("source_offsets", {}),
                "bounding_box": c.get("bounding_box", {}),
                "publication_date": c.get("publication_date")
            })
        return clean_answer, clean_citations

response_composer = ResponseComposer()
