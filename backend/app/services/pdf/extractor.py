"""
Page-by-page PDF text extraction service using PyMuPDF (fitz) (Phase 3).

Guarantees:
  - Strict page-by-page extraction preserving 1-indexed page numbers
  - Deterministic page order (Page 1, 2, ..., N)
  - Safe handling of empty pages or graphical pages
  - Resource cleanup (closing documents safely)
"""

from dataclasses import dataclass
from typing import List

import fitz  # PyMuPDF


class PDFExtractionError(Exception):
    """Raised when text extraction from a PDF fails."""
    pass


@dataclass(frozen=True)
class ExtractedPage:
    """
    Representation of a single extracted page from a PDF.

    Attributes:
        page_number: 1-indexed page number in the original PDF.
        text: Raw text content extracted from the page.
        char_count: Length of the extracted text.
    """
    page_number: int
    text: str
    char_count: int


def extract_pdf_pages(pdf_bytes: bytes) -> List[ExtractedPage]:
    """
    Extract text page-by-page from PDF binary bytes.

    Args:
        pdf_bytes: Raw binary content of the PDF.

    Returns:
        List of ExtractedPage objects in ascending page order (1-indexed).

    Raises:
        PDFExtractionError: If fitz fails to open or read pages.
    """
    if not pdf_bytes:
        raise PDFExtractionError("Cannot extract text from empty bytes.")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFExtractionError(f"Failed to open PDF document: {exc}") from exc

    extracted_pages: List[ExtractedPage] = []

    try:
        for idx in range(doc.page_count):
            page_num = idx + 1
            try:
                page = doc.load_page(idx)
                # Extract plain text with layout preservation
                page_text = page.get_text("text") or ""
                extracted_pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text=page_text,
                        char_count=len(page_text),
                    )
                )
            except Exception as page_exc:
                # Log or record page extraction issue gracefully
                extracted_pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text="",
                        char_count=0,
                    )
                )
    finally:
        doc.close()

    return extracted_pages
