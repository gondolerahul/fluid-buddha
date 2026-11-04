"""Per-conversation sliding-window state (Backend Context Buffer, arch §3.3)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.ai.base import ChatMessage
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
