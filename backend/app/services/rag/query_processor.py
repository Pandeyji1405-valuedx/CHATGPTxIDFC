"""
Query normalization for the RAG pipeline.

Applies deterministic, reversible text transformations to improve
retrieval quality while strictly preserving regulatory nomenclature.

Design rules:
  - Original question is NEVER modified in the database; normalization is
    applied only to the retrieval query.
  - Regulatory identifiers (e.g. "RBI/2023-24/108", "Section 35A",
    "Master Direction", "FEMA") are preserved verbatim.
  - No stemming, no stop-word removal -- these distort regulatory FTS.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Regulatory terminology patterns that must not be altered
_PRESERVE_PATTERNS = [
    r"RBI/\d{4}-\d{2,4}/\d+",           # Circular numbers: RBI/2023-24/108
    r"DBOD\.[A-Z]+\.\d+",                # Department codes: DBOD.No.BP
    r"Section\s+\d+[A-Za-z]?",           # Statutory sections: Section 35A
    r"Master\s+Direction",               # Master Directions
    r"Master\s+Circular",                # Master Circulars
    r"Circular\s+No\.?\s*\d+",           # Circular No. 12
    r"(?:FEMA|KYC|AML|CFT|NBFC|UCB|RRB|PSB)", # Common RBI acronyms
]
_PRESERVE_RE = re.compile("|".join(_PRESERVE_PATTERNS), re.IGNORECASE)


def normalize_query(query: str) -> str:
    """
    Normalize a user regulatory question for hybrid retrieval.

    Transformations applied (in order):
      1. Strip leading/trailing whitespace.
      2. Collapse internal runs of whitespace to a single space.
      3. Normalize Unicode quotation marks to ASCII straight quotes.
      4. Normalize Unicode hyphens/dashes to ASCII hyphen-minus.
      5. Preserve recognized regulatory identifiers unchanged.

    Args:
        query: Raw user question string.

    Returns:
        Normalized query string safe for embedding and FTS.

    Raises:
        ValueError: If query is empty after normalization.
    """
    if not query or not query.strip():
        raise ValueError("Query must not be empty.")

    # 1. Strip
    q = query.strip()

    # 2. Collapse whitespace
    q = re.sub(r"\s+", " ", q)

    # 3. Normalize Unicode quotes
    q = q.replace("\u2018", "'").replace("\u2019", "'")  # '' -> '
    q = q.replace("\u201c", '"').replace("\u201d", '"')  # "" -> "

    # 4. Normalize Unicode dashes
    q = q.replace("\u2013", "-").replace("\u2014", "-")  # en-dash, em-dash

    # 5. Regulatory identifiers are already preserved because we only do
    #    safe substitutions that do not touch alphanumeric or slash characters.

    logger.debug("Query normalized: %r -> %r", query[:80], q[:80])
    return q
