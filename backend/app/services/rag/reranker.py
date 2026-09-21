"""
BGE Cross-Encoder Reranker — Phase 4 RAG Pipeline.

Applies BAAI/bge-reranker-v2-m3 cross-encoder scoring to merged
retrieval candidates.  The cross-encoder sees (query, chunk_text) pairs
and scores their semantic relevance directly, producing a calibrated
float score that is used both for ranking and evidence gating.

Design rules:
  - Reranker is loaded lazily on first use; it is expensive to load.
  - MockReranker provides deterministic offline behaviour for unit tests.
  - If RERANKER_ENABLED=False, raw retrieval scores are used as-is.
"""

import logging
import os
from typing import List

from app.core.config import get_settings
from app.services.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)
settings = get_settings()

# Singleton reranker model (loaded once per worker process)
_reranker_model = None


def _get_reranker():
    """Lazy-load the BGE cross-encoder model."""
    global _reranker_model
    if _reranker_model is None:
        from sentence_transformers.cross_encoder import CrossEncoder
        model_name = settings.RERANKER_MODEL_NAME
        logger.info("Loading BGE reranker model: %s", model_name)
        _reranker_model = CrossEncoder(model_name, max_length=512)
        logger.info("BGE reranker loaded successfully.")
    return _reranker_model


class BGEReranker:
    """
    Cross-encoder reranker using BAAI/bge-reranker-v2-m3.

    Scores (query, chunk) pairs and returns candidates sorted by
    relevance score descending.
    """

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int,
    ) -> List[RetrievedChunk]:
        """
        Score and rank candidates using the BGE cross-encoder.

        Args:
            query:      Normalized user question.
            candidates: Merged retrieval candidates.
            top_k:      Number of top candidates to return.

        Returns:
            Top-K candidates sorted by rerank_score descending.
        """
        if not candidates:
            return []

        if not settings.RERANKER_ENABLED:
            logger.debug("Reranker disabled; returning candidates sorted by raw score.")
            for c in candidates:
                c.rerank_score = c.score
            return sorted(candidates, key=lambda x: x.rerank_score, reverse=True)[:top_k]

        try:
            model = _get_reranker()
            pairs = [(query, c.text) for c in candidates]
            scores = model.predict(pairs)

            for chunk, score in zip(candidates, scores):
                chunk.rerank_score = float(score)

            ranked = sorted(candidates, key=lambda x: x.rerank_score, reverse=True)
            return ranked[:top_k]

        except Exception as exc:
            logger.warning(
                "BGE reranker failed (%s); falling back to raw score ranking.", exc
            )
            for c in candidates:
                c.rerank_score = c.score
            return sorted(candidates, key=lambda x: x.rerank_score, reverse=True)[:top_k]


class MockReranker:
    """
    Deterministic reranker for offline unit tests.

    Assigns scores in descending order based on list position;
    the first candidate receives the highest score.
    """

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int,
    ) -> List[RetrievedChunk]:
        for i, chunk in enumerate(candidates):
            # Descending: first chunk gets highest mock score
            chunk.rerank_score = 1.0 - (i * 0.05)
        return candidates[:top_k]
