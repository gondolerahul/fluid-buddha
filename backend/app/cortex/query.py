"""
The ``query_cortex`` retrieval tool + grounding guardrail (Req 3.4.3).

Returns the top grounded snippets and a ``confidence`` = best cosine similarity.
The Heavy Thinker's system prompt forbids answering capability/pricing/integration
questions without calling this first; when ``confidence`` falls below the
configured threshold the agent must pivot gracefully instead of inventing facts.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional
from urllib.parse import urlsplit

from app.cortex.bridge import CortexBridge

logger = logging.getLogger(__name__)


async def query_cortex(
    bridge: CortexBridge,
    query: str,
    *,
    top_k: int = 5,
    threshold: float = 0.45,
) -> dict[str, Any]:
    rows = await bridge.search(query, top_k=top_k)
    snippets = [
        {
            "text": (r.get("content") or "").strip(),
            "score": round(float(r.get("score", 0.0)), 4),
            "document": r.get("document_title"),
            "section": r.get("section_title"),
            "filename": (r.get("source_ref") or {}).get("filename"),
        }
        for r in rows
        if (r.get("content") or "").strip()
    ]
    confidence = snippets[0]["score"] if snippets else 0.0
    grounded = confidence >= threshold
    result = {
        "query": query,
        "found": grounded,
        "confidence": confidence,
        "snippets": snippets if grounded else snippets[:2],
    }
    if not grounded:
        result["guardrail"] = (
            "Low retrieval confidence. Do NOT invent capabilities. Acknowledge "
            "the gap and pivot to the closest supported capability or offer to "
            "connect the user with the team."
        )
    logger.info(
        "query_cortex(%r) -> found=%s confidence=%.3f (%d snippets)",
        query[:60], grounded, confidence, len(snippets),
    )
    return result


def _label(name: str) -> str:
    """A readable source name: ``📄 07-pricing.md`` → ``Pricing``."""
    base = re.sub(r"^[^\w]+", "", (name or "").strip())   # leading icon/punctuation
    if base.startswith(("http://", "https://")):
        path = urlsplit(base).path.strip("/")
        base = path.rsplit("/", 1)[-1] if path else urlsplit(base).netloc
    base = re.sub(r"\.(md|txt|html?)$", "", base, flags=re.IGNORECASE)
    base = re.sub(r"^\d+[-_]", "", base)
    words = re.sub(r"[-_]+", " ", base).strip()
    return words[:1].upper() + words[1:] if words else "Source"


def _route(name: str) -> Optional[str]:
    from app.orchestrator.sitemap import route_from_url
    from ingestion.scraper import route_for

    if (name or "").startswith(("http://", "https://")):
        return route_from_url(name) or None
    return route_for(name or "")


def citations(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Grounding sources for the visitor (WS8): one entry per source document,
    best score first, with a readable label and the site route when known."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for s in snippets:
        name = s.get("filename") or s.get("document") or ""
        if not name or name in seen:
            continue
        seen.add(name)
        entry: dict[str, Any] = {
            "document": s.get("document"), "section": s.get("section"),
            "score": s.get("score"), "label": _label(name),
        }
        route = _route(name)
        if route:
            entry["route"] = route
        out.append(entry)
    return out
