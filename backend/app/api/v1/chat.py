"""
Chat REST API Router — Phase 4 Core RBI RAG.

Provides the following endpoints:

  POST   /api/v1/chat/message
    Submit a regulatory question. Optionally continues an existing conversation.
    Returns a grounded RAG answer with verified citations.

  GET    /api/v1/chat/conversations
    List the authenticated user's conversations.

  GET    /api/v1/chat/conversations/{conversation_id}
    Retrieve a conversation with full message history.

  DELETE /api/v1/chat/conversations/{conversation_id}
    Delete a conversation and all its messages.

Security rules:
  - All endpoints require a valid Bearer token (get_current_user).
  - Users can only access their own conversations (ownership enforced by query).
  - Ownership violations return 404 (not 403) to avoid leaking ID existence.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.chat import Conversation, Message, MessageRole
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    CitationResponse,
    ConversationDetailResponse,
    ConversationSummaryResponse,
    MessageResponse,
)
from app.services.rag.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ------------------------------------------------------------------ #
# Helper: ownership guard
# ------------------------------------------------------------------ #

async def _get_owned_conversation(
    conversation_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Conversation:
    """
    Load a conversation, verifying it belongs to current_user.

    Raises 404 if not found OR if owned by a different user (ownership
    indistinguishable from absence to prevent ID enumeration).
    """
    stmt = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    conv = result.scalars().first()
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conv


from app.services.security.rate_limit_service import RateLimiter
from app.services.security.audit_service import AuditService

chat_rate_limiter = RateLimiter(endpoint_group="chat")


# ------------------------------------------------------------------ #
# POST /api/v1/chat/message
# ------------------------------------------------------------------ #

@router.post(
    "/message",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(chat_rate_limiter)],
    summary="Ask a regulatory question",
    description=(
        "Submit a regulatory question and receive a grounded RAG answer "
        "with traceable RBI source citations. "
        "Supply an existing conversation_id to continue a thread, "
        "or omit it to start a new conversation."
    ),
)
async def ask_question(
    body: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ---------------------------------------------------------------- #
    # 1. Resolve or create conversation
    # ---------------------------------------------------------------- #
    if body.conversation_id:
        conversation = await _get_owned_conversation(
            conversation_id=body.conversation_id,
            current_user=current_user,
            db=db,
        )
    else:
        # Auto-create with title derived from first message (truncated)
        title = body.message[:80].strip() + ("..." if len(body.message) > 80 else "")
        conversation = Conversation(
            user_id=current_user.id,
            title=title,
            message_count=0,
        )
        db.add(conversation)
        await db.flush()
        await db.refresh(conversation)

    # ---------------------------------------------------------------- #
    # 2. Persist user message (verbatim — no normalization)
    # ---------------------------------------------------------------- #
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=body.message,
    )
    db.add(user_msg)
    conversation.message_count += 1
    await db.flush()
    await db.refresh(user_msg)

    # ---------------------------------------------------------------- #
    # 3. Phase 5 Session Memory & Query Contextualization
    # ---------------------------------------------------------------- #
    from app.services.cache.redis_service import RedisService
    from app.services.cache.contextualizer import QueryContextualizer
    from app.services.cache.cache_service import CacheService
    from app.services.cache.variant_service import VariantService
    from app.services.rag.llm_gateway import get_llm_gateway

    # Tenant identifier — always sourced from auth context, never from client input.
    # In Phase 5 the platform operates under a single-tenant model for IDFC Bank.
    TENANT_ID = "idfc_bank"

    redis_service = RedisService()
    contextualizer = QueryContextualizer()
    llm_gateway = get_llm_gateway()

    # Fetch recent session history (Phase 5B)
    # Failure is safe: empty list causes standalone-query path.
    session_history = []
    try:
        session_history = await redis_service.get_session_context(
            tenant_id=TENANT_ID,
            user_id=str(current_user.id),
            conversation_id=str(conversation.id),
        )
    except Exception as _redis_read_exc:
        logger.warning(
            "Redis session read failed for user=%s conv=%s (%s). Continuing without session context.",
            current_user.id,
            conversation.id,
            _redis_read_exc,
        )

    # Deterministic query contextualization (Phase 5B)
    # original_query is always preserved; canonical_query is the enriched retrieval query.
    canonical_query, was_contextualized = await contextualizer.contextualize(
        prompt=body.message,
        session_history=session_history,
        llm_gateway=llm_gateway,
    )

    # ---------------------------------------------------------------- #
    # 4. Phase 5C/D: Sequential 3-Tier Cache Lookup (Tiers 1-3)
    # ---------------------------------------------------------------- #
    # Strict governance validation runs on every candidate.
    # Only after all three tiers miss does execution fall through to
    # the Phase 4 Main Hybrid RAG pipeline (Tier 4).
    variant_service = VariantService(llm_gateway=llm_gateway)
    cache_service = CacheService(
        redis_service=redis_service,
        variant_service=variant_service,
    )
    cached_candidate, cache_type, cache_latency_ms = await cache_service.lookup(
        canonical_query=canonical_query,
        user=current_user,
        db=db,
        tenant_id=TENANT_ID,
    )

    if cached_candidate:
        # CACHE HIT from Tiers 1-3
        answer_text = cached_candidate["answer"]
        citations_raw = cached_candidate.get("citations") or []
        citations_objs = [CitationResponse(**c) for c in citations_raw]
        retrieval_type = "rag"
        metrics = {
            "cache_hit": True,
            "cache_type": cache_type,
            "tokens_saved": 450,
            "total_latency_ms": cache_latency_ms,
            "cache_lookup_latency_ms": cache_latency_ms,
            "retrieval_latency_ms": 0.0,
            "generation_latency_ms": 0.0,
            "was_contextualized": was_contextualized,
            "canonical_query": canonical_query,
        }
    else:
        # CACHE MISS — Execute Tier 4 Main Hybrid RAG Pipeline
        rag_service = RAGService(llm_gateway=llm_gateway)
        try:
            rag_result = await rag_service.answer(query=canonical_query, db=db)
        except Exception as exc:
            logger.error("RAG pipeline error for user %s: %s", current_user.id, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while processing your question. Please try again.",
            )

        answer_text = rag_result.answer
        retrieval_type = rag_result.retrieval_type
        citations_objs = rag_result.citations
        citations_dict = [c.model_dump(mode="json") for c in citations_objs]

        metrics = rag_result.metrics
        metrics["cache_hit"] = False
        metrics["cache_type"] = "none"
        metrics["was_contextualized"] = was_contextualized
        metrics["canonical_query"] = canonical_query

        # Write-through to governed cache only for grounded answers with citations.
        # write_through uses db.flush() not commit — the outer commit below
        # handles the full transaction atomically.
        if retrieval_type == "rag" and citations_dict:
            cached_rec = await cache_service.write_through(
                canonical_query=canonical_query,
                original_user_query=body.message,
                answer=answer_text,
                citations=citations_dict,
                db=db,
                tenant_id=TENANT_ID,
                required_role=current_user.role.value,
            )
            # Phase 5E: Generate bounded governed question variants (non-fatal).
            # Variant generation never blocks the response. Failure is logged.
            if cached_rec is not None:
                try:
                    await variant_service.create_variants(
                        cached_answer=cached_rec,
                        canonical_query=canonical_query,
                        db=db,
                        tenant_id=TENANT_ID,
                    )
                except Exception as _variant_exc:
                    logger.warning(
                        "Phase 5E variant generation failed (non-fatal) for conv=%s: %s",
                        conversation.id,
                        _variant_exc,
                    )

    # ---------------------------------------------------------------- #
    # 5. Append Turn to Redis Session Memory (Phase 5B)
    # ---------------------------------------------------------------- #
    # Store both original_query and canonical_query so future contextualizer
    # turns can extract the correct resolved entity from prior turns.
    # Redis failure MUST NOT corrupt PostgreSQL history.
    turn_payload = {
        "message_id": str(user_msg.id),
        "role": "USER",
        "original_query": body.message,
        "canonical_query": canonical_query,
        "summary_answer": answer_text[:250],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await redis_service.append_session_turn(
            tenant_id=TENANT_ID,
            user_id=str(current_user.id),
            conversation_id=str(conversation.id),
            turn=turn_payload,
        )
    except Exception as _redis_write_exc:
        logger.warning(
            "Redis session write failed for user=%s conv=%s (%s). PostgreSQL history unaffected.",
            current_user.id,
            conversation.id,
            _redis_write_exc,
        )

    # ---------------------------------------------------------------- #
    # 6. Persist assistant message with citations and metrics
    # ---------------------------------------------------------------- #
    citations_json = [c.model_dump(mode="json") for c in citations_objs]

    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=answer_text,
        retrieval_type=retrieval_type,
        citations=citations_json,
        metrics=metrics,
    )
    db.add(assistant_msg)
    conversation.message_count += 1
    await db.flush()
    await db.refresh(assistant_msg)

    await db.commit()

    logger.info(
        "Chat message answered: user=%s, conv=%s, type=%s, citations=%d, cache_hit=%s",
        current_user.id,
        conversation.id,
        retrieval_type,
        len(citations_objs),
        metrics.get("cache_hit", False),
    )

    return ChatMessageResponse(
        conversation_id=conversation.id,
        message_id=assistant_msg.id,
        answer=answer_text,
        retrieval_type=retrieval_type,
        citations=citations_objs,
        created_at=assistant_msg.created_at,
        metrics=metrics,
    )


# ------------------------------------------------------------------ #
# GET /api/v1/chat/conversations
# ------------------------------------------------------------------ #

@router.get(
    "/conversations",
    response_model=List[ConversationSummaryResponse],
    summary="List conversations",
    description="List all conversations belonging to the authenticated user.",
)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    result = await db.execute(stmt)
    convs = result.scalars().all()
    return [
        ConversationSummaryResponse(
            id=c.id,
            title=c.title,
            message_count=c.message_count,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]


# ------------------------------------------------------------------ #
# GET /api/v1/chat/conversations/{conversation_id}
# ------------------------------------------------------------------ #

@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation detail",
    description=(
        "Retrieve a conversation with its full message history. "
        "Returns 404 if the conversation does not exist or belongs to another user."
    ),
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = [
        MessageResponse(
            id=m.id,
            role=m.role.value,
            content=m.content,
            retrieval_type=m.retrieval_type,
            citations=(
                [CitationResponse(**c) for c in m.citations]
                if m.citations else None
            ),
            metrics=m.metrics,
            created_at=m.created_at,
        )
        for m in sorted(
            conv.messages,
            key=lambda x: (
                x.created_at,
                0 if (getattr(x.role, 'value', x.role) == MessageRole.USER.value or x.role == MessageRole.USER) else 1
            )
        )
    ]

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        message_count=conv.message_count,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


# ------------------------------------------------------------------ #
# DELETE /api/v1/chat/conversations/{conversation_id}
# ------------------------------------------------------------------ #

@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
    description=(
        "Delete a conversation and all its messages. "
        "Returns 404 if the conversation does not exist or belongs to another user."
    ),
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_owned_conversation(conversation_id, current_user, db)
    await db.delete(conv)
    await db.commit()
    logger.info("Conversation %s deleted by user %s", conversation_id, current_user.id)
