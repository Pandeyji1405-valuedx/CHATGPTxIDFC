"""
RBI Automatic Document Update Monitoring Service (Phase 8).

Responsibilities:
  - Check official RBI circular feeds/sources for new or updated regulatory documents.
  - Download and validate PDFs via PDFValidator.
  - Ingest new circulars via DocumentIngestionService.
  - Trigger version-aware cache invalidation via InvalidationService when circulars supersede earlier versions.
  - Log immutable audit events via AuditService.
  - Fully governed: never bypasses document validation or ingestion lifecycle controls.
"""

import hashlib
import logging
import uuid
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.document import DocumentUploadMetadata, DocumentUploadResponse
from app.services.cache.invalidation_service import CacheInvalidationService
from app.services.documents.ingestion_service import DocumentIngestionService
from app.services.pdf.validator import validate_pdf_bytes
from app.services.security.audit_service import AuditService

logger = logging.getLogger(__name__)


class RBIDocumentMonitorService:
    """
    Service for checking, downloading, and ingesting official RBI document updates.
    """

    def __init__(
        self,
        ingestion_service: Optional[DocumentIngestionService] = None,
        invalidation_service: Optional[CacheInvalidationService] = None,
    ):
        self.ingestion_service = ingestion_service or DocumentIngestionService()
        self.invalidation_service = invalidation_service or CacheInvalidationService()

    async def check_and_ingest_update(
        self,
        db: AsyncSession,
        pdf_bytes: bytes,
        filename: str,
        title: str,
        circular_number: str,
        topic: str = "Regulatory Compliance",
        published_date: Optional[date] = None,
        effective_date: Optional[date] = None,
        supersedes_version_id: Optional[uuid.UUID] = None,
        tenant_id: str = "idfc_bank",
        actor_id: Optional[uuid.UUID] = None,
    ) -> DocumentUploadResponse:
        """
        Process a candidate RBI document update from official monitoring feed.

        Flow:
          1. Validate PDF bytes
          2. Assemble metadata
          3. Ingest into PostgreSQL & ChromaDB
          4. If explicit supersession, invalidate dependent reusable cache entries
          5. Log audit log event

        Args:
            db: Async database session.
            pdf_bytes: Downloaded PDF file content.
            filename: PDF filename.
            title: Official circular title.
            circular_number: RBI circular number (e.g. RBI/2024-25/112).
            topic: Regulatory topic.
            published_date: Official publication date.
            effective_date: Coming-into-force date.
            supersedes_version_id: Optional explicit superseded version ID.
            tenant_id: Tenant identifier.
            actor_id: Optional user/system actor UUID.

        Returns:
            DocumentUploadResponse object.
        """
        # Step 1: Validate PDF bytes
        is_valid, error_msg = validate_pdf_bytes(pdf_bytes, filename)
        if not is_valid:
            await AuditService.log_event(
                db=db,
                action="document.monitor.validation_failed",
                resource_type="document",
                outcome="FAILURE",
                tenant_id=tenant_id,
                actor_id=actor_id,
                details={"filename": filename, "error": error_msg},
            )
            raise ValueError(f"Downloaded RBI PDF validation failed: {error_msg}")

        # Step 2: Assemble metadata
        doc_key = "rbi_" + circular_number.lower().replace("/", "_").replace("-", "_")
        metadata = DocumentUploadMetadata(
            title=title,
            document_key=doc_key,
            document_type="circular",
            circular_number=circular_number,
            topic=topic,
            source_name="Reserve Bank of India",
            source_url=f"https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx?Id={circular_number}",
            published_date=published_date or date.today(),
            effective_date=effective_date or date.today(),
            supersedes_version_id=supersedes_version_id,
        )

        # Step 3: Ingest via governed pipeline
        response = await self.ingestion_service.ingest_rbi_pdf(
            db=db,
            pdf_bytes=pdf_bytes,
            filename=filename,
            metadata=metadata,
        )

        # Step 4: If version supersedes an older version, invalidate cache dependencies
        if supersedes_version_id:
            invalidated_count = await self.invalidation_service.invalidate_version_dependencies(
                version_id=supersedes_version_id,
                db=db,
            )
            logger.info(
                "Monitor ingestion: Superseded version %s — invalidated %d cached answer(s).",
                supersedes_version_id,
                invalidated_count,
            )

        # Step 5: Audit log event
        await AuditService.log_event(
            db=db,
            action="document.monitor.ingest_success",
            resource_type="document_version",
            resource_id=str(response.version.id),
            outcome="SUCCESS",
            tenant_id=tenant_id,
            actor_id=actor_id,
            details={
                "document_id": str(response.document.id),
                "circular_number": circular_number,
                "chunks_indexed": response.chunks_indexed,
                "is_duplicate": response.is_duplicate,
            },
        )

        return response
