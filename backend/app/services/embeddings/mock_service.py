"""
Mock embedding service for deterministic offline unit testing (Phase 3).

Generates consistent normalized vectors derived deterministically from the SHA-256
hash of input texts.
"""

import hashlib
import math
from typing import List

from app.services.embeddings.base import BaseEmbeddingService

DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class MockEmbeddingService(BaseEmbeddingService):
    """
    Fast, deterministic, dependency-free embedding service for unit tests.
    """

    def __init__(self, dimension: int = 768):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _generate_vector(self, text: str) -> List[float]:
        """Generate a deterministic normalized vector derived from token feature hashing."""
        vec = [0.0] * self._dimension
        tokens = [w for w in text.lower().replace(":", " ").replace(".", " ").replace(",", " ").split() if w]
        if not tokens:
            tokens = [text]
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimension
            sign = 1.0 if ((h >> 8) & 1) else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(f"{DOCUMENT_PREFIX}{t}") for t in texts]

    def embed_query(self, query: str) -> List[float]:
        if not query or not query.strip():
            raise ValueError("Query text cannot be empty.")
        return self._generate_vector(f"{QUERY_PREFIX}{query.strip()}")

