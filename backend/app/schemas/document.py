"""
Pydantic schemas for Document and DocumentVersion entities (Phase 3).
"""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentStatus, IngestionStatus


# ------------------------------------------------------------------ #
# Document Version Schemas
# ------------------------------------------------------------------ #
class DocumentVersionResponse(BaseModel):
    """API response model for a single DocumentVersion."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    published_date: Optional[date] = None
    effective_date: Optional[date] = None
    status: DocumentStatus
    file_name: str
    file_hash: str
    file_size_bytes: int
    page_count: int
    chunk_count: int
    ingestion_status: IngestionStatus
    error_message: Optional[str] = None
    superseded_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ #
# Document Schemas
# ------------------------------------------------------------------ #
class DocumentResponse(BaseModel):
    """API response model for a Document with its version history."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_key: str
    title: str
    document_type: str
    circular_number: Optional[str] = None
    topic: Optional[str] = None
    source_name: str
    source_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    versions: list[DocumentVersionResponse] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


# ------------------------------------------------------------------ #
# Ingestion Request & Response Schemas
# ------------------------------------------------------------------ #
class DocumentUploadMetadata(BaseModel):
    """Optional metadata fields provided during multipart PDF upload."""

    title: Optional[str] = None
    document_key: Optional[str] = None
    document_type: str = "circular"
    circular_number: Optional[str] = None
    topic: Optional[str] = None
    source_name: str = "Reserve Bank of India"
    source_url: Optional[str] = None
    version_number: Optional[int] = None
    published_date: Optional[date] = None
    effective_date: Optional[date] = None
    supersedes_version_id: Optional[uuid.UUID] = None


class DocumentUploadResponse(BaseModel):
    """Response returned upon successful document ingestion."""

    document: DocumentResponse
    version: DocumentVersionResponse
    message: str
    chunks_indexed: int
    is_duplicate: bool = False
