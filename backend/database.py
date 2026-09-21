from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.config import settings

is_sqlite = "sqlite" in settings.DATABASE_URL
connect_args = {"check_same_thread": False} if is_sqlite else {}

engine_kwargs = {
    "connect_args": connect_args,
    "echo": False,
}
if not is_sqlite:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_and_migrate_db(target_engine=None):
    """
    Ensures all database tables and newly added schema columns exist seamlessly
    without manual DDL migrations.
    """
    from sqlalchemy import text
    eng = target_engine or engine
    
    # 1. Create any missing tables (e.g. feedback_items, conversation_summaries)
    Base.metadata.create_all(bind=eng)

    # 2. Add any newly added columns if they don't exist
    MIGRATION_COLUMNS = [
        ("users", "tenant_id", "VARCHAR(50) DEFAULT 'default_tenant'"),
        ("users", "department", "VARCHAR(100) DEFAULT 'Retail Banking'"),
        ("users", "auth_provider", "VARCHAR(50) DEFAULT 'local'"),
        ("users", "avatar_url", "TEXT"),
        ("users", "role", "VARCHAR(50) DEFAULT 'user'"),
        ("conversations", "tenant_id", "VARCHAR(50) DEFAULT 'default_tenant'"),
        ("conversations", "title", "VARCHAR(255) DEFAULT 'New Conversation'"),
        ("conversations", "regulator_scope", "VARCHAR(100) DEFAULT 'ALL'"),
        ("conversations", "as_of_date_scope", "VARCHAR(50)"),
        ("messages", "tenant_id", "VARCHAR(50) DEFAULT 'default_tenant'"),
        ("messages", "normalized_content", "TEXT"),
        ("responses", "source_type", "VARCHAR(50) DEFAULT 'DATABASE'"),
        ("responses", "confidence", "FLOAT DEFAULT 1.0"),
        ("responses", "citations_json", "TEXT"),
        ("responses", "ambiguity_flags_json", "TEXT"),
        ("responses", "validation_status", "VARCHAR(50) DEFAULT 'VALIDATED'"),
        ("responses", "query_trace_id", "VARCHAR(64)"),
        ("responses", "prompt_version", "VARCHAR(50) DEFAULT 'v1.0'"),
        ("responses", "model_version", "VARCHAR(50) DEFAULT 'gemini-3.6-flash'"),
        ("responses", "tokens_input", "INTEGER DEFAULT 0"),
        ("responses", "tokens_output", "INTEGER DEFAULT 0"),
        ("knowledge_documents", "tenant_id", "VARCHAR(50) DEFAULT 'default_tenant'"),
        ("knowledge_documents", "notification_number", "VARCHAR(255)"),
        ("knowledge_documents", "publication_date", "VARCHAR(50)"),
        ("knowledge_documents", "effective_date", "VARCHAR(50)"),
        ("knowledge_documents", "effective_from", "VARCHAR(50)"),
        ("knowledge_documents", "effective_until", "VARCHAR(50)"),
        ("knowledge_documents", "regulator", "VARCHAR(50) DEFAULT 'RBI'"),
        ("knowledge_documents", "source", "VARCHAR(100) DEFAULT 'RBI'"),
        ("knowledge_documents", "source_url", "TEXT"),
        ("knowledge_documents", "document_type", "VARCHAR(50) DEFAULT 'pdf'"),
        ("knowledge_documents", "department", "VARCHAR(100) DEFAULT 'Regulatory Compliance'"),
        ("knowledge_documents", "status", "VARCHAR(50) DEFAULT 'active'"),
        ("knowledge_documents", "superseded_by_id", "VARCHAR(36)"),
        ("knowledge_documents", "file_path", "TEXT"),
        ("knowledge_documents", "version", "VARCHAR(50) DEFAULT '1.0'"),
        ("knowledge_documents", "checksum", "VARCHAR(64)"),
        ("knowledge_documents", "processing_status", "VARCHAR(50) DEFAULT 'indexed'"),
        ("knowledge_documents", "failure_reason", "TEXT"),
        ("knowledge_documents", "page_count", "INTEGER DEFAULT 1"),
        ("knowledge_documents", "is_ocr", "BOOLEAN DEFAULT FALSE"),
        ("knowledge_documents", "ocr_confidence", "FLOAT"),
        ("knowledge_documents", "ocr_ambiguity_notes", "TEXT"),
        ("knowledge_chunks", "tenant_id", "VARCHAR(50) DEFAULT 'default_tenant'"),
        ("knowledge_chunks", "page_number", "INTEGER DEFAULT 1"),
        ("knowledge_chunks", "chunk_index", "INTEGER DEFAULT 0"),
        ("knowledge_chunks", "section", "VARCHAR(255)"),
        ("knowledge_chunks", "source_offsets_json", "TEXT"),
        ("knowledge_chunks", "bounding_box_json", "TEXT"),
        ("users", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("users", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("conversations", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("conversations", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("messages", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("responses", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("entities", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("knowledge_documents", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("knowledge_documents", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("knowledge_chunks", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("audit_logs", "tenant_id", "VARCHAR(50) DEFAULT 'default_tenant'"),
        ("audit_logs", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
    ]

    is_pg = "postgresql" in str(eng.url).lower()
    for table, col, col_type in MIGRATION_COLUMNS:
        try:
            with eng.begin() as conn:
                if is_pg:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};"))
        except Exception:
            pass
    
    # Populate existing rows with default values
    if is_pg:
        defaults_sqls = [
            "UPDATE knowledge_documents SET regulator = source WHERE regulator IS NULL;",
            "UPDATE knowledge_documents SET effective_from = publication_date WHERE effective_from IS NULL;",
            "UPDATE knowledge_documents SET status = 'active' WHERE status IS NULL;",
            "UPDATE knowledge_documents SET department = 'Regulatory Compliance' WHERE department IS NULL;",
            "UPDATE knowledge_documents SET tenant_id = 'default_tenant' WHERE tenant_id IS NULL;",
            "UPDATE knowledge_documents SET updated_at = created_at WHERE updated_at IS NULL;",
            "UPDATE knowledge_chunks SET tenant_id = 'default_tenant' WHERE tenant_id IS NULL;",
        ]
        for sql in defaults_sqls:
            try:
                with eng.begin() as conn:
                    conn.execute(text(sql))
            except Exception:
                pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
