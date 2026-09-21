"""
Deterministic text cleaning and normalization for RBI regulatory text (Phase 3).

Rules:
  - Preserves exact regulatory phrasing, statutory section references, and dates
  - Strips non-printable control characters, soft hyphens, and ligature anomalies
  - Collapses redundant whitespace and runs of blank lines
  - Completely deterministic: same input text always produces identical cleaned text
"""

import re
import unicodedata

# Regex patterns for deterministic cleanup
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HORIZONTAL_WHITESPACE = re.compile(r"[ \t\f\v]+")
_EXCESSIVE_NEWLINES = re.compile(r"\n{3,}")
_SOFT_HYPHEN = re.compile(r"\xad")

# Standard typographic ligatures to ASCII replacements
_LIGATURE_MAP = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "ft",
    "\ufb06": "st",
}


def clean_regulatory_text(text: str) -> str:
    """
    Deterministically normalize extracted PDF text.

    Args:
        text: Raw text string from a PDF page.

    Returns:
        Normalized clean string preserving exact legal and regulatory terminology.
    """
    if not text:
        return ""

    # 1. Unicode normalization (NFKC decomposes compatibility characters like ligatures)
    normalized = unicodedata.normalize("NFKC", text)

    # 2. Replace any remaining known typographic ligatures
    for lig, replacement in _LIGATURE_MAP.items():
        normalized = normalized.replace(lig, replacement)

    # 3. Strip soft hyphens
    normalized = _SOFT_HYPHEN.sub("", normalized)

    # 4. Remove unwanted control characters (preserve standard \n, \t, \r)
    normalized = _CONTROL_CHAR_PATTERN.sub("", normalized)

    # 5. Standardize line endings (\r\n -> \n, \r -> \n)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 6. Normalize trailing whitespace on each line
    lines = [_HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)

    # 7. Collapse runs of 3+ blank lines down to 2
    normalized = _EXCESSIVE_NEWLINES.sub("\n\n", normalized)

    return normalized.strip()
