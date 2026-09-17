# Contributing to CHATGPTxIDFC

Thank you for your interest in contributing to **CHATGPTxIDFC**! This document provides guidelines and instructions for contributing to this project.

---

## Code of Conduct

Please treat all contributors with respect and maintain a professional and welcoming environment.

---

## Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Pandeyji1405-valuedx/CHATGPTxIDFC.git
cd CHATGPTxIDFC
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
Copy `.env.example` to `.env` and adjust the variables if needed:
```bash
cp .env.example .env
```

### 5. Run the Application
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## Testing Standards

All pull requests must pass the automated test suite with high coverage:

```bash
pytest tests/ -v
```

To run coverage report:
```bash
pytest --cov=backend --cov-report=term-missing tests/
```

### Key Architectural Guidelines
- **Zero Internet Chat Rule**: The user chat execution path must NEVER access external search engines or unverified internet data.
- **Grounding & Validation**: Ensure any factual answers are strictly backed by approved KB chunks or authenticated conversation history.
- **Multi-Account Isolation**: Verify that all database queries filter strictly by `user_id`.
- **OCR Ambiguity**: Maintain contextual ambiguity detection without producing false positives on standard English prose.

---

## Pull Request Workflow

1. Fork the repository and create a new feature branch: `git checkout -b feature/your-feature-name`.
2. Commit your changes with clear, descriptive commit messages.
3. Ensure all tests pass locally.
4. Push to your branch and submit a Pull Request to `main`.
5. Clearly describe your changes, the rationale, and include test verification evidence.

---

## Reporting Issues

If you find a bug or have a feature request, please open an Issue on GitHub with:
- A clear, descriptive title.
- Steps to reproduce the bug.
- Expected behavior vs. actual behavior.
- Relevant log output or screenshots.
