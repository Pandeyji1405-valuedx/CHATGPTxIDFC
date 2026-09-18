import os
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session, sessionmaker
from backend.database import SessionLocal, engine, Base
from backend.models import KnowledgeDocument, KnowledgeChunk, User
from backend.auth import get_password_hash
from backend.rag.vector_store import hybrid_vector_store
from backend.ingestion.chunker import document_chunker
from backend.ingestion.ocr_engine import ocr_engine
from backend.ingestion.generate_and_ingest_official_kb import REAL_OFFICIAL_DIRECTIVES

# Build CURATED_RBI_DOCS dynamically from the 12 authentic official directives
CURATED_RBI_DOCS = []
for directive in REAL_OFFICIAL_DIRECTIVES:
    sections_text = []
    for s in directive.get("sections", []):
        sections_text.append(f"{s['heading']}\n{s['content']}")
    full_text = "\n\n".join(sections_text)
    
    CURATED_RBI_DOCS.append({
        "title": directive["title"],
        "notification_number": directive["notification_number"],
        "publication_date": directive["publication_date"],
        "effective_date": directive["effective_date"],
        "source": "RBI" if directive["source"] == "RBI" else "BANK_POLICY",
        "source_url": directive["source_url"],
        "document_type": "scanned_pdf" if directive.get("is_ocr") else "pdf",
        "page_count": len(directive.get("sections", [])) or 1,
        "is_ocr": directive.get("is_ocr", False),
        "text_content": full_text
    })

def seed_database_and_vector_store(custom_engine=None):
    """
    Seeds initial admin/users and builds hybrid vector store index.
    When running against PostgreSQL, utilizes the 100% authentic PDF knowledge base pipeline.
    """
    if custom_engine is None:
        from backend.ingestion.generate_and_ingest_official_kb import seed_and_ingest_all
        db = SessionLocal()
        try:
            doc_count = db.query(KnowledgeDocument).count()
            if doc_count == 0:
                seed_and_ingest_all()
            else:
                # Rebuild in-memory vector store from PostgreSQL records
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
                from backend.cache.redis_cache import redis_cache
                redis_cache.flushall()
        finally:
            db.close()
        return

    # In-memory test engine execution
    SessionMaker = sessionmaker(bind=custom_engine)
    db = SessionMaker()

    try:
        # 1. Seed Users
        admin_email = "admin@idfcbank.com"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                email=admin_email,
                name="System Administrator",
                password_hash=get_password_hash("Admin@12345"),
                role="admin",
                auth_provider="local"
            )
            db.add(admin)

        demo_user_email = "customer@idfcbank.com"
        demo_user = db.query(User).filter(User.email == demo_user_email).first()
        if not demo_user:
            demo_user = User(
                email=demo_user_email,
                name="Siddharth Sharma",
                password_hash=get_password_hash("Customer@123"),
                role="user",
                auth_provider="local"
            )
            db.add(demo_user)

        db.commit()

        # 2. Seed Curated Documents
        all_chunks_for_index = []

        for doc_data in CURATED_RBI_DOCS:
            checksum = hashlib.sha256(doc_data["text_content"].encode("utf-8")).hexdigest()
            existing_doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.checksum == checksum).first()

            if not existing_doc:
                ambiguities = ocr_engine.detect_character_ambiguities(doc_data["text_content"])
                amb_notes = f"Detected {len(ambiguities)} potential ambiguities" if ambiguities else None

                doc_record = KnowledgeDocument(
                    title=doc_data["title"],
                    notification_number=doc_data["notification_number"],
                    publication_date=doc_data["publication_date"],
                    effective_date=doc_data["effective_date"],
                    source=doc_data["source"],
                    source_url=doc_data["source_url"],
                    document_type=doc_data["document_type"],
                    page_count=doc_data["page_count"],
                    is_ocr=doc_data["is_ocr"],
                    ocr_confidence=0.84 if doc_data["is_ocr"] else 1.0,
                    ocr_ambiguity_notes=amb_notes,
                    checksum=checksum,
                    processing_status="indexed"
                )
                db.add(doc_record)
                db.commit()
                db.refresh(doc_record)
                doc_id = doc_record.id
            else:
                doc_id = existing_doc.id

            chunks = document_chunker.split_text_into_chunks(doc_data["text_content"], page_number=1)
            for c_idx, c in enumerate(chunks):
                existing_chunk = db.query(KnowledgeChunk).filter(
                    KnowledgeChunk.document_id == doc_id,
                    KnowledgeChunk.chunk_index == c_idx
                ).first()

                if not existing_chunk:
                    chunk_obj = KnowledgeChunk(
                        document_id=doc_id,
                        page_number=c["page_number"],
                        chunk_index=c_idx,
                        section=c.get("section", "General"),
                        chunk_text=c["chunk_text"]
                    )
                    db.add(chunk_obj)
                    db.commit()
                    db.refresh(chunk_obj)
                    chunk_id = chunk_obj.id
                else:
                    chunk_id = existing_chunk.id

                all_chunks_for_index.append({
                    "id": chunk_id,
                    "document_id": doc_id,
                    "doc_title": doc_data["title"],
                    "notification_number": doc_data["notification_number"],
                    "source": doc_data["source"],
                    "page_number": c["page_number"],
                    "section": c.get("section", "General"),
                    "chunk_text": c["chunk_text"],
                    "publication_date": doc_data["publication_date"]
                })

        db.commit()

        # 3. Build Hybrid Vector Index in Memory
        hybrid_vector_store.build_index(all_chunks_for_index)

    except Exception as e:
        db.rollback()
        print(f"Error seeding knowledge base: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database_and_vector_store()
