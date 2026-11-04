"""
Relay credentials for voice handoff calls (M2-2).

Browser-to-browser audio (WebRTC) needs a relay ("TURN" server) when either
side is behind a strict network. We run coturn with ``use-auth-secret``: it
shares ``TURN_SECRET`` with this backend, and accepts a username of the form
``<expiry unix time>:<label>`` whose password is
``base64(HMAC-SHA1(secret, username))``. So each call gets credentials that
stop working after ``TURN_TTL_SECONDS``, and no per-user accounts live on the
relay. (See the coturn service in ``docker-compose.yml``.)

Without ``TURN_URLS`` only the STUN servers are offered (fine on one network).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time

from app.config import Settings, get_settings


def ice_servers(label: str, settings: Settings | None = None, now: float | None = None) -> list[dict]:
    s = settings or get_settings()
    out: list[dict] = []
    stun = [u.strip() for u in s.stun_urls.split(",") if u.strip()]
    if stun:
        out.append({"urls": stun})
    turn = [u.strip() for u in s.turn_urls.split(",") if u.strip()]
    if turn and s.turn_secret:
        expiry = int((now if now is not None else time.time()) + s.turn_ttl_seconds)
        username = f"{expiry}:{label}"
        mac = hmac.new(s.turn_secret.encode(), username.encode(), hashlib.sha1).digest()
        out.append({"urls": turn, "username": username,
                    "credential": base64.b64encode(mac).decode()})
    return out
