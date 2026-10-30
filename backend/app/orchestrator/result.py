"""Shared result types produced by the cognitive loop and consumed by both the
HTTP /chat route and the WebSocket transport."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ClientAction:
    """A DOM/navigation command for the frontend (EVENTS channel)."""
    type: str                      # navigate | set_icp | scroll_to
    path: Optional[str] = None
    icp: Optional[str] = None
    section_id: Optional[str] = None
    direction: Optional[str] = None  # for scroll_to: up | down | top | bottom

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.path is not None:
            d["path"] = self.path
        if self.icp is not None:
            d["icp"] = self.icp
        if self.section_id is not None:
            d["sectionId"] = self.section_id
        if self.direction is not None:
            d["direction"] = self.direction
        return d


@dataclass
class ComponentPayload:
    """A dynamic UI component for the frontend registry (DATA channel)."""
    sync_id: str
    component_type: str            # flowchart | roi_calculator | table
    initial_state: dict[str, Any]
    explanation_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sync_id": self.sync_id,
            "component_type": self.component_type,
            "initial_state": self.initial_state,
            "explanation_text": self.explanation_text,
        }


@dataclass
class PageSpec:
    """A full runtime-generated page (Extreme tier) for the DATA channel."""
    sync_id: str
    title: str
    sections: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"sync_id": self.sync_id, "title": self.title, "sections": self.sections}


@dataclass
class Grounding:
    confidence: float = 0.0
    found: bool = False
    sources: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"confidence": self.confidence, "found": self.found, "sources": self.sources}


@dataclass
class TurnResult:
    intent: str = "general"
    persona: Optional[str] = None
    ack: str = ""
    answer_text: str = ""
    actions: list[ClientAction] = field(default_factory=list)
    components: list[ComponentPayload] = field(default_factory=list)
    pages: list[PageSpec] = field(default_factory=list)
    grounding: Grounding = field(default_factory=Grounding)
    # Cost analytics (req F): LLM tier + tokens/tool-calls this turn spent.
    llm_kind: str = "thinker"
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0

    def to_message_dict(self) -> dict[str, Any]:
        """Shape consumed by the frontend Pragya `Message` (text path)."""
        return {
            "text": self.answer_text or self.ack,
            "ack": self.ack,
            "intent": self.intent,
            "persona": self.persona,
            "actions": [a.to_dict() for a in self.actions],
            "components": [c.to_dict() for c in self.components],
            "pages": [p.to_dict() for p in self.pages],
            "grounding": self.grounding.to_dict(),
        }
