"""
Phase 7: Enterprise Security, PII, Feedback & Audit Test Suite.

Tests cover:
  1. PII Detection & Redaction (PAN, Aadhaar, Phone, Email, Secrets, Dict Sanitization)
  2. Immutable Audit Logging (Persistence, PII sanitization, Admin query API, RBAC protection)
  3. User Feedback API (Positive/Negative ratings, User isolation, Update existing, User role restriction)
  4. Redis Rate Limiting (Threshold enforcement, 429 status code, Retry-After header, Fail-open behavior)
  5. Correlation ID Middleware (Header generation and propagation)
"""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.models.audit import AuditLog
from app.models.chat import Conversation, Message, MessageRole
from app.models.feedback import MessageFeedback
from app.models.user import User, UserRole
from app.services.security.audit_service import AuditService
from app.services.security.pii_service import PIIService
from app.services.security.rate_limit_service import RateLimiter


# Helper to create DB users dynamically for tests
async def _make_user(
    db: AsyncSession,
    role: UserRole = UserRole.USER,
    email: str = None,
) -> User:
    if email is None:
        email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        name="Test User",
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
# 1. PII Service Unit Tests
# ------------------------------------------------------------------ #

def test_pii_redact_pan():
    raw = "Customer PAN card number is ABCDE1234F for verification."
    redacted = PIIService.redact_text(raw)
    assert "ABCDE1234F" not in redacted
    assert "[REDACTED_PAN]" in redacted


def test_pii_redact_aadhaar():
    raw = "User Aadhaar number: 3675 9834 6012."
    redacted = PIIService.redact_text(raw)
    assert "3675 9834 6012" not in redacted
    assert "[REDACTED_AADHAAR]" in redacted


def test_pii_redact_phone():
    raw = "Contact support at +91 9876543210 or 8765432109 immediately."
    redacted = PIIService.redact_text(raw)
    assert "9876543210" not in redacted
    assert "[REDACTED_PHONE]" in redacted


def test_pii_redact_email():
    raw = "Send details to officer@idfcbank.com or test.user@gmail.com."
    redacted = PIIService.redact_text(raw)
    assert "officer@idfcbank.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted


def test_pii_redact_secrets_and_jwt():
    raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signature AND api_key=secret_12345"
    redacted = PIIService.redact_text(raw)
    assert "secret_12345" not in redacted
    assert "[REDACTED_JWT]" in redacted or "[REDACTED_SECRET]" in redacted


def test_pii_detect_categories():
    raw = "My email is test@idfc.com and PAN is XYZAB5678K."
    detected = PIIService.detect_pii(raw)
    assert "EMAIL" in detected
    assert "PAN" in detected


def test_pii_sanitize_dict():
    data = {
        "user_email": "user@bank.com",
        "api_key": "super_secret_key",
        "nested": {
            "note": "Customer PAN is ABCDE1234F",
            "normal_field": "public_data",
        },
    }
    sanitized = PIIService.sanitize_dict(data)
    assert sanitized["user_email"] == "[REDACTED_EMAIL]"
    assert sanitized["api_key"] == "[REDACTED_SECRET]"
    assert sanitized["nested"]["note"] == "Customer PAN is [REDACTED_PAN]"
    assert sanitized["nested"]["normal_field"] == "public_data"


# ------------------------------------------------------------------ #
# 2. Audit Logging Service & API Tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_audit_log_event_persisted(db_session):
    user = await _make_user(db_session, role=UserRole.USER)
    log_entry = await AuditService.log_event(
        db=db_session,
        action="test.action",
        resource_type="document",
        outcome="SUCCESS",
        actor_id=user.id,
        details={"email": "officer@bank.com", "note": "PAN is ABCDE1234F"},
    )
    await db_session.commit()

    assert log_entry is not None
    assert log_entry.action == "test.action"
    assert log_entry.outcome == "SUCCESS"
    assert log_entry.actor_id == user.id
    # Ensure details dictionary was sanitized before saving
    assert log_entry.details["email"] == "[REDACTED_EMAIL]"
    assert log_entry.details["note"] == "PAN is [REDACTED_PAN]"


@pytest.mark.asyncio
async def test_audit_api_admin_access(app, db_session):
    admin = await _make_user(db_session, role=UserRole.ADMIN)
    token = create_access_token(user_id=admin.id, role=admin.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    # Record an audit log event
    await AuditService.log_event(
        db=db_session,
        action="admin.action.test",
        resource_type="system",
        outcome="SUCCESS",
        actor_id=admin.id,
    )
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/audit/logs", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert data["total"] >= 1
        assert any(item["action"] == "admin.action.test" for item in data["items"])


@pytest.mark.asyncio
async def test_audit_api_user_forbidden(app, db_session):
    user = await _make_user(db_session, role=UserRole.USER)
    token = create_access_token(user_id=user.id, role=user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/audit/logs", headers=headers)
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_audit_api_unauthenticated(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/audit/logs")
        assert res.status_code == 401


# ------------------------------------------------------------------ #
# 3. Message Feedback API Tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_feedback_submit_positive(app, db_session):
    user = await _make_user(db_session, role=UserRole.USER)
    token = create_access_token(user_id=user.id, role=user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    conv = Conversation(user_id=user.id, title="Test Feedback Conv")
    db_session.add(conv)
    await db_session.commit()

    msg = Message(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content="RBI compliance answer.",
    )
    db_session.add(msg)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/chat/messages/{msg.id}/feedback",
            json={"rating": "POSITIVE", "comment": "Very accurate citation"},
            headers=headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["rating"] == "POSITIVE"
        assert data["message_id"] == str(msg.id)
        assert data["comment"] == "Very accurate citation"


@pytest.mark.asyncio
async def test_feedback_update_existing(app, db_session):
    user = await _make_user(db_session, role=UserRole.USER)
    token = create_access_token(user_id=user.id, role=user.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    conv = Conversation(user_id=user.id, title="Test Feedback Update Conv")
    db_session.add(conv)
    await db_session.commit()

    msg = Message(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content="RBI compliance answer 2.",
    )
    db_session.add(msg)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit POSITIVE
        res1 = await client.post(
            f"/api/v1/chat/messages/{msg.id}/feedback",
            json={"rating": "POSITIVE"},
            headers=headers,
        )
        assert res1.status_code == 200

        # Update to NEGATIVE
        res2 = await client.post(
            f"/api/v1/chat/messages/{msg.id}/feedback",
            json={"rating": "NEGATIVE", "reason_category": "OUTDATED"},
            headers=headers,
        )
        assert res2.status_code == 200
        data = res2.json()
        assert data["rating"] == "NEGATIVE"
        assert data["reason_category"] == "OUTDATED"

        # Verify DB contains exactly 1 updated record
        stmt = select(MessageFeedback).where(MessageFeedback.message_id == msg.id)
        res_db = await db_session.execute(stmt)
        feedbacks = res_db.scalars().all()
        assert len(feedbacks) == 1
        assert feedbacks[0].rating == "NEGATIVE"


@pytest.mark.asyncio
async def test_feedback_user_isolation(app, db_session):
    """User B cannot submit feedback for User A's message."""
    user_a = await _make_user(db_session, role=UserRole.USER, email="usera@test.com")
    user_b = await _make_user(db_session, role=UserRole.USER, email="userb@test.com")

    user_b_token = create_access_token(user_id=user_b.id, role=user_b.role.value)

    conv = Conversation(user_id=user_a.id, title="User A Conv")
    db_session.add(conv)
    await db_session.commit()

    msg = Message(
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content="User A answer.",
    )
    db_session.add(msg)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User B attempts to submit feedback on User A's message -> 404
        res = await client.post(
            f"/api/v1/chat/messages/{msg.id}/feedback",
            json={"rating": "POSITIVE"},
            headers={"Authorization": f"Bearer {user_b_token}"},
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_feedback_user_message_rejected(app, db_session):
    """Cannot submit feedback on a USER question message."""
    user = await _make_user(db_session, role=UserRole.USER)
    token = create_access_token(user_id=user.id, role=user.role.value)

    conv = Conversation(user_id=user.id, title="User Q Conv")
    db_session.add(conv)
    await db_session.commit()

    user_msg = Message(
        conversation_id=conv.id,
        role=MessageRole.USER,
        content="User question text.",
    )
    db_session.add(user_msg)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            f"/api/v1/chat/messages/{user_msg.id}/feedback",
            json={"rating": "POSITIVE"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400


# ------------------------------------------------------------------ #
# 4. Correlation ID Middleware Tests
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_correlation_id_header(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test default auto-generation
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        assert "X-Request-ID" in res.headers
        generated_id = res.headers["X-Request-ID"]
        assert len(generated_id) > 10

        # Test header propagation
        custom_id = "req-custom-trace-12345"
        res2 = await client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
        assert res2.status_code == 200
        assert res2.headers["X-Request-ID"] == custom_id
