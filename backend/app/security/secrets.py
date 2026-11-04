"""
Encryption of stored secrets (M2-1 SSO client secrets; later BYO model keys
and integration secrets — M2-11, M3-4).

Fernet (AES-128-CBC + HMAC-SHA256, from ``cryptography``) with a key from
``SECRETS_KEY`` (a urlsafe-base64 32-byte key: ``python -c "from
cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``).
Without it the key is derived from ``JWT_SECRET`` — fine for development, but
then rotating the JWT secret makes stored secrets unreadable, so production
should set its own (``SECRETS_KEY`` may hold several keys, comma-separated,
newest first, to rotate).
"""
from __future__ import annotations

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import get_settings

logger = logging.getLogger(__name__)


class SecretUnreadable(RuntimeError):
    """A stored secret can't be decrypted with the configured keys."""


@lru_cache(maxsize=4)
def _fernet(keys: str, fallback: str) -> MultiFernet:
    parts = [k.strip() for k in keys.split(",") if k.strip()]
    if not parts:
        derived = base64.urlsafe_b64encode(hashlib.sha256(f"fb-secrets:{fallback}".encode()).digest())
        parts = [derived.decode()]
    return MultiFernet([Fernet(k) for k in parts])


def _box() -> MultiFernet:
    s = get_settings()
    if not s.secrets_key and not s.is_dev_env:
        logger.warning("SECRETS_KEY is not set: stored secrets use a key derived from JWT_SECRET")
    return _fernet(s.secrets_key, s.jwt_secret)


def encrypt(plain: str) -> str:
    return _box().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _box().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise SecretUnreadable("stored secret can't be decrypted with the configured keys") from exc
