"""
Phase 5E Version-Aware Cache Invalidation Engine.

Responsibilities:
  1. Find every CachedAnswer that depends on a given document_version_id via
     the cache_document_dependencies join table.
  2. Mark those CachedAnswer records is_active=False.
  3. Mark all QuestionVariant records pointing to those answers is_active=False.
  4. Evict the corresponding Redis exact-cache entries (best-effort).
  5. Leave all historical conversations and messages completely untouched.

Governance Rules:
  - Historical chat (conversations, messages) is NEVER modified or deleted.
  - Only reusable cache tables (cached_answers, question_variants) are affected.
  - Redis failure MUST NOT corrupt PostgreSQL invalidation state.
  - Invalidation is idempotent: running twice produces the same safe result.
  - Validation gate (CacheValidationGate) rejects candidates with stale
    document versions independently, providing defence-in-depth.
"""

import logging
import uuid
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cache import CachedAnswer, CacheDocumentDependency, QuestionVariant
from app.services.cache.redis_service import RedisService

logger = logging.getLogger(__name__)


class CacheInvalidationService:
    """
    Cascade invalidation of reusable cache entries on document version changes.

    Idempotent: calling invalidate_version_dependencies() multiple times for the
    same version_id is safe — records already set to is_active=False are not
    double-counted.
    """

    def __init__(self, redis_service: Optional[RedisService] = None):
        self.redis_service = redis_service or RedisService()

    async def invalidate_version_dependencies(
        self,
        version_id: uuid.UUID,
        db: AsyncSession,
    ) -> int:
        """
        Invalidate all reusable cached_answers dependent on the given version_id,
        and cascade deactivation to their associated question_variants.

        Args:
            version_id: UUID of the document version being superseded/withdrawn.
            db:         Async database session. Caller is responsible for
                        committing the transaction after this call.

        Returns:
            Number of CachedAnswer records newly invalidated (those that were
            previously active). Already-inactive records are not counted.

        Transaction safety:
            This method uses db.flush() for all writes. It does NOT call
            db.commit() — that is the caller's responsibility. This prevents
            mid-handler transaction boundary violations.

        Redis safety:
            Redis eviction is attempted after the PostgreSQL writes are flushed.
            If Redis is unavailable the flush still succeeds and PostgreSQL
            state is correct. The CacheValidationGate provides defence-in-depth
            by independently checking document version status on every lookup.
        """
        # ------------------------------------------------------------------
        # Step 1: Find all cache_answer_ids that depend on this version
        # ------------------------------------------------------------------
        dep_stmt = select(CacheDocumentDependency.cache_answer_id).where(
            CacheDocumentDependency.document_version_id == version_id
        )
        dep_res = await db.execute(dep_stmt)
        all_cache_ids: List[uuid.UUID] = list(dep_res.scalars().all())

        if not all_cache_ids:
            logger.info(
                "No reusable cache entries depend on document version %s — nothing to invalidate.",
                version_id,
            )
            return 0

        # ------------------------------------------------------------------
        # Step 2: Deactivate the CachedAnswer records (idempotent: only where active)
        # ------------------------------------------------------------------
        answer_update_stmt = (
            update(CachedAnswer)
            .where(
                CachedAnswer.id.in_(all_cache_ids),
                CachedAnswer.is_active == True,
            )
            .values(is_active=False)
            .execution_options(synchronize_session="fetch")
        )
        answer_res = await db.execute(answer_update_stmt)
        invalidated_count: int = answer_res.rowcount
        await db.flush()

        if invalidated_count > 0:
            logger.info(
                "Invalidated %d CachedAnswer record(s) dependent on document version %s.",
                invalidated_count,
                version_id,
            )
        else:
            logger.info(
                "All %d CachedAnswer record(s) dependent on version %s were already inactive.",
                len(all_cache_ids),
                version_id,
            )

        # ------------------------------------------------------------------
        # Step 3: Deactivate associated QuestionVariant records
        # ------------------------------------------------------------------
        variant_update_stmt = (
            update(QuestionVariant)
            .where(
                QuestionVariant.cache_answer_id.in_(all_cache_ids),
                QuestionVariant.is_active == True,
            )
            .values(is_active=False)
            .execution_options(synchronize_session="fetch")
        )
        variant_res = await db.execute(variant_update_stmt)
        invalidated_variants: int = variant_res.rowcount
        await db.flush()

        if invalidated_variants > 0:
            logger.info(
                "Invalidated %d QuestionVariant record(s) linked to version %s.",
                invalidated_variants,
                version_id,
            )

        # ------------------------------------------------------------------
        # Step 4: Evict Redis exact-cache keys (best-effort; failure is non-fatal)
        # ------------------------------------------------------------------
        try:
            evicted = await self.redis_service.evict_version_keys(str(version_id))
            logger.info(
                "Evicted %d Redis key(s) for version %s.",
                evicted,
                version_id,
            )
        except Exception as redis_exc:
            # Redis failure MUST NOT prevent PostgreSQL invalidation from being committed.
            # The CacheValidationGate will independently reject stale candidates.
            logger.warning(
                "Redis eviction failed for version %s (%s). "
                "PostgreSQL invalidation is intact; stale Redis entries will be "
                "rejected by CacheValidationGate on next lookup.",
                version_id,
                redis_exc,
            )

        return invalidated_count

    async def invalidate_cache_answer(
        self,
        cache_answer_id: uuid.UUID,
        db: AsyncSession,
    ) -> bool:
        """
        Directly deactivate a single CachedAnswer and its variants.

        Useful for targeted administrative invalidation of a specific answer
        without requiring a full document version lifecycle event.

        Args:
            cache_answer_id: UUID of the CachedAnswer to invalidate.
            db:              Async session. Caller commits.

        Returns:
            True if the record was found and deactivated, False if already
            inactive or not found.
        """
        # Deactivate the answer
        answer_stmt = (
            update(CachedAnswer)
            .where(
                CachedAnswer.id == cache_answer_id,
                CachedAnswer.is_active == True,
            )
            .values(is_active=False)
            .execution_options(synchronize_session="fetch")
        )
        answer_res = await db.execute(answer_stmt)
        deactivated = answer_res.rowcount > 0
        await db.flush()

        if not deactivated:
            return False

        # Deactivate variants
        variant_stmt = (
            update(QuestionVariant)
            .where(
                QuestionVariant.cache_answer_id == cache_answer_id,
                QuestionVariant.is_active == True,
            )
            .values(is_active=False)
            .execution_options(synchronize_session="fetch")
        )
        await db.execute(variant_stmt)
        await db.flush()

        logger.info(
            "Directly invalidated CachedAnswer %s and its variants.",
            cache_answer_id,
        )
        return True
