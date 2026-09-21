"""Chunking service package."""

from app.services.chunking.text_chunker import DocumentChunk, chunk_pages

__all__ = ["DocumentChunk", "chunk_pages"]
