"""
Taste profile (Phase 3, strategy §5).

A visitor's preferences for how pages and the agent present things. Only the
dimensions below exist — no sensitive inference (health, religion, finances…)
and nothing that changes prices.

Each dimension holds ``{value, confidence, source, at}``:

* **explicit** (the visitor chose it, or said so: "keep it short") → confidence
  1.0, never overridden by inference;
* **implicit** (what they did) → confidence moves 0.15 per event toward the
  observed value, and decays with a 14-day half-life.

Anonymous visitors keep their profile in the browser for the session; the
server only stores it for visitors who chose "Remember me" (``taste_profiles``
cascades from ``visitor_memories``).
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DIMENSIONS: dict[str, tuple[str, ...]] = {
    "density": ("airy", "balanced", "compact"),
    "format": ("prose", "bullets", "tables", "charts", "visuals"),
    "detail": ("summary", "standard", "deep"),
    "modality": ("voice", "text", "silent"),
    "tone": ("formal", "friendly", "concise"),
    "motion": ("calm", "standard", "lively"),
    "scheme": ("light", "dark", "auto"),
}
STEP = 0.15
HALF_LIFE_S = 14 * 24 * 3600
CONFIDENT = 0.5
MAX_INTERESTS = 20
_TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9 -]{0,39}$")
FORMAT_GROUP = {"prose": "text", "bullets": "text", "tables": "tables", "charts": "visual", "visuals": "visual"}


@dataclass
class Taste:
    dims: dict[str, dict[str, Any]] = field(default_factory=dict)
    interests: dict[str, float] = field(default_factory=dict)

    # ---- reading --------------------------------------------------------------
    def value(self, dim: str, *, min_conf: float = CONFIDENT, now: Optional[float] = None) -> Optional[str]:
        d = self.dims.get(dim)
        if not d:
            return None
        return d["value"] if confidence(d, now) >= min_conf else None

    def bucket(self) -> str:
        """The coarse key plans are cached by: confident density × format group."""
        dens = self.value("density")
        fmt = self.value("format")
        parts = []
        if dens and dens != "balanced":
            parts.append(f"d:{dens}")
        if fmt and FORMAT_GROUP.get(fmt, "text") != "text":
            parts.append(f"f:{FORMAT_GROUP[fmt]}")
        return "|".join(parts)

    def brief(self) -> str:
        """A short description for the planners' prompts ('' when nothing is known)."""
        bits = []
        words = {
            ("density", "compact"): "compact layouts", ("density", "airy"): "airy layouts",
            ("format", "tables"): "tables over prose", ("format", "charts"): "charts", ("format", "visuals"): "visuals",
            ("format", "bullets"): "bullet points", ("detail", "summary"): "short summaries",
            ("detail", "deep"): "in-depth detail", ("tone", "concise"): "a concise tone",
            ("tone", "formal"): "a formal tone", ("tone", "friendly"): "a friendly tone",
        }
        for dim in ("density", "format", "detail", "tone"):
            v = self.value(dim)
            if v and (dim, v) in words:
                bits.append(words[(dim, v)])
        top = [k for k, _ in sorted(self.interests.items(), key=lambda kv: -kv[1])[:3]]
        out = ("Prefers " + ", ".join(bits) + ".") if bits else ""
        if top:
            out += (" " if out else "") + "Interested in: " + ", ".join(top) + "."
        return out

    # ---- writing --------------------------------------------------------------
    def apply(self, dim: str, value: str, *, explicit: bool = False, now: Optional[float] = None) -> bool:
        if value not in DIMENSIONS.get(dim, ()):
            return False
        now = now or time.time()
        cur = self.dims.get(dim)
        if explicit:
            self.dims[dim] = {"value": value, "confidence": 1.0, "source": "explicit", "at": now}
            return True
        if cur and cur.get("source") == "explicit":
            return False  # inference never overrides the visitor's own choice
        conf = confidence(cur, now) if cur else 0.0
        if cur and cur["value"] == value:
            conf = min(0.95, conf + STEP)
        elif conf > STEP:
            conf -= STEP  # evidence against the current value weakens it first
            self.dims[dim] = {**cur, "confidence": conf, "at": now}  # type: ignore[dict-item]
            return True
        else:
            conf = STEP
        self.dims[dim] = {"value": value, "confidence": round(conf, 3), "source": "implicit", "at": now}
        return True

    def interest(self, topic: str, weight: float = 1.0) -> None:
        t = str(topic or "").strip().lower()[:40]
        if not _TOPIC_RE.match(t):
            return
        self.interests[t] = round(self.interests.get(t, 0.0) * 0.9 + weight, 3)
        if len(self.interests) > MAX_INTERESTS:
            for k, _ in sorted(self.interests.items(), key=lambda kv: kv[1])[: len(self.interests) - MAX_INTERESTS]:
                self.interests.pop(k, None)

    def merge(self, other: "Taste") -> "Taste":
        """Combine a stored profile with the session's: explicit beats implicit,
        then the newer entry wins."""
        out = Taste(dict(self.dims), dict(self.interests))
        for dim, d in other.dims.items():
            cur = out.dims.get(dim)
            if cur is None or (d.get("source") == "explicit" and cur.get("source") != "explicit") \
                    or (d.get("source") == cur.get("source") and d.get("at", 0) > cur.get("at", 0)):
                out.dims[dim] = d
        for k, v in other.interests.items():
            out.interests[k] = max(out.interests.get(k, 0.0), v)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"dims": self.dims, "interests": self.interests, "bucket": self.bucket()}

    def public(self, now: Optional[float] = None) -> dict[str, Any]:
        """What the visitor's panel shows: value, how sure, and whether they chose it."""
        return {"dims": {k: {"value": d["value"], "confidence": round(confidence(d, now), 2),
                             "source": d.get("source", "implicit")} for k, d in self.dims.items()},
                "interests": dict(sorted(self.interests.items(), key=lambda kv: -kv[1])[:10]),
                "bucket": self.bucket(), "options": {k: list(v) for k, v in DIMENSIONS.items()}}


def confidence(d: Optional[dict[str, Any]], now: Optional[float] = None) -> float:
    if not d:
        return 0.0
    conf = float(d.get("confidence") or 0.0)
    if d.get("source") == "explicit":
        return conf
    age = max(0.0, (now or time.time()) - float(d.get("at") or 0))
    return conf * math.pow(0.5, age / HALF_LIFE_S)


def clean(raw: Any) -> Taste:
    """A profile from the browser or the database, with anything unknown dropped."""
    raw = raw if isinstance(raw, dict) else {}
    t = Taste()
    dims = raw.get("dims") if isinstance(raw.get("dims"), dict) else {}
    now = time.time()
    for dim, d in dims.items():
        if dim not in DIMENSIONS or not isinstance(d, dict) or d.get("value") not in DIMENSIONS[dim]:
            continue
        try:
            conf = max(0.0, min(1.0, float(d.get("confidence") or 0)))
            at = min(float(d.get("at") or now), now)
        except (TypeError, ValueError):
            continue
        src = "explicit" if d.get("source") == "explicit" else "implicit"
        t.dims[dim] = {"value": d["value"], "confidence": conf if src == "implicit" else 1.0, "source": src, "at": at}
    inter = raw.get("interests") if isinstance(raw.get("interests"), dict) else {}
    for k, v in list(inter.items())[:MAX_INTERESTS]:
        k2 = str(k).strip().lower()[:40]
        if _TOPIC_RE.match(k2) and isinstance(v, (int, float)) and not isinstance(v, bool):
            t.interests[k2] = max(0.0, min(100.0, float(v)))
    return t


# ---- events ---------------------------------------------------------------------

# Things a visitor says that are explicit preferences.
_SAID: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\b(simpler|keep it short|in short|briefly|tl;?dr|just the summary|short version)\b", re.I), "detail", "summary"),
    (re.compile(r"\b(more detail|in (more )?depth|go deeper|explain (it )?fully|the details)\b", re.I), "detail", "deep"),
    (re.compile(r"\b(as a table|in a table|show (me )?a table|compare .* side by side|side[- ]by[- ]side)\b", re.I), "format", "tables"),
    (re.compile(r"\b(as a chart|show (me )?a (chart|graph)|visuali[sz]e)\b", re.I), "format", "charts"),
    (re.compile(r"\b(bullet points?|as a list)\b", re.I), "format", "bullets"),
    (re.compile(r"\b(less clutter|too busy|too much on (the )?(page|screen))\b", re.I), "density", "airy"),
]


def from_text(t: Taste, said: str) -> list[tuple[str, str]]:
    """Explicit preferences in what the visitor said; applied to ``t``."""
    hits = []
    for rx, dim, value in _SAID:
        if rx.search(said or ""):
            t.apply(dim, value, explicit=True)
            hits.append((dim, value))
    return hits


# Implicit events the widget reports, and what they suggest.
_EVENTS: dict[str, tuple[str, str]] = {
    "mic": ("modality", "voice"), "typed": ("modality", "text"),
    "reduced_motion": ("motion", "calm"), "dark_scheme": ("scheme", "dark"), "light_scheme": ("scheme", "light"),
    "opened_table": ("format", "tables"), "opened_chart": ("format", "charts"), "opened_faq": ("detail", "summary"),
    "expanded_detail": ("detail", "deep"), "skimmed": ("density", "compact"),
}
MAX_EVENTS = 30


def apply_events(t: Taste, events: Any) -> int:
    """``[{type, dim?, value?}]`` → updates. ``set`` events are explicit choices
    from the preferences panel; ``reset`` clears one dimension (or all)."""
    n = 0
    if not isinstance(events, list):
        return 0
    for ev in events[:MAX_EVENTS]:
        if not isinstance(ev, dict):
            continue
        kind = str(ev.get("type") or "")
        if kind == "set":
            n += int(t.apply(str(ev.get("dim")), str(ev.get("value")), explicit=True))
        elif kind == "reset":
            dim = ev.get("dim")
            if dim in DIMENSIONS:
                t.dims.pop(dim, None)
            elif dim is None:
                t.dims.clear()
                t.interests.clear()
            n += 1
        elif kind == "interest":
            t.interest(str(ev.get("topic") or ""))
            n += 1
        elif kind in _EVENTS:
            dim, value = _EVENTS[kind]
            n += int(t.apply(dim, value))
    return n


# ---- storage (remembered visitors only) --------------------------------------------

async def load(db: AsyncSession, site_key: str, visitor: Optional[str]) -> Optional[Taste]:
    if not visitor:
        return None
    r = (await db.execute(text("SELECT dims, interests FROM taste_profiles WHERE site_key = :s AND visitor_id = :v"),
                          {"s": site_key, "v": visitor})).first()
    return clean({"dims": r.dims, "interests": r.interests}) if r else None


async def save(db: AsyncSession, site_key: str, visitor: str, t: Taste) -> bool:
    """Stored only when the visitor has a memory (opted in) on a site that offers it."""
    from app.memory import store as memory

    if await memory.get(db, site_key, visitor) is None:
        return False
    await db.execute(text("""
        INSERT INTO taste_profiles (site_key, visitor_id, dims, interests)
        VALUES (:s, :v, CAST(:d AS jsonb), CAST(:i AS jsonb))
        ON CONFLICT (site_key, visitor_id) DO UPDATE SET dims = EXCLUDED.dims,
            interests = EXCLUDED.interests, updated_at = now()
    """), {"s": site_key, "v": visitor, "d": json.dumps(t.dims), "i": json.dumps(t.interests)})
    await db.commit()
    return True


async def resolve(db: AsyncSession, site_key: str, visitor: Optional[str], session_raw: Any) -> Taste:
    """The taste to plan with: the stored profile (if remembered) merged with the session's."""
    session = clean(session_raw)
    stored = await load(db, site_key, visitor) if visitor else None
    return stored.merge(session) if stored else session


# ---- compact form (the `fbtaste` cookie the Next.js adapter forwards) -------------

def compact(t: Taste) -> str:
    """``density:compact,format:tables`` — confident values only, no interests."""
    return ",".join(f"{d}:{v}" for d in DIMENSIONS if (v := t.value(d)))


def from_compact(s: Optional[str]) -> Taste:
    t = Taste()
    for part in str(s or "").split(",")[: len(DIMENSIONS)]:
        dim, _, value = part.strip().partition(":")
        if value in DIMENSIONS.get(dim, ()):
            t.dims[dim] = {"value": value, "confidence": 0.6, "source": "implicit", "at": time.time()}
    return t
