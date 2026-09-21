"""Embeddings service package."""

from app.services.embeddings.base import BaseEmbeddingService
from app.services.embeddings.mock_service import MockEmbeddingService
from app.services.embeddings.nomic_service import (
    DOCUMENT_PREFIX,
    QUERY_PREFIX,
    NomicEmbeddingService,
)

__all__ = [
    "BaseEmbeddingService",
    "NomicEmbeddingService",
    "MockEmbeddingService",
    "DOCUMENT_PREFIX",
    "QUERY_PREFIX",
]
