"""
Tenant + website persistence for the admin dashboard (req A, B).

Two raw-DDL tables kept separate from the CORTEX ORM (same approach as
``site_tours`` / ``conversation_cache``) so they need no migration and can't
perturb the knowledge schema:

* ``tenants``         — a person who signs up (email + bcrypt password hash).
* ``tenant_websites`` — a site a tenant attaches. Its ``site_key`` is the slug
  the ``<fluid-buddha>`` SDK passes as ``data-site``; ``site_entity_id(site_key)``
  (app/config.py) already maps any string to an isolated cortex tree, so tenant
  sites need no change to the grounding layer.
"""
from __future__ import annotations

import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import SITE_KEYS

logger = logging.getLogger(__name__)

# Built-in demo/seed sites. They are not tenant-owned, so no tenant may register
# a website under one of these keys (see docs/defects.md D-4).
_RESERVED_SITE_KEYS = set(SITE_KEYS)

_DDL_TENANTS = """
CREATE TABLE IF NOT EXISTS tenants (
    id            uuid PRIMARY KEY,
    email         text UNIQUE NOT NULL,
    password_hash text NOT NULL,
    name          text,
    created_at    timestamptz NOT NULL DEFAULT now()
)
"""

_DDL_WEBSITES = """
CREATE TABLE IF NOT EXISTS tenant_websites (
    id           uuid PRIMARY KEY,
    tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    site_key     text UNIQUE NOT NULL,
    public_key   text,
    name         text NOT NULL,
    domain       text,
    intelligence text NOT NULL DEFAULT 'advance',
    design       text NOT NULL DEFAULT 'level1',
    accent       text,
    status       text NOT NULL DEFAULT 'active',
    created_at   timestamptz NOT NULL DEFAULT now()
)
"""

# Idempotent bridge until Alembic (F-3): add the widget public_key to pre-existing
# tables and enforce its uniqueness. Postgres allows multiple NULLs in a UNIQUE
# index, so older rows without a key are fine.
_DDL_WEBSITES_MIGRATE = (
    "ALTER TABLE tenant_websites ADD COLUMN IF NOT EXISTS public_key text",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_websites_public_key "
    "ON tenant_websites(public_key)",
)


@dataclass
class Tenant:
    id: uuid.UUID
    email: str
    name: Optional[str]
    created_at: datetime

    def public(self) -> dict:
        return {
            "id": str(self.id),
            "email": self.email,
            "name": self.name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Website:
    id: uuid.UUID
    tenant_id: uuid.UUID
    site_key: str
    name: str
    domain: Optional[str]
    intelligence: str
    design: str
    accent: Optional[str]
    status: str
    created_at: datetime
    public_key: Optional[str] = None

    def public(self) -> dict:
        return {
            "id": str(self.id),
            "site_key": self.site_key,
            # The widget key the owner embeds; server-resolved on the public path
            # so the client never selects a site or tier (docs/defects.md D-1).
            "public_key": self.public_key,
            "name": self.name,
            "domain": self.domain,
            "intelligence": self.intelligence,
            "design": self.design,
            "accent": self.accent,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


async def ensure_tables(db: AsyncSession) -> None:
    await db.execute(text(_DDL_TENANTS))
    await db.execute(text(_DDL_WEBSITES))
    for stmt in _DDL_WEBSITES_MIGRATE:
        await db.execute(text(stmt))


def slugify(name: str) -> str:
    """A url/site-key-safe slug from a website name."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "site"


def generate_public_key() -> str:
    """An unguessable per-website widget key (embedded in the SDK snippet)."""
    return "fbk_" + secrets.token_urlsafe(24)


# ---- tenants --------------------------------------------------------------
async def create_tenant(
    db: AsyncSession, *, email: str, password_hash: str, name: Optional[str] = None
) -> Tenant:
    await ensure_tables(db)
    tid = uuid.uuid4()
    await db.execute(
        text(
            "INSERT INTO tenants (id, email, password_hash, name) "
            "VALUES (:id, :email, :ph, :name)"
        ),
        {"id": tid, "email": email.strip().lower(), "ph": password_hash, "name": name},
    )
    await db.commit()
    return Tenant(id=tid, email=email.strip().lower(), name=name, created_at=datetime.utcnow())


async def get_tenant_by_email(db: AsyncSession, email: str) -> Optional[dict]:
    """Returns the full row incl. password_hash (for login verification)."""
    await ensure_tables(db)
    res = await db.execute(
        text("SELECT id, email, password_hash, name, created_at FROM tenants "
             "WHERE email = :email"),
        {"email": (email or "").strip().lower()},
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Optional[Tenant]:
    await ensure_tables(db)
    res = await db.execute(
        text("SELECT id, email, name, created_at FROM tenants WHERE id = :id"),
        {"id": tenant_id},
    )
    row = res.mappings().first()
    if not row:
        return None
    return Tenant(id=row["id"], email=row["email"], name=row["name"],
                  created_at=row["created_at"])


# ---- websites -------------------------------------------------------------
async def site_key_exists(db: AsyncSession, site_key: str) -> bool:
    await ensure_tables(db)
    res = await db.execute(
        text("SELECT 1 FROM tenant_websites WHERE site_key = :k"), {"k": site_key}
    )
    return res.first() is not None


async def _unique_site_key(db: AsyncSession, base: str) -> str:
    # Reserved built-in keys count as taken, so a tenant can never be assigned
    # one and hijack a seeded demo site (docs/defects.md D-4).
    def taken(k: str) -> bool:
        return k in _RESERVED_SITE_KEYS

    key = base
    n = 1
    while taken(key) or await site_key_exists(db, key):
        n += 1
        key = f"{base}-{n}"
    return key


async def create_website(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    name: str,
    domain: Optional[str] = None,
    intelligence: str = "advance",
    design: str = "level1",
    accent: Optional[str] = None,
) -> Website:
    await ensure_tables(db)
    wid = uuid.uuid4()
    site_key = await _unique_site_key(db, slugify(name))
    public_key = generate_public_key()
    await db.execute(
        text(
            "INSERT INTO tenant_websites "
            "(id, tenant_id, site_key, public_key, name, domain, intelligence, design, accent) "
            "VALUES (:id, :tid, :sk, :pk, :name, :domain, :intel, :design, :accent)"
        ),
        {
            "id": wid, "tid": tenant_id, "sk": site_key, "pk": public_key, "name": name,
            "domain": domain, "intel": intelligence, "design": design, "accent": accent,
        },
    )
    await db.commit()
    return Website(
        id=wid, tenant_id=tenant_id, site_key=site_key, name=name, domain=domain,
        intelligence=intelligence, design=design, accent=accent, status="active",
        created_at=datetime.utcnow(), public_key=public_key,
    )


def _row_to_website(row) -> Website:
    return Website(
        id=row["id"], tenant_id=row["tenant_id"], site_key=row["site_key"],
        name=row["name"], domain=row["domain"], intelligence=row["intelligence"],
        design=row["design"], accent=row["accent"], status=row["status"],
        created_at=row["created_at"], public_key=row.get("public_key"),
    )


_WEBSITE_COLS = (
    "id, tenant_id, site_key, public_key, name, domain, intelligence, "
    "design, accent, status, created_at"
)


async def list_websites(db: AsyncSession, tenant_id: uuid.UUID) -> list[Website]:
    await ensure_tables(db)
    res = await db.execute(
        text(f"SELECT {_WEBSITE_COLS} FROM tenant_websites WHERE tenant_id = :tid "
             "ORDER BY created_at DESC"),
        {"tid": tenant_id},
    )
    return [_row_to_website(r) for r in res.mappings().all()]


async def get_website(
    db: AsyncSession, website_id: uuid.UUID, tenant_id: uuid.UUID
) -> Optional[Website]:
    """Tenant-scoped fetch: returns None if the site isn't owned by this tenant."""
    await ensure_tables(db)
    res = await db.execute(
        text(f"SELECT {_WEBSITE_COLS} FROM tenant_websites "
             "WHERE id = :id AND tenant_id = :tid"),
        {"id": website_id, "tid": tenant_id},
    )
    row = res.mappings().first()
    return _row_to_website(row) if row else None


async def get_website_by_public_key(
    db: AsyncSession, public_key: str
) -> Optional[Website]:
    """Resolve a website from its widget key (the public, unauthenticated path)."""
    if not public_key:
        return None
    await ensure_tables(db)
    res = await db.execute(
        text(f"SELECT {_WEBSITE_COLS} FROM tenant_websites WHERE public_key = :pk"),
        {"pk": public_key},
    )
    row = res.mappings().first()
    return _row_to_website(row) if row else None


def is_reserved_site_key(site_key: str) -> bool:
    return site_key in _RESERVED_SITE_KEYS


async def update_website(
    db: AsyncSession, website_id: uuid.UUID, tenant_id: uuid.UUID, **fields
) -> Optional[Website]:
    allowed = {"name", "domain", "intelligence", "design", "accent", "status"}
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not sets:
        return await get_website(db, website_id, tenant_id)
    assignments = ", ".join(f"{k} = :{k}" for k in sets)
    params = {**sets, "id": website_id, "tid": tenant_id}
    await db.execute(
        text(f"UPDATE tenant_websites SET {assignments} "
             "WHERE id = :id AND tenant_id = :tid"),
        params,
    )
    await db.commit()
    return await get_website(db, website_id, tenant_id)


async def delete_website(
    db: AsyncSession, website_id: uuid.UUID, tenant_id: uuid.UUID, site_key: str
) -> bool:
    """Delete a website and everything built for it (docs/defects.md D-6).

    The row delete cascades to ``tenant_sources``; the knowledge tree, tour,
    replay caches and usage rows are purged in the same transaction so a later
    site that reuses the slug can never inherit them.
    """
    from app.cortex.purge import purge_site

    await ensure_tables(db)
    res = await db.execute(
        text("DELETE FROM tenant_websites WHERE id = :id AND tenant_id = :tid"),
        {"id": website_id, "tid": tenant_id},
    )
    if not (res.rowcount or 0):
        await db.rollback()
        return False
    removed = await purge_site(db, site_key)
    await db.commit()
    logger.info("deleted website site=%s purged=%s", site_key, removed)
    return True
