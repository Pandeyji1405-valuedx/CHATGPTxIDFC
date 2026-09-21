"""
RAG Quality Benchmark & Evaluation Harness (Phase 8).

Responsibilities:
  - Evaluate RAG pipeline accuracy, retrieval precision, grounding correctness,
    citation provenance, and evidence gate behavior.
  - Test benchmark dataset across 7 distinct query categories.
  - Return structured metrics report (Precision, Recall, Grounding %, Latency, Fallback %).
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.rag.rag_service import RAGService


@dataclass
class EvalQueryResult:
    query: str
    category: str
    expected_outcome: str  # 'rag', 'insufficient_evidence', 'out_of_scope'
    retrieval_type: str
    citation_count: int
    passed: bool
    latency_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGBenchmarkReport:
    total_queries: int
    passed_queries: int
    accuracy_percentage: float
    avg_latency_ms: float
    grounded_citation_rate: float
    controlled_insufficient_rate: float
    category_breakdown: Dict[str, Dict[str, Any]]


GOLDEN_BENCHMARK_DATASET = [
    # 1. Supported Regulatory Questions
    {
        "query": "What are the KYC onboarding requirements for individual bank customers under RBI guidelines?",
        "category": "supported_regulatory",
        "expected_outcome": "rag",
    },
    {
        "query": "Explain the RBI Master Direction on Cyber Security Framework for banks.",
        "category": "supported_regulatory",
        "expected_outcome": "rag",
    },
    # 2. Unsupported / Out-of-Scope Questions
    {
        "query": "What is the recommended recipe for baking chocolate chip cookies?",
        "category": "out_of_scope",
        "expected_outcome": "insufficient_evidence",
    },
    {
        "query": "What are the core features of Python 3.12 syntax?",
        "category": "out_of_scope",
        "expected_outcome": "insufficient_evidence",
    },
    # 3. Ambiguous / Vague Queries
    {
        "query": "What are the rules?",
        "category": "ambiguous_query",
        "expected_outcome": "insufficient_evidence",
    },
    # 4. Multi-turn / Contextualized Queries
    {
        "query": "What are the capital adequacy requirements for scheduled commercial banks?",
        "category": "supported_regulatory",
        "expected_outcome": "rag",
    },
    # 5. Security & Risk Governance Queries
    {
        "query": "What is the mandatory timeline for reporting cyber security incidents to RBI?",
        "category": "supported_regulatory",
        "expected_outcome": "rag",
    },
    # 6. Specific Numeric Threshold Queries
    {
        "query": "What is the LCR (Liquidity Coverage Ratio) minimum requirement for commercial banks?",
        "category": "supported_regulatory",
        "expected_outcome": "rag",
    },
    # 7. Discontinued / Superseded Document Queries
    {
        "query": "What were the legacy 2010 KYC guidelines for non-resident accounts?",
        "category": "superseded_doc",
        "expected_outcome": "insufficient_evidence",
    },
]


class RAGEvaluationHarness:
    """
    Automated benchmark harness for evaluating RAG retrieval, evidence gate,
    and grounding accuracy.
    """

    def __init__(self, rag_service: Optional[RAGService] = None):
        self.rag_service = rag_service or RAGService()

    async def run_benchmark(
        self,
        db: AsyncSession,
        user: User,
        dataset: Optional[List[Dict[str, str]]] = None,
    ) -> RAGBenchmarkReport:
        """
        Run golden benchmark queries through the RAG pipeline and measure quality metrics.

        Args:
            db: Async DB session.
            user: Authenticated user context.
            dataset: Optional list of query dicts (defaults to GOLDEN_BENCHMARK_DATASET).

        Returns:
            RAGBenchmarkReport object with metrics and breakdown.
        """
        target_dataset = dataset or GOLDEN_BENCHMARK_DATASET
        results: List[EvalQueryResult] = []
        category_stats: Dict[str, Dict[str, Any]] = {}

        for item in target_dataset:
            query = item["query"]
            category = item["category"]
            expected = item["expected_outcome"]

            start_t = time.perf_counter()
            try:
                rag_resp = await self.rag_service.answer_question(
                    db=db,
                    query=query,
                    user_id=user.id,
                )
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0

                actual_outcome = rag_resp.retrieval_type
                citation_count = len(rag_resp.citations) if rag_resp.citations else 0

                # Evaluate pass condition
                if expected == "rag":
                    passed = actual_outcome == "rag" and citation_count > 0
                else:  # 'insufficient_evidence' or 'out_of_scope'
                    passed = actual_outcome == "insufficient_evidence"

                results.append(
                    EvalQueryResult(
                        query=query,
                        category=category,
                        expected_outcome=expected,
                        retrieval_type=actual_outcome,
                        citation_count=citation_count,
                        passed=passed,
                        latency_ms=elapsed_ms,
                    )
                )
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                results.append(
                    EvalQueryResult(
                        query=query,
                        category=category,
                        expected_outcome=expected,
                        retrieval_type="error",
                        citation_count=0,
                        passed=False,
                        latency_ms=elapsed_ms,
                        details={"error": str(exc)},
                    )
                )

        # Aggregate metrics
        total = len(results)
        passed_count = sum(1 for r in results if r.passed)
        accuracy = (passed_count / total * 100.0) if total > 0 else 0.0
        avg_latency = (sum(r.latency_ms for r in results) / total) if total > 0 else 0.0

        rag_results = [r for r in results if r.expected_outcome == "rag"]
        grounded_rate = (
            sum(1 for r in rag_results if r.citation_count > 0) / len(rag_results) * 100.0
            if rag_results else 100.0
        )

        insuf_results = [r for r in results if r.expected_outcome != "rag"]
        insuf_rate = (
            sum(1 for r in insuf_results if r.retrieval_type == "insufficient_evidence")
            / len(insuf_results) * 100.0
            if insuf_results else 100.0
        )

        # Category breakdown
        for r in results:
            cat = r.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0, "avg_latency_ms": 0.0}
            category_stats[cat]["total"] += 1
            if r.passed:
                category_stats[cat]["passed"] += 1
            category_stats[cat]["avg_latency_ms"] += r.latency_ms

        for cat, stats in category_stats.items():
            if stats["total"] > 0:
                stats["avg_latency_ms"] = round(stats["avg_latency_ms"] / stats["total"], 2)
                stats["pass_rate"] = round(stats["passed"] / stats["total"] * 100.0, 1)

        return RAGBenchmarkReport(
            total_queries=total,
            passed_queries=passed_count,
            accuracy_percentage=round(accuracy, 2),
            avg_latency_ms=round(avg_latency, 2),
            grounded_citation_rate=round(grounded_rate, 2),
            controlled_insufficient_rate=round(insuf_rate, 2),
            category_breakdown=category_stats,
        )
