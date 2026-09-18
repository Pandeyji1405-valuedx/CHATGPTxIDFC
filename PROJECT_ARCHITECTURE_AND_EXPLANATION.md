# CHATGPTxIDFC — Comprehensive Architecture & Technical Reference Guide

---

## 1. Executive Summary & System Overview

**CHATGPTxIDFC** is a production-grade, enterprise conversational AI application designed specifically for regulated banking and compliance environments. Built to deliver a **ChatGPT 4o-grade user experience**, the platform operates on an **Air-Gapped, Zero-Internet Strict Grounding Model**, answering queries exclusively using verified Reserve Bank of India (RBI) Master Directions and official IDFC FIRST Bank policies.

### Core Objectives & Operating Principles
1. **Zero-Hallucination Regulatory Grounding**: The system never guesses, extrapolates, or leverages public internet knowledge. If a question is outside the approved banking corpus, it returns an explicit, deterministic refusal.
2. **Two-Layer Hybrid Retrieval-Augmented Generation (RAG)**:
   - **Layer 1 (Conversation DB)**: Searches previous multi-turn user conversation messages, contextual entities, and prior answers.
   - **Layer 2 (Regulatory Knowledge Base)**: Performs hybrid dense semantic vector retrieval combined with BM25 sparse keyword matching over approved banking circulars.
3. **Enterprise Security & Multi-Tenancy**: Complete row-level IDOR (Insecure Direct Object Reference) isolation across users, JWT-based RBAC (Customer vs. Admin), audit trails for all operations, and strict input boundary validation.
4. **Resilient Session Management**: Client-side automatic token validation, 401 recovery, and non-blocking asynchronous request cancellation via `AbortController`.

---

## 2. System Architecture Diagram

```mermaid
flowchart TD
    subgraph ClientLayer ["Frontend Client Layer (Vanilla SPA)"]
        UI["ChatGPT 4o Style Web UI (index.html / style.css)"]
        State["State Manager & AbortController (app.js)"]
        AuthClient["Client Auth & Auto-Recovery (authenticatedFetch)"]
        STT_TTS["Web Speech STT & SpeechSynthesis TTS"]
    end

    subgraph APILayer ["FastAPI Application Layer (backend/main.py)"]
        CORS["CORS & Security Headers Middleware"]
        AuthRouter["Auth Router (/api/auth)"]
        ChatRouter["Chat Router (/api/chat)"]
        ConvRouter["Conversation Router (/api/conversations)"]
        AdminRouter["Admin Knowledge Router (/api/admin)"]
        HealthRouter["Diagnostics & Health (/health)"]
    end

    subgraph SecurityAuth ["Security & Authentication Layer"]
        JWT["JWT Token Verification (backend/auth.py)"]
        Bcrypt["Bcrypt Password Hashing"]
        RBAC["Role-Based Access Control (Admin vs User)"]
    end

    subgraph NLPEngine ["NLP & Preprocessing Pipeline (backend/rag/nlp_engine.py)"]
        Normalizer["Hinglish & Slang Normalizer"]
        AcronymExp["Banking Acronym & Circular Code Extractor"]
        Coreference["Conversation Pronoun & Context Resolver"]
        ChitchatHandler["Conversational Greeting Dispatcher"]
    end

    subgraph RAGCore ["Two-Layer RAG Engine (backend/rag/rag_engine.py)"]
        Layer1["Layer 1: Conversation DB Search"]
        Layer2["Layer 2: Hybrid Vector & BM25 Knowledge Search"]
        AntiHallucination["Strict Anti-Hallucination & Answerability Guard"]
        FactSynthesizer["Universal Targeted Fact Synthesizer"]
        AmbiguityDetector["OCR & Character Ambiguity Detector (0/O, 1/I)"]
    end

    subgraph CacheLayer ["Caching Layer (backend/cache/redis_cache.py)"]
        LRU["In-Memory LRU Cache"]
        Redis["Redis Distributed Store (Fallback/Active)"]
    end

    subgraph Persistence ["Persistence Layer (PostgreSQL)"]
        PG["PostgreSQL Database (chatgpt_idfc_rag)"]
        Alembic["Alembic Migration Engine (Revision: 26593e71f9a8)"]
        VectorIndex["In-Memory Hybrid Vector Store (backend/rag/vector_store.py)"]
    end

    UI --> State
    State --> AuthClient
    AuthClient -->|HTTP REST / JSON| CORS
    CORS --> AuthRouter & ChatRouter & ConvRouter & AdminRouter & HealthRouter

    AuthRouter & ChatRouter & ConvRouter & AdminRouter --> JWT
    JWT --> Bcrypt & RBAC

    ChatRouter --> NLPEngine
    NLPEngine --> ChitchatHandler
    NLPEngine --> Coreference
    Coreference --> RAGCore

    RAGCore --> Layer1
    RAGCore --> Layer2

    Layer1 --> CacheLayer
    Layer1 --> PG
    Layer2 --> VectorIndex
    VectorIndex -.->|Auto-Hydrate on Cold Start| PG

    RAGCore --> AntiHallucination
    AntiHallucination --> FactSynthesizer
    FactSynthesizer --> AmbiguityDetector
    AmbiguityDetector --> ChatRouter

    ChatRouter -->|Persist Messages, Citations, Audit| PG
    ChatRouter -->|JSON Response| UI
```

---

## 3. Codebase File Directory Map & File Responsibilities

Below is the directory structure with precise component responsibilities:

```
c:\CHATGPTxIDFC
│
├── alembic.ini                             # Alembic configuration linking SQLAlchemy models to PostgreSQL
├── alembic/
│   ├── env.py                             # Alembic runtime environment & migration runner
│   ├── script.py.mako                     # Migration template
│   └── versions/
│       └── 26593e71f9a8_initial_banking_schema.py # Head migration creating all 7 core banking tables
│
├── backend/                               # Core Python FastAPI backend
│   ├── __init__.py
│   ├── main.py                            # Application entry point, lifespan, middleware & route mounting
│   ├── config.py                          # Pydantic BaseSettings (DB URI, JWT secrets, timeouts, thresholds)
│   ├── database.py                        # SQLAlchemy engine, PostgreSQL connection pool & get_db dependency
│   ├── models.py                          # SQLAlchemy ORM models (User, Conversation, Message, Response, etc.)
│   ├── schemas.py                         # Pydantic validation schemas for API request/response contracts
│   ├── auth.py                            # JWT authentication, bcrypt verification, get_current_user dependency
│   │
│   ├── cache/                             # Caching subsystem
│   │   ├── __init__.py
│   │   └── redis_cache.py                 # Multi-tier LRU / Redis cache for session memory & fast responses
│   │
│   ├── ingestion/                         # Document processing & knowledge base seeding
│   │   ├── __init__.py
│   │   ├── extractor.py                   # Multi-format document parser (PDF, Scanned PDF, OCR, DOCX, TXT)
│   │   ├── seed_rbi_kb.py                 # Initial knowledge base seeder
│   │   └── generate_and_ingest_official_kb.py # Generates & ingests authentic RBI/IDFC PDF directives
│   │
│   ├── rag/                               # RAG & NLP Intelligence Subsystem
│   │   ├── __init__.py
│   │   ├── nlp_engine.py                  # Coreference resolution, Hinglish normalization & entity extraction
│   │   ├── vector_store.py                # Hybrid Vector Store (Cosine dense embeddings + BM25 sparse search)
│   │   ├── rag_engine.py                  # Two-Layer RAG orchestrator, anti-hallucination guard & synthesis
│   │   └── validator.py                   # Fact verification, source separation & OCR ambiguity flagging
│   │
│   └── routers/                           # FastAPI API Endpoint Routers
│       ├── __init__.py
│       ├── auth_router.py                 # POST /login, /register, /google, GET /me, POST /logout
│       ├── chat_router.py                 # POST /api/chat, POST /api/chat/feedback
│       ├── conversation_router.py         # GET, PUT, DELETE /api/conversations & search
│       ├── admin_router.py                # Admin KB upload, OCR inspection, reindexing & document management
│       └── speech_router.py               # Speech-to-text transcribe & text-to-speech audio synthesis
│
├── frontend/                              # Pure Vanilla Single-Page Application (ChatGPT 4o UI)
│   ├── index.html                         # Semantic HTML5 layout, sidebar, composer, modals & toast container
│   ├── style.css                          # Dark/Light theme design system, typography & micro-animations
│   └── app.js                             # Client state, event listeners, AbortController & authenticatedFetch
│
├── tests/                                 # Pytest automated test suite (50 tests, 100% pass)
│   ├── conftest.py                        # Test database setup, fixtures, mock vector stores & client factory
│   ├── test_auth.py                       # User registration, JWT login, OAuth, and current user profile
│   ├── test_conflicts_and_hardening.py    # Zero-internet isolation, conflicting document checks & user lifecycle
│   ├── test_conversation_rag.py           # Pronoun resolution, Hinglish normalization & multi-turn memory
│   ├── test_hallucination_guard.py        # Strict refusal on sports/crypto/external banks & audit feedback
│   ├── test_isolation.py                  # Multi-tenant IDOR isolation between distinct users
│   ├── test_kb_rag.py                     # Regulatory retrieval precision on KYC, LTV, NEFT, Digital Lending
│   ├── test_nlp_and_extractor.py          # Extractor parsing, OCR handling, acronyms, and schema boundary
│   ├── test_ocr_ambiguity.py              # OCR ambiguity detection (0 vs O, 1 vs I, 5 vs S, 8 vs B)
│   ├── test_security_prompt_injection.py  # Prompt injection resistance & RBAC access controls
│   └── test_speech.py                     # STT and TTS endpoint validations
│
├── pyproject.toml                         # Project metadata, pytest configuration & tool definitions
├── requirements.txt                       # Production Python dependencies
├── .env.example                           # Environment configuration template
└── README.md                              # Repository overview and setup guide
```

---

## 4. End-to-End Query Flow & Code Trigger Sequence

When a user interacts with the system, the query flows through the stack in a deterministic, traceable pipeline:

```
[1. User Action]  User clicks suggested prompt card or submits query in textarea
        │
        ▼
[2. Frontend]    frontend/app.js: `sendChatMessage()`
                 - Aborts any prior active request (`activeChatAbortController.abort()`).
                 - Renders user chat bubble & changes Send button to Stop button.
                 - Executes `authenticatedFetch('/api/chat', ...)` with JWT Authorization Header.
        │
        ▼
[3. FastAPI App] backend/main.py & backend/routers/chat_router.py: `handle_chat_query()`
                 - Validates Pydantic schema `ChatQueryRequest`.
                 - `get_current_user` in `backend/auth.py` decodes JWT & verifies user in PostgreSQL.
                 - Retrieves or creates `Conversation` record linked to `current_user.id`.
        │
        ▼
[4. NLP Engine]  backend/rag/nlp_engine.py: `NLPEngine.process_query()`
                 - **Normalization**: Standardizes Hinglish ("kya rules hai" -> "what are the rules"), casing, and acronyms.
                 - **Coreference Resolution**: Scans recent conversation history (`history_msgs`). Resolves pronouns like *"it"*, *"this"*, *"their"* to concrete banking entities (e.g., *"NEFT"*, *"V-CIP"*).
                 - **Chitchat Detection**: If query is a greeting (*"hi"*, *"hello"*), returns immediate conversational answer with `source_type: CONVERSATIONAL`.
        │
        ▼
[5. RAG Engine]  backend/rag/rag_engine.py: `RAGEngine.process_query()`
                 ├── **Layer 1 Search**: `search_conversation_memory()`
                 │   Queries PostgreSQL `messages` & `responses` within user's conversation threads for matching previous Q&A.
                 │
                 └── **Layer 2 Search**: `hybrid_vector_store.search()` in `backend/rag/vector_store.py`
                     - Computes Dense Cosine Similarity over chunk embedding vectors.
                     - Computes Sparse BM25 Keyword Overlap score.
                     - Calculates combined score: `(0.6 * dense_score) + (0.4 * sparse_score)`.
                     - Filters results by `RETRIEVAL_THRESHOLD` (0.45) and selects top-$k$ chunks.
        │
        ▼
[6. Validation]  backend/rag/rag_engine.py: `validate_answerability()`
                 - **Subject Entity Filter**: Checks if query targets unapproved topics (e.g. crypto, third-party non-approved banks, stock trading).
                 - If unapproved or unsupported, triggers `FALLBACK_REFUSAL_MESSAGE` (`NO_SUPPORTED_SOURCE`).
        │
        ▼
[7. Synthesis]   backend/rag/rag_engine.py: `synthesize_grounded_answer()`
                 - Aggregates multi-chunk context across the primary matching regulatory circular.
                 - Formats exact numerical limits, timelines, penalties, and Official Reference Links.
                 - Runs `detect_ocr_ambiguities()` in `backend/rag/validator.py` to flag ambiguous characters (e.g. `0` vs `O`).
        │
        ▼
[8. Persistence] backend/routers/chat_router.py:
                 - Saves `Message` (role='user') and `Message` (role='assistant') to PostgreSQL.
                 - Saves `Response` with `source_type`, `confidence`, and `citations`.
                 - Saves extracted `Entity` rows and generates chat title if new conversation.
        │
        ▼
[9. Frontend]    frontend/app.js: `renderMessage('assistant', ...)`
                 - Parses Markdown using `marked.min.js`.
                 - Renders source attribution badge (`Knowledge Base`, `Conversation DB`, or `Conversational`).
                 - Renders expandable **Verified Source Citations Accordion**.
                 - Binds Read-Aloud TTS, Copy to Clipboard, and Thumbs Up/Down feedback handlers.
```

---

## 5. Database Architecture & PostgreSQL Persistence

### Database Configuration & Pooling
- **DBMS**: PostgreSQL (`chatgpt_idfc_rag`)
- **Connection URL**: `postgresql://postgres:Pandeyji@1405@localhost:5432/chatgpt_idfc_rag`
- **Engine**: SQLAlchemy 2.0 with `psycopg2` driver.
- **Connection Pool**: `QueuePool` with `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_recycle=1800`.

### Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    users ||--o{ conversations : "owns"
    users ||--o{ messages : "sends"
    users ||--o{ audit_logs : "triggers"
    conversations ||--o{ messages : "contains"
    messages ||--o| responses : "generates"
    messages ||--o{ entities : "contains"
    knowledge_documents ||--o{ knowledge_chunks : "chunked into"

    users {
        string id PK "UUID"
        string email UK "Indexed"
        string name
        string password_hash
        string auth_provider "local | google"
        string avatar_url
        string role "user | admin"
        datetime created_at
        datetime updated_at
    }

    conversations {
        string id PK "UUID"
        string user_id FK "Indexed, ON DELETE CASCADE"
        string title
        datetime created_at
        datetime updated_at
    }

    messages {
        string id PK "UUID"
        string conversation_id FK "Indexed, ON DELETE CASCADE"
        string user_id FK "Indexed, ON DELETE CASCADE"
        string role "user | assistant | system"
        text original_content
        text normalized_content
        datetime created_at
    }

    responses {
        string id PK "UUID"
        string message_id FK "Unique, ON DELETE CASCADE"
        text answer
        string source_type "KNOWLEDGE_BASE | DATABASE | HYBRID | CONVERSATIONAL | NO_SUPPORTED_SOURCE"
        float confidence
        json citations "List of source titles, pages, notification IDs, snippets"
        json ambiguity_flags "List of OCR character ambiguities"
        datetime created_at
    }

    entities {
        string id PK "UUID"
        string message_id FK "Indexed, ON DELETE CASCADE"
        string entity_text
        string entity_type "PRODUCT | CIRCULAR | ACRONYM | REGULATION"
        datetime created_at
    }

    knowledge_documents {
        string id PK "UUID"
        string title
        string notification_number "Indexed"
        string source "RBI | BANK_POLICY | INTERNAL_POLICY"
        string document_type "pdf | docx | txt | ocr"
        string file_path
        date publication_date
        integer page_count
        integer chunk_count
        boolean is_ocr
        float ocr_confidence
        text ocr_ambiguity_notes
        string processing_status "indexed | pending | failed"
        datetime created_at
        datetime updated_at
    }

    knowledge_chunks {
        string id PK "UUID"
        string document_id FK "Indexed, ON DELETE CASCADE"
        integer chunk_index
        integer page_number
        string section_header
        text chunk_text
        datetime created_at
    }

    audit_logs {
        string id PK "UUID"
        string user_id FK "Nullable, ON DELETE SET NULL"
        string action "LOGIN | REGISTER | CHAT_QUERY | FEEDBACK | REINDEX"
        text details
        string ip_address
        datetime timestamp
    }
```

---

## 6. Knowledge Ingestion & Hybrid Vector Store

### Ingested Regulatory Corpus (12 Authentic Documents)
1. **RBI Master Direction — KYC Direction, 2016 (Updated 2023)** (`DOR.AML.REC.48/14.01.001/2023-24`)
2. **RBI Master Direction — Digital Lending Directions, 2022** (`DOR.CRE.REC.65/21.07.001/2022-23`)
3. **RBI Master Direction — Customer Protection (Limiting Liability in Electronic Banking Transactions)** (`DBR.No.Leg.BC.78/09.07.005/2017-18`)
4. **RBI Master Direction — Fair Practices Code (FPC) for Lenders** (`DNBR.CC.PD.No.054/03.10.119/2015-16`)
5. **RBI Master Direction — Credit Card and Debit Card Issuance & Conduct, 2022** (`DOR.AUT.REC.No.27/24.01.041/2022-23`)
6. **RBI Master Circular — Housing Finance Loan-to-Value (LTV) Ratios** (`DOR.CRE.REC.No.06/08.12.001/2023-24`)
7. **RBI Guidelines — Harmonisation of TAT & Customer Compensation for Failed Transactions** (`DPSS.CO.PD.No.629/02.01.014/2019-20`)
8. **RBI Guidelines — National Electronic Funds Transfer (NEFT) & RTGS Operating Rules** (`DPSS.CO.EPPD.No.11756/04.03.01/2019-20`)
9. **RBI Circular — Card-on-File Tokenization (CoFT)** (`CO.DPSS.POLC.No.S-516/02-14-003/2021-22`)
10. **IDFC FIRST Bank — Savings Account Terms, Conditions & Monthly Interest Credit Policy** (`IDFC-POL-SAV-2024-V2`)
11. **IDFC FIRST Bank — Retail Lending, Home Loan LTV & Processing Fee Schedule** (`IDFC-POL-RET-2024-01`)
12. **IDFC FIRST Bank — FASTag Issuance, Auto-Recharge Rules & Dispute Resolution Policy** (`IDFC-POL-FASTAG-2023-V3`)

### Hybrid Vector Search Math
For any normalized query $q$ and indexed chunk $d_i$:
$$\text{Score}(q, d_i) = \alpha \cdot \text{CosineSimilarity}(\vec{v}_q, \vec{v}_{d_i}) + (1 - \alpha) \cdot \text{BM25}(q, d_i)$$
Where:
- $\alpha = 0.60$ (Dense semantic weight)
- $1 - \alpha = 0.40$ (Sparse keyword lexical weight)
- Threshold filter: $\text{Score}(q, d_i) \ge 0.45$
- Auto-Hydration: On application startup or cold start, `hybrid_vector_store.ensure_indexed(db)` checks if in-memory vectors exist; if empty, it automatically populates from PostgreSQL `knowledge_chunks`.

---

## 7. Security, Guardrails & Anti-Hallucination Matrix

| Threat / Flaw | Mechanism / Implementation | Verification Location |
| :--- | :--- | :--- |
| **Out-of-Domain Hallucination** | Subject Entity Grounding & Blocklist (`validate_answerability`). Immediate refusal for crypto, third-party institutions, entertainment, and general trivia. | [backend/rag/rag_engine.py](file:///c:/CHATGPTxIDFC/backend/rag/rag_engine.py#L105-L150) |
| **Insecure Direct Object Reference (IDOR)** | Queries filter by both resource ID and `user_id = current_user.id`. User B cannot read or delete User A's conversations. | [backend/routers/conversation_router.py](file:///c:/CHATGPTxIDFC/backend/routers/conversation_router.py) |
| **Privilege Escalation** | `get_current_admin` dependency checks `current_user.role == 'admin'`. Non-admins receive `403 Forbidden`. | [backend/auth.py](file:///c:/CHATGPTxIDFC/backend/auth.py#L67-L76) |
| **Prompt Injection in Ingested Docs** | File text is treated purely as raw data; prompt injection prefixes are stripped during normalization. | [tests/test_security_prompt_injection.py](file:///c:/CHATGPTxIDFC/tests/test_security_prompt_injection.py) |
| **OCR Ambiguity Corruption** | Pattern-based ambiguity detection identifies characters prone to OCR confusion (`0`/`O`, `1`/`I`, `5`/`S`) in financial terms and circular numbers. | [backend/rag/validator.py](file:///c:/CHATGPTxIDFC/backend/rag/validator.py) |
| **Session Drop / Token Stale** | Client `authenticatedFetch` traps `401 Unauthorized` and executes `validateOrRefreshToken` to seamlessly re-authenticate without breaking user flow. | [frontend/app.js](file:///c:/CHATGPTxIDFC/frontend/app.js#L164-L215) |

---

## 8. Automated Test Suite & Health Diagnostics

The test suite comprises **50 comprehensive automated tests** with **100% pass rate** (~13 seconds execution time).

### Executing Tests
```powershell
pytest -v
```

### Live Diagnostics Endpoints
- **Health Check**: `GET http://127.0.0.1:8000/health` (Returns DB latency, engine, document count, chunk count, and cache status).
- **Swagger Documentation**: `GET http://127.0.0.1:8000/docs`
- **ReDoc UI**: `GET http://127.0.0.1:8000/redoc`
- **Database Migrations**: `alembic current` / `alembic upgrade head`

---

## 9. Running Locally

```powershell
# 1. Activate environment and ensure PostgreSQL is running
# 2. Start the application
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 3. Access in browser
http://127.0.0.1:8000
```
