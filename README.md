# CHATGPTxIDFC — Production Banking Conversational AI

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Coverage](https://img.shields.io/badge/Coverage-85%25-brightgreen.svg)](tests/)
[![Tests](https://img.shields.io/badge/Tests-35%20Passed-success.svg)](tests/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Architecture: Two--Layer%20RAG](https://img.shields.io/badge/Architecture-Two--Layer%20RAG-darkred.svg)](architecture.md)

A production-quality banking conversational AI assistant engineered with a modern ChatGPT-style user experience, strict source-controlled knowledge grounding, two-layer RAG architecture, OCR with character ambiguity detection, multi-account isolation, and a zero-internet answering policy.

---

## 🏛️ System Architecture

```text
                               ┌─────────────────────────────────────────┐
                               │             User / Client               │
                               │  (ChatGPT UI / Voice / Multi-Account)   │
                               └────────────────────┬────────────────────┘
                                                    │ User Query / Voice Input
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │         FastAPI Chat Controller         │
                               └────────────────────┬────────────────────┘
                                                    │
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │               NLP Engine                │
                               │  • Hinglish Normalization               │
                               │  • Entity & Intent Extraction           │
                               │  • Pronoun & Coreference Resolution     │
                               └────────────────────┬────────────────────┘
                                                    │ Resolved Query
                                                    ▼
                             ┌─────────────────────────────────────────────┐
                             │             Two-Layer RAG Engine            │
                             ├──────────────────────┬──────────────────────┤
                             │       Layer 1        │       Layer 2        │
                             │   Conversation RAG   │    Banking KB RAG    │
                             │ (User Chat History)  │ (16+ RBI Directions) │
                             └──────────┬───────────┴──────────┬───────────┘
                                        │                      │
                                        └───────────┬──────────┘
                                                    │ Retrieved Chunks & Context
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │            Grounding Validator          │
                               │  • Circular Number & Policy Check       │
                               │  • Numeric / Amount Verification        │
                               │  • Conflict Detection (Source A vs B)   │
                               │  • Zero-Internet Fallback Guard         │
                               └────────────────────┬────────────────────┘
                                                    │ Verified Grounded Answer
                                                    ▼
                               ┌─────────────────────────────────────────┐
                               │           Response & Citations          │
                               │  • Formatted Markdown Output            │
                               │  • Interactive Citation Badges          │
                               │  • OCR Character Ambiguity Flags        │
                               └─────────────────────────────────────────┘
```

---

## ✨ Key Features

1. **ChatGPT-like User Interface**:
   - Modern sleek banking theme (IDFC burgundy `#97144D` & obsidian `#0d1117` palette, glassmorphism, Inter typography).
   - Sidebar conversation management with date grouping (*Today, Yesterday, Previous 7 Days*), search, inline renaming, and deletion.
   - Auto-generated conversation titles based on query intent.
   - Responsive message stream with markdown formatting, copy button, and interactive citation badges.

2. **Two-Layer RAG System**:
   - **Layer 1 (Conversation DB RAG)**: Searches historical user interactions, performs coreference/pronoun resolution (*"its limit"* $\rightarrow$ *"NEFT limit"*, *"his age"* $\rightarrow$ *"Sachin Tendulkar's age"*), and extracts banking entities.
   - **Layer 2 (Banking Knowledge Base RAG)**: Hybrid TF-IDF / dense vector retrieval + exact circular matching over 16+ curated official RBI Master Directions and IDFC FIRST Bank policies.

3. **Strict Zero-Internet Answering Policy**:
   - Web access is strictly restricted to administrative knowledge base ingestion.
   - User chat requests **never** invoke external search engines or unverified internet data.
   - If reliable approved sources cannot be retrieved, the system returns a controlled fallback:
     > *"I couldn't find sufficient verified information in the approved knowledge base or your conversation history to answer this accurately."*

4. **OCR & Banking Character Ambiguity Engine**:
   - Scanned PDF and image extraction with text-layer detection.
   - Scans for visually ambiguous characters in critical banking fields (`0` vs `O`, `1` vs `I`/`l`, `5` vs `S`, `2` vs `Z`, `8` vs `B`) in circular IDs, dates, and amounts.
   - Flags ambiguity warnings in citations for human verification against original documents.

5. **Multi-Account Authentication & Data Isolation**:
   - JWT tokens with bcrypt password hashing + Google OAuth integration.
   - Account Switcher: Manage and switch between multiple logged-in accounts instantly.
   - Strict application-level row isolation preventing any cross-user conversation crosstalk (`WHERE user_id == current_user.id`).

6. **Speech-to-Text (STT) & Text-to-Speech (TTS)**:
   - Voice input via Web Speech API with an editable review bar before query submission.
   - "🔊 Read Aloud" synthesis on assistant responses.

7. **Admin Knowledge Base Portal**:
   - Document upload for PDF, DOCX, TXT, CSV, and images.
   - Page-by-page OCR inspection, chunk counts, ambiguity notes, and one-click re-indexing.

---

## 📁 Repository Structure

```text
CHATGPTxIDFC/
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI Workflow
├── backend/
│   ├── main.py                  # FastAPI server & static file mounting
│   ├── config.py                # Environment & tuning settings
│   ├── database.py              # SQLite with WAL mode & session manager
│   ├── models.py                # SQLAlchemy ORM models
│   ├── schemas.py               # Pydantic v2 validation models
│   ├── auth.py                  # JWT auth, password hashing & dependencies
│   ├── routers/
│   │   ├── auth_router.py       # Auth endpoints (register, login, google, me)
│   │   ├── chat_router.py       # Main 2-Layer RAG chat endpoint
│   │   ├── conversations_router.py # Conversation CRUD & search
│   │   ├── admin_router.py      # Knowledge Base admin portal endpoints
│   │   └── speech_router.py     # Speech STT & TTS endpoints
│   ├── rag/
│   │   ├── nlp_engine.py        # NLP, entity extraction & pronoun resolution
│   │   ├── vector_store.py      # Hybrid vector store (TF-IDF + Cosine + Exact boost)
│   │   ├── validator.py         # Grounding & anti-hallucination fact validator
│   │   └── rag_engine.py        # Two-Layer RAG pipeline coordinator
│   └── ingestion/
│       ├── extractor.py         # Multi-format document text & image extractor
│       ├── ocr_engine.py        # OCR & character ambiguity detection
│       ├── chunker.py           # Semantic paragraph & section chunker
│       └── seed_rbi_kb.py       # Curated 16+ RBI & IDFC knowledge seeder
├── frontend/
│   ├── index.html               # ChatGPT-style UI
│   ├── style.css                # Sleek dark/light banking theme
│   └── app.js                   # Client state, voice & API coordinator
├── tests/
│   ├── conftest.py              # Test database and client fixtures
│   ├── test_auth.py             # Auth & Google OAuth tests
│   ├── test_isolation.py        # Multi-account isolation tests
│   ├── test_conversation_rag.py # Pronoun resolution & Hinglish tests
│   ├── test_kb_rag.py           # RBI circulars & regulations RAG tests
│   ├── test_ocr_ambiguity.py    # OCR ambiguity detection tests
│   ├── test_hallucination_guard.py # Zero-internet & fallback tests
│   ├── test_security_prompt_injection.py # Security & RBAC tests
│   └── test_speech.py           # STT & TTS endpoint tests
├── architecture.md              # In-depth technical system specifications
├── CONTRIBUTING.md              # Contribution guidelines & workflows
├── SECURITY.md                  # Security policies & airgap guarantees
├── CHANGELOG.md                 # Release notes & version history
├── LICENSE                      # MIT License
├── pyproject.toml               # Python project configuration
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment variable templates
```

---

## 🚀 Quickstart & Execution

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/Pandeyji1405-valuedx/CHATGPTxIDFC.git
cd CHATGPTxIDFC

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

### 4. Run the Application

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser at: **`http://127.0.0.1:8000`**

#### Default Demo Credentials:
- **Customer User**: `customer@idfcbank.com` / `Customer@123`
- **Admin User**: `admin@idfcbank.com` / `Admin@12345`

---

## 🧪 Automated Testing

Run the full automated test suite (35 unit and integration tests):

```bash
pytest tests/ -v
```

Generate a test coverage report:

```bash
pytest --cov=backend --cov-report=term-missing tests/
```

---

## 📄 Documentation Links

- [Architecture Specification](architecture.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)

---

## 🛡️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
