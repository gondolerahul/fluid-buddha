"""
Per-site agent profile — the "brain" settings that used to be HireBuddha text
hard-coded across the prompts, personas, tour planner and sitemap
(docs/defects.md D-9; roadmap Phase 0 "De-HireBuddha the brain").

A profile says who the agent is (``agent_name``), which business it represents
(``company_name``) and how it sounds (``brand_voice``); the visitor personas it
may switch between; the concrete example the guided tour ends on
(``closing_use_case``); and the site's navigable routes (the sitemap).

HireBuddha's built-in profile reproduces the previous constants exactly, so the
flagship demo is unchanged. Any other site gets a neutral profile — no personas,
no routes — until its owner edits it or ingestion adds routes.

Storage is ``site_profiles`` (raw DDL keyed by ``site_key``, same approach as the
other admin tables). The prompt builders are synchronous, so they read through
``profile_for(site_key)``, an in-process cache; request entry points call
``ensure_profile`` first. The cache has a short TTL, so an edit shows at once on
the replica that saved it and on other replicas within ``_TTL_S``.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.personas import PERSONAS as _HIREBUDDHA_PERSONAS
from app.orchestrator.sitemap import (
    HIREBUDDHA_DYNAMIC_PREFIXES,
    HIREBUDDHA_ROUTES,
    normalize_route,
)

logger = logging.getLogger(__name__)

DEFAULT_AGENT_NAME = "Pragya"
DEFAULT_BRAND_VOICE = (
    "warm, sharp, and concise — you speak like a senior solutions engineer, "
    "not a brochure"
)


_TTL_S = 30.0


@dataclass
class Persona:
    slug: str
    label: str
    focus: str = ""
    tone: str = ""
    landing: str = ""


@dataclass
class SiteProfile:
    site_key: str
    company_name: str
    agent_name: str = DEFAULT_AGENT_NAME
    brand_voice: str = DEFAULT_BRAND_VOICE
    personas: list[Persona] = field(default_factory=list)
    closing_use_case: str = ""
    routes: list[str] = field(default_factory=list)
    dynamic_prefixes: list[str] = field(default_factory=list)
    # What the agent says first when opened; empty = a page-aware welcome
    # written by the model. A greeting test's winner lands here (M2-4).
    greeting: str = ""
    # The persona a conversation starts in (a slug of ``personas``), and
    # whether the guided tour is offered: both settable by a test's winner.
    default_persona: str = ""
    tour_enabled: bool = True
    # Products visitors compare this one with; Insights counts their mentions (M2-5).
    competitors: list[str] = field(default_factory=list)
    # The next step a recap page offers (M2-6), e.g. "Book a demo" → URL.
    cta_label: str = ""
    cta_url: str = ""

    @property
    def persona_slugs(self) -> list[str]:
        return [p.slug for p in self.personas]

    def persona(self, slug: Optional[str]) -> Optional[Persona]:
        return next((p for p in self.personas if p.slug == slug), None)

    def closing_narration(self) -> str:
        """The tour's last, use-case stop (spoken)."""
        return self.closing_use_case or (
            f"That's a quick look at {self.company_name}. Ask me anything, or I can "
            "show you how it would work for your team."
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any], base: "SiteProfile") -> "SiteProfile":
        """Overlay stored fields onto ``base`` (defaults fill anything missing)."""
        merged = {**base.to_dict(), **{k: v for k, v in data.items() if v is not None}}
        personas = [
            Persona(**{k: p.get(k, "") for k in ("slug", "label", "focus", "tone", "landing")})
            for p in merged.get("personas") or []
            if isinstance(p, dict) and p.get("slug")
        ]
        return SiteProfile(
            site_key=base.site_key,
            company_name=str(merged.get("company_name") or base.company_name),
            agent_name=str(merged.get("agent_name") or base.agent_name),
            brand_voice=str(merged.get("brand_voice") or base.brand_voice),
            personas=personas,
            closing_use_case=str(merged.get("closing_use_case") or ""),
            routes=_clean_routes(merged.get("routes") or []),
            dynamic_prefixes=[str(p) for p in merged.get("dynamic_prefixes") or []],
            greeting=str(merged.get("greeting") or "").strip(),
            default_persona=(str(merged.get("default_persona") or "")
                             if merged.get("default_persona") in {p.slug for p in personas} else ""),
            tour_enabled=merged.get("tour_enabled") is not False,
            competitors=_clean_names(merged.get("competitors") or []),
            cta_label=str(merged.get("cta_label") or "").strip()[:60],
            cta_url=_clean_cta(str(merged.get("cta_url") or "")),
        )


def _clean_cta(url: str) -> str:
    url = url.strip()
    bad = set("\"'<> ") | {"\r", "\n", "\t"}
    return url if url.startswith("https://") and len(url) <= 500 and not bad & set(url) else ""


def _clean_names(names: list[Any]) -> list[str]:
    out: list[str] = []
    for n in names:
        n = " ".join(str(n).split())[:60]
        if n and n.lower() not in {o.lower() for o in out}:
            out.append(n)
    return out[:30]


def _clean_routes(routes: list[Any]) -> list[str]:
    out: list[str] = []
    for r in routes:
        norm = normalize_route(str(r))
        if norm and norm not in out:
            out.append(norm)
    return out


# ---- defaults --------------------------------------------------------------

_HIREBUDDHA_CLOSING = (
    "Here's a concrete example: say your team spends about ten hours a week "
    "screening and scheduling candidates. HireBuddha can automate that in roughly a "
    "day of setup — saving on the order of 40 hours and a few thousand dollars a "
    "month, while giving you faster, more consistent hiring. That's the kind of "
    "outcome we'd map out together."
)


def _hirebuddha_profile() -> SiteProfile:
    return SiteProfile(
        site_key="hirebuddha",
        company_name="HireBuddha",
        personas=[Persona(slug=slug, **p) for slug, p in _HIREBUDDHA_PERSONAS.items()],
        closing_use_case=_HIREBUDDHA_CLOSING,
        routes=list(HIREBUDDHA_ROUTES),
        dynamic_prefixes=list(HIREBUDDHA_DYNAMIC_PREFIXES),
    )


def _display_name(site_key: str) -> str:
    return " ".join(w.capitalize() for w in site_key.replace("_", "-").split("-") if w) or site_key


def default_profile(site_key: str, company_name: Optional[str] = None) -> SiteProfile:
    """Built-in profile: HireBuddha's legacy brain, else a neutral one."""
    if site_key == "hirebuddha":
        return _hirebuddha_profile()
    return SiteProfile(site_key=site_key, company_name=company_name or _display_name(site_key))


# ---- storage ---------------------------------------------------------------

async def _tenant_site_name(db: AsyncSession, site_key: str) -> Optional[str]:
    if not (await db.execute(text("SELECT to_regclass('tenant_websites')"))).scalar():
        return None
    res = await db.execute(
        text("SELECT name FROM tenant_websites WHERE site_key = :k"), {"k": site_key}
    )
    return res.scalar()


async def load_profile(db: AsyncSession, site_key: str) -> SiteProfile:
    """The stored profile overlaid on the default, or the default if none is stored.

    A tenant site's default company name is its website name."""
    base = default_profile(site_key, await _tenant_site_name(db, site_key))
    row = (await db.execute(
        text("SELECT profile FROM site_profiles WHERE site_key = :k"), {"k": site_key}
    )).scalar()
    if not row:
        return base
    data = row if isinstance(row, dict) else json.loads(row)
    return SiteProfile.from_dict(data, base)


async def save_profile(db: AsyncSession, profile: SiteProfile) -> SiteProfile:
    payload = profile.to_dict()
    payload.pop("site_key", None)
    await db.execute(
        text(
            "INSERT INTO site_profiles (site_key, profile, updated_at) "
            "VALUES (:k, CAST(:p AS jsonb), now()) "
            "ON CONFLICT (site_key) DO UPDATE SET profile = CAST(:p AS jsonb), updated_at = now()"
        ),
        {"k": profile.site_key, "p": json.dumps(payload)},
    )
    await db.commit()
    remember(profile)
    return profile


async def merge_routes(db: AsyncSession, site_key: str, routes: list[str]) -> SiteProfile:
    """Add routes discovered at ingestion to the site's sitemap (keeps existing)."""
    profile = await load_profile(db, site_key)
    before = list(profile.routes)
    profile.routes = _clean_routes(before + list(routes))
    if profile.routes != before:
        await save_profile(db, profile)
    return profile


# ---- cache -----------------------------------------------------------------

_cache: dict[str, tuple[float, SiteProfile]] = {}


def remember(profile: SiteProfile) -> None:
    _cache[profile.site_key] = (time.monotonic() + _TTL_S, profile)


def invalidate(site_key: str) -> None:
    _cache.pop(site_key, None)


def profile_for(site_key: Optional[str]) -> SiteProfile:
    """Synchronous read for the prompt builders. Falls back to the built-in
    default when the site hasn't been loaded yet (call ``ensure_profile``)."""
    site_key = site_key or "hirebuddha"
    hit = _cache.get(site_key)
    return hit[1] if hit else default_profile(site_key)


async def ensure_profile(site_key: str) -> SiteProfile:
    """Load the site's profile into the cache unless a fresh copy is there."""
    hit = _cache.get(site_key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    from app.db import session_scope  # local: keeps this module import-light

    try:
        async with session_scope() as db:
            profile = await load_profile(db, site_key)
    except Exception as exc:  # never let a profile read break a conversation
        logger.warning("profile load failed for %s: %s", site_key, exc)
        profile = hit[1] if hit else default_profile(site_key)
    remember(profile)
    return profile
