"""
RAG Service Orchestrator — Phase 4 Core RBI RAG.

Coordinates the full RAG pipeline:

  1. Query normalization (deterministic, preserves regulatory terms)
  2. Hybrid Retrieval:
       A. Dense   — ChromaDB + Nomic Embed v1.5
       B. Sparse  — PostgreSQL FTS on document_chunks
  3. Candidate merge & deduplication by chunk_id
  4. BGE cross-encoder reranking
  5. Deterministic Evidence Gate:
       - If no candidates OR top reranker score < RAG_MIN_EVIDENCE_SCORE
         -> return controlled "insufficient evidence" response WITHOUT calling Gemini
  6. Regulatory prompt construction (evidence blocks with source IDs)
  7. Gemini structured generation (google-genai SDK, JSON output)
  8. Backend citation validation & assembly (grounding.py)
  9. Return RAGResult to the API layer for persistence

ZERO Phase 5+ scope:
  No Redis, no cache, no session memory, no Neo4j, no feedback, no PII redaction.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.schemas.chat import CitationResponse
from app.services.rag.generator import GeminiGenerator
from app.services.rag.llm_gateway import LLMGatewayInterface, GeminiLLMAdapter, get_llm_gateway
from app.services.rag.grounding import validate_and_build_citations
from app.services.rag.prompt_builder import build_prompt
from app.services.rag.query_processor import normalize_query
from app.services.rag.reranker import BGEReranker
from app.services.rag.retriever import HybridRetriever, RetrievedChunk

logger = logging.getLogger(__name__)
settings = get_settings()

INSUFFICIENT_EVIDENCE_MSG = (
    "I was unable to find sufficient information in the indexed RBI regulatory documents "
    "to answer your question. Please verify the question refers to an RBI circular, "
    "master direction, or notification that has been uploaded to the knowledge base."
)

GREETINGS_MAP = {
    "hi": "Hello! I am your IDFC Advisory Assistant. How can I assist you with RBI regulatory directions, circulars, or compliance requirements today?",
    "hello": "Hello! How can I assist your regulatory compliance query today?",
    "hey": "Hey there! Feel free to ask any RBI compliance or regulatory questions.",
    "good morning": "Good morning! How can I assist you with RBI regulatory master directions today?",
    "good afternoon": "Good afternoon! How can I help you with your compliance queries today?",
    "good evening": "Good evening! How can I assist with your RBI compliance or regulatory queries?",
    "good night": "Good night! Have a restful evening. Feel free to ask any regulatory compliance questions whenever you return.",
    "gn": "Good night! Have a great rest.",
    "thank you": "You're very welcome! Let me know if you need any further regulatory clarifications.",
    "thanks": "Happy to help! Feel free to ask if you have any more RBI compliance questions.",
    "bye": "Goodbye! Have a great day ahead.",
    "goodbye": "Goodbye! Have a great day.",
}


@dataclass
class RAGResult:
    """
    The outcome of a single RAG pipeline execution.

    Attributes:
        answer:         Final answer text (grounded or insufficient evidence message).
        retrieval_type: "rag" | "insufficient_evidence" | "conversational"
        citations:      Backend-verified citations (empty for insufficient_evidence).
        metrics:        Diagnostic payload for observability.
    """

    answer: str
    retrieval_type: str  # "rag" | "insufficient_evidence" | "conversational"
    citations: List[CitationResponse] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


class RAGService:
    """
    Full RAG pipeline orchestrator using LLMGateway abstraction.

    Injectable dependencies allow unit tests to swap in mocks without
    touching the database or calling real ML models.
    """

    def __init__(
        self,
        retriever: Optional[HybridRetriever] = None,
        reranker: Optional[BGEReranker] = None,
        generator: Optional[Any] = None,
        llm_gateway: Optional[LLMGatewayInterface] = None,
    ):
        self.retriever = retriever or HybridRetriever()
        self.reranker = reranker or BGEReranker()
        if llm_gateway:
            self.llm_gateway = llm_gateway
        elif generator:
            self.llm_gateway = GeminiLLMAdapter(generator=generator)
        else:
            self.llm_gateway = get_llm_gateway()


    async def answer(self, query: str, db: AsyncSession) -> RAGResult:
        """
        Execute the full RAG pipeline for a single user question.

        Args:
            query: Raw user question string (stored verbatim by the API layer).
            db:    Async SQLAlchemy session.

        Returns:
            RAGResult with the answer, citations, retrieval_type, and metrics.
        """
        t_start = time.monotonic()
        metrics: dict = {}

        # ------------------------------------------------------------------ #
        # Step 0: Conversational greeting check
        # ------------------------------------------------------------------ #
        clean_q = query.lower().strip("!.,? ")
        if clean_q in GREETINGS_MAP:
            metrics["gate_decision"] = "conversational_greeting"
            metrics["total_latency_ms"] = round((time.monotonic() - t_start) * 1000)
            return RAGResult(
                answer=GREETINGS_MAP[clean_q],
                retrieval_type="conversational",
                metrics=metrics,
            )

        # ------------------------------------------------------------------ #
        # Step 1: Query normalization
        # ------------------------------------------------------------------ #
        try:
            normalized_query = normalize_query(query)
        except ValueError as exc:
            return RAGResult(
                answer=INSUFFICIENT_EVIDENCE_MSG,
                retrieval_type="insufficient_evidence",
                metrics={"error": str(exc)},
            )
        metrics["normalized_query"] = normalized_query

        # ------------------------------------------------------------------ #
        # Step 2 & 3: Hybrid retrieval + merge
        # ------------------------------------------------------------------ #
        t_retrieval = time.monotonic()
        candidates: List[RetrievedChunk] = await self.retriever.retrieve(
            query=normalized_query,
            db=db,
        )
        metrics["retrieval_latency_ms"] = round((time.monotonic() - t_retrieval) * 1000)
        metrics["dense_plus_sparse_count"] = len(candidates)

        # ------------------------------------------------------------------ #
        # Step 4: BGE reranking
        # ------------------------------------------------------------------ #
        t_rerank = time.monotonic()
        reranked: List[RetrievedChunk] = self.reranker.rerank(
            query=normalized_query,
            candidates=candidates,
            top_k=settings.RAG_RERANK_TOP_K,
        )
        metrics["rerank_latency_ms"] = round((time.monotonic() - t_rerank) * 1000)
        metrics["reranked_count"] = len(reranked)

        # ------------------------------------------------------------------ #
        # Step 5: Deterministic Evidence Gate
        # ------------------------------------------------------------------ #
        top_score = reranked[0].rerank_score if reranked else 0.0
        metrics["top_rerank_score"] = top_score
        metrics["min_evidence_score"] = settings.RAG_MIN_EVIDENCE_SCORE

        if not reranked or top_score < settings.RAG_MIN_EVIDENCE_SCORE:
            logger.info(
                "Evidence gate: BLOCKED. candidates=%d, top_score=%.4f, threshold=%.4f",
                len(reranked),
                top_score,
                settings.RAG_MIN_EVIDENCE_SCORE,
            )
            metrics["gate_decision"] = "insufficient_evidence"
            metrics["total_latency_ms"] = round((time.monotonic() - t_start) * 1000)
            return RAGResult(
                answer=INSUFFICIENT_EVIDENCE_MSG,
                retrieval_type="insufficient_evidence",
                metrics=metrics,
            )

        metrics["gate_decision"] = "proceed"
        logger.info(
            "Evidence gate: PASSED. candidates=%d, top_score=%.4f",
            len(reranked),
            top_score,
        )

        # ------------------------------------------------------------------ #
        # Step 6: Prompt construction
        # ------------------------------------------------------------------ #
        prompt = build_prompt(query=normalized_query, chunks=reranked)

        # ------------------------------------------------------------------ #
        # Step 7: LLM structured generation via LLM Gateway
        # ------------------------------------------------------------------ #
        t_llm = time.monotonic()
        try:
            llm_response = await self.llm_gateway.generate(prompt)
        except Exception as exc:
            logger.error("Gemini generation failed: %s", exc)
            metrics["llm_error"] = str(exc)
            metrics["total_latency_ms"] = round((time.monotonic() - t_start) * 1000)
            return RAGResult(
                answer="An error occurred while generating the response. Please try again.",
                retrieval_type="insufficient_evidence",
                metrics=metrics,
            )
        metrics["llm_latency_ms"] = round((time.monotonic() - t_llm) * 1000)
        metrics["gemini_citation_ids_raw"] = llm_response.citation_ids

        # ------------------------------------------------------------------ #
        # Step 8: Backend citation validation & assembly
        # ------------------------------------------------------------------ #
        citations = validate_and_build_citations(
            citation_ids=llm_response.citation_ids,
            candidate_chunks=reranked,
        )
        metrics["verified_citations"] = len(citations)
        metrics["total_latency_ms"] = round((time.monotonic() - t_start) * 1000)

        logger.info(
            "RAG pipeline complete: latency=%dms, citations=%d",
            metrics["total_latency_ms"],
            len(citations),
        )

        return RAGResult(
            answer=llm_response.answer,
            retrieval_type="rag",
            citations=citations,
            metrics=metrics,
        )
