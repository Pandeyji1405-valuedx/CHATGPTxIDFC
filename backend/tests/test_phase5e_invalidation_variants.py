"""
Phase 5E: Version-Aware Cache Invalidation + Governed Question Variants
Test Suite.

BRD Acceptance Criteria Map:

A.  ACTIVE version has reusable cache — answer is returned
B.  SUPERSEDED version → dependent CachedAnswers invalidated
C.  INACTIVE version → dependent CachedAnswers invalidated
D.  WITHDRAWN-equivalent (INACTIVE, secondary test) → invalidated
E.  Redis exact key is evicted on invalidation
F.  Redis failure does NOT corrupt PostgreSQL invalidation
G.  Historical Conversation records remain unchanged after invalidation
H.  Historical Message records remain unchanged after invalidation
I.  Invalidation is idempotent
J.  Multiple CachedAnswers depending on one version → all invalidated
K.  One CachedAnswer depending on multiple versions → correct handling
L.  Valid active variant points to approved CachedAnswer
M.  Active variant can be resolved (variant hash → CachedAnswer)
N.  Inactive variant cannot be resolved
O.  Variant preserves tenant isolation
P.  Variant preserves document-version provenance (cache_answer_id traceable)
Q.  Materially different regulatory entity type is rejected by validation gate
R.  Variant cannot revive an inactive CachedAnswer
S.  Invalidated CachedAnswer is not promoted back into Redis by variant lookup
T.  Existing 10 governance gates still apply after variant resolution
U.  Variant generation skips duplicate hashes (idempotent)
V.  Variant with too-short text is rejected by validate_variant
W.  Direct invalidate_cache_answer deactivates answer + variants
X.  Variant generation is skipped for inactive CachedAnswer
"""

import json
import uuid
from datetime import datetime, date, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fakeredis
import pytest
from sqlalchemy import select

from app.models.cache import CachedAnswer, CacheDocumentDependency, QuestionVariant
from app.models.chat import Conversation, Message, MessageRole
from app.models.document import Document, DocumentStatus, DocumentVersion, IngestionStatus
from app.models.user import User, UserRole
from app.services.cache.cache_service import CacheService, hash_query
from app.services.cache.invalidation_service import CacheInvalidationService
from app.services.cache.redis_service import RedisService, set_mock_redis_client
from app.services.cache.validation_gate import CacheValidationGate
from app.services.cache.variant_service import VariantService
from app.services.rag.llm_gateway import MockLLMAdapter


# ------------------------------------------------------------------ #
# Shared Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def setup_mock_redis():
    """Inject fakeredis for all tests in this module."""
    fake_client = fakeredis.FakeRedis(decode_responses=True)
    set_mock_redis_client(fake_client)
    yield fake_client
    set_mock_redis_client(None)


@pytest.fixture
def test_user():
    return User(
        id=uuid.uuid4(),
        email="user@idfcbank.com",
        password_hash="hash",
        name="Regular User",
        role=UserRole.USER,
        is_active=True,
    )


@pytest.fixture
async def base_document_version(db_session):
    """Create an ACTIVE document + version ready for cache dependency tests."""
    uid = uuid.uuid4().hex[:8]
    doc = Document(
        id=uuid.uuid4(),
        document_key=f"md-kyc-{uid}",
        title="Master Direction KYC 2016",
        document_type="master_direction",
        circular_number="RBI/DBR/2015-16/18",
    )
    db_session.add(doc)
    await db_session.flush()

    ver = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_number=1,
        status=DocumentStatus.ACTIVE,
        ingestion_status=IngestionStatus.COMPLETED,
        file_name="kyc.pdf",
        file_hash=uid * 4,
        storage_path="storage/kyc.pdf",
    )
    db_session.add(ver)
    await db_session.commit()
    await db_session.refresh(ver)
    return doc, ver


def _make_cached_answer(ver, query="What are KYC requirements?", tenant="idfc_bank") -> CachedAnswer:
    """Helper to create a CachedAnswer ORM object without persisting."""
    return CachedAnswer(
        id=uuid.uuid4(),
        query_hash=hash_query(query),
        original_user_query=query,
        canonical_query=query,
        answer="KYC requires customer identification and due diligence.",
        citations=[
            {
                "document_id": str(uuid.uuid4()),
                "version_id": str(ver.id),
                "chunk_id": "chunk-1",
                "document_title": "Master Direction KYC",
                "page_number": 1,
                "version_number": ver.version_number,
            }
        ],
        tenant_id=tenant,
        required_role="USER",
        is_active=True,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )


async def _persist_cache_with_dep(db, cached_answer, ver):
    """Persist a CachedAnswer + its document dependency."""
    db.add(cached_answer)
    await db.flush()
    dep = CacheDocumentDependency(
        cache_answer_id=cached_answer.id,
        document_version_id=ver.id,
    )
    db.add(dep)
    await db.commit()
    await db.refresh(cached_answer)
    return cached_answer


# ------------------------------------------------------------------ #
# A. ACTIVE version has reusable cache — answer returned
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_a_active_version_cache_returns_answer(
    db_session, test_user, base_document_version
):
    """[A] CachedAnswer with ACTIVE version passes governance."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver)
    await _persist_cache_with_dep(db_session, cached, ver)

    gate = CacheValidationGate()
    candidate = {
        "is_active": True,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "tenant_id": "idfc_bank",
        "required_role": "USER",
        "citations": [{"version_id": str(ver.id), "chunk_id": "chunk-1"}],
    }
    approved, reason = await gate.validate_candidate(candidate, test_user, db_session)
    assert approved, f"Unexpected rejection: {reason}"


# ------------------------------------------------------------------ #
# B. SUPERSEDED version invalidates dependent cache
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_b_superseded_version_invalidates_cache(
    db_session, base_document_version
):
    """[B] Setting status=SUPERSEDED then calling invalidation deactivates cache."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver)
    await _persist_cache_with_dep(db_session, cached, ver)

    # Supersede the version
    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    count = await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    assert count == 1

    refreshed = (
        await db_session.execute(
            select(CachedAnswer).where(CachedAnswer.id == cached.id)
        )
    ).scalar_one()
    assert refreshed.is_active is False


# ------------------------------------------------------------------ #
# C. INACTIVE version invalidates dependent cache
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_c_inactive_version_invalidates_cache(
    db_session, base_document_version
):
    """[C] Status=INACTIVE → invalidation deactivates dependent CachedAnswer."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What is CRAR limit?")
    await _persist_cache_with_dep(db_session, cached, ver)

    ver.status = DocumentStatus.INACTIVE
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    count = await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    assert count == 1

    refreshed = (
        await db_session.execute(
            select(CachedAnswer).where(CachedAnswer.id == cached.id)
        )
    ).scalar_one()
    assert refreshed.is_active is False


# ------------------------------------------------------------------ #
# D. WITHDRAWN (INACTIVE secondary confirmation)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_d_withdrawn_equivalent_invalidates_cache(
    db_session, base_document_version
):
    """[D] 'Withdrawn' maps to INACTIVE in the BRD; invalidation must work."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What are liquidity norms?")
    await _persist_cache_with_dep(db_session, cached, ver)

    # Withdrawn = INACTIVE in the current model
    ver.status = DocumentStatus.INACTIVE
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    count = await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    assert count >= 1

    refreshed = (
        await db_session.execute(
            select(CachedAnswer).where(CachedAnswer.id == cached.id)
        )
    ).scalar_one()
    assert refreshed.is_active is False


# ------------------------------------------------------------------ #
# E. Redis exact key is evicted on invalidation
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_e_redis_key_evicted_on_invalidation(
    db_session, base_document_version, setup_mock_redis
):
    """[E] After invalidation, the Redis version index set is removed."""
    doc, ver = base_document_version
    q = "What is the NPA classification period?"
    cached = _make_cached_answer(ver, query=q)
    await _persist_cache_with_dep(db_session, cached, ver)

    # Index in Redis (simulates write_through behavior)
    q_hash = hash_query(q)
    redis_svc = RedisService()
    await redis_svc.index_version_dependency(str(ver.id), q_hash)
    await redis_svc.set_exact_cache(q_hash, {"answer": "cached", "is_active": True})

    # Confirm key exists
    client = setup_mock_redis
    assert await client.scard(f"cache_index:version:{ver.id}") == 1
    assert await client.get(f"exact_cache:{q_hash}") is not None

    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=redis_svc)
    await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    # Index set must be removed
    assert await client.scard(f"cache_index:version:{ver.id}") == 0
    # Exact cache key must be evicted
    assert await client.get(f"exact_cache:{q_hash}") is None


# ------------------------------------------------------------------ #
# F. Redis failure does NOT corrupt PostgreSQL invalidation
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_f_redis_failure_does_not_corrupt_pg_invalidation(
    db_session, base_document_version
):
    """[F] Redis eviction error is logged but PG invalidation still commits."""

    class BrokenRedis(RedisService):
        async def evict_version_keys(self, version_id: str) -> int:
            raise ConnectionError("Redis is down")

    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What is the credit risk weight?")
    await _persist_cache_with_dep(db_session, cached, ver)

    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=BrokenRedis())
    count = await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    # PostgreSQL invalidation must succeed despite Redis failure
    assert count == 1
    refreshed = (
        await db_session.execute(
            select(CachedAnswer).where(CachedAnswer.id == cached.id)
        )
    ).scalar_one()
    assert refreshed.is_active is False


# ------------------------------------------------------------------ #
# G. Historical Conversation records unchanged
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_g_historical_conversations_unchanged(db_session, base_document_version):
    """[G] Conversations are NEVER modified by cache invalidation."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What is the SARFAESI threshold?")
    await _persist_cache_with_dep(db_session, cached, ver)

    # Create a conversation
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Regulatory Q&A",
        message_count=1,
    )
    db_session.add(conv)
    await db_session.commit()
    conv_id = conv.id

    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    # Conversation must still exist and be unchanged
    result = await db_session.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )
    conv_after = result.scalar_one_or_none()
    assert conv_after is not None, "Conversation was deleted — this is forbidden."
    assert conv_after.title == "Regulatory Q&A"


# ------------------------------------------------------------------ #
# H. Historical Message records unchanged
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_h_historical_messages_unchanged(db_session, base_document_version):
    """[H] Messages are NEVER modified or deleted by cache invalidation."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What is the Prompt Corrective Action framework?")
    await _persist_cache_with_dep(db_session, cached, ver)

    conv = Conversation(id=uuid.uuid4(), user_id=uuid.uuid4(), title="Test", message_count=1)
    db_session.add(conv)
    await db_session.flush()

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role=MessageRole.USER,
        content="What is the Prompt Corrective Action framework?",
    )
    db_session.add(msg)
    await db_session.commit()
    msg_id = msg.id

    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    result = await db_session.execute(
        select(Message).where(Message.id == msg_id)
    )
    msg_after = result.scalar_one_or_none()
    assert msg_after is not None, "Message was deleted — this is forbidden."
    assert msg_after.content == "What is the Prompt Corrective Action framework?"


# ------------------------------------------------------------------ #
# I. Invalidation is idempotent
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_i_invalidation_is_idempotent(db_session, base_document_version):
    """[I] Running invalidation twice returns 0 on second call; state is consistent."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What is the SLR requirement?")
    await _persist_cache_with_dep(db_session, cached, ver)

    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())

    count1 = await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    count2 = await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    assert count1 == 1
    assert count2 == 0  # Already inactive; idempotent


# ------------------------------------------------------------------ #
# J. Multiple CachedAnswers depending on one version are all invalidated
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_j_multiple_answers_all_invalidated(db_session, base_document_version):
    """[J] All three CachedAnswers depending on the same version are deactivated."""
    doc, ver = base_document_version
    queries = [
        "What is the KYC definition?",
        "Who must perform KYC?",
        "When is re-KYC required?",
    ]
    cached_ids = []
    for q in queries:
        ca = _make_cached_answer(ver, query=q)
        await _persist_cache_with_dep(db_session, ca, ver)
        cached_ids.append(ca.id)

    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    count = await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    assert count == 3
    for ca_id in cached_ids:
        rec = (await db_session.execute(
            select(CachedAnswer).where(CachedAnswer.id == ca_id)
        )).scalar_one()
        assert rec.is_active is False


# ------------------------------------------------------------------ #
# K. One CachedAnswer depending on multiple versions
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_k_answer_with_multiple_version_deps(db_session, base_document_version):
    """[K] Answer with 2 version deps: invalidating either version deactivates it."""
    doc, ver1 = base_document_version

    # Create a second version
    ver2 = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc.id,
        version_number=2,
        status=DocumentStatus.ACTIVE,
        ingestion_status=IngestionStatus.COMPLETED,
        file_name="kyc_v2.pdf",
        file_hash="v2hashxyz" * 4,
        storage_path="storage/kyc_v2.pdf",
    )
    db_session.add(ver2)
    await db_session.flush()

    ca = _make_cached_answer(ver1, query="Cross-version KYC question?")
    db_session.add(ca)
    await db_session.flush()

    dep1 = CacheDocumentDependency(cache_answer_id=ca.id, document_version_id=ver1.id)
    dep2 = CacheDocumentDependency(cache_answer_id=ca.id, document_version_id=ver2.id)
    db_session.add(dep1)
    db_session.add(dep2)
    await db_session.commit()

    # Invalidate via ver1
    ver1.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    count = await invalidation_svc.invalidate_version_dependencies(ver1.id, db_session)
    await db_session.commit()

    assert count == 1

    rec = (await db_session.execute(
        select(CachedAnswer).where(CachedAnswer.id == ca.id)
    )).scalar_one()
    assert rec.is_active is False


# ------------------------------------------------------------------ #
# L. Valid variant points to approved CachedAnswer
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_l_valid_variant_stored_correctly(db_session, base_document_version):
    """[L] A valid variant record is created and links to the CachedAnswer."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What are KYC requirements for individual customers?")
    await _persist_cache_with_dep(db_session, cached, ver)

    variant_text = "What does RBI require for KYC of individual clients?"
    v_hash = hash_query(variant_text)
    variant = QuestionVariant(
        id=uuid.uuid4(),
        cache_answer_id=cached.id,
        variant_query=variant_text,
        variant_hash=v_hash,
        is_active=True,
        tenant_id="idfc_bank",
    )
    db_session.add(variant)
    await db_session.commit()

    # Verify linkage
    result = await db_session.execute(
        select(QuestionVariant).where(QuestionVariant.cache_answer_id == cached.id)
    )
    variants = result.scalars().all()
    assert len(variants) == 1
    assert variants[0].is_active is True
    assert variants[0].tenant_id == "idfc_bank"
    assert variants[0].cache_answer_id == cached.id


# ------------------------------------------------------------------ #
# M. Active variant can be resolved to CachedAnswer
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_m_active_variant_resolves_to_cached_answer(
    db_session, base_document_version
):
    """[M] resolve_variant returns the CachedAnswer for an active variant."""
    doc, ver = base_document_version
    canonical = "What are the RBI KYC requirements for corporate entities?"
    cached = _make_cached_answer(ver, query=canonical)
    await _persist_cache_with_dep(db_session, cached, ver)

    variant_text = "What KYC must be done for corporate customers per RBI?"
    v_hash = hash_query(variant_text)
    variant = QuestionVariant(
        id=uuid.uuid4(),
        cache_answer_id=cached.id,
        variant_query=variant_text,
        variant_hash=v_hash,
        is_active=True,
        tenant_id="idfc_bank",
    )
    db_session.add(variant)
    await db_session.commit()

    variant_svc = VariantService()
    result = await variant_svc.resolve_variant(v_hash, db_session, tenant_id="idfc_bank")
    assert result is not None
    assert result.id == cached.id


# ------------------------------------------------------------------ #
# N. Inactive variant cannot be resolved
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_n_inactive_variant_not_resolved(db_session, base_document_version):
    """[N] is_active=False variant returns None from resolve_variant."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What are CRR requirements?")
    await _persist_cache_with_dep(db_session, cached, ver)

    variant_text = "What is the cash reserve ratio?"
    v_hash = hash_query(variant_text)
    variant = QuestionVariant(
        id=uuid.uuid4(),
        cache_answer_id=cached.id,
        variant_query=variant_text,
        variant_hash=v_hash,
        is_active=False,  # Already deactivated
        tenant_id="idfc_bank",
    )
    db_session.add(variant)
    await db_session.commit()

    variant_svc = VariantService()
    result = await variant_svc.resolve_variant(v_hash, db_session, tenant_id="idfc_bank")
    assert result is None


# ------------------------------------------------------------------ #
# O. Variant preserves tenant isolation
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_o_variant_tenant_isolation(db_session, base_document_version):
    """[O] Variant for 'idfc_bank' is not resolved for 'rival_bank'."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What is the LCR requirement?")
    await _persist_cache_with_dep(db_session, cached, ver)

    variant_text = "What liquidity coverage ratio must banks maintain?"
    v_hash = hash_query(variant_text)
    variant = QuestionVariant(
        id=uuid.uuid4(),
        cache_answer_id=cached.id,
        variant_query=variant_text,
        variant_hash=v_hash,
        is_active=True,
        tenant_id="idfc_bank",
    )
    db_session.add(variant)
    await db_session.commit()

    variant_svc = VariantService()

    # Correct tenant: should resolve
    result_correct = await variant_svc.resolve_variant(v_hash, db_session, tenant_id="idfc_bank")
    assert result_correct is not None

    # Wrong tenant: must NOT resolve
    result_wrong = await variant_svc.resolve_variant(v_hash, db_session, tenant_id="rival_bank")
    assert result_wrong is None


# ------------------------------------------------------------------ #
# P. Variant preserves document-version provenance
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_p_variant_preserves_provenance(db_session, base_document_version):
    """[P] Variant → CachedAnswer → CacheDocumentDependency chain is intact."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What are the prudential norms for NBFCs?")
    await _persist_cache_with_dep(db_session, cached, ver)

    variant_text = "What norms must NBFCs follow under RBI prudential guidelines?"
    v_hash = hash_query(variant_text)
    variant = QuestionVariant(
        id=uuid.uuid4(),
        cache_answer_id=cached.id,
        variant_query=variant_text,
        variant_hash=v_hash,
        is_active=True,
        tenant_id="idfc_bank",
    )
    db_session.add(variant)
    await db_session.commit()

    # Trace: variant → cached_answer_id → cache_document_dependencies → version_id
    variant_svc = VariantService()
    resolved = await variant_svc.resolve_variant(v_hash, db_session, tenant_id="idfc_bank")
    assert resolved is not None

    dep_result = await db_session.execute(
        select(CacheDocumentDependency).where(
            CacheDocumentDependency.cache_answer_id == resolved.id
        )
    )
    deps = dep_result.scalars().all()
    assert len(deps) == 1
    assert deps[0].document_version_id == ver.id


# ------------------------------------------------------------------ #
# Q. Materially different regulatory entity type rejected by validation gate
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_q_entity_scope_change_rejected(base_document_version):
    """[Q] Variant that changes 'banks' to 'NBFCs' is rejected by _validate_variant."""
    doc, ver = base_document_version
    variant_svc = VariantService()

    canonical = "What are the KYC requirements for banks under RBI?"
    # Scope change: banks → NBFCs
    bad_variant = "What are the KYC requirements for NBFCs under RBI?"

    is_valid, reason = variant_svc._validate_variant(
        variant_text=bad_variant,
        canonical_query=canonical,
        tenant_id="idfc_bank",
        cached_answer_tenant="idfc_bank",
    )
    assert not is_valid
    assert "nbfc" in reason.lower() or "scope" in reason.lower()


# ------------------------------------------------------------------ #
# R. Variant cannot revive an inactive CachedAnswer
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_r_variant_cannot_revive_inactive_answer(
    db_session, base_document_version
):
    """[R] resolve_variant returns None when CachedAnswer is_active=False."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What are the repo rate guidelines?")
    await _persist_cache_with_dep(db_session, cached, ver)

    variant_text = "What is the repo rate as per RBI?"
    v_hash = hash_query(variant_text)
    variant = QuestionVariant(
        id=uuid.uuid4(),
        cache_answer_id=cached.id,
        variant_query=variant_text,
        variant_hash=v_hash,
        is_active=True,
        tenant_id="idfc_bank",
    )
    db_session.add(variant)
    await db_session.commit()

    # Deactivate the cached answer (simulates version invalidation)
    cached.is_active = False
    await db_session.commit()

    variant_svc = VariantService()
    result = await variant_svc.resolve_variant(v_hash, db_session, tenant_id="idfc_bank")
    assert result is None, "Variant must not revive an inactive CachedAnswer."


# ------------------------------------------------------------------ #
# S. Invalidated answer not promoted back into Redis by variant lookup
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_s_invalidated_answer_not_promoted_to_redis(
    db_session, test_user, base_document_version, setup_mock_redis
):
    """[S] After invalidation, variant lookup returns None — Redis stays clean."""
    doc, ver = base_document_version
    canonical = "What is the minimum capital requirement for banks?"
    cached = _make_cached_answer(ver, query=canonical)
    await _persist_cache_with_dep(db_session, cached, ver)

    variant_text = "What capital must banks hold under RBI norms?"
    v_hash = hash_query(variant_text)
    variant = QuestionVariant(
        id=uuid.uuid4(),
        cache_answer_id=cached.id,
        variant_query=variant_text,
        variant_hash=v_hash,
        is_active=True,
        tenant_id="idfc_bank",
    )
    db_session.add(variant)
    await db_session.commit()

    # Invalidate
    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()
    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    await invalidation_svc.invalidate_version_dependencies(ver.id, db_session)
    await db_session.commit()

    # Variant must not resolve
    variant_svc = VariantService()
    cache_service = CacheService(variant_service=variant_svc)
    result, cache_type, _ = await cache_service.lookup(
        canonical_query=variant_text,
        user=test_user,
        db=db_session,
        tenant_id="idfc_bank",
    )

    assert result is None
    assert cache_type == "none"

    # Redis must have no entry for this hash
    client = setup_mock_redis
    assert await client.get(f"exact_cache:{v_hash}") is None


# ------------------------------------------------------------------ #
# T. Existing 10 governance gates still apply after variant resolution
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_t_governance_gates_apply_after_variant_resolution(
    db_session, test_user, base_document_version
):
    """[T] Gate 6 (version freshness) rejects resolved variant if version is SUPERSEDED."""
    doc, ver = base_document_version
    canonical = "What are the requirements for digital lending?"
    cached = _make_cached_answer(ver, query=canonical)
    await _persist_cache_with_dep(db_session, cached, ver)

    variant_text = "What must banks follow for online loans under RBI?"
    v_hash = hash_query(variant_text)
    variant = QuestionVariant(
        id=uuid.uuid4(),
        cache_answer_id=cached.id,
        variant_query=variant_text,
        variant_hash=v_hash,
        is_active=True,
        tenant_id="idfc_bank",
    )
    db_session.add(variant)
    await db_session.commit()

    # Supersede version — but don't run invalidation_service (testing gate directly)
    ver.status = DocumentStatus.SUPERSEDED
    await db_session.commit()

    # Governance gate must reject the answer
    gate = CacheValidationGate()
    candidate = {
        "is_active": True,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "tenant_id": "idfc_bank",
        "required_role": "USER",
        "citations": [{"version_id": str(ver.id), "chunk_id": "chunk-1"}],
    }
    approved, reason = await gate.validate_candidate(candidate, test_user, db_session)
    assert not approved
    assert "SUPERSEDED" in reason or "ACTIVE" in reason


# ------------------------------------------------------------------ #
# U. Variant generation skips duplicates (idempotent)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_u_variant_generation_skips_duplicates(
    db_session, base_document_version
):
    """[U] Calling create_variants twice does not create duplicate variant records."""
    doc, ver = base_document_version
    canonical = "What is the definition of NPA for banks?"
    cached = _make_cached_answer(ver, query=canonical)
    await _persist_cache_with_dep(db_session, cached, ver)

    class FixedVariantLLM(MockLLMAdapter):
        async def generate(self, prompt):
            from app.services.rag.llm_gateway import LLMResponse
            return LLMResponse(
                answer='{"variants": ["Define NPA for scheduled banks.", "What constitutes NPA per RBI?"]}',
                citation_ids=[],
                raw_response="",
            )

    variant_svc = VariantService(llm_gateway=FixedVariantLLM())

    count1 = await variant_svc.create_variants(cached, canonical, db_session)
    await db_session.commit()

    count2 = await variant_svc.create_variants(cached, canonical, db_session)
    await db_session.commit()

    # Second call should not add duplicates
    assert count2 == 0  # All hashes already stored


# ------------------------------------------------------------------ #
# V. Variant with too-short text is rejected
# ------------------------------------------------------------------ #

def test_v_too_short_variant_rejected():
    """[V] Variant shorter than 10 chars is rejected by _validate_variant."""
    svc = VariantService()
    is_valid, reason = svc._validate_variant(
        variant_text="NPA?",
        canonical_query="What is the NPA classification norm for banks?",
        tenant_id="idfc_bank",
        cached_answer_tenant="idfc_bank",
    )
    assert not is_valid
    assert "short" in reason.lower()


# ------------------------------------------------------------------ #
# W. Direct invalidate_cache_answer deactivates answer + variants
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_w_direct_cache_answer_invalidation(
    db_session, base_document_version
):
    """[W] invalidate_cache_answer() deactivates the answer and all its variants."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What are the RTGS settlement timings?")
    await _persist_cache_with_dep(db_session, cached, ver)

    # Add two variants
    for variant_text in [
        "What time does RTGS work?",
        "RTGS working hours as per RBI?",
    ]:
        v = QuestionVariant(
            id=uuid.uuid4(),
            cache_answer_id=cached.id,
            variant_query=variant_text,
            variant_hash=hash_query(variant_text),
            is_active=True,
            tenant_id="idfc_bank",
        )
        db_session.add(v)
    await db_session.commit()

    invalidation_svc = CacheInvalidationService(redis_service=RedisService())
    result = await invalidation_svc.invalidate_cache_answer(cached.id, db_session)
    await db_session.commit()

    assert result is True

    # Answer deactivated
    refreshed_answer = (
        await db_session.execute(select(CachedAnswer).where(CachedAnswer.id == cached.id))
    ).scalar_one()
    assert refreshed_answer.is_active is False

    # Both variants deactivated
    result_variants = await db_session.execute(
        select(QuestionVariant).where(QuestionVariant.cache_answer_id == cached.id)
    )
    for v in result_variants.scalars().all():
        assert v.is_active is False


# ------------------------------------------------------------------ #
# X. Variant generation skipped for inactive CachedAnswer
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_x_variant_generation_skips_inactive_answer(
    db_session, base_document_version
):
    """[X] create_variants() returns 0 and stores nothing for inactive answer."""
    doc, ver = base_document_version
    cached = _make_cached_answer(ver, query="What are the AML thresholds?")
    await _persist_cache_with_dep(db_session, cached, ver)

    # Deactivate the answer
    cached.is_active = False
    await db_session.commit()

    class FixedVariantLLM(MockLLMAdapter):
        async def generate(self, prompt):
            from app.services.rag.llm_gateway import LLMResponse
            return LLMResponse(
                answer='{"variants": ["What are AML limits under RBI?"]}',
                citation_ids=[],
                raw_response="",
            )

    variant_svc = VariantService(llm_gateway=FixedVariantLLM())
    count = await variant_svc.create_variants(
        cached_answer=cached,
        canonical_query="What are the AML thresholds?",
        db=db_session,
    )
    assert count == 0

    # Confirm no variants written
    result = await db_session.execute(
        select(QuestionVariant).where(QuestionVariant.cache_answer_id == cached.id)
    )
    assert len(result.scalars().all()) == 0
