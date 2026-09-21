import os
import uuid
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, Conversation, Message, Response, Entity, AuditLog, get_utc_now
from backend.schemas import (
    ChatQueryRequest, ChatQueryResponse, CitationItem, AmbiguityFlag,
    ChatFeedbackRequest, ChatFeedbackResponse, ChatAttachmentInfo, ChatAttachmentUploadResponse
)
from backend.auth import get_current_user
from backend.rag.rag_engine import rag_engine
from backend.config import settings
from backend.ingestion.extractor import document_extractor

router = APIRouter(prefix="/api/chat", tags=["Chat & RAG"])

@router.post("/upload-attachment", response_model=ChatAttachmentUploadResponse)
async def upload_chat_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads and extracts multimodal file content (PDF, Image, Voice/Audio, DOCX, CSV, Text)
    for in-depth conversational examination in chat, exactly like ChatGPT.
    """
    filename = file.filename or "uploaded_attachment.pdf"
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file payload is empty."
        )

    # Save to user chat attachments dir
    chat_att_dir = os.path.join(settings.UPLOAD_DIR, "chat_attachments")
    os.makedirs(chat_att_dir, exist_ok=True)
    saved_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    file_path = os.path.join(chat_att_dir, saved_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # Extract text, OCR, or transcript
    extracted = document_extractor.extract(file_bytes, filename)
    ext = filename.lower().split(".")[-1] if "." in filename else "file"

    att = ChatAttachmentInfo(
        id=str(uuid.uuid4()),
        filename=filename,
        file_type=ext,
        file_size=len(file_bytes),
        extracted_text=extracted.get("full_text", ""),
        file_url=f"/static/uploads/chat_attachments/{saved_filename}"
    )
    return ChatAttachmentUploadResponse(attachment=att)

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
    - Searches Conversation Database (Layer 1) & Approved Multi-Regulator Knowledge Base (Layer 2).
    - Supports multimodal user attachments (PDF, OCR Image, Voice, Audio, Documents) for deep analysis.
    - Grounded Answer Synthesis, Token Budgeting, Response Composition & Fact Validation.
    - Stores messages, entities, source citations, and OCR ambiguity flags.
    - Zero-internet policy strictly enforced.
    """
    raw_query = req.query.strip() if req.query else "Analyze this attached file and provide detailed regulatory insights."

    try:
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
                tenant_id=getattr(current_user, "tenant_id", "default_tenant"),
                title="New Conversation",
                regulator_scope=",".join(req.regulator_filter) if req.regulator_filter else "ALL",
                as_of_date_scope=req.as_of_date
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)

        # 2. Extract friendly user display name
        from backend.rag.nlp_engine import nlp_engine
        user_name = nlp_engine.extract_friendly_user_name(current_user.name, current_user.email)

        # 3. Run Multi-Regulator 2-Layer RAG Pipeline with Attachment Support
        att_dict = req.attachment.model_dump() if req.attachment else None
        rag_result = rag_engine.process_query(
            db=db,
            user_id=current_user.id,
            user_name=user_name,
            conversation_id=conversation.id,
            raw_query=raw_query,
            attachment_context=att_dict,
            regulator_filter=req.regulator_filter,
            as_of_date=req.as_of_date,
            department_filter=req.department_filter,
            requested_depth=req.requested_depth or "concise",
            tenant_id=getattr(current_user, "tenant_id", "default_tenant")
        )

        # 3. Update Conversation Title if it is still default
        if conversation.title in ["New Conversation", "New Chat"]:
            new_title = generate_chat_title(rag_result["normalized_query"], rag_result["resolved_entities"])
            conversation.title = new_title
            conversation.updated_at = get_utc_now()
            db.commit()

        def clean_str(s: Optional[str]) -> str:
            return (s or "").replace("\x00", "").strip()

        # 4. Save User Message
        user_msg = Message(
            conversation_id=conversation.id,
            user_id=current_user.id,
            tenant_id=getattr(current_user, "tenant_id", "default_tenant"),
            role="user",
            original_content=clean_str(rag_result["original_query"]),
            normalized_content=clean_str(rag_result["normalized_query"])
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # 5. Save Extracted Entities
        for ent in rag_result["resolved_entities"]:
            ent_record = Entity(
                message_id=user_msg.id,
                entity_type="RESOLVED_ENTITY",
                entity_value=clean_str(ent),
                canonical_value=clean_str(ent)
            )
            db.add(ent_record)

        # 6. Save Assistant Message and Response Record
        assistant_msg = Message(
            conversation_id=conversation.id,
            user_id=current_user.id,
            tenant_id=getattr(current_user, "tenant_id", "default_tenant"),
            role="assistant",
            original_content=clean_str(rag_result["answer"]),
            normalized_content=clean_str(rag_result["answer"])
        )
        db.add(assistant_msg)
        db.commit()
        db.refresh(assistant_msg)

        tokens_dict = rag_result.get("tokens_used", {})
        response_record = Response(
            message_id=assistant_msg.id,
            answer=rag_result["answer"],
            source_type=rag_result["source_type"],
            confidence=rag_result["confidence"],
            citations_json=json.dumps(rag_result["citations"]),
            ambiguity_flags_json=json.dumps(rag_result["ambiguity_flags"]),
            validation_status="VALIDATED" if rag_result["source_type"] != "NO_SUPPORTED_SOURCE" else "FALLBACK",
            query_trace_id=rag_result.get("query_trace_id"),
            tokens_input=tokens_dict.get("tokens_input", 0),
            tokens_output=tokens_dict.get("tokens_output", 0)
        )
        db.add(response_record)

        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            tenant_id=getattr(current_user, "tenant_id", "default_tenant"),
            action="QUERY",
            resource_type="conversation",
            resource_id=conversation.id,
            details=f"Source: {rag_result['source_type']}, Confidence: {rag_result['confidence']}, Regulators: {rag_result.get('regulator_scope')}",
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
            query_trace_id=rag_result.get("query_trace_id"),
            original_query=rag_result["original_query"],
            normalized_query=rag_result["normalized_query"],
            resolved_entities=rag_result["resolved_entities"],
            regulator_scope=rag_result.get("regulator_scope", "ALL"),
            as_of_date_applied=rag_result.get("as_of_date_applied"),
            answer=rag_result["answer"],
            source_type=rag_result["source_type"],
            confidence=rag_result["confidence"],
            citations=[CitationItem(**c) for c in rag_result["citations"]],
            ambiguity_flags=[AmbiguityFlag(**a) for a in rag_result["ambiguity_flags"]],
            clarification_needed=rag_result["clarification_needed"],
            tokens_used=tokens_dict,
            attachment=req.attachment
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the banking query: {str(e)}"
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
        tenant_id=getattr(current_user, "tenant_id", "default_tenant"),
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
