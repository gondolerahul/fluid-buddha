"""
Applying a vertical template to a site (M2-9), without overwriting edits.

For each profile setting the template has:

* set it when the site's value is empty or still exactly what an earlier
  template application set (nobody changed it since);
* otherwise keep the site's value — it was edited by hand — and report it.

Personas are added by slug (an existing persona is never changed), triggers
by name. ``plan`` is the preview; ``apply`` does it and records what the
template set, for the next time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.orchestrator.profile import DEFAULT_BRAND_VOICE, SiteProfile, load_profile, save_profile
from app.templates import TemplatePack
from app.triggers import store as triggers

FIELDS = ("brand_voice", "greeting", "greeting_hi", "starter_questions", "guardrails",
          "preferred_components", "lead_fields", "tour_outline", "safety")
LABELS = {
    "brand_voice": "Voice", "greeting": "Greeting", "greeting_hi": "Greeting in Hindi",
    "starter_questions": "Starter questions", "guardrails": "Rules the agent follows",
    "preferred_components": "Preferred components", "lead_fields": "Details to ask for",
    "tour_outline": "What the tour covers", "safety": "Medical safety",
}


@dataclass
class Plan:
    template: str
    set: dict[str, Any] = field(default_factory=dict)      # field -> new value
    kept: list[str] = field(default_factory=list)          # edited by hand
    same: list[str] = field(default_factory=list)          # already as the template has it
    personas_added: list[dict[str, str]] = field(default_factory=list)
    triggers_added: list[str] = field(default_factory=list)
    suggested_actions: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"template": self.template,
                "set": [{"field": k, "label": LABELS[k], "value": v} for k, v in self.set.items()],
                "kept": [{"field": k, "label": LABELS[k]} for k in self.kept],
                "personas_added": self.personas_added, "triggers_added": self.triggers_added,
                "suggested_actions": self.suggested_actions}


def _empty(name: str, value: Any) -> bool:
    if name == "brand_voice":
        return not value or value == DEFAULT_BRAND_VOICE
    return value in ("", None, [], {})


def plan(profile: SiteProfile, rules: list[dict], pack: TemplatePack) -> Plan:
    applied = (profile.template or {}).get("applied") or {}
    out = Plan(template=pack.id, suggested_actions=[a.model_dump() for a in pack.suggested_actions])
    want = pack.profile.model_dump()
    for name in FIELDS:
        new, cur = want[name], getattr(profile, name)
        if _empty(name, new):
            continue
        if cur == new:
            out.same.append(name)
        elif _empty(name, cur) or (name in applied and applied[name] == cur):
            out.set[name] = new
        else:
            out.kept.append(name)
    have = {p.slug for p in profile.personas}
    out.personas_added = [p.model_dump() for p in pack.profile.personas if p.slug not in have]
    names = {r["name"].lower() for r in rules}
    out.triggers_added = [t.name for t in pack.triggers if t.name.lower() not in names]
    return out


async def preview(db: AsyncSession, site_key: str, pack: TemplatePack) -> Plan:
    return plan(await load_profile(db, site_key), await triggers.rules(db, site_key), pack)


async def apply(db: AsyncSession, site_key: str, pack: TemplatePack) -> Plan:
    """Apply ``pack``; the caller commits."""
    profile = await load_profile(db, site_key)
    p = plan(profile, await triggers.rules(db, site_key), pack)
    data = profile.to_dict()
    data.update(p.set)
    data["personas"] = [*data["personas"], *p.personas_added]
    # Remember what this template stands for, for the next apply.
    data["template"] = {"id": pack.id, "applied_at": datetime.now(timezone.utc).isoformat(),
                        "applied": {k: pack.profile.model_dump()[k] for k in FIELDS
                                    if k in p.set or k in p.same}}
    await save_profile(db, SiteProfile.from_dict(data, profile))
    added = []
    for rule in pack.triggers:
        if rule.name in p.triggers_added:
            try:
                await triggers.create(db, site_key, rule)
                added.append(rule.name)
            except ValueError:      # the site is at its trigger limit
                pass
    p.triggers_added = added
    return p
