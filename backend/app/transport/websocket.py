"""
Multiplexed WebSocket transport — the voice-first cognitive loop (Req 3.2/3.3).

One connection per visitor. The session:
  * receives mic AUDIO chunks (or a client-side transcript) and STATE updates,
  * masks latency by speaking the Fast Router ack first, then streams the
    grounded Heavy Thinker answer,
  * tags correlated DATA (UI) + AUDIO (TTS) with a shared ``sync_id`` so the
    frontend jitter buffer can sync them,
  * handles barge-in by cancelling the in-flight response task.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
import uuid
import zlib
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db import session_scope
from app.orchestrator.loop import bump_probe, should_probe, THINKER_SWITCH_CONFIDENCE
from app.orchestrator.result import ClientAction, Grounding
from app.design.system import ensure_design
from app.orchestrator.profile import ensure_profile
from app.orchestrator.rewrite import depends_on_history
from app.orchestrator.tour_store import load_plan
from app.tenancy.public_access import PublicAccessError, resolve_public_site
from app.transport.guard import check_public_budget
from app.orchestrator.state import (
    ConversationState,
    normalize_intelligence,
    normalize_sections,
)
from app.transport.envelope import Channel, make, pack_audio, unpack_audio
from app.trust.pii import PiiVault, contains_pii, redact
from app.trust.settings import Privacy, get_privacy

logger = logging.getLogger("a2ui.ws")
router = APIRouter()

# A new utterance arriving within this window of the previous one (while the
# response is still in flight) is treated as a CONTINUATION of the same question
# and coalesced — handles ASR/VAD splitting one spoken thought into fragments.
_COALESCE_WINDOW_S = 10.0

# Mic audio kept for one utterance: a minute of PCM16 @ 16 kHz. Anything past
# that is dropped rather than buffered without bound.
_MAX_UTTERANCE_BYTES = 16000 * 2 * 60

# Spoken before a replayed (cached) answer so a cache hit sounds like a fresh
# turn: ack first, then the answer (D-8). Few, fixed phrases so their audio is
# itself served from the audio cache after the first synthesis.
_REPLAY_ACKS = ("Sure.", "Good question.", "Happy to explain.")


def _replay_ack(transcript: str) -> str:
    return _REPLAY_ACKS[zlib.crc32(transcript.encode("utf-8")) % len(_REPLAY_ACKS)]


def _sid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def split_for_tts(text: str, min_chars: int = 24) -> list[str]:
    """Break spoken text into sentence-sized chunks for incremental TTS.

    Each chunk is synthesised + streamed separately so the FIRST chunk can play
    after only its own (short) synthesis instead of waiting for the whole
    utterance — the dominant latency win for long answers. Short sentences are
    merged up to ``min_chars`` so we don't over-fragment the prosody.
    """
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?…])\s+", text)
    out: list[str] = []
    buf = ""
    for s in parts:
        s = s.strip()
        if not s:
            continue
        buf = f"{buf} {s}".strip() if buf else s
        if len(buf) >= min_chars:
            out.append(buf)
            buf = ""
    if buf:
        if out:
            out[-1] = f"{out[-1]} {buf}".strip()  # fold a tiny tail into the last chunk
        else:
            out.append(buf)
    return out or [text]


class VoiceSession:
    def __init__(
        self, ws: WebSocket, runtime, site_key: str = "hirebuddha",
        intelligence: str = "advance", tier_locked: bool = False,
        binary_audio: bool = False,
    ) -> None:
        self.ws = ws
        # The client asked for TTS audio as binary frames (WS5).
        self.binary_audio = binary_audio
        self.rt = runtime
        self.session_id = uuid.uuid4().hex
        # When the tier is server-resolved from a widget key, the client may not
        # change it mid-session via STATE/sync (docs/defects.md D-1).
        self._tier_locked = tier_locked
        self.state = ConversationState(
            site_key=site_key, intelligence=normalize_intelligence(intelligence)
        )
        self._audio: list[bytes] = []
        self._audio_bytes = 0
        self._response_task: asyncio.Task | None = None
        self._persona_emitted: str | None = None
        self._greeted = False
        self._last_utt_text = ""
        self._last_utt_at = 0.0
        # True only while the ANSWER (not the ack) is being spoken — barge-in
        # ignores speech during the ack/thinking phase (user finishing their turn).
        self._answer_speaking = False
        # Conversation cache (Feature 2): cached past answers fed to the thinker as
        # context this turn, and fire-and-forget recording tasks kept referenced.
        self._related: list = []
        self._bg_tasks: set[asyncio.Task] = set()
        # Debounced live reaction to the visitor playing with a component.
        self._react_task: asyncio.Task | None = None
        # The tour plan handed to the client on hello; tour_say speaks only its steps.
        self._tour_plan = None
        # Trust layer (WS8): the site's privacy settings (loaded on connect), and
        # when the visitor allowed the microphone. Audio is ignored until then
        # if the site requires consent.
        self.privacy = Privacy()
        self._consent_at: datetime | None = None
        self._consent_asked = False

    # ---- low-level send -------------------------------------------------
    async def send(self, channel: str, type_: str, payload=None, sync_id=None) -> None:
        await self.ws.send_json(make(channel, type_, payload, sync_id))

    # ---- lifecycle ------------------------------------------------------
    async def run(self) -> None:
        await self.ws.accept()
        try:
            async with session_scope() as db:
                self.privacy = await get_privacy(db, self.state.site_key)
        except Exception as exc:   # defaults keep masking and consent on
            logger.warning("ws[%s]: privacy settings unavailable: %s",
                           self.session_id[:8], exc)
        self.state.pii = PiiVault(enabled=self.privacy.redact_pii)
        await self.send(Channel.EVENTS, "ready", {
            "session_id": self.session_id,
            "privacy": self.privacy.public(),
            "config": {
                "filler_delay_ms": self.rt.settings.ui_filler_delay_ms,
                "sample_rate": self.rt.settings.tts_sample_rate,
                "audio_frames": "binary" if self.binary_audio else "json",
            },
        })
        try:
            while True:
                msg = await self.ws.receive()
                if msg["type"] == "websocket.disconnect":
                    raise WebSocketDisconnect(msg.get("code", 1000))
                if msg.get("bytes") is not None:
                    await self._on_binary(msg["bytes"])
                    continue
                try:
                    env = json.loads(msg.get("text") or "")
                except ValueError:
                    continue  # a malformed frame shouldn't end the session
                if isinstance(env, dict):
                    await self._dispatch(env)
        except WebSocketDisconnect:
            logger.info("ws disconnect session=%s", self.session_id)
        finally:
            await self._cancel_response()

    async def _dispatch(self, env: dict) -> None:
        channel = env.get("channel")
        type_ = (env.get("type") or "").lower()
        payload = env.get("payload") or {}

        if channel == Channel.AUDIO:
            if self.privacy.consent_required and self._consent_at is None:
                await self._ask_consent()
                return
            if type_ == "start":
                self._audio.clear()
                self._audio_bytes = 0
            elif type_ == "chunk":
                data = payload.get("data")
                if data:
                    try:
                        self._add_audio(base64.b64decode(data))
                    except ValueError:
                        pass
            elif type_ == "end":
                transcript = payload.get("transcript") or await self._asr()
                if transcript.strip():
                    await self._on_utterance(transcript.strip())
        elif channel == Channel.EVENTS and type_ == "text":
            text = (payload.get("text") or "").strip()
            if text:
                await self._on_utterance(text)
        elif channel == Channel.EVENTS and type_ == "consent":
            if payload.get("mic") is True and self._consent_at is None:
                self._consent_at = datetime.now(timezone.utc)
                logger.info("ws[%s]: microphone consent given", self.session_id[:8])
        elif channel == Channel.EVENTS and type_ == "hello":
            await self._on_hello(payload)
        elif channel == Channel.EVENTS and type_ == "tour_say":
            await self._on_tour_say(payload)
        elif channel == Channel.STATE:
            if type_ == "barge_in":
                await self._on_barge_in(payload)
            elif isinstance(payload.get("component_state"), dict):
                await self._on_component_state(payload["component_state"])
            else:  # sync
                self._update_state(payload)

    async def _on_binary(self, frame: bytes) -> None:
        """A binary frame from the widget is a mic chunk (WS5)."""
        audio = unpack_audio(frame)
        if audio is None:
            return
        if self.privacy.consent_required and self._consent_at is None:
            await self._ask_consent()
            return
        self._add_audio(audio[1])

    def _add_audio(self, pcm: bytes) -> None:
        if pcm and self._audio_bytes + len(pcm) <= _MAX_UTTERANCE_BYTES:
            self._audio.append(pcm)
            self._audio_bytes += len(pcm)

    async def _ask_consent(self) -> None:
        """Mic audio arrived before the visitor allowed it: drop it and tell
        the widget once."""
        if not self._consent_asked:
            self._consent_asked = True
            await self.send(Channel.EVENTS, "consent_required",
                            {"privacy": self.privacy.public()})

    def _update_state(self, payload: dict) -> None:
        if "page" in payload:
            self.state.page = payload["page"]
        # Accept either "viewport" or the friendlier "section" for the in-view area.
        if "section" in payload:
            self.state.viewport = payload["section"]
        elif "viewport" in payload:
            self.state.viewport = payload["viewport"]
        if isinstance(payload.get("sections"), list):
            self.state.sections = normalize_sections(payload["sections"])
        if payload.get("persona"):
            self.state.persona = payload["persona"]
        if payload.get("intelligence") and not self._tier_locked:
            self.state.intelligence = normalize_intelligence(payload["intelligence"])

    # ---- ASR over buffered audio (real engines) -------------------------
    async def _asr(self) -> str:
        if not self._audio:
            return ""

        async def chunks() -> AsyncIterator[bytes]:
            for c in self._audio:
                yield c

        final = ""
        try:
            async for ev in self.rt.engines.asr.transcribe_stream(chunks()):
                if ev.is_final and ev.text:
                    final = ev.text
        except Exception as exc:  # ASR failure shouldn't kill the socket
            logger.warning("ASR failed: %s", exc)
        return final

    # ---- turn handling --------------------------------------------------
    async def _budget_blocked(self) -> bool:
        """Apply the per-site rate limit + daily spend cap before a spoken turn
        (docs/defects.md D-3). Tells the client why when it refuses. Fails open
        if the guard itself errors, so a DB hiccup doesn't silence the agent."""
        try:
            async with session_scope() as db:
                reason = await check_public_budget(db, self.state.site_key, self.rt.settings)
        except Exception as exc:
            logger.warning("ws[%s]: budget check failed: %s", self.session_id[:8], exc)
            return False
        if reason:
            logger.info("ws[%s]: turn refused (%s)", self.session_id[:8], reason)
            await self.send(Channel.EVENTS, "error", {"reason": reason})
            return True
        return False

    async def _on_utterance(self, transcript: str) -> None:
        if await self._budget_blocked():
            return
        sid = self.session_id[:8]
        now = time.monotonic()
        in_flight = bool(self._response_task and not self._response_task.done())
        # Fragmented speech: if the previous response is still running and this
        # utterance arrived quickly, it's almost certainly a continuation of the
        # same question — combine rather than discard the earlier part.
        if (in_flight and self._last_utt_text
                and now - self._last_utt_at < _COALESCE_WINDOW_S):
            transcript = f"{self._last_utt_text} {transcript}".strip()
            logger.info("ws[%s]: coalesced continuation -> %r", sid,
                        redact(transcript)[:200])
        else:
            logger.info("ws[%s]: user> %r", sid, redact(transcript)[:160])
        self._last_utt_text = transcript
        self._last_utt_at = now
        await self._cancel_response()  # supersede any in-flight response
        self._response_task = asyncio.create_task(self._respond(transcript))

    async def _on_hello(self, payload: dict) -> None:
        """Voice-first onboarding: the visitor opened the agent. If a guided tour
        was authored for this site at ingestion, hand the plan to the client and
        let it drive the speak→scroll choreography (Req 5); otherwise fall back to
        the page-aware spoken welcome. Fired once per session (Req 3.x)."""
        self._update_state(payload)
        if self._greeted:
            return
        self._greeted = True
        await self._cancel_response()

        # Only offer the tour if the client hasn't opted out (data-tour="false");
        # otherwise the visitor still gets the spoken welcome.
        if payload.get("tour", True) is not False:
            plan = await self._load_tour()
            if plan is not None:
                self._tour_plan = plan
                await self.send(Channel.EVENTS, "tour_plan",
                                {"stops": [s.to_dict() for s in plan.stops]})
                logger.info("ws[%s]: sent tour plan (%d stops)",
                            self.session_id[:8], len(plan.stops))
                return

        self._response_task = asyncio.create_task(self._welcome())

    async def _load_tour(self):
        try:
            async with session_scope() as db:
                return await load_plan(db, self.state.site_key)
        except Exception as exc:
            logger.warning("ws[%s]: tour load failed: %s", self.session_id[:8], exc)
            return None

    async def _on_tour_say(self, payload: dict) -> None:
        """Speak one pre-planned tour narration, then signal completion so the
        client performs the stop's move (scroll/navigate) only AFTER the voice
        has finished — the exact speak/scroll sync the tour requires (Req 5).

        The client only chooses WHICH step; the words always come from the
        stored plan, so tour_say can't be used to speak arbitrary text."""
        index = payload.get("index")
        text = await self._tour_narration(index)
        if text is None:
            await self.send(Channel.EVENTS, "error", {"reason": "unknown_tour_step"})
            return
        if not text or await self._budget_blocked():
            return
        await self._cancel_response()
        self._response_task = asyncio.create_task(self._tour_say(text, index))

    async def _tour_narration(self, index) -> str | None:
        """Stored narration for tour step ``index``; None if there is no such step."""
        if isinstance(index, bool) or not isinstance(index, int):
            return None
        plan = self._tour_plan or await self._load_tour()
        if plan is None or not 0 <= index < len(plan.stops):
            return None
        return (plan.stops[index].narration or "").strip()

    async def _tour_say(self, text: str, index) -> None:
        try:
            # Narration is interruptible by a genuine barge-in (the VAD onset gate
            # keeps incidental noise from triggering it).
            self._answer_speaking = True
            try:
                await self._speak(text, _sid("tour"))
            finally:
                self._answer_speaking = False
            await self.send(Channel.EVENTS, "tour_done", {"index": index})
            # Record each played tour step (Req: tour recorded for every step).
            self._spawn(self._record_tour_stop(index, text))
        except asyncio.CancelledError:
            await self.send(Channel.EVENTS, "interrupted", {})
            raise
        except Exception as exc:
            logger.exception("ws[%s]: tour_say failed: %s", self.session_id[:8], exc)

    async def _welcome(self) -> None:
        try:
            async with session_scope() as db:
                bridge = self.rt.bridge(db, self.state.site_key)
                think = await self.rt.loop.welcome(self.state, bridge)
            self._answer_speaking = True
            try:
                await self._speak(
                    think.answer_text, _sid("welcome"), grounding=think.grounding
                )
            finally:
                self._answer_speaking = False
            self.state.add_turn("(visitor arrived on the page)", think.answer_text)
            self._spawn(self._record_turn(
                question="(visitor arrived on the page)",
                answer_text=think.answer_text, components=think.components,
                actions=think.actions, channel="welcome",
            ))
        except asyncio.CancelledError:
            await self.send(Channel.EVENTS, "interrupted", {})
            raise
        except Exception as exc:
            logger.exception("welcome failed: %s", exc)

    async def _respond(self, heard: str) -> None:
        # PII masking (WS8): from here on the router, the thinker, the history
        # and every store see placeholders, never the visitor's details. A turn
        # that carries them is personal, so it is neither replayed nor cached.
        pii = self.state.pii
        transcript = pii.mask(heard)
        personal = transcript != heard
        # A mid-conversation follow-up ("how much is it?") only makes sense in
        # this conversation: answer it fresh and don't cache it (WS5).
        followup = depends_on_history(transcript, self.state.history)

        # Cache-first (Feature 2): if we've answered a near-identical question for
        # this persona before and have enough history, replay it verbatim
        # (components + byte-exact audio) instead of re-thinking.
        if not personal and not followup and await self._maybe_replay(transcript):
            return

        think_task: asyncio.Task | None = None
        t0 = time.monotonic()
        try:
            await self.send(Channel.STATE, "transcript", {"text": heard})

            # 1. Fast Router — instant ack (latency masking, Req 3.3.1)
            self._persona_emitted = self.state.persona
            route = await self.rt.loop.route(transcript, self.state)

            # Adaptive persona + probe decision (Feature 1): switch only on a
            # confident, changed read; decide whether to weave in a qualifying
            # question this turn so we keep learning who the visitor is.
            probe = should_probe(self.state)
            switch = bool(route.persona) and self.rt.loop.apply_persona(
                self.state, route.persona, route.persona_confidence,
                explicit=route.persona_explicit,
            )
            bump_probe(self.state, probe)
            persona = self.state.persona

            # 2. Hybrid: most turns take the LEAN path (one retrieval + one
            #    generation, no tool loop); only turns that need a diagram, page,
            #    navigation, or numbers escalate to the Heavy Thinker. Start it NOW
            #    so reasoning runs *while* the ack is spoken — overlapping the two
            #    removes the dead air between ack and answer. (Req 3 / 3.3.2) A
            #    cached near-match (below the replay bar) rides along as context.
            heavy = self.rt.loop.needs_heavy(transcript, route.intent, self.state)
            think_task = asyncio.create_task(
                self._think(transcript, persona, heavy,
                            related=self._related, probe=probe)
            )

            await self._speak(pii.spoken(route.ack), _sid("ack"))

            if switch:
                self._persona_emitted = self.state.persona
                await self.send(Channel.EVENTS, "set_persona",
                                {"persona": self.state.persona})

            think = await think_task
            think_task = None

            # 3. Emit DATA (components + full generated pages) — share sync_id
            #    with the spoken answer
            primary_sync: str | None = None
            for comp in think.components:
                primary_sync = primary_sync or comp.sync_id
                self.state.register_component(
                    comp.sync_id, comp.component_type, comp.initial_state)
                await self.send(Channel.DATA, "render", comp.to_dict(), comp.sync_id)
            for page in think.pages:
                primary_sync = primary_sync or page.sync_id
                await self.send(Channel.DATA, "render_page", page.to_dict(), page.sync_id)
            # In-place updates of components already on screen (D-11).
            for p in think.patches:
                if self.state.update_component_state(p.target_sync_id, p.patch) is not None:
                    await self.send(Channel.DATA, "patch", p.to_dict(), p.target_sync_id)

            # 4. Emit EVENTS (DOM commands)
            for action in think.actions:
                await self._emit_action(action)

            # 5. Stream the grounded answer as TTS, synced to its component
            self._answer_speaking = True  # now interruptible by a real barge-in
            try:
                await self._speak(pii.spoken(think.answer_text), primary_sync or _sid("utt"),
                                  grounding=think.grounding)
            finally:
                self._answer_speaking = False
            self.state.add_turn(transcript, think.answer_text)
            self._last_utt_text = ""  # turn answered — next utterance starts fresh
            logger.info(
                "ws[%s]: turn complete — answer_len=%d actions=%d components=%d",
                self.session_id[:8], len(think.answer_text),
                len(think.actions), len(think.components),
            )
            # Record the full multimodal turn for future replay (fire-and-forget).
            # A patch targets this session's components, and a captured lead holds
            # one visitor's contact details, so neither turn may be replayed.
            personal = personal or contains_pii(think.answer_text)
            if not think.patches and not think.leads and not personal and not followup:
                self._spawn(self._record_turn(
                    question=transcript, answer_text=think.answer_text,
                    components=think.components, actions=think.actions,
                    channel="voice", grounding=think.grounding,
                ))
            # Record cost/performance for this generated voice turn (req F/G).
            self._spawn(self._record_usage(
                intent=route.intent, transcript=transcript, ack=route.ack,
                answer_text=think.answer_text, think=think,
                served_from_cache=False, t0=t0,
            ))
            self._spawn(self._record_conversation(
                question=pii.stored(transcript), answer=pii.stored(think.answer_text),
                intent=route.intent,
                grounding=think.grounding.to_dict(), served_from_cache=False,
                leads=think.leads,
            ))
        except asyncio.CancelledError:
            logger.info("ws[%s]: turn CANCELLED before completion (barge-in or "
                        "new utterance)", self.session_id[:8])
            await self.send(Channel.EVENTS, "interrupted", {})
            raise
        except Exception as exc:
            logger.exception("ws[%s]: response failed: %s", self.session_id[:8], exc)
            await self.send(Channel.EVENTS, "error", {"message": "Something went wrong."})
        finally:
            # Never leave the concurrently-started thinker running orphaned (e.g.
            # a barge-in cancelled us mid-ack).
            if think_task and not think_task.done():
                think_task.cancel()
                try:
                    await think_task
                except (asyncio.CancelledError, Exception):
                    pass

    async def _think(self, transcript: str, persona, heavy: bool = True,
                     related=None, probe: bool = False):
        """Run the chosen reasoning path in its own DB session so it executes
        concurrently with the spoken ack. ``heavy`` selects the grounded tool
        loop; otherwise the lean single-shot path answers (Hybrid). ``related``
        injects cached near-matches as context; ``probe`` asks the model to weave
        in a qualifying question."""
        async with session_scope() as db:
            bridge = self.rt.bridge(db, self.state.site_key)
            if heavy:
                return await self.rt.loop.think(
                    transcript, self.state, bridge, persona,
                    related=related, probe=probe,
                )
            return await self.rt.loop.think_lean(
                transcript, self.state, bridge, persona, related=related, probe=probe,
            )

    async def _emit_action(self, action: ClientAction) -> None:
        if action.type == "navigate":
            await self.send(Channel.EVENTS, "navigate", {"path": action.path}, _sid("evt"))
        elif action.type == "scroll_to":
            await self.send(Channel.EVENTS, "scroll_to",
                            {"sectionId": action.section_id,
                             "direction": action.direction}, _sid("evt"))
        elif action.type == "set_icp":
            # The Fast Router may already have switched persona this turn; only
            # emit when it actually changes (silent-switch dedupe, Req 3.6) and
            # passes the flip-flop guard.
            if (action.icp and action.icp != self._persona_emitted
                    and self.rt.loop.apply_persona(
                        self.state, action.icp, THINKER_SWITCH_CONFIDENCE)):
                self._persona_emitted = action.icp
                await self.send(Channel.EVENTS, "set_persona",
                                {"persona": action.icp}, _sid("evt"))

    async def _speak(self, text: str, sync_id: str, grounding=None) -> None:
        if not text:
            return
        basic = self.state.intelligence == "basic"
        # Sentence-streamed TTS: synthesise + stream one chunk at a time so the
        # first chunk plays after ~its own synthesis (~2-3s) rather than blocking
        # on the entire utterance (which logs showed at ~18s for a long answer).
        # The FIRST chunk keeps the caller's sync_id so a gated UI component still
        # gates the speech and the full transcript/grounding surface together;
        # later chunks get fresh ungated ids and play in FIFO arrival order.
        #
        # Synthesis runs one segment AHEAD of the one being sent (WS5): while
        # segment n streams out, n+1 is already synthesising, so a long answer
        # has no silent gap between sentences.
        segments = split_for_tts(text)
        queues: list[asyncio.Queue] = []
        tasks: list[asyncio.Task] = []

        def synth(i: int) -> None:
            q: asyncio.Queue = asyncio.Queue()
            queues.append(q)
            tasks.append(asyncio.create_task(self._synthesize(segments[i], q)))

        done = False
        try:
            if not basic:
                synth(0)
            for idx, seg_text in enumerate(segments):
                if not basic and idx + 1 < len(segments):
                    synth(idx + 1)
                seg_id = sync_id if idx == 0 else _sid("utt")
                start_payload: dict = {}
                if idx == 0:
                    start_payload["text"] = text
                    if grounding is not None:
                        start_payload["grounding"] = grounding.to_dict()
                await self.send(Channel.AUDIO, "start", start_payload, seg_id)
                # Basic tier is text-only: emit start/end (so the message +
                # grounding still surface) but skip TTS synthesis.
                if not basic:
                    while (chunk := await queues[idx].get()) is not None:
                        await self._send_audio(chunk, seg_id)
                await self.send(Channel.AUDIO, "end", {}, seg_id)
            done = True
        finally:
            for t in tasks:
                if t.done():
                    continue
                if done:   # only the audio-cache write is left: let it finish
                    self._bg_tasks.add(t)
                    t.add_done_callback(self._bg_tasks.discard)
                else:      # barge-in or error: stop synthesising
                    t.cancel()

    async def _synthesize(self, seg_text: str, q: asyncio.Queue) -> None:
        """Produce one segment's PCM into ``q``, then None. Serves byte-exact
        cached PCM when we've synthesised this exact text + voice before, else
        streams live TTS and persists it for next time (Feature 2 audio cache).
        A TTS failure ends the segment silently; the text is already shown."""
        use_cache = self.rt.settings.audio_cache_enabled
        buf = bytearray()
        try:
            if use_cache:
                cached = await self._audio_cache_get(seg_text)
                if cached is not None:
                    for frame in self._frames(cached):
                        q.put_nowait(frame)
                    return
            async for chunk in self.rt.engines.tts.synthesize_stream(seg_text):
                if chunk:
                    buf.extend(chunk)
                    q.put_nowait(bytes(chunk))
        except asyncio.CancelledError:
            buf.clear()
            raise
        except Exception as exc:
            buf.clear()
            logger.warning("ws[%s]: TTS failed: %s", self.session_id[:8], exc)
        finally:
            q.put_nowait(None)
        if use_cache and buf:
            await self._audio_cache_put(seg_text, bytes(buf))

    def _frames(self, pcm: bytes) -> list[bytes]:
        """Re-chunk cached PCM into ~0.2s frames so playback ramps like live TTS."""
        frame = max(1, int(self.rt.settings.tts_sample_rate * 0.2)) * 2  # 16-bit mono
        return [pcm[i:i + frame] for i in range(0, len(pcm), frame)]

    async def _send_audio(self, pcm: bytes, seg_id: str) -> None:
        if self.binary_audio:
            await self.ws.send_bytes(pack_audio(seg_id, pcm))
        else:
            await self.send(Channel.AUDIO, "chunk",
                            {"data": base64.b64encode(pcm).decode("ascii")}, seg_id)

    # ---- conversation cache (Feature 2) ---------------------------------
    def _spawn(self, coro) -> None:
        """Run a fire-and-forget side task (recording) without blocking the turn
        or letting it be garbage-collected mid-flight."""
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _audio_cache_get(self, seg_text: str):
        try:
            async with session_scope() as db:
                cache = self.rt.audio_cache(db)
                return await cache.get(cache.key(seg_text))
        except Exception:
            return None

    async def _audio_cache_put(self, seg_text: str, pcm: bytes) -> None:
        try:
            async with session_scope() as db:
                cache = self.rt.audio_cache(db)
                await cache.put(cache.key(seg_text), self.state.site_key, pcm)
        except Exception:
            pass

    async def _record_turn(self, *, question, answer_text, components, actions,
                           channel, grounding=None) -> None:
        if not self.rt.settings.conversation_cache_enabled or not answer_text:
            return
        try:
            async with session_scope() as db:
                cache = self.rt.episodic(db, self.state.site_key)
                await cache.record(
                    question=question, answer_text=answer_text,
                    components=[c.to_dict() for c in components],
                    actions=[a.to_dict() for a in actions],
                    persona=self.state.persona, page=self.state.page, channel=channel,
                    grounding=grounding.to_dict() if grounding is not None else None,
                )
        except Exception as exc:
            logger.warning("ws[%s]: record_turn failed: %s", self.session_id[:8], exc)

    async def _record_conversation(self, *, question, answer, intent, grounding,
                                   served_from_cache, leads=()) -> None:
        """Append the turn to this session's transcript (Insights, WS10), then
        save any lead the agent captured in it (WS7)."""
        from app.insights.store import record_turn as record_conversation_turn
        try:
            async with session_scope() as db:
                await record_conversation_turn(
                    db, site_key=self.state.site_key, session_id=self.session_id,
                    channel="voice", question=question, answer=answer, intent=intent,
                    persona=self.state.persona, page=self.state.page,
                    grounding=grounding, served_from_cache=served_from_cache,
                    consent_at=self._consent_at,
                )
        except Exception as exc:
            logger.warning("ws[%s]: conversation record failed: %s",
                           self.session_id[:8], exc)
        if leads:
            from app.leads.capture import save_captured
            await save_captured(self.state.site_key, self.session_id,
                                self.state.persona, list(leads))

    async def _record_usage(
        self, *, intent, transcript, ack="", answer_text="", think=None,
        served_from_cache=False, t0=None,
    ) -> None:
        """Persist one voice-turn usage event for analytics (req F/G). ASR
        duration is estimated from the transcript length (~15 chars/sec of
        speech); TTS chars are everything spoken (ack + answer)."""
        from app.analytics.usage import TurnMetrics, record_turn
        try:
            latency = (time.monotonic() - t0) * 1000.0 if t0 else 0.0
            metrics = TurnMetrics(
                site_key=self.state.site_key, session_id=self.session_id,
                channel="voice", intent=intent, persona=self.state.persona,
                page=self.state.page, served_from_cache=served_from_cache,
                asr_ms=(len(transcript or "") / 15.0) * 1000.0,
                tts_chars=len(ack or "") + len(answer_text or ""),
                latency_ms=latency,
            )
            if think is not None and not served_from_cache:
                metrics.add_llm(
                    kind=getattr(think, "llm_kind", "thinker"),
                    input_tokens=getattr(think, "input_tokens", 0),
                    output_tokens=getattr(think, "output_tokens", 0),
                    tool_calls=getattr(think, "tool_calls", 0),
                )
            async with session_scope() as db:
                await record_turn(db, metrics)
        except Exception as exc:
            logger.debug("ws[%s]: usage record skipped: %s", self.session_id[:8], exc)

    async def _record_tour_stop(self, index, narration) -> None:
        if not self.rt.settings.conversation_cache_enabled or not narration:
            return
        try:
            async with session_scope() as db:
                cache = self.rt.episodic(db, self.state.site_key)
                await cache.record_tour_stop(
                    index=index, narration=narration, move=None,
                    persona=self.state.persona, page=self.state.page,
                )
        except Exception as exc:
            logger.warning("ws[%s]: record_tour_stop failed: %s",
                           self.session_id[:8], exc)

    async def _maybe_replay(self, transcript: str) -> bool:
        """Hybrid replay decision. Sets ``self._related`` for the context tier and
        returns True only when it has fully handled the turn by replaying."""
        self._related = []
        st = self.rt.settings
        if not st.conversation_cache_enabled:
            return False
        try:
            async with session_scope() as db:
                cache = self.rt.episodic(db, self.state.site_key)
                hits = await cache.query(
                    transcript=transcript, persona=self.state.persona,
                    page=self.state.page, top_k=st.episodic_top_k,
                )
                total = await cache.count(persona=self.state.persona)
        except Exception as exc:
            logger.warning("ws[%s]: replay query failed: %s", self.session_id[:8], exc)
            return False
        # Only engage once enough history exists for this persona ("enough data"),
        # unless the tenant pinned this answer (WS8).
        if not hits:
            return False
        best = hits[0]
        if not best.pinned and total < st.episodic_min_episodes:
            return False
        if best.score >= st.episodic_replay_threshold:
            await self._replay(transcript, best)
            return True
        if best.score >= st.episodic_context_threshold:
            self._related = hits  # ride along as context for a fresh answer
        return False

    async def _replay(self, transcript: str, best) -> None:
        """Stream a cached answer verbatim: components, then byte-exact audio."""
        t0 = time.monotonic()
        logger.info("ws[%s]: REPLAY (score=%.3f, %d components) for %r",
                    self.session_id[:8], best.score, len(best.components),
                    transcript[:80])
        ack = _replay_ack(transcript)
        try:
            await self.send(Channel.STATE, "transcript", {"text": transcript})
            await self._speak(ack, _sid("ack"))
            primary_sync: str | None = None
            for comp in best.components:
                sid = _sid("ui")
                primary_sync = primary_sync or sid
                self.state.register_component(
                    sid, comp.get("component_type", ""), comp.get("initial_state", {}))
                await self.send(Channel.DATA, "render", {**comp, "sync_id": sid}, sid)
            for action in best.actions:
                await self._emit_cached_action(action)
            self._answer_speaking = True
            try:
                # The original answer's sources travel with the replay (WS8).
                g = best.grounding
                await self._speak(best.answer_text, primary_sync or _sid("utt"),
                                  grounding=Grounding(**g) if g else None)
            finally:
                self._answer_speaking = False
        except asyncio.CancelledError:
            await self.send(Channel.EVENTS, "interrupted", {})
            raise
        self.state.add_turn(transcript, best.answer_text)
        self._last_utt_text = ""
        try:
            async with session_scope() as db:
                await self.rt.episodic(db, self.state.site_key).mark_hit(
                    best.question, self.state.persona
                )
        except Exception:
            pass
        # Cached voice turn: no LLM spend — only TTS (req G shows the saving).
        self._spawn(self._record_usage(
            intent="cached", transcript=transcript, ack=ack, answer_text=best.answer_text,
            served_from_cache=True, t0=t0,
        ))
        self._spawn(self._record_conversation(
            question=transcript, answer=best.answer_text, intent="cached",
            grounding=best.grounding, served_from_cache=True,
        ))

    async def _emit_cached_action(self, action: dict) -> None:
        """Re-emit a stored action dict (ClientAction.to_dict shape) on replay."""
        t = action.get("type")
        if t == "navigate" and action.get("path"):
            await self.send(Channel.EVENTS, "navigate", {"path": action["path"]}, _sid("evt"))
        elif t == "scroll_to" and (action.get("sectionId") or action.get("direction")):
            await self.send(Channel.EVENTS, "scroll_to",
                            {"sectionId": action.get("sectionId"),
                             "direction": action.get("direction")}, _sid("evt"))
        elif t == "set_icp" and action.get("icp"):
            self.state.persona = action["icp"]
            self._persona_emitted = action["icp"]
            await self.send(Channel.EVENTS, "set_persona",
                            {"persona": action["icp"]}, _sid("evt"))

    # ---- live component reactions (Features 3/4 follow-up) ---------------
    async def _on_component_state(self, cs: dict) -> None:
        """The visitor changed an interactive component. Merge the new state and
        (debounced) speak a short reaction — unless we're already talking or
        mid-turn (never talk over the user or another answer)."""
        sync_id = cs.get("sync_id")
        if not sync_id:
            return
        patch = {k: v for k, v in cs.items() if k != "sync_id"}
        if self.state.update_component_state(sync_id, patch) is None:
            return  # unknown component (e.g. rendered in a previous session)
        # Debounce: supersede any pending reaction so rapid drags coalesce into a
        # single comment on the settled values.
        self._cancel_react()
        self._react_task = asyncio.create_task(self._react_after_delay(sync_id))

    async def _react_after_delay(self, sync_id: str, delay: float = 0.7) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        # Never talk over the agent's own answer, a turn in flight, or a tour —
        # a genuine question always wins (it cancels this task first).
        if self._answer_speaking or (self._response_task and not self._response_task.done()):
            return
        entry = self.state.components.get(sync_id)
        if not entry:
            return
        try:
            text = await self.rt.loop.react(entry, self.state.persona, self.state.site_key)
        except Exception as exc:
            logger.warning("ws[%s]: react failed: %s", self.session_id[:8], exc)
            return
        if not text:
            return
        logger.info("ws[%s]: live reaction to %s", self.session_id[:8], sync_id)
        self._answer_speaking = True
        try:
            await self._speak(text, _sid("react"))
        except asyncio.CancelledError:
            await self.send(Channel.EVENTS, "interrupted", {})
        finally:
            self._answer_speaking = False

    def _cancel_react(self) -> None:
        task = self._react_task
        if task and not task.done():
            task.cancel()
        self._react_task = None

    # ---- barge-in (Req 3.3.4 / 3.5) -------------------------------------
    async def _on_barge_in(self, payload: dict) -> None:
        sid = self.session_id[:8]
        # Only a barge-in DURING the spoken answer is a real interruption. Speech
        # while the ack is playing or the thinker is still running is almost
        # always the visitor finishing their own sentence — ignore it so we don't
        # kill the turn and leave them with no answer (the cause of the dropped
        # last query). A genuine new question still arrives via _on_utterance.
        if not self._answer_speaking:
            logger.info("ws[%s]: barge-in ignored (answer not yet speaking)", sid)
            return
        logger.info("ws[%s]: barge-in — interrupting answer", sid)
        await self._cancel_response()
        await self.send(Channel.EVENTS, "recalibrating", {})
        # The correction itself arrives as the next AUDIO/end or EVENTS/text,
        # which starts a fresh turn with the reported state in context.

    async def _cancel_response(self) -> None:
        self._cancel_react()  # a new turn / barge-in supersedes a live reaction
        task = self._response_task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._response_task = None
        self._answer_speaking = False


@router.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket) -> None:
    runtime = websocket.app.state.runtime
    # Resolve site + tier server-side (docs/defects.md D-1). A widget key pins
    # the site and its configured tier; a registered tenant site may not be
    # reached by raw site_key without one.
    try:
        async with session_scope() as rdb:
            resolved = await resolve_public_site(
                rdb,
                key=websocket.query_params.get("key"),
                site=websocket.query_params.get("site"),
                intelligence=websocket.query_params.get("intelligence"),
                origin=websocket.headers.get("origin"),
            )
    except PublicAccessError as exc:
        await websocket.accept()
        await websocket.send_json(make(Channel.EVENTS, "error", {"reason": exc.reason}))
        await websocket.close(code=4403)
        return

    # Load the site's agent profile (name, personas, sitemap) for the prompts.
    await ensure_profile(resolved.site_key)
    await ensure_design(resolved.site_key)  # themes Extreme pages (WS9)
    session = VoiceSession(
        websocket, runtime, site_key=resolved.site_key,
        intelligence=resolved.intelligence, tier_locked=resolved.tier_locked,
        binary_audio=websocket.query_params.get("audio") == "binary",
    )
    await session.run()
