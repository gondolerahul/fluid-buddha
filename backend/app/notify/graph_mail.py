"""
Email through Microsoft 365 (Exchange Online) with Microsoft Graph.

Used when ``EMAIL_TRANSPORT=graph``. Microsoft is retiring password sign-in for
SMTP (SMTP AUTH basic authentication), so a Microsoft 365 sender goes through
Graph's ``sendMail`` with an app registration instead:

* the app signs in with the client-credentials flow (``GRAPH_TENANT_ID``,
  ``GRAPH_CLIENT_ID``, ``GRAPH_CLIENT_SECRET``); the token is kept until
  shortly before it expires;
* the message is the same MIME message the SMTP path builds (text and HTML
  parts, ``List-Unsubscribe`` and the other headers intact), posted
  base64-encoded to ``/users/{sender}/sendMail``, where the sender is the
  address in ``SMTP_FROM``;
* Exchange limits the app to that one mailbox (RBAC for Applications, see
  docs/deployment/azure-operator-guide.md), so a leaked secret can't send as
  anyone else.

Graph accepts a message with 202. Anything else raises :class:`GraphSendError`,
and the outbox retries it like an SMTP failure.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Optional
from urllib.parse import quote

import httpx

from app.config import Settings

GRAPH_URL = "https://graph.microsoft.com/v1.0"
LOGIN_URL = "https://login.microsoftonline.com"
SCOPE = "https://graph.microsoft.com/.default"
REFRESH_MARGIN_S = 300   # fetch a new token this long before the old one expires


class GraphSendError(RuntimeError):
    """Microsoft Graph refused the sign-in or the message."""


@dataclass
class _Token:
    value: str
    expires_at: float          # time.monotonic()
    key: tuple[str, str, str]  # tenant, client, secret: a changed setting means a new token


_token: Optional[_Token] = None
# Tests swap in an httpx.MockTransport here.
_transport: Optional[httpx.AsyncBaseTransport] = None


def sender_address(settings: Settings) -> str:
    return parseaddr(settings.smtp_from)[1]


def _error_text(r: httpx.Response) -> str:
    """The error code and message from a Graph or sign-in error body, short."""
    try:
        body = r.json()
    except ValueError:
        return r.text[:300]
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):   # Graph: {"error": {"code": ..., "message": ...}}
        return f"{err.get('code')}: {err.get('message')}"[:300]
    if err:                     # sign-in: {"error": ..., "error_description": ...}
        return f"{err}: {body.get('error_description', '')}"[:300]
    return r.text[:300]


async def _access_token(client: httpx.AsyncClient, settings: Settings) -> str:
    global _token
    key = (settings.graph_tenant_id.strip(), settings.graph_client_id.strip(),
           settings.graph_client_secret.strip())
    now = time.monotonic()
    if _token and _token.key == key and _token.expires_at - REFRESH_MARGIN_S > now:
        return _token.value
    r = await client.post(
        f"{LOGIN_URL}/{quote(key[0], safe='')}/oauth2/v2.0/token",
        data={"grant_type": "client_credentials", "client_id": key[1],
              "client_secret": key[2], "scope": SCOPE})
    if r.status_code != 200:
        raise GraphSendError(f"sign-in failed ({r.status_code}): {_error_text(r)}")
    body = r.json()
    _token = _Token(body["access_token"], now + float(body.get("expires_in", 3600)), key)
    return _token.value


async def send(msg: EmailMessage, settings: Settings) -> None:
    """Send ``msg`` as the ``SMTP_FROM`` mailbox. Raises GraphSendError."""
    global _token
    sender = sender_address(settings)
    if not sender:
        raise GraphSendError("SMTP_FROM has no address to send from")
    # MIME wants CRLF line endings; Graph takes the whole message base64-encoded.
    mime = base64.b64encode(msg.as_bytes(policy=msg.policy.clone(linesep="\r\n")))
    async with httpx.AsyncClient(timeout=settings.smtp_timeout_seconds, trust_env=False,
                                 follow_redirects=False, transport=_transport) as client:
        token = await _access_token(client, settings)
        r = await client.post(
            f"{GRAPH_URL}/users/{quote(sender, safe='@')}/sendMail", content=mime,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"})
    if r.status_code == 401:
        _token = None   # revoked or rotated: sign in again on the next attempt
    if r.status_code != 202:
        raise GraphSendError(f"sendMail failed ({r.status_code}): {_error_text(r)}")
