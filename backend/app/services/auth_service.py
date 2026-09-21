"""
Authentication business logic service.

Handles:
  - User registration (validate → hash → persist)
  - User authentication (lookup → verify → token)

Security rules enforced here:
  - Plaintext password is hashed before persistence
  - Identical generic error for wrong email and wrong password
    (prevents user-enumeration via timing or messages)
  - Never returns or logs password_hash
"""

import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest, TokenResponse
from app.schemas.user import UserResponse
from app.services.user_service import get_user_by_email

logger = logging.getLogger(__name__)

# Generic message used for BOTH wrong-email and wrong-password failures.
# Using the same message prevents user enumeration.
_INVALID_CREDENTIALS_MSG = "Invalid email or password."


async def register_user(db: AsyncSession, request: RegisterRequest) -> TokenResponse:
    """
    Register a new user account.

    Steps:
      1. Check for duplicate email
      2. Hash the password with Argon2id
      3. Persist the new user record
      4. Issue a JWT access token immediately (no separate login required)

    Args:
        db:      Async database session.
        request: Validated registration payload.

    Returns:
        TokenResponse containing the access token and safe user profile.

    Raises:
        HTTPException 409: If the email is already registered.
    """
    # Duplicate email check
    existing = await get_user_by_email(db, request.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create user — password is hashed here, never stored as plaintext
    user = User(
        name=request.name,
        email=request.email,
        password_hash=hash_password(request.password),
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    await db.flush()    # Assign id without committing
    await db.refresh(user)

    logger.info("New user registered: id=%s role=%s", user.id, user.role)

    token = create_access_token(user_id=user.id, role=user.role.value)

    # Log audit event for registration
    from app.services.security.audit_service import AuditService
    await AuditService.log_event(
        db=db,
        action="auth.register.success",
        resource_type="user",
        resource_id=str(user.id),
        outcome="SUCCESS",
        actor_id=user.id,
        details={"name": user.name},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


async def login_user(db: AsyncSession, email: str, password: str) -> TokenResponse:
    """
    Authenticate a user and return a JWT access token.

    Steps:
      1. Look up user by email
      2. Verify password hash (constant-time comparison)
      3. Check account is active
      4. Issue JWT

    Args:
        db:       Async database session.
        email:    Normalized email from LoginRequest.
        password: Plaintext password from LoginRequest.

    Returns:
        TokenResponse on success.

    Raises:
        HTTPException 401: Invalid credentials (generic message).
        HTTPException 403: Account is disabled.
    """
    from app.services.security.audit_service import AuditService

    user = await get_user_by_email(db, email)

    # Use verify_password even when user is None to prevent timing attacks
    # (argon2 verify is the slow part; we don't want a fast path on missing email)
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=4$dummysalt$dummyhash"
    stored_hash = user.password_hash if user else dummy_hash

    password_ok = verify_password(password, stored_hash)

    if user is None or not password_ok:
        await AuditService.log_event(
            db=db,
            action="auth.login.failure",
            resource_type="user",
            resource_id=str(user.id) if user else None,
            outcome="FAILURE",
            actor_id=user.id if user else None,
            details={"reason": "Invalid credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS_MSG,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        await AuditService.log_event(
            db=db,
            action="auth.login.failure",
            resource_type="user",
            resource_id=str(user.id),
            outcome="DENIED",
            actor_id=user.id,
            details={"reason": "Account disabled"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled. Please contact support.",
        )

    await AuditService.log_event(
        db=db,
        action="auth.login.success",
        resource_type="user",
        resource_id=str(user.id),
        outcome="SUCCESS",
        actor_id=user.id,
    )

    token = create_access_token(user_id=user.id, role=user.role.value)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
