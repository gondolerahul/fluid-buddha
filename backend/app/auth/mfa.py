"""
Two-factor sign-in with an authenticator app (TOTP, RFC 6238) — M2-11.

Standard parameters every authenticator understands: SHA-1, 6 digits, 30 s
steps, one step of clock drift either way. A code's time step is remembered
after use, so the same code can't be replayed within its window. Ten one-time
recovery codes are issued when two-factor is switched on; only their hashes
are stored.

Written out here (about 40 lines) rather than adding a dependency.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Optional
from urllib.parse import quote

STEP = 30
DIGITS = 6
DRIFT = 1           # steps accepted either side of now
RECOVERY_CODES = 10


def new_secret() -> str:
    """A 160-bit secret, base32 (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def code_at(secret: str, step: int) -> str:
    mac = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def current_step(now: Optional[float] = None) -> int:
    return int((time.time() if now is None else now) // STEP)


def verify(secret: str, code: str, *, last_step: Optional[int] = None,
           now: Optional[float] = None) -> Optional[int]:
    """The matching time step, or None. Steps at or before ``last_step`` (an
    already used code) never match."""
    code = (code or "").strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    here = current_step(now)
    for step in range(here - DRIFT, here + DRIFT + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def otpauth_uri(secret: str, account: str, issuer: str = "FluidBuddha") -> str:
    label = f"{quote(issuer)}:{quote(account, safe='@')}"
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP}")


# ---- recovery codes ---------------------------------------------------------------

def _hash(code: str) -> str:
    return hashlib.sha256(code.strip().lower().replace("-", "").encode()).hexdigest()


def new_recovery_codes() -> tuple[list[str], list[str]]:
    """(codes to show once, hashes to store)."""
    codes = []
    for _ in range(RECOVERY_CODES):
        raw = secrets.token_hex(5)   # 10 hex characters
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes, [_hash(c) for c in codes]


def use_recovery_code(code: str, hashes: list[str]) -> Optional[list[str]]:
    """The remaining hashes if ``code`` is one of them, else None."""
    h = _hash(code or "")
    for i, stored in enumerate(hashes):
        if hmac.compare_digest(stored, h):
            return hashes[:i] + hashes[i + 1:]
    return None
