"""
Models package.

Import all ORM model classes here so that Alembic's env.py can
discover them via `Base.metadata` for auto-generated migrations.

Phase 1: No application tables.
Phase 2: User model for authentication.
Phase 3: Document, DocumentVersion models.
Phase 4: DocumentChunk, Conversation, Message models.
"""

# Re-export Base for convenience
from app.db.base import Base  # noqa: F401

# Phase 2: User model — imported so Alembic detects the `users` table
from app.models.user import User, UserRole  # noqa: F401

# Phase 3: Document & DocumentVersion models — imported for Alembic detection
from app.models.document import (  # noqa: F401
    Document,
    DocumentStatus,
    DocumentVersion,
    IngestionStatus,
)

# Phase 4: RAG chunk store and chat history models
from app.models.chunk import DocumentChunk  # noqa: F401
from app.models.chat import Conversation, Message, MessageRole  # noqa: F401

# Phase 7: Audit log and user feedback models
from app.models.audit import AuditLog  # noqa: F401
from app.models.feedback import MessageFeedback  # noqa: F401
