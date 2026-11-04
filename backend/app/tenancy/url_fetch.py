"""
Fetch a tenant-supplied URL without letting it reach internal networks
(docs/defects.md D-5).

A URL source is fetched by the backend, so an unchecked URL would let a tenant
make the server request cloud metadata (169.254.169.254), localhost services
or private ranges, and read the response back through the ingested text.

Guards:

- only ``http``/``https``, no credentials in the URL;
- a literal IP host, and every address the hostname resolves to, must be
  public (``ipaddress.is_global`` and not multicast; IPv4-mapped IPv6 is
  unwrapped first);
- redirects are followed by hand, and each hop is re-validated;
- response size and content type are capped; environment proxies are ignored.

``INGEST_ALLOW_PRIVATE_URLS`` turns the address checks off, for crawling a
site running on the developer's own machine. Never set it in production.

Residual risk: the address is checked at resolve time and the connection
re-resolves, so a DNS-rebinding host could still switch addresses in between.
Closing that needs connection-level IP pinning or an egress-restricted fetch
worker — the follow-up noted in the implementation plan.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
TIMEOUT_S = 15.0
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")
_USER_AGENT = "FluidBuddhaIngest/1.0"


class UnsafeURLError(ValueError):
    """The URL may not be fetched (scheme, address, size or type)."""


def _private_allowed() -> bool:
    from app.config import get_settings

    return bool(getattr(get_settings(), "ingest_allow_private_urls", False))


def _ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return (not ip.is_global) or ip.is_multicast


def check_url(url: str) -> tuple[str, int]:
    """Validate a URL's shape (no DNS). Returns ``(host, port)``."""
    try:
        parts = urlsplit((url or "").strip())
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError(f"invalid URL: {exc}") from exc
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("only http(s) URLs can be ingested")
    if not parts.hostname:
        raise UnsafeURLError("URL has no host")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs with credentials are not allowed")
    host = parts.hostname
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and _ip_blocked(literal) and not _private_allowed():
        raise UnsafeURLError("URL points to a non-public address")
    return host, port or (443 if parts.scheme == "https" else 80)


async def _resolve_addresses(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM
    )
    return [info[4][0] for info in infos]


async def check_resolved(host: str, port: int) -> None:
    """Every address ``host`` resolves to must be public."""
    if _private_allowed():
        return
    try:
        addresses = await _resolve_addresses(host, port)
    except OSError as exc:
        raise UnsafeURLError(f"could not resolve host: {host}") from exc
    if not addresses:
        raise UnsafeURLError(f"could not resolve host: {host}")
    for addr in addresses:
        ip = ipaddress.ip_address(addr.split("%", 1)[0])  # drop any IPv6 zone id
        if _ip_blocked(ip):
            raise UnsafeURLError("URL resolves to a non-public address")


@dataclass
class Fetched:
    url: str            # after redirects
    content_type: str   # lower-case, no parameters ("" when absent)
    body: bytes
    encoding: str

    @property
    def text(self) -> str:
        return self.body.decode(self.encoding or "utf-8", errors="replace")


async def fetch_public_text(
    url: str, *, transport: Optional[httpx.AsyncBaseTransport] = None
) -> str:
    """GET a public http(s) URL and return its text, enforcing the guards above."""
    return (await fetch_public(url, transport=transport)).text


async def fetch_public(
    url: str,
    *,
    allowed_types: Optional[tuple[str, ...]] = None,
    max_bytes: Optional[int] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Fetched:
    """GET a public http(s) URL with the guards above; ``allowed_types`` widens
    what may come back (robots.txt, sitemaps, CSS, PDFs for the crawler)."""
    allowed_types = allowed_types or ALLOWED_CONTENT_TYPES
    max_bytes = max_bytes or MAX_BYTES
    async with httpx.AsyncClient(
        timeout=TIMEOUT_S, follow_redirects=False, trust_env=False, transport=transport,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            host, port = check_url(url)
            await check_resolved(host, port)
            async with client.stream("GET", url) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise UnsafeURLError("redirect without a Location header")
                    url = urljoin(url, location)
                    continue
                resp.raise_for_status()
                ctype = resp.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if ctype and ctype not in allowed_types:
                    raise UnsafeURLError(f"unsupported content type: {ctype}")
                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise UnsafeURLError("response is too large")
                return Fetched(url=url, content_type=ctype, body=bytes(body),
                               encoding=resp.charset_encoding or "utf-8")
    raise UnsafeURLError("too many redirects")
