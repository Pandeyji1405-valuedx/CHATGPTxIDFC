"""
SQLAlchemy async engine and session factory.

Provides:
- Async engine configured from DATABASE_URL
- AsyncSession factory for dependency injection
- FastAPI dependency `get_db` for route handlers
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# ------------------------------------------------------------------ #
# Async Engine
# ------------------------------------------------------------------ #
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # Log SQL in debug/development mode
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,           # Validate connections before use
)

# ------------------------------------------------------------------ #
# Session Factory
# ------------------------------------------------------------------ #
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,       # Prevent lazy-load errors after commit
    autocommit=False,
    autoflush=False,
)


# ------------------------------------------------------------------ #
# FastAPI Dependency
# ------------------------------------------------------------------ #
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.

    Guarantees the session is closed after the request completes,
    even if an exception is raised.

    Usage in a route::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
