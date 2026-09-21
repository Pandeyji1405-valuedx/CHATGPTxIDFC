"""
PDF file validation service (Phase 3).

Verifies:
  - File extension is .pdf
  - File size does not exceed maximum configured limit
  - Magic byte header contains valid %PDF- signature
  - PyMuPDF (fitz) can open and parse the document structure
  - Document contains at least one page and is not password-protected
"""

import io
from typing import Tuple

import fitz  # PyMuPDF


def validate_pdf_bytes(
    content: bytes,
    filename: str,
    max_size_bytes: int = 52428800,  # 50 MB
) -> Tuple[bool, str | None]:
    """
    Validate uploaded PDF content against security and structure requirements.

    Args:
        content: Raw binary content of the uploaded file.
        filename: Original filename submitted by client.
        max_size_bytes: Maximum allowed file size in bytes.

    Returns:
        (True, None) if valid, or (False, "error message") if invalid.
    """
    # 1. Check filename extension
    if not filename.lower().endswith(".pdf"):
        return False, "File must have a .pdf extension."

    # 2. Check non-empty content
    if not content or len(content) == 0:
        return False, "PDF file is empty (0 bytes)."

    # 3. Check file size limit
    if len(content) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        return False, f"File size ({len(content) / (1024 * 1024):.1f} MB) exceeds maximum limit ({max_mb:.0f} MB)."

    # 4. Check PDF magic bytes (%PDF- in first 1024 bytes)
    header = content[:1024]
    if b"%PDF-" not in header:
        return False, "File is not a valid PDF document (missing %PDF- header signature)."

    # 5. Verify PDF structure with PyMuPDF
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        return False, f"Corrupt or unreadable PDF document: {exc}"

    try:
        if doc.is_encrypted:
            # Try empty password; if fails, reject encrypted PDF
            if not doc.authenticate(""):
                return False, "Password-protected or encrypted PDFs are not supported."

        if doc.page_count < 1:
            return False, "PDF contains no pages."

    finally:
        doc.close()

    return True, None
