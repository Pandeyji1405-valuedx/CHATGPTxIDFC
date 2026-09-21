# IDFC Advisory Assistant — Governed RBI Compliance Platform & Conversational AI

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.2%20%7C%20TypeScript-61DAFB.svg?style=flat&logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8.3-646CFF.svg?style=flat&logo=vite&logoColor=white)](https://vitejs.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B%20%7C%20pgvector-336791.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7.0%2B-DC382D.svg?style=flat&logo=redis&logoColor=white)](https://redis.io)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.6-FF6F00.svg)](https://www.trychroma.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise regulatory compliance intelligence and banking conversational AI platform for IDFC FIRST Bank. Engineered with strict source-controlled knowledge grounding, multi-tier cost-saving caching, hybrid retrieval (ChromaDB + PostgreSQL FTS), BGE reranking, anti-hallucination guardrails, multi-account isolation, and a zero-internet answering policy.

---

## 🏛️ System Architecture

```text
                               ┌─────────────────────────────────────────┐
                               │             User / Client               │
                               │  (React 19 + TypeScript / Tailwind CSS) │
                               └────────────────────┬────────────────────┘
                                                    │ User Query / Audio Stream
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │       FastAPI Gateway & API v1          │
                               │  • JWT Auth & Argon2id RBAC             │
                               │  • PII Detection & Redaction            │
                               │  • Audit Trail Logging                  │
                               └────────────────────┬────────────────────┘
                                                    │
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │       4-Tier Cost-Saving Cache          │
                               ├─────────────────────────────────────────┤
                               │ Tier 1: Redis Exact Cache (<100ms)      │
                               │ Tier 2: PostgreSQL Exact Cache          │
                               │ Tier 3: pgvector Semantic Cache (>0.92) │
                               │ Tier 4: RAG Pipeline + Variant Warming  │
                               └────────────────────┬────────────────────┘
                                                    │ Cache Miss
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │         Two-Layer RAG Engine            │
                               ├────────────────────┬────────────────────┤
                               │ Layer 1: Conv RAG  │ Layer 2: KB RAG    │
                               │ Multi-turn Context │ Hybrid Dense/Sparse│
                               │ Pronoun Resolution │ BGE Reranker v2-m3 │
                               └──────────┬─────────┴──────────┬─────────┘
                                          │                    │
                                          └─────────┬──────────┘
                                                    │ Candidate Chunks
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │       Evidence Gate & Generator         │
                               │  • Circular & Policy Verification       │
                               │  • Grounded Google Gemini 3.6 Flash     │
                               │  • Hallucination Fallback Guard         │
                               └────────────────────┬────────────────────┘
                                                    │ Verified Grounded Answer
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │          Response & Citations           │
                               │  • Formatted Markdown Output            │
                               │  • Interactive Citation Badges          │
                               │  • OCR Character Ambiguity Flags        │
                               └─────────────────────────────────────────┘
```

---

## ✨ Key Capabilities & Features

1. **Enterprise React 19 Frontend**:
   - Built with Vite, TypeScript, and Tailwind CSS.
   - Clean dark/light themes tailored with IDFC Burgundy `#97144D` accents.
   - Dynamic conversation sidebar with search, auto-naming, and history grouping.
   - Admin Document Management portal with drag-and-drop upload and real-time ingestion status.
   - Account switcher with multi-tenant row-level data isolation.

2. **Hybrid Retrieval & Reranking Engine**:
   - **Dense Vector Search**: ChromaDB with Nomic Embed v1.5 (768-dim embeddings).
   - **Sparse Full-Text Search**: PostgreSQL FTS (`tsvector`) and TF-IDF fallback.
   - **BGE Reranker v2-m3**: High-precision semantic reranker with strict relevance score thresholds.

3. **4-Tier Cost-Saving Cache Cascade**:
   - **Tier 1 (Redis Exact Cache)**: Sub-100ms response for identical query strings.
   - **Tier 2 (PostgreSQL Exact Cache)**: Secondary database exact lookup.
   - **Tier 3 (PostgreSQL `pgvector` Semantic Cache)**: Cosine similarity search ($\ge 0.92$) for paraphrased queries.
   - **Tier 4 (Full RAG Pipeline)**: Executed on cache MISS, with automated **LLM Question Variant Generation** to pre-warm future paraphrases.

4. **Strict Grounding & Zero-Internet Policy**:
   - User chat requests **never** invoke external search engines or unverified internet data.
   - If reliable approved sources cannot be retrieved, the system returns a safe, controlled fallback.

5. **OCR & Banking Character Ambiguity Engine**:
   - Scanned PDF and image extraction with text-layer detection via PyMuPDF.
   - Scans for visually ambiguous characters in critical banking fields (`0` vs `O`, `1` vs `I`/`l`, `5` vs `S`, `2` vs `Z`, `8` vs `B`) in circular IDs, dates, and amounts.

6. **Enterprise Security & Compliance**:
   - Argon2id password hashing + JWT authentication.
   - Role-Based Access Control (RBAC: `ADMIN` for document upload/management; `USER` for chat).
   - PII Detection & Redaction middleware.
   - Complete Audit Trail Logging & User Feedback collection.

---

## 🛠️ Technology Stack

| Layer | Technology | Version / Model |
|---|---|---|
| **Frontend Framework** | React + TypeScript | 19.2 / TS 6.0 |
| **Frontend Build & Styling** | Vite + Tailwind CSS | 8.3 / 3.4 |
| **Backend Framework** | FastAPI + Uvicorn | 0.115 / 0.34 |
| **Backend Runtime** | Python | 3.11+ |
| **Database & ORM** | PostgreSQL 15+ + SQLAlchemy 2.0 (async) / SQLite | `asyncpg` / `psycopg2` |
| **Vector Cache Engine** | PostgreSQL `pgvector` | 0.5+ |
| **Vector Database** | ChromaDB | 0.6 |
| **Session Memory & Cache** | Redis | 7.0+ |
| **PDF Extraction** | PyMuPDF (`fitz`) | 1.25 |
| **Embeddings Model** | Nomic Embed v1.5 | `nomic-ai/nomic-embed-text-v1.5` (768-dim) |
| **Reranker Model** | BGE Reranker v2-m3 | `BAAI/bge-reranker-v2-m3` |
| **LLM Generator** | Google Gemini | `gemini-3.6-flash` |
| **Password Hashing** | Argon2id (`argon2-cffi`) / bcrypt | 23.1 |
| **JWT Security** | `python-jose[cryptography]` | 3.5 |

---

## 📂 Project Structure

```text
CHATGPTxIDFC/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── auth.py          # /register, /login, /me, /protected
│   │   │   ├── chat.py          # /message, /conversations, /conversations/{id}
│   │   │   ├── documents.py     # /upload (ADMIN async background), /documents, /versions
│   │   │   ├── feedback.py      # User feedback collection
│   │   │   └── health.py        # /health
│   │   ├── auth/                # JWT creation/decoding, Argon2id hashing, role dependencies
│   │   ├── core/config.py       # Pydantic Settings (DB, Redis, Gemini, Chroma, Models)
│   │   ├── db/                  # Async SQLAlchemy engine & session factory
│   │   ├── models/              # User, Document, DocumentVersion, Cache, Audit, Feedback ORM models
│   │   ├── schemas/             # Pydantic schemas for request/response payloads
│   │   └── services/
│   │       ├── auth_service.py  # Auth & user business logic
│   │       ├── cache/           # 4-tier cache cascade, Redis service, Contextualizer, Variants
│   │       ├── chunking/        # Deterministic page-aware chunker
│   │       ├── documents/       # Async document ingestion orchestrator & storage repo
│   │       ├── embeddings/      # Nomic Embed v1.5 embedding service
│   │       ├── pdf/             # PyMuPDF extractor, text cleaner, PDF validator
│   │       ├── rag/             # Hybrid retriever, BGE reranker, Evidence Gate, Gemini generator
│   │       ├── security/        # PII redaction, audit logging, rate limiter
│   │       └── vector_db/       # ChromaDB vector collection service
│   │   └── main.py              # FastAPI app initialization & middleware wiring
│   ├── alembic/                 # Database migrations (001 to 006)
│   ├── tests/                   # Pytest automated unit & integration tests
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── auth/                # Token management & authService
│   │   ├── components/          # Navbar, ProtectedRoute, HealthStatus, Sidebar, AppLayout
│   │   ├── context/             # AuthContext & useAuth hook
│   │   ├── pages/               # AdminDocumentsPage, ChatPage, LandingPage, Login, Register
│   │   ├── services/            # Axios client, chatService, documentService
│   │   └── types/               # TypeScript interfaces (chat, auth, documents)
│   ├── package.json
│   ├── vite.config.ts
│   └── .env.example
│
├── docs/                        # Architecture diagrams & implementation specs
├── tests/                       # Root test suite
├── .gitignore                   # Root ignore rules
└── README.md
```

---

## ⚙️ Quick Start & Setup Guide

### 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+ & npm 9+**
- **PostgreSQL 15+** (with `pgvector` extension) or SQLite
- **Redis 7.0+** (Optional / Fallbacks to In-Memory LRU)

### 2. Backend Setup

```powershell
# Navigate to project root or backend
cd c:\CHATGPTxIDFC

# Create & activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements.txt

# Configure environment variables
Copy-Item .env.example .env
# Edit .env and supply your DATABASE_URL, REDIS_URL, and GEMINI_API_KEY

# Run database migrations
alembic upgrade head

# Start FastAPI dev server
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

- Backend API: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`

### 3. Frontend Setup

```powershell
# Open a new terminal and navigate to frontend
cd frontend

# Install dependencies
npm install

# Create environment configuration
Copy-Item .env.example .env

# Start Vite development server
npm run dev
```

- Frontend client runs at: `http://localhost:5173`

---

## 🧪 Automated Testing

Run the full automated test suite:

```powershell
# Run backend tests
pytest backend/tests/ -v

# Run root tests
pytest tests/ -v
```

---

## 🔒 Security & Compliance

- **No Hardcoded Secrets**: All keys, passwords, and tokens are loaded strictly via environment variables.
- **Role-Based Guards**: Document upload requires the `ADMIN` role. Regular users can only access chat and view approved documents.
- **PII Protection**: Dynamic redaction strips sensitive personal identifiers prior to prompt assembly.
- **Audit Traceability**: Immutable database audit logs record user actions, logins, uploads, and queries with tenant correlation.

---

## 📄 License

Internal Tool — Property of IDFC Bank. All rights reserved.
