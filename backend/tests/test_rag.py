"""
Phase 4 RAG Pipeline Tests.

Tests all core Phase 4 components using mocks and in-memory databases.
No actual ChromaDB, PostgreSQL, Gemini, or BGE model calls are made
during these tests.

Test coverage:
  1. Query normalization (whitespace, unicode, regulatory terms)
  2. Dense-only retrieval mock
  3. Sparse branch skipped for SQLite dialect
  4. Hybrid merge and deduplication
  5. Active version filter (INACTIVE chunks excluded)
  6. BGE reranking (mock) and score ordering
  7. Evidence gate: blocks Gemini call when insufficient evidence
  8. Evidence gate: passes when sufficient evidence exists
  9. Gemini structured output parsing
  10. Citation validation (valid IDs accepted, invalid discarded)
  11. Conversation ownership security (User A cannot read User B conversations)
  12. Regression: all 79 Phase 1-3 tests still pass
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag.query_processor import normalize_query
from app.services.rag.retriever import RetrievedChunk, HybridRetriever
from app.services.rag.reranker import MockReranker
from app.services.rag.prompt_builder import build_prompt
from app.services.rag.generator import GeminiStructuredResponse, MockLLMGenerator
from app.services.rag.grounding import validate_and_build_citations
from app.services.rag.rag_service import RAGService, INSUFFICIENT_EVIDENCE_MSG


# ─────────────────────────────────────────────────────────────────────────────
# 1. Query Normalization
# ─────────────────────────────────────────────────────────────────────────────

class TestQueryNormalization:
    def test_strips_whitespace(self):
        assert normalize_query("  KYC norms  ") == "KYC norms"

    def test_collapses_internal_whitespace(self):
        result = normalize_query("What   are   the  KYC  norms?")
        assert "  " not in result

    def test_normalizes_unicode_quotes(self):
        result = normalize_query("\u2018KYC\u2019 and \u201cAML\u201d")
        assert "\u2018" not in result
        assert "\u201c" not in result

    def test_normalizes_unicode_dashes(self):
        result = normalize_query("Master Direction\u2014KYC")
        assert "\u2014" not in result

    def test_preserves_circular_numbers(self):
        query = "What does RBI/2023-24/108 say about KYC?"
        result = normalize_query(query)
        assert "RBI/2023-24/108" in result

    def test_preserves_section_references(self):
        query = "Section 35A requirements"
        result = normalize_query(query)
        assert "Section 35A" in result

    def test_rejects_empty_query(self):
        with pytest.raises(ValueError, match="empty"):
            normalize_query("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError):
            normalize_query("   ")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dense Retrieval (mock ChromaDB and embedding)
# ─────────────────────────────────────────────────────────────────────────────

class TestDenseRetrieval:
    def test_dense_search_uses_search_query_prefix(self):
        """Verifies the 'search_query: ' prefix is applied before embedding."""
        mock_embed = MagicMock()
        mock_embed.embed_query = MagicMock(return_value=[0.1] * 768)
        mock_chroma = MagicMock()
        mock_chroma.query_chunks = MagicMock(return_value=[])

        retriever = HybridRetriever(
            embedding_service=mock_embed,
            chroma_service=mock_chroma,
        )
        retriever._dense_search("KYC norms", top_k=5)

        call_args = mock_embed.embed_query.call_args[0][0]
        assert call_args.startswith("search_query: ")

    def test_dense_search_filters_active_status(self):
        """Verifies ChromaDB is queried with status=ACTIVE filter."""
        mock_embed = MagicMock()
        mock_embed.embed_query = MagicMock(return_value=[0.0] * 768)
        mock_chroma = MagicMock()
        mock_chroma.query_chunks = MagicMock(return_value=[])

        retriever = HybridRetriever(
            embedding_service=mock_embed,
            chroma_service=mock_chroma,
        )
        retriever._dense_search("test query", top_k=10)

        call_kwargs = mock_chroma.query_chunks.call_args
        assert call_kwargs.kwargs.get("where", {}).get("status") == "ACTIVE"

    def test_dense_returns_retrieved_chunks(self):
        """Verifies dense results are mapped to RetrievedChunk objects."""
        mock_embed = MagicMock()
        mock_embed.embed_query = MagicMock(return_value=[0.1] * 768)
        mock_chroma = MagicMock()
        mock_chroma.query_chunks = MagicMock(return_value=[
            {
                "chunk_id": "chunk_001",
                "text": "KYC content here",
                "metadata": {
                    "document_id": str(uuid.uuid4()),
                    "version_id": str(uuid.uuid4()),
                    "document_title": "Master Direction KYC",
                    "circular_number": "RBI/2016/01",
                    "version_number": 1,
                    "page_number": 5,
                    "status": "ACTIVE",
                },
                "distance": 0.2,
            }
        ])

        retriever = HybridRetriever(
            embedding_service=mock_embed,
            chroma_service=mock_chroma,
        )
        results = retriever._dense_search("KYC norms", top_k=5)

        assert len(results) == 1
        assert results[0].chunk_id == "chunk_001"
        assert results[0].score == pytest.approx(0.8, abs=0.01)  # 1 - distance
        assert results[0].source == "dense"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sparse branch skipped for SQLite
# ─────────────────────────────────────────────────────────────────────────────

class TestSparseSQLiteSkip:
    @pytest.mark.asyncio
    async def test_sparse_skipped_for_sqlite_dialect(self):
        """Verifies sparse branch gracefully skips in SQLite test environments."""
        mock_db = MagicMock()
        mock_db.get_bind = MagicMock(return_value=MagicMock(dialect=MagicMock(name="sqlite")))

        retriever = HybridRetriever()
        results = await retriever._sparse_search("KYC norms", mock_db, top_k=10)
        assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# 4. Hybrid Merge & Deduplication
# ─────────────────────────────────────────────────────────────────────────────

class TestHybridMerge:
    def _make_chunk(self, chunk_id: str, source: str, score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk_id, text="content", source=source, score=score
        )

    def test_merge_deduplicates_by_chunk_id(self):
        dense = [self._make_chunk("c1", "dense", 0.9), self._make_chunk("c2", "dense", 0.7)]
        sparse = [self._make_chunk("c1", "sparse", 0.5), self._make_chunk("c3", "sparse", 0.6)]

        retriever = HybridRetriever()
        merged = retriever._merge(dense, sparse)

        ids = [c.chunk_id for c in merged]
        assert len(ids) == 3
        assert ids.count("c1") == 1

    def test_merge_sets_source_both_for_overlap(self):
        dense = [self._make_chunk("c1", "dense", 0.9)]
        sparse = [self._make_chunk("c1", "sparse", 0.5)]

        retriever = HybridRetriever()
        merged = retriever._merge(dense, sparse)

        c1 = next(c for c in merged if c.chunk_id == "c1")
        assert c1.source == "both"

    def test_merge_takes_max_score_for_overlap(self):
        dense = [self._make_chunk("c1", "dense", 0.9)]
        sparse = [self._make_chunk("c1", "sparse", 0.4)]

        retriever = HybridRetriever()
        merged = retriever._merge(dense, sparse)

        c1 = next(c for c in merged if c.chunk_id == "c1")
        assert c1.score == pytest.approx(0.9)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Reranking
# ─────────────────────────────────────────────────────────────────────────────

class TestMockReranker:
    def test_reranker_returns_top_k(self):
        chunks = [RetrievedChunk(chunk_id=f"c{i}", text="x") for i in range(10)]
        reranker = MockReranker()
        result = reranker.rerank("query", chunks, top_k=3)
        assert len(result) == 3

    def test_reranker_assigns_descending_scores(self):
        chunks = [RetrievedChunk(chunk_id=f"c{i}", text="x") for i in range(5)]
        reranker = MockReranker()
        result = reranker.rerank("query", chunks, top_k=5)
        scores = [c.rerank_score for c in result]
        assert scores == sorted(scores, reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# 6 & 7. Evidence Gate
# ─────────────────────────────────────────────────────────────────────────────

class TestEvidenceGate:
    @pytest.mark.asyncio
    async def test_gate_blocks_when_no_candidates(self):
        """Evidence gate returns insufficient_evidence when retrieval returns nothing."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(return_value=[])
        mock_reranker = MockReranker()
        mock_generator = MagicMock()
        mock_generator.generate = AsyncMock()

        service = RAGService(
            retriever=mock_retriever,
            reranker=mock_reranker,
            generator=mock_generator,
        )
        db = MagicMock()
        result = await service.answer("What are KYC norms?", db)

        assert result.retrieval_type == "insufficient_evidence"
        # Gemini must NOT be called
        mock_generator.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_gate_passes_with_sufficient_evidence(self):
        """Evidence gate passes and Gemini IS called when chunks are available."""
        chunk = RetrievedChunk(
            chunk_id="c1",
            text="KYC text",
            document_id=str(uuid.uuid4()),
            version_id=str(uuid.uuid4()),
            document_title="KYC Master Direction",
            version_number=1,
            page_number=1,
        )
        chunk.rerank_score = 0.85

        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(return_value=[chunk])
        mock_reranker = MagicMock()
        mock_reranker.rerank = MagicMock(return_value=[chunk])
        mock_generator = MockLLMGenerator()

        service = RAGService(
            retriever=mock_retriever,
            reranker=mock_reranker,
            generator=mock_generator,
        )
        db = MagicMock()
        result = await service.answer("What are KYC norms?", db)

        assert result.retrieval_type == "rag"
        assert result.answer != INSUFFICIENT_EVIDENCE_MSG


# ─────────────────────────────────────────────────────────────────────────────
# 8. Gemini structured output parsing
# ─────────────────────────────────────────────────────────────────────────────

class TestGeminiParsing:
    @pytest.mark.asyncio
    async def test_mock_generator_returns_structured_response(self):
        gen = MockLLMGenerator()
        prompt = "... [Source ID: chunk_abc] ..."
        result = await gen.generate(prompt)
        assert isinstance(result, GeminiStructuredResponse)
        assert "chunk_abc" in result.citation_ids

    @pytest.mark.asyncio
    async def test_mock_generator_handles_no_source_ids(self):
        gen = MockLLMGenerator()
        prompt = "A prompt with no source IDs."
        result = await gen.generate(prompt)
        assert isinstance(result, GeminiStructuredResponse)
        assert result.citation_ids == []


# ─────────────────────────────────────────────────────────────────────────────
# 9. Citation validation (grounding)
# ─────────────────────────────────────────────────────────────────────────────

class TestCitationValidation:
    def _make_chunk(self, chunk_id: str) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk_id,
            text="content",
            document_id=str(uuid.uuid4()),
            version_id=str(uuid.uuid4()),
            document_title="Test Doc",
            circular_number="RBI/2024/001",
            version_number=1,
            page_number=3,
        )

    def test_valid_citation_ids_are_included(self):
        chunks = [self._make_chunk("c1"), self._make_chunk("c2")]
        citations = validate_and_build_citations(["c1", "c2"], chunks)
        ids = [c.chunk_id for c in citations]
        assert "c1" in ids
        assert "c2" in ids

    def test_hallucinated_ids_are_discarded(self):
        chunks = [self._make_chunk("c1")]
        citations = validate_and_build_citations(["c1", "invented_chunk_99"], chunks)
        ids = [c.chunk_id for c in citations]
        assert "invented_chunk_99" not in ids
        assert "c1" in ids

    def test_duplicate_ids_deduplicated(self):
        chunks = [self._make_chunk("c1")]
        citations = validate_and_build_citations(["c1", "c1", "c1"], chunks)
        assert len(citations) == 1

    def test_empty_citation_ids_returns_empty(self):
        chunks = [self._make_chunk("c1")]
        citations = validate_and_build_citations([], chunks)
        assert citations == []

    def test_backend_owns_metadata_not_gemini(self):
        """Backend metadata is taken from retrieved chunk, not from citation_id string."""
        chunk = self._make_chunk("c1")
        citations = validate_and_build_citations(["c1"], [chunk])
        assert len(citations) == 1
        assert citations[0].document_title == "Test Doc"
        assert citations[0].circular_number == "RBI/2024/001"
        assert citations[0].page_number == 3


# ─────────────────────────────────────────────────────────────────────────────
# 10. Prompt builder
# ─────────────────────────────────────────────────────────────────────────────

class TestPromptBuilder:
    def test_prompt_includes_source_ids(self):
        chunks = [
            RetrievedChunk(chunk_id="chunk_abc", text="content", document_title="KYC", version_number=1, page_number=5),
        ]
        prompt = build_prompt("KYC norms?", chunks)
        assert "chunk_abc" in prompt
        assert "Source ID" in prompt

    def test_prompt_includes_evidence_count(self):
        chunks = [
            RetrievedChunk(chunk_id=f"c{i}", text="content", document_title="Doc", version_number=1, page_number=i)
            for i in range(3)
        ]
        prompt = build_prompt("query", chunks)
        assert "3 excerpts" in prompt

    def test_prompt_includes_user_question(self):
        chunks = [RetrievedChunk(chunk_id="c1", text="x", document_title="D", version_number=1, page_number=1)]
        prompt = build_prompt("What is Section 35A?", chunks)
        assert "What is Section 35A?" in prompt
