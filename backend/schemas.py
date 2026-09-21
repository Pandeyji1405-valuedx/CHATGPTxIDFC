from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Auth Schemas ---
class UserRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6)
    department: Optional[str] = "Retail Banking"

    @field_validator("name", "email")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field cannot be empty or whitespace only")
        return s

class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def strip_email(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Email cannot be empty")
        return s

class GoogleAuthRequest(BaseModel):
    credential: str # Google ID token or token string
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None

class SwitchAccountRequest(BaseModel):
    user_id: Optional[str] = None
    email: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    tenant_id: str = "default_tenant"
    email: str
    name: str
    auth_provider: str
    avatar_url: Optional[str] = None
    role: str
    department: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# --- Citation & Ambiguity Schemas ---
class CitationItem(BaseModel):
    source: str = "RBI" # RBI, SEBI, IRDAI, BANK_POLICY, INTERNAL, CONVERSATION_DATABASE
    document_id: Optional[str] = None
    document_title: str
    notification_number: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    regulator: Optional[str] = "RBI"
    status: Optional[str] = "active" # active, superseded
    page_number: Optional[int] = 1
    section: Optional[str] = None
    snippet: str
    source_offsets: Optional[Dict[str, Any]] = None
    bounding_box: Optional[Dict[str, Any]] = None
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
    regulator_scope: Optional[str] = "ALL"
    as_of_date_scope: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message_preview: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ConversationDetail(BaseModel):
    id: str
    title: str
    regulator_scope: Optional[str] = "ALL"
    as_of_date_scope: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ConversationCreate(BaseModel):
    title: Optional[str] = "New Conversation"
    regulator_scope: Optional[str] = "ALL"
    as_of_date_scope: Optional[str] = None

class ConversationRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Title cannot be empty or whitespace only")
        return s

class ChatQueryRequest(BaseModel):
    conversation_id: Optional[str] = None
    query: str = Field(..., min_length=1)
    regulator_filter: Optional[List[str]] = None # ["ALL"] or ["RBI", "SEBI", "IRDAI", "INTERNAL"]
    as_of_date: Optional[str] = None # ISO format "YYYY-MM-DD" or None for current active rules
    department_filter: Optional[str] = None
    requested_depth: Optional[str] = "concise" # concise, detailed, comparison

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Query cannot be empty or whitespace only")
        return s

class ChatQueryResponse(BaseModel):
    conversation_id: str
    conversation_title: str
    user_message_id: str
    assistant_message_id: str
    query_trace_id: Optional[str] = None
    original_query: str
    normalized_query: str
    resolved_entities: List[str] = []
    regulator_scope: str = "ALL"
    as_of_date_applied: Optional[str] = None
    answer: str
    source_type: str # DATABASE, KNOWLEDGE_BASE, DATABASE_AND_KNOWLEDGE_BASE, NO_SUPPORTED_SOURCE
    confidence: float
    citations: List[CitationItem] = []
    ambiguity_flags: List[AmbiguityFlag] = []
    clarification_needed: bool = False
    tokens_used: Optional[Dict[str, int]] = None

# --- Admin Knowledge Base & MIS Schemas ---
class KnowledgeDocumentResponse(BaseModel):
    id: str
    tenant_id: str = "default_tenant"
    title: str
    notification_number: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    effective_from: Optional[str] = None
    effective_until: Optional[str] = None
    regulator: str = "RBI"
    source: str = "RBI"
    source_url: Optional[str] = None
    document_type: str
    department: Optional[str] = None
    status: str = "active" # draft, active, superseded, withdrawn, archived
    superseded_by_id: Optional[str] = None
    version: str = "1.0"
    processing_status: str
    failure_reason: Optional[str] = None
    page_count: int = 1
    is_ocr: bool = False
    ocr_confidence: Optional[float] = None
    ocr_ambiguity_notes: Optional[str] = None
    chunk_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DocumentDetailResponse(BaseModel):
    document: KnowledgeDocumentResponse
    chunks_preview: List[Dict[str, Any]] = []

class SupersedeDocumentRequest(BaseModel):
    document_id: Optional[str] = None
    superseded_by_id: Optional[str] = None
    superseded_by_notification: Optional[str] = None
    effective_until: Optional[str] = None
    effective_until_date: Optional[str] = None
    reason: Optional[str] = None

class IngestionSummaryResponse(BaseModel):
    total_documents: int
    active_documents: int
    superseded_documents: int
    draft_documents: int
    failed_documents: int
    total_chunks: int
    by_regulator: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    documents_by_regulator: Dict[str, int] = {}
    documents_by_status: Dict[str, int] = {}
    ocr_statistics: Dict[str, Any] = {}
    recent_ingestions: List[KnowledgeDocumentResponse] = []

class ConsumptionMISResponse(BaseModel):
    total_queries: int
    avoided_calls_cache: int
    cache_hit_rate_pct: float
    total_tokens_input: int
    total_tokens_output: int
    p50_latency_ms: float
    p95_latency_ms: float
    queries_by_regulator: Dict[str, int] = {}
    feedback_by_category: Dict[str, int] = {}

# --- Feedback Schemas (PRD 8-Category Taxonomy) ---
class FeedbackSubmissionRequest(BaseModel):
    message_id: Optional[str] = None
    query_trace_id: Optional[str] = None
    rating: Any = "POSITIVE"
    category: Optional[str] = None # INCORRECT_FACT, INCOMPLETE, WRONG_SOURCE, SUPERSEDED_OUTDATED, TOO_LONG, TOO_SHORT, WRONG_REGULATOR, UNCLEAR
    comment: Optional[str] = None
    suggested_correction: Optional[str] = None

class FeedbackSubmissionResponse(BaseModel):
    status: str
    feedback_id: str
    message: str
    category: Optional[str] = None

class ChatFeedbackRequest(BaseModel): # Backward compatibility
    message_id: str
    rating: int = Field(..., ge=1, le=5)
    feedback_text: Optional[str] = None
    category: Optional[str] = "ACCURACY"

class ChatFeedbackResponse(BaseModel):
    status: str
    message: str
    message_id: str
