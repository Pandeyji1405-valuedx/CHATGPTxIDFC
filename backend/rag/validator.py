import re
from typing import List, Dict, Any, Tuple, Optional

class AnswerValidator:
    def __init__(self):
        pass

    def extract_factual_tokens(self, text: str) -> Dict[str, List[str]]:
        """Extracts critical factual tokens: circular codes, monetary numbers, percentages, dates."""
        # Monetary values e.g. ₹2 Lakh, ₹50,000, 2,00,000
        monetary = re.findall(r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:Lakh|Crore|Cr|L))?", text, re.IGNORECASE)
        # Percentages e.g. 40%, 80%, 9.5%
        percentages = re.findall(r"\b\d+(?:\.\d+)?\s*%", text)
        # Dates e.g. 2023, 2022-23, 01/04/2023
        dates = re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:19|20)\d{2}(?:-\d{2})?\b", text)
        # Circular / Regulatory IDs (specific banking prefixes)
        circulars = re.findall(r"(?:RBI/\d{4}-\d{2}/\d+|(?:DOR|DBR|DPSS|CEP|FIDD|DBOD|DBS|CIR|IDFC)\.[A-Z0-9\.\-/]+)", text, re.IGNORECASE)

        return {
            "monetary": list(set(monetary)),
            "percentages": list(set(percentages)),
            "dates": list(set(dates)),
            "circulars": list(set(circulars))
        }

    def check_conflicting_sources(self, retrieved_chunks: List[Dict[str, Any]]) -> Optional[str]:
        """
        Detects if multiple retrieved sources contain contrasting dates, circular versions, or policies.
        """
        if len(retrieved_chunks) < 2:
            return None

        # Group by different document titles
        doc_titles = list(set(c.get("doc_title", "") for c in retrieved_chunks if c.get("doc_title")))
        if len(doc_titles) > 1:
            # Check if any have differing dates or explicit version indicators
            notifs = [c.get("notification_number") for c in retrieved_chunks if c.get("notification_number")]
            if len(set(notifs)) > 1:
                return f"Multiple approved regulatory circulars ({', '.join(set(notifs))}) were retrieved. Results reflect the most authoritative provisions."

        return None

    def validate_grounding(
        self,
        answer: str,
        retrieved_context: str,
        source_type: str
    ) -> Tuple[bool, str, List[str]]:
        """
        Verifies that factual claims in the answer are grounded in the retrieved context.
        Returns: (is_valid, sanitized_answer, list_of_violations)
        """
        if source_type == "NO_SUPPORTED_SOURCE":
            return True, answer, []

        answer_facts = self.extract_factual_tokens(answer)
        context_upper = retrieved_context.upper()
        violations = []

        # Check circulars
        for raw_circ in answer_facts["circulars"]:
            circ = raw_circ.strip(".,;:()[]{}'\" \t\n")
            if circ and circ.upper() not in context_upper:
                violations.append(f"Regulatory circular '{circ}' not found in retrieved context.")

        # Check percentages
        for raw_pct in answer_facts["percentages"]:
            pct = raw_pct.strip(".,;:()[]{}'\" \t\n")
            clean_pct = pct.replace(" ", "")
            if clean_pct and clean_pct not in context_upper.replace(" ", ""):
                num_only = re.sub(r"[^\d\.]", "", clean_pct)
                if num_only and num_only not in context_upper:
                    violations.append(f"Percentage '{pct}' not verified by retrieved sources.")

        # Check monetary limits
        for raw_money in answer_facts["monetary"]:
            money = raw_money.strip(".,;:()[]{}'\" \t\n")
            digits = re.findall(r"\d+", money)
            if digits and not any(d in context_upper for d in digits):
                violations.append(f"Monetary figure '{money}' not verified by retrieved sources.")

        if violations:
            # If critical facts are unverified, fall back to controlled refusal
            fallback_answer = "I couldn't find sufficient verified information in the approved knowledge base or your conversation history to answer this accurately."
            return False, fallback_answer, violations

        return True, answer, []

answer_validator = AnswerValidator()
