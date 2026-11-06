"""
Campaigns (M3-1): the brief a landing page is composed from, its page cache
and its numbers.

A campaign is a site's goal for a page (who it's for, what it must say, which
sections it may use, the call to action) plus the proof the customer supplies
— testimonials and logos, which the composer may quote but never invent. It
can carry a variant B (another headline, messages or CTA) split 50/50 with
the original, measured on conversions.

Composed pages are cached per (campaign version, arm, persona, question,
language, content version): editing the campaign or re-ingesting the site's
content composes afresh; everything else is served from the cache.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import site_entity_id
from app.orchestrator.pagegen import SECTION_TYPES

# What a landing page may be built from. ``hero`` and ``cta`` are always there.
LANDING_SECTIONS = ("feature_grid", "text", "pricing_table", "testimonials", "logos", "faq",
                    "comparison", "roi_calculator", "chart", "enquiry_form", "media")
SECTION_LABELS = {
    "feature_grid": "Feature cards", "text": "Text / answer", "pricing_table": "Pricing", "testimonials": "Testimonials",
    "logos": "Customer logos", "faq": "FAQ", "comparison": "Comparison table", "roi_calculator": "ROI calculator",
    "chart": "Chart", "enquiry_form": "Enquiry form", "media": "Image",
}
DEFAULT_SECTIONS = ("feature_grid", "text", "testimonials", "logos", "faq", "enquiry_form")
ALWAYS = ("hero", "cta")
STATUSES = ("draft", "live", "paused")
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,58}[a-z0-9])?$")

assert set(LANDING_SECTIONS) <= set(SECTION_TYPES)


class CampaignError(ValueError):
    """A campaign that can't be saved as given (shown to the editor)."""


@dataclass
class Campaign:
    id: uuid.UUID
    site_key: str
    slug: str
    name: str
    status: str = "draft"
    goal: str = ""
    audience: str = ""
    persona: Optional[str] = None
    key_messages: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    cta_label: str = ""
    cta_url: str = ""
    testimonials: list[dict] = field(default_factory=list)
    logos: list[dict] = field(default_factory=list)
    variant: Optional[dict] = None
    embed_origins: list[str] = field(default_factory=list)
    version: int = 1
    created_at: Any = None
    updated_at: Any = None

    def public(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d["id"] = str(self.id)
        for k in ("created_at", "updated_at"):
            d[k] = d[k].isoformat() if d[k] is not None else None
        return d

    def brief(self, arm: str) -> dict[str, Any]:
        """The arm's copy: variant B overrides headline, messages and CTA."""
        v = (self.variant or {}) if arm == "b" else {}
        return {
            "headline": v.get("headline") or "",
            "key_messages": v.get("key_messages") or self.key_messages,
            "cta_label": v.get("cta_label") or self.cta_label,
        }


_COLS = ("id, site_key, slug, name, status, goal, audience, persona, key_messages, sections, cta_label, "
         "cta_url, testimonials, logos, variant, embed_origins, version, created_at, updated_at")


def _row(r: Any) -> Campaign:
    d = dict(r)
    for k in ("testimonials", "logos"):
        if isinstance(d.get(k), str):
            d[k] = json.loads(d[k])
    if isinstance(d.get("variant"), str):
        d["variant"] = json.loads(d["variant"])
    d["key_messages"] = list(d.get("key_messages") or [])
    d["sections"] = list(d.get("sections") or [])
    d["embed_origins"] = list(d.get("embed_origins") or [])
    return Campaign(**d)


# ---- validation ----------------------------------------------------------------------

def _s(v: Any, n: int) -> str:
    return " ".join(str(v or "").split())[:n]


def _https(v: Any, n: int = 500) -> str:
    u = str(v or "").strip()[:n]
    if not u:
        return ""
    parts = urlsplit(u)
    if parts.scheme != "https" or not parts.netloc:
        raise CampaignError(f"Use an https:// link: {u[:80]}")
    return u


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:60].strip("-") or "campaign"


def clean(raw: dict[str, Any], *, personas: list[str]) -> dict[str, Any]:
    """Validate an editor's campaign. Raises ``CampaignError``."""
    name = _s(raw.get("name"), 120)
    if not name:
        raise CampaignError("Give the campaign a name.")
    slug = str(raw.get("slug") or "").strip().lower() or slugify(name)
    if not SLUG_RE.match(slug):
        raise CampaignError("The link name may use a-z, 0-9 and dashes (2-60 characters).")
    status = raw.get("status") or "draft"
    if status not in STATUSES:
        raise CampaignError("Status is draft, live or paused.")
    persona = raw.get("persona") or None
    if persona and persona not in personas:
        raise CampaignError("Pick one of the site's personas, or none.")
    messages = [m for m in (_s(x, 200) for x in (raw.get("key_messages") or [])[:8]) if m]
    sections = [s for s in dict.fromkeys(raw.get("sections") or DEFAULT_SECTIONS) if s in LANDING_SECTIONS]
    testimonials = []
    for t in (raw.get("testimonials") or [])[:8]:
        quote, who = _s((t or {}).get("quote"), 400), _s((t or {}).get("name"), 80)
        if quote and who:
            testimonials.append({"quote": quote, "name": who, "role": _s(t.get("role"), 80)})
    logos = []
    for lg in (raw.get("logos") or [])[:12]:
        src = _https((lg or {}).get("src"))
        if src:
            logos.append({"src": src, "alt": _s(lg.get("alt"), 80) or "Customer logo"})
    variant = raw.get("variant") or None
    if variant:
        v = {"headline": _s(variant.get("headline"), 160),
             "key_messages": [m for m in (_s(x, 200) for x in (variant.get("key_messages") or [])[:8]) if m],
             "cta_label": _s(variant.get("cta_label"), 60)}
        variant = v if any(v.values()) else None
    origins = []
    for o in (raw.get("embed_origins") or [])[:5]:
        u = _https(o, 200)
        if u:
            p = urlsplit(u)
            origins.append(f"https://{p.netloc}")
    return {
        "name": name, "slug": slug, "status": status, "goal": _s(raw.get("goal"), 500),
        "audience": _s(raw.get("audience"), 300), "persona": persona, "key_messages": messages,
        "sections": sections, "cta_label": _s(raw.get("cta_label"), 60), "cta_url": _https(raw.get("cta_url")),
        "testimonials": testimonials, "logos": logos, "variant": variant, "embed_origins": origins,
    }


# ---- CRUD ----------------------------------------------------------------------------

async def list_for_site(db: AsyncSession, site_key: str) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        f"SELECT {_COLS}, "
        "(SELECT count(DISTINCT viewer) FROM campaign_events e WHERE e.campaign_id = c.id AND kind = 'view' "
        " AND created_at > now() - interval '30 days') AS views_30d, "
        "(SELECT count(DISTINCT viewer) FROM campaign_events e WHERE e.campaign_id = c.id AND kind = 'convert' "
        " AND created_at > now() - interval '30 days') AS conversions_30d "
        "FROM campaigns c WHERE site_key = :s ORDER BY created_at DESC"), {"s": site_key})).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        views, conv = d.pop("views_30d"), d.pop("conversions_30d")
        out.append({**_row(d).public(), "views_30d": views, "conversions_30d": conv})
    return out


async def get(db: AsyncSession, site_key: str, campaign_id: uuid.UUID) -> Optional[Campaign]:
    r = (await db.execute(text(f"SELECT {_COLS} FROM campaigns WHERE site_key = :s AND id = :id"),
                          {"s": site_key, "id": campaign_id})).mappings().first()
    return _row(r) if r else None


async def by_slug(db: AsyncSession, site_key: str, slug: str) -> Optional[Campaign]:
    r = (await db.execute(text(f"SELECT {_COLS} FROM campaigns WHERE site_key = :s AND slug = :slug"),
                          {"s": site_key, "slug": slug})).mappings().first()
    return _row(r) if r else None


def _params(v: dict[str, Any]) -> dict[str, Any]:
    return {**v, "testimonials": json.dumps(v["testimonials"]), "logos": json.dumps(v["logos"]),
            "variant": json.dumps(v["variant"]) if v["variant"] else None}


async def create(db: AsyncSession, site_key: str, v: dict[str, Any], user_id: Any = None) -> Campaign:
    if await by_slug(db, site_key, v["slug"]):
        raise CampaignError("Another campaign already uses that link name.")
    cid = uuid.uuid4()
    await db.execute(text(
        "INSERT INTO campaigns (id, site_key, slug, name, status, goal, audience, persona, key_messages, "
        "sections, cta_label, cta_url, testimonials, logos, variant, embed_origins, created_by) VALUES "
        "(:id, :site, :slug, :name, :status, :goal, :audience, :persona, :key_messages, :sections, :cta_label, "
        ":cta_url, CAST(:testimonials AS jsonb), CAST(:logos AS jsonb), CAST(:variant AS jsonb), :embed_origins, :u)"),
        {**_params(v), "id": cid, "site": site_key, "u": user_id})
    return await get(db, site_key, cid)  # type: ignore[return-value]


async def update(db: AsyncSession, c: Campaign, v: dict[str, Any]) -> Campaign:
    other = await by_slug(db, c.site_key, v["slug"])
    if other and other.id != c.id:
        raise CampaignError("Another campaign already uses that link name.")
    # Copy changes the page: compose afresh. Status alone doesn't.
    content = {k: v[k] for k in v if k != "status"}
    old = {k: getattr(c, k) for k in content}
    bump = 1 if content != old else 0
    await db.execute(text(
        "UPDATE campaigns SET slug = :slug, name = :name, status = :status, goal = :goal, audience = :audience, "
        "persona = :persona, key_messages = :key_messages, sections = :sections, cta_label = :cta_label, "
        "cta_url = :cta_url, testimonials = CAST(:testimonials AS jsonb), logos = CAST(:logos AS jsonb), "
        "variant = CAST(:variant AS jsonb), embed_origins = :embed_origins, version = version + :bump, "
        "updated_at = now() WHERE id = :id"), {**_params(v), "id": c.id, "bump": bump})
    if bump:
        await clear_cache(db, c.id)
    return await get(db, c.site_key, c.id)  # type: ignore[return-value]


async def delete(db: AsyncSession, site_key: str, campaign_id: uuid.UUID) -> bool:
    return bool((await db.execute(text("DELETE FROM campaigns WHERE site_key = :s AND id = :id"),
                                  {"s": site_key, "id": campaign_id})).rowcount)


# ---- the page cache ------------------------------------------------------------------

async def content_version(db: AsyncSession, site_key: str) -> str:
    """Changes whenever the site's knowledge is (re)ingested."""
    r = (await db.execute(text(
        "SELECT count(n.id) AS n, max(n.created_at) AS at FROM cortex_nodes n "
        "JOIN cortex_trees t ON t.id = n.tree_id WHERE t.memory_domain = 'knowledge' AND t.entity_id = :e"),
        {"e": site_entity_id(site_key)})).mappings().first()
    return f"{r['n']}:{r['at'].isoformat() if r and r['at'] else '-'}"


def cache_key(c: Campaign, *, arm: str, persona: Optional[str], question: Optional[str], lang: str,
              content: str) -> str:
    q = " ".join((question or "").lower().split())
    raw = json.dumps([c.version, arm, persona or "", q, lang, content])
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


async def cached_page(db: AsyncSession, campaign_id: uuid.UUID, key: str) -> Optional[dict[str, Any]]:
    r = (await db.execute(text(
        "UPDATE campaign_pages SET hits = hits + 1, last_hit_at = now() "
        "WHERE campaign_id = :c AND cache_key = :k RETURNING spec"), {"c": campaign_id, "k": key})).first()
    if r is None:
        return None
    return r[0] if isinstance(r[0], dict) else json.loads(r[0])


async def any_cached_page(db: AsyncSession, campaign_id: uuid.UUID, arm: str) -> Optional[dict[str, Any]]:
    """A page already composed for this arm (served to bots and when composing
    is rate limited), the general one (no question) first."""
    r = (await db.execute(text(
        "SELECT spec FROM campaign_pages WHERE campaign_id = :c AND arm = :a "
        "ORDER BY (question IS NULL) DESC, hits DESC LIMIT 1"), {"c": campaign_id, "a": arm})).first()
    if r is None:
        return None
    return r[0] if isinstance(r[0], dict) else json.loads(r[0])


async def store_page(db: AsyncSession, campaign_id: uuid.UUID, key: str, *, arm: str, persona: Optional[str],
                     question: Optional[str], spec: dict[str, Any], composer: str, build_ms: int) -> None:
    await db.execute(text(
        "INSERT INTO campaign_pages (id, campaign_id, cache_key, arm, persona, question, spec, composer, build_ms) "
        "VALUES (:id, :c, :k, :a, :p, :q, CAST(:spec AS jsonb), :comp, :ms) "
        "ON CONFLICT (campaign_id, cache_key) DO UPDATE SET spec = EXCLUDED.spec, composer = EXCLUDED.composer, "
        "build_ms = EXCLUDED.build_ms, created_at = now()"),
        {"id": uuid.uuid4(), "c": campaign_id, "k": key, "a": arm, "p": persona, "q": question,
         "spec": json.dumps(spec, default=str), "comp": composer, "ms": build_ms})


async def clear_cache(db: AsyncSession, campaign_id: uuid.UUID) -> int:
    return (await db.execute(text("DELETE FROM campaign_pages WHERE campaign_id = :c"),
                             {"c": campaign_id})).rowcount or 0


# ---- arms and events -----------------------------------------------------------------

def assign_arm(c: Campaign, viewer: str) -> str:
    if not c.variant:
        return "a"
    h = hashlib.sha256(f"{c.id}:{viewer}".encode()).digest()
    return "b" if h[0] & 1 else "a"


async def record(db: AsyncSession, c: Campaign, *, viewer: str, kind: str, arm: str,
                 persona: Optional[str] = None, source: Optional[str] = None,
                 cached: Optional[bool] = None) -> None:
    await db.execute(text(
        "INSERT INTO campaign_events (campaign_id, site_key, viewer, kind, arm, persona, source, cached) "
        "VALUES (:c, :s, :v, :k, :a, :p, :src, :cached)"),
        {"c": c.id, "s": c.site_key, "v": viewer[:64], "k": kind, "a": arm, "p": persona,
         "src": (source or None) and source[:60], "cached": cached})


async def analytics(db: AsyncSession, c: Campaign, days: int = 30) -> dict[str, Any]:
    """Views, engagement and conversions (unique viewers), by arm, persona and
    source; a daily series; the cache; and, with a variant, the verdict."""
    from app.experiments.stats import variant_verdict

    p = {"c": c.id, "d": days}
    since = "created_at > now() - make_interval(days => :d)"

    async def counts(group: Optional[str]) -> list[dict[str, Any]]:
        # Each visitor counts once, under the arm, persona and source of their
        # first view; their engagement and conversion are credited there.
        g = f"v.{group}, " if group else ""
        rows = (await db.execute(text(
            "WITH v AS (SELECT DISTINCT ON (viewer) viewer, arm, persona, source FROM campaign_events "
            f"  WHERE campaign_id = :c AND kind = 'view' AND {since} ORDER BY viewer, created_at), "
            "k AS (SELECT viewer, bool_or(kind = 'engage') AS e, bool_or(kind = 'convert') AS x "
            f"  FROM campaign_events WHERE campaign_id = :c AND {since} GROUP BY viewer) "
            f"SELECT {g}count(*) AS views, count(*) FILTER (WHERE k.e) AS engaged, "
            "count(*) FILTER (WHERE k.x) AS converted FROM v LEFT JOIN k USING (viewer)"
            + (f" GROUP BY v.{group} ORDER BY views DESC" if group else "")), p)).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            d["conversion_rate"] = round(d["converted"] / d["views"], 4) if d["views"] else 0.0
            out.append(d)
        return out

    total = (await counts(None))[0]
    by_arm = await counts("arm")
    daily = [{"day": str(r["day"]), "views": r["views"], "converted": r["converted"]} for r in (await db.execute(text(
        "SELECT date_trunc('day', created_at)::date AS day, "
        "count(DISTINCT viewer) FILTER (WHERE kind = 'view') AS views, "
        "count(DISTINCT viewer) FILTER (WHERE kind = 'convert') AS converted "
        f"FROM campaign_events WHERE campaign_id = :c AND {since} GROUP BY 1 ORDER BY 1"), p)).mappings().all()]
    cache = (await db.execute(text(
        "SELECT count(*) AS pages, coalesce(sum(hits), 0) AS hits, "
        "coalesce(avg(build_ms), 0)::int AS avg_build_ms FROM campaign_pages WHERE campaign_id = :c"),
        {"c": c.id})).mappings().first()
    served = (await db.execute(text(
        "SELECT count(*) FILTER (WHERE cached) AS cached, count(*) AS views FROM campaign_events "
        f"WHERE campaign_id = :c AND kind = 'view' AND {since}"), p)).mappings().first()
    out: dict[str, Any] = {
        "days": days, "total": total, "by_arm": by_arm, "by_persona": await counts("persona"),
        "by_source": await counts("source"), "daily": daily,
        "cache": {**dict(cache), "served_from_cache": served["cached"], "page_views": served["views"],
                  "hit_rate": round(served["cached"] / served["views"], 4) if served["views"] else 0.0},
    }
    if c.variant:
        arms = {r["arm"]: r for r in by_arm}
        a, b = arms.get("a", {}), arms.get("b", {})
        out["experiment"] = variant_verdict([("a", a.get("views", 0), a.get("converted", 0)),
                                             ("b", b.get("views", 0), b.get("converted", 0))])
    return out
