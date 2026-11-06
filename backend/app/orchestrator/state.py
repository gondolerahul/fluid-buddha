"""Per-conversation sliding-window state (Backend Context Buffer, arch §3.3)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.ai.base import ChatMessage
from app.i18n.detect import choose
from app.trust.pii import PiiVault


INTELLIGENCE_LEVELS = ("basic", "high", "advance", "extreme")
DEFAULT_INTELLIGENCE = "advance"


def normalize_intelligence(raw: Any) -> str:
    """Coerce a reported intelligence level to a known value (default advance)."""
    val = str(raw or "").strip().lower()
    return val if val in INTELLIGENCE_LEVELS else DEFAULT_INTELLIGENCE


def normalize_sections(raw: Any) -> list[dict]:
    """Coerce a reported sections payload into [{"id", "label"}].

    Accepts either ["hero", "plans"] or [{"id": "plans", "label": "Choose Your
    Plan"}] so the frontend can evolve without breaking the backend.
    """
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, dict) and item.get("id"):
            out.append({"id": str(item["id"]), "label": str(item.get("label") or "")})
        elif isinstance(item, str) and item:
            out.append({"id": item, "label": ""})
        if len(out) >= 40:
            break
    return out


@dataclass
class ConversationState:
    site_key: str = "hirebuddha"
    persona: Optional[str] = None
    intelligence: str = DEFAULT_INTELLIGENCE  # basic|high|advance|extreme — gates tools
    page: Optional[str] = None          # current route, reported by frontend STATE
    viewport: Optional[str] = None      # current section in view
    sections: list[dict] = field(default_factory=list)  # [{"id","label"}] scroll targets
    history: list[ChatMessage] = field(default_factory=list)
    max_turns: int = 12                 # keep the last N text turns
    # ---- adaptive persona (Feature 1) ----
    persona_confidence: float = 0.0     # 0..1 strength of the current persona read
    turns_since_probe: int = 0          # turns since we last asked a qualifying question
    persona_locked: bool = False        # set once the visitor explicitly self-identifies
    # ---- rendered-component registry (live reactions) ----
    # sync_id -> {"component_type", "state"} for components currently on screen, so
    # the agent can react when the visitor plays with one. Capped (last N).
    components: dict[str, dict] = field(default_factory=dict)
    max_components: int = 8
    # Placeholders for the visitor's PII in this conversation (WS8): the model
    # and the history only ever see the masked text.
    pii: PiiVault = field(default_factory=PiiVault)
    # Live takeover (M2-2): the last person-to-visitor message already folded
    # into ``history``, so the agent knows what was said when it takes over again.
    live_seen: int = 0
    # ---- language (M2-7) ----
    lang: str = "en"                    # this turn's reply language: en | hi
    lang_seen: str = "en"               # what the visitor wrote: en | hi | hinglish
    lang_pref: Optional[str] = None     # asked for ("reply in Hindi"), kept
    ui_lang: Optional[str] = None       # the widget's language (hello / chat)
    used_hindi: bool = False            # wrote in Devanagari at some point
    # ---- returning-visitor memory (M3-3) ----
    # The widget's anonymous visitor id. Their conversation is linked to it
    # only while they have opted in (the record checks), so a visitor who says
    # "Remember me" mid-conversation has this conversation remembered too.
    visitor_id: Optional[str] = None
    memory_loaded: bool = False         # their memory is in ``history`` already

    def pick_language(self, text: str, enabled) -> str:
        """Decide this turn's reply language from what the visitor wrote."""
        choice, self.lang_pref = choose(text, enabled=enabled, pref=self.lang_pref,
                                        ui=self.ui_lang, used_hindi=self.used_hindi)
        self.lang, self.lang_seen = choice.reply, choice.seen
        self.used_hindi = self.used_hindi or choice.seen == "hi"
        return self.lang

    def start_language(self, ui: Optional[str], enabled) -> None:
        """Before anything is said: a Hindi widget on a Hindi site starts in Hindi."""
        self.ui_lang = ui if ui in ("en", "hi") else None
        self.lang = "hi" if self.ui_lang == "hi" and "hi" in enabled else "en"

    def to_dict(self) -> dict:
        """JSON-able form for a shared session store (F-3)."""
        return {
            "site_key": self.site_key, "persona": self.persona,
            "intelligence": self.intelligence, "page": self.page,
            "viewport": self.viewport, "sections": self.sections,
            "history": [{"role": m.role, "text": m.text} for m in self.history
                        if m.role in ("user", "model")],
            "persona_confidence": self.persona_confidence,
            "turns_since_probe": self.turns_since_probe,
            "persona_locked": self.persona_locked,
            "components": self.components,
            "pii": self.pii.to_dict(),
            "live_seen": self.live_seen,
            "lang": self.lang, "lang_seen": self.lang_seen, "lang_pref": self.lang_pref,
            "ui_lang": self.ui_lang, "used_hindi": self.used_hindi,
            "visitor_id": self.visitor_id, "memory_loaded": self.memory_loaded,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationState":
        state = cls(site_key=str(data["site_key"]))
        state.persona = data.get("persona")
        state.intelligence = normalize_intelligence(data.get("intelligence"))
        state.page = data.get("page")
        state.viewport = data.get("viewport")
        state.sections = normalize_sections(data.get("sections") or [])
        state.history = [ChatMessage(role=str(m["role"]), text=str(m.get("text") or ""))
                         for m in data.get("history") or []]
        state.persona_confidence = float(data.get("persona_confidence") or 0.0)
        state.turns_since_probe = int(data.get("turns_since_probe") or 0)
        state.persona_locked = bool(data.get("persona_locked"))
        state.components = dict(data.get("components") or {})
        state.pii = PiiVault.from_dict(data.get("pii") or {})
        state.live_seen = int(data.get("live_seen") or 0)
        state.lang = "hi" if data.get("lang") == "hi" else "en"
        state.lang_seen = str(data.get("lang_seen") or "en")
        state.lang_pref = data.get("lang_pref") if data.get("lang_pref") in ("en", "hi") else None
        state.ui_lang = data.get("ui_lang") if data.get("ui_lang") in ("en", "hi") else None
        state.used_hindi = bool(data.get("used_hindi"))
        state.visitor_id = data.get("visitor_id") or None
        state.memory_loaded = bool(data.get("memory_loaded"))
        return state

    def remember(self, visitor: str, mem: Optional[dict]) -> None:
        """A returning visitor who opted in (M3-3): put what the agent remembers
        at the start of the history, once."""
        from app.memory.store import note
        self.visitor_id = visitor
        text = note(mem) if mem else None
        if text and not self.memory_loaded:
            self.history[:0] = [ChatMessage(role="user", text="(I've talked to you before.)"),
                                ChatMessage(role="model", text=text)]
        self.memory_loaded = True

    def add_turn(self, user_text: str, model_text: str) -> None:
        self.history.append(ChatMessage(role="user", text=user_text))
        self.history.append(ChatMessage(role="model", text=model_text))
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-self.max_turns * 2:]

    def register_component(self, sync_id: str, component_type: str, state: dict) -> None:
        """Remember a component the agent just rendered (so it can react when the
        visitor interacts with it). Evicts oldest beyond ``max_components``."""
        if not sync_id:
            return
        self.components[sync_id] = {
            "component_type": component_type, "state": dict(state or {})
        }
        while len(self.components) > self.max_components:
            self.components.pop(next(iter(self.components)))

    def update_component_state(self, sync_id: str, patch: dict) -> Optional[dict]:
        """Merge a reported interaction patch into a registered component; returns
        the updated entry, or None if the component isn't known."""
        entry = self.components.get(sync_id)
        if entry is None:
            return None
        entry["state"] = {**entry.get("state", {}), **(patch or {})}
        return entry
