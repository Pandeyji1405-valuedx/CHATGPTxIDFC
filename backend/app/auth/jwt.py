"""
JWT token creation and validation.

Design:
- Stateless access tokens only (Phase 2)
- HS256 signing with a configurable secret key
- Claims: sub, role, type, jti, iat, exp

Security rules:
  - Secret key loaded from environment only (never hardcoded)
  - JTI (JWT ID) provides uniqueness per token
  - Token type claim prevents access tokens from being reused
    as other token types in future (e.g. password-reset tokens)
  - Never log the full token string
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.config import get_settings

settings = get_settings()

# ------------------------------------------------------------------ #
# Token type constants
# ------------------------------------------------------------------ #
ACCESS_TOKEN_TYPE = "access"


# ------------------------------------------------------------------ #
# Payload model (typed dict for clarity)
# ------------------------------------------------------------------ #
class TokenPayload:
    """
    Decoded and validated JWT payload container.

    Attributes:
        sub:  Subject — string representation of the user's UUID.
        role: User's role string (USER / ADMIN).
        type: Token type (must equal ACCESS_TOKEN_TYPE).
        jti:  JWT ID — unique identifier for this token.
        exp:  Expiry datetime (UTC).
    """

    __slots__ = ("sub", "role", "type", "jti", "exp")

    def __init__(self, sub: str, role: str, token_type: str, jti: str, exp: datetime):
        self.sub = sub
        self.role = role
        self.type = token_type
        self.jti = jti
        self.exp = exp


# ------------------------------------------------------------------ #
# Token creation
# ------------------------------------------------------------------ #
def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """
    Create a signed JWT access token.

    Args:
        user_id: The user's UUID (stored in `sub` as a string).
        role:    The user's role string.

    Returns:
        A compact JWT string (header.payload.signature).
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "jti": str(uuid.uuid4()),   # Unique per token
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


# ------------------------------------------------------------------ #
# Token validation
# ------------------------------------------------------------------ #
def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT access token.

    Validates:
    - Signature (using the server's secret key)
    - Expiry (exp claim)
    - Token type (must be ACCESS_TOKEN_TYPE)
    - Required claims presence

    Args:
        token: The raw JWT string from the Authorization header.

    Returns:
        A TokenPayload with decoded claims.

    Raises:
        JWTError: On invalid signature, malformed token, or missing claims.
        ExpiredSignatureError: When the token has expired (sub-class of JWTError).
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError:
        raise JWTError("Token has expired.")
    except JWTError:
        raise JWTError("Token is invalid or malformed.")

    # Validate required claims
    sub: str | None = payload.get("sub")
    role: str | None = payload.get("role")
    token_type: str | None = payload.get("type")
    jti: str | None = payload.get("jti")

    if not all([sub, role, token_type, jti]):
        raise JWTError("Token is missing required claims.")

    if token_type != ACCESS_TOKEN_TYPE:
        raise JWTError(f"Invalid token type: expected '{ACCESS_TOKEN_TYPE}'.")

    exp_timestamp = payload.get("exp")
    exp_dt = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc) if exp_timestamp else datetime.now(timezone.utc)

    return TokenPayload(
        sub=sub,          # type: ignore[arg-type]
        role=role,        # type: ignore[arg-type]
        token_type=token_type,  # type: ignore[arg-type]
        jti=jti,          # type: ignore[arg-type]
        exp=exp_dt,
    )
