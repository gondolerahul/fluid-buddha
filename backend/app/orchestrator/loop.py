"""
The cognitive loop: Observe -> Plan -> Act -> Speak.

Sequences the Fast Router (instant ack + persona inference) and the Heavy
Thinker (grounded reasoning + UI generation) for a single user utterance, and
maintains the silent persona-switch invariant (Req 3.6).
"""
from __future__ import annotations

import logging

from app.ai.factory import AIEngines
from app.config import Settings
from app.cortex.bridge import CortexBridge
from app.orchestrator.lean import LeanResponder, needs_heavy
from app.orchestrator.personas import valid_personas
from app.orchestrator.result import ClientAction, TurnResult
from app.orchestrator.router import FastRouter
from app.experience.taste import clean as _clean_taste
from app.orchestrator.state import ConversationState
from app.orchestrator.thinker import HeavyThinker

logger = logging.getLogger(__name__)

# Adaptive-persona tuning (Feature 1).
_PROBE_EVERY = 3                 # min turns between qualifying questions
_PROBE_CONFIDENCE = 0.5          # probe while our read is weaker than this
_SWITCH_CONFIDENCE = 0.6         # switch only on a read at least this strong
_LOCK_OVERRIDE_CONFIDENCE = 0.9  # override a self-identified persona only this strong
# Confidence assigned to a Heavy-Thinker `set_persona` tool call (a deliberate
# model decision, treated as a confident switch).
THINKER_SWITCH_CONFIDENCE = 0.8


def should_probe(state: ConversationState) -> bool:
    """Time to weave in a qualifying question? Only when the persona is unknown
    or weakly held, the visitor hasn't self-identified, and we haven't probed
    recently (so it never feels like an interrogation)."""
    if state.persona_locked:
        return False
    return (
        (state.persona is None or state.persona_confidence < _PROBE_CONFIDENCE)
        and state.turns_since_probe >= _PROBE_EVERY
    )


def bump_probe(state: ConversationState, probed: bool) -> None:
    state.turns_since_probe = 0 if probed else state.turns_since_probe + 1



def taste_brief(state) -> str:
    """The visitor's taste in a sentence for the prompt (Phase 3), or ''."""
    raw = getattr(state, "taste", None)
    return _clean_taste(raw).brief() if raw else ""


class CognitiveLoop:
    def __init__(self, engines: AIEngines, settings: Settings) -> None:
        self._settings = settings
        self.router = FastRouter(engines.llm, settings)
        self.thinker = HeavyThinker(engines.llm, settings)
        self.lean = LeanResponder(engines.llm, settings)

    async def route(self, user_text: str, state: ConversationState):
        """Fast path only — returns the ack/persona for immediate TTS."""
        return await self.router.route(user_text, state.history, state.site_key,
                                       lang=state.lang, seen=state.lang_seen)

    @staticmethod
    def needs_heavy(transcript: str, intent: str = "general",
                    state: ConversationState | None = None) -> bool:
        """Hybrid router: does this turn need the Heavy Thinker (tools/diagram/
        navigation/page/patch) or can the lean single-shot path handle it?"""
        return needs_heavy(transcript, intent,
                           has_components=bool(state and state.components))

    @staticmethod
    def apply_persona(
        state: ConversationState, persona: str | None, confidence: float,
        *, explicit: bool = False,
    ) -> bool:
        """Decide whether to (silently) switch the site persona. Returns True if a
        switch should be surfaced to the client. Guards against flip-flop: a weak
        signal never switches, and a self-identified persona is only overridden by
        an equally explicit/strong later signal."""
        if persona not in valid_personas(state.site_key):
            return False
        if explicit:
            state.persona_locked = True
        if persona == state.persona:
            state.persona_confidence = max(state.persona_confidence, confidence)
            return False
        if state.persona_locked and not explicit and confidence < _LOCK_OVERRIDE_CONFIDENCE:
            return False
        if confidence < _SWITCH_CONFIDENCE:
            return False
        state.persona = persona
        state.persona_confidence = confidence
        return True

    async def think_lean(
        self, user_text: str, state: ConversationState, bridge: CortexBridge, persona,
        related=None, probe: bool = False, search: str = "",
    ):
        """Fast conversational path — one retrieval + one generation, no tools."""
        return await self.lean.respond(
            user_text=user_text,
            persona=persona,
            bridge=bridge,
            history=state.history,
            site_key=state.site_key,
            page=state.page,
            section=state.viewport,
            related=related,
            probe=probe,
            lang=state.lang,
            seen=state.lang_seen,
            taste_brief=taste_brief(state),
            search=search,
        )

    async def think(
        self, user_text: str, state: ConversationState, bridge: CortexBridge, persona,
        related=None, probe: bool = False,
    ):
        return await self.thinker.think(
            user_text=user_text,
            persona=persona,
            bridge=bridge,
            history=state.history,
            site_key=state.site_key,
            intelligence=state.intelligence,
            page=state.page,
            section=state.viewport,
            sections=state.sections,
            related=related,
            probe=probe,
            on_screen=state.components,
            pii=state.pii,
            lang=state.lang,
            seen=state.lang_seen,
            taste_brief=taste_brief(state),
            on_screen_plan=state.page_plan,
        )

    async def react(self, entry: dict, persona, site_key: str, lang: str = "en") -> str:
        """Short live reaction to a visitor's component interaction."""
        return await self.thinker.react(
            component_type=entry.get("component_type", ""),
            state=entry.get("state", {}),
            persona=persona, site_key=site_key, lang=lang,
        )

    async def welcome(self, state: ConversationState, bridge: CortexBridge):
        """Agent-initiated, page-aware greeting (voice-first onboarding)."""
        return await self.thinker.welcome(
            persona=state.persona,
            bridge=bridge,
            site_key=state.site_key,
            intelligence=state.intelligence,
            page=state.page,
            section=state.viewport,
            sections=state.sections,
            lang=state.lang,
        )

    async def run_turn(
        self, *, user_text: str, state: ConversationState, bridge: CortexBridge,
        related=None,
    ) -> TurnResult:
        """Full synchronous turn (used by the HTTP /chat path)."""
        route = await self.router.route(user_text, state.history, state.site_key,
                                        lang=state.lang, seen=state.lang_seen)
        result = TurnResult(intent=route.intent, ack=route.ack)

        # Adaptive persona switch — only on a confident, changed read (Req 3.6.2).
        probe = should_probe(state)
        if route.persona and self.apply_persona(
            state, route.persona, route.persona_confidence,
            explicit=route.persona_explicit,
        ):
            result.actions.append(ClientAction(type="set_icp", icp=route.persona))
        bump_probe(state, probe)
        persona = state.persona

        if self.needs_heavy(user_text, route.intent, state):
            think = await self.thinker.think(
                user_text=user_text,
                persona=persona,
                bridge=bridge,
                history=state.history,
                site_key=state.site_key,
                intelligence=state.intelligence,
                page=state.page,
                section=state.viewport,
                sections=state.sections,
                related=related,
                probe=probe,
                on_screen=state.components,
                pii=state.pii,
                lang=state.lang,
                seen=state.lang_seen,
                taste_brief=taste_brief(state),
                on_screen_plan=state.page_plan,
            )
        else:
            think = await self.lean.respond(
                user_text=user_text,
                persona=persona,
                bridge=bridge,
                history=state.history,
                site_key=state.site_key,
                page=state.page,
                section=state.viewport,
                related=related,
                probe=probe,
                lang=state.lang,
                seen=state.lang_seen,
                taste_brief=taste_brief(state),
                search=route.query_en,
            )
        result.answer_text = think.answer_text
        result.components.extend(think.components)
        for c in think.components:  # so a later correction can patch it (D-11)
            state.register_component(c.sync_id, c.component_type, c.initial_state)
        result.pages.extend(think.pages)
        result.patches.extend(think.patches)
        result.leads.extend(think.leads)
        result.proposals.extend(think.proposals)
        for p in think.patches:
            state.update_component_state(p.target_sync_id, p.patch)
        result.grounding = think.grounding
        result.llm_kind = think.llm_kind
        result.input_tokens = think.input_tokens
        result.output_tokens = think.output_tokens
        result.tool_calls = think.tool_calls

        for action in think.actions:
            if action.type == "set_icp":
                if action.icp and self.apply_persona(
                    state, action.icp, THINKER_SWITCH_CONFIDENCE
                ):
                    result.actions.append(action)
            else:
                result.actions.append(action)

        result.persona = state.persona
        state.add_turn(user_text, think.answer_text)
        return result
