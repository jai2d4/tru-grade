"""Password hashing for Phase 21 accounts.

PBKDF2-HMAC-SHA256 via the stdlib (`hashlib`) rather than bcrypt/argon2 — no
extra native-code dependency to add to the Docker build, while still being a
real, salted, per-password-iterated hash (a categorical step up from
plaintext or a bare unsalted digest). The iteration count matches OWASP's
2023 minimum recommendation for PBKDF2-SHA256.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    """Returns `algorithm$iterations$salt_hex$digest_hex`, self-describing so
    the iteration count can be raised later without invalidating old hashes."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time comparison; any malformed stored hash fails closed."""
    try:
        algorithm, iterations_s, salt, hex_digest = encoded.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_s)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return hmac.compare_digest(candidate.hex(), hex_digest)
