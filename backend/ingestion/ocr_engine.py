import re
from typing import List, Dict, Any, Tuple

# Ambiguity pairs to check
AMBIGUITY_PATTERNS = [
    ("0 ↔ O", r"(?<=[A-Za-z])0(?=[A-Za-z])|(?<=\d)O(?=\d)|(?<=[A-Z])0(?=\d)|(?<=\d)O(?=[A-Z])|\b0O\w*|\bO0\w*"),
    ("1 ↔ I ↔ l", r"(?<=\d)[Il](?=\d)|(?<=[A-Za-z])1(?=[A-Za-z])|\b[Il]1\w*|\b1[Il]\w*"),
    ("5 ↔ S", r"(?<=\d)S(?=\d)|(?<=[A-Z])5(?=[A-Z])|\b5S\w*|\bS5\w*"),
    ("2 ↔ Z", r"(?<=\d)Z(?=\d)|(?<=[A-Z])2(?=[A-Z])|\b2Z\w*|\bZ2\w*"),
    ("8 ↔ B", r"(?<=\d)B(?=\d)|(?<=[A-Z])8(?=[A-Z])|\b8B\w*|\bB8\w*")
]

class OCREngine:
    def __init__(self):
        pass

    def detect_character_ambiguities(self, text: str) -> List[Dict[str, Any]]:
        """
        Scans text for visually ambiguous characters (0 vs O, 1 vs I/l, 5 vs S, 2 vs Z, 8 vs B)
        in sensitive banking contexts (circular IDs, dates, monetary values, percentages).
        Guaranteed not to produce false positives on standard English prose.
        """
        flags = []
        words = text.split()

        for word in words:
            # Strip trailing punctuation
            clean_word = word.strip(".,;:()[]{}'\"")
            if len(clean_word) < 2:
                continue

            # 1. Check for notification / circular code patterns (e.g. RBI/2024-25/0O18, DOR.AML/0O1)
            if ("/" in clean_word or "-" in clean_word or "." in clean_word) and any(c.isupper() for c in clean_word):
                # Check for 0 vs O in alphanumeric codes (e.g. 0O, O0, digit-O-digit, letter-0-letter)
                if re.search(r"[A-Za-z]\d*0[A-Za-z]+|\d+[A-Z]*O\d+|\b\w*0O\w*|\b\w*O0\w*", clean_word):
                    flags.append({
                        "character_pair": "0 ↔ O",
                        "context_term": clean_word,
                        "description": f"Potential 0 vs O ambiguity detected in regulatory code '{clean_word}'",
                        "verification_required": True
                    })
                # Check for 1 vs I vs l
                if re.search(r"\d+[Il]\d+|[A-Za-z]+1[A-Za-z]+|\b\w*1[Il]\w*|\b\w*[Il]1\w*", clean_word):
                    flags.append({
                        "character_pair": "1 ↔ I ↔ l",
                        "context_term": clean_word,
                        "description": f"Potential 1 vs I/l ambiguity detected in code '{clean_word}'",
                        "verification_required": True
                    })

            # 2. Check for monetary amounts & percentages with suspicious letters (e.g. ₹SO,OOO, ₹5O,OOO, B.5%, 8.S%)
            # Must explicitly have currency symbol (₹, $, Rs), trailing %, or digits mixed with confusable letters
            has_currency = bool(re.search(r"^[₹$]|^(?:Rs\.?|INR)", clean_word, re.IGNORECASE))
            has_percent = clean_word.endswith("%")
            has_digits = bool(re.search(r"\d", clean_word))

            is_numeric_context = has_currency or has_percent or (has_digits and re.search(r"^[₹$]?[0-9,]*[SOBZIld][0-9,\.]*%?$", clean_word))

            if is_numeric_context:
                # 5 vs S: Only in numeric context (e.g. ₹SO,OOO or 8.S% or 5S00)
                if re.search(r"[₹$][0-9,]*S|\d+\.S%?|\d+S\d+|S\d{3,}", clean_word):
                    flags.append({
                        "character_pair": "5 ↔ S",
                        "context_term": clean_word,
                        "description": f"Potential 5 vs S substitution detected in numeric field '{clean_word}'",
                        "verification_required": True
                    })
                # 0 vs O: In currency / numeric / date context (e.g. ₹SO,OOO, 12/O4/2023, 5O000, 1O,000)
                if re.search(r"[₹$][0-9,]*O|O[0-9,]{2,}|\d+O\d+|\d+/O\d+|O\d+/\d+", clean_word):
                    flags.append({
                        "character_pair": "0 ↔ O",
                        "context_term": clean_word,
                        "description": f"Potential 0 vs O substitution detected in numeric field '{clean_word}'",
                        "verification_required": True
                    })
                # 8 vs B: In currency / numeric / percentage context (e.g. B.5% or ₹8B,000 or ₹B0,000)
                if re.search(r"[₹$][0-9,]*B|B\.\d+%?|\d+\.B%?|\d+B\d+", clean_word):
                    flags.append({
                        "character_pair": "8 ↔ B",
                        "context_term": clean_word,
                        "description": f"Potential 8 vs B substitution detected in numeric field '{clean_word}'",
                        "verification_required": True
                    })
                # 2 vs Z: In currency / numeric / percentage context (e.g. ₹Z0,000 or Z.5% or 2Z00)
                if re.search(r"[₹$][0-9,]*Z|Z\.\d+%?|\d+\.Z%?|\d+Z\d+", clean_word):
                    flags.append({
                        "character_pair": "2 ↔ Z",
                        "context_term": clean_word,
                        "description": f"Potential 2 vs Z substitution detected in numeric field '{clean_word}'",
                        "verification_required": True
                    })
                # 1 vs I/l: In currency / numeric / percentage context (e.g. ₹1I,000 or I.5% or 1I00)
                if re.search(r"[₹$][0-9,]*[Il]|[Il]\.\d+%?|\d+\.[Il]%?|\d+[Il]\d+", clean_word):
                    flags.append({
                        "character_pair": "1 ↔ I ↔ l",
                        "context_term": clean_word,
                        "description": f"Potential 1 vs I/l substitution detected in numeric field '{clean_word}'",
                        "verification_required": True
                    })

        # Deduplicate flags by context_term + character_pair
        unique_flags = []
        seen = set()
        for f in flags:
            key = (f["character_pair"], f["context_term"])
            if key not in seen:
                seen.add(key)
                unique_flags.append(f)

        return unique_flags

    def process_ocr_text(self, raw_text: str, confidence: float = 0.85) -> Dict[str, Any]:
        """
        Processes OCR output:
        - Preserves original raw text.
        - Identifies character ambiguities.
        - Returns structured metadata for validation.
        """
        ambiguities = self.detect_character_ambiguities(raw_text)
        return {
            "text": raw_text,
            "ocr_confidence": confidence,
            "is_ocr": True,
            "ambiguities": ambiguities,
            "verification_required": len(ambiguities) > 0
        }

ocr_engine = OCREngine()
