# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-09-17

### Added
- **ChatGPT-Style UI**: Modern dark obsidian & IDFC burgundy aesthetic with conversation sidebar, message streaming, citation badges, and voice synthesis.
- **Two-Layer RAG Engine**:
  - Layer 1: Conversation Database RAG with pronoun/coreference resolution and Hinglish translation.
  - Layer 2: Banking Knowledge Base RAG with hybrid TF-IDF/dense vector retrieval and exact circular ID matching.
- **OCR Engine with Banking Ambiguity Detection**: Multi-format document parser (PDF, DOCX, TXT, CSV, images) and character ambiguity scanner (`0/O`, `1/I/l`, `5/S`, `2/Z`, `8/B`).
- **Zero-Internet Answering Policy & Grounding**: Strict fallback for unverified queries with fact verification against retrieved context.
- **Multi-Account Switching & Row Isolation**: Instant JWT account switching and strict per-user database row isolation.
- **Speech-to-Text & Text-to-Speech**: Speech recognition with editable review bar and browser speech synthesis.
- **Admin KB Portal**: Document ingestion, OCR inspector, chunk viewer, and one-click re-indexing.
- **Automated Test Suite**: 35 comprehensive unit and integration tests with 85% code coverage.
