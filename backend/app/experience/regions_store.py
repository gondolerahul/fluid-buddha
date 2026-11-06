"""
Storage for adaptive regions (Phase 1): the site switch, region slots, intent
families and the G1 plan cache.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
RULE_KEYS = ("paths", "utm_source", "utm_medium", "utm_campaign", "referrer_hosts", "query_terms")
PLAN_STATUSES = ("auto", "pinned", "blocked")


def _iso(v: Any) -> Any:
    return v.isoformat() if hasattr(v, "isoformat") else v


# ---- site switch ------------------------------------------------------------

async def regions_enabled(db: AsyncSession, site_key: str) -> bool:
    v = (await db.execute(text("SELECT regions_enabled FROM site_experience WHERE site_key = :sk"),
                          {"sk": site_key})).scalar()
    return True if v is None else bool(v)


async def set_regions_enabled(db: AsyncSession, site_key: str, enabled: bool) -> None:
    await db.execute(text("""
        INSERT INTO site_experience (site_key, regions_enabled) VALUES (:sk, :e)
        ON CONFLICT (site_key) DO UPDATE SET regions_enabled = EXCLUDED.regions_enabled, updated_at = now()
    """), {"sk": site_key, "e": enabled})
    await db.commit()


# ---- region slots -----------------------------------------------------------

@dataclass
class RegionSlot:
    id: str
    name: str
    label: str = ""
    purpose: str = ""
    components: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    enabled: bool = True

    def on_page(self, path: str) -> bool:
        return not self.pages or any(fnmatch.fnmatchcase(path, p) for p in self.pages)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "label": self.label, "purpose": self.purpose,
                "components": self.components, "pages": self.pages, "enabled": self.enabled}


def _slot(r: Any) -> RegionSlot:
    return RegionSlot(id=str(r.id), name=r.name, label=r.label, purpose=r.purpose,
                      components=list(r.components or []), pages=list(r.pages or []),
                      enabled=bool(r.enabled))


async def list_slots(db: AsyncSession, site_key: str) -> list[RegionSlot]:
    rows = (await db.execute(text(
        "SELECT id, name, label, purpose, components, pages, enabled FROM site_regions "
        "WHERE site_key = :sk ORDER BY name"), {"sk": site_key})).all()
    return [_slot(r) for r in rows]


async def upsert_slot(db: AsyncSession, site_key: str, slot: dict[str, Any]) -> RegionSlot:
    await db.execute(text("""
        INSERT INTO site_regions (id, site_key, name, label, purpose, components, pages, enabled)
        VALUES (:id, :sk, :name, :label, :purpose, :components, :pages, :enabled)
        ON CONFLICT (site_key, name) DO UPDATE SET label = EXCLUDED.label, purpose = EXCLUDED.purpose,
            components = EXCLUDED.components, pages = EXCLUDED.pages, enabled = EXCLUDED.enabled
    """), {"id": uuid.uuid4(), "sk": site_key, **slot})
    await db.commit()
    row = (await db.execute(text(
        "SELECT id, name, label, purpose, components, pages, enabled FROM site_regions "
        "WHERE site_key = :sk AND name = :n"), {"sk": site_key, "n": slot["name"]})).first()
    return _slot(row)


async def delete_slot(db: AsyncSession, site_key: str, name: str) -> bool:
    res = await db.execute(text("DELETE FROM site_regions WHERE site_key = :sk AND name = :n"),
                           {"sk": site_key, "n": name})
    await db.commit()
    return (res.rowcount or 0) > 0


# ---- intent families --------------------------------------------------------

@dataclass
class IntentFamily:
    id: str
    slug: str
    label: str
    description: str = ""
    stage: str = ""
    rules: dict[str, list[str]] = field(default_factory=dict)
    priority: int = 0
    enabled: bool = True
    updated_at: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "slug": self.slug, "label": self.label, "description": self.description,
                "stage": self.stage, "rules": self.rules, "priority": self.priority,
                "enabled": self.enabled, "updated_at": _iso(self.updated_at)}


def clean_rules(raw: Any) -> dict[str, list[str]]:
    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, list[str]] = {}
    for k in RULE_KEYS:
        v = raw.get(k)
        if isinstance(v, str):
            v = [x for x in re.split(r"[,\n]", v)]
        if isinstance(v, list):
            items = [str(x).strip().lower()[:120] for x in v if str(x).strip()][:30]
            if items:
                out[k] = items
    return out


def _family(r: Any) -> IntentFamily:
    rules = r.rules if isinstance(r.rules, dict) else json.loads(r.rules or "{}")
    return IntentFamily(id=str(r.id), slug=r.slug, label=r.label, description=r.description,
                        stage=r.stage, rules=rules, priority=r.priority, enabled=bool(r.enabled),
                        updated_at=r.updated_at)


async def list_families(db: AsyncSession, site_key: str) -> list[IntentFamily]:
    rows = (await db.execute(text(
        "SELECT id, slug, label, description, stage, rules, priority, enabled, updated_at "
        "FROM site_intent_families WHERE site_key = :sk ORDER BY priority DESC, slug"),
        {"sk": site_key})).all()
    return [_family(r) for r in rows]


async def upsert_family(db: AsyncSession, site_key: str, fam: dict[str, Any]) -> IntentFamily:
    await db.execute(text("""
        INSERT INTO site_intent_families (id, site_key, slug, label, description, stage, rules, priority, enabled)
        VALUES (:id, :sk, :slug, :label, :description, :stage, CAST(:rules AS jsonb), :priority, :enabled)
        ON CONFLICT (site_key, slug) DO UPDATE SET label = EXCLUDED.label,
            description = EXCLUDED.description, stage = EXCLUDED.stage, rules = EXCLUDED.rules,
            priority = EXCLUDED.priority, enabled = EXCLUDED.enabled, updated_at = now()
    """), {"id": uuid.uuid4(), "sk": site_key, **fam, "rules": json.dumps(fam["rules"])})
    await db.commit()
    row = (await db.execute(text(
        "SELECT id, slug, label, description, stage, rules, priority, enabled, updated_at "
        "FROM site_intent_families WHERE site_key = :sk AND slug = :s"),
        {"sk": site_key, "s": fam["slug"]})).first()
    return _family(row)


async def delete_family(db: AsyncSession, site_key: str, slug: str) -> bool:
    res = await db.execute(text("DELETE FROM site_intent_families WHERE site_key = :sk AND slug = :s"),
                           {"sk": site_key, "s": slug})
    await db.commit()
    return (res.rowcount or 0) > 0


# ---- plan cache -------------------------------------------------------------

def normalize_page(page: Any) -> str:
    p = str(page or "/").split("?", 1)[0].split("#", 1)[0].strip().lower() or "/"
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1:
        p = p.rstrip("/")
    return p[:300]


def plan_cache_key(*, family: str, persona: str, lang: str, page: str, regions: list[str],
                   content_version: str, manifest_version: Optional[int]) -> str:
    raw = json.dumps([family, persona or "", lang or "en", normalize_page(page), sorted(regions),
                      content_version, manifest_version])
    return hashlib.sha256(raw.encode()).hexdigest()[:40]


_PLAN_COLS = ("id, site_key, cache_key, family, persona, lang, page, regions, content_version, "
              "manifest_version, plan, composer, status, hit_count, build_ms, created_at, last_hit_at")


def _plan_row(r: Any) -> dict[str, Any]:
    m = dict(r._mapping)
    m["id"] = str(m["id"])
    m["regions"] = [x for x in (m.get("regions") or "").split(",") if x]
    for k in ("created_at", "last_hit_at"):
        m[k] = _iso(m.get(k))
    return m


async def pinned_plan(db: AsyncSession, site_key: str, *, family: str, page: str,
                      regions: list[str]) -> Optional[dict[str, Any]]:
    r = (await db.execute(text(
        f"SELECT {_PLAN_COLS} FROM plan_cache WHERE site_key = :sk AND family = :f AND page = :p "
        "AND regions = :r AND status = 'pinned' ORDER BY created_at DESC LIMIT 1"),
        {"sk": site_key, "f": family, "p": normalize_page(page), "r": ",".join(sorted(regions))})).first()
    return _plan_row(r) if r else None


async def cached_plan(db: AsyncSession, site_key: str, key: str) -> Optional[dict[str, Any]]:
    r = (await db.execute(text(
        f"SELECT {_PLAN_COLS} FROM plan_cache WHERE site_key = :sk AND cache_key = :k "
        "AND status <> 'blocked'"), {"sk": site_key, "k": key})).first()
    return _plan_row(r) if r else None


async def record_hit(db: AsyncSession, plan_row_id: str) -> None:
    await db.execute(text("UPDATE plan_cache SET hit_count = hit_count + 1, last_hit_at = now() "
                          "WHERE id = :id"), {"id": uuid.UUID(plan_row_id)})
    await db.commit()


async def store_plan(db: AsyncSession, site_key: str, *, key: str, family: str, persona: str,
                     lang: str, page: str, regions: list[str], content_version: str,
                     manifest_version: Optional[int], plan: dict[str, Any], composer: str,
                     build_ms: int) -> dict[str, Any]:
    await db.execute(text("""
        INSERT INTO plan_cache (id, site_key, cache_key, family, persona, lang, page, regions,
            content_version, manifest_version, plan, composer, build_ms)
        VALUES (:id, :sk, :k, :f, :persona, :lang, :page, :regions, :cv, :mv, CAST(:plan AS jsonb), :composer, :ms)
        ON CONFLICT (site_key, cache_key) DO UPDATE SET plan = EXCLUDED.plan, composer = EXCLUDED.composer,
            build_ms = EXCLUDED.build_ms, created_at = now()
          WHERE plan_cache.status = 'auto'
    """), {"id": uuid.uuid4(), "sk": site_key, "k": key, "f": family, "persona": persona or "",
           "lang": lang or "en", "page": normalize_page(page), "regions": ",".join(sorted(regions)),
           "cv": content_version, "mv": manifest_version, "plan": json.dumps(plan),
           "composer": composer, "ms": build_ms})
    await db.commit()
    got = await cached_plan(db, site_key, key)
    assert got is not None
    return got


async def list_plans(db: AsyncSession, site_key: str, *, family: Optional[str] = None,
                     persona: Optional[str] = None, page: Optional[str] = None,
                     status: Optional[str] = None, limit: int = 100) -> list[dict[str, Any]]:
    where = ["site_key = :sk"]
    params: dict[str, Any] = {"sk": site_key, "lim": max(1, min(limit, 500))}
    for col, val in (("family", family), ("persona", persona), ("status", status)):
        if val is not None and val != "":
            where.append(f"{col} = :{col}")
            params[col] = val
    if page:
        where.append("page = :page")
        params["page"] = normalize_page(page)
    rows = (await db.execute(text(
        f"SELECT {_PLAN_COLS} FROM plan_cache WHERE {' AND '.join(where)} "
        "ORDER BY (status = 'pinned') DESC, hit_count DESC, created_at DESC LIMIT :lim"), params)).all()
    return [_plan_row(r) for r in rows]


async def get_plan(db: AsyncSession, site_key: str, plan_row_id: str) -> Optional[dict[str, Any]]:
    try:
        pid = uuid.UUID(plan_row_id)
    except ValueError:
        return None
    r = (await db.execute(text(f"SELECT {_PLAN_COLS} FROM plan_cache WHERE site_key = :sk AND id = :id"),
                          {"sk": site_key, "id": pid})).first()
    return _plan_row(r) if r else None


async def set_plan_status(db: AsyncSession, site_key: str, plan_row_id: str, status: str) -> Optional[dict[str, Any]]:
    """Pin, unpin or block. Blocking frees the row's cache key (renamed), so the
    next visitor with that key triggers a fresh build."""
    cur = await get_plan(db, site_key, plan_row_id)
    if cur is None or status not in PLAN_STATUSES:
        return None
    if status == "pinned":
        # One pinned plan per (family, page, region set).
        await db.execute(text(
            "UPDATE plan_cache SET status = 'auto' WHERE site_key = :sk AND family = :f AND page = :p "
            "AND regions = :r AND status = 'pinned' AND id <> :id"),
            {"sk": site_key, "f": cur["family"], "p": cur["page"], "r": ",".join(cur["regions"]),
             "id": uuid.UUID(plan_row_id)})
    key_sql = ", cache_key = cache_key || '#blocked#' || left(id::text, 8)" \
        if status == "blocked" and "#blocked#" not in cur["cache_key"] else ""
    await db.execute(text(f"UPDATE plan_cache SET status = :st{key_sql} WHERE site_key = :sk AND id = :id"),
                     {"st": status, "sk": site_key, "id": uuid.UUID(plan_row_id)})
    await db.commit()
    return await get_plan(db, site_key, plan_row_id)


async def delete_plan(db: AsyncSession, site_key: str, plan_row_id: str) -> bool:
    try:
        pid = uuid.UUID(plan_row_id)
    except ValueError:
        return False
    res = await db.execute(text("DELETE FROM plan_cache WHERE site_key = :sk AND id = :id"),
                           {"sk": site_key, "id": pid})
    await db.commit()
    return (res.rowcount or 0) > 0
