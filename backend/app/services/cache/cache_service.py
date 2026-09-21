"""
Phase 5 Sequential Cache Service (Tiers 1–3 + 5E Variant Lookup).

Orchestrates sequential cache lookups and write-through:
  1.   Redis Exact Cache          (Tier 1   — hot in-memory)
  1.5. PG QuestionVariant Lookup  (Tier 1.5 — variant hash → CachedAnswer → gates)
  2.   PostgreSQL Exact Cache     (Tier 2   — persistent backstop)
  3.   PostgreSQL pgvector Semantic Cache (Tier 3 — cosine similarity >= threshold)
  4.   Main Hybrid RAG            (Tier 4 — fallback, invoked by caller)

Enforces strict governance validation before returning ANY candidate.

HIGH SIMILARITY IS NOT SUFFICIENT for a cache hit.  Every candidate must
pass ALL governance gates in CacheValidationGate before being returned.

Variant lookup (Tier 1.5, Phase 5E):
  A question variant is an alias for an approved cached answer.
  Variant resolution still requires all 10 governance gates to pass.
  Inactive variants (is_active=False) are never resolved.
  Variants pointing to inactive CachedAnswer records are silently dropped.

asyncpg parameter binding notes
--------------------------------
asyncpg uses positional placeholders ($1, $2, ...) at the wire level.
SQLAlchemy translates named parameters (:name) to positional internally,
but the ::cast syntax within SQL strings causes asyncpg to misparse the
parameter list.  To safely cast query vectors we use CAST(:name AS vector)
which avoids the :: operator being adjacent to the parameter placeholder.
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select, text, bindparam
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.cache import CachedAnswer, CacheDocumentDependency, QuestionVariant
from app.models.user import User
from app.services.cache.redis_service import RedisService
from app.services.cache.validation_gate import CacheValidationGate
from app.services.embeddings.nomic_service import NomicEmbeddingService

logger = logging.getLogger(__name__)
settings = get_settings()


def hash_query(query: str) -> str:
    """Compute normalized SHA-256 hash of query string."""
    norm = " ".join(query.lower().strip().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _embed_to_pg_literal(embed: List[float]) -> str:
    """
    Serialize a float vector to PostgreSQL vector literal string.

    Using the '[f1,f2,...]' string format which can be safely passed
    to pgvector via CAST(... AS vector) without triggering asyncpg
    positional-parameter parsing issues.
    """
    return f"[{','.join(str(f) for f in embed)}]"


class CacheService:
    """
    Tier 1–3 cache orchestrator with Phase 5E variant lookup and write-through.
    """

    def __init__(
        self,
        redis_service: Optional[RedisService] = None,
        embedding_service: Optional[NomicEmbeddingService] = None,
        validation_gate: Optional[CacheValidationGate] = None,
        variant_service=None,  # Optional[VariantService] — avoids circular import
    ):
        self.redis_service = redis_service or RedisService()
        self.embedding_service = embedding_service or NomicEmbeddingService()
        self.validation_gate = validation_gate or CacheValidationGate()
        # variant_service is injected lazily by chat.py to avoid circular imports
        self.variant_service = variant_service

    async def lookup(
        self,
        canonical_query: str,
        user: User,
        db: AsyncSession,
        tenant_id: str = "idfc_bank",
    ) -> Tuple[Optional[Dict[str, Any]], str, float]:
        """
        Execute sequential cache lookup (Tiers 1 → 1.5 variant → 2 → 3).

        Returns:
            Tuple of (candidate_dict_or_none, cache_type_string, lookup_latency_ms)
            cache_type_string is one of:
              "redis_exact", "pg_variant", "pg_exact", "pg_semantic", "none"

        The caller (chat.py) invokes Tier 4 (Main Hybrid RAG) when this returns None.
        """
        if not settings.CACHE_ENABLED:
            return None, "none", 0.0

        t_start = time.monotonic()
        q_hash = hash_query(canonical_query)

        # ------------------------------------------------------------------ #
        # Tier 1: Redis Exact Cache
        # ------------------------------------------------------------------ #
        try:
            t1_candidate = await self.redis_service.get_exact_cache(q_hash)
            if t1_candidate:
                approved, reason = await self.validation_gate.validate_candidate(
                    t1_candidate, user, db, tenant_id=tenant_id
                )
                if approved:
                    latency = round((time.monotonic() - t_start) * 1000, 2)
                    logger.info(
                        "Tier 1 Redis Exact Cache HIT (%.2fms) for '%s'",
                        latency,
                        canonical_query[:50],
                    )
                    return t1_candidate, "redis_exact", latency
                else:
                    logger.info(
                        "Tier 1 Redis Exact Candidate REJECTED by Gate: %s", reason
                    )
        except Exception as redis_exc:
            # Redis failure must not abort the chat request
            logger.warning(
                "Tier 1 Redis exact lookup failed (continuing to Tier 2): %s", redis_exc
            )

        # ------------------------------------------------------------------ #
        # Tier 1.5: Phase 5E — QuestionVariant Lookup
        # Checks whether the incoming query hash matches a stored variant alias.
        # The variant resolves to a CachedAnswer which still passes ALL 10 gates.
        # Inactive variants (is_active=False) are never returned.
        # ------------------------------------------------------------------ #
        if self.variant_service is not None:
            try:
                variant_answer = await self.variant_service.resolve_variant(
                    q_hash, db, tenant_id=tenant_id
                )
                if variant_answer:
                    candidate_dict = self._record_to_dict(variant_answer)
                    approved, reason = await self.validation_gate.validate_candidate(
                        candidate_dict, user, db, tenant_id=tenant_id
                    )
                    if approved:
                        latency = round((time.monotonic() - t_start) * 1000, 2)
                        logger.info(
                            "Tier 1.5 Variant Cache HIT (%.2fms) for '%s'",
                            latency,
                            canonical_query[:50],
                        )
                        # Write-through the resolved answer to Redis under the
                        # variant hash so subsequent identical requests hit Tier 1
                        try:
                            await self.redis_service.set_exact_cache(q_hash, candidate_dict)
                        except Exception as redis_wt_exc:
                            logger.warning(
                                "Tier 1.5 Redis write-through failed (non-fatal): %s",
                                redis_wt_exc,
                            )
                        return candidate_dict, "pg_variant", latency
                    else:
                        logger.info(
                            "Tier 1.5 Variant Candidate REJECTED by Gate: %s", reason
                        )
            except Exception as variant_exc:
                logger.warning(
                    "Tier 1.5 variant lookup failed (continuing to Tier 2): %s",
                    variant_exc,
                )

        # ------------------------------------------------------------------ #
        # Tier 2: PostgreSQL Exact Cache Backstop
        # ------------------------------------------------------------------ #
        stmt = (
            select(CachedAnswer)
            .where(
                CachedAnswer.query_hash == q_hash,
                CachedAnswer.is_active == True,
                CachedAnswer.expires_at > datetime.now(timezone.utc),
            )
            .order_by(CachedAnswer.created_at.desc())
            .limit(1)
        )
        res = await db.execute(stmt)
        t2_record = res.scalars().first()

        if t2_record:
            candidate_dict = self._record_to_dict(t2_record)
            approved, reason = await self.validation_gate.validate_candidate(
                candidate_dict, user, db, tenant_id=tenant_id
            )
            if approved:
                # Increment hit count — use flush, not commit, to avoid
                # mid-handler transaction boundary issues.
                t2_record.hit_count += 1
                await db.flush()

                # Write-through to Tier 1 Redis (best-effort; failure is non-fatal)
                try:
                    await self.redis_service.set_exact_cache(q_hash, candidate_dict)
                except Exception as redis_write_exc:
                    logger.warning(
                        "Tier 2 Redis write-through failed (non-fatal): %s", redis_write_exc
                    )

                latency = round((time.monotonic() - t_start) * 1000, 2)
                logger.info(
                    "Tier 2 PG Exact Cache HIT (%.2fms) for '%s'",
                    latency,
                    canonical_query[:50],
                )
                return candidate_dict, "pg_exact", latency
            else:
                logger.info(
                    "Tier 2 PG Exact Candidate REJECTED by Gate: %s", reason
                )

        # ------------------------------------------------------------------ #
        # Tier 3: PostgreSQL + pgvector Semantic Cache
        # ------------------------------------------------------------------ #
        # CRITICAL: wrap in a savepoint so that any DB error during the
        # pgvector query rolls back only this sub-transaction and leaves the
        # outer chat transaction (conversation/message inserts) intact.
        try:
            async with db.begin_nested():
                # embed_query() internally prepends "search_query: " prefix per
                # Nomic Embed v1.5 specification.
                q_embed = self.embedding_service.embed_query(canonical_query)
                embed_str = _embed_to_pg_literal(q_embed)

                # Use CAST(:param AS vector) rather than :param::vector to avoid
                # the asyncpg bug where :: adjacent to a named param causes a
                # parse error ("unexpected message type 'D' inside simple query")
                sim_sql = text(
                    """
                    SELECT id, query_hash, original_user_query, canonical_query,
                           answer, citations, tenant_id, required_role,
                           is_active, expires_at, created_at,
                           (1 - (query_vector <=> CAST(:embed AS vector))) AS similarity
                    FROM cached_answers
                    WHERE is_active = TRUE
                      AND expires_at > NOW()
                      AND query_vector IS NOT NULL
                      AND (1 - (query_vector <=> CAST(:embed AS vector))) >= :threshold
                    ORDER BY query_vector <=> CAST(:embed AS vector) ASC
                    LIMIT 1;
                    """
                )

                res = await db.execute(
                    sim_sql,
                    {
                        "embed": embed_str,
                        "threshold": settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD,
                    },
                )
                row = res.fetchone()

                if row:
                    t3_dict = {
                        "id": str(row.id),
                        "query_hash": row.query_hash,
                        "original_user_query": row.original_user_query,
                        "canonical_query": row.canonical_query,
                        "answer": row.answer,
                        "citations": (
                            row.citations
                            if isinstance(row.citations, list)
                            else json.loads(row.citations or "[]")
                        ),
                        "tenant_id": row.tenant_id,
                        "required_role": row.required_role,
                        "is_active": row.is_active,
                        "expires_at": (
                            row.expires_at.isoformat() if row.expires_at else None
                        ),
                        "similarity": float(row.similarity),
                    }

                    approved, reason = await self.validation_gate.validate_candidate(
                        t3_dict, user, db, tenant_id=tenant_id
                    )
                    if approved:
                        # Write-through to Tier 1 Redis (best-effort)
                        try:
                            await self.redis_service.set_exact_cache(q_hash, t3_dict)
                        except Exception as redis_write_exc:
                            logger.warning(
                                "Tier 3 Redis write-through failed (non-fatal): %s",
                                redis_write_exc,
                            )

                        latency = round((time.monotonic() - t_start) * 1000, 2)
                        logger.info(
                            "Tier 3 PG Semantic Cache HIT (sim=%.4f, %.2fms) for '%s'",
                            row.similarity,
                            latency,
                            canonical_query[:50],
                        )
                        return t3_dict, "pg_semantic", latency
                    else:
                        logger.info(
                            "Tier 3 PG Semantic Candidate REJECTED by Gate "
                            "(sim=%.4f): %s",
                            row.similarity,
                            reason,
                        )

        except Exception as exc:
            # Savepoint auto-rolled back; outer transaction is clean.
            # Log as WARNING so operators can detect pgvector availability issues.
            logger.warning(
                "Tier 3 pgvector semantic lookup failed (continuing to Tier 4): %s",
                exc,
            )

        latency = round((time.monotonic() - t_start) * 1000, 2)
        logger.debug("Cache MISS across Tiers 1-3 (%.2fms) for '%s'", latency, canonical_query[:50])
        return None, "none", latency

    async def write_through(
        self,
        canonical_query: str,
        original_user_query: str,
        answer: str,
        citations: List[Dict[str, Any]],
        db: AsyncSession,
        tenant_id: str = "idfc_bank",
        required_role: str = "USER",
    ) -> Optional[CachedAnswer]:
        """
        Persist a grounded RAG answer to PostgreSQL with full provenance,
        then write-through to Redis hot cache.

        Provenance stored per BRD:
          - tenant_id, required_role, query_hash, original_user_query,
            canonical_query, answer, citations, query_vector,
            document version dependencies (via CacheDocumentDependency),
            created_at, expires_at, updated_at, is_active, hit_count.

        Returns:
            CachedAnswer ORM object on success, None on failure.
        """
        if not settings.CACHE_ENABLED:
            return None

        try:
            q_hash = hash_query(canonical_query)

            # Generate embedding (with "search_query: " prefix — Nomic v1.5 spec)
            q_embed = self.embedding_service.embed_query(canonical_query)
            embed_str = _embed_to_pg_literal(q_embed)

            expires_at = datetime.now(timezone.utc) + timedelta(days=30)

            # Create CachedAnswer record
            cached_rec = CachedAnswer(
                query_hash=q_hash,
                original_user_query=original_user_query,
                canonical_query=canonical_query,
                answer=answer,
                citations=citations,
                tenant_id=tenant_id,
                required_role=required_role,
                is_active=True,
                expires_at=expires_at,
            )
            db.add(cached_rec)
            await db.flush()

            # Store vector embedding using CAST(:embed AS vector) to avoid
            # the asyncpg ::vector parsing issue.
            try:
                await db.execute(
                    text(
                        "UPDATE cached_answers "
                        "SET query_vector = CAST(:embed AS vector) "
                        "WHERE id = :id"
                    ),
                    {"embed": embed_str, "id": cached_rec.id},
                )
            except Exception as v_exc:
                logger.warning(
                    "pgvector embedding write skipped for cache entry %s: %s",
                    cached_rec.id,
                    v_exc,
                )

            # Build document version dependency records for cascade invalidation
            version_ids: set = set()
            for c in citations:
                v_id = c.get("version_id")
                if v_id:
                    try:
                        version_ids.add(uuid.UUID(str(v_id)))
                    except ValueError:
                        pass

            for v_id in version_ids:
                dep = CacheDocumentDependency(
                    cache_answer_id=cached_rec.id,
                    document_version_id=v_id,
                )
                db.add(dep)
                # Index in Redis for O(1) invalidation lookup
                try:
                    await self.redis_service.index_version_dependency(str(v_id), q_hash)
                except Exception as redis_idx_exc:
                    logger.warning(
                        "Redis version index write failed for v_id=%s: %s",
                        v_id,
                        redis_idx_exc,
                    )

            await db.flush()

            # Write-through to Tier 1 Redis hot cache
            cache_dict = self._record_to_dict(cached_rec)
            try:
                await self.redis_service.set_exact_cache(q_hash, cache_dict)
            except Exception as redis_wt_exc:
                logger.warning(
                    "Redis write-through failed after cache write (non-fatal): %s",
                    redis_wt_exc,
                )

            logger.info(
                "Cached answer persisted (id=%s, deps=%d) for '%s'",
                cached_rec.id,
                len(version_ids),
                canonical_query[:50],
            )
            return cached_rec

        except Exception as exc:
            logger.error(
                "Failed persisting cache entry for '%s': %s",
                canonical_query[:50],
                exc,
                exc_info=True,
            )
            return None

    def _record_to_dict(self, record: CachedAnswer) -> Dict[str, Any]:
        """Convert CachedAnswer ORM object to JSON-serializable dictionary."""
        return {
            "id": str(record.id),
            "query_hash": record.query_hash,
            "original_user_query": record.original_user_query,
            "canonical_query": record.canonical_query,
            "answer": record.answer,
            "citations": (
                record.citations if isinstance(record.citations, list) else []
            ),
            "tenant_id": record.tenant_id,
            "required_role": record.required_role,
            "is_active": record.is_active,
            "expires_at": (
                record.expires_at.isoformat() if record.expires_at else None
            ),
        }
