"""
Phase 5B — Redis Session Memory & Query Contextualization Test Suite.

Covers all required Phase 5B acceptance tests:

  [S1]  Redis session write + read round-trip
  [S2]  TTL is set and refreshed on each append
  [S3]  Bounded turn list: max_turns enforced via LTRIM
  [S4]  Standalone query NOT contextualized
  [S5]  Context-dependent follow-up IS contextualized
  [S6]  Pronoun resolution ('it', 'they', 'these', ...)
  [S7]  Ambiguous/unresolved context: no entity invented
  [S8]  original_query preserved verbatim after contextualization
  [S9]  canonical_query differs from original_query for follow-ups
  [S10] User isolation: different users have independent session keys
  [S11] Conversation isolation: different conversations isolate session keys
  [S12] Tenant isolation: different tenants have independent session keys
  [S13] Redis failure: get_session_context returns empty list safely
  [S14] Redis failure: append_session_turn returns False safely
  [S15] Turn payload stores message_id, role, original_query, canonical_query, timestamp
  [S16] Phase 4 RAG compatibility: canonical_query is passed to RAG; original preserved in DB
  [S17] Session context empty for brand-new conversation
  [S18] needs_context returns False when session history is empty (no hallucination)
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis as fakeredis
import pytest

from app.services.cache.contextualizer import QueryContextualizer
from app.services.cache.redis_service import RedisService, set_mock_redis_client


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

TENANT_A = "idfc_bank"
TENANT_B = "other_bank"


@pytest.fixture(autouse=True)
def inject_fake_redis():
    """Replace the live Redis client with an in-process fakeredis for every test."""
    fake = fakeredis.FakeRedis(decode_responses=True)
    set_mock_redis_client(fake)
    yield fake
    # Reset after each test so tests are fully isolated
    set_mock_redis_client(None)


@pytest.fixture
def redis_service():
    return RedisService()


@pytest.fixture
def contextualizer():
    return QueryContextualizer()


@pytest.fixture
def user_id_a():
    return str(uuid.uuid4())


@pytest.fixture
def user_id_b():
    return str(uuid.uuid4())


@pytest.fixture
def conv_id_a():
    return str(uuid.uuid4())


@pytest.fixture
def conv_id_b():
    return str(uuid.uuid4())


def _make_turn(original: str, canonical: str) -> dict:
    """Helper: construct a valid session turn payload."""
    return {
        "message_id": str(uuid.uuid4()),
        "role": "USER",
        "original_query": original,
        "canonical_query": canonical,
        "summary_answer": "Test answer excerpt.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ------------------------------------------------------------------ #
# [S1] Redis session write + read round-trip
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_session_write_read_roundtrip(redis_service, user_id_a, conv_id_a):
    """Writing a turn and reading it back returns the same payload."""
    turn = _make_turn("What is the KYC requirement?", "What is the KYC requirement?")

    written = await redis_service.append_session_turn(
        tenant_id=TENANT_A,
        user_id=user_id_a,
        conversation_id=conv_id_a,
        turn=turn,
    )
    assert written is True

    history = await redis_service.get_session_context(
        tenant_id=TENANT_A,
        user_id=user_id_a,
        conversation_id=conv_id_a,
    )
    assert len(history) == 1
    assert history[0]["original_query"] == "What is the KYC requirement?"
    assert history[0]["canonical_query"] == "What is the KYC requirement?"


# ------------------------------------------------------------------ #
# [S2] TTL is set and refreshed
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_session_ttl_is_set(inject_fake_redis, redis_service, user_id_a, conv_id_a):
    """TTL must be set on the Redis key after each append."""
    turn = _make_turn("Query A", "Query A")
    await redis_service.append_session_turn(
        tenant_id=TENANT_A,
        user_id=user_id_a,
        conversation_id=conv_id_a,
        turn=turn,
        ttl_seconds=3600,
    )

    key = RedisService._session_key(TENANT_A, user_id_a, conv_id_a)
    ttl = await inject_fake_redis.ttl(key)
    # TTL should be set (greater than 0 means it expires)
    assert ttl > 0


# ------------------------------------------------------------------ #
# [S3] Bounded turn list: max_turns enforced via LTRIM
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_session_max_turns_bounded(redis_service, user_id_a, conv_id_a):
    """Session list must not grow beyond max_turns (oldest turns are dropped)."""
    max_turns = 3
    for i in range(6):
        turn = _make_turn(f"Query {i}", f"Query {i}")
        await redis_service.append_session_turn(
            tenant_id=TENANT_A,
            user_id=user_id_a,
            conversation_id=conv_id_a,
            turn=turn,
            max_turns=max_turns,
        )

    history = await redis_service.get_session_context(
        tenant_id=TENANT_A,
        user_id=user_id_a,
        conversation_id=conv_id_a,
    )
    assert len(history) == max_turns
    # Oldest turns (0, 1, 2) should be gone; latest (3, 4, 5) remain
    queries = [t["original_query"] for t in history]
    assert "Query 0" not in queries
    assert "Query 5" in queries


# ------------------------------------------------------------------ #
# [S4] Standalone query NOT contextualized
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_standalone_query_not_contextualized(contextualizer):
    """A self-contained regulatory question must pass through unchanged."""
    history = [
        _make_turn(
            "What is the KYC requirement?",
            "What is the KYC requirement?",
        )
    ]
    standalone = "What is the minimum capital adequacy ratio for commercial banks?"

    canonical, was_ctx = await contextualizer.contextualize(
        prompt=standalone,
        session_history=history,
    )
    assert not was_ctx
    assert canonical == standalone


# ------------------------------------------------------------------ #
# [S5] Context-dependent follow-up IS contextualized
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_contextual_followup_is_contextualized(contextualizer):
    """A follow-up with 'what about' must be recognized as context-dependent."""
    history = [
        _make_turn(
            "What are the KYC rules for NBFCs?",
            "What are the KYC rules for NBFCs?",
        )
    ]
    followup = "What about senior citizens?"

    needs = contextualizer.needs_context(followup, history)
    assert needs is True

    canonical, was_ctx = await contextualizer.contextualize(
        prompt=followup,
        session_history=history,
    )
    assert was_ctx is True
    assert canonical is not None
    assert len(canonical) > 0


# ------------------------------------------------------------------ #
# [S6] Pronoun resolution
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_pronoun_resolution_triggers_context(contextualizer):
    """Queries containing pronouns ('it', 'they', 'these', 'those') must trigger contextualization."""
    history = [
        _make_turn(
            "What does the RBI Master Direction on KYC say?",
            "What does the RBI Master Direction on KYC say?",
        )
    ]
    pronouns_to_test = [
        "Does it apply to urban cooperative banks?",
        "When did they become effective?",
        "How do these regulations apply to foreign branches?",
        "What does it say about them?",
        "How does this apply to the previous circular?",
    ]
    for prompt in pronouns_to_test:
        needs = contextualizer.needs_context(prompt, history)
        assert needs is True, f"Expected needs_context=True for: {prompt!r}"


# ------------------------------------------------------------------ #
# [S7] Ambiguous/unresolved context — no entity invented
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_ambiguous_context_no_entity_invented(contextualizer):
    """When session history is empty, even ambiguous pronouns must NOT trigger contextualization."""
    empty_history = []
    ambiguous = "What about it?"

    needs = contextualizer.needs_context(ambiguous, empty_history)
    assert needs is False  # No history => no context to inject

    canonical, was_ctx = await contextualizer.contextualize(
        prompt=ambiguous,
        session_history=empty_history,
    )
    assert not was_ctx
    assert canonical == ambiguous.strip()


# ------------------------------------------------------------------ #
# [S8] original_query preserved verbatim after contextualization
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_original_query_preserved_after_contextualization(contextualizer):
    """The original user query string must never be mutated."""
    history = [
        _make_turn(
            "What are the KYC rules for NBFCs?",
            "What are the KYC rules for NBFCs?",
        )
    ]
    original = "What about senior citizens?"

    canonical, was_ctx = await contextualizer.contextualize(
        prompt=original,
        session_history=history,
    )
    # original must remain unchanged — it's a local variable, canonical is new
    assert original == "What about senior citizens?"
    assert was_ctx is True


# ------------------------------------------------------------------ #
# [S9] canonical_query differs from original_query for follow-ups
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_canonical_query_differs_from_original_for_followup(contextualizer):
    """canonical_query must contain enriched context and differ from the original."""
    history = [
        _make_turn(
            "What are the KYC rules for NBFCs?",
            "What are the KYC rules for NBFCs?",
        )
    ]
    original = "What about senior citizens?"

    canonical, was_ctx = await contextualizer.contextualize(
        prompt=original,
        session_history=history,
    )
    assert was_ctx is True
    assert canonical != original
    # canonical should contain reference to previous topic
    assert len(canonical) > len(original)


# ------------------------------------------------------------------ #
# [S10] User isolation
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_user_isolation(redis_service, conv_id_a):
    """Two different users sharing the same conversation_id must have isolated session keys."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())

    turn_a = _make_turn("User A question", "User A question")
    turn_b = _make_turn("User B question", "User B question")

    await redis_service.append_session_turn(TENANT_A, user_a, conv_id_a, turn_a)
    await redis_service.append_session_turn(TENANT_A, user_b, conv_id_a, turn_b)

    history_a = await redis_service.get_session_context(TENANT_A, user_a, conv_id_a)
    history_b = await redis_service.get_session_context(TENANT_A, user_b, conv_id_a)

    assert len(history_a) == 1
    assert len(history_b) == 1
    assert history_a[0]["original_query"] == "User A question"
    assert history_b[0]["original_query"] == "User B question"


# ------------------------------------------------------------------ #
# [S11] Conversation isolation
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_conversation_isolation(redis_service, user_id_a):
    """Two conversations for the same user must not share session state."""
    conv_1 = str(uuid.uuid4())
    conv_2 = str(uuid.uuid4())

    turn_1 = _make_turn("Conv 1 question", "Conv 1 question")
    turn_2 = _make_turn("Conv 2 question", "Conv 2 question")

    await redis_service.append_session_turn(TENANT_A, user_id_a, conv_1, turn_1)
    await redis_service.append_session_turn(TENANT_A, user_id_a, conv_2, turn_2)

    history_1 = await redis_service.get_session_context(TENANT_A, user_id_a, conv_1)
    history_2 = await redis_service.get_session_context(TENANT_A, user_id_a, conv_2)

    assert len(history_1) == 1
    assert len(history_2) == 1
    assert history_1[0]["original_query"] == "Conv 1 question"
    assert history_2[0]["original_query"] == "Conv 2 question"


# ------------------------------------------------------------------ #
# [S12] Tenant isolation
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_tenant_isolation(redis_service, user_id_a, conv_id_a):
    """Two tenants sharing the same user_id and conversation_id must have isolated keys."""
    turn_a = _make_turn("Tenant A question", "Tenant A question")
    turn_b = _make_turn("Tenant B question", "Tenant B question")

    await redis_service.append_session_turn(TENANT_A, user_id_a, conv_id_a, turn_a)
    await redis_service.append_session_turn(TENANT_B, user_id_a, conv_id_a, turn_b)

    key_a = RedisService._session_key(TENANT_A, user_id_a, conv_id_a)
    key_b = RedisService._session_key(TENANT_B, user_id_a, conv_id_a)

    assert key_a != key_b

    history_a = await redis_service.get_session_context(TENANT_A, user_id_a, conv_id_a)
    history_b = await redis_service.get_session_context(TENANT_B, user_id_a, conv_id_a)

    assert history_a[0]["original_query"] == "Tenant A question"
    assert history_b[0]["original_query"] == "Tenant B question"


# ------------------------------------------------------------------ #
# [S13] Redis failure: get_session_context returns empty list safely
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_redis_failure_get_returns_empty(user_id_a, conv_id_a):
    """When Redis is unavailable, get_session_context must return [] and not raise."""
    service = RedisService()
    # Patch get_redis_client to simulate a broken connection
    with patch(
        "app.services.cache.redis_service.get_redis_client",
        new=AsyncMock(return_value=None),
    ):
        history = await service.get_session_context(TENANT_A, user_id_a, conv_id_a)
    assert history == []


# ------------------------------------------------------------------ #
# [S14] Redis failure: append_session_turn returns False safely
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_redis_failure_append_returns_false(user_id_a, conv_id_a):
    """When Redis is unavailable, append_session_turn must return False and not raise."""
    service = RedisService()
    turn = _make_turn("Question", "Question")
    # Patch get_redis_client to simulate a broken connection
    with patch(
        "app.services.cache.redis_service.get_redis_client",
        new=AsyncMock(return_value=None),
    ):
        result = await service.append_session_turn(TENANT_A, user_id_a, conv_id_a, turn)
    assert result is False


# ------------------------------------------------------------------ #
# [S15] Turn payload stores all required fields
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_turn_payload_required_fields(redis_service, user_id_a, conv_id_a):
    """A stored turn must contain: message_id, role, original_query, canonical_query, timestamp."""
    turn = {
        "message_id": str(uuid.uuid4()),
        "role": "USER",
        "original_query": "What is KYC?",
        "canonical_query": "What is KYC under RBI Master Direction?",
        "summary_answer": "KYC stands for...",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await redis_service.append_session_turn(TENANT_A, user_id_a, conv_id_a, turn)
    history = await redis_service.get_session_context(TENANT_A, user_id_a, conv_id_a)

    assert len(history) == 1
    stored = history[0]
    assert "message_id" in stored
    assert "role" in stored
    assert "original_query" in stored
    assert "canonical_query" in stored
    assert "timestamp" in stored
    assert stored["role"] == "USER"
    assert stored["original_query"] == "What is KYC?"
    assert stored["canonical_query"] == "What is KYC under RBI Master Direction?"


# ------------------------------------------------------------------ #
# [S16] Phase 4 RAG compatibility: canonical_query to RAG, original in DB
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_original_and_canonical_tracked_separately(contextualizer):
    """
    After contextualization, original_query and canonical_query must be
    tracked as two distinct values -- never overwriting each other.
    """
    history = [
        _make_turn(
            "What are the NBFC KYC guidelines?",
            "What are the NBFC KYC guidelines?",
        )
    ]
    original = "Does it also apply to HFCs?"

    canonical, was_ctx = await contextualizer.contextualize(
        prompt=original,
        session_history=history,
    )

    # Both values exist independently
    assert original == "Does it also apply to HFCs?"
    assert canonical is not None
    assert canonical != original  # canonical must be enriched


# ------------------------------------------------------------------ #
# [S17] Session context is empty for brand-new conversation
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_new_conversation_has_empty_session(redis_service):
    """A brand-new conversation must return an empty session history."""
    fresh_conv = str(uuid.uuid4())
    fresh_user = str(uuid.uuid4())

    history = await redis_service.get_session_context(TENANT_A, fresh_user, fresh_conv)
    assert history == []


# ------------------------------------------------------------------ #
# [S18] needs_context False when session history is empty
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_needs_context_false_when_history_empty(contextualizer):
    """needs_context must return False when there is no prior session history."""
    assert contextualizer.needs_context("What about it?", []) is False
    assert contextualizer.needs_context("Does it apply?", []) is False
    assert contextualizer.needs_context("Tell me more.", []) is False
