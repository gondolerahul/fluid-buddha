"""
Resolve the site + capability tier for the UNAUTHENTICATED public widget paths
(``/chat`` and ``/ws/voice``), so a visitor can neither reach a tenant's
knowledge base by guessing its ``site_key`` nor choose their own (more
expensive) tier. See docs/defects.md D-1.

Rules:

- **With a widget ``key``** — resolve the owning website, use ITS ``site_key``
  and configured tier, ignore any client-supplied ``site``/``intelligence``, and
  enforce the Origin allow-list.
- **Without a key** — a built-in demo site (or an unregistered key, e.g. the
  ad-hoc site keys used in tests) is allowed with the client-requested tier,
  because no tenant owns it. A *registered* tenant site is refused: it must be
  reached with its widget key.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.orchestrator.state import normalize_intelligence
from app.tenancy import store


class PublicAccessError(Exception):
    """Raised when a public request may not reach the requested site."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class ResolvedSite:
    site_key: str
    intelligence: str
    tier_locked: bool  # True -> ignore any client-requested tier for this session
    website: Optional[store.Website] = None


def _origin_host(origin: Optional[str]) -> str:
    if not origin:
        return ""
    return (urlsplit(origin).hostname or "").lower()


def _origin_allowed(website: store.Website, origin: Optional[str]) -> bool:
    """Allow-list the site's domain (and its subdomains).

    Lenient on purpose: dev environments and sites with no domain configured
    skip the check, so local testing and not-yet-configured sites keep working.
    """
    if get_settings().is_dev_env:
        return True
    domain = (website.domain or "").strip().lower()
    if not domain:
        return True
    host = _origin_host(origin)
    if not host:
        return False
    return host == domain or host.endswith("." + domain)


async def resolve_public_site(
    db: AsyncSession,
    *,
    key: Optional[str],
    site: Optional[str],
    intelligence: Optional[str],
    origin: Optional[str] = None,
) -> ResolvedSite:
    key = (key or "").strip()
    if key:
        website = await store.get_website_by_public_key(db, key)
        if website is None or website.status != "active":
            raise PublicAccessError("invalid_widget_key")
        if not _origin_allowed(website, origin):
            raise PublicAccessError("origin_not_allowed")
        return ResolvedSite(
            site_key=website.site_key,
            intelligence=normalize_intelligence(website.intelligence),
            tier_locked=True,
            website=website,
        )

    site = (site or "hirebuddha").strip()
    # A registered tenant site must be reached with its widget key; built-in
    # demo sites (and unregistered keys) stay open with the requested tier.
    if not store.is_reserved_site_key(site) and await store.site_key_exists(db, site):
        raise PublicAccessError("widget_key_required")
    return ResolvedSite(
        site_key=site,
        intelligence=normalize_intelligence(intelligence or "advance"),
        tier_locked=False,
    )
