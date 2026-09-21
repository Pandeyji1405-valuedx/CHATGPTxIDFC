"""
User ORM model.

Defines the `users` table used for authentication and authorization.
This is the only table introduced in Phase 2.

Future phases will add:
- conversations (Phase 4)
- messages (Phase 4)
- documents (Phase 3)
- feedback, audit_logs (Phase 7)
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, enum.Enum):
    """
    Application role enumeration.

    USER  — Standard authenticated user (default).
    ADMIN — Elevated privileges for future admin operations.

    Using str-based enum means values are stored as plain strings
    and serialize cleanly in JSON/Pydantic without extra conversion.
    """

    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):
    """
    Persistent user record for authentication.

    Security rules enforced at this layer:
    - password_hash stores ONLY the Argon2 digest, never plaintext
    - email is normalized to lowercase before persistence
    - is_active enables soft-disable without deletion
    """

    __tablename__ = "users"

    # ------------------------------------------------------------------ #
    # Primary key
    # ------------------------------------------------------------------ #
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Stored lowercase-normalized; enforce uniqueness at DB level",
    )

    # ------------------------------------------------------------------ #
    # Security  — NEVER expose this field in API responses
    # ------------------------------------------------------------------ #
    password_hash: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Argon2id digest. Never stored or returned as plaintext.",
    )

    # ------------------------------------------------------------------ #
    # Authorization
    # ------------------------------------------------------------------ #
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )

    # ------------------------------------------------------------------ #
    # Account status
    # ------------------------------------------------------------------ #
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Soft-disable account without deletion",
    )

    # ------------------------------------------------------------------ #
    # Timestamps  (timezone-aware UTC)
    # ------------------------------------------------------------------ #
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
