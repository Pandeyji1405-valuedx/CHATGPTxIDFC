"""
Password hashing and verification using Argon2id.

Argon2id is the recommended algorithm per OWASP (2024):
- Memory-hard: resists GPU/ASIC attacks
- Side-channel resistant
- Configurable time/memory/parallelism parameters

Security rules:
  - Never log plaintext passwords
  - Never return hashes in API responses
  - Always verify via this module; never compare hashes manually
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# ------------------------------------------------------------------ #
# Hasher singleton
# Default parameters (Argon2id):
#   time_cost=3, memory_cost=65536 (64 MB), parallelism=4
#   These are OWASP-recommended minimum settings.
# ------------------------------------------------------------------ #
_hasher = PasswordHasher()


def hash_password(plaintext: str) -> str:
    """
    Hash a plaintext password with Argon2id.

    Each call generates a unique random salt automatically.
    The returned string encodes the algorithm, parameters, salt,
    and digest — everything needed for future verification.

    Args:
        plaintext: The raw password string from the user.

    Returns:
        An Argon2id encoded hash string suitable for database storage.

    Raises:
        ValueError: If plaintext is empty (defense-in-depth; Pydantic
                    validation should catch this before we reach here).
    """
    if not plaintext:
        raise ValueError("Password must not be empty.")
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a stored Argon2id hash.

    Returns True on match, False on any verification failure.
    Exceptions from the argon2 library are caught and converted
    to False to prevent information leakage through exception types.

    Args:
        plaintext: The raw password string provided by the user.
        hashed:    The Argon2id encoded hash string from the database.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    try:
        return _hasher.verify(hashed, plaintext)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
