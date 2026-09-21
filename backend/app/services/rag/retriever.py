"""
Hybrid Retriever — Phase 4 RAG Pipeline.

Implements two explicit retrieval branches:
  A. Dense retrieval:  ChromaDB + Nomic Embed v1.5
     - Prepends "search_query: " prefix to the query before embedding.
     - Filters ChromaDB by status=ACTIVE.
  B. Sparse/lexical retrieval: PostgreSQL Full-Text Search
     - Executes plainto_tsquery("simple", :query) against document_chunks.
     - Filters by status=ACTIVE.

Results from both branches are merged and deduplicated by chunk_id,
preserving the best metadata.  The merged set is then passed to the
BGE reranker.

PostgreSQL is NOT used for vector search.  ChromaDB is NOT used for
keyword search.  Each branch is independently query-able.

Test isolation: when the DB engine dialect is "sqlite" (in-memory tests),
the sparse branch is silently skipped to avoid incompatible SQL syntax.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.embeddings.nomic_service import NomicEmbeddingService
from app.services.vector_db.chroma_service import ChromaDBService

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RetrievedChunk:
    """
    A single candidate chunk surfaced from dense or sparse retrieval.

    Attributes:
        chunk_id:       Shared identifier between ChromaDB and document_chunks.
        text:           Raw chunk content.
        page_number:    Source PDF page (1-indexed).
        document_id:    UUID string of the parent document.
        version_id:     UUID string of the parent version.
        document_title: Human-readable title from document metadata.
        circular_number: Optional RBI circular reference.
        version_number: Document version integer.
        section:        Optional section heading.
        topic:          Optional regulatory topic.
        source:         "dense" | "sparse" | "both"
        score:          Raw retrieval score (distance for dense, rank for sparse).
        rerank_score:   BGE cross-encoder score (populated by reranker).
    """

    chunk_id: str
    text: str
    page_number: int = 0
    document_id: str = ""
    version_id: str = ""
    document_title: str = ""
    circular_number: Optional[str] = None
    version_number: int = 1
    section: Optional[str] = None
    topic: Optional[str] = None
    source: str = "dense"
    score: float = 0.0
    rerank_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class HybridRetriever:
    """
    Executes dense + sparse retrieval and merges candidates by chunk_id.
    """

    def __init__(
        self,
        embedding_service: Optional[NomicEmbeddingService] = None,
        chroma_service: Optional[ChromaDBService] = None,
    ):
        self.embedding_service = embedding_service or NomicEmbeddingService()
        self.chroma_service = chroma_service or ChromaDBService()

    async def retrieve(
        self,
        query: str,
        db: AsyncSession,
        vector_top_k: Optional[int] = None,
        sparse_top_k: Optional[int] = None,
    ) -> List[RetrievedChunk]:
        """
        Run both retrieval branches and return merged deduplicated candidates.

        Args:
            query:        Normalized user query.
            db:           Async SQLAlchemy session (used for sparse branch).
            vector_top_k: Override for dense top-k (default from settings).
            sparse_top_k: Override for sparse top-k (default from settings).

        Returns:
            Merged list of RetrievedChunk objects.
        """
        _vk = vector_top_k or settings.RAG_VECTOR_TOP_K
        _sk = sparse_top_k or settings.RAG_SPARSE_TOP_K

        dense_candidates = self._dense_search(query, _vk)
        sparse_candidates = await self._sparse_search(query, db, _sk)

        merged = self._merge(dense_candidates, sparse_candidates)
        logger.info(
            "Hybrid retrieval: dense=%d, sparse=%d, merged=%d",
            len(dense_candidates),
            len(sparse_candidates),
            len(merged),
        )
        return merged

    # ------------------------------------------------------------------ #
    # Dense Branch — ChromaDB
    # ------------------------------------------------------------------ #

    def _dense_search(self, query: str, top_k: int) -> List[RetrievedChunk]:
        """
        Embed the query with Nomic prefix and query ChromaDB.

        ChromaDB uses cosine distance (lower = more similar).
        We convert to a similarity-ish score as (1 - distance).
        """
        try:
            prefixed = f"search_query: {query}"
            embedding = self.embedding_service.embed_query(prefixed)
            raw_results = self.chroma_service.query_chunks(
                query_embedding=embedding,
                n_results=top_k,
                where={"status": "ACTIVE"},
            )
        except Exception as exc:
            logger.warning("Dense retrieval failed: %s", exc)
            return []

        candidates: List[RetrievedChunk] = []
        for r in raw_results:
            meta = r.get("metadata", {})
            distance = float(r.get("distance", 1.0))
            sim_score = max(0.0, 1.0 - distance)
            candidates.append(
                RetrievedChunk(
                    chunk_id=r["chunk_id"],
                    text=r.get("text", ""),
                    page_number=int(meta.get("page_number", 0)),
                    document_id=str(meta.get("document_id", "")),
                    version_id=str(meta.get("version_id", "")),
                    document_title=str(meta.get("document_title", "")),
                    circular_number=meta.get("circular_number") or None,
                    version_number=int(meta.get("version_number", 1)),
                    section=meta.get("section") or None,
                    topic=meta.get("topic") or None,
                    source="dense",
                    score=sim_score,
                    metadata=meta,
                )
            )
        return candidates

    # ------------------------------------------------------------------ #
    # Sparse Branch — PostgreSQL FTS
    # ------------------------------------------------------------------ #

    async def _sparse_search(
        self,
        query: str,
        db: AsyncSession,
        top_k: int,
    ) -> List[RetrievedChunk]:
        """
        Execute PostgreSQL Full-Text Search on the document_chunks table.

        Uses the "simple" FTS configuration to preserve regulatory identifiers
        (circular numbers, section codes) without stemming distortion.

        Gracefully skips if the DB is SQLite (in-memory test mode).
        """
        # Detect SQLite (in-memory test environment)
        try:
            dialect = db.get_bind().dialect.name if hasattr(db, "get_bind") else ""
        except Exception:
            dialect = ""

        if dialect == "sqlite":
            logger.debug("Sparse search skipped: SQLite dialect detected (test mode).")
            return []

        sql = text(
            """
            SELECT
                dc.chunk_id,
                dc.content,
                dc.page_number,
                dc.section,
                dc.topic,
                dc.circular_number,
                dc.document_id::text,
                dc.version_id::text,
                d.title        AS document_title,
                dv.version_number,
                ts_rank_cd(
                    to_tsvector('simple', dc.content),
                    plainto_tsquery('simple', :query)
                ) AS rank_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            JOIN document_versions dv ON dv.id = dc.version_id
            WHERE
                dc.status = 'ACTIVE'
                AND dv.status = 'ACTIVE'
                AND dv.ingestion_status = 'COMPLETED'
                AND to_tsvector('simple', dc.content) @@ plainto_tsquery('simple', :query)
            ORDER BY rank_score DESC
            LIMIT :top_k
            """
        )

        try:
            result = await db.execute(sql, {"query": query, "top_k": top_k})
            rows = result.fetchall()
        except Exception as exc:
            logger.warning("Sparse FTS search failed: %s", exc)
            return []

        candidates: List[RetrievedChunk] = []
        for row in rows:
            candidates.append(
                RetrievedChunk(
                    chunk_id=row.chunk_id,
                    text=row.content,
                    page_number=int(row.page_number or 0),
                    document_id=str(row.document_id),
                    version_id=str(row.version_id),
                    document_title=str(row.document_title or ""),
                    circular_number=row.circular_number or None,
                    version_number=int(row.version_number or 1),
                    section=row.section or None,
                    topic=row.topic or None,
                    source="sparse",
                    score=float(row.rank_score or 0.0),
                )
            )
        return candidates

    # ------------------------------------------------------------------ #
    # Merge & Deduplication
    # ------------------------------------------------------------------ #

    def _merge(
        self,
        dense: List[RetrievedChunk],
        sparse: List[RetrievedChunk],
    ) -> List[RetrievedChunk]:
        """
        Merge dense and sparse candidates by chunk_id.

        When a chunk appears in both branches:
          - source is set to "both"
          - score is set to max(dense_score, sparse_score) as a conservative
            upper bound until reranking re-scores all candidates equally.

        The merged list preserves insertion order: dense first, then new
        sparse-only additions, so dense metadata takes priority.
        """
        seen: Dict[str, RetrievedChunk] = {}

        for chunk in dense:
            seen[chunk.chunk_id] = chunk

        for chunk in sparse:
            if chunk.chunk_id in seen:
                existing = seen[chunk.chunk_id]
                existing.source = "both"
                existing.score = max(existing.score, chunk.score)
            else:
                seen[chunk.chunk_id] = chunk

        return list(seen.values())
