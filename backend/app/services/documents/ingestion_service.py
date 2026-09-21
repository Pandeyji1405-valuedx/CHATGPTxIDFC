"""
Document Ingestion Orchestration Service (Phase 3).

Coordinates the end-to-end ingestion pipeline:
  1. PDF validation (signature, size, readability)
  2. SHA-256 fingerprinting & duplicate detection (idempotent ingestion)
  3. Local filesystem storage
  4. PostgreSQL record management (documents, document_versions)
  5. Page-by-page text extraction (PyMuPDF)
  6. Deterministic text cleaning
  7. Paragraph-aware chunking with deterministic IDs
  8. Vector embedding generation (Nomic Embed v1.5 with 'search_document: ' prefix)
  9. ChromaDB vector indexing (rbi_documents collection)
  10. Atomic state update in PostgreSQL (status=ACTIVE, ingestion_status=COMPLETED)
"""

import asyncio
import hashlib
import logging
import re
import uuid
from typing import Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.chunk import DocumentChunk
from app.models.document import Document, DocumentStatus, DocumentVersion, IngestionStatus
from app.schemas.document import (
    DocumentResponse,
    DocumentUploadMetadata,
    DocumentUploadResponse,
    DocumentVersionResponse,
)
from app.services.chunking.text_chunker import chunk_pages
from app.services.documents.document_service import (
    get_document_by_id,
    get_document_by_key,
    get_document_version_by_id,
    get_version_by_hash,
    list_document_versions,
)
from app.services.documents.storage import save_pdf_file
from app.services.embeddings.base import BaseEmbeddingService
from app.services.embeddings.nomic_service import NomicEmbeddingService
from app.services.pdf.cleaner import clean_regulatory_text
from app.services.pdf.extractor import ExtractedPage, extract_pdf_pages
from app.services.pdf.validator import validate_pdf_bytes
from app.services.vector_db.chroma_service import ChromaDBService

logger = logging.getLogger(__name__)
settings = get_settings()


def _slugify(text: str) -> str:
    """Generate a clean URL/key slug from title or circular number."""
    clean = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", clean)[:200] or f"doc-{uuid.uuid4().hex[:8]}"


from app.db.session import AsyncSessionLocal
from app.services.cache.invalidation_service import CacheInvalidationService


class DocumentIngestionService:
    """
    Orchestrates the ingestion of RBI regulatory PDFs into PostgreSQL and ChromaDB.
    """

    def __init__(
        self,
        embedding_service: Optional[BaseEmbeddingService] = None,
        chroma_service: Optional[ChromaDBService] = None,
        invalidation_service: Optional[CacheInvalidationService] = None,
        storage_dir: Optional[str] = None,
        session_factory: Optional[Callable[[], AsyncSession]] = None,
    ):
        self.embedding_service = embedding_service or NomicEmbeddingService()
        self.chroma_service = chroma_service or ChromaDBService()
        self.invalidation_service = invalidation_service or CacheInvalidationService()
        self.storage_dir = storage_dir or settings.STORAGE_DIR
        self.session_factory = session_factory or AsyncSessionLocal

    async def prepare_document_upload(
        self,
        db: AsyncSession,
        pdf_bytes: bytes,
        filename: str,
        metadata: Optional[DocumentUploadMetadata] = None,
    ) -> tuple[Document, DocumentVersion, bool, bool]:
        """
        Validate PDF and persist Document and DocumentVersion metadata (PROCESSING).

        Returns:
            Tuple of (Document, DocumentVersion, is_duplicate, is_already_completed)
        """
        meta = metadata or DocumentUploadMetadata()

        # 1. PDF Validation
        is_valid, validation_err = validate_pdf_bytes(
            content=pdf_bytes,
            filename=filename,
            max_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
        )
        if not is_valid:
            raise ValueError(f"PDF Validation failed: {validation_err}")

        # 2. SHA-256 Fingerprint & Idempotency Check
        file_hash = hashlib.sha256(pdf_bytes).hexdigest()
        existing_version = await get_version_by_hash(db, file_hash)

        if existing_version is not None:
            doc = await get_document_by_id(db, existing_version.document_id)
            if existing_version.ingestion_status == IngestionStatus.COMPLETED:
                logger.info("Idempotent hit: file_hash=%s already ingested (COMPLETED).", file_hash)
                return (doc, existing_version, True, True)
            elif existing_version.ingestion_status == IngestionStatus.PROCESSING:
                logger.info("Idempotent hit: file_hash=%s is already PROCESSING.", file_hash)
                return (doc, existing_version, True, True)
            elif existing_version.ingestion_status == IngestionStatus.FAILED:
                logger.info("Idempotent retry: file_hash=%s previously FAILED. Resetting version %s for retry.", file_hash, existing_version.id)
                storage_path = save_pdf_file(
                    content=pdf_bytes,
                    file_hash=file_hash,
                    original_filename=filename,
                    base_dir=self.storage_dir,
                )
                existing_version.storage_path = storage_path
                existing_version.file_size_bytes = len(pdf_bytes)
                existing_version.ingestion_status = IngestionStatus.PROCESSING
                existing_version.status = DocumentStatus.INACTIVE
                existing_version.error_message = None
                existing_version.page_count = 0
                existing_version.chunk_count = 0
                await db.commit()
                reloaded_doc = await get_document_by_id(db, doc.id)
                reloaded_ver = await get_document_version_by_id(db, existing_version.id)
                return (reloaded_doc or doc, reloaded_ver or existing_version, True, False)

        # 3. Local Filesystem Storage
        storage_path = save_pdf_file(
            content=pdf_bytes,
            file_hash=file_hash,
            original_filename=filename,
            base_dir=self.storage_dir,
        )

        # 4. Resolve or Create Parent Document in PostgreSQL
        doc_title = (meta.title or filename.replace(".pdf", "").replace("_", " ").strip()).title()
        doc_key = meta.document_key or _slugify(meta.circular_number or doc_title)

        document = await get_document_by_key(db, doc_key)
        if document is None:
            document = Document(
                document_key=doc_key,
                title=doc_title,
                document_type=meta.document_type or "circular",
                circular_number=meta.circular_number,
                topic=meta.topic,
                source_name=meta.source_name or "Reserve Bank of India",
                source_url=meta.source_url,
            )
            db.add(document)
            await db.flush()
            await db.refresh(document)
        else:
            if meta.circular_number:
                document.circular_number = meta.circular_number
            if meta.topic:
                document.topic = meta.topic
            if meta.source_url:
                document.source_url = meta.source_url

        # Determine version number
        if meta.version_number:
            version_num = meta.version_number
        else:
            existing_versions = await list_document_versions(db, document.id)
            max_ver = max([v.version_number for v in existing_versions], default=0)
            version_num = max_ver + 1

        # 5. Create DocumentVersion in PostgreSQL (status=INACTIVE, ingestion_status=PROCESSING)
        version = DocumentVersion(
            document_id=document.id,
            version_number=version_num,
            published_date=meta.published_date,
            effective_date=meta.effective_date,
            status=DocumentStatus.INACTIVE,
            file_name=filename,
            file_hash=file_hash,
            storage_path=storage_path,
            file_size_bytes=len(pdf_bytes),
            page_count=0,
            chunk_count=0,
            ingestion_status=IngestionStatus.PROCESSING,
        )
        db.add(version)
        await db.commit()

        reloaded_doc = await get_document_by_id(db, document.id)
        reloaded_ver = await get_document_version_by_id(db, version.id)
        return (reloaded_doc or document, reloaded_ver or version, False, False)

    def _execute_cpu_bound_ingestion(
        self,
        storage_path: str,
        document_title: str,
        circular_number: Optional[str],
        topic: Optional[str],
        document_type: str,
        version_number: int,
        file_hash: str,
        doc_id: uuid.UUID,
        ver_id: uuid.UUID,
    ) -> tuple[int, int, list, list]:
        """
        Synchronous CPU-heavy extraction, text cleaning, chunking, Nomic embedding generation,
        and ChromaDB vector indexing. Runs in a separate worker thread via asyncio.to_thread
        to keep the FastAPI main event loop 100% unblocked and responsive.
        """
        # Ensure ChromaDB chunks from any previous partial attempt are purged
        try:
            self.chroma_service.delete_version_chunks(ver_id)
        except Exception as cleanup_exc:
            logger.debug("ChromaDB pre-indexing cleanup notice for ver_id %s: %s", ver_id, cleanup_exc)

        with open(storage_path, "rb") as f:
            pdf_bytes = f.read()

        extracted_pages = extract_pdf_pages(pdf_bytes)
        page_count = len(extracted_pages)

        cleaned_pages = [
            ExtractedPage(
                page_number=p.page_number,
                text=clean_regulatory_text(p.text),
                char_count=len(clean_regulatory_text(p.text)),
            )
            for p in extracted_pages
        ]

        doc_meta_dict = {
            "title": document_title,
            "circular_number": circular_number or "",
            "topic": topic or "",
            "document_type": document_type,
            "version_number": version_number,
            "file_hash": file_hash,
            "status": DocumentStatus.ACTIVE.value,
        }

        chunks = chunk_pages(
            pages=cleaned_pages,
            document_id=doc_id,
            version_id=ver_id,
            doc_metadata=doc_meta_dict,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

        indexed_count = 0
        embeddings: list = []
        if chunks:
            chunk_texts = [c.text for c in chunks]
            embeddings = self.embedding_service.embed_documents(chunk_texts)
            indexed_count = self.chroma_service.index_chunks(
                chunks=chunks,
                embeddings=embeddings,
            )

        return page_count, indexed_count, chunks, embeddings

    async def process_version_background(
        self,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        metadata: Optional[DocumentUploadMetadata] = None,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """
        Execute heavy extraction, chunking, Nomic embedding, and ChromaDB indexing in the background.
        If db is provided, uses that session; otherwise opens an independent session via self.session_factory.
        """
        if db is not None:
            await self._run_background_pipeline(db, document_id, version_id, metadata)
        else:
            async with self.session_factory() as new_db:
                await self._run_background_pipeline(new_db, document_id, version_id, metadata)

    async def _run_background_pipeline(
        self,
        db: AsyncSession,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        metadata: Optional[DocumentUploadMetadata] = None,
    ) -> None:
        """Helper executing background ingestion pipeline on a given AsyncSession."""
        meta = metadata or DocumentUploadMetadata()

        version = await get_document_version_by_id(db, version_id)
        document = await get_document_by_id(db, document_id)

        if version is None or document is None:
            logger.error("Background ingestion error: version %s or document %s not found.", version_id, document_id)
            return

        if version.ingestion_status == IngestionStatus.COMPLETED:
            logger.info("Background ingestion skipped: version %s already COMPLETED.", version_id)
            return

        try:
            # Offload heavy CPU-bound extraction, chunking, embedding generation, and ChromaDB vector indexing
            # off the asyncio event loop to a worker thread via asyncio.to_thread
            page_count, indexed_count, chunks, embeddings = await asyncio.to_thread(
                self._execute_cpu_bound_ingestion,
                version.storage_path,
                document.title,
                document.circular_number,
                document.topic,
                document.document_type,
                version.version_number,
                version.file_hash,
                document.id,
                version.id,
            )

            version.page_count = page_count
            version.chunk_count = indexed_count

            if chunks:
                await self._persist_chunks_to_postgres(db, document, version, chunks)

            # Explicit supersession handling
            if meta.supersedes_version_id:
                old_ver = await get_document_version_by_id(db, meta.supersedes_version_id)
                if old_ver and old_ver.document_id == document.id:
                    old_ver.status = DocumentStatus.SUPERSEDED
                    old_ver.superseded_by_id = version.id
                    await self.invalidation_service.invalidate_version_dependencies(old_ver.id, db)
                    logger.info("Version %s explicitly superseded version %s", version.id, old_ver.id)

            # Mark version ACTIVE and COMPLETED
            version.status = DocumentStatus.ACTIVE
            version.ingestion_status = IngestionStatus.COMPLETED
            version.error_message = None
            await db.commit()

            logger.info(
                "Background ingestion completed successfully for doc_id=%s, ver_id=%s, chunks=%d",
                document.id,
                version.id,
                indexed_count,
            )

        except Exception as exc:
            logger.error("Background ingestion failed for version %s: %s", version.id, exc, exc_info=True)
            try:
                self.chroma_service.delete_version_chunks(version.id)
            except Exception as cleanup_exc:
                logger.warning("Failed to cleanup ChromaDB chunks on failure: %s", cleanup_exc)

            version.status = DocumentStatus.INACTIVE
            version.ingestion_status = IngestionStatus.FAILED
            version.error_message = str(exc)[:2048]
            await db.commit()

    async def ingest_rbi_pdf(
        self,
        db: AsyncSession,
        pdf_bytes: bytes,
        filename: str,
        metadata: Optional[DocumentUploadMetadata] = None,
    ) -> DocumentUploadResponse:
        """
        Synchronously prepare upload and execute background ingestion (for CLI/tests/monitor).
        """
        document, version, is_duplicate, is_already_completed = await self.prepare_document_upload(
            db=db,
            pdf_bytes=pdf_bytes,
            filename=filename,
            metadata=metadata,
        )

        if is_already_completed:
            return DocumentUploadResponse(
                document=DocumentResponse.model_validate(document),
                version=DocumentVersionResponse.model_validate(version),
                message="Document version already exists and is fully indexed (idempotent upload).",
                chunks_indexed=version.chunk_count,
                is_duplicate=True,
            )

        # Synchronously execute background pipeline using current session db
        try:
            await self.process_version_background(document.id, version.id, metadata, db=db)
        except Exception:
            pass

        # Reload committed version state
        reloaded_doc = await get_document_by_id(db, document.id)
        reloaded_ver = await get_document_version_by_id(db, version.id)

        if reloaded_ver and reloaded_ver.ingestion_status == IngestionStatus.FAILED:
            raise RuntimeError(f"Document ingestion failed: {reloaded_ver.error_message}")

        return DocumentUploadResponse(
            document=DocumentResponse.model_validate(reloaded_doc),
            version=DocumentVersionResponse.model_validate(reloaded_ver),
            message="RBI regulatory document ingested and indexed successfully.",
            chunks_indexed=reloaded_ver.chunk_count if reloaded_ver else 0,
            is_duplicate=is_duplicate,
        )

    async def _persist_chunks_to_postgres(
        self,
        db: AsyncSession,
        document: Document,
        version: DocumentVersion,
        chunks: list,
    ) -> int:
        """
        Idempotently persist chunk records into the PostgreSQL document_chunks table.

        This method supports the sparse (lexical) FTS retrieval branch.  Each chunk
        already indexed in ChromaDB is mirrored here so PostgreSQL FTS queries can
        run without touching the vector store.

        Idempotency: existing chunk_ids are skipped (SELECT first, INSERT if absent).

        Args:
            db:       Async database session.
            document: Parent Document ORM instance.
            version:  Parent DocumentVersion ORM instance.
            chunks:   List of DocumentChunk dataclasses from the chunking pipeline.

        Returns:
            Number of new rows inserted.
        """
        from sqlalchemy import select

        inserted = 0
        for chunk in chunks:
            # Check if already exists (idempotent for re-ingestion)
            stmt = select(DocumentChunk.id).where(
                DocumentChunk.chunk_id == chunk.chunk_id
            )
            existing = await db.execute(stmt)
            if existing.scalars().first() is not None:
                continue

            meta = chunk.metadata
            db_chunk = DocumentChunk(
                document_id=document.id,
                version_id=version.id,
                chunk_id=chunk.chunk_id,
                content=chunk.text,
                page_number=chunk.page_number,
                section=meta.get("section") or None,
                topic=meta.get("topic") or None,
                circular_number=meta.get("circular_number") or None,
                status=DocumentStatus.ACTIVE,
            )
            db.add(db_chunk)
            inserted += 1

        if inserted:
            await db.flush()
            logger.info(
                "Persisted %d new chunk records to PostgreSQL for version_id=%s",
                inserted,
                version.id,
            )
        return inserted
