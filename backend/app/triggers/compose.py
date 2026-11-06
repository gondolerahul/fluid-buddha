"""
The agent writes a proactive trigger's message for the page (M2-3 follow-up).

A rule with ``compose`` asks for one short opener that fits the page the visitor
is on ("Comparing plans? I can tell you which fits a 20-person team."). It is
written once per rule, page and language and cached in ``trigger_messages``, so
a busy page costs one model call. The rule's own message is the fallback —
when the model is unavailable, for bots, for pages outside the rule's page
list, and once a rule has ``MAX_PAGES`` cached pages (so arbitrary URLs can't
run up model spend).

In mock mode the opener is built from the page title, deterministically.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MAX_PAGES = 200
MAX_CHARS = 160

PROMPT = """You write the one-line opener a website's AI assistant shows when it
offers help to a visitor who has been on a page for a while.

Company: {company}
Page path: {path}
Page title: {title}
The site owner's default message (keep its intent): {fallback}

Rules: one sentence (at most 18 words), friendly and specific to this page,
invites a question, written in {language}. Keep product and company names as
written. No emojis, no quotation marks, no prices, discounts or promises.
Reply with the sentence only."""


def page_matches(path: str, patterns: list[str]) -> bool:
    """Same rule as the widget: no patterns = everywhere; ``*`` matches anything."""
    if not patterns:
        return True
    for p in patterns:
        rx = "^" + re.escape(p).replace(r"\*", ".*") + "$"
        if re.match(rx, path):
            return True
    return False


def clean_path(page: str) -> str:
    page = (page or "/").split("?")[0].split("#")[0].strip() or "/"
    return page[:200] if page.startswith("/") else "/"


def _topic(title: str, path: str) -> str:
    """'Pricing | Acme' → 'Pricing'; '/blog/sso-guide' → 'sso guide'."""
    t = re.split(r"\s[|\-–—·]\s", title or "")[0].strip()
    if not t:
        seg = [s for s in path.split("/") if s]
        t = (seg[-1] if seg else "").replace("-", " ").replace("_", " ").strip()
    return t[:60]


def mock_message(title: str, path: str, lang: str, fallback: str) -> str:
    topic = _topic(title, path)
    if not topic:
        return fallback
    if lang == "hi":
        return f"{topic} के बारे में कोई सवाल? मैं यहीं जवाब दे सकती हूँ।"
    return f"Questions about {topic}? I can answer them right here."


def tidy(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip()).strip("\"'“”‘’ ")
    if len(s) > MAX_CHARS:
        s = s[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return s


async def message_for(db: AsyncSession, *, site_key: str, rule: dict, page: str, title: str,
                      lang: str, llm: Any = None, model: Optional[str] = None,
                      company: str = "") -> str:
    """The opener for ``rule`` on ``page`` (cached), or the rule's message."""
    fallback = rule["message"]
    path = clean_path(page)
    lang = "hi" if lang == "hi" else "en"
    if not rule.get("compose") or not page_matches(path, rule.get("pages") or []):
        return fallback
    cached = (await db.execute(text(
        "SELECT message FROM trigger_messages WHERE rule_id = :r AND page = :p AND lang = :l"),
        {"r": rule["id"], "p": path, "l": lang})).scalar()
    if cached:
        return cached
    n = (await db.execute(text("SELECT count(*) FROM trigger_messages WHERE rule_id = :r"),
                          {"r": rule["id"]})).scalar() or 0
    if n >= MAX_PAGES:
        return fallback
    title = re.sub(r"\s+", " ", title or "")[:120]
    if llm is None:
        message = mock_message(title, path, lang, fallback)
    else:
        from app.ai.base import ChatMessage
        from app.analytics.pricing import estimate_tokens
        from app.analytics.usage import record_background

        system = PROMPT.format(company=company or "the company", path=path, title=title or "(none)",
                               fallback=fallback, language="Hindi" if lang == "hi" else "English")
        try:
            resp = await llm.generate(system=system, messages=[ChatMessage(role="user", text="Write it.")],
                                      model=model, temperature=0.4, max_output_tokens=60,
                                      thinking_budget=0)
            message = tidy(resp.text) or fallback
            await record_background(db, site_key, intent="trigger",
                                    input_tokens=resp.input_tokens or estimate_tokens(system),
                                    output_tokens=resp.output_tokens or estimate_tokens(resp.text))
        except Exception as exc:
            logger.warning("trigger message not written (rule %s): %s", rule["id"], exc)
            return fallback
    await db.execute(text(
        "INSERT INTO trigger_messages (rule_id, page, lang, message) VALUES (:r, :p, :l, :m) "
        "ON CONFLICT DO NOTHING"), {"r": rule["id"], "p": path, "l": lang, "m": message})
    await db.commit()
    return message
