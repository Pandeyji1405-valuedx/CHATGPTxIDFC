"""
User data-access service.

Thin repository layer for user queries.
All database interactions for user records go here — never in route handlers.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """
    Fetch a user by email address (case-insensitive, pre-normalized).

    Caller is responsible for normalizing email before calling this function.

    Args:
        db:    Async database session.
        email: Lowercase-normalized email string.

    Returns:
        User ORM instance if found, otherwise None.
    """
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """
    Fetch a user by their UUID primary key.

    Args:
        db:      Async database session.
        user_id: UUID of the user.

    Returns:
        User ORM instance if found, otherwise None.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
