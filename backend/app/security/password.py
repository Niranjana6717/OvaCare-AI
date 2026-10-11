"""
Password hashing.

Uses the standard library's `hashlib.pbkdf2_hmac` (PBKDF2-HMAC-SHA256, a
NIST-approved KDF, SP 800-132) with a random 16-byte salt per password and
600,000 iterations (in line with OWASP's 2023+ PBKDF2-SHA256 guidance),
rather than bcrypt/passlib — those weren't installable in this project's
original development sandbox (see docs/deployment.md), while `hashlib` is
always available, which is also why this module's logic has real, executed
test coverage (backend/tests/test_password.py) instead of being
written-and-assumed. bcrypt/argon2 remain fine, equally-secure alternatives
if a deployment target has them available — swapping the KDF only requires
changing `_hash_raw`/`verify_password` below; the stored-hash format
(`pbkdf2_sha256$<iterations>$<salt>$<hash>`) is self-describing so a future
algorithm could be added alongside it without invalidating existing hashes.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGORITHM_TAG = "pbkdf2_sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16

MIN_PASSWORD_LENGTH = 10


def hash_password(plain_password: str) -> str:
    salt = secrets.token_hex(_SALT_BYTES)
    digest = _hash_raw(plain_password, salt, _ITERATIONS)
    return f"{_ALGORITHM_TAG}${_ITERATIONS}${salt}${digest}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations_str, salt, expected_digest = hashed_password.split("$")
    except ValueError:
        return False
    if algorithm != _ALGORITHM_TAG:
        return False
    actual_digest = _hash_raw(plain_password, salt, int(iterations_str))
    return hmac.compare_digest(actual_digest, expected_digest)


def _hash_raw(plain_password: str, salt: str, iterations: int) -> str:
    raw = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return raw.hex()


def password_meets_policy(plain_password: str) -> tuple[bool, str | None]:
    """Minimal, honest policy — length + character variety. No fabricated
    'entropy score' or similar unverified strength claims."""
    if len(plain_password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    has_letter = any(c.isalpha() for c in plain_password)
    has_digit = any(c.isdigit() for c in plain_password)
    if not (has_letter and has_digit):
        return False, "Password must contain both letters and numbers."
    return True, None
