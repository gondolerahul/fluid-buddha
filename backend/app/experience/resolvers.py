"""Resolvers for bindings that need the database or site knowledge (P2-6):
``entity:<Type>`` and ``content:search``."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.experience.entities import resolve_entity_binding

logger = logging.getLogger(__name__)


def make_resolver(db: AsyncSession, rt: Any, site_key: str, bridge: Any = None):
    async def resolve(ref: str, params: dict[str, Any]) -> Any:
        if ref.startswith("entity:"):
            return await resolve_entity_binding(db, site_key, ref[7:], params)
        if ref == "content:search":
            query = str(params.get("query") or "")[:300]
            if not query or (rt is None and bridge is None):
                return []
            try:
                b = bridge if bridge is not None else rt.bridge(db, site_key=site_key)
                found = await b.search(query, top_k=int(params.get("limit") or 4))
            except Exception as exc:
                logger.warning("content binding search failed: %s", exc)
                return []
            from app.config import get_settings

            threshold = get_settings().cortex_confidence_threshold
            return [{"text": (r.get("content") or "").strip()[:800],
                     "label": (r.get("source_ref") or {}).get("filename") or r.get("document_title") or "Site content"}
                    for r in found if (r.get("content") or "").strip() and float(r.get("score") or 0) >= threshold]
        return None
    return resolve
