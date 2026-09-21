"""
Local filesystem storage service for uploaded RBI regulatory PDFs (Phase 3).
"""

import os
import re
from typing import Optional

from app.core.config import get_settings

settings = get_settings()


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and unsafe characters."""
    base = os.path.basename(filename)
    clean = re.sub(r"[^\w\.-]", "_", base)
    return clean or "document.pdf"


def save_pdf_file(
    content: bytes,
    file_hash: str,
    original_filename: str,
    base_dir: Optional[str] = None,
) -> str:
    """
    Save raw PDF bytes to disk partitioned by hash prefix.

    Args:
        content: Binary PDF bytes.
        file_hash: SHA-256 hex string.
        original_filename: Original client filename.
        base_dir: Optional override for storage directory.

    Returns:
        Absolute or relative filesystem path of the saved file.
    """
    storage_root = base_dir or settings.STORAGE_DIR
    sub_dir = os.path.join(storage_root, file_hash[:2])
    os.makedirs(sub_dir, exist_ok=True)

    safe_name = _sanitize_filename(original_filename)
    target_path = os.path.join(sub_dir, f"{file_hash}_{safe_name}")

    if not os.path.exists(target_path):
        with open(target_path, "wb") as f:
            f.write(content)

    return os.path.abspath(target_path)


def get_pdf_bytes(storage_path: str) -> bytes:
    """Read stored PDF file bytes from disk."""
    if not os.path.exists(storage_path):
        raise FileNotFoundError(f"Stored PDF file not found at: {storage_path}")
    with open(storage_path, "rb") as f:
        return f.read()
