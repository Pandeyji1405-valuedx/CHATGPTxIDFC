import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "CHATGPTxIDFC Banking RAG Assistant"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ALLOWED_ORIGINS: str = "*"

    SECRET_KEY: str = "chatgptxidfc_super_secure_jwt_secret_key_2026_banking_rag_987654321"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    GOOGLE_CLIENT_ID: str = "mock-google-client-id-banking-idfc.apps.googleusercontent.com"
    GOOGLE_CLIENT_SECRET: str = "mock-google-client-secret-banking-idfc"

    DATABASE_URL: str = "postgresql://postgres:Pandeyji%401405@localhost:5432/chatgpt_idfc_rag"

    # Gemini Flash LLM Settings
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    USE_GEMINI_SYNTHESIS: bool = True
    GEMINI_TIMEOUT_SECONDS: int = 15

    # RAG Tuning Parameters
    RETRIEVAL_THRESHOLD: float = 0.20
    TOP_K_CHUNKS: int = 6
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 100
    MAX_HISTORY_MESSAGES: int = 10

    # Policy Enforcements
    STRICT_NO_INTERNET_CHAT: bool = True
    ENABLE_OCR_AMBIGUITY_DETECTION: bool = True
    OCR_CONFIDENCE_THRESHOLD: float = 0.70

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    KB_DIR: str = os.path.join(DATA_DIR, "kb")
    UPLOAD_DIR: str = os.path.join(DATA_DIR, "uploads")

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()

# Ensure data directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.KB_DIR, exist_ok=True)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
