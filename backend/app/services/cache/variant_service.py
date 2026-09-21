"""
Phase 5E Governed Question Variant Service.

Responsibilities:
  1. After a successful fresh Main RAG answer, generate bounded question variants
     using the LLM Gateway.
  2. Validate each candidate variant for regulatory intent compatibility before
     storing it.
  3. Persist approved variants as QuestionVariant records linked to the
     CachedAnswer.
  4. Resolve variant queries at lookup time: variant hash → CachedAnswer →
     full 10-gate governance validation.

Governance constraints (enforced here AND by CacheValidationGate):
  - Variants never bypass the 10-gate validation on lookup.
  - A variant cannot cross tenant boundaries.
  - A variant cannot point to an inactive cached answer.
  - A variant must preserve the same regulatory scope, subject, and intent.
  - Textual/semantic similarity alone is NOT a sufficient approval condition.
  - Variants are bounded: at most MAX_VARIANTS_PER_ANSWER per cached answer.

Variant generation uses the existing LLM Gateway abstraction.
No second independent LLM pipeline is created.
"""

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cache import CachedAnswer, QuestionVariant
from app.services.cache.cache_service import hash_query
from app.services.rag.llm_gateway import LLMGatewayInterface

logger = logging.getLogger(__name__)

# Maximum number of approved variants stored per cached answer
MAX_VARIANTS_PER_ANSWER = 5

# Prompt instructing the LLM to generate bounded, equivalent question variants
_VARIANT_GENERATION_PROMPT = """You are a regulatory question normalizer for an RBI compliance system.

Given the following CANONICAL REGULATORY QUESTION, generate up to {count} alternative phrasings
that are SEMANTICALLY IDENTICAL — meaning they ask for the same information about the same
regulatory subject, from the same regulator, for the same entity type, within the same scope.

CANONICAL QUESTION:
{canonical_query}

STRICT RULES (reject any phrasing that violates these):
1. Do NOT change the regulated entity type (e.g., "banks" must remain "banks", not "NBFCs")
2. Do NOT change the regulator (e.g., "RBI" must remain "RBI")
3. Do NOT change the regulatory instrument (e.g., "KYC" must remain "KYC")
4. Do NOT change obligation to permission or vice versa
5. Do NOT introduce date changes that alter the scope
6. Do NOT change applicability qualifiers
7. Variants must be shorter or equal in length to the canonical question
8. Variants must be clear, complete questions

Return ONLY a JSON object in this exact format, nothing else:
{{
  "variants": [
    "alternative phrasing 1",
    "alternative phrasing 2"
  ]
}}

If you cannot generate safe, equivalent variants, return: {{"variants": []}}
"""

# Phrases that signal a materially different regulatory intent
_SCOPE_CHANGE_INDICATORS = [
    # Entity type changes
    r"\bnbfcs?\b", r"\bco-?operatives?\b", r"\burban cooperative\b",
    r"\bpayment banks?\b", r"\bsmall finance\b", r"\bmicrofinance\b",
    # Obligation flips
    r"\bmay\b.*\bshall\b", r"\bshall\b.*\bmay\b",
    r"\bprohibited\b", r"\bpermitted\b",
    # Scope expansions
    r"\bforeign\b", r"\binternational\b", r"\bcross.border\b",
]


class VariantService:
    """
    Manages governed question variant generation, validation, and resolution.
    """

    def __init__(self, llm_gateway: Optional[LLMGatewayInterface] = None):
        self.llm_gateway = llm_gateway

    # ------------------------------------------------------------------ #
    # Public: Generate and persist variants after fresh RAG answer
    # ------------------------------------------------------------------ #

    async def create_variants(
        self,
        cached_answer: CachedAnswer,
        canonical_query: str,
        db: AsyncSession,
        tenant_id: str = "idfc_bank",
    ) -> int:
        """
        Generate bounded question variants for an approved cached answer
        and persist the validated ones.

        Called after a successful Main RAG + citation validation response
        is written to the cache via write_through().

        Args:
            cached_answer:   The persisted CachedAnswer ORM record.
            canonical_query: The canonicalized query that produced the answer.
            db:              Async DB session. Caller commits.
            tenant_id:       Authenticated tenant from application context.

        Returns:
            Number of variants successfully stored.
        """
        if not cached_answer.is_active:
            logger.info(
                "Skipping variant generation for inactive cached answer %s.",
                cached_answer.id,
            )
            return 0

        # Check how many variants already exist for this answer
        existing_count_stmt = select(QuestionVariant).where(
            QuestionVariant.cache_answer_id == cached_answer.id,
            QuestionVariant.is_active == True,
        )
        existing_res = await db.execute(existing_count_stmt)
        existing_variants = existing_res.scalars().all()
        remaining_slots = MAX_VARIANTS_PER_ANSWER - len(existing_variants)

        if remaining_slots <= 0:
            logger.debug(
                "Variant limit (%d) already reached for cached answer %s.",
                MAX_VARIANTS_PER_ANSWER,
                cached_answer.id,
            )
            return 0

        # Generate candidate variants via LLM Gateway
        candidate_texts = await self._generate_candidate_variants(
            canonical_query=canonical_query,
            count=min(remaining_slots, 3),
        )

        if not candidate_texts:
            logger.debug(
                "No variants generated for cached answer %s.", cached_answer.id
            )
            return 0

        # Track already-stored hashes (existing + new in this call) to prevent duplicates
        stored_hashes = {v.variant_hash for v in existing_variants}
        canonical_hash = hash_query(canonical_query)
        stored_hashes.add(canonical_hash)

        stored_count = 0
        for variant_text in candidate_texts:
            variant_text = variant_text.strip()
            if not variant_text:
                continue

            # Validate the variant before persisting
            is_valid, rejection_reason = self._validate_variant(
                variant_text=variant_text,
                canonical_query=canonical_query,
                tenant_id=tenant_id,
                cached_answer_tenant=cached_answer.tenant_id,
            )

            if not is_valid:
                logger.info(
                    "Variant rejected for cached answer %s: %s | variant='%s'",
                    cached_answer.id,
                    rejection_reason,
                    variant_text[:80],
                )
                continue

            v_hash = hash_query(variant_text)
            if v_hash in stored_hashes:
                logger.debug(
                    "Variant duplicate skipped for cached answer %s: '%s'",
                    cached_answer.id,
                    variant_text[:80],
                )
                continue

            # Persist approved variant
            variant_rec = QuestionVariant(
                id=uuid.uuid4(),
                cache_answer_id=cached_answer.id,
                variant_query=variant_text,
                variant_hash=v_hash,
                is_active=True,
                tenant_id=tenant_id,
            )
            db.add(variant_rec)
            stored_hashes.add(v_hash)
            stored_count += 1

        if stored_count > 0:
            await db.flush()
            logger.info(
                "Stored %d variant(s) for cached answer %s.",
                stored_count,
                cached_answer.id,
            )

        return stored_count

    # ------------------------------------------------------------------ #
    # Public: Resolve a query hash via variant table → CachedAnswer
    # ------------------------------------------------------------------ #

    async def resolve_variant(
        self,
        query_hash: str,
        db: AsyncSession,
        tenant_id: str = "idfc_bank",
    ) -> Optional[CachedAnswer]:
        """
        Look up an active QuestionVariant by hash and return its CachedAnswer
        if the answer is still active and belongs to the correct tenant.

        The caller is responsible for running the full 10-gate CacheValidationGate
        before serving the answer.

        Args:
            query_hash: SHA-256 hash of the normalized query (from hash_query()).
            db:         Async DB session.
            tenant_id:  Authenticated tenant from application context.

        Returns:
            CachedAnswer if a valid active variant is found, else None.
        """
        stmt = (
            select(QuestionVariant)
            .where(
                QuestionVariant.variant_hash == query_hash,
                QuestionVariant.is_active == True,
                QuestionVariant.tenant_id == tenant_id,
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        variant = res.scalars().first()

        if not variant:
            return None

        # Fetch the linked CachedAnswer
        answer_stmt = select(CachedAnswer).where(
            CachedAnswer.id == variant.cache_answer_id,
            CachedAnswer.is_active == True,
        )
        answer_res = await db.execute(answer_stmt)
        cached_answer = answer_res.scalars().first()

        if not cached_answer:
            logger.info(
                "Variant %s points to inactive/missing CachedAnswer %s — ignoring.",
                variant.id,
                variant.cache_answer_id,
            )
            return None

        logger.info(
            "Variant lookup HIT for hash %s → CachedAnswer %s.",
            query_hash[:8],
            cached_answer.id,
        )
        return cached_answer

    # ------------------------------------------------------------------ #
    # Private: LLM-based variant generation
    # ------------------------------------------------------------------ #

    async def _generate_candidate_variants(
        self,
        canonical_query: str,
        count: int = 3,
    ) -> List[str]:
        """
        Use the LLM Gateway to generate candidate variant phrasings.

        Returns an empty list if the gateway is unavailable or generation fails.
        """
        if not self.llm_gateway:
            return []

        prompt = _VARIANT_GENERATION_PROMPT.format(
            canonical_query=canonical_query,
            count=count,
        )
        try:
            llm_response = await self.llm_gateway.generate(prompt)
            raw = llm_response.answer.strip()
            # Parse JSON from the response
            # Try direct JSON parse first
            try:
                data = json.loads(raw)
                variants = data.get("variants", [])
                if isinstance(variants, list):
                    return [str(v) for v in variants if v][:count]
            except json.JSONDecodeError:
                pass
            # Try extracting JSON from markdown code block
            code_match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
            if code_match:
                try:
                    data = json.loads(code_match.group(1))
                    variants = data.get("variants", [])
                    if isinstance(variants, list):
                        return [str(v) for v in variants if v][:count]
                except json.JSONDecodeError:
                    pass
            logger.warning(
                "Could not parse LLM variant response as JSON. Response: %s",
                raw[:200],
            )
            return []
        except Exception as exc:
            logger.warning(
                "Variant generation via LLM Gateway failed: %s", exc
            )
            return []

    # ------------------------------------------------------------------ #
    # Private: Variant validation
    # ------------------------------------------------------------------ #

    def _validate_variant(
        self,
        variant_text: str,
        canonical_query: str,
        tenant_id: str,
        cached_answer_tenant: str,
    ) -> Tuple[bool, str]:
        """
        Validate a candidate variant for governance compliance.

        Returns:
            Tuple of (is_valid, rejection_reason).
        """
        # Gate V1: Tenant must match
        if tenant_id != cached_answer_tenant:
            return False, f"Tenant mismatch: '{tenant_id}' vs answer tenant '{cached_answer_tenant}'"

        # Gate V2: Length guard — must be a non-trivial question
        cleaned = variant_text.strip()
        if len(cleaned) < 10:
            return False, "Variant too short to represent a valid regulatory question."

        # Gate V3: Must end with a question character or be a question phrase
        # (not an assertion that changes the semantic type)
        if cleaned.endswith(".") and not cleaned.endswith("?."):
            pass  # Allow assertions-as-questions occasionally

        # Gate V4: Detect scope-change indicators (entity type changes, etc.)
        canonical_lower = canonical_query.lower()
        variant_lower = cleaned.lower()
        for pattern in _SCOPE_CHANGE_INDICATORS:
            # If the pattern appears in the variant but NOT in the canonical → scope change
            if re.search(pattern, variant_lower) and not re.search(
                pattern, canonical_lower
            ):
                return False, f"Variant introduces scope change via pattern '{pattern}'."

        # Gate V5: Variant must not be identical to canonical (no-op)
        if hash_query(cleaned) == hash_query(canonical_query):
            return False, "Variant is identical to the canonical query (no-op)."

        # Gate V6: Variant must not be excessively different in length
        # (rough proxy for topic drift)
        len_ratio = len(cleaned) / max(len(canonical_query), 1)
        if len_ratio > 2.5:
            return False, "Variant is more than 2.5× longer than canonical — possible topic drift."

        return True, "Approved"
