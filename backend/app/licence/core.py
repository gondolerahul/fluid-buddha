"""
Licence keys for self-hosted installs (M3-5), verified offline.

A licence is a signed token:

    FBL1.<base64url(JSON payload)>.<base64url(Ed25519 signature)>

The signature covers ``FBL1.<payload>``. The payload names the signing key
(``kid``), the licence (``lid``), the customer, how many websites and team
seats it covers, its features (``"*"`` = all), when it was issued, when it
expires, and the grace period after expiry. The public keys are built into
the app (``PUBLIC_KEYS``); nothing phones home. Only the holder of the private
key (``scripts/licence_tool.py``) can issue one.

States, from a licence and the time:

* ``valid``     — more than 30 days left;
* ``expiring``  — 30 days or fewer left (the console says so);
* ``grace``     — expired, inside the grace period (everything still works,
                  with a banner);
* ``expired``   — past the grace period: the console turns read-only;
* ``missing`` / ``invalid`` — no licence, or one that doesn't verify: the
                  same as expired.

Visitor-facing paths (the widget, hosted pages, the agent endpoint) never stop
because of the licence: customers' websites keep working while the operator
sorts it out.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

PREFIX = "FBL1"
EXPIRING_DAYS = 30
DEFAULT_GRACE_DAYS = 14
FEATURES = ("byo_model", "agent_access", "campaigns", "sso", "voice_handoff")

# kid -> raw Ed25519 public key (base64). Rotate by adding a new key and
# issuing with it; keep the old one until its licences expire.
PUBLIC_KEYS: dict[str, str] = {
    "fb-2026-1": "tZuFdqT5ArLY3hQAc5yXCirTJaoaOPqsE+3rptYUsz8=",
}


class LicenceError(ValueError):
    """``reason``: malformed | unknown_key | bad_signature."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Licence:
    lid: str
    customer: str
    sites: int
    seats: int
    features: list[str]
    issued_at: datetime
    expires_at: datetime
    grace_days: int = DEFAULT_GRACE_DAYS
    kid: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def has(self, feature: str) -> bool:
        return "*" in self.features or feature in self.features

    def public(self) -> dict[str, Any]:
        return {"lid": self.lid, "customer": self.customer, "sites": self.sites, "seats": self.seats,
                "features": list(FEATURES) if "*" in self.features else self.features,
                "issued_at": self.issued_at.isoformat(), "expires_at": self.expires_at.isoformat(),
                "grace_days": self.grace_days}


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _ts(v: Any) -> datetime:
    return datetime.fromtimestamp(int(v), tz=timezone.utc)


def sign(payload: dict[str, Any], private_key: Ed25519PrivateKey) -> str:
    """Issue a token (the licence tool and tests; never the running app)."""
    body = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    msg = f"{PREFIX}.{body}".encode()
    return f"{PREFIX}.{body}.{_b64e(private_key.sign(msg))}"


def parse(token: str, keys: Optional[dict[str, str]] = None) -> Licence:
    """Verify and read a token. Raises ``LicenceError``."""
    keys = PUBLIC_KEYS if keys is None else keys
    parts = "".join((token or "").split()).split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise LicenceError("malformed")
    try:
        payload = json.loads(_b64d(parts[1]))
        sig = _b64d(parts[2])
    except (ValueError, json.JSONDecodeError):
        raise LicenceError("malformed")
    if not isinstance(payload, dict):
        raise LicenceError("malformed")
    pub = keys.get(str(payload.get("kid") or ""))
    if not pub:
        raise LicenceError("unknown_key")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(pub)).verify(sig, f"{PREFIX}.{parts[1]}".encode())
    except (InvalidSignature, ValueError):
        raise LicenceError("bad_signature")
    try:
        features = payload.get("features") or ["*"]
        return Licence(
            lid=str(payload["lid"]), customer=str(payload["customer"]), sites=int(payload["sites"]),
            seats=int(payload["seats"]), features=[str(f) for f in features],
            issued_at=_ts(payload["iat"]), expires_at=_ts(payload["exp"]),
            grace_days=int(payload.get("grace_days", DEFAULT_GRACE_DAYS)), kid=str(payload["kid"]),
            extra={k: v for k, v in payload.items()
                   if k not in ("lid", "customer", "sites", "seats", "features", "iat", "exp", "grace_days", "kid")})
    except (KeyError, TypeError, ValueError):
        raise LicenceError("malformed")


def state(lic: Optional[Licence], now: Optional[datetime] = None, *, error: Optional[str] = None) -> dict[str, Any]:
    """What the licence means right now, for the console and the guards."""
    now = now or datetime.now(timezone.utc)
    if error:
        return {"state": "invalid", "reason": error, "usable": False}
    if lic is None:
        return {"state": "missing", "usable": False}
    grace_until = lic.expires_at + timedelta(days=lic.grace_days)
    days_left = (lic.expires_at - now).total_seconds() / 86400
    out: dict[str, Any] = {"licence": lic.public(), "days_left": int(days_left // 1) if days_left >= 0 else int(days_left),
                           "grace_until": grace_until.isoformat()}
    if now <= lic.expires_at:
        out.update(state="expiring" if days_left <= EXPIRING_DAYS else "valid", usable=True)
    elif now <= grace_until:
        out.update(state="grace", usable=True)
    else:
        out.update(state="expired", usable=False)
    return out
