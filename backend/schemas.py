from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Auth Schemas ---
class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6)

class UserLoginRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    credential: str # Google ID token or token string
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    auth_provider: str
    avatar_url: Optional[str] = None
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# --- Citation & Ambiguity Schemas ---
class CitationItem(BaseModel):
    source: str # RBI, BANK_POLICY, CONVERSATION_DATABASE
    document_title: str
    notification_number: Optional[str] = None
    publication_date: Optional[str] = None
    page_number: Optional[int] = 1
    section: Optional[str] = None
    snippet: str
    score: float = 1.0

class AmbiguityFlag(BaseModel):
    character_pair: str # e.g. "0 ↔ O", "1 ↔ I ↔ l", "5 ↔ S"
    context_term: str # e.g. "RBI/2023-24/0O1"
    description: str
    verification_required: bool = True

# --- Chat & Conversation Schemas ---
class MessageResponse(BaseModel):
    id: str
    role: str
    original_content: str
    normalized_content: Optional[str] = None
    created_at: datetime
    answer: Optional[str] = None
    source_type: Optional[str] = None # DATABASE, KNOWLEDGE_BASE, DATABASE_AND_KNOWLEDGE_BASE, NO_SUPPORTED_SOURCE
    confidence: Optional[float] = None
    citations: Optional[List[CitationItem]] = None
    ambiguity_flags: Optional[List[AmbiguityFlag]] = None

    model_config = ConfigDict(from_attributes=True)

class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"

class ConversationRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)

class ChatQueryRequest(BaseModel):
    conversation_id: Optional[str] = None
    query: str = Field(..., min_length=1)

class ChatQueryResponse(BaseModel):
    conversation_id: str
    conversation_title: str
    user_message_id: str
    assistant_message_id: str
    original_query: str
    normalized_query: str
    resolved_entities: List[str] = []
    answer: str
    source_type: str # DATABASE, KNOWLEDGE_BASE, DATABASE_AND_KNOWLEDGE_BASE, NO_SUPPORTED_SOURCE
    confidence: float
    citations: List[CitationItem] = []
    ambiguity_flags: List[AmbiguityFlag] = []
    clarification_needed: bool = False

# --- Admin Knowledge Base Schemas ---
class KnowledgeDocumentResponse(BaseModel):
    id: str
    title: str
    notification_number: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    document_type: str
    version: str
    processing_status: str
    page_count: int
    is_ocr: bool
    ocr_confidence: Optional[float] = None
    ocr_ambiguity_notes: Optional[str] = None
    chunk_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(BaseModel):
    document: KnowledgeDocumentResponse
    chunks_preview: List[Dict[str, Any]] = []
