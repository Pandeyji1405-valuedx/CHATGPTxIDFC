"""
Citation Grounding — Phase 4 RAG Pipeline.

The backend is the sole authority for citation metadata.
Gemini provides only chunk_id references; this module validates those
references against the actual retrieved evidence set and constructs
authoritative CitationResponse objects from trusted database records.

Design rules:
  - Any chunk_id returned by Gemini that is NOT in the retrieved set
    is silently discarded (prevents hallucinated citations).
  - All fields (document_title, circular_number, page_number, version_number,
    section) are populated from the RetrievedChunk record, never from Gemini.
  - Deduplication: each chunk_id appears at most once in the citation list.
"""

import logging
import uuid
from typing import Dict, List

from app.schemas.chat import CitationResponse
from app.services.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


def validate_and_build_citations(
    citation_ids: List[str],
    candidate_chunks: List[RetrievedChunk],
) -> List[CitationResponse]:
    """
    Build verified CitationResponse objects from Gemini's claimed citation_ids.

    Args:
        citation_ids:     List of chunk_id strings returned by Gemini.
        candidate_chunks: The actual retrieved (and reranked) chunk evidence set.

    Returns:
        List of CitationResponse objects for chunk_ids that exist in the
        evidence set.  Unknown IDs are discarded with a warning log.
    """
    # Index retrieved chunks by their chunk_id for O(1) lookup
    evidence_index: Dict[str, RetrievedChunk] = {
        c.chunk_id: c for c in candidate_chunks
    }

    citations: List[CitationResponse] = []
    seen_ids: set = set()

    for cid in citation_ids:
        cid = cid.strip()
        if not cid:
            continue

        if cid in seen_ids:
            continue  # Deduplicate

        if cid not in evidence_index:
            logger.warning(
                "Gemini cited chunk_id %r which is not in the retrieved evidence set. "
                "Discarding (potential hallucination).",
                cid,
            )
            continue

        chunk = evidence_index[cid]
        seen_ids.add(cid)

        # Safely parse UUIDs; skip if malformed
        try:
            doc_uuid = uuid.UUID(chunk.document_id)
            ver_uuid = uuid.UUID(chunk.version_id)
        except (ValueError, AttributeError) as exc:
            logger.warning("Malformed UUID in chunk %r: %s", cid, exc)
            continue

        citations.append(
            CitationResponse(
                document_id=doc_uuid,
                version_id=ver_uuid,
                document_title=chunk.document_title or "Unknown Document",
                circular_number=chunk.circular_number or None,
                version_number=chunk.version_number or 1,
                page_number=chunk.page_number or 0,
                section=chunk.section or None,
                chunk_id=cid,
            )
        )

    logger.debug(
        "Citation grounding: Gemini cited %d ids, %d verified, %d discarded.",
        len(citation_ids),
        len(citations),
        len(citation_ids) - len(citations),
    )
    return citations
