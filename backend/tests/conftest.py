"""
Pytest shared fixtures and configuration.

Phase 2 additions:
  - In-memory SQLite database (aiosqlite) for auth tests
  - get_db dependency override so tests never need a real PostgreSQL server
  - Authenticated client fixture for protected-route tests
  - Helper to create a registered test user

Phase 1 fixtures preserved:
  - client fixture (health endpoint tests)
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import create_application

# ------------------------------------------------------------------ #
# In-memory SQLite async URL (no real PostgreSQL needed for unit tests)
# ------------------------------------------------------------------ #
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ------------------------------------------------------------------ #
# Session-scoped async engine + schema creation
# ------------------------------------------------------------------ #
@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create an in-memory SQLite async engine with StaticPool for cross-session test isolation."""
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    """Return a session factory bound to the test engine."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    """Provide a function-scoped DB session for direct database tests."""
    async with test_session_factory() as session:
        yield session
        await session.rollback()



# ------------------------------------------------------------------ #
# FastAPI app with get_db overridden to use in-memory SQLite
# ------------------------------------------------------------------ #
@pytest_asyncio.fixture(scope="session")
async def app(test_session_factory):
    """
    Application instance with get_db overridden to use the test DB.
    """
    # Import all models so Base.metadata is fully populated
    import app.models  # noqa: F401

    test_app = create_application()

    async def _override_get_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    from app.api.v1.documents import get_ingestion_service
    from app.services.documents.ingestion_service import DocumentIngestionService
    from app.services.embeddings.mock_service import MockEmbeddingService
    from app.services.vector_db.chroma_service import ChromaDBService
    import tempfile

    test_temp_storage = tempfile.mkdtemp(prefix="test_storage_")

    test_ingestion_service = DocumentIngestionService(
        embedding_service=MockEmbeddingService(dimension=768),
        chroma_service=ChromaDBService(in_memory=True, collection_name="test_api_col"),
        storage_dir=test_temp_storage,
        session_factory=test_session_factory,
    )

    test_app.dependency_overrides[get_db] = _override_get_db
    test_app.dependency_overrides[get_ingestion_service] = lambda: test_ingestion_service
    return test_app


# ------------------------------------------------------------------ #
# Unauthenticated client (Phase 1 health tests + unprotected auth tests)
# ------------------------------------------------------------------ #
@pytest_asyncio.fixture(scope="session")
async def client(app):
    """
    Session-scoped async HTTP client. No authentication headers.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ------------------------------------------------------------------ #
# Registered user helpers
# ------------------------------------------------------------------ #
TEST_USER = {
    "name": "Test User",
    "email": "testuser@example.com",
    "password": "TestPass123!",
}

TEST_ADMIN = {
    "name": "Admin User",
    "email": "admin@example.com",
    "password": "AdminPass123!",
}


@pytest_asyncio.fixture(scope="session")
async def registered_user_token(client: AsyncClient) -> str:
    """
    Register a dedicated fixture user and return the JWT access token.

    Uses a separate email from TEST_USER to avoid clashing with
    test_register_duplicate_email (which registers TEST_USER twice).
    """
    fixture_user = {
        "name": "Fixture User",
        "email": "fixture.user@example.com",
        "password": "FixturePass123!",
    }
    response = await client.post("/api/v1/auth/register", json=fixture_user)
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


@pytest_asyncio.fixture(scope="session")
async def auth_client(app, registered_user_token: str) -> AsyncClient:
    """
    Authenticated async HTTP client.
    Sends Authorization: Bearer <token> on every request.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {registered_user_token}"},
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def admin_user_token(test_session_factory) -> str:
    """Create an ADMIN role user directly in the database and issue a JWT token."""
    from app.auth.jwt import create_access_token
    from app.auth.password import hash_password
    from app.models.user import User, UserRole

    async with test_session_factory() as session:
        admin = User(
            name="System Administrator",
            email="admin.system@example.com",
            password_hash=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

    return create_access_token(user_id=admin.id, role=UserRole.ADMIN.value)


@pytest_asyncio.fixture(scope="session")
async def admin_client(app, admin_user_token: str) -> AsyncClient:
    """Authenticated async HTTP client with ADMIN credentials."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {admin_user_token}"},
    ) as ac:
        yield ac


def create_sample_pdf_bytes(pages_text: list[str]) -> bytes:
    """Create an in-memory PDF with specified text per page using PyMuPDF."""
    import fitz

    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text.strip():
            page.insert_text((50, 72), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
