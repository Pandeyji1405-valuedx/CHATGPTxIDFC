"""
Abstract embedding service interface (Phase 3).

Allows replacing or mocking the embedding model without impacting
the ingestion pipeline or retrieval services.
"""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingService(ABC):
    """Abstract interface for text embedding generation."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate vector embeddings for a list of document chunk texts.
        Must apply document-specific prefix if required by the model.

        Args:
            texts: List of chunk text strings.

        Returns:
            List of float vector embeddings.
        """
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """
        Generate a single vector embedding for a search query.
        Must apply query-specific prefix if required by the model.

        Args:
            query: Query text string.

        Returns:
            Float vector embedding.
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality (e.g., 768)."""
        pass
