"""
Authentication API router — Phase 2.

Endpoints:
  POST /api/v1/auth/register  — Create new account
  POST /api/v1/auth/login     — Authenticate and receive JWT
  GET  /api/v1/auth/me        — Current user profile (JWT required)
  GET  /api/v1/auth/protected — Smoke test for USER-role access (JWT required)

All business logic lives in app/services/auth_service.py.
Route handlers are intentionally thin.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import login_user, register_user

from app.services.security.rate_limit_service import RateLimiter

router = APIRouter(prefix="/auth", tags=["Authentication"])

auth_rate_limiter = RateLimiter(endpoint_group="auth")


# ------------------------------------------------------------------ #
# Register
# ------------------------------------------------------------------ #
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limiter)],
    summary="Register a new user account",
    description=(
        "Creates a new user record. Password is hashed with Argon2id before storage. "
        "Returns a JWT access token on success — no separate login step needed."
    ),
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user and issue an access token."""
    return await register_user(db, request)


# ------------------------------------------------------------------ #
# Login
# ------------------------------------------------------------------ #
@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limiter)],
    summary="Authenticate and receive JWT",
    description=(
        "Validates email and password. Returns a JWT access token on success. "
        "Invalid credentials always return the same generic error message "
        "to prevent user enumeration."
    ),
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate user and return access token."""
    return await login_user(db, request.email, request.password)


# ------------------------------------------------------------------ #
# Current User
# ------------------------------------------------------------------ #
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Returns the authenticated user's profile. Requires a valid Bearer token.",
)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the authenticated user's safe profile."""
    return UserResponse.model_validate(current_user)


# ------------------------------------------------------------------ #
# Protected endpoint smoke test (USER role)
# ------------------------------------------------------------------ #
@router.get(
    "/protected",
    summary="Protected endpoint smoke test",
    description=(
        "Demonstrates that JWT authentication and role enforcement work correctly. "
        "Requires a valid Bearer token with at least USER role. "
        "ADMIN role also has access."
    ),
)
async def protected(
    current_user: User = Depends(require_role(UserRole.USER, UserRole.ADMIN)),
) -> dict:
    """Smoke test for authenticated USER (or ADMIN) access."""
    return {
        "message": "Access granted.",
        "user_id": str(current_user.id),
        "role": current_user.role.value,
    }
