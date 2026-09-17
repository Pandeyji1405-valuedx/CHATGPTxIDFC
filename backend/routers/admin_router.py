import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, KnowledgeDocument, KnowledgeChunk, AuditLog
from backend.schemas import KnowledgeDocumentResponse, DocumentDetailResponse
from backend.auth import get_current_admin
from backend.config import settings
from backend.ingestion.extractor import document_extractor
from backend.ingestion.chunker import document_chunker
from backend.rag.vector_store import hybrid_vector_store

router = APIRouter(prefix="/api/admin", tags=["Knowledge Base Administration"])

ALLOWED_EXTENSIONS = {"pdf", "txt", "docx", "csv", "png", "jpg", "jpeg", "md"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024 # 25 MB

def rebuild_vector_index(db: Session):
    """Refreshes the in-memory hybrid vector store from all DB chunks."""
    all_chunks = db.query(KnowledgeChunk).all()
    records = []
    for c in all_chunks:
        doc = c.document
        if doc:
            records.append({
                "id": c.id,
                "document_id": c.document_id,
                "doc_title": doc.title,
                "notification_number": doc.notification_number,
                "source": doc.source,
                "page_number": c.page_number,
                "section": c.section,
                "chunk_text": c.chunk_text,
                "publication_date": doc.publication_date
            })
    hybrid_vector_store.build_index(records)

@router.get("/documents", response_model=List[KnowledgeDocumentResponse])
def list_documents(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    docs = db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).all()
    res = []
    for d in docs:
        chunk_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == d.id).count()
        doc_resp = KnowledgeDocumentResponse(
            id=d.id,
            title=d.title,
            notification_number=d.notification_number,
            publication_date=d.publication_date,
            effective_date=d.effective_date,
            source=d.source,
            source_url=d.source_url,
            document_type=d.document_type,
            version=d.version,
            processing_status=d.processing_status,
            page_count=d.page_count,
            is_ocr=d.is_ocr,
            ocr_confidence=d.ocr_confidence,
            ocr_ambiguity_notes=d.ocr_ambiguity_notes,
            chunk_count=chunk_count,
            created_at=d.created_at
        )
        res.append(doc_resp)
    return res

@router.post("/documents/upload", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source: Optional[str] = Form("RBI"),
    notification_number: Optional[str] = Form(None),
    publication_date: Optional[str] = Form(None),
    effective_date: Optional[str] = Form(None),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Security Validation: Extension & Size
    filename = file.filename or "uploaded_document.pdf"
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type .{ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum limit of 25MB"
        )

    # Extract Text, OCR, and Character Ambiguities
    try:
        extracted = document_extractor.extract_document(file_bytes, filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process and extract text from document: {str(e)}"
        )

    # Save physical copy in uploads folder
    safe_save_name = f"{extracted['checksum'][:12]}_{filename}"
    save_path = os.path.join(settings.UPLOAD_DIR, safe_save_name)
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    # Format Ambiguity Notes
    amb_notes = None
    if extracted["ambiguities"]:
        amb_notes = f"Detected {len(extracted['ambiguities'])} potential character ambiguities (e.g., {extracted['ambiguities'][0]['character_pair']})"

    doc_title = title.strip() if title else filename.replace("_", " ").rsplit(".", 1)[0]

    # Create Document Record
    doc_record = KnowledgeDocument(
        title=doc_title,
        notification_number=notification_number.strip() if notification_number else None,
        publication_date=publication_date.strip() if publication_date else None,
        effective_date=effective_date.strip() if effective_date else None,
        source=source.strip() if source else "RBI",
        document_type=extracted["document_type"],
        file_path=save_path,
        page_count=extracted["page_count"],
        is_ocr=extracted["is_ocr"],
        ocr_confidence=extracted["ocr_confidence"],
        ocr_ambiguity_notes=amb_notes,
        checksum=extracted["checksum"],
        processing_status="indexed"
    )
    db.add(doc_record)
    db.commit()
    db.refresh(doc_record)

    # Chunk Document
    chunks = document_chunker.chunk_document_pages(extracted["pages"])
    for c in chunks:
        chunk_record = KnowledgeChunk(
            document_id=doc_record.id,
            page_number=c["page_number"],
            chunk_index=c["chunk_index"],
            section=c.get("section", "General"),
            chunk_text=c["chunk_text"]
        )
        db.add(chunk_record)

    db.commit()

    # Re-index hybrid vector store
    rebuild_vector_index(db)

    # Audit log
    audit = AuditLog(
        user_id=current_admin.id,
        action="UPLOAD_KB",
        resource_type="knowledge_document",
        resource_id=doc_record.id,
        details=f"Uploaded {filename} with {len(chunks)} chunks",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()

    return KnowledgeDocumentResponse(
        id=doc_record.id,
        title=doc_record.title,
        notification_number=doc_record.notification_number,
        publication_date=doc_record.publication_date,
        effective_date=doc_record.effective_date,
        source=doc_record.source,
        source_url=doc_record.source_url,
        document_type=doc_record.document_type,
        version=doc_record.version,
        processing_status=doc_record.processing_status,
        page_count=doc_record.page_count,
        is_ocr=doc_record.is_ocr,
        ocr_confidence=doc_record.ocr_confidence,
        ocr_ambiguity_notes=doc_record.ocr_ambiguity_notes,
        chunk_count=len(chunks),
        created_at=doc_record.created_at
    )

@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document_detail(
    document_id: str,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    chunks = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == document_id).order_by(KnowledgeChunk.chunk_index.asc()).all()
    chunk_count = len(chunks)

    doc_resp = KnowledgeDocumentResponse(
        id=doc.id,
        title=doc.title,
        notification_number=doc.notification_number,
        publication_date=doc.publication_date,
        effective_date=doc.effective_date,
        source=doc.source,
        source_url=doc.source_url,
        document_type=doc.document_type,
        version=doc.version,
        processing_status=doc.processing_status,
        page_count=doc.page_count,
        is_ocr=doc.is_ocr,
        ocr_confidence=doc.ocr_confidence,
        ocr_ambiguity_notes=doc.ocr_ambiguity_notes,
        chunk_count=chunk_count,
        created_at=doc.created_at
    )

    chunks_preview = [
        {
            "id": c.id,
            "page_number": c.page_number,
            "chunk_index": c.chunk_index,
            "section": c.section,
            "chunk_text_preview": c.chunk_text[:200] + ("..." if len(c.chunk_text) > 200 else "")
        }
        for c in chunks
    ]

    return DocumentDetailResponse(
        document=doc_resp,
        chunks_preview=chunks_preview
    )

@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Delete physical file if exists
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    db.delete(doc)
    db.commit()

    # Re-index vector store
    rebuild_vector_index(db)

    audit = AuditLog(
        user_id=current_admin.id,
        action="DELETE_KB",
        resource_type="knowledge_document",
        resource_id=document_id,
        details=f"Deleted document {doc.title}",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()

    return {"message": "Document deleted and index refreshed"}

@router.post("/reindex")
def reindex_all(
    request: Request,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    rebuild_vector_index(db)
    chunk_count = db.query(KnowledgeChunk).count()
    return {
        "message": f"Successfully re-indexed {chunk_count} chunks across all knowledge base documents",
        "total_chunks": chunk_count
    }
