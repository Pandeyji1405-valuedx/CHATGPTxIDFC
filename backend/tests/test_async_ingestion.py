"""
Tests for Async Background Document Ingestion Workflow.

Covers:
  1. POST /api/v1/documents/upload returns HTTP 202 Accepted immediately.
  2. DocumentVersion initial ingestion_status is PROCESSING and status is INACTIVE.
  3. Background worker executes extraction, Nomic embedding, and ChromaDB indexing.
  4. Final state transitions to COMPLETED / ACTIVE with page & chunk counts populated.
  5. Background failures transition to FAILED / INACTIVE with safe error_message stored.
  6. Independent DB session usage in background task.
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentStatus, IngestionStatus
from app.schemas.document import DocumentUploadMetadata
from app.services.documents.document_service import get_document_by_key, get_document_version_by_id, list_document_versions
from app.services.documents.ingestion_service import DocumentIngestionService
from app.services.embeddings.mock_service import MockEmbeddingService
from app.services.vector_db.chroma_service import ChromaDBService
from tests.conftest import create_sample_pdf_bytes


@pytest.mark.asyncio
async def test_api_upload_returns_202_accepted_immediately(admin_client: AsyncClient):
    """Test that POST /api/v1/documents/upload returns 202 Accepted immediately with status PROCESSING."""
    pdf_bytes = create_sample_pdf_bytes(["RBI Circular on Async Upload Testing."])
    files = {"file": ("async_test_01.pdf", pdf_bytes, "application/pdf")}
    data = {
        "title": "Async Upload Test Document",
        "document_key": "async-upload-test-01",
        "topic": "Compliance",
    }

    response = await admin_client.post(
        "/api/v1/documents/upload",
        files=files,
        data=data,
    )
    assert response.status_code == 202
    body = response.json()
    assert body["version"]["ingestion_status"] == "PROCESSING"
    assert body["version"]["status"] == "INACTIVE"
    assert "accepted" in body["message"].lower() or "background" in body["message"].lower()


@pytest.mark.asyncio
async def test_prepare_upload_and_background_processing(test_session_factory, tmp_path):
    """Test prepare_document_upload and background processing transition to COMPLETED."""
    embedder = MockEmbeddingService(dimension=768)
    chroma = ChromaDBService(in_memory=True, collection_name=f"test_async_{uuid.uuid4().hex[:8]}")
    service = DocumentIngestionService(
        embedding_service=embedder,
        chroma_service=chroma,
        storage_dir=str(tmp_path),
        session_factory=test_session_factory,
    )

    pdf_bytes = create_sample_pdf_bytes([
        "Section 1: RBI Prudential Norms on Income Recognition.",
        "Section 2: Asset Classification and Provisioning Pertaining to Advances.",
    ])

    metadata = DocumentUploadMetadata(
        title="Prudential Norms 2024",
        document_key="prudential-norms-2024",
        topic="Prudential Norms",
    )

    # Step 1: Prepare upload synchronously (request phase)
    async with test_session_factory() as session:
        doc, ver, is_dup, is_done = await service.prepare_document_upload(
            db=session,
            pdf_bytes=pdf_bytes,
            filename="prudential_norms_2024.pdf",
            metadata=metadata,
        )
        assert ver.ingestion_status == IngestionStatus.PROCESSING
        assert ver.status == DocumentStatus.INACTIVE
        assert is_dup is False
        doc_id = doc.id
        ver_id = ver.id

    # Step 2: Background processing execution
    async with test_session_factory() as session:
        await service.process_version_background(doc_id, ver_id, metadata, db=session)

    # Step 3: Verify final state in independent DB session
    async with test_session_factory() as session:
        reloaded_ver = await get_document_version_by_id(session, ver_id)
        assert reloaded_ver is not None
        assert reloaded_ver.ingestion_status == IngestionStatus.COMPLETED
        assert reloaded_ver.status == DocumentStatus.ACTIVE
        assert reloaded_ver.page_count == 2
        assert reloaded_ver.chunk_count == 2
        assert reloaded_ver.error_message is None


@pytest.mark.asyncio
async def test_background_processing_failure_handling(test_session_factory, tmp_path):
    """Test that background ingestion failure sets ingestion_status=FAILED and status=INACTIVE."""
    class FailingChromaService(ChromaDBService):
        def index_chunks(self, chunks, embeddings):
            raise RuntimeError("ChromaDB index failure simulation.")

    embedder = MockEmbeddingService(dimension=768)
    chroma = FailingChromaService(in_memory=True, collection_name=f"test_fail_{uuid.uuid4().hex[:8]}")
    service = DocumentIngestionService(
        embedding_service=embedder,
        chroma_service=chroma,
        storage_dir=str(tmp_path),
        session_factory=test_session_factory,
    )

    pdf_bytes = create_sample_pdf_bytes(["Failing background upload text."])

    metadata = DocumentUploadMetadata(
        title="Failing Document",
        document_key="failing-doc-key",
    )

    # Prepare upload
    async with test_session_factory() as session:
        doc, ver, _, _ = await service.prepare_document_upload(
            db=session,
            pdf_bytes=pdf_bytes,
            filename="failing_doc.pdf",
            metadata=metadata,
        )
        ver_id = ver.id

    # Execute background processing (catches exception internally)
    async with test_session_factory() as session:
        await service.process_version_background(doc.id, ver_id, metadata, db=session)

    # Verify failure state
    async with test_session_factory() as session:
        reloaded_ver = await get_document_version_by_id(session, ver_id)
        assert reloaded_ver is not None
        assert reloaded_ver.ingestion_status == IngestionStatus.FAILED
        assert reloaded_ver.status == DocumentStatus.INACTIVE
        assert reloaded_ver.error_message is not None
        assert "ChromaDB index failure" in reloaded_ver.error_message


@pytest.mark.asyncio
async def test_idempotency_completed_same_hash(test_session_factory, tmp_path):
    """Same file_hash with COMPLETED status returns duplicate without re-indexing or creating new version."""
    embedder = MockEmbeddingService(dimension=768)
    chroma = ChromaDBService(in_memory=True, collection_name=f"test_comp_{uuid.uuid4().hex[:8]}")
    service = DocumentIngestionService(
        embedding_service=embedder,
        chroma_service=chroma,
        storage_dir=str(tmp_path),
        session_factory=test_session_factory,
    )
    pdf_bytes = create_sample_pdf_bytes(["Completed document content."])
    meta = DocumentUploadMetadata(title="Completed Doc", document_key="completed-doc-key")

    # Ingest once synchronously
    async with test_session_factory() as session:
        resp1 = await service.ingest_rbi_pdf(session, pdf_bytes, "comp.pdf", meta)
        assert resp1.version.ingestion_status == IngestionStatus.COMPLETED

    # Prepare upload second time with same pdf_bytes
    async with test_session_factory() as session:
        doc2, ver2, is_dup, is_done = await service.prepare_document_upload(session, pdf_bytes, "comp.pdf", meta)
        assert is_dup is True
        assert is_done is True
        assert ver2.id == resp1.version.id
        assert ver2.version_number == 1


@pytest.mark.asyncio
async def test_idempotency_processing_same_hash(test_session_factory, tmp_path):
    """Same file_hash with PROCESSING status returns is_already_completed=True to prevent duplicate work."""
    service = DocumentIngestionService(
        storage_dir=str(tmp_path),
        session_factory=test_session_factory,
    )
    pdf_bytes = create_sample_pdf_bytes(["In-flight processing content."])
    meta = DocumentUploadMetadata(title="Processing Doc", document_key="processing-doc-key")

    async with test_session_factory() as session:
        doc1, ver1, _, _ = await service.prepare_document_upload(session, pdf_bytes, "proc.pdf", meta)
        assert ver1.ingestion_status == IngestionStatus.PROCESSING

    # Upload same file again while first is still PROCESSING
    async with test_session_factory() as session:
        doc2, ver2, is_dup, is_done = await service.prepare_document_upload(session, pdf_bytes, "proc.pdf", meta)
        assert is_dup is True
        assert is_done is True
        assert ver2.id == ver1.id


@pytest.mark.asyncio
async def test_idempotency_failed_retry_same_hash(test_session_factory, tmp_path):
    """Same file_hash with FAILED status resets existing version for retry without creating a duplicate version."""
    class FailingChromaService(ChromaDBService):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.should_fail = True

        def index_chunks(self, chunks, embeddings):
            if self.should_fail:
                raise RuntimeError("Simulated failure")
            return super().index_chunks(chunks, embeddings)

    embedder = MockEmbeddingService(dimension=768)
    chroma = FailingChromaService(in_memory=True, collection_name=f"test_retry_{uuid.uuid4().hex[:8]}")
    service = DocumentIngestionService(
        embedding_service=embedder,
        chroma_service=chroma,
        storage_dir=str(tmp_path),
        session_factory=test_session_factory,
    )
    pdf_bytes = create_sample_pdf_bytes(["Retry document content."])
    meta = DocumentUploadMetadata(title="Retry Doc", document_key="retry-doc-key")

    # Upload 1: Fail ingestion
    async with test_session_factory() as session:
        doc1, ver1, _, _ = await service.prepare_document_upload(session, pdf_bytes, "retry.pdf", meta)
        ver_id = ver1.id
        await service.process_version_background(doc1.id, ver_id, meta, db=session)

    async with test_session_factory() as session:
        ver_after_fail = await get_document_version_by_id(session, ver_id)
        assert ver_after_fail.ingestion_status == IngestionStatus.FAILED

    # Upload 2: Retry with same pdf_bytes
    chroma.should_fail = False  # Enable success on retry
    async with test_session_factory() as session:
        doc2, ver2, is_dup, is_done = await service.prepare_document_upload(session, pdf_bytes, "retry.pdf", meta)
        assert is_dup is True
        assert is_done is False
        assert ver2.id == ver_id  # Reuses existing version ID
        assert ver2.ingestion_status == IngestionStatus.PROCESSING
        assert ver2.version_number == 1

        # Execute retry background processing
        await service.process_version_background(doc2.id, ver2.id, meta, db=session)

    # Verify retry eventually succeeded
    async with test_session_factory() as session:
        ver_after_retry = await get_document_version_by_id(session, ver_id)
        assert ver_after_retry.ingestion_status == IngestionStatus.COMPLETED
        assert ver_after_retry.status == DocumentStatus.ACTIVE
        assert ver_after_retry.error_message is None
        # Verify version count remains 1
        versions = await list_document_versions(session, doc1.id)
        assert len(versions) == 1
        assert versions[0].version_number == 1


@pytest.mark.asyncio
async def test_new_hash_version_sequence_preserved(test_session_factory, tmp_path):
    """Uploading a new file_hash for an existing document increments version_number correctly."""
    embedder = MockEmbeddingService(dimension=768)
    chroma = ChromaDBService(in_memory=True, collection_name=f"test_seq_{uuid.uuid4().hex[:8]}")
    service = DocumentIngestionService(
        embedding_service=embedder,
        chroma_service=chroma,
        storage_dir=str(tmp_path),
        session_factory=test_session_factory,
    )
    pdf1 = create_sample_pdf_bytes(["Version 1 content."])
    pdf2 = create_sample_pdf_bytes(["Version 2 content with new text."])
    meta = DocumentUploadMetadata(title="Multi Version Doc", document_key="multi-ver-doc")

    # Ingest version 1
    async with test_session_factory() as session:
        resp1 = await service.ingest_rbi_pdf(session, pdf1, "v1.pdf", meta)
        assert resp1.version.version_number == 1

    # Ingest version 2 (different hash)
    async with test_session_factory() as session:
        resp2 = await service.ingest_rbi_pdf(session, pdf2, "v2.pdf", meta)
        assert resp2.version.version_number == 2
        assert resp2.version.id != resp1.version.id

    async with test_session_factory() as session:
        versions = await list_document_versions(session, resp1.document.id)
        assert len(versions) == 2
        ver_nums = sorted([v.version_number for v in versions])
        assert ver_nums == [1, 2]

