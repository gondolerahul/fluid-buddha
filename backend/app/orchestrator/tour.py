"""
Guided Website Tour (Req 5) — planned ONCE at ingestion, played back at runtime.

A tour is an ordered list of stops. Each stop has a short spoken ``narration``
and an optional ``move`` to perform *after* the narration has finished playing
(scroll within the page, or navigate to another page). Because the plan is fully
authored at ingestion time, runtime playback needs no LLM at all — it's just
"speak → wait until done speaking → move → next", which is what makes the
speak/scroll sync exact (the frontend gates each move on audio completion).

The plan deliberately ends on a concrete use-case: how the site's platform would
automate it, the time-to-automate, the monthly/yearly time + money saved, and the
new capabilities it unlocks. The agent's name, the company and the fallback
closing example come from the site's profile (app/orchestrator/profile.py).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from app.ai.base import ChatMessage, LLMClient
from app.config import Settings
from app.orchestrator.profile import profile_for

logger = logging.getLogger(__name__)

# A move performed AFTER a stop's narration finishes playing.
#   {"type": "navigate", "route": "/pricing"}
#   {"type": "scroll", "target": "down" | "top" | "bottom" | "<section-id>"}
Move = dict[str, Any]


@dataclass
class TourStop:
    narration: str
    move: Optional[Move] = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"narration": self.narration}
        if self.move:
            d["move"] = self.move
        if self.label:
            d["label"] = self.label
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TourStop":
        move = d.get("move") if isinstance(d.get("move"), dict) else None
        return TourStop(
            narration=str(d.get("narration", "")).strip(),
            move=move,
            label=str(d.get("label", "")),
        )


@dataclass
class TourPlan:
    site_key: str
    stops: list[TourStop] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"site_key": self.site_key, "stops": [s.to_dict() for s in self.stops]}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TourPlan":
        return TourPlan(
            site_key=str(d.get("site_key", "")),
            stops=[TourStop.from_dict(s) for s in d.get("stops", []) if isinstance(s, dict)],
        )

    def is_usable(self) -> bool:
        return len([s for s in self.stops if s.narration]) >= 2


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

_PLANNER_TEMPLATE = """You are the tour director for {agent}, a voice guide embedded \
on the {company} website. From the catalogue of pages you are given, design a SHORT \
guided tour (about 6-9 stops) that a first-time visitor hears and sees.

The tour must:
- Open with a one-sentence warm welcome that says what the site/company does.
- Walk through 2-4 key pages. For each, give a stop that NARRATES what that part \
of the page is about (grounded ONLY in the provided content — never invent \
features, prices, or names), then MOVES on.
- Use `scroll` (target "down") to progress DOWN a long page as you explain it, \
and `navigate` (with a real route from the catalogue) to move between pages.
- END with a concrete USE-CASE stop: pick a realistic task this visitor's \
business does manually, and explain how the {company} platform would automate \
it — roughly how long it takes to set up, how much TIME and MONEY it saves per \
month and per year, and what NEW capabilities it unlocks. Keep numbers plausible \
and clearly framed as an illustrative estimate.

Each narration is SPOKEN, so keep it to 1-3 natural sentences. Output ONLY a JSON \
object of this exact shape (no markdown, no prose):
{"stops":[{"narration":"...","move":{"type":"navigate","route":"/..."}},\
{"narration":"...","move":{"type":"scroll","target":"down"}},\
{"narration":"...","label":"use-case"}]}
The final stop has no move. A stop's `move` runs AFTER its narration is spoken."""


def _planner_system(site_key: str) -> str:
    profile = profile_for(site_key)
    out = (
        _PLANNER_TEMPLATE.replace("{agent}", profile.agent_name)
        .replace("{company}", profile.company_name)
    )
    if profile.tour_outline:   # from a vertical template (M2-9)
        out += ("\nWhere the site has pages for them, cover these, in this order: "
                + "; ".join(profile.tour_outline) + ".")
    return out


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _page_catalog(documents: Sequence[Any]) -> list[dict[str, str]]:
    """Compact {route, title, summary} catalogue for the planner prompt."""
    cat: list[dict[str, str]] = []
    seen: set[str] = set()
    for doc in documents:
        route = getattr(doc, "route", None) or "/"
        if route in seen:
            continue
        seen.add(route)
        content = (getattr(doc, "content", "") or "").strip()
        # First heading-ish line as a title, then a short plain-text summary
        # (markdown markers stripped so spoken narration stays clean).
        first_line = content.splitlines()[0].strip("# ").strip() if content else route
        plain = re.sub(r"[#*`>_\[\]]+", " ", content)
        summary = re.sub(r"\s+", " ", plain).strip()[:360]
        cat.append({"route": route, "title": first_line[:80], "summary": summary})
        if len(cat) >= 14:
            break
    return cat


def _fallback_plan(site_key: str, catalog: list[dict[str, str]]) -> TourPlan:
    """Deterministic plan (mock mode / planner failure) so a tour always exists.

    Walks the homepage + a couple of key pages with a scroll-through, then a
    generic illustrative use-case so the runtime + sync can always be exercised.
    """
    profile = profile_for(site_key)
    stops: list[TourStop] = [
        TourStop(
            narration=f"Welcome! I'm {profile.agent_name} — let me give you a quick "
            "guided tour of what we do here. Sit back, I'll walk you through it.",
            move={"type": "scroll", "target": "top"},
            label="intro",
        )
    ]
    # Prefer the homepage first, then up to three other pages.
    home = next((c for c in catalog if c["route"] in ("/", "/home")), None)
    ordered = ([home] if home else []) + [c for c in catalog if c is not home][:3]
    for c in ordered:
        if not c:
            continue
        title = c["title"] or c["route"]
        stops.append(TourStop(
            narration=f"Here's {title}. {c['summary'][:160]}".strip(),
            move={"type": "scroll", "target": "down"},
            label=c["route"],
        ))
        stops.append(TourStop(
            narration="As we scroll, you can see how this comes together for your team.",
            move={"type": "navigate", "route": ordered[(ordered.index(c) + 1) % len(ordered)]["route"]}
            if len(ordered) > 1 else None,
            label=f"{c['route']}#more",
        ))
    stops.append(TourStop(narration=profile.closing_narration(), label="use-case"))
    return TourPlan(site_key=site_key, stops=stops)


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    m = _JSON_RE.search(text)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


async def plan_tour(
    *,
    site_key: str,
    documents: Sequence[Any],
    llm: LLMClient,
    settings: Settings,
) -> TourPlan:
    """Author a TourPlan from a site's ingested pages. Falls back to a
    deterministic plan in mock mode or if the planner output is unusable."""
    catalog = _page_catalog(documents)
    if not catalog:
        return _fallback_plan(site_key, catalog)

    if settings.mock_ai:
        return _fallback_plan(site_key, catalog)

    prompt = (
        "Site: " + site_key + "\nPage catalogue (route — title — summary):\n"
        + "\n".join(f"- {c['route']} — {c['title']} — {c['summary']}" for c in catalog)
    )
    try:
        resp = await llm.generate(
            system=_planner_system(site_key),
            messages=[ChatMessage(role="user", text=prompt)],
            model=settings.heavy_model,
            temperature=0.6,
            max_output_tokens=1400,
            thinking_budget=0,
        )
        data = _extract_json(resp.text)
        plan = TourPlan.from_dict({"site_key": site_key, **data}) if data else TourPlan(site_key)
    except Exception as exc:  # planner must never block ingestion
        logger.warning("tour planner failed for %s (%s); using fallback", site_key, exc)
        plan = TourPlan(site_key)

    if not plan.is_usable():
        logger.info("tour planner returned an unusable plan for %s; using fallback", site_key)
        plan = _fallback_plan(site_key, catalog)
    logger.info("tour planned for %s: %d stops", site_key, len(plan.stops))
    return plan


def plan_as_json(plan: TourPlan) -> str:
    return json.dumps(plan.to_dict())
