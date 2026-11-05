"""
Vertical templates (M2-9): a starting setup for a kind of business.

Each pack (``app/templates/<id>.yaml``) holds profile settings — voice,
greeting, personas, starter questions, the rules the agent always follows,
preferred components, the details to ask for, what the guided tour covers,
an optional safety mode — plus proactive triggers (M2-3) and suggested
actions (M2-8). Packs are checked against ``TemplatePack`` when loaded; a bad
pack fails the import (and the test suite), never a tenant's request.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from app.actions.fields import KINDS
from app.orchestrator.components import KNOWN_COMPONENTS
from app.triggers.store import RuleIn

_DIR = Path(__file__).parent


class PersonaPack(BaseModel):
    slug: str = Field(..., pattern=r"^[a-z][a-z0-9_-]{1,30}$")
    label: str = Field(..., min_length=1, max_length=60)
    focus: str = Field("", max_length=300)
    tone: str = Field("", max_length=200)


class ProfilePack(BaseModel):
    brand_voice: str = Field(..., min_length=1, max_length=300)
    greeting: str = Field(..., min_length=1, max_length=300)
    greeting_hi: str = Field("", max_length=300)
    personas: list[PersonaPack] = Field(..., min_length=1, max_length=8)
    starter_questions: list[str] = Field(default_factory=list, max_length=4)
    starter_questions_hi: list[str] = Field(default_factory=list, max_length=4)
    guardrails: list[str] = Field(default_factory=list, max_length=10)
    preferred_components: list[str] = Field(default_factory=list, max_length=8)
    lead_fields: list[str] = Field(default_factory=list, max_length=6)
    tour_outline: list[str] = Field(default_factory=list, max_length=9)
    safety: Literal["", "medical"] = ""

    @field_validator("preferred_components")
    @classmethod
    def _known(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if c not in KNOWN_COMPONENTS]
        if bad:
            raise ValueError(f"unknown components: {', '.join(bad)}")
        return v

    @field_validator("personas")
    @classmethod
    def _unique(cls, v: list[PersonaPack]) -> list[PersonaPack]:
        if len({p.slug for p in v}) != len(v):
            raise ValueError("persona slugs must be unique")
        return v


class SuggestedAction(BaseModel):
    kind: str
    label: str = Field(..., max_length=80)
    why: str = Field("", max_length=200)

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        return v


class TemplatePack(BaseModel):
    id: str = Field(..., pattern=r"^[a-z][a-z_]{1,30}$")
    name: str = Field(..., max_length=60)
    description: str = Field("", max_length=200)
    profile: ProfilePack
    triggers: list[RuleIn] = Field(default_factory=list, max_length=6)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list, max_length=6)

    def summary(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description,
                "personas": [p.label for p in self.profile.personas],
                "suggested_actions": [a.model_dump() for a in self.suggested_actions]}


def parse(text: str) -> TemplatePack:
    """Check one pack (YAML). Raises pydantic.ValidationError."""
    return TemplatePack.model_validate(yaml.safe_load(text))


@lru_cache
def packs() -> dict[str, TemplatePack]:
    out = {}
    for f in sorted(_DIR.glob("*.yaml")):
        pack = parse(f.read_text(encoding="utf-8"))
        if pack.id != f.stem:
            raise ValueError(f"{f.name}: id {pack.id!r} must match the file name")
        out[pack.id] = pack
    return out


def get(template_id: Optional[str]) -> Optional[TemplatePack]:
    return packs().get(template_id or "")
