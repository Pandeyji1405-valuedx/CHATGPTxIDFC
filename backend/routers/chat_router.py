import json
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Conversation, Message, Response, Entity, AuditLog, get_utc_now
from backend.schemas import (
    ChatQueryRequest, ChatQueryResponse, CitationItem, AmbiguityFlag,
    ChatFeedbackRequest, ChatFeedbackResponse
)
from backend.auth import get_current_user
from backend.rag.rag_engine import rag_engine

router = APIRouter(prefix="/api/chat", tags=["Chat & RAG"])

def generate_chat_title(query: str, entities: list) -> str:
    """Generates a concise 3-6 word conversation title without sensitive details."""
    clean_q = re.sub(r"[^\w\s]", "", query).strip()
    words = clean_q.split()

    if entities:
        main_ent = entities[0]
        return f"{main_ent} Information"

    if len(words) <= 5:
        return " ".join([w.capitalize() for w in words])

    # Take first 4-5 words
    title_words = words[:4]
    return " ".join([w.capitalize() for w in title_words])

@router.post("", response_model=ChatQueryResponse)
def handle_chat_query(
    req: ChatQueryRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Core RAG Chat Endpoint:
    - Normalizes user query & resolves conversational references/pronouns.
    - Searches Conversation Database (Layer 1) & Approved Banking Knowledge Base (Layer 2).
    - Grounded Answer Synthesis & Fact Validation.
    - Stores messages, entities, source citations, and OCR ambiguity flags.
    - Zero-internet policy strictly enforced.
    """
    raw_query = req.query.strip()
    if not raw_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty"
        )

    # 1. Get or Create Conversation
    conversation = None
    if req.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == req.conversation_id,
            Conversation.user_id == current_user.id
        ).first()

    if not conversation:
        conversation = Conversation(
            user_id=current_user.id,
            title="New Conversation"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # 2. Run 2-Layer RAG Pipeline
    rag_result = rag_engine.process_query(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation.id,
        raw_query=raw_query
    )

    # 3. Update Conversation Title if it is still default
    if conversation.title in ["New Conversation", "New Chat"]:
        new_title = generate_chat_title(rag_result["normalized_query"], rag_result["resolved_entities"])
        conversation.title = new_title
        conversation.updated_at = get_utc_now()
        db.commit()

    # 4. Save User Message
    user_msg = Message(
        conversation_id=conversation.id,
        user_id=current_user.id,
        role="user",
        original_content=rag_result["original_query"],
        normalized_content=rag_result["normalized_query"]
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # 5. Save Extracted Entities
    for ent in rag_result["resolved_entities"]:
        ent_record = Entity(
            message_id=user_msg.id,
            entity_type="RESOLVED_ENTITY",
            entity_value=ent,
            canonical_value=ent
        )
        db.add(ent_record)

    # 6. Save Assistant Message and Response Record
    assistant_msg = Message(
        conversation_id=conversation.id,
        user_id=current_user.id,
        role="assistant",
        original_content=rag_result["answer"],
        normalized_content=rag_result["answer"]
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    response_record = Response(
        message_id=assistant_msg.id,
        answer=rag_result["answer"],
        source_type=rag_result["source_type"],
        confidence=rag_result["confidence"],
        citations_json=json.dumps(rag_result["citations"]),
        ambiguity_flags_json=json.dumps(rag_result["ambiguity_flags"]),
        validation_status="VALIDATED" if rag_result["source_type"] != "NO_SUPPORTED_SOURCE" else "FALLBACK"
    )
    db.add(response_record)

    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action="QUERY",
        resource_type="conversation",
        resource_id=conversation.id,
        details=f"Source: {rag_result['source_type']}, Confidence: {rag_result['confidence']}",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)

    # Update conversation timestamp
    conversation.updated_at = get_utc_now()
    db.commit()

    return ChatQueryResponse(
        conversation_id=conversation.id,
        conversation_title=conversation.title,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        original_query=rag_result["original_query"],
        normalized_query=rag_result["normalized_query"],
        resolved_entities=rag_result["resolved_entities"],
        answer=rag_result["answer"],
        source_type=rag_result["source_type"],
        confidence=rag_result["confidence"],
        citations=[CitationItem(**c) for c in rag_result["citations"]],
        ambiguity_flags=[AmbiguityFlag(**a) for a in rag_result["ambiguity_flags"]],
        clarification_needed=rag_result["clarification_needed"]
    )

@router.post("/feedback", response_model=ChatFeedbackResponse)
def submit_chat_feedback(
    req: ChatFeedbackRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits user accuracy feedback and ratings on specific assistant messages
    for regulatory audit compliance.
    """
    msg = db.query(Message).filter(Message.id == req.message_id).first()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target message not found"
        )

    # Save to AuditLog
    audit = AuditLog(
        user_id=current_user.id,
        action="FEEDBACK",
        resource_type="message",
        resource_id=req.message_id,
        details=f"Rating: {req.rating}/5, Category: {req.category}, Comments: {req.feedback_text or 'None'}",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()

    return ChatFeedbackResponse(
        status="recorded",
        message="Thank you! Your feedback has been recorded for compliance and accuracy auditing.",
        message_id=req.message_id
    )
