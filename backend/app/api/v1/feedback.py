"""
Message Feedback API Router (Phase 7).

Endpoints:
  POST /api/v1/chat/messages/{message_id}/feedback — Submit or update rating/feedback for an assistant message.
  GET  /api/v1/chat/messages/{message_id}/feedback — Retrieve rating/feedback for a message.

Security & Authorization:
  - Users can only submit feedback for messages belonging to their conversations and tenant.
  - Cross-user/cross-tenant attempts return 404 or 403.
  - Submitting feedback does not alter or delete the historical assistant message.
"""

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.chat import Conversation, Message, MessageRole
from app.models.feedback import MessageFeedback
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.security.audit_service import AuditService
from app.services.security.pii_service import PIIService
from app.services.security.rate_limit_service import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/messages", tags=["Feedback"])

# Specific rate limit for feedback submission
feedback_rate_limiter = RateLimiter(endpoint_group="feedback")


@router.post(
    "/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(feedback_rate_limiter)],
    summary="Submit or update feedback for an assistant response.",
)
async def submit_feedback(
    message_id: uuid.UUID,
    payload: FeedbackCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageFeedback:
    """
    Submit user feedback (rating POSITIVE/NEGATIVE, reason category, comment)
    for an assistant message.

    Tenant & User Isolation:
      Verifies that the message exists, belongs to an ASSISTANT role, and
      resides within a conversation owned by the authenticated user and tenant.
    """
    tenant_id = getattr(current_user, "tenant_id", "idfc_bank")
    correlation_id = getattr(request.state, "correlation_id", None)

    # Validate message and ownership
    stmt = (
        select(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.id == message_id,
            Conversation.user_id == current_user.id,
        )
    )
    res = await db.execute(stmt)
    row = res.first()

    if not row:
        await AuditService.log_event(
            db=db,
            action="feedback.submitted",
            resource_type="chat_message",
            resource_id=str(message_id),
            outcome="DENIED",
            tenant_id=tenant_id,
            actor_id=current_user.id,
            correlation_id=correlation_id,
            details={"reason": "Message not found or unauthorized user access"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found or access denied.",
        )

    message, conversation = row

    if message.role != MessageRole.ASSISTANT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback can only be submitted for assistant responses.",
        )

    # Normalize rating
    rating_upper = payload.rating.upper().strip()
    if rating_upper not in {"POSITIVE", "NEGATIVE", "LIKE", "DISLIKE", "THUMBS_UP", "THUMBS_DOWN"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rating must be 'POSITIVE' or 'NEGATIVE'.",
        )
    if rating_upper in {"LIKE", "THUMBS_UP"}:
        rating_upper = "POSITIVE"
    elif rating_upper in {"DISLIKE", "THUMBS_DOWN"}:
        rating_upper = "NEGATIVE"

    # Redact PII from user comment for storage/audit
    sanitized_comment = (
        PIIService.redact_text(payload.comment.strip()) if payload.comment else None
    )

    # Check for existing feedback by this user on this message
    existing_stmt = select(MessageFeedback).where(
        MessageFeedback.message_id == message_id,
        MessageFeedback.user_id == current_user.id,
    )
    existing_res = await db.execute(existing_stmt)
    feedback_rec = existing_res.scalars().first()

    if feedback_rec:
        # Update existing
        feedback_rec.rating = rating_upper
        feedback_rec.reason_category = payload.reason_category
        feedback_rec.comment = sanitized_comment
        action_type = "feedback.updated"
    else:
        # Create new
        feedback_rec = MessageFeedback(
            id=uuid.uuid4(),
            message_id=message_id,
            conversation_id=conversation.id,
            user_id=current_user.id,
            tenant_id=tenant_id,
            rating=rating_upper,
            reason_category=payload.reason_category,
            comment=sanitized_comment,
        )
        db.add(feedback_rec)
        action_type = "feedback.submitted"

    # Log audit event
    await AuditService.log_event(
        db=db,
        action=action_type,
        resource_type="chat_message",
        resource_id=str(message_id),
        outcome="SUCCESS",
        tenant_id=tenant_id,
        actor_id=current_user.id,
        correlation_id=correlation_id,
        details={
            "conversation_id": str(conversation.id),
            "rating": rating_upper,
            "reason_category": payload.reason_category,
            "has_comment": bool(sanitized_comment),
        },
    )

    await db.commit()
    await db.refresh(feedback_rec)
    return feedback_rec


@router.get(
    "/{message_id}/feedback",
    response_model=Optional[FeedbackResponse],
    summary="Get feedback for an assistant response.",
)
async def get_feedback(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Optional[MessageFeedback]:
    """
    Get existing feedback submitted by the current user for a message.
    """
    stmt = select(MessageFeedback).where(
        MessageFeedback.message_id == message_id,
        MessageFeedback.user_id == current_user.id,
    )
    res = await db.execute(stmt)
    return res.scalars().first()
