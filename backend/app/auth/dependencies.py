"""
FastAPI authentication and authorization dependencies.

Provides reusable dependencies for:
  - Extracting and validating JWT from Authorization header
  - Loading the authenticated user from the database
  - Role-based authorization guards

Usage in route handlers::

    @router.get("/me")
    async def me(current_user: User = Depends(get_current_user)):
        ...

    @router.get("/admin-only")
    async def admin(user: User = Depends(require_role(UserRole.ADMIN))):
        ...
"""

import uuid
import logging
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# HTTPBearer extracts the Bearer token from the Authorization header.
# auto_error=False lets us return a custom 401 instead of FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: authenticate and return the current user.

    Flow:
      1. Read Bearer token from Authorization header
      2. Validate JWT signature and expiry
      3. Extract user ID from `sub` claim
      4. Load user from PostgreSQL
      5. Verify account is active

    Returns:
        The authenticated and active User ORM instance.

    Raises:
        HTTPException 401: Missing token, invalid token, expired token,
                           user not found, or inactive account.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    # ---------------------------------------------------------------- #
    # Validate JWT
    # ---------------------------------------------------------------- #
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise credentials_exception

    # ---------------------------------------------------------------- #
    # Parse user ID
    # ---------------------------------------------------------------- #
    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError:
        raise credentials_exception

    # ---------------------------------------------------------------- #
    # Load user from database
    # ---------------------------------------------------------------- #
    from app.services.user_service import get_user_by_id  # avoid circular import

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    # ---------------------------------------------------------------- #
    # Verify account is active
    # ---------------------------------------------------------------- #
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled.",
        )

    return user


def require_role(*roles: UserRole) -> Callable:
    """
    Return a FastAPI dependency that enforces role-based access control.

    Usage::

        @router.get("/admin")
        async def admin_only(user: User = Depends(require_role(UserRole.ADMIN))):
            ...

    Args:
        *roles: One or more UserRole values that are permitted.

    Returns:
        A dependency function that raises 403 if the user's role is not
        in the allowed set.
    """
    async def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions. "
                    f"Required: {[r.value for r in roles]}, "
                    f"got: {current_user.role.value}."
                ),
            )
        return current_user

    return _check_role
