"""Password hashing and session token helpers.

Uses passlib's argon2 scheme (memory-hard, recommended default for new
designs) with bcrypt kept as a verify-only fallback in case hashes were ever
imported from elsewhere. Session tokens are generated with `secrets.token_urlsafe`
rather than anything guessable/sequential.
"""
from __future__ import annotations

import secrets

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


class PasswordPolicyError(ValueError):
    """Raised when a password does not meet the minimum server-side policy."""


def validate_password_policy(password: str, min_length: int) -> None:
    if len(password) < min_length:
        raise PasswordPolicyError(
            f"Password must be at least {min_length} characters long."
        )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def generate_session_token() -> str:
    return secrets.token_urlsafe(48)
