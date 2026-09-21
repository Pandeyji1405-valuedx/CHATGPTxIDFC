"""
Pydantic schemas for the Phase 4 Chat / RAG API.

These schemas define the request and response shapes for all
/api/v1/chat/* endpoints.

Key design rules:
  - CitationResponse contains ONLY backend-verified metadata.
    It is constructed by grounding.py from retrieved chunk records,
    never from Gemini model output.
  - ChatMessageRequest.message stores the user raw question exactly.
  - Metrics fields are intentionally opaque dicts for forward-compatibility.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Citation schema (backend-assembled, grounded in retrieved evidence)
# --------------------------------------------------------------------------- #

class CitationResponse(BaseModel):
    """
    A single verified source citation grounded in a retrieved chunk.

    All fields are populated from PostgreSQL/ChromaDB records by the backend.
    Gemini never contributes to this object directly.
    """

    document_id: uuid.UUID
    version_id: uuid.UUID
    document_title: str
    circular_number: Optional[str] = None
    version_number: int
    page_number: int
    section: Optional[str] = None
    chunk_id: str

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- #
# Request schemas
# --------------------------------------------------------------------------- #

class ChatMessageRequest(BaseModel):
    """
    Request body for POST /api/v1/chat/message.

    conversation_id: If None, a new conversation is created automatically.
    message:         User's regulatory question (stored verbatim).
    """

    conversation_id: Optional[uuid.UUID] = None
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User regulatory question. Stored verbatim, not modified.",
    )


# --------------------------------------------------------------------------- #
# Response schemas
# --------------------------------------------------------------------------- #

class ChatMessageResponse(BaseModel):
    """
    Response for a single RAG answer turn.

    answer:         Gemini-generated answer grounded in RBI evidence, or the
                    controlled 'insufficient evidence' message.
    retrieval_type: 'rag' | 'insufficient_evidence'
    citations:      Backend-verified source references. Empty for
                    insufficient_evidence responses.
    """

    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    retrieval_type: str
    citations: List[CitationResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSummaryResponse(BaseModel):
    """Summary row used in conversation list endpoints."""

    id: uuid.UUID
    title: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Full message detail including role, content, and citations."""

    id: uuid.UUID
    role: str
    content: str
    retrieval_type: Optional[str] = None
    citations: Optional[List[CitationResponse]] = None
    metrics: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(BaseModel):
    """Full conversation with all messages."""

    id: uuid.UUID
    title: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    model_config = {"from_attributes": True}
