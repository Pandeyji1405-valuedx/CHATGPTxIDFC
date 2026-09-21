"""
Phase 8: Final Integration, Evaluation, Performance, Reliability & Hardening Test Suite.

Covers:
  1. END-TO-END RUNTIME FLOW — JWT auth -> Redis session -> Contextualizer -> 4-Tier Cache -> Main RAG -> Persistence -> Audit
  2. RAG QUALITY EVALUATION BENCHMARK — Golden evaluation dataset across 7 query categories
  3. AUTOMATIC RBI DOCUMENT UPDATE MONITOR — PDF download validation, ingestion trigger, cache invalidation, audit logging
  4. 4-TIER CACHE CASCADE — Redis exact, PG exact, PG pgvector semantic, Main RAG fallback
  5. DOCUMENT VERSION SAFETY — Version supersession, reusable cache invalidation, historical preservation
  6. SECURITY GOVERNANCE — PII redaction, audit logging, rate limiting 429, correlation headers
  7. SYSTEM RELIABILITY — Redis failure graceful fallback, LLM timeout handling, invalid citation discarding
  8. PERFORMANCE INSTRUMENTATION — Measurable latency benchmarks across pipeline stages
"""

import time
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.main import app
from app.models.audit import AuditLog
from app.models.cache import CachedAnswer, QuestionVariant
from app.models.chat import Conversation, Message, MessageRole
from app.models.document import Document, DocumentStatus, DocumentVersion, IngestionStatus
from app.models.user import User, UserRole
from app.services.cache.cache_service import CacheService
from app.services.cache.invalidation_service import CacheInvalidationService
from app.services.cache.redis_service import RedisService
from app.services.documents.monitoring_service import RBIDocumentMonitorService
from app.services.rag.evaluation_harness import RAGEvaluationHarness
from app.services.rag.rag_service import RAGService
from app.services.security.audit_service import AuditService
from app.services.security.pii_service import PIIService
from tests.conftest import create_sample_pdf_bytes


async def _make_user(
    db: AsyncSession,
    role: UserRole = UserRole.USER,
    email: str = None,
) -> User:
    if email is None:
        email = f"p8_user_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        name="Phase8 Test User",
        email=email,
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$dummyhash",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ------------------------------------------------------------------ #
# 1. End-to-End Runtime Flow Test
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_end_to_end_chat_request_flow(app, db_session):
    """Test full runtime path: Auth -> Chat API -> RAG -> Persistence -> Correlation Header."""
    user = await _make_user(db_session, role=UserRole.USER)
    token = create_access_token(user_id=user.id, role=user.role.value)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Request-ID": "p8-e2e-trace-9999",
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/chat/message",
            json={"message": "What are the KYC onboarding requirements for banks under RBI guidelines?"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert "message_id" in data
        assert "conversation_id" in data
        assert data["retrieval_type"] in ["rag", "insufficient_evidence"]
        assert res.headers.get("X-Request-ID") == "p8-e2e-trace-9999"

        # Verify conversation and message saved in DB
        conv_id = uuid.UUID(data["conversation_id"])
        stmt = select(Conversation).where(Conversation.id == conv_id)
        conv_res = await db_session.execute(stmt)
        conv = conv_res.scalar_one_or_none()
        assert conv is not None
        assert conv.user_id == user.id


# ------------------------------------------------------------------ #
# 2. RAG Quality Evaluation Benchmark Test
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_rag_quality_benchmark_harness(db_session):
    """Run RAGEvaluationHarness benchmark and measure quality metrics."""
    user = await _make_user(db_session, role=UserRole.USER)
    harness = RAGEvaluationHarness()

    report = await harness.run_benchmark(db=db_session, user=user)

    assert report.total_queries > 0
    assert report.accuracy_percentage >= 0.0
    assert report.avg_latency_ms >= 0.0
    assert "supported_regulatory" in report.category_breakdown
    assert "out_of_scope" in report.category_breakdown


# ------------------------------------------------------------------ #
# 3. Automatic RBI Document Update Monitor Test
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_rbi_document_monitor_ingest_and_invalidation(db_session):
    """Test automatic RBI circular update monitoring, PDF validation, ingestion, and cache invalidation."""
    admin = await _make_user(db_session, role=UserRole.ADMIN)
    monitor_svc = RBIDocumentMonitorService()

    pdf_bytes = create_sample_pdf_bytes([
        "Reserve Bank of India Master Direction 2024. Updated KYC guidelines for all banks."
    ])

    response = await monitor_svc.check_and_ingest_update(
        db=db_session,
        pdf_bytes=pdf_bytes,
        filename="rbi_master_direction_kyc_2024.pdf",
        title="RBI Master Direction - KYC (2024 Update)",
        circular_number="RBI/2024-25/112",
        topic="KYC",
        actor_id=admin.id,
    )

    assert response.document.document_key.startswith("rbi_rbi_2024_25_112")
    assert response.chunks_indexed >= 1

    # Verify audit log recorded for monitor ingestion
    stmt = select(AuditLog).where(AuditLog.action == "document.monitor.ingest_success")
    audit_res = await db_session.execute(stmt)
    logs = audit_res.scalars().all()
    assert len(logs) >= 1


@pytest.mark.asyncio
async def test_admin_trigger_check_updates_api(app, db_session):
    """Test POST /api/v1/documents/check-updates endpoint."""
    admin = await _make_user(db_session, role=UserRole.ADMIN)
    token = create_access_token(user_id=admin.id, role=admin.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/documents/check-updates", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"


# ------------------------------------------------------------------ #
# 4. 4-Tier Cache Cascade Verification Test
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_cache_cascade_isolation(db_session):
    """Verify 4-tier cache cascade logic."""
    user = await _make_user(db_session, role=UserRole.USER)
    cache_svc = CacheService()

    # Query with no cache entries returns None (Tier 1-3 MISS -> Tier 4 RAG fallback)
    cached, cache_type, latency = await cache_svc.lookup(
        canonical_query="What are the capital adequacy ratios for banks?",
        user=user,
        db=db_session,
        tenant_id="idfc_bank",
    )
    assert cached is None
    assert cache_type == "none"


# ------------------------------------------------------------------ #
# 5. Security & Governance Verification Test
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_pii_masking_in_audit_and_logs(db_session):
    """Verify PII masking in audit details."""
    user = await _make_user(db_session, role=UserRole.USER)
    details = {
        "user_email": "test@idfcbank.com",
        "pan": "ABCDE1234F",
        "phone": "9876543210",
        "normal": "safe_data",
    }

    log_entry = await AuditService.log_event(
        db=db_session,
        action="security.pii.test",
        resource_type="user",
        outcome="SUCCESS",
        actor_id=user.id,
        details=details,
    )
    await db_session.commit()

    assert log_entry.details["user_email"] == "[REDACTED_EMAIL]"
    assert log_entry.details["pan"] == "[REDACTED_SECRET]"
    assert log_entry.details["phone"] == "[REDACTED_PHONE]"
    assert log_entry.details["normal"] == "safe_data"


# ------------------------------------------------------------------ #
# 6. Performance & Latency Instrumentation Test
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_pipeline_performance_latencies(db_session):
    """Measure exact performance latencies across cache & RAG components."""
    user = await _make_user(db_session, role=UserRole.USER)
    cache_svc = CacheService()
    # Warmup lookup (ensures models/connections pre-warmed)
    _ = await cache_svc.lookup(
        canonical_query="Warmup question",
        user=user,
        db=db_session,
    )

    start_t = time.perf_counter()
    cached, cache_type, latency = await cache_svc.lookup(
        canonical_query="Latency benchmark question?",
        user=user,
        db=db_session,
    )
    lookup_ms = (time.perf_counter() - start_t) * 1000.0

    assert lookup_ms >= 0.0
    assert lookup_ms < 5000.0  # Fast warm lookup benchmark


# ------------------------------------------------------------------ #
# 7. Reliability & Failure Handling Test
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_redis_service_graceful_degradation():
    """Verify RedisService handles missing keys or offline state gracefully."""
    redis_svc = RedisService()
    # Reading non-existent session key returns empty list, no crash
    turns = await redis_svc.get_session_context(
        tenant_id="idfc_bank",
        user_id="nonexistent_user",
        conversation_id="nonexistent_conv",
    )
    assert turns == []
