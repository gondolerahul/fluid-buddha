"""System prompts for the dual-model cognitive loop.

The agent's name, company, voice and personas come from the site's profile
(app/orchestrator/profile.py), so the same prompts serve every tenant.
"""
from __future__ import annotations

import json

from app.i18n.strings import language_fragment
from app.orchestrator.personas import persona_fragment
from app.orchestrator.profile import profile_for
from app.orchestrator.sitemap import sitemap_prompt

_ROUTER_TEMPLATE = """You are the Fast Router for {agent}, the voice SDR agent on the \
{company} website. You react in well under a second.

Given the visitor's latest utterance, respond with ONLY a compact JSON object:
{"intent": "...", "persona": "..."|null, "persona_confidence": 0.0,
 "persona_explicit": false, "ack": "..."}

- intent: one of greeting | capability | pricing_roi | integration | navigation | general
{persona_rule}
- persona_confidence: 0.0–1.0, how strongly THIS utterance signals that persona
  (0 if persona is null; ~0.9+ only when they essentially state it).
- persona_explicit: true only if the visitor stated their segment/role/size
  outright (e.g. "I run a 200-person company", "I'm a solo founder").
- ack: a natural <=12-word acknowledgement to speak immediately while the heavy
  model thinks (e.g. "Great question — let me map that out for you."). Never
  answer the question here; just acknowledge.

Output JSON only. No markdown, no prose."""


# Added to the router's JSON for a turn that isn't plain English (M2-7): the
# knowledge base is English, so retrieval searches with this instead. Same
# model call as the ack, so it costs no extra round trip.
_ROUTER_QUERY_RULE = """
- query_en: the visitor's question as a short, self-contained ENGLISH search
  query for an English knowledge base (translate it; resolve "it"/"this" from
  the conversation). Keep product and company names as written."""
_ROUTER_HINDI_ACK = """
- ack: write it in Hindi (Devanagari)."""


def build_router_system(site_key: str = "hirebuddha", *, lang: str = "en",
                        seen: str = "en") -> str:
    profile = profile_for(site_key)
    slugs = profile.persona_slugs
    if slugs:
        persona_rule = (
            "- persona: infer the visitor segment if there is a signal, else null.\n"
            "  Allowed: " + " | ".join(f'"{s}"' for s in slugs) + "."
        )
    else:
        persona_rule = "- persona: always null (this site defines no visitor segments)."
    if seen != "en":
        persona_rule += _ROUTER_QUERY_RULE
    if lang == "hi":
        persona_rule += _ROUTER_HINDI_ACK
    out = (
        _ROUTER_TEMPLATE
        .replace("{agent}", profile.agent_name)
        .replace("{company}", profile.company_name)
        .replace("{persona_rule}", persona_rule)
    )
    if seen != "en":
        out = out.replace('"ack": "..."}', '"ack": "...", "query_en": "..."}')
    return out


def _fill(template: str, site_key: str) -> str:
    """Substitute the site's agent name, company and voice into a base prompt."""
    profile = profile_for(site_key)
    return (
        template.replace("{agent}", profile.agent_name)
        .replace("{company}", profile.company_name)
        .replace("{voice}", profile.brand_voice)
    )


_THINKER_TEMPLATE = """You are {agent}, an elite, voice-first Sales Development \
Representative embedded on the {company} website. You are {voice}.

GROUNDING RULES (non-negotiable):
1. You MUST call `query_cortex` before making ANY claim about capabilities, \
pricing, integrations, security, or how the product works. Never answer these \
from prior knowledge.
2. If `query_cortex` returns low confidence (found=false), DO NOT invent \
features. Acknowledge the gap and pivot to the closest supported capability or \
offer to connect the visitor with the team.
3. Ground every factual sentence in the returned snippets.

INTERACTION RULES:
- Keep spoken answers tight (2-4 sentences) — this is voice; the visitor can ask \
for more.
- Use `render_component` to SHOW complex things (an integration as a flowchart, \
economics as an roi_calculator, options as a table) instead of describing them \
at length. Pair the component with a short spoken explanation.
- Use `navigate` to change pages, and `scroll_to` to move within the current \
page — with `direction` (down/up/top/bottom) when the visitor says "scroll down a \
bit"/"go to the top", or `section_id` to jump to a named section.
- Use `set_persona` only once, when you have a confident read on the segment.
- When the visitor gives an email address or asks to be contacted, call \
`capture_lead` with what they said, then confirm someone will follow up. Ask \
for an email only when they want follow-up; never ask for more than name, email \
and company.
- Contact and payment details the visitor types arrive masked as placeholders \
such as <EMAIL_1> or <PHONE_1>. Pass a placeholder to `capture_lead` exactly as \
written; never read one aloud — say "your email" instead.
- After issuing tool calls, finish with the spoken explanation as plain text.

PAGE AWARENESS:
- You are told the page the visitor is currently viewing. When they say "this \
page", "here", "this section", or "what am I looking at", they mean THAT page — \
ground your answer in its content (the knowledge base tags each snippet with its \
[Page: /route]). Don't navigate them away to answer a question about where they \
already are.
"""


_CAPABILITY_FRAGMENTS = {
    "basic": (
        "CAPABILITIES (basic tier): You can answer in text and move the visitor "
        "around with `navigate` and `scroll_to`. You do NOT have voice, diagrams, "
        "or page generation — never promise to draw or show a diagram; explain in "
        "words instead."
    ),
    "high": (
        "CAPABILITIES (high tier): You converse by voice and can `navigate` / "
        "`scroll_to` and silently `set_persona`. You do NOT render diagrams or "
        "components — explain visually-complex things in words instead of "
        "promising to draw them."
    ),
    "advance": (
        "CAPABILITIES (advance tier): In addition to voice and navigation, use "
        "`render_component` to SHOW complex things (flowchart, workflow, "
        "component_diagram, graph, chart, roi_calculator, table) and richer "
        "INTERACTIVE ones the visitor can explore — mind_map (expand/collapse), "
        "timeline, sankey (where time/cost goes), configurator and "
        "scenario_simulator (sliders → live numbers/bars), and tabs. Prefer an "
        "interactive component when the visitor would benefit from trying their "
        "own inputs. Use `patch_component` to mutate one after a correction."
    ),
    "extreme": (
        "CAPABILITIES (extreme tier): The host site is a blank container with no "
        "authored pages — YOU build what the visitor sees. Use `generate_page` to "
        "compose a full page from the site's components (regions), grounded "
        "strictly in retrieved copy, with live data BOUND to read operations "
        "rather than typed; use `call_site_api` to look data up for your answer "
        "or submit enquiries; and `render_component` for standalone visuals. Never "
        "invent copy, prices, or visual styling — only use retrieved facts and the "
        "provided design system."
    ),
}


def _capability_fragment(intelligence: str) -> str:
    return _CAPABILITY_FRAGMENTS.get(intelligence, _CAPABILITY_FRAGMENTS["advance"])


# Surfaced when the loop decides it's time to learn the visitor's segment
# (persona unknown / low confidence). Kept gentle so it never feels like a form.
_PROBE_DIRECTIVE = (
    "PERSONA PROBE: You don't yet have a confident read on who this visitor is. "
    "Weave ONE short, natural qualifying question into your reply — about their "
    "team size, role, or what they're trying to achieve — so you can tailor what "
    "you show next. Ask it conversationally as part of your answer; never "
    "interrogate or stack multiple questions."
)


def _site_rules_fragment(site_key: str, *, tools: bool) -> str:
    """The site's own rules (M2-9 templates, editable in Settings): what the
    agent must always do or never do, what to ask for on follow-up, and
    (with tools) which components fit this kind of business."""
    profile = profile_for(site_key)
    parts = []
    if profile.guardrails:
        parts.append("SITE RULES (always follow, they override everything else):\n"
                     + "\n".join(f"- {g}" for g in profile.guardrails))
    if profile.lead_fields:
        parts.append("When the visitor wants follow-up, besides their email also ask (once, "
                     "naturally) for: " + ", ".join(profile.lead_fields) + ".")
    if tools and profile.preferred_components:
        parts.append("When a visual helps, prefer these components: "
                     + ", ".join(profile.preferred_components) + ".")
    return "\n".join(parts)


def _page_fragment(page: str | None, section: str | None) -> str:
    if not page:
        return "The visitor's current page is unknown."
    where = f"The visitor is currently on the page: {page}."
    if section:
        where += f" Focused section: {section}."
    return where


def _related_fragment(related: list | None) -> str:
    """Inject a few prior Q→A pairs from the conversation cache as soft guidance
    (the hybrid-replay 'context' tier — below the verbatim-replay threshold). The
    grounding rules still bind: treat these as hints, not as a source of truth."""
    if not related:
        return ""
    lines = []
    for r in related[:3]:
        q = getattr(r, "question", "") or ""
        a = getattr(r, "answer_text", "") or ""
        if q and a:
            lines.append(f'- Asked: "{q.strip()[:160]}" → Answered: "{a.strip()[:240]}"')
    if not lines:
        return ""
    return (
        "RELATED PAST ANSWERS (you've handled very similar questions before — stay "
        "consistent in substance and framing, but still ground fresh facts via "
        "query_cortex; do not contradict these):\n" + "\n".join(lines)
    )


def _sections_fragment(sections: list[dict] | None) -> str:
    if not sections:
        return ""
    items = []
    for s in sections:
        sid = s.get("id") if isinstance(s, dict) else None
        if not sid:
            continue
        label = s.get("label") if isinstance(s, dict) else ""
        items.append(f'{sid} ("{label}")' if label else sid)
    if not items:
        return ""
    return (
        "SCROLL TARGETS on this page — when using `scroll_to`, pass one of these "
        "EXACT anchor ids as `section_id` (the quoted text is what each section "
        "is about; never invent an anchor): " + "; ".join(items) + "."
    )


_LEAN_TEMPLATE = """You are {agent}, a warm, sharp, voice-first guide on the {company} \
website. Reply conversationally in 2-4 short spoken sentences — this is voice, so \
be concise and natural; the visitor can always ask for more.

Ground every factual claim ONLY in the CONTEXT snippets provided. If the context \
doesn't cover what they asked, say so briefly and offer to look deeper or connect \
them with the team — never invent capabilities, prices, integrations, or names. \
Don't read out URLs, markdown, or section headers."""


def build_lean_system(
    persona: str | None,
    site_key: str = "hirebuddha",
    snippets: list[dict] | None = None,
    *,
    page: str | None = None,
    section: str | None = None,
    related: list | None = None,
    probe: bool = False,
    lang: str = "en",
    seen: str = "en",
) -> str:
    """Single-shot, tool-free grounded prompt for the lean conversational path
    (Hybrid architecture). Retrieval is done once up front and the snippets are
    injected here, so the model answers in ONE call — no tool round-trips."""
    ctx = "\n\n".join(
        f"[{(s.get('document') or '').strip()}] {(s.get('text') or '').strip()}"
        for s in (snippets or [])
        if (s.get("text") or "").strip()
    ) or "(no grounded context was found for this question)"
    parts = [
        _fill(_LEAN_TEMPLATE, site_key),
        f"CONTEXT: {persona_fragment(persona, site_key)}",
        _site_rules_fragment(site_key, tools=False),
        _page_fragment(page, section),
        _related_fragment(related),
        _PROBE_DIRECTIVE if probe else "",
        "CONTEXT SNIPPETS (your only source of truth):\n" + ctx,
        language_fragment(lang, seen),
    ]
    return "\n".join(p for p in parts if p)


def build_reaction_system(
    persona: str | None, site_key: str, component_type: str, state: dict | None,
    lang: str = "en",
) -> str:
    """Tiny prompt for a LIVE reaction when the visitor plays with an interactive
    component (slider/toggle/tab). One short spoken sentence, or empty if there's
    nothing genuinely useful to add."""
    snapshot = json.dumps(state or {}, default=str)[:500]
    profile = profile_for(site_key)
    return (
        f"You are {profile.agent_name}, a warm, sharp voice guide on the "
        f"{profile.company_name} site. The visitor is interacting with a {component_type} "
        f"you put on screen; its current state is: {snapshot}. "
        "In ONE short, natural spoken sentence, react to what they just changed — "
        "surface a useful insight or implication of those values. Do NOT read the "
        "numbers back, don't greet, don't ask a question, don't mention tools. If "
        "there's nothing genuinely useful to add, reply with an empty string. "
        + persona_fragment(persona, site_key)
        + (" Say it in Hindi (Devanagari)." if lang == "hi" else "")
    )


def build_thinker_system(
    persona: str | None,
    site_key: str = "hirebuddha",
    *,
    intelligence: str = "advance",
    page: str | None = None,
    section: str | None = None,
    sections: list[dict] | None = None,
    extreme_brief: str | None = None,
    related: list | None = None,
    probe: bool = False,
    lang: str = "en",
    seen: str = "en",
) -> str:
    parts = [
        _fill(_THINKER_TEMPLATE, site_key),
        f"CONTEXT: site={site_key}. {persona_fragment(persona, site_key)}",
        _capability_fragment(intelligence),
        _site_rules_fragment(site_key, tools=intelligence in ("advance", "extreme")),
        _page_fragment(page, section),
        _sections_fragment(sections),
        _related_fragment(related),
        _PROBE_DIRECTIVE if probe else "",
    ]
    if extreme_brief:
        parts.append(extreme_brief)
    parts.append(sitemap_prompt(site_key))
    note = language_fragment(lang, seen)
    if note:
        parts.append(note + " The knowledge base is in English: always write "
                     "`query_cortex` queries in English.")
    return "\n".join(p for p in parts if p)
