# System Architecture & Technical Specifications
## Banking RAG Conversational AI Application (CHATGPTxIDFC)

### 1. High-Level Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                                 FRONTEND LAYER                                    |
|  - Modern ChatGPT-style Web App (Vite + React / Modern Vanilla SPA)               |
|  - Multi-Account Switcher & Profile Drawer                                        |
|  - Interactive Speech-to-Text (STT) & Text-to-Speech (TTS) Engine                 |
|  - Real-time Streaming, Source Citations & Banking OCR Ambiguity Indicators       |
|  - Admin Knowledge Base Management, Ingestion Status & OCR Text Inspection        |
+------------------------------------------+----------------------------------------+
                                           | HTTPS / REST / SSE Stream
                                           v
+-----------------------------------------------------------------------------------+
|                                BACKEND API LAYER                                  |
|  FastAPI + Async Python 3.12 Architecture                                          |
|  - Security & Auth (JWT, Bcrypt, Google OAuth Flow, Rate Limiting, Audit Logs)    |
|  - Session & User-Level Row Isolation                                             |
|  - RESTful Endpoints + SSE Streaming Responses                                    |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                            NLP & QUERY RESOLUTION ENGINE                          |
|  - Multilingual & Hinglish Normalizer                                             |
|  - Intent Classifier & Entity Extractor (NER for Banking: KYC, NEFT, RTGS, etc.)  |
|  - Pronoun & Coreference Resolution via Conversation Context Memory               |
|  - Dual Query Output: Original Query + Normalized Disambiguated Query             |
+------------------------------------------+----------------------------------------+
                                           |
                    +----------------------+----------------------+
                    |                                             |
                    v                                             v
+---------------------------------------+   +---------------------------------------+
|  RAG LAYER 1: CONVERSATION DB RAG     |   |  RAG LAYER 2: BANKING KNOWLEDGE RAG   |
|  - Conversation Session History       |   |  - Approved RBI Master Directions     |
|  - User Conversational Memory         |   |  - IDFC FIRST Bank Policy Repository  |
|  - Previous Q&A Semantic Retrieval    |   |  - Hybrid Search (BM25 + Dense Vector)|
|  - Fast Cache & Direct Answer Match   |   |  - Strict Confidence Threshold Filter |
+---------------------------------------+   +---------------------------------------+
                    |                                             |
                    +----------------------+----------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                        RESPONSE GENERATION & VALIDATION                           |
|  - Grounded LLM Generation (Strict Zero External Web Access Policy)               |
|  - Post-Generation Fact Verification (Numbers, Dates, Circulars, Percentages)     |
|  - OCR Character Ambiguity Resolution (0 vs O, 1 vs I/l, 5 vs S, 8 vs B)          |
|  - Controlled Fallback for Insufficient / Low-Confidence Information              |
|  - Source Attribution & Citation Metadata Builder                                |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                           STORAGE & VECTOR DATABASE                               |
|  - Relational Database (SQLite / SQLAlchemy) with Strict Per-User Data Isolation  |
|  - Vector Store (Vector Embeddings + Cosine Index / BM25 Inverted Index)          |
|  - Secure Document Repository (PDFs, DOCX, TXT, Scanned Imgs, OCR Layer)          |
+-----------------------------------------------------------------------------------+
```

---

### 2. Core Architectural Components

#### 2.1 Two-Layer Retrieval-Augmented Generation (RAG) System
1. **Layer 1 — Conversation Database RAG**:
   - Searches historical interactions and user conversational memory.
   - Coreference/pronoun resolution resolves terms like *"its transaction limit"* $\rightarrow$ *"NEFT transaction limit"*.
   - If an unambiguous, recent conversation answer exists with high confidence, it returns it directly as `DATABASE` source.

2. **Layer 2 — Banking Knowledge Base RAG**:
   - Indexes official RBI master directions, circulars, notifications, and IDFC FIRST Bank policy documentation.
   - **Hybrid Retrieval**: Combines exact token / regex matching (for circular numbers e.g. `RBI/2023-24/105`, percentages, monetary limits) with dense cosine semantic embeddings.
   - **Confidence Thresholding**: If max similarity score is below `0.65`, the system refuses to speculate and returns a controlled `NO_SUPPORTED_SOURCE` notice.

#### 2.2 Strict Zero-Internet Answering & Hallucination Guardrails
- **No Internet Search for Answering**: Web access is strictly limited to initial administrative document ingestion. Answering relies 100% on the internal knowledge base.
- **LLM as Grounded Synthesizer**: The prompt strictly confines the model to provided context chunks.
- **Post-Generation Verification Engine**: Verifies all numerical values, interest rates, penalty rules, circular references, and dates against the source chunks before final delivery.

#### 2.3 Intelligent OCR & Banking Character Ambiguity Engine
- Automatically checks if PDF pages are native text or scanned raster images.
- Implements OCR extraction using Python image processing and text extraction.
- Detects ambiguous banking characters (`0` vs `O`, `1` vs `I`/`l`, `5` vs `S`, `2` vs `Z`, `8` vs `B`) in circular IDs, dates, account numbers, and rates.
- Flags ambiguities in response citations so users are alerted to verify critical digits against the original scanned document.

#### 2.4 Multi-Account Authentication & User Isolation
- JWT token-based authentication with Bcrypt password hashing.
- Google OAuth 2.0 integration + developer authentication simulation.
- Multi-account switching: Frontend manages tokens for multiple logged-in accounts without losing conversation state or leaking cross-user history.
- Row-Level Security (RLS) principle: Every conversation, message, and memory query requires explicit `user_id` verification.

#### 2.5 Admin Knowledge Base Management
- Document ingestion pipeline supporting PDF, DOCX, TXT, CSV, PNG, JPG.
- Admin dashboard to inspect ingestion status, page counts, OCR confidence, extracted text, and trigger re-indexing.

---

### 3. Database Schema

```sql
-- Users Table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    auth_provider TEXT DEFAULT 'local', -- 'local', 'google'
    avatar_url TEXT,
    role TEXT DEFAULT 'user',           -- 'user', 'admin'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversations Table
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Messages Table
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,                -- 'user', 'assistant', 'system'
    original_content TEXT NOT NULL,
    normalized_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Responses & Source Citations Table
CREATE TABLE responses (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    answer TEXT NOT NULL,
    source_type TEXT NOT NULL,         -- 'DATABASE', 'KNOWLEDGE_BASE', 'DATABASE + KNOWLEDGE_BASE', 'NO_SUPPORTED_SOURCE'
    confidence REAL DEFAULT 1.0,
    citations_json TEXT,               -- JSON array of document titles, notification numbers, pages, snippets
    ambiguity_flags_json TEXT,         -- JSON array of character ambiguity warnings (e.g., 0 vs O)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Knowledge Base Documents Table
CREATE TABLE knowledge_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    notification_number TEXT,
    publication_date TEXT,
    effective_date TEXT,
    source TEXT NOT NULL DEFAULT 'RBI', -- 'RBI', 'IDFC_FIRST_BANK', 'INTERNAL_POLICY'
    source_url TEXT,
    document_type TEXT NOT NULL,        -- 'pdf', 'scanned_pdf', 'docx', 'txt', 'image'
    file_path TEXT,
    version TEXT DEFAULT '1.0',
    checksum TEXT NOT NULL,
    status TEXT DEFAULT 'indexed',      -- 'pending', 'processing', 'indexed', 'failed'
    page_count INTEGER DEFAULT 1,
    is_ocr BOOLEAN DEFAULT FALSE,
    ocr_confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Knowledge Base Chunks & Vector Store Table
CREATE TABLE knowledge_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    page_number INTEGER DEFAULT 1,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding_json TEXT,                -- Vector embedding serialized as JSON array
    metadata_json TEXT,                 -- Header, section, notification references
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resolved Entities Table
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    message_id TEXT REFERENCES messages(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,          -- 'REGULATION', 'BANKING_SERVICE', 'LIMIT', 'ORGANIZATION'
    entity_value TEXT NOT NULL,
    canonical_value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Logs Table
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 4. API Specification

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Register new user with email and password |
| `POST` | `/api/auth/login` | Login user, return JWT bearer token |
| `POST` | `/api/auth/google` | Google OAuth authentication handler |
| `GET` | `/api/auth/me` | Fetch authenticated user profile |
| `GET` | `/api/conversations` | List user's conversations (sorted by updated_at) |
| `POST` | `/api/conversations` | Create new conversation session |
| `GET` | `/api/conversations/{id}` | Get full conversation messages & citations |
| `PUT` | `/api/conversations/{id}` | Rename conversation title |
| `DELETE` | `/api/conversations/{id}` | Delete conversation |
| `GET` | `/api/conversations/search` | Search across past conversation titles, queries, and answers |
| `POST` | `/api/chat` | Main RAG chat endpoint (supporting streaming & source attribution) |
| `POST` | `/api/speech/transcribe` | Audio file speech-to-text transcription fallback |
| `POST` | `/api/speech/synthesize` | Text-to-speech audio synthesis fallback |
| `GET` | `/api/admin/documents` | List knowledge base documents & ingestion status |
| `POST` | `/api/admin/documents/upload` | Upload & ingest document (PDF, scanned PDF, DOCX, TXT, image) |
| `DELETE` | `/api/admin/documents/{id}` | Remove knowledge document and re-index |
| `POST` | `/api/admin/reindex` | Trigger vector & hybrid index rebuild |

---

### 5. Curated RBI Banking Knowledge Base Dataset
The initial repository includes 15+ comprehensive official RBI guidelines & circulars:
1. **RBI Master Direction on Know Your Customer (KYC) Direction, 2016 (Updated 2023)** — CDD, V-CIP, OVD, Risk Categorization.
2. **RBI Procedural Guidelines for National Electronic Funds Transfer (NEFT)** — 24x7 Settlement, Limits, Reversal Timelines.
3. **RBI Guidelines on Real Time Gross Settlement (RTGS) System** — Minimum threshold (₹2 Lakhs), operating hours, charges.
4. **RBI Master Direction on Regulatory Framework for Digital Lending (2022)** — RE/LSP responsibilities, Key Fact Statement (KFS), Cooling-off period.
5. **RBI Master Direction on Cyber Security Framework in Banks** — Incident reporting, 2FA, SOC monitoring.
6. **RBI Circular on Customer Protection – Limiting Liability in Unauthorised Electronic Banking Transactions** — Zero liability vs limited liability timelines.
7. **RBI Master Direction on Priority Sector Lending (PSL) – Targets and Classification** — 40% ANBC target, Agriculture, MSME sub-targets.
8. **RBI Master Direction – Credit Card and Debit Card – Issuance and Conduct Directions, 2022** — Billing cycle, unsolicited cards, late payment charges.
9. **RBI Guidelines on Fair Practices Code for Lenders** — Transparency, loan sanction letters, recovery practices.
10. **RBI Master Direction on Interest Rate on Rupee Deposits** — Senior citizen differential rates, premature withdrawal penalty rules.
11. **RBI Master Direction on Housing Finance & Loan-to-Value (LTV) Ratios** — LTV caps (80%/90%), risk weights.
12. **RBI Integrated Ombudsman Scheme, 2021** — Turnaround times (30 days), appeal process, compensation.
13. **IDFC FIRST Bank Savings Account & Deposit Rules** — Monthly interest credit, zero fee banking features.
14. **IDFC FIRST Bank Digital & FASTag Guidelines** — Minimum balance, recharge rules, dispute resolution.
15. **RBI Circular on Microfinance Loans Direction, 2022** — Household income assessment, collateral-free loans.
