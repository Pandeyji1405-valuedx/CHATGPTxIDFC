import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Message, FeedbackItem, AuditLog, get_utc_now
from backend.schemas import FeedbackSubmissionRequest, FeedbackSubmissionResponse
from backend.auth import get_current_user

router = APIRouter(prefix="/api/feedback", tags=["Feedback & Evaluation Triage"])

VALID_CATEGORIES = {
    "INCORRECT_FACT", "INCOMPLETE", "WRONG_SOURCE", "SUPERSEDED_OUTDATED",
    "TOO_LONG", "TOO_SHORT", "WRONG_REGULATOR", "UNCLEAR"
}

@router.post("", response_model=FeedbackSubmissionResponse)
def submit_structured_feedback(
    req: FeedbackSubmissionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits structured regulatory feedback conforming to PRD Section 5.4 8-category taxonomy:
    - INCORRECT_FACT, INCOMPLETE, WRONG_SOURCE, SUPERSEDED_OUTDATED,
    - TOO_LONG, TOO_SHORT, WRONG_REGULATOR, UNCLEAR.
    """
    if req.rating == "NEGATIVE" and req.category:
        if req.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category '{req.category}'. Must be one of: {', '.join(VALID_CATEGORIES)}"
            )

    msg = None
    if req.message_id:
        msg = db.query(Message).filter(Message.id == req.message_id).first()

    feedback_item = FeedbackItem(
        tenant_id=getattr(current_user, "tenant_id", "default_tenant"),
        user_id=current_user.id,
        message_id=req.message_id,
        query_trace_id=req.query_trace_id or (msg.response.query_trace_id if (msg and msg.response) else None),
        rating=req.rating,
        category=req.category,
        comment=req.comment,
        status="PENDING_REVIEW"
    )
    db.add(feedback_item)
    db.commit()
    db.refresh(feedback_item)

    # Log to audit trail
    audit = AuditLog(
        tenant_id=getattr(current_user, "tenant_id", "default_tenant"),
        user_id=current_user.id,
        action="FEEDBACK_SUBMISSION",
        resource_type="feedback_item",
        resource_id=feedback_item.id,
        details=f"Rating: {req.rating}, Category: {req.category or 'N/A'}, Comment: {req.comment or 'None'}",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()

    return FeedbackSubmissionResponse(
        status="logged",
        feedback_id=feedback_item.id,
        category=feedback_item.category,
        message="Thank you! Your feedback has been categorized and queued for regulatory review."
    )

@router.get("", response_model=List[dict])
def list_feedback_items(
    rating: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists submitted feedback items for quality reviewers and compliance administrators.
    """
    query = db.query(FeedbackItem).filter(
        FeedbackItem.tenant_id == getattr(current_user, "tenant_id", "default_tenant")
    )
    if rating:
        query = query.filter(FeedbackItem.rating == rating.upper())
    if category:
        query = query.filter(FeedbackItem.category == category.upper())

    items = query.order_by(FeedbackItem.created_at.desc()).limit(100).all()
    return [
        {
            "id": it.id,
            "user_id": it.user_id,
            "message_id": it.message_id,
            "query_trace_id": it.query_trace_id,
            "rating": it.rating,
            "category": it.category,
            "comment": it.comment,
            "status": it.status,
            "created_at": it.created_at
        }
        for it in items
    ]
