"""
Single sign-on with OpenID Connect (M2-1): "Sign in with Google" for
everyone, and each account's own identity provider (Okta, Microsoft Entra,
Auth0, Keycloak… — anything that speaks OIDC).

The flow is the authorization-code flow with PKCE:

1. ``start`` picks the provider (Google, or the account that has *verified*
   the person's email domain), stores a single-use ``state`` with a ``nonce``
   and a PKCE verifier (``sso_logins``), and returns the provider's sign-in URL.
2. The provider sends the browser back to ``/auth/sso/callback`` with a code;
   ``finish`` exchanges it (with the verifier), checks the ID token's
   signature against the provider's published keys, its issuer, audience,
   expiry and nonce, then finds or creates the person.

Who gets in:
* **Google** proves a verified email; the person must already belong to an
  account (or accept an invitation first). Google never creates memberships.
* **An account's own provider** may sign in people of the domains that account
  has proven with a DNS TXT record (``fluidbuddha-verify=<token>``); they join
  with the account's default role on first sign-in. Unproven domains are
  refused, so nobody can point someone else's domain at their own provider.

Every outbound request (discovery, keys, token exchange, DNS-over-HTTPS) goes
through the SSRF checks used for URL sources; HTTPS only outside dev.
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode, urlsplit

import httpx
import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.security import secrets as stored
from app.tenancy.url_fetch import check_resolved, check_url

GOOGLE_ISSUER = "https://accounts.google.com"
STATE_MAX_AGE_S = 600
_DISCOVERY_TTL_S = 3600
_ALGS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](-?[a-z0-9])*\.)+[a-z]{2,63}$")

# Tests swap in an httpx.MockTransport (it never touches DNS).
_transport: Optional[httpx.AsyncBaseTransport] = None
_discovery_cache: dict[str, tuple[float, dict]] = {}


class SSOError(Exception):
    """Something the person (or their admin) should be told, in plain words."""


@dataclass
class Provider:
    name: str                       # "google" | "oidc"
    issuer: str
    client_id: str
    client_secret: str
    tenant_id: Optional[uuid.UUID]  # None for Google
    default_role: str = "viewer"


def redirect_uri() -> str:
    return get_settings().public_api_url.rstrip("/") + "/auth/sso/callback"


# ---- HTTP -----------------------------------------------------------------------

def _check_target(url: str) -> tuple[str, int]:
    if not url.startswith("https://") and not get_settings().is_dev_env:
        raise SSOError("Identity provider addresses must use https.")
    try:
        return check_url(url)
    except ValueError as exc:
        raise SSOError(f"Identity provider address refused: {exc}") from exc


async def _request(method: str, url: str, **kw) -> dict:
    host, port = _check_target(url)
    if _transport is None:
        try:
            await check_resolved(host, port)
        except ValueError as exc:
            raise SSOError(f"Identity provider address refused: {exc}") from exc
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False,
                                     transport=_transport) as client:
            resp = await client.request(method, url, **kw)
    except httpx.HTTPError as exc:
        raise SSOError(f"Couldn't reach the identity provider ({type(exc).__name__}).") from exc
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400:
        detail = data.get("error_description") or data.get("error") or f"HTTP {resp.status_code}"
        raise SSOError(f"The identity provider refused: {detail}")
    return data


async def discover(issuer: str) -> dict:
    issuer = issuer.rstrip("/")
    hit = _discovery_cache.get(issuer)
    if hit and time.monotonic() - hit[0] < _DISCOVERY_TTL_S:
        return hit[1]
    doc = await _request("GET", f"{issuer}/.well-known/openid-configuration")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not isinstance(doc.get(key), str):
            raise SSOError(f"The identity provider's configuration has no {key}.")
    if doc.get("issuer", "").rstrip("/") != issuer:
        raise SSOError("The identity provider reports a different issuer than configured.")
    _discovery_cache[issuer] = (time.monotonic(), doc)
    return doc


# ---- providers ---------------------------------------------------------------------

def google() -> Provider:
    s = get_settings()
    if not s.google_client_id:
        raise SSOError("Sign in with Google isn't set up on this server.")
    return Provider("google", GOOGLE_ISSUER, s.google_client_id, s.google_client_secret, None)


async def provider_for_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Provider:
    row = (await db.execute(text(
        "SELECT issuer, client_id, client_secret_enc, default_role FROM tenant_sso "
        "WHERE tenant_id = :t AND enabled"), {"t": tenant_id})).mappings().first()
    if not row:
        raise SSOError("Single sign-on isn't set up for this account.")
    secret = stored.decrypt(row["client_secret_enc"]) if row["client_secret_enc"] else ""
    return Provider("oidc", row["issuer"], row["client_id"], secret, tenant_id,
                    row["default_role"])


async def tenant_for_domain(db: AsyncSession, domain: str) -> Optional[uuid.UUID]:
    return (await db.execute(text(
        "SELECT d.tenant_id FROM sso_domains d JOIN tenant_sso s ON s.tenant_id = d.tenant_id "
        "WHERE d.domain = :d AND d.verified_at IS NOT NULL AND s.enabled"),
        {"d": domain.lower()})).scalar()


# ---- the flow ------------------------------------------------------------------------

def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


async def start(db: AsyncSession, *, provider: str, email: Optional[str]) -> str:
    """Begin a sign-in; returns the URL to send the browser to."""
    if provider == "google":
        p = google()
    else:
        domain = (email or "").strip().lower().rpartition("@")[2]
        if not domain:
            raise SSOError("Enter your work email to sign in with SSO.")
        tenant_id = await tenant_for_domain(db, domain)
        if tenant_id is None:
            raise SSOError(f"No single sign-on is set up for {domain}.")
        p = await provider_for_tenant(db, tenant_id)
    doc = await discover(p.issuer)
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    await db.execute(text(
        "INSERT INTO sso_logins (state, nonce, code_verifier, provider, tenant_id) "
        "VALUES (:s, :n, :v, :p, :t)"),
        {"s": state, "n": nonce, "v": verifier, "p": p.name, "t": p.tenant_id})
    await db.execute(text("DELETE FROM sso_logins WHERE created_at < now() - interval '1 day'"))
    params = {
        "response_type": "code", "client_id": p.client_id, "redirect_uri": redirect_uri(),
        "scope": "openid email profile", "state": state, "nonce": nonce,
        "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
    }
    if email:
        params["login_hint"] = email.strip()
    sep = "&" if urlsplit(doc["authorization_endpoint"]).query else "?"
    return f"{doc['authorization_endpoint']}{sep}{urlencode(params)}"


async def _verify_id_token(id_token: str, p: Provider, doc: dict, nonce: str) -> dict:
    try:
        kid = jwt.get_unverified_header(id_token).get("kid")
    except jwt.PyJWTError as exc:
        raise SSOError("The identity provider sent an unreadable sign-in token.") from exc
    jwks = await _request("GET", doc["jwks_uri"])
    try:
        keys = jwt.PyJWKSet.from_dict(jwks).keys
    except jwt.PyJWTError as exc:
        raise SSOError("The identity provider's signing keys are unreadable.") from exc
    candidates = [k for k in keys if kid is None or k.key_id == kid]
    if not candidates:
        raise SSOError("The sign-in token was signed with an unknown key.")
    issuers = [p.issuer, p.issuer.rstrip("/")]
    if p.name == "google":
        issuers.append("accounts.google.com")
    last: Exception | None = None
    for key in candidates:
        try:
            claims = jwt.decode(id_token, key.key, algorithms=_ALGS, audience=p.client_id,
                                issuer=issuers, leeway=60,
                                options={"require": ["exp", "iat", "iss", "aud", "sub"]})
            break
        except jwt.PyJWTError as exc:
            last = exc
    else:
        raise SSOError(f"The sign-in token didn't check out ({type(last).__name__}).")
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise SSOError("The sign-in token doesn't belong to this sign-in (nonce).")
    return claims


@dataclass
class Identity:
    email: str
    name: Optional[str]
    provider: Provider


async def finish(db: AsyncSession, *, state: str, code: str) -> Identity:
    row = (await db.execute(text(
        "DELETE FROM sso_logins WHERE state = :s RETURNING nonce, code_verifier, provider, "
        "tenant_id, extract(epoch FROM now() - created_at) AS age"),
        {"s": state or ""})).mappings().first()
    await db.commit()   # single use, even if the rest fails
    if not row or row["age"] > STATE_MAX_AGE_S:
        raise SSOError("This sign-in link has expired. Please try again.")
    p = google() if row["provider"] == "google" else await provider_for_tenant(db, row["tenant_id"])
    doc = await discover(p.issuer)
    tokens = await _request("POST", doc["token_endpoint"], data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(),
        "client_id": p.client_id, "client_secret": p.client_secret,
        "code_verifier": row["code_verifier"]}, headers={"Accept": "application/json"})
    if not isinstance(tokens.get("id_token"), str):
        raise SSOError("The identity provider didn't send an ID token.")
    claims = await _verify_id_token(tokens["id_token"], p, doc, row["nonce"])
    email = str(claims.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise SSOError("The identity provider didn't share an email address.")
    verified = claims.get("email_verified")
    if verified is False or verified == "false" or (p.name == "google" and verified is not True):
        raise SSOError("Your email address isn't verified with the identity provider.")
    if p.tenant_id is not None:
        domain = email.rpartition("@")[2]
        if await tenant_for_domain(db, domain) != p.tenant_id:
            raise SSOError(f"This account's single sign-on doesn't cover {domain}.")
    return Identity(email=email, name=claims.get("name"), provider=p)


# ---- domains ---------------------------------------------------------------------------

def txt_value(token: str) -> str:
    return f"fluidbuddha-verify={token}"


async def dns_txt(domain: str) -> list[str]:
    url = get_settings().dns_over_https_url
    data = await _request("GET", url, params={"name": domain, "type": "TXT"},
                          headers={"Accept": "application/dns-json"})
    out = []
    for ans in data.get("Answer") or []:
        if ans.get("type") == 16:
            out.append(str(ans.get("data", "")).replace('" "', "").strip('"'))
    return out


async def verify_domain(db: AsyncSession, tenant_id: uuid.UUID, domain: str) -> bool:
    row = (await db.execute(text(
        "SELECT token FROM sso_domains WHERE domain = :d AND tenant_id = :t"),
        {"d": domain, "t": tenant_id})).first()
    if not row:
        return False
    if txt_value(row[0]) not in await dns_txt(domain):
        return False
    await db.execute(text("UPDATE sso_domains SET verified_at = now() WHERE domain = :d"),
                     {"d": domain})
    return True
