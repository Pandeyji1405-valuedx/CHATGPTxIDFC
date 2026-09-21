"""
Nomic Embed v1.5 embedding service implementation (Phase 3).

Follows official Nomic Embed v1.5 specifications:
  - Document prefix: "search_document: "
  - Query prefix:    "search_query: "
  - Embedding dimension: 768
  - Uses sentence-transformers with batching
"""

import logging
from typing import List, Optional

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings
from app.services.embeddings.base import BaseEmbeddingService

logger = logging.getLogger(__name__)
settings = get_settings()

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


_SHARED_MODEL: Optional[SentenceTransformer] = None


class NomicEmbeddingService(BaseEmbeddingService):
    """
    Nomic Embed v1.5 model wrapper.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None,
        dimension: Optional[int] = None,
    ):
        self._model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._model: Optional[SentenceTransformer] = None

    def _get_model(self) -> SentenceTransformer:
        """Lazy-load the SentenceTransformer model on first invocation (singleton cache with instance override)."""
        if self._model is not None:
            return self._model
        global _SHARED_MODEL
        if _SHARED_MODEL is None:
            logger.info("Loading Nomic Embed v1.5 model: %s", self._model_name)
            try:
                _SHARED_MODEL = SentenceTransformer(
                    self._model_name,
                    trust_remote_code=True,
                )
            except Exception as exc:
                logger.error("Failed to load embedding model %s: %s", self._model_name, exc)
                raise RuntimeError(
                    f"Could not load embedding model '{self._model_name}': {exc}"
                ) from exc
        return _SHARED_MODEL

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of document texts with 'search_document: ' prefix.

        Args:
            texts: List of raw document chunk texts.

        Returns:
            List of float vector embeddings (768-dim each).
        """
        if not texts:
            return []

        prefixed_texts = [f"{DOCUMENT_PREFIX}{t}" for t in texts]
        model = self._get_model()

        try:
            embeddings = model.encode(
                prefixed_texts,
                batch_size=self._batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return [e.tolist() for e in embeddings]
        except Exception as exc:
            logger.error("Error during document embedding generation: %s", exc)
            raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    def embed_query(self, query: str) -> List[float]:
        """
        Generate an embedding for a query text with 'search_query: ' prefix.

        Args:
            query: Raw query text.

        Returns:
            Float vector embedding (768-dim).
        """
        if not query or not query.strip():
            raise ValueError("Query text cannot be empty for embedding generation.")

        prefixed_query = f"{QUERY_PREFIX}{query.strip()}"
        model = self._get_model()

        try:
            embedding = model.encode(
                prefixed_query,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return embedding.tolist()
        except Exception as exc:
            logger.error("Error during query embedding generation: %s", exc)
            raise RuntimeError(f"Query embedding generation failed: {exc}") from exc
