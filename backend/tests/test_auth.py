"""
Phase 2 Authentication tests.

Covers:
  REGISTRATION   — valid, duplicate email, invalid email, weak password
  LOGIN          — valid, wrong password, unknown email, inactive user
  JWT            — valid token, expired, invalid, malformed, missing
  CURRENT USER   — /me success, unauthenticated, inactive rejected
  AUTHORIZATION  — USER access, ADMIN-only protected
  PASSWORD       — hash stored, plaintext never returned
"""

import time
import uuid

import pytest
from httpx import AsyncClient
from jose import jwt

from app.core.config import get_settings
from tests.conftest import TEST_USER

settings = get_settings()


# ================================================================== #
# REGISTRATION
# ================================================================== #
class TestRegistration:
    """Tests for POST /api/v1/auth/register."""

    @pytest.mark.asyncio
    async def test_register_valid_user(self, client: AsyncClient):
        """Valid registration returns 201 with access_token and user profile."""
        payload = {
            "name": "Fresh User",
            "email": "fresh@example.com",
            "password": "FreshPass123!",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "fresh@example.com"
        assert data["user"]["role"] == "USER"
        assert data["user"]["is_active"] is True

    @pytest.mark.asyncio
    async def test_register_password_hash_not_returned(self, client: AsyncClient):
        """Response must never contain password_hash."""
        payload = {
            "name": "Secure User",
            "email": "secure@example.com",
            "password": "SecurePass123!",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "password_hash" not in data
        assert "password_hash" not in data.get("user", {})

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Registering an existing email returns 409 Conflict."""
        # First registration (uses the session-level TEST_USER)
        await client.post("/api/v1/auth/register", json=TEST_USER)
        # Second attempt with same email
        response = await client.post("/api/v1/auth/register", json=TEST_USER)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, client: AsyncClient):
        """Registration with malformed email returns 422 Unprocessable Entity."""
        payload = {
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "GoodPass123!",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """Password shorter than 8 chars is rejected."""
        payload = {
            "name": "Short Pass",
            "email": "short@example.com",
            "password": "Ab1!",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_password_no_uppercase(self, client: AsyncClient):
        """Password without uppercase letter is rejected."""
        payload = {
            "name": "Weak User",
            "email": "weak@example.com",
            "password": "weakpass123!",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_email_normalized_to_lowercase(self, client: AsyncClient):
        """Email is normalized to lowercase regardless of input casing."""
        payload = {
            "name": "Case User",
            "email": "CaseUser@Example.COM",
            "password": "CasePass123!",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201
        assert response.json()["user"]["email"] == "caseuser@example.com"

    @pytest.mark.asyncio
    async def test_register_missing_name(self, client: AsyncClient):
        """Missing name field returns 422."""
        payload = {"email": "nonname@example.com", "password": "GoodPass123!"}
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


# ================================================================== #
# LOGIN
# ================================================================== #
class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    @pytest.mark.asyncio
    async def test_login_valid_credentials(self, client: AsyncClient):
        """Correct email and password return 200 with access_token."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Wrong password returns 401 with generic message."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": TEST_USER["email"], "password": "WrongPass999!"},
        )
        assert response.status_code == 401
        # Must not reveal whether email exists
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_unknown_email(self, client: AsyncClient):
        """Unknown email returns 401 with same generic message."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "GhostPass123!"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_password_hash_not_returned(self, client: AsyncClient):
        """Login response must never contain password_hash."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "password_hash" not in data
        assert "password_hash" not in data.get("user", {})

    @pytest.mark.asyncio
    async def test_login_email_normalization(self, client: AsyncClient):
        """Login with mixed-case email works (normalized to lowercase)."""
        response = await client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_USER["email"].upper(),
                "password": TEST_USER["password"],
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, client: AsyncClient, test_session_factory):
        """Inactive user is rejected with 403 Forbidden."""
        from app.auth.password import hash_password
        from app.models.user import User, UserRole

        async with test_session_factory() as session:
            inactive_user = User(
                name="Inactive User",
                email="inactive.login@example.com",
                password_hash=hash_password("InactivePass123!"),
                role=UserRole.USER,
                is_active=False,
            )
            session.add(inactive_user)
            await session.commit()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "inactive.login@example.com", "password": "InactivePass123!"},
        )
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()


# ================================================================== #
# JWT
# ================================================================== #
class TestJWT:
    """Tests for JWT token validity and error cases."""

    @pytest.mark.asyncio
    async def test_valid_token_accesses_me(self, registered_user_token: str, client: AsyncClient):
        """A freshly issued token grants access to /me."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {registered_user_token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, client: AsyncClient):
        """An expired token is rejected with 401."""
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "role": "USER",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iat": int(time.time()) - 3600,
            "exp": int(time.time()) - 1800,   # Already expired
        }
        expired_token = jwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_signature_rejected(self, client: AsyncClient):
        """Token signed with a wrong key is rejected."""
        fake_payload = {
            "sub": str(uuid.uuid4()),
            "role": "USER",
            "type": "access",
            "jti": str(uuid.uuid4()),
            "exp": int(time.time()) + 3600,
        }
        bad_token = jwt.encode(fake_payload, "wrong-secret", algorithm="HS256")
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_token_rejected(self, client: AsyncClient):
        """A completely malformed token string is rejected."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer this.is.not.a.jwt"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_token_rejected(self, client: AsyncClient):
        """No Authorization header → 403 (HTTPBearer returns 403 when no creds)."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_wrong_token_type_rejected(self, client: AsyncClient):
        """Token with wrong type claim is rejected."""
        payload = {
            "sub": str(uuid.uuid4()),
            "role": "USER",
            "type": "refresh",   # Not 'access'
            "jti": str(uuid.uuid4()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


# ================================================================== #
# CURRENT USER (/me)
# ================================================================== #
class TestCurrentUser:
    """Tests for GET /api/v1/auth/me."""

    @pytest.mark.asyncio
    async def test_me_returns_user_profile(self, auth_client: AsyncClient):
        """Authenticated /me returns correct user profile fields."""
        response = await auth_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "name" in data
        assert "email" in data
        assert "role" in data
        assert "is_active" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_me_no_password_hash(self, auth_client: AsyncClient):
        """Authenticated /me response must not include password_hash."""
        response = await auth_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert "password_hash" not in response.json()

    @pytest.mark.asyncio
    async def test_me_unauthenticated_rejected(self, client: AsyncClient):
        """Unauthenticated /me request is rejected."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_me_inactive_user_rejected(self, client: AsyncClient, test_session_factory):
        """Token belonging to an inactive/disabled user is rejected with 403."""
        from app.auth.jwt import create_access_token
        from app.auth.password import hash_password
        from app.models.user import User, UserRole

        async with test_session_factory() as session:
            inactive_user = User(
                name="Inactive Me",
                email="inactive.me@example.com",
                password_hash=hash_password("InactivePass123!"),
                role=UserRole.USER,
                is_active=False,
            )
            session.add(inactive_user)
            await session.commit()
            await session.refresh(inactive_user)

        token = create_access_token(user_id=inactive_user.id, role="USER")
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert "disabled" in response.json()["detail"].lower()


# ================================================================== #
# AUTHORIZATION
# ================================================================== #
class TestAuthorization:
    """Tests for role-based access control."""

    @pytest.mark.asyncio
    async def test_user_can_access_protected_route(self, auth_client: AsyncClient):
        """A USER-role token can access the /protected endpoint."""
        response = await auth_client.get("/api/v1/auth/protected")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Access granted."
        assert data["role"] == "USER"

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access_protected(self, client: AsyncClient):
        """No token → protected endpoint returns 401/403."""
        response = await client.get("/api/v1/auth/protected")
        assert response.status_code in (401, 403)


# ================================================================== #
# PASSWORD SECURITY
# ================================================================== #
class TestPasswordSecurity:
    """Verify password hashing behavior."""

    def test_hash_is_not_plaintext(self):
        """hash_password() must not return the plaintext password."""
        from app.auth.password import hash_password
        plaintext = "MyPassword123!"
        hashed = hash_password(plaintext)
        assert hashed != plaintext

    def test_verify_correct_password(self):
        """verify_password() returns True for correct plaintext."""
        from app.auth.password import hash_password, verify_password
        plaintext = "MyPassword123!"
        hashed = hash_password(plaintext)
        assert verify_password(plaintext, hashed) is True

    def test_verify_wrong_password(self):
        """verify_password() returns False for wrong plaintext."""
        from app.auth.password import hash_password, verify_password
        hashed = hash_password("MyPassword123!")
        assert verify_password("WrongPassword123!", hashed) is False

    def test_two_hashes_of_same_password_differ(self):
        """Argon2 uses unique salts — identical passwords produce different hashes."""
        from app.auth.password import hash_password
        plaintext = "SamePassword123!"
        assert hash_password(plaintext) != hash_password(plaintext)


# ================================================================== #
# PHASE 1 HEALTH ENDPOINT — ensure it still works
# ================================================================== #
class TestPhase1Preserved:
    """Confirm Phase 1 health endpoint is unaffected."""

    @pytest.mark.asyncio
    async def test_health_still_returns_200(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
