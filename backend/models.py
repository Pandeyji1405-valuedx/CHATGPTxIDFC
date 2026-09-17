import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)
    auth_provider = Column(String(50), default="local") # local, google
    avatar_url = Column(Text, nullable=True)
    role = Column(String(50), default="user") # user, admin
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), default="New Conversation", nullable=False)
    created_at = Column(DateTime, default=get_utc_now)
    updated_at = Column(DateTime, default=get_utc_now, onupdate=get_utc_now)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False) # user, assistant, system
    original_content = Column(Text, nullable=False)
    normalized_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

    conversation = relationship("Conversation", back_populates="messages")
    user = relationship("User", back_populates="messages")
    response = relationship("Response", back_populates="message", uselist=False, cascade="all, delete-orphan")
    entities = relationship("Entity", back_populates="message", cascade="all, delete-orphan")

class Response(Base):
    __tablename__ = "responses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, unique=True)
    answer = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False) # DATABASE, KNOWLEDGE_BASE, DATABASE_AND_KNOWLEDGE_BASE, NO_SUPPORTED_SOURCE
    confidence = Column(Float, default=1.0)
    citations_json = Column(Text, nullable=True) # JSON array of citations
    ambiguity_flags_json = Column(Text, nullable=True) # JSON array of OCR ambiguity warnings
    validation_status = Column(String(50), default="VALIDATED") # VALIDATED, REJECTED, FALLBACK
    created_at = Column(DateTime, default=get_utc_now)

    message = relationship("Message", back_populates="response")

class Entity(Base):
    __tablename__ = "entities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False) # REGULATION, BANKING_SERVICE, LIMIT, ORGANIZATION, PERSON, PRONOUN
    entity_value = Column(String(255), nullable=False)
    canonical_value = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=get_utc_now)

    message = relationship("Message", back_populates="entities")

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(500), nullable=False)
    notification_number = Column(String(255), nullable=True, index=True)
    publication_date = Column(String(50), nullable=True)
    effective_date = Column(String(50), nullable=True)
    source = Column(String(100), default="RBI", nullable=False) # RBI, BANK_POLICY, INTERNAL_POLICY
    source_url = Column(Text, nullable=True)
    document_type = Column(String(50), nullable=False) # pdf, scanned_pdf, docx, txt, csv, image
    file_path = Column(Text, nullable=True)
    version = Column(String(50), default="1.0")
    checksum = Column(String(64), nullable=False)
    processing_status = Column(String(50), default="indexed") # pending, processing, indexed, failed
    page_count = Column(Integer, default=1)
    is_ocr = Column(Boolean, default=False)
    ocr_confidence = Column(Float, nullable=True)
    ocr_ambiguity_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

    chunks = relationship("KnowledgeChunk", back_populates="document", cascade="all, delete-orphan")

class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, default=1)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    section = Column(String(255), nullable=True)
    embedding_json = Column(Text, nullable=True) # Serialized JSON vector
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

    document = relationship("KnowledgeDocument", back_populates="chunks")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False) # LOGIN, LOGOUT, QUERY, UPLOAD_KB, DELETE_KB, REINDEX
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_utc_now)

    user = relationship("User", back_populates="audit_logs")
