"""
PII Detection & Masking Service (Phase 7).

Responsibilities:
  - Detect personal sensitive information (PAN, Aadhaar, Phone, Email, Credit Cards, Secrets).
  - Mask / redact PII from operational logs, audit metadata, and telemetry.
  - Distinguish original private chat records (stored intact in DB for user view) from
    sanitized logs/audit records.
  - Pure, deterministic, regex-based, highly testable.
"""

import re
from typing import Any, Dict, List, Tuple

# Compiled Regex Patterns
_PII_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    # Secrets / Tokens / Passwords (check first to avoid partial matches by lower rules)
    (
        "SECRET",
        re.compile(
            r"(?i)\b(password|secret|api[_\-]?key|bearer[_\-]?token|access[_\-]?token|jwt[_\-]?token)\b\s*[:=]\s*[\"']?([^\s\"',}]+)[\"']?",
        ),
        r"\1=[REDACTED_SECRET]",
    ),
    # JWT Tokens (eyJ...)
    (
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "[REDACTED_JWT]",
    ),
    # Indian PAN Card: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F)
    (
        "PAN",
        re.compile(r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]{1}\b"),
        "[REDACTED_PAN]",
    ),
    # Indian Aadhaar Card: 12 digits starting with 2-9, optional spaces (e.g. 3675 9834 6012)
    (
        "AADHAAR",
        re.compile(r"\b[2-9]{1}\d{3}\s?\d{4}\s?\d{4}\b"),
        "[REDACTED_AADHAAR]",
    ),
    # Email addresses
    (
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    # Indian Mobile Numbers: +91 or 0 prefix optional, 10 digits starting with 6-9
    (
        "PHONE",
        re.compile(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b"),
        "[REDACTED_PHONE]",
    ),
    # Credit Card Numbers: 13-16 digits with optional dashes/spaces
    (
        "CARD",
        re.compile(r"\b(?:\d[ \-]*?){13,16}\b"),
        "[REDACTED_CARD]",
    ),
]


class PIIService:
    """
    Deterministic PII detection and redaction utility.
    """

    @staticmethod
    def redact_text(text: str) -> str:
        """
        Redact sensitive PII and secrets from a string.

        Args:
            text: Input string.

        Returns:
            Sanitized string with PII replaced by placeholders.
        """
        if not text:
            return text

        sanitized = text
        for category, pattern, replacement in _PII_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    @staticmethod
    def detect_pii(text: str) -> List[str]:
        """
        Detect categories of PII present in a string.

        Returns:
            List of detected PII categories (e.g. ['PAN', 'EMAIL']).
        """
        if not text:
            return []

        detected = []
        for category, pattern, _ in _PII_PATTERNS:
            if pattern.search(text):
                detected.append(category)
        return list(set(detected))

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively redact PII and secrets from keys and values in a dictionary.

        Args:
            data: Input dictionary.

        Returns:
            New dictionary with sanitized string values and redacted sensitive keys.
        """
        if not isinstance(data, dict):
            return data

        sensitive_keys = {
            "password", "secret", "token", "api_key", "jwt", "authorization",
            "access_token", "refresh_token", "credit_card", "pan", "aadhaar"
        }

        sanitized = {}
        for key, val in data.items():
            key_lower = str(key).lower()
            if any(s in key_lower for s in sensitive_keys):
                sanitized[key] = "[REDACTED_SECRET]"
            elif isinstance(val, str):
                sanitized[key] = cls.redact_text(val)
            elif isinstance(val, dict):
                sanitized[key] = cls.sanitize_dict(val)
            elif isinstance(val, list):
                sanitized[key] = [
                    cls.sanitize_dict(v) if isinstance(v, dict)
                    else cls.redact_text(v) if isinstance(v, str)
                    else v
                    for v in val
                ]
            else:
                sanitized[key] = val
        return sanitized
