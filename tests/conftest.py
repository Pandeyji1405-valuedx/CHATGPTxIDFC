import pytest
import os
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import app
from backend.database import Base, get_db
from backend.ingestion.seed_rbi_kb import seed_database_and_vector_store
from backend.config import settings

# Test database
TEST_DB_URL = "sqlite:///./data/test_banking_rag.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    # Setup test DB
    Base.metadata.create_all(bind=test_engine)
    seed_database_and_vector_store(custom_engine=test_engine)
    yield
    # Teardown
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./data/test_banking_rag.db"):
        try:
            os.remove("./data/test_banking_rag.db")
        except Exception:
            pass

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_headers_user1(client):
    res = client.post("/api/auth/register", json={
        "name": "User Alpha",
        "email": f"user_alpha_{os.urandom(4).hex()}@idfcbank.com",
        "password": "Password@123"
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def auth_headers_user2(client):
    res = client.post("/api/auth/register", json={
        "name": "User Beta",
        "email": f"user_beta_{os.urandom(4).hex()}@idfcbank.com",
        "password": "Password@456"
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def auth_headers_admin(client):
    res = client.post("/api/auth/login", json={
        "email": "admin@idfcbank.com",
        "password": "Admin@12345"
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
