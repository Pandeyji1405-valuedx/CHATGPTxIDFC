import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import get_db
from backend.models import User, Conversation, Message, Response
from backend.schemas import (
    ConversationSummary, ConversationDetail, ConversationCreate,
    ConversationRename, MessageResponse, CitationItem, AmbiguityFlag
)
from backend.auth import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

@router.get("", response_model=List[ConversationSummary])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all conversations for the authenticated user, sorted by latest update."""
    convs = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).all()

    summaries = []
    for c in convs:
        msg_count = db.query(Message).filter(Message.conversation_id == c.id).count()
        last_msg = db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.created_at.desc()).first()
        last_preview = last_msg.original_content[:80] if last_msg else None

        summaries.append(ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=msg_count,
            last_message_preview=last_preview
        ))
    return summaries

@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
def create_conversation(
    req: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Creates a new empty conversation for the authenticated user."""
    conv = Conversation(
        user_id=current_user.id,
        title=req.title or "New Conversation"
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[]
    )

@router.get("/search", response_model=List[ConversationSummary])
def search_conversations(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Searches across conversation titles, original queries, normalized queries,
    and assistant responses strictly for the authenticated user.
    """
    search_term = f"%{q.strip()}%"
    matching_convs = db.query(Conversation).filter(
        Conversation.user_id == current_user.id,
        or_(
            Conversation.title.ilike(search_term),
            Conversation.messages.any(Message.original_content.ilike(search_term)),
            Conversation.messages.any(Message.normalized_content.ilike(search_term)),
            Conversation.messages.any(Message.response.has(Response.answer.ilike(search_term)))
        )
    ).order_by(Conversation.updated_at.desc()).all()

    summaries = []
    for c in matching_convs:
        msg_count = db.query(Message).filter(Message.conversation_id == c.id).count()
        last_msg = db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.created_at.desc()).first()
        summaries.append(ConversationSummary(
            id=c.id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=msg_count,
            last_message_preview=last_msg.original_content[:80] if last_msg else None
        ))
    return summaries

@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation_details(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches full conversation history with citations and ambiguity flags."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized"
        )

    db_msgs = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    messages_list = []
    for m in db_msgs:
        citations = []
        ambiguity_flags = []
        answer_text = None
        source_type = None
        confidence = None

        if m.response:
            resp = m.response
            answer_text = resp.answer
            source_type = resp.source_type
            confidence = resp.confidence
            if resp.citations_json:
                try:
                    c_data = json.loads(resp.citations_json)
                    citations = [CitationItem(**c) for c in c_data]
                except Exception:
                    pass
            if resp.ambiguity_flags_json:
                try:
                    a_data = json.loads(resp.ambiguity_flags_json)
                    ambiguity_flags = [AmbiguityFlag(**a) for a in a_data]
                except Exception:
                    pass

        messages_list.append(MessageResponse(
            id=m.id,
            role=m.role,
            original_content=m.original_content,
            normalized_content=m.normalized_content,
            created_at=m.created_at,
            answer=answer_text,
            source_type=source_type,
            confidence=confidence,
            citations=citations,
            ambiguity_flags=ambiguity_flags
        ))

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages_list
    )

@router.put("/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: str,
    req: ConversationRename,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized"
        )

    conv.title = req.title.strip()
    db.commit()
    db.refresh(conv)

    return ConversationSummary(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=db.query(Message).filter(Message.conversation_id == conv.id).count()
    )

@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized"
        )

    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted successfully"}
