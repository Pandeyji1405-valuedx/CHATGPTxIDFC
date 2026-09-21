"""
Pydantic schemas for Message Feedback (Phase 7).
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """Payload to create or update user feedback on a message."""

    rating: str = Field(
        ...,
        description="Rating value: POSITIVE or NEGATIVE.",
        examples=["POSITIVE", "NEGATIVE"],
    )
    reason_category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional categorization for feedback (e.g. INACCURATE, OUTDATED, UNHELPFUL).",
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional free-form user comment.",
    )


class FeedbackResponse(BaseModel):
    """Response payload returning saved feedback."""

    id: uuid.UUID
    message_id: uuid.UUID
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: str
    rating: str
    reason_category: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
