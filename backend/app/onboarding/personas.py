"""
Derive visitor personas from a crawled site (WS9).

Sites usually say who they serve in their URLs: ``/for/startups``,
``/solutions/agencies``, ``/industries/healthcare``. Each such page becomes a
persona (slug from the path, label from its heading, focus from its
description) with that page as its landing route. When the URLs don't say, a
real model is asked to read the page titles and descriptions and propose two to
four; in mock mode that step is skipped.

Personas are only added to a site that has none, so a tenant's own edits are
never overwritten.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional
from urllib.parse import urlsplit

from app.onboarding.crawler import CrawledPage
from app.orchestrator.profile import Persona

logger = logging.getLogger(__name__)

MAX_PERSONAS = 6
_AUDIENCE_DIRS = {
    "for", "solutions", "solution", "industries", "industry", "use-cases", "usecases",
    "use-case", "who-we-serve", "customers", "teams", "roles", "audiences", "segments",
    "verticals", "sectors",
}
# Child pages under an audience dir that are not audiences.
_NOT_AUDIENCE = {"overview", "all", "index", "page", "case-studies", "pricing"}
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _SLUG_RE.sub("-", (text or "").lower()).strip("-")[:48]


def _first_sentence(text: str, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    return s[:limit].rstrip()


def _clean_label(page: CrawledPage, segment: str) -> str:
    label = (page.info.h1 if page.info else "") or ""
    if not label or len(label) > 60:
        label = segment.replace("-", " ").replace("_", " ").title()
    return label.strip()


def from_urls(pages: list[CrawledPage]) -> list[Persona]:
    """Personas named by audience-style URLs."""
    out: list[Persona] = []
    for page in pages:
        segs = [s for s in urlsplit(page.url).path.lower().split("/") if s]
        for i, seg in enumerate(segs[:-1]):
            if seg not in _AUDIENCE_DIRS:
                continue
            child = segs[i + 1]
            if child in _NOT_AUDIENCE:
                break
            slug = slugify(re.sub(r"^for-", "", child))
            if slug and all(p.slug != slug for p in out):
                desc = (page.info.description if page.info else "") or ""
                out.append(Persona(
                    slug=slug,
                    label=_clean_label(page, child),
                    focus=_first_sentence(desc or (page.info.text if page.info else "")),
                    landing="/" + "/".join(segs),
                ))
            break
        if len(out) >= MAX_PERSONAS:
            break
    return out


_PROMPT = """You are setting up a website's sales assistant. From the pages below,
name the 2 to 4 kinds of visitors the site is written for (for example: "startup
founders", "enterprise IT", "clinic managers"). Reply with JSON only:
[{"label": "...", "focus": "what they care about, under 15 words",
  "tone": "how to speak to them, under 8 words", "landing": "/path or empty"}]

Pages:
"""


async def from_model(pages: list[CrawledPage], llm) -> list[Persona]:
    """Ask the model for personas when the URLs don't name any."""
    lines = []
    for p in pages[:20]:
        if not p.info:
            continue
        path = urlsplit(p.url).path or "/"
        lines.append(f"- {path} | {p.info.name} | {p.info.description[:160]}")
    if not lines:
        return []
    from app.ai.base import ChatMessage

    try:
        resp = await llm.generate(
            system="Reply with JSON only.",
            messages=[ChatMessage(role="user", text=_PROMPT + "\n".join(lines))],
            tools=None, temperature=0.2, max_output_tokens=600,
        )
    except Exception as exc:
        logger.warning("persona suggestion failed: %s", exc)
        return []
    return parse_model_personas(getattr(resp, "text", "") or "")


def parse_model_personas(text: str) -> list[Persona]:
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    try:
        items = json.loads(m.group(0))
    except ValueError:
        return []
    out: list[Persona] = []
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        label = str(it.get("label") or "").strip()[:60]
        slug = slugify(label)
        if not slug or any(p.slug == slug for p in out):
            continue
        landing = str(it.get("landing") or "").strip()
        out.append(Persona(
            slug=slug, label=label[:1].upper() + label[1:],
            focus=str(it.get("focus") or "").strip()[:160],
            tone=str(it.get("tone") or "").strip()[:80],
            landing=landing if landing.startswith("/") else "",
        ))
        if len(out) >= 4:
            break
    return out


async def derive_personas(pages: list[CrawledPage], llm: Optional[object] = None,
                          *, mock: bool = True) -> list[Persona]:
    found = from_urls(pages)
    if len(found) >= 2 or mock or llm is None:
        return found
    return found or await from_model(pages, llm)
