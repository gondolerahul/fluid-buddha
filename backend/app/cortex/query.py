"""
The ``query_cortex`` retrieval tool + zero-hallucination guardrail (Req 3.4.3).

Returns the top grounded snippets and a ``confidence`` = best cosine similarity.
The Heavy Thinker's system prompt forbids answering capability/pricing/integration
questions without calling this first; when ``confidence`` falls below the
configured threshold the agent must pivot gracefully instead of inventing facts.
"""
from __future__ import annotations

import logging
from typing import Any

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
