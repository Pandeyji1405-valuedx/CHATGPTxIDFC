# IDFC Advisory Assistant — Governed RBI Compliance Platform

> **Enterprise Regulatory Intelligence & RAG Chatbot Platform for IDFC Bank.**  
> Powered by FastAPI, React + TypeScript, PostgreSQL + `pgvector`, ChromaDB, Redis, Nomic Embed v1.5, BGE Reranker v2-m3, and Google Gemini 3.6 Flash.

---

## 🌟 Overview

**IDFC Advisory Assistant** is an end-to-end, production-grade regulatory compliance platform designed to assist banking professionals in querying, verifying, and navigating official Reserve Bank of India (RBI) Master Circulars and guidelines with zero hallucination risk and sub-second cached responses.

### Key Capabilities

- 📄 **Async Background Document Ingestion**: Process large regulatory PDF circulars asynchronously without HTTP request timeouts while preserving 10-step versioning, SHA-256 fingerprinting, PyMuPDF page-aware chunking, Nomic Embed v1.5 vector indexing, and explicit supersession tracking.
- 🔍 **Hybrid Retrieval Engine**: Combines **Dense Vector Search** (ChromaDB + Nomic Embed 768-dim embeddings) and **Sparse Full-Text Search** (PostgreSQL FTS `tsvector`).
- 🎯 **BGE Reranker & Evidence Gate**: Re-ranks candidates using `BAAI/bge-reranker-v2-m3` and enforces a confidence threshold to decline out-of-scope queries cleanly.
- ⚡ **4-Tier Cost-Saving Cache Cascade**:
  - **Tier 1 (Redis Exact Cache)**: Sub-100ms response for identical query strings.
  - **Tier 2 (PostgreSQL Exact Cache)**: Secondary database exact lookup.
  - **Tier 3 (PostgreSQL `pgvector` Semantic Cache)**: Cosine similarity search ($\ge 0.92$) for paraphrased queries (~700ms).
  - **Tier 4 (Full RAG Pipeline)**: Executed on cache MISS, with automated **LLM Question Variant Generation** (pre-warming future paraphrases).
- 🧠 **Multi-Turn LLM Contextualization**: Uses Gemini 3.6 Flash to rewrite short follow-up questions (e.g., *"What about a matured SHG?"*) against 10 turns of conversation context into complete canonical queries.
- 🔐 **Enterprise Security & Compliance**:
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
| **Database & ORM** | PostgreSQL 15+ + SQLAlchemy 2.0 (async) | 2.0 / `asyncpg` |
| **Vector Cache Engine** | PostgreSQL `pgvector` | 0.5+ |
| **Vector Database** | ChromaDB | 0.6 |
| **Session Memory & Cache** | Redis | 7.0+ |
| **PDF Extraction** | PyMuPDF (`fitz`) | 1.25 |
| **Embeddings Model** | Nomic Embed v1.5 | `nomic-ai/nomic-embed-text-v1.5` (768-dim) |
| **Reranker Model** | BGE Reranker v2-m3 | `BAAI/bge-reranker-v2-m3` |
| **LLM Generator** | Google Gemini | `gemini-3.6-flash` |
| **Password Hashing** | Argon2id (`argon2-cffi`) | 23.1 |
| **JWT Security** | `python-jose[cryptography]` | 3.5 |

---

## 📂 Project Structure

```
IDFC_ChatBot/
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
│   │   ├── components/          # Navbar, ProtectedRoute, HealthStatus, Citation Modal
│   │   ├── context/             # AuthContext & useAuth hook
│   │   ├── pages/               # AdminDocumentsPage, ChatPage, LandingPage, Login, Register
│   │   ├── services/            # Axios client, chatService, documentService
│   │   └── types/               # TypeScript interfaces (chat, auth, documents)
│   ├── package.json
│   └── .env.example
│
├── docs/                        # Architecture diagrams & implementation specs
├── .gitignore                   # Root ignore rules
└── README.md
```

---

## ⚙️ Quick Start & Setup Guide

### 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+ & npm 9+**
- **PostgreSQL 15+** (with `pgvector` extension enabled)
- **Redis 7.0+**

### 2. Database Setup

```sql
CREATE DATABASE idfc_chatbot_db;
\c idfc_chatbot_db;
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Backend Setup

```powershell
# Navigate to backend
cd backend

# Create & activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Create environment configuration
Copy-Item .env.example .env
# Edit .env and supply your DATABASE_URL, REDIS_URL, and GEMINI_API_KEY

# Run database migrations
alembic upgrade head

# Start FastAPI dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend server will run at: `http://localhost:8000`  
Interactive API Docs (Swagger): `http://localhost:8000/docs`

### 4. Frontend Setup

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

The frontend client will run at: `http://localhost:5173`

---

## 🧪 Automated Testing

To run the complete automated test suite:

```powershell
cd backend
.venv\Scripts\Activate.ps1
pytest -v
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
