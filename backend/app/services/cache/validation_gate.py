"""
Phase 5 Cache Governance Validation Gate.

Enforces ALL BRD-mandated compliance rules before ANY cached regulatory
answer is served to an authenticated user.

Gate checklist (10 gates):
  1.  Expiry & System Active Status
  2.  Tenant isolation (candidate tenant == authenticated tenant)
  3.  Permissions / ACL (user role satisfies required_role)
  4.  Scope compatibility (reserved for future use, always passes currently)
  5.  Regulator compatibility (reserved for future use, always passes currently)
  6.  Document version freshness (ALL cited versions must be ACTIVE + COMPLETED)
  7.  Effective date (cited regulation must be currently effective)
  8.  Citation availability (citations must be non-empty and parseable)
  9.  Model/prompt policy compatibility (model_policy_version, reserved)
 10.  Cache active flag (is_active == True)

Core Rule: HIGH SEMANTIC SIMILARITY ALONE MUST NEVER PRODUCE A CACHE HIT.
"""

import logging
import uuid
from datetime import datetime, date, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentStatus, DocumentVersion, IngestionStatus
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


class CacheValidationGate:
    """
    Evaluates all BRD governance validation rules for candidate cached answers.
    """

    async def validate_candidate(
        self,
        candidate: Dict[str, Any],
        user: User,
        db: AsyncSession,
        tenant_id: str = "idfc_bank",
    ) -> Tuple[bool, str]:
        """
        Evaluate candidate against all 10 governance gates.

        Args:
            candidate:  Dictionary representation of the cached answer record.
            user:       Currently authenticated user (from JWT — never from client body).
            db:         Async SQLAlchemy session.
            tenant_id:  Authenticated tenant (from application context, not client input).

        Returns:
            Tuple of (is_approved, rejection_reason).
            is_approved == True means the candidate may be returned.
        """

        # ------------------------------------------------------------------ #
        # Gate 10: Cache Active Flag
        # ------------------------------------------------------------------ #
        if not candidate.get("is_active", True):
            return False, "Cache entry is_active=False; entry has been deactivated."

        # ------------------------------------------------------------------ #
        # Gate 1: Expiry
        # ------------------------------------------------------------------ #
        expires_at_raw = candidate.get("expires_at")
        if expires_at_raw:
            try:
                if isinstance(expires_at_raw, datetime):
                    exp_dt = expires_at_raw
                else:
                    exp_dt = datetime.fromisoformat(
                        str(expires_at_raw).replace("Z", "+00:00")
                    )
                now = datetime.now(timezone.utc)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt <= now:
                    return False, f"Cache entry expired at {exp_dt.isoformat()}."
            except Exception as parse_exc:
                logger.warning(
                    "Failed parsing cache expiry '%s': %s", expires_at_raw, parse_exc
                )
                return False, "Invalid cache expiry metadata; entry rejected."

        # ------------------------------------------------------------------ #
        # Gate 2: Tenant Isolation
        # ------------------------------------------------------------------ #
        candidate_tenant = candidate.get("tenant_id", "")
        if not candidate_tenant:
            return False, "Cache entry has no tenant_id; entry rejected."
        if candidate_tenant != tenant_id:
            return (
                False,
                f"Tenant mismatch: candidate tenant '{candidate_tenant}' != "
                f"authenticated tenant '{tenant_id}'.",
            )

        # ------------------------------------------------------------------ #
        # Gate 3: Permissions / ACL
        # ------------------------------------------------------------------ #
        required_role_str = (candidate.get("required_role") or "USER").upper().strip()
        if required_role_str == "ADMIN" and user.role != UserRole.ADMIN:
            return (
                False,
                f"User role '{user.role.value}' insufficient; "
                f"cached answer requires ADMIN access.",
            )

        # ------------------------------------------------------------------ #
        # Gate 4: Scope Compatibility (BRD reserved; always passes in Phase 5)
        # ------------------------------------------------------------------ #
        # scope metadata will be added in a later phase when multi-scope
        # regulatory data is available. No rejection here.

        # ------------------------------------------------------------------ #
        # Gate 5: Regulator Compatibility (BRD reserved; always passes in Phase 5)
        # ------------------------------------------------------------------ #
        # Regulator-level filtering will be layered in Phase 6+.

        # ------------------------------------------------------------------ #
        # Gate 8: Citation Availability
        # ------------------------------------------------------------------ #
        # Reusable answer must retain valid, parseable citations.
        citations = candidate.get("citations")
        if citations is None:
            return False, "Cache entry has no citations field; entry rejected."
        if isinstance(citations, str):
            try:
                import json as _json
                citations = _json.loads(citations)
            except Exception:
                return False, "Cache entry citations field is unparseable; entry rejected."
        if not isinstance(citations, list):
            return False, "Cache entry citations is not a list; entry rejected."
        # An empty citations list is only acceptable for "insufficient_evidence" responses;
        # for a reusable governed answer we require at least one citation.
        # If a cached answer has zero citations we conservatively reject it
        # because we cannot validate provenance.
        # NOTE: The write_through path only caches when citations are non-empty,
        # so this guard mainly catches data integrity failures.
        if len(citations) == 0:
            return (
                False,
                "Cache entry has no citations; cannot validate provenance.",
            )

        # ------------------------------------------------------------------ #
        # Gate 6 & 7: Document Version Freshness + Effective Date
        # ------------------------------------------------------------------ #
        version_ids: List[uuid.UUID] = []
        for c in citations:
            if not isinstance(c, dict):
                continue
            v_id_str = c.get("version_id")
            if v_id_str:
                try:
                    version_ids.append(uuid.UUID(str(v_id_str)))
                except (ValueError, AttributeError):
                    pass

        if version_ids:
            stmt = select(DocumentVersion).where(
                DocumentVersion.id.in_(version_ids)
            )
            result = await db.execute(stmt)
            versions = result.scalars().all()

            found_ids = {v.id for v in versions}
            missing = set(version_ids) - found_ids
            if missing:
                return (
                    False,
                    f"Cited document version(s) {missing} no longer exist in database.",
                )

            today = date.today()
            for v in versions:
                # Gate 6: Version must be ACTIVE
                if v.status != DocumentStatus.ACTIVE:
                    return (
                        False,
                        f"Cited document version {v.id} has status "
                        f"'{v.status.value}' (must be ACTIVE).",
                    )
                # Gate 6: Ingestion must be COMPLETED
                if v.ingestion_status != IngestionStatus.COMPLETED:
                    return (
                        False,
                        f"Cited document version {v.id} ingestion status is "
                        f"'{v.ingestion_status.value}' (must be COMPLETED).",
                    )
                # Gate 7: Regulation must be currently effective
                if v.effective_date and v.effective_date > today:
                    return (
                        False,
                        f"Cited regulation version {v.id} has effective_date "
                        f"{v.effective_date} which is in the future.",
                    )

        # ------------------------------------------------------------------ #
        # Gate 9: Model / Prompt Policy Compatibility (BRD reserved)
        # ------------------------------------------------------------------ #
        # model_policy_version metadata will be added when the TP LLM gateway
        # and versioned prompt templates are integrated. No rejection here.

        # ------------------------------------------------------------------ #
        # All gates passed
        # ------------------------------------------------------------------ #
        return True, "Approved"
