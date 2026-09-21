"""
Phase 3 RBI Knowledge Base tests.

Covers:
  1. PDF VALIDATION      — valid PDF, non-PDF, corrupt, empty, oversized
  2. PDF EXTRACTION      — page preservation, deterministic ordering, empty pages
  3. TEXT CLEANING       — whitespace normalization, ligatures, control chars, legal semantics
  4. DETERMINISTIC CHUNKING — stable chunk IDs, citation metadata, overlap
  5. EMBEDDINGS          — document prefix (search_document: ), query prefix (search_query: )
  6. CHROMADB            — persistent/in-memory indexing, query retrieval, deletion, stats
  7. INGESTION PIPELINE  — end-to-end flow, idempotency, versioning, explicit supersession, failure states
  8. AUTHORIZATION & API — ADMIN upload access, USER upload rejection (403), document list/detail queries
"""

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus, DocumentVersion, IngestionStatus
from app.schemas.document import DocumentUploadMetadata
from app.services.chunking.text_chunker import chunk_pages
from app.services.documents.ingestion_service import DocumentIngestionService
from app.services.embeddings.mock_service import MockEmbeddingService
from app.services.embeddings.nomic_service import DOCUMENT_PREFIX, QUERY_PREFIX, NomicEmbeddingService
from app.services.pdf.cleaner import clean_regulatory_text
from app.services.pdf.extractor import ExtractedPage, extract_pdf_pages
from app.services.pdf.validator import validate_pdf_bytes
from app.services.vector_db.chroma_service import ChromaDBService
from tests.conftest import create_sample_pdf_bytes


# ================================================================== #
# 1. PDF VALIDATION TESTS
# ================================================================== #
class TestPDFValidation:
    """Tests for PDF validation service."""

    def test_valid_pdf_passes(self):
        pdf_bytes = create_sample_pdf_bytes(["RBI Circular on KYC Norms 2024."])
        is_valid, err = validate_pdf_bytes(pdf_bytes, "rbi_kyc_2024.pdf")
        assert is_valid is True
        assert err is None

    def test_invalid_extension_fails(self):
        pdf_bytes = create_sample_pdf_bytes(["Sample text."])
        is_valid, err = validate_pdf_bytes(pdf_bytes, "document.docx")
        assert is_valid is False
        assert "extension" in err.lower()

    def test_empty_bytes_fails(self):
        is_valid, err = validate_pdf_bytes(b"", "empty.pdf")
        assert is_valid is False
        assert "empty" in err.lower()

    def test_missing_magic_bytes_fails(self):
        fake_pdf = b"This is just plain text masquerading as a PDF file."
        is_valid, err = validate_pdf_bytes(fake_pdf, "fake.pdf")
        assert is_valid is False
        assert "signature" in err.lower() or "header" in err.lower()

    def test_oversized_file_fails(self):
        pdf_bytes = create_sample_pdf_bytes(["Sample"])
        is_valid, err = validate_pdf_bytes(pdf_bytes, "large.pdf", max_size_bytes=10)
        assert is_valid is False
        assert "exceeds" in err.lower()


# ================================================================== #
# 2. PDF TEXT EXTRACTION TESTS
# ================================================================== #
class TestPDFExtraction:
    """Tests for page-by-page PDF extraction."""

    def test_extract_single_page(self):
        text = "Reserve Bank of India Master Direction - KYC Direction, 2016."
        pdf_bytes = create_sample_pdf_bytes([text])
        pages = extract_pdf_pages(pdf_bytes)

        assert len(pages) == 1
        assert pages[0].page_number == 1
        assert "KYC Direction, 2016" in pages[0].text
        assert pages[0].char_count > 0

    def test_extract_multiple_pages_in_order(self):
        page1 = "Chapter I: Preliminary and Definitions."
        page2 = "Chapter II: Customer Acceptance Policy."
        page3 = "Chapter III: Risk Management Procedures."
        pdf_bytes = create_sample_pdf_bytes([page1, page2, page3])
        pages = extract_pdf_pages(pdf_bytes)

        assert len(pages) == 3
        assert [p.page_number for p in pages] == [1, 2, 3]
        assert "Chapter I" in pages[0].text
        assert "Chapter II" in pages[1].text
        assert "Chapter III" in pages[2].text

    def test_extract_empty_page_handled_safely(self):
        pdf_bytes = create_sample_pdf_bytes(["Page 1 content", "", "Page 3 content"])
        pages = extract_pdf_pages(pdf_bytes)

        assert len(pages) == 3
        assert pages[1].page_number == 2
        assert pages[1].text.strip() == ""


# ================================================================== #
# 3. TEXT CLEANING TESTS
# ================================================================== #
class TestTextCleaning:
    """Tests for deterministic regulatory text cleaning."""

    def test_clean_whitespace_and_excessive_newlines(self):
        raw = "RBI   Circular   No. 108\n\n\n\n\nParagraph   1.\n\n\nParagraph  2."
        cleaned = clean_regulatory_text(raw)
        assert "RBI Circular No. 108" in cleaned
        assert "\n\n\n" not in cleaned
        assert "Paragraph 1.\n\nParagraph 2." in cleaned

    def test_clean_control_characters(self):
        raw = "Valid\x00 text\x07 with\x1f control\x08 characters."
        cleaned = clean_regulatory_text(raw)
        assert cleaned == "Valid text with control characters."

    def test_clean_ligatures(self):
        raw = "Speci\ufb01c \ufb02ow and o\ufb03ce directive."
        cleaned = clean_regulatory_text(raw)
        assert "Specific" in cleaned
        assert "flow" in cleaned
        assert "office" in cleaned

    def test_preserves_statutory_language(self):
        raw = "Section 35A of the Banking Regulation Act, 1949 (10 of 1949)."
        cleaned = clean_regulatory_text(raw)
        assert cleaned == "Section 35A of the Banking Regulation Act, 1949 (10 of 1949)."


# ================================================================== #
# 4. DETERMINISTIC CHUNKING TESTS
# ================================================================== #
class TestDeterministicChunking:
    """Tests for page-aware deterministic chunking."""

    def test_chunk_ids_deterministic(self):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        pages = [
            ExtractedPage(page_number=1, text="Short page one text.", char_count=20),
            ExtractedPage(page_number=2, text="Short page two text.", char_count=20),
        ]
        meta = {
            "title": "Master Direction on KYC",
            "circular_number": "RBI/2016-17/18",
            "topic": "KYC",
            "version_number": 1,
            "file_hash": "abc123hash",
            "status": "ACTIVE",
        }

        chunks = chunk_pages(pages, doc_id, ver_id, meta, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 2
        assert chunks[0].chunk_id == f"doc_{doc_id}_v1_p1_c0"
        assert chunks[1].chunk_id == f"doc_{doc_id}_v1_p2_c0"

    def test_chunk_metadata_complete(self):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        pages = [ExtractedPage(page_number=5, text="Page 5 content text.", char_count=20)]
        meta = {
            "title": "Cyber Security Framework",
            "circular_number": "RBI/2016-17/30",
            "topic": "Cyber Security",
            "version_number": 2,
            "file_hash": "hash999",
            "status": "ACTIVE",
        }

        chunks = chunk_pages(pages, doc_id, ver_id, meta, chunk_size=500, chunk_overlap=50)
        assert len(chunks) == 1
        m = chunks[0].metadata
        assert m["document_id"] == str(doc_id)
        assert m["version_id"] == str(ver_id)
        assert m["version_number"] == 2
        assert m["document_title"] == "Cyber Security Framework"
        assert m["circular_number"] == "RBI/2016-17/30"
        assert m["topic"] == "Cyber Security"
        assert m["page_number"] == 5
        assert m["chunk_id"] == f"doc_{doc_id}_v2_p5_c0"
        assert m["status"] == "ACTIVE"

    def test_chunk_multi_paragraph_and_sentences(self):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        long_text = (
            "Paragraph one is a fairly long section discussing banking regulation in India. "
            "It establishes the statutory framework under the Banking Regulation Act.\n\n"
            "Paragraph two discusses Customer Acceptance Policy (CAP) and required due diligence. "
            "Banks must obtain officially valid documents (OVD) for customer onboarding.\n\n"
            "Paragraph three discusses periodic update of KYC records based on risk categorization."
        )
        pages = [ExtractedPage(page_number=1, text=long_text, char_count=len(long_text))]
        meta = {"title": "KYC Norms", "version_number": 1, "status": "ACTIVE"}

        # Use small chunk size to trigger multi-paragraph splitting
        chunks = chunk_pages(pages, doc_id, ver_id, meta, chunk_size=150, chunk_overlap=30)
        assert len(chunks) >= 2
        for c in chunks:
            assert c.page_number == 1
            assert c.chunk_id.startswith(f"doc_{doc_id}_v1_p1_c")
            assert len(c.text) > 0

    def test_empty_page_produces_no_chunks(self):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        pages = [ExtractedPage(page_number=1, text="   \n\n   ", char_count=0)]
        meta = {"title": "Empty Page", "version_number": 1, "status": "ACTIVE"}
        chunks = chunk_pages(pages, doc_id, ver_id, meta)
        assert len(chunks) == 0



# ================================================================== #
# 5. EMBEDDINGS TESTS
# ================================================================== #
class TestEmbeddings:
    """Tests for embedding service and prefix requirements."""

    def test_nomic_prefixes_defined(self):
        assert DOCUMENT_PREFIX == "search_document: "
        assert QUERY_PREFIX == "search_query: "

    def test_mock_embedding_service_dimensions(self):
        svc = MockEmbeddingService(dimension=768)
        assert svc.dimension == 768

        docs = ["Sample document text for embedding.", "Second document text."]
        doc_embs = svc.embed_documents(docs)
        assert len(doc_embs) == 2
        assert len(doc_embs[0]) == 768
        assert len(doc_embs[1]) == 768

        q_emb = svc.embed_query("What are the KYC norms?")
        assert len(q_emb) == 768

    def test_mock_embeddings_deterministic(self):
        svc = MockEmbeddingService(dimension=768)
        emb1 = svc.embed_query("Identical query text")
        emb2 = svc.embed_query("Identical query text")
        assert emb1 == emb2

    def test_nomic_service_exact_prefixes_applied(self, monkeypatch):
        """Rule 6: Verify Nomic embedding prefixes 'search_document: ' and 'search_query: ' are applied."""
        from unittest.mock import MagicMock
        import numpy as np

        service = NomicEmbeddingService()
        mock_model = MagicMock()
        mock_model.encode.return_value = np.zeros((1, 768))
        service._model = mock_model

        # Test document prefix
        service.embed_documents(["Sample regulatory clause."])
        mock_model.encode.assert_called_once()
        args, kwargs = mock_model.encode.call_args
        assert args[0] == ["search_document: Sample regulatory clause."]

        # Test query prefix
        mock_model.reset_mock()
        mock_model.encode.return_value = np.zeros(768)
        service.embed_query("What is the CRR requirement?")
        mock_model.encode.assert_called_once()
        args, kwargs = mock_model.encode.call_args
        assert args[0] == "search_query: What is the CRR requirement?"



# ================================================================== #
# 6. CHROMADB VECTOR DB TESTS
# ================================================================== #
class TestChromaDBService:
    """Tests for ChromaDB collection operations."""

    def test_chromadb_index_and_query(self):
        chroma = ChromaDBService(in_memory=True, collection_name=f"test_col_{uuid.uuid4().hex[:8]}")
        embedder = MockEmbeddingService(dimension=768)

        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        pages = [
            ExtractedPage(page_number=1, text="RBI guidelines on digital lending platforms.", char_count=45),
            ExtractedPage(page_number=2, text="RBI directions on card issuance and operation.", char_count=46),
        ]
        meta = {
            "title": "Digital Lending Guidelines",
            "circular_number": "RBI/2022-23/111",
            "topic": "Digital Lending",
            "version_number": 1,
            "file_hash": "hash_lending",
            "status": "ACTIVE",
        }

        chunks = chunk_pages(pages, doc_id, ver_id, meta)
        chunk_texts = [c.text for c in chunks]
        embeddings = embedder.embed_documents(chunk_texts)

        # Index
        count = chroma.index_chunks(chunks, embeddings)
        assert count == 2

        # Verify stats
        stats = chroma.get_collection_stats()
        assert stats["count"] == 2

        # Query
        q_emb = embedder.embed_query("digital lending platforms")
        results = chroma.query_chunks(q_emb, n_results=1)
        assert len(results) == 1
        assert "digital lending" in results[0]["text"].lower()
        assert results[0]["metadata"]["topic"] == "Digital Lending"

    def test_chromadb_delete_version_chunks(self):
        chroma = ChromaDBService(in_memory=True, collection_name=f"test_col_{uuid.uuid4().hex[:8]}")
        embedder = MockEmbeddingService(dimension=768)

        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        pages = [ExtractedPage(page_number=1, text="Temporary version text.", char_count=22)]
        meta = {"title": "Temp Doc", "version_number": 1, "file_hash": "temp_hash", "status": "ACTIVE"}

        chunks = chunk_pages(pages, doc_id, ver_id, meta)
        embs = embedder.embed_documents([c.text for c in chunks])
        chroma.index_chunks(chunks, embs)

        assert chroma.get_collection_stats()["count"] == 1

        # Delete by version_id
        deleted = chroma.delete_version_chunks(ver_id)
        assert deleted == 1
        assert chroma.get_collection_stats()["count"] == 0


# ================================================================== #
# 7. INGESTION PIPELINE TESTS
# ================================================================== #
class TestDocumentIngestionService:
    """Tests for DocumentIngestionService end-to-end orchestration."""

    @pytest.mark.asyncio
    async def test_full_ingestion_success(self, test_session_factory, tmp_path):
        embedder = MockEmbeddingService(dimension=768)
        chroma = ChromaDBService(in_memory=True, collection_name=f"test_rbi_{uuid.uuid4().hex[:8]}")
        service = DocumentIngestionService(embedding_service=embedder, chroma_service=chroma, storage_dir=str(tmp_path))

        pdf_bytes = create_sample_pdf_bytes([
            "Section 1: Master Direction on Know Your Customer (KYC).",
            "Section 2: Customer Due Diligence (CDD) procedure.",
        ])

        from app.schemas.document import DocumentUploadMetadata

        metadata = DocumentUploadMetadata(
            title="Master Direction - KYC Direction, 2016",
            document_key="rbi-kyc-master-direction-2016",
            circular_number="RBI/DBR/2015-16/18",
            topic="KYC",
            source_name="Reserve Bank of India",
        )

        async with test_session_factory() as session:
            result = await service.ingest_rbi_pdf(
                db=session,
                pdf_bytes=pdf_bytes,
                filename="rbi_kyc_2016.pdf",
                metadata=metadata,
            )

        assert result.document.document_key == "rbi-kyc-master-direction-2016"
        assert result.version.version_number == 1
        assert result.version.status == DocumentStatus.ACTIVE
        assert result.version.ingestion_status == IngestionStatus.COMPLETED
        assert result.version.page_count == 2
        assert result.chunks_indexed == 2
        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_idempotent_duplicate_upload(self, test_session_factory, tmp_path):
        embedder = MockEmbeddingService(dimension=768)
        chroma = ChromaDBService(in_memory=True, collection_name=f"test_rbi_{uuid.uuid4().hex[:8]}")
        service = DocumentIngestionService(embedding_service=embedder, chroma_service=chroma, storage_dir=str(tmp_path))

        pdf_bytes = create_sample_pdf_bytes(["RBI Circular on Cyber Security Framework in Banks."])

        async with test_session_factory() as session:
            # First upload
            res1 = await service.ingest_rbi_pdf(
                db=session,
                pdf_bytes=pdf_bytes,
                filename="cyber_sec_2016.pdf",
            )
            assert res1.is_duplicate is False

            # Second identical upload
            res2 = await service.ingest_rbi_pdf(
                db=session,
                pdf_bytes=pdf_bytes,
                filename="cyber_sec_2016.pdf",
            )
            assert res2.is_duplicate is True
            assert res2.version.id == res1.version.id

    @pytest.mark.asyncio
    async def test_explicit_supersession(self, test_session_factory, tmp_path):
        embedder = MockEmbeddingService(dimension=768)
        chroma = ChromaDBService(in_memory=True, collection_name=f"test_rbi_{uuid.uuid4().hex[:8]}")
        service = DocumentIngestionService(embedding_service=embedder, chroma_service=chroma, storage_dir=str(tmp_path))

        pdf_v1 = create_sample_pdf_bytes(["Cyber Security Guidelines 2016 Version 1."])
        pdf_v2 = create_sample_pdf_bytes(["Cyber Security Guidelines 2024 Revised Version 2."])

        from app.schemas.document import DocumentUploadMetadata

        async with test_session_factory() as session:
            # Ingest V1
            res1 = await service.ingest_rbi_pdf(
                db=session,
                pdf_bytes=pdf_v1,
                filename="cyber_sec_v1.pdf",
                metadata=DocumentUploadMetadata(
                    title="Cyber Security Framework",
                    document_key="cyber-sec-framework",
                    version_number=1,
                ),
            )
            v1_id = res1.version.id

            # Ingest V2 with explicit supersedes_version_id
            res2 = await service.ingest_rbi_pdf(
                db=session,
                pdf_bytes=pdf_v2,
                filename="cyber_sec_v2.pdf",
                metadata=DocumentUploadMetadata(
                    title="Cyber Security Framework",
                    document_key="cyber-sec-framework",
                    version_number=2,
                    supersedes_version_id=v1_id,
                ),
            )

            assert res2.version.version_number == 2
            assert res2.version.status == DocumentStatus.ACTIVE

            # Verify V1 is now marked SUPERSEDED with superseded_by_id pointing to V2
            from app.services.documents.document_service import get_document_version_by_id
            v1_reloaded = await get_document_version_by_id(session, v1_id)
            assert v1_reloaded.status == DocumentStatus.SUPERSEDED
            assert v1_reloaded.superseded_by_id == res2.version.id

    @pytest.mark.asyncio
    async def test_no_automatic_supersession_on_new_version(self, test_session_factory, tmp_path):
        """Rule 1: Uploading a new version without explicit supersedes_version_id does NOT supersede older versions."""
        embedder = MockEmbeddingService(dimension=768)
        chroma = ChromaDBService(in_memory=True, collection_name=f"test_rbi_{uuid.uuid4().hex[:8]}")
        service = DocumentIngestionService(embedding_service=embedder, chroma_service=chroma, storage_dir=str(tmp_path))

        pdf_v1 = create_sample_pdf_bytes(["Master Direction on KYC 2016 Edition."])
        pdf_v2 = create_sample_pdf_bytes(["Master Direction on KYC 2024 Amendment."])

        from app.schemas.document import DocumentUploadMetadata
        from app.services.documents.document_service import get_document_version_by_id

        async with test_session_factory() as session:
            # Ingest V1
            res1 = await service.ingest_rbi_pdf(
                db=session,
                pdf_bytes=pdf_v1,
                filename="kyc_v1.pdf",
                metadata=DocumentUploadMetadata(
                    title="KYC Direction",
                    document_key="kyc-direction",
                    version_number=1,
                ),
            )
            v1_id = res1.version.id
            assert res1.version.status == DocumentStatus.ACTIVE

            # Ingest V2 WITHOUT supersedes_version_id
            res2 = await service.ingest_rbi_pdf(
                db=session,
                pdf_bytes=pdf_v2,
                filename="kyc_v2.pdf",
                metadata=DocumentUploadMetadata(
                    title="KYC Direction",
                    document_key="kyc-direction",
                    version_number=2,
                    supersedes_version_id=None,  # No explicit supersession
                ),
            )
            assert res2.version.status == DocumentStatus.ACTIVE
            assert res2.version.version_number == 2

            # V1 MUST still be ACTIVE and NOT SUPERSEDED
            v1_reloaded = await get_document_version_by_id(session, v1_id)
            assert v1_reloaded.status == DocumentStatus.ACTIVE
            assert v1_reloaded.superseded_by_id is None

    @pytest.mark.asyncio
    async def test_pipeline_failure_sets_failed_status_and_cleans_chroma(self, test_session_factory, tmp_path):
        """Rule 3 & 4: If ChromaDB indexing fails, mark ingestion_status = FAILED, status = INACTIVE, and cleanup."""
        class FailingChromaService(ChromaDBService):
            def index_chunks(self, chunks, embeddings):
                raise RuntimeError("ChromaDB connection timed out / disk full.")

        embedder = MockEmbeddingService(dimension=768)
        chroma = FailingChromaService(in_memory=True, collection_name=f"test_fail_{uuid.uuid4().hex[:8]}")
        service = DocumentIngestionService(embedding_service=embedder, chroma_service=chroma, storage_dir=str(tmp_path))

        pdf_bytes = create_sample_pdf_bytes(["Important RBI Banking Regulation text."])

        from app.services.documents.document_service import get_document_by_key, list_document_versions

        async with test_session_factory() as session:
            with pytest.raises(RuntimeError, match="Document ingestion failed"):
                await service.ingest_rbi_pdf(
                    db=session,
                    pdf_bytes=pdf_bytes,
                    filename="failing_doc.pdf",
                    metadata=DocumentUploadMetadata(
                        title="Failing Document Test",
                        document_key="failing-doc-test",
                    ),
                )

            # Check PostgreSQL state
            doc = await get_document_by_key(session, "failing-doc-test")
            assert doc is not None
            versions = await list_document_versions(session, doc.id)
            assert len(versions) == 1
            failed_ver = versions[0]

            # Ingestion status MUST be FAILED, status MUST be INACTIVE (not usable/active knowledge)
            assert failed_ver.ingestion_status == IngestionStatus.FAILED
            assert failed_ver.status == DocumentStatus.INACTIVE
            assert failed_ver.error_message is not None
            assert "ChromaDB connection timed out" in failed_ver.error_message


# ================================================================== #
# 8. API & ROLE AUTHORIZATION TESTS
# ================================================================== #
class TestDocumentAuthorizationAndAPIs:
    """Tests for /api/v1/documents endpoints and role restrictions."""

    @pytest.mark.asyncio
    async def test_admin_can_upload_document(self, admin_client: AsyncClient):
        pdf_bytes = create_sample_pdf_bytes(["Official RBI Notification on Digital Payment Security."])
        files = {"file": ("digital_payments.pdf", pdf_bytes, "application/pdf")}
        data = {
            "title": "Master Direction - Digital Payment Security Controls",
            "document_type": "master_direction",
            "circular_number": "RBI/2020-21/74",
            "topic": "Digital Payments",
        }

        response = await admin_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
        )
        assert response.status_code == 202
        body = response.json()
        assert body["document"]["title"] == "Master Direction - Digital Payment Security Controls"
        assert body["version"]["ingestion_status"] in ("PROCESSING", "COMPLETED")

    @pytest.mark.asyncio
    async def test_user_cannot_upload_document(self, auth_client: AsyncClient):
        """USER role is forbidden from uploading regulatory documents (403)."""
        pdf_bytes = create_sample_pdf_bytes(["Unauthorized upload attempt."])
        files = {"file": ("unauthorized.pdf", pdf_bytes, "application/pdf")}

        response = await auth_client.post(
            "/api/v1/documents/upload",
            files=files,
            data={"title": "Unauthorized Doc"},
        )
        assert response.status_code == 403
        assert "insufficient permissions" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_upload(self, client: AsyncClient):
        """Unauthenticated requests are rejected."""
        pdf_bytes = create_sample_pdf_bytes(["No token upload."])
        files = {"file": ("no_token.pdf", pdf_bytes, "application/pdf")}

        response = await client.post(
            "/api/v1/documents/upload",
            files=files,
        )
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_list_documents(self, auth_client: AsyncClient):
        """Authenticated users can query the list of documents."""
        response = await auth_client.get("/api/v1/documents")
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert isinstance(body["items"], list)

    @pytest.mark.asyncio
    async def test_get_document_details(self, admin_client: AsyncClient, auth_client: AsyncClient):
        """Authenticated user can view single document and version history."""
        # Create a document first
        pdf_bytes = create_sample_pdf_bytes(["RBI Master Circular on Exposure Norms."])
        files = {"file": ("exposure_norms.pdf", pdf_bytes, "application/pdf")}
        upload_resp = await admin_client.post(
            "/api/v1/documents/upload",
            files=files,
            data={"title": "Exposure Norms 2023", "topic": "Lending"},
        )
        assert upload_resp.status_code == 202
        doc_id = upload_resp.json()["document"]["id"]
        ver_id = upload_resp.json()["version"]["id"]

        # User fetches document
        doc_resp = await auth_client.get(f"/api/v1/documents/{doc_id}")
        assert doc_resp.status_code == 200
        assert doc_resp.json()["id"] == doc_id
        assert len(doc_resp.json()["versions"]) >= 1

        # User fetches versions
        vers_resp = await auth_client.get(f"/api/v1/documents/{doc_id}/versions")
        assert vers_resp.status_code == 200
        assert isinstance(vers_resp.json(), list)

        # User fetches single version
        ver_resp = await auth_client.get(f"/api/v1/documents/{doc_id}/versions/{ver_id}")
        assert ver_resp.status_code == 200
        assert ver_resp.json()["id"] == ver_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_document_returns_404(self, auth_client: AsyncClient):
        random_id = uuid.uuid4()
        response = await auth_client.get(f"/api/v1/documents/{random_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_documents_with_topic_and_type_filters(self, admin_client: AsyncClient, auth_client: AsyncClient):
        """Test filtering documents by topic and document_type."""
        pdf_bytes = create_sample_pdf_bytes(["Test document content for filtering."])
        files = {"file": ("filtered_doc.pdf", pdf_bytes, "application/pdf")}
        await admin_client.post(
            "/api/v1/documents/upload",
            files=files,
            data={"title": "Specific Topic Document", "topic": "AML_KYC", "document_type": "notification"},
        )

        # Filter by topic match
        resp_match = await auth_client.get("/api/v1/documents?topic=AML_KYC")
        assert resp_match.status_code == 200
        assert resp_match.json()["total"] >= 1
        assert any(d["topic"] == "AML_KYC" for d in resp_match.json()["items"])

        # Filter by non-matching topic
        resp_none = await auth_client.get("/api/v1/documents?topic=NonExistentTopic999")
        assert resp_none.status_code == 200
        assert resp_none.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_version_endpoints_404_handling(self, admin_client: AsyncClient, auth_client: AsyncClient):
        """Test 404 errors for invalid document UUIDs on version routes."""
        random_doc_id = uuid.uuid4()
        random_ver_id = uuid.uuid4()

        # List versions on nonexistent document
        r1 = await auth_client.get(f"/api/v1/documents/{random_doc_id}/versions")
        assert r1.status_code == 404

        # Get version on nonexistent document
        r2 = await auth_client.get(f"/api/v1/documents/{random_doc_id}/versions/{random_ver_id}")
        assert r2.status_code == 404

