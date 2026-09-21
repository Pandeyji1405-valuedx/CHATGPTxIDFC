"""
Deterministic text chunking service for RBI regulatory documents (Phase 3).

Splits cleaned page texts into structured chunks while preserving:
  - Exact page boundaries (a chunk never spans across multiple pages)
  - Citation metadata (document_id, version_id, page_number, circular_number, topic)
  - Deterministic chunk IDs: doc_{document_id}_v{version_number}_p{page_number}_c{chunk_index}
"""

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

from app.services.pdf.extractor import ExtractedPage


@dataclass(frozen=True)
class DocumentChunk:
    """
    Structured text chunk prepared for vector embedding and indexing.

    Attributes:
        chunk_id: Deterministic unique chunk identifier.
        text: Normalized chunk text content.
        page_number: Original PDF page number (1-indexed).
        chunk_index: 0-indexed position within the page.
        metadata: Serialized dictionary for ChromaDB filtering & citation.
    """
    chunk_id: str
    text: str
    page_number: int
    chunk_index: int
    metadata: Dict[str, Any]


def _split_text_into_chunks(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
) -> List[str]:
    """
    Split text into chunks using paragraph and sentence boundaries.

    Args:
        text: Page text string.
        chunk_size: Target maximum characters per chunk.
        chunk_overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        List of chunk text strings.
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    # Split into paragraphs first
    paragraphs = text.split("\n\n")
    raw_chunks: List[str] = []
    current_chunk: List[str] = []
    current_len = 0

    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue

        # If single paragraph exceeds chunk_size, split by sentences or lines
        if len(para_clean) > chunk_size:
            # Flush existing buffer
            if current_chunk:
                raw_chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_len = 0

            # Split large paragraph by sentence or line
            sentences = [s.strip() for s in para_clean.replace("\n", " ").split(". ") if s.strip()]
            s_buf: List[str] = []
            s_len = 0
            for sentence in sentences:
                s_text = sentence + ("." if not sentence.endswith(".") else "")
                if s_len + len(s_text) + 1 > chunk_size and s_buf:
                    raw_chunks.append(" ".join(s_buf))
                    # Overlap with last sentence if feasible
                    s_buf = [s_buf[-1], s_text] if chunk_overlap > 0 and len(s_buf[-1]) < chunk_overlap else [s_text]
                    s_len = sum(len(x) + 1 for x in s_buf)
                else:
                    s_buf.append(s_text)
                    s_len += len(s_text) + 1
            if s_buf:
                raw_chunks.append(" ".join(s_buf))
            continue

        # Normal paragraph accumulation
        if current_len + len(para_clean) + 2 > chunk_size and current_chunk:
            raw_chunks.append("\n\n".join(current_chunk))
            # Start next chunk with overlap from the last paragraph if small enough
            if chunk_overlap > 0 and len(current_chunk[-1]) < chunk_overlap:
                current_chunk = [current_chunk[-1], para_clean]
                current_len = sum(len(p) + 2 for p in current_chunk)
            else:
                current_chunk = [para_clean]
                current_len = len(para_clean)
        else:
            current_chunk.append(para_clean)
            current_len += len(para_clean) + 2

    if current_chunk:
        raw_chunks.append("\n\n".join(current_chunk))

    return [c.strip() for c in raw_chunks if c.strip()]


def chunk_pages(
    pages: List[ExtractedPage],
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    doc_metadata: Dict[str, Any],
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> List[DocumentChunk]:
    """
    Chunk all extracted PDF pages and attach deterministic IDs and citation metadata.

    Args:
        pages: List of ExtractedPage objects.
        document_id: UUID of the parent document.
        version_id: UUID of the document version.
        doc_metadata: Metadata dictionary (title, circular_number, topic, version_number, etc.).
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Character overlap.

    Returns:
        List of DocumentChunk objects ready for vector embedding.
    """
    chunks: List[DocumentChunk] = []
    version_num = int(doc_metadata.get("version_number", 1))
    doc_title = str(doc_metadata.get("title", ""))
    circular_no = str(doc_metadata.get("circular_number", "") or "")
    topic = str(doc_metadata.get("topic", "") or "")
    doc_type = str(doc_metadata.get("document_type", "circular"))
    file_hash = str(doc_metadata.get("file_hash", ""))
    status = str(doc_metadata.get("status", "ACTIVE"))

    for page in pages:
        page_text = page.text.strip()
        if not page_text:
            continue

        text_pieces = _split_text_into_chunks(
            text=page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for chunk_idx, piece in enumerate(text_pieces):
            # Deterministic chunk ID
            chunk_id = f"doc_{document_id}_v{version_num}_p{page.page_number}_c{chunk_idx}"

            # Structured metadata (all values are strings/ints/bools for ChromaDB compatibility)
            chunk_meta: Dict[str, Any] = {
                "document_id": str(document_id),
                "version_id": str(version_id),
                "version_number": version_num,
                "document_title": doc_title,
                "circular_number": circular_no,
                "topic": topic,
                "document_type": doc_type,
                "page_number": page.page_number,
                "chunk_index": chunk_idx,
                "chunk_id": chunk_id,
                "status": status,
                "file_hash": file_hash,
            }

            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=piece,
                    page_number=page.page_number,
                    chunk_index=chunk_idx,
                    metadata=chunk_meta,
                )
            )

    return chunks
