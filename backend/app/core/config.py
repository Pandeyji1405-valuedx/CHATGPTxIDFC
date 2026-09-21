"""
Application configuration management.

Uses Pydantic BaseSettings to load configuration from environment variables
and an optional .env file. All settings are type-validated at startup.
"""

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central application settings loaded from environment variables.

    Every attribute maps directly to an environment variable (case-insensitive).
    Provides defaults suitable for local development.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars gracefully
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    APP_NAME: str = "IDFC RBI Compliance Chatbot"
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # ------------------------------------------------------------------ #
    # Server
    # ------------------------------------------------------------------ #
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ------------------------------------------------------------------ #
    # PostgreSQL / SQLAlchemy
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:password@localhost:5432/idfc_chatbot_db"
    )
    DATABASE_SYNC_URL: str = (
        "postgresql+psycopg2://postgres:password@localhost:5432/idfc_chatbot_db"
    )

    # SQLAlchemy connection pool settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # ------------------------------------------------------------------ #
    # Security / JWT  (implemented Phase 2)
    # ------------------------------------------------------------------ #
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_MINIMUM_32_CHARS"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ------------------------------------------------------------------ #
    # Document Storage & Ingestion (Phase 3)
    # ------------------------------------------------------------------ #
    STORAGE_DIR: str = "storage/documents"
    CHROMADB_DIR: str = "storage/chromadb"
    CHROMA_COLLECTION_NAME: str = "rbi_documents"
    EMBEDDING_MODEL_NAME: str = "nomic-ai/nomic-embed-text-v1.5"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_BATCH_SIZE: int = 32
    MAX_UPLOAD_SIZE_BYTES: int = 52428800  # 50 MB
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    # ------------------------------------------------------------------ #
    # RAG Pipeline — Phase 4
    # ------------------------------------------------------------------ #
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_THINKING_LEVEL: str = "low"  # "none" | "low" | "medium" | "high"

    # Retrieval tuning
    RAG_VECTOR_TOP_K: int = 20       # Dense (ChromaDB) candidates
    RAG_SPARSE_TOP_K: int = 20       # Sparse (PostgreSQL FTS) candidates
    RAG_RERANK_TOP_K: int = 5        # Final top-K after BGE reranking
    RAG_MIN_EVIDENCE_SCORE: float = 0.0  # BGE score gate (env-configured)

    # Reranker
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_ENABLED: bool = True

    # ------------------------------------------------------------------ #
    # Memory & Cost-Saving Cache — Phase 5
    # ------------------------------------------------------------------ #
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    CACHE_ENABLED: bool = True
    EXACT_CACHE_TTL_SECONDS: int = 86400           # 24 Hours
    SEMANTIC_CACHE_SIMILARITY_THRESHOLD: float = 0.92
    SESSION_MEMORY_TTL_SECONDS: int = 3600         # 1 Hour sliding TTL
    SESSION_MEMORY_MAX_TURNS: int = 10             # Max turns retained per session key
    LLM_GATEWAY_PROVIDER: str = "gemini"           # "gemini" | "mock"

    # ------------------------------------------------------------------ #
    # Security, Rate Limiting & Audit — Phase 7
    # ------------------------------------------------------------------ #
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_CHAT_PER_MINUTE: int = 30
    RATE_LIMIT_DOC_PER_MINUTE: int = 10
    RATE_LIMIT_FEEDBACK_PER_MINUTE: int = 30
    RATE_LIMIT_FAIL_OPEN: bool = True
    AUDIT_LOG_ENABLED: bool = True
    PII_REDACTION_ENABLED: bool = True


    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    FRONTEND_URL: str = "http://localhost:5173"

    @field_validator("FRONTEND_URL", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str) -> str:
        """Accept comma-separated URLs and return a cleaned string."""
        return v.strip()

    @property
    def cors_origins(self) -> List[str]:
        """Return CORS allowed origins as a list."""
        return [origin.strip() for origin in self.FRONTEND_URL.split(",")]

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        """True when APP_ENV is 'production'."""
        return self.APP_ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        """True when APP_ENV is 'development'."""
        return self.APP_ENV.lower() == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached singleton Settings instance.

    Using lru_cache ensures that environment variables are read once
    at application startup rather than on every request.
    """
    return Settings()
