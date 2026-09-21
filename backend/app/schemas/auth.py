"""
Authentication request and response schemas.

Pydantic models for:
  - RegisterRequest: user registration payload
  - LoginRequest: login credentials
  - TokenResponse: JWT access token response
"""

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserResponse


# ------------------------------------------------------------------ #
# Password validation constants
# ------------------------------------------------------------------ #
_MIN_PASSWORD_LENGTH = 8
_MAX_PASSWORD_LENGTH = 128

# Regex: at least one uppercase, one lowercase, one digit.
# Does NOT impose exotic character requirements — just sensible hygiene.
_PASSWORD_PATTERN = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$"
)


# ------------------------------------------------------------------ #
# Registration
# ------------------------------------------------------------------ #
class RegisterRequest(BaseModel):
    """Payload for POST /api/v1/auth/register."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's full name.",
        examples=["Test User"],
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address. Stored normalized to lowercase.",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=_MIN_PASSWORD_LENGTH,
        max_length=_MAX_PASSWORD_LENGTH,
        description=(
            f"Password ({_MIN_PASSWORD_LENGTH}–{_MAX_PASSWORD_LENGTH} chars). "
            "Must contain at least one uppercase letter, one lowercase letter, "
            "and one digit."
        ),
        examples=["StrongPassword123!"],
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Name must not be blank.")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase for consistent storage and lookup."""
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        """Enforce minimum complexity: uppercase + lowercase + digit."""
        if not _PASSWORD_PATTERN.match(v):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one digit."
            )
        return v


# ------------------------------------------------------------------ #
# Login
# ------------------------------------------------------------------ #
class LoginRequest(BaseModel):
    """Payload for POST /api/v1/auth/login."""

    email: EmailStr = Field(..., examples=["user@example.com"])
    password: str = Field(..., examples=["StrongPassword123!"])

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


# ------------------------------------------------------------------ #
# Token response
# ------------------------------------------------------------------ #
class TokenResponse(BaseModel):
    """Response body for successful authentication (register or login)."""

    access_token: str = Field(..., description="JWT bearer token.")
    token_type: str = Field(default="bearer", description="Always 'bearer'.")
    user: UserResponse = Field(..., description="Authenticated user profile.")
