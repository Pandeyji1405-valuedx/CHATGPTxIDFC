import json
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import get_db
from backend.models import User, Conversation, Message, Response
from backend.schemas import (
    ConversationSummary, ConversationDetail, ConversationCreate,
    ConversationRename, MessageResponse, CitationItem, AmbiguityFlag,
    ShareConversationRequest, ShareConversationResponse,
    SharedConversationViewResponse, SharedMessageItem
)
from backend.auth import get_current_user
from backend.cache.redis_cache import redis_cache

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])
share_router = APIRouter(prefix="/api/share", tags=["Share"])

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

@router.post("/{conversation_id}/share", response_model=ShareConversationResponse)
def share_conversation(
    conversation_id: str,
    req: ShareConversationRequest = ShareConversationRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    FR-24: Generates a secure, read-only shareable snapshot link for compliance review and enterprise collaboration.
    """
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

    shared_messages = []
    for m in db_msgs:
        citations = []
        source_type = None
        if m.response:
            source_type = m.response.source_type
            if m.response.citations_json:
                try:
                    citations = json.loads(m.response.citations_json)
                except Exception:
                    pass
        content = m.original_content if m.role == "user" else (m.response.answer if m.response else m.original_content)
        shared_messages.append({
            "role": m.role,
            "content": content,
            "source_type": source_type,
            "citations": citations,
            "created_at": m.created_at.isoformat() if m.created_at else datetime.now(timezone.utc).isoformat()
        })

    share_token = secrets.token_urlsafe(16)
    hours = req.expires_in_hours or 72
    expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    ttl_seconds = hours * 3600

    snapshot_payload = {
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else datetime.now(timezone.utc).isoformat(),
        "shared_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
        "messages": shared_messages,
        "regulator_scope": "ALL",
        "shared_by": current_user.name
    }

    redis_cache.set(f"shared_conv:{share_token}", json.dumps(snapshot_payload), ex=ttl_seconds)

    return ShareConversationResponse(
        conversation_id=conv.id,
        share_token=share_token,
        share_url=f"/share/{share_token}",
        title=conv.title,
        expires_at=expires_at.isoformat(),
        message="Secure read-only conversation snapshot generated successfully."
    )

@share_router.get("/{share_token}", response_model=SharedConversationViewResponse)
def get_shared_conversation_view(share_token: str):
    """
    Public read-only view for shared conversation snapshot.
    """
    data_str = redis_cache.get(f"shared_conv:{share_token}")
    if not data_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared conversation link has expired or is invalid."
        )

    try:
        data = json.loads(data_str)
        return SharedConversationViewResponse(
            title=data.get("title", "Shared Conversation"),
            created_at=data.get("created_at", ""),
            shared_at=data.get("shared_at", ""),
            expires_at=data.get("expires_at"),
            messages=[SharedMessageItem(**m) for m in data.get("messages", [])],
            regulator_scope=data.get("regulator_scope", "ALL"),
            is_expired=False
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load shared conversation snapshot."
        )

@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        ).first()

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or unauthorized"
            )

        # Explicitly clean up messages and dependent records
        db.query(Message).filter(Message.conversation_id == conv.id).delete(synchronize_session=False)
        db.delete(conv)
        db.commit()
        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation."
        )
