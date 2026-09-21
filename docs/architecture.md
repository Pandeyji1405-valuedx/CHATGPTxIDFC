# IDFC Advisory Assistant — Architecture & System Design

> **Document Status:** Fully Updated — All Implemented Core Systems (Phases 1 through 7).  
> **Target Platform:** IDFC Bank Enterprise Regulatory Knowledge & Compliance Platform  
> **Primary Stack:** FastAPI, React + TypeScript, PostgreSQL (`pgvector` + FTS), ChromaDB, Redis, Nomic Embed v1.5, BGE Reranker v2-m3, Google Gemini 3.6 Flash.

---

## 1. Official Development Roadmap & Implementation Status

| Phase | Title | Scope / Description | Implementation Status |
|---|---|---|---|
| **Phase 1** | Foundation | FastAPI scaffold, PostgreSQL connection pool, SQLAlchemy async models, Alembic migrations | ✅ **Complete** |
| **Phase 2** | Authentication & RBAC | Argon2id password hashing, JWT bearer auth, role-based access control (`ADMIN` vs `USER`) | ✅ **Complete** |
| **Phase 3** | Knowledge Base & Ingestion | Async background PDF parser (PyMuPDF), SHA-256 fingerprinting, page-aware chunking, Nomic Embed v1.5, ChromaDB vector indexing | ✅ **Complete** |
| **Phase 4** | Core RBI RAG Pipeline | Hybrid Dense+Sparse retrieval, BGE Reranker v2-m3 cross-encoder, Evidence Gate thresholding, Gemini 3.6 Flash generation with page citations | ✅ **Complete** |
| **Phase 5** | Memory & 4-Tier Cache | Redis sliding session memory, Query Contextualizer, Tier 1 Redis Exact Cache, Tier 2 PG Exact Cache, Tier 3 PG `pgvector` Semantic Cache, Question Variant generation | ✅ **Complete** |
| **Phase 6** | Knowledge Graph | Neo4j regulatory graph, entity extraction & graph-augmented retrieval | 🔜 Deferred (Planned) |
| **Phase 7** | Security & Audit Trail | PII detection & redaction middleware, immutable audit logging (`audit_logs`), user feedback collection (`feedback`), rate limiting | ✅ **Complete** |
| **Phase 8** | Integration & Hardening | Async background reliability, complete unit/integration testing suite | ✅ **Complete** |

---

## 2. High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             Client Layer (Browser)                              │
│              React 19 + TypeScript + Vite 8 + Tailwind CSS 3.4                  │
│     · Protected Chat Workspace        · Admin Knowledge Base PDF Upload         │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │  HTTPS / REST JSON + Bearer JWT
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Backend Application                          │
│                            (Python 3.11, Uvicorn)                               │
│                                                                                 │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────────┐  ┌───────────┐ │
│  │ Auth API (/auth) │  │ Chat API (/chat)│  │ Docs (/upload) │  │ Feedback  │ │
│  └────────┬─────────┘  └────────┬────────┘  └───────┬────────┘  └─────┬─────┘ │
│           │                     │                   │                 │       │
│  ┌────────▼─────────────────────▼───────────────────▼─────────────────▼─────┐ │
│  │                          Security & Audit Layer                          │ │
│  │    PII Masking Service · Audit Logger (`audit_logs`) · Rate Limiter      │ │
│  └────────┬─────────────────────┬───────────────────┬─────────────────┬─────┘ │
│           │                     │                   │                 │       │
│  ┌────────▼─────────────────────▼───────────────────▼─────────────────▼─────┐ │
│  │                              Service Layer                               │ │
│  │   AuthService · Query Contextualizer · 4-Tier Cache Cascade              │ │
│  │   HybridRetriever (ChromaDB + PG FTS) · BGE Reranker · Evidence Gate     │ │
│  │   Gemini 3.6 Flash LLM Gateway · Citation Validator                      │ │
│  │   Async Document Ingestion Orchestrator & Storage Repository             │ │
│  └────────┬─────────────────────┬───────────────────┬─────────────────┬─────┘ │
└───────────┼─────────────────────┼───────────────────┼─────────────────┼───────┘
            │                     │                   │                 │
            ▼                     ▼                   ▼                 ▼
┌───────────────────────┐ ┌───────────────┐ ┌────────────────┐ ┌─────────────────┐
│ PostgreSQL Database   │ │ Redis Server  │ │ ChromaDB Store │ │ Local Storage   │
│ · System of Record    │ │ · Session     │ │ · Collection:  │ │ · Raw PDFs      │
│ · pgvector Embeddings │ │   Memory      │ │   rbi_docs     │ │   storage/      │
│ · FTS tsvector        │ │ · Tier 1      │ │ · Nomic Embed  │ │   documents/    │
│ · Cache & Audit Logs  │ │   Exact Cache │ │   v1.5 (768d)  │ │                 │
└───────────────────────┘ └───────────────┘ └────────────────┘ └─────────────────┘
```

---

## 3. Async Background Document Ingestion Workflow (Phase 3)

Large RBI regulatory PDFs are processed asynchronously in background tasks to prevent HTTP request timeouts while maintaining 100% version consistency and audit traceability.

```
Upload Request (ADMIN only: POST /api/v1/documents/upload)
        │
        ▼
1. Initial Validation (File Extension, %PDF- Magic Bytes, Max 50MB Size)
        │
        ▼
2. SHA-256 Binary Fingerprinting & Idempotency Check
   │ ──► If duplicate file_hash & status == COMPLETED ──► Return existing version immediately
   │
   ▼
3. Store PDF File on Filesystem (`storage/documents/{hash}.pdf`)
        │
        ▼
4. Create PostgreSQL Parent Document (`documents` table) & DocumentVersion Record (`status=INACTIVE`, `ingestion_status=PROCESSING`)
        │
        ▼
5. Return HTTP 202 Accepted (Immediately releases HTTP client)
        │
        ▼
[Background Processing Routine]
6. PyMuPDF (`fitz`) Text Extraction (Page-by-page, preserving 1-indexed boundaries)
        │
        ▼
7. Deterministic Text Cleaning (Unicode NFKC, control char stripping, ligature normalization)
        │
        ▼
8. Deterministic Page Chunking (Unique Chunk ID: `doc_{doc_id}_v{ver}_p{page}_c{idx}`)
        │
        ▼
9. Vector Embedding Generation (Nomic Embed v1.5 with prefix `"search_document: "`, 768-dim)
        │
        ▼
10. ChromaDB Vector Indexing (`rbi_documents` collection)
        │
        ▼
11. Atomic State Transition (`status=ACTIVE`, `ingestion_status=COMPLETED`)
    [On Failure: `status=INACTIVE`, `ingestion_status=FAILED`, record error message]
```

---

## 4. End-to-End Chat & 4-Tier Cache Cascade Workflow (Phases 4, 5, 7)

```
User Query (POST /api/v1/chat/message)
        │
        ▼
1. Security & PII Inspection (Masks sensitive personal data prior to execution)
        │
        ▼
2. Query Contextualizer (Inspects 10 Redis session turns; rewrites follow-up into canonical query)
        │
        ▼
3. 4-Tier Cache Cascade Execution
        │
        ├──► Tier 1: Redis Exact Cache Lookup (Key: Query SHA-256 Hash)
        │        └──► HIT ──► Return Cached Answer (<100ms)
        │
        ├──► Tier 2: PostgreSQL Exact Cache Lookup (`cached_answers` table)
        │        └──► HIT ──► Populate Redis & Return Cached Answer
        │
        ├──► Tier 3: PostgreSQL `pgvector` Semantic Cache Lookup (Cosine Similarity ≥ 0.92)
        │        └──► HIT ──► Return Cached Answer (~700ms)
        │
        └──► Tier 4: Main Hybrid RAG Pipeline (Cache MISS)
                 │
                 ▼
          Hybrid Retrieval
          · Dense Retrieval: ChromaDB Top-20 (Nomic Embed prefix `"search_query: "`)
          · Sparse Retrieval: PostgreSQL FTS Top-20 (`to_tsvector('simple', content)`)
                 │
                 ▼
          BGE Cross-Encoder Reranker (`BAAI/bge-reranker-v2-m3`)
          · Reranks merged candidates; computes relevance scores
                 │
                 ▼
          Evidence Gate Thresholding
          · Evaluates candidate relevance; passes top 5 chunks
                 │
                 ▼
          Gemini 3.6 Flash Generation
          · Generates answer grounded strictly on retrieved chunk context
                 │
                 ▼
          Citation Validation & Grounding
          · Matches answer claims against 1-indexed document page metadata
                 │
                 ▼
          Cache Write-Through & Variant Generation
          · Saves answer to `cached_answers` & links `cache_document_dependencies`
          · Calls Gemini Flash to synthesize 3 alternative `question_variants`
                 │
                 ▼
          Return Grounded Response to User (HTTP 200 OK)
```

---

## 5. Database Entity Relationship Diagram (PostgreSQL)

```
┌──────────────┐           ┌────────────────────┐           ┌──────────────────────────────┐
│    users     │           │     documents      │           │      document_versions       │
├──────────────┤           ├────────────────────┤           ├──────────────────────────────┤
│ id (PK)      │           │ id (PK)            │1        N │ id (PK)                      │
│ name         │           │ document_key (UNI) ├───────────┤ document_id (FK)             │
│ email (UNI)  │           │ title              │           │ version_number               │
│ password_hash│           │ document_type      │           │ status (ACTIVE/INACTIVE/SUPER│
│ role (ENUM)  │           │ circular_number    │           │ file_hash (UNI)              │
│ created_at   │           │ topic              │           │ storage_path                 │
└──────┬───────┘           └────────────────────┘           │ ingestion_status (COMPLETED) │
       │                                                    └──────────────┬───────────────┘
       │                                                                   │
       │                                                                   │1
       │1                                                                  │
       │                                                                   │N
       │N                                                           ┌──────┴──────────────────────┐
┌──────┴───────┐           ┌────────────────────┐                   │   document_chunks           │
│conversations │           │  cached_answers    │                   ├─────────────────────────────┤
├──────────────┤           ├────────────────────┤                   │ id (PK)                     │
│ id (PK)      │1        N │ id (PK)            │                   │ version_id (FK)             │
│ user_id (FK) ├───────────┤ query_hash (UNI)   │                   │ chunk_id (UNI)              │
│ title        │           │ original_user_query│                   │ content                     │
│ message_count│           │ canonical_query    │                   │ page_number                 │
└──────┬───────┘           │ answer             │                   │ section                     │
       │                   │ query_vector (VEC) │                   └─────────────────────────────┘
       │1                  └─────────┬──────────┘
       │                             │
       │N                            │1
┌──────┴───────┐                     │
│   messages   │                     │N
├──────────────┤           ┌─────────┴────────────────────┐         ┌─────────────────────────────┐
│ id (PK)      │           │ cache_document_dependencies  │         │      question_variants      │
│ conversation_│           ├──────────────────────────────┤         ├─────────────────────────────┤
│ id (FK)      │           │ id (PK)                      │         │ id (PK)                     │
│ role (ENUM)  │           │ cache_answer_id (FK)         │         │ cache_answer_id (FK)        │
│ content      │           │ document_version_id (FK)     │         │ variant_query               │
│ citations    │           └──────────────────────────────┘         │ variant_hash (UNI)          │
│ metrics      │                                                    └─────────────────────────────┘
└──────────────┘
```

---

## 6. Detailed Schema Specification

### Core Tables Summary

1. `users`: User identity, Argon2id passwords, roles (`ADMIN`, `USER`).
2. `documents`: Master circular / regulatory policy registry.
3. `document_versions`: Revision history, ingestion status (`COMPLETED`, `FAILED`), and supersession pointers (`superseded_by_id`).
4. `document_chunks`: Sparse PostgreSQL FTS text storage mapped 1-to-1 with ChromaDB vector chunks.
5. `conversations`: Conversation sessions per user.
6. `messages`: Turn-by-turn chat history, citations JSON, and performance metrics JSON.
7. `cached_answers`: Persistent Tier 2 exact & Tier 3 `pgvector` (768-dim) semantic cache store.
8. `cache_document_dependencies`: Links cached answers to specific `document_version_id` revisions for version-aware invalidation.
9. `question_variants`: Synthesized question paraphrases pointing to active `cached_answers`.
10. `audit_logs`: Immutable audit trail tracking logins, document uploads, and query actions with correlation IDs.
11. `feedback`: User feedback (thumbs up/down, comments) linked to assistant messages.

---

## 7. Security & Compliance Controls

- **Authentication**: JWT Bearer tokens with 30-minute expiration.
- **Password Security**: Argon2id via `argon2-cffi` with salt and memory cost configuration.
- **PII Redaction**: Regular expression & NER-based masking replacing names, phone numbers, and account identifiers before sending prompts to external APIs.
- **Audit Logging**: Structured log records inserted into `audit_logs` for every security, upload, and chat operation.
- **Governance Cache Gates**: Cache hits require active document version status (`ACTIVE`), valid role matching, and non-expired timestamps.
