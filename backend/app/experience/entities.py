"""
Structured entities and content connectors (P2-6, strategy §4.2.4).

Generated pages need *records* to bind to, not only text to quote: products,
plans, case studies, locations, posts. Entities are typed JSON records keyed by
a slug, filled by hand, by importing JSON or CSV, or by a connector that syncs
a content feed:

* ``json_feed`` — any URL returning JSON (Strapi, Sanity, a headless CMS, a
  static file): ``items_path`` selects the list, ``key_field`` the slug, and
  ``fields`` maps output fields to input paths;
* ``wordpress`` — ``/wp-json/wp/v2/posts`` (or ``pages``) with the fields
  WordPress returns, flattened (``title``, ``excerpt``, ``content``, ``link``,
  ``date``, ``image``).

Syncing upserts by key and removes the connector's records the feed no longer
has. Fetching goes through the SSRF-safe fetcher.
"""
from __future__ import annotations

import csv
import html
import io
import json
import re
import uuid
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.experience.binding import select

TYPE_RE = re.compile(r"^[A-Z][A-Za-z0-9]{0,39}$")
MAX_ENTITIES_PER_TYPE = 2000
MAX_RECORD_BYTES = 20_000
_TAG_RE = re.compile(r"<[^>]+>")
_KEY_BAD = re.compile(r"[^a-z0-9-]+")

Fetch = Callable[..., Awaitable[Any]]


def clean_key(v: Any) -> str:
    return _KEY_BAD.sub("-", str(v or "").strip().lower()).strip("-")[:120]


def _strip_html(v: Any) -> str:
    return html.unescape(_TAG_RE.sub(" ", str(v or ""))).strip()


def _row(r: Any) -> dict[str, Any]:
    return {"id": str(r.id), "type": r.type, "key": r.key, "data": r.data, "source": r.source,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None}


# ---- entities ---------------------------------------------------------------

async def entity_types(db: AsyncSession, site_key: str) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT type, count(*) AS n FROM site_entities WHERE site_key = :sk GROUP BY type ORDER BY type"),
        {"sk": site_key})).all()
    return [{"type": r.type, "count": r.n} for r in rows]


async def list_entities(db: AsyncSession, site_key: str, etype: str, *, limit: int = 100,
                        offset: int = 0) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT id, type, key, data, source, updated_at FROM site_entities "
        "WHERE site_key = :sk AND type = :t ORDER BY key LIMIT :lim OFFSET :off"),
        {"sk": site_key, "t": etype, "lim": max(1, min(limit, 500)), "off": max(0, offset)})).all()
    return [_row(r) for r in rows]


async def get_entity(db: AsyncSession, site_key: str, etype: str, key: str) -> Optional[dict[str, Any]]:
    r = (await db.execute(text(
        "SELECT id, type, key, data, source, updated_at FROM site_entities "
        "WHERE site_key = :sk AND type = :t AND key = :k"), {"sk": site_key, "t": etype, "k": key})).first()
    return _row(r) if r else None


def check_record(etype: str, key: str, data: Any) -> Optional[str]:
    if not TYPE_RE.match(etype or ""):
        return "a type is a capitalised name such as Product or CaseStudy"
    if not key:
        return "each record needs a key"
    if not isinstance(data, dict):
        return "a record is a JSON object"
    if len(json.dumps(data, default=str)) > MAX_RECORD_BYTES:
        return f"record {key} is larger than {MAX_RECORD_BYTES // 1000} kB"
    return None


async def upsert_entities(db: AsyncSession, site_key: str, etype: str, records: list[tuple[str, dict]],
                          *, source: str = "manual") -> int:
    n = 0
    for key, data in records[:MAX_ENTITIES_PER_TYPE]:
        await db.execute(text("""
            INSERT INTO site_entities (id, site_key, type, key, data, source)
            VALUES (:id, :sk, :t, :k, CAST(:d AS jsonb), :src)
            ON CONFLICT (site_key, type, key) DO UPDATE SET data = EXCLUDED.data,
                source = EXCLUDED.source, updated_at = now()
        """), {"id": uuid.uuid4(), "sk": site_key, "t": etype, "k": key,
               "d": json.dumps(data, default=str), "src": source})
        n += 1
    await db.commit()
    return n


async def delete_entity(db: AsyncSession, site_key: str, etype: str, key: str) -> bool:
    res = await db.execute(text("DELETE FROM site_entities WHERE site_key = :sk AND type = :t AND key = :k"),
                           {"sk": site_key, "t": etype, "k": key})
    await db.commit()
    return (res.rowcount or 0) > 0


def parse_import(raw: str, fmt: str, key_field: str) -> tuple[list[tuple[str, dict]], list[str]]:
    """JSON (a list, or an object with one list) or CSV → ``[(key, record)]``."""
    problems: list[str] = []
    items: list[Any] = []
    if fmt == "csv":
        try:
            items = list(csv.DictReader(io.StringIO(raw)))
        except csv.Error as exc:
            return [], [f"CSV: {exc}"]
    else:
        try:
            data = json.loads(raw)
        except ValueError as exc:
            return [], [f"JSON: {exc}"]
        if isinstance(data, dict):
            lists = [v for v in data.values() if isinstance(v, list)]
            data = lists[0] if len(lists) == 1 else [data]
        items = data if isinstance(data, list) else []
    out: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for i, it in enumerate(items[:MAX_ENTITIES_PER_TYPE]):
        if not isinstance(it, dict):
            problems.append(f"item {i + 1}: not an object")
            continue
        key = clean_key(it.get(key_field) or it.get("slug") or it.get("id") or it.get("name") or it.get("title"))
        if not key:
            problems.append(f"item {i + 1}: no {key_field}")
            continue
        if key in seen:
            problems.append(f"item {i + 1}: duplicate key {key}")
            continue
        seen.add(key)
        out.append((key, {k: v for k, v in it.items() if v not in (None, "")}))
    return out, problems


# ---- bindings ---------------------------------------------------------------

async def resolve_entity_binding(db: AsyncSession, site_key: str, etype: str,
                                 params: dict[str, Any]) -> Any:
    """``entity:<Type>`` → one record (``params.key``) or a filtered list."""
    if not TYPE_RE.match(etype):
        return None
    key = params.get("key")
    if key:
        e = await get_entity(db, site_key, etype, clean_key(key))
        return {"key": e["key"], **e["data"]} if e else None
    limit = params.get("limit")
    try:
        limit = max(1, min(int(limit), 100)) if limit is not None else 50
    except (TypeError, ValueError):
        limit = 50
    rows = await list_entities(db, site_key, etype, limit=500)
    where = params.get("where") if isinstance(params.get("where"), dict) else {}
    out = []
    for r in rows:
        rec = {"key": r["key"], **r["data"]}
        if all(str(rec.get(k)) == str(v) for k, v in where.items()):
            out.append(rec)
        if len(out) >= limit:
            break
    return out


# ---- connectors -------------------------------------------------------------

KINDS = ("json_feed", "wordpress")


def _connector(r: Any) -> dict[str, Any]:
    return {"id": str(r.id), "kind": r.kind, "name": r.name, "url": r.url, "entity_type": r.entity_type,
            "config": r.config, "last_sync_at": r.last_sync_at.isoformat() if r.last_sync_at else None,
            "last_status": r.last_status}


async def list_connectors(db: AsyncSession, site_key: str) -> list[dict[str, Any]]:
    rows = (await db.execute(text(
        "SELECT id, kind, name, url, entity_type, config, last_sync_at, last_status FROM site_connectors "
        "WHERE site_key = :sk ORDER BY created_at"), {"sk": site_key})).all()
    return [_connector(r) for r in rows]


async def get_connector(db: AsyncSession, site_key: str, cid: str) -> Optional[dict[str, Any]]:
    try:
        u = uuid.UUID(cid)
    except ValueError:
        return None
    r = (await db.execute(text(
        "SELECT id, kind, name, url, entity_type, config, last_sync_at, last_status FROM site_connectors "
        "WHERE site_key = :sk AND id = :id"), {"sk": site_key, "id": u})).first()
    return _connector(r) if r else None


async def create_connector(db: AsyncSession, site_key: str, *, kind: str, name: str, url: str,
                           entity_type: str, config: dict[str, Any]) -> dict[str, Any]:
    cid = uuid.uuid4()
    await db.execute(text("""
        INSERT INTO site_connectors (id, site_key, kind, name, url, entity_type, config)
        VALUES (:id, :sk, :kind, :name, :url, :t, CAST(:c AS jsonb))
    """), {"id": cid, "sk": site_key, "kind": kind, "name": name, "url": url, "t": entity_type,
           "c": json.dumps(config)})
    await db.commit()
    got = await get_connector(db, site_key, str(cid))
    assert got is not None
    return got


async def delete_connector(db: AsyncSession, site_key: str, cid: str) -> bool:
    c = await get_connector(db, site_key, cid)
    if c is None:
        return False
    await db.execute(text("DELETE FROM site_entities WHERE site_key = :sk AND source = :src"),
                     {"sk": site_key, "src": f"connector:{cid}"})
    await db.execute(text("DELETE FROM site_connectors WHERE site_key = :sk AND id = :id"),
                     {"sk": site_key, "id": uuid.UUID(cid)})
    await db.commit()
    return True


def _wp_record(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    def rendered(k: str) -> str:
        v = item.get(k)
        return _strip_html(v.get("rendered") if isinstance(v, dict) else v)
    rec = {"title": rendered("title"), "excerpt": rendered("excerpt")[:600],
           "content": rendered("content")[:4000], "link": item.get("link") or "",
           "date": item.get("date") or ""}
    media = (item.get("_embedded") or {}).get("wp:featuredmedia") or []
    if media and isinstance(media[0], dict) and str(media[0].get("source_url", "")).startswith("https://"):
        rec["image"] = media[0]["source_url"]
    return clean_key(item.get("slug") or item.get("id")), {k: v for k, v in rec.items() if v}


def map_feed(data: Any, kind: str, config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Feed JSON → ``[(key, record)]`` for a connector."""
    if kind == "wordpress":
        items = data if isinstance(data, list) else []
        return [r for r in (_wp_record(i) for i in items if isinstance(i, dict)) if r[0]]
    items = select(data, config.get("items_path") or "$") if config.get("items_path") else data
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []
    key_field = config.get("key_field") or "slug"
    fields: dict[str, str] = config.get("fields") or {}
    out = []
    for it in items[:MAX_ENTITIES_PER_TYPE]:
        if not isinstance(it, dict):
            continue
        key = clean_key(select(it, key_field) if str(key_field).startswith("$") else it.get(key_field))
        if not key:
            continue
        if fields:
            rec = {name: select(it, path if path.startswith("$") else f"$.{path}") for name, path in fields.items()}
            rec = {k: v for k, v in rec.items() if v not in (None, "")}
        else:
            rec = {k: v for k, v in it.items() if v not in (None, "")}
        out.append((key, rec))
    return out


def feed_url(kind: str, url: str) -> str:
    if kind == "wordpress":
        base = url.rstrip("/")
        if "/wp-json/" in base:
            return base if "per_page" in base else base + ("&" if "?" in base else "?") + "per_page=50&_embed=1"
        return base + "/wp-json/wp/v2/posts?per_page=50&_embed=1"
    return url


async def sync_connector(db: AsyncSession, site_key: str, conn: dict[str, Any], fetch: Fetch) -> dict[str, Any]:
    """Fetch the feed, upsert its records, remove the ones it no longer has."""
    status = "ok"
    try:
        got = await fetch(feed_url(conn["kind"], conn["url"]), allowed_types=("application/json", "text/json"),
                          max_bytes=10_000_000)
        records = map_feed(json.loads(got.text), conn["kind"], conn.get("config") or {})
    except Exception as exc:
        records, status = [], f"failed: {str(exc)[:200]}"
    source = f"connector:{conn['id']}"
    n = 0
    if status == "ok":
        n = await upsert_entities(db, site_key, conn["entity_type"], records, source=source)
        keys = [k for k, _ in records]
        await db.execute(text(
            "DELETE FROM site_entities WHERE site_key = :sk AND source = :src AND NOT (key = ANY(:keys))"),
            {"sk": site_key, "src": source, "keys": keys})
        status = f"ok: {n} record{'s' if n != 1 else ''}"
    await db.execute(text(
        "UPDATE site_connectors SET last_sync_at = now(), last_status = :st WHERE id = :id"),
        {"st": status, "id": uuid.UUID(conn["id"])})
    await db.commit()
    return {"status": status, "records": n}
