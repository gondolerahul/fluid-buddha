"""
Conversation cache — episodic memory + hybrid replay (Feature 2).

Two cooperating stores:

* ``conversation_cache`` (raw-DDL table here) is the **source of truth for
  replay**: every turn's transcript, answer, rendered components and actions,
  scoped by persona + page, with its own pgvector embedding column. Replay is
  decided from (a) a deterministic exact normalised-question match and
  (b) cosine similarity over the embedding — so "ask the same thing twice"
  replays verbatim regardless of the embedding backend.

* CORTEX ``EpisodicTreeService`` is populated **best-effort** alongside, giving
  the agent a real hierarchical episodic memory (month → day → episode) for
  semantic recall and future consolidation (``DreamingEngine``). Replay never
  depends on it, so the package's storage quirks can't break a conversation.

Golden answers (WS8): each row has a ``status``. ``pinned`` is the tenant's
approved answer: it wins an exact match, replays before the "enough data"
gate and survives retention. ``blocked`` never replays, and its question is
not cached again, so it is always answered fresh. ``auto`` is everything else.

Privacy (Req 4.2): only transcripts + agent output + component specs are stored
here — never the visitor's microphone audio (that lives only in the agent's TTS
cache, see ``app/transport/answer_audio.py``).
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cortex_memory.embedding import embed_query
from cortex_memory.episodic_tree import EpisodicTreeService

from app.config import Settings, site_entity_id
from app.cortex.providers import CortexProviders

logger = logging.getLogger(__name__)


def normalize_question(q: str) -> str:
    """Casefold + collapse whitespace so trivially different phrasings of the
    same question hit the exact-match path."""
    return " ".join((q or "").strip().lower().split())


@dataclass
class CachedAnswer:
    """A replayable past turn pulled from the cache."""
    question: str
    answer_text: str
    components: list[dict]
    actions: list[dict]
    persona: Optional[str]
    page: Optional[str]
    score: float           # 1.0 for an exact-question match, else cosine
    match: str             # 'exact' | 'semantic'
    grounding: Optional[dict] = None   # the original answer's sources (WS8)
    pinned: bool = False               # the tenant's approved answer (WS8)


@dataclass
class _EpisodeRun:
    """Minimal run-shaped object satisfying ``EpisodicTreeService.write_episode``
    (it reads id/created_at/input_data/result_data/context_state/status + cost
    fields, and embeds input+output)."""
    id: uuid.UUID
    input_data: str
    result_data: str
    context_state: dict
    status: str = "complete"
    created_at: datetime = field(default_factory=datetime.utcnow)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    execution_time_ms: int = 0


class EpisodicCache:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        providers: CortexProviders,
        *,
        site_key: str = "hirebuddha",
    ) -> None:
        self.db = session
        self.settings = settings
        self.providers = providers
        self.site_key = site_key
        self.entity_id = site_entity_id(site_key)
        self.company_id = settings.cortex_company_id
        self.dim = settings.embed_dim

    # ---- embeddings -----------------------------------------------------
    async def _embed(self, q: str) -> Optional[list[float]]:
        try:
            return await embed_query(self.providers.embedding, q)
        except Exception as exc:  # embedding is optional; exact-match still works
            logger.debug("episodic embed failed: %s", exc)
            return None

    # ---- write ----------------------------------------------------------
    async def record(
        self,
        *,
        question: str,
        answer_text: str,
        components: Optional[list[dict]] = None,
        actions: Optional[list[dict]] = None,
        persona: Optional[str] = None,
        page: Optional[str] = None,
        channel: str = "voice",
        kind: str = "turn",
        grounding: Optional[dict] = None,
        lang: str = "en",
    ) -> None:
        if not (question and answer_text):
            return
        lang = "hi" if lang == "hi" else "en"
        if kind == "turn" and await self._curated(question, lang):
            return   # a pinned answer stands; a blocked question stays uncached
        try:
            vec = await self._embed(question)
            sql = (
                "INSERT INTO conversation_cache "
                "(id, site_key, persona, page, kind, q_norm, question, answer_text, "
                " components, actions, channel, grounding, lang, embedding) VALUES "
                "(:id, :s, :p, :pg, :k, :qn, :q, :a, CAST(:c AS jsonb), "
                "CAST(:ac AS jsonb), :ch, CAST(:g AS jsonb), :lang, "
                + ("CAST(:emb AS vector)" if vec is not None else "NULL") + ")"
            )
            await self.db.execute(text(sql), {
                "id": uuid.uuid4(),
                "s": self.site_key,
                "p": persona,
                "pg": page,
                "k": kind,
                "qn": normalize_question(question),
                "q": question[:2000],
                "a": answer_text,
                "c": json.dumps(components or []),
                "ac": json.dumps(actions or []),
                "ch": channel,
                "g": json.dumps(grounding) if grounding else None,
                "lang": lang,
                "emb": json.dumps(vec) if vec is not None else None,
            })
            await self.db.commit()
        except Exception as exc:
            logger.warning("conversation_cache record failed: %s", exc)
            try:
                await self.db.rollback()
            except Exception:
                pass
            return

        if self.settings.episodic_memory_enabled and kind == "turn":
            await self._write_episode(question, answer_text, persona, page, channel)

    async def _curated(self, question: str, lang: str = "en") -> bool:
        try:
            res = await self.db.execute(text(
                "SELECT 1 FROM conversation_cache WHERE site_key=:s AND kind='turn' "
                "AND q_norm=:qn AND lang=:lang AND status <> 'auto' LIMIT 1"
            ), {"s": self.site_key, "qn": normalize_question(question), "lang": lang})
            return res.first() is not None
        except Exception:
            return False

    async def _write_episode(
        self, question: str, answer_text: str,
        persona: Optional[str], page: Optional[str], channel: str,
    ) -> None:
        """Populate the CORTEX episodic tree (best-effort, fully isolated)."""
        try:
            svc = EpisodicTreeService(
                self.db, self.company_id, embedding=self.providers.embedding
            )
            run = _EpisodeRun(
                id=uuid.uuid4(),
                input_data=question,
                result_data=answer_text,
                context_state={"persona": persona, "page": page, "channel": channel},
            )
            await svc.write_episode(self.entity_id, run)
            await self.db.commit()
        except Exception as exc:
            logger.debug("CORTEX episode write skipped (non-fatal): %s", exc)
            try:
                await self.db.rollback()
            except Exception:
                pass

    async def record_tour_stop(
        self, *, index: int, narration: str, move: Optional[dict],
        persona: Optional[str], page: Optional[str],
    ) -> None:
        """Record one played tour step (Req: 'tour recorded for every step').
        Stored as kind='tour_stop' so it never matches a normal turn replay."""
        await self.record(
            question=f"[tour stop {index}]",
            answer_text=narration,
            components=[],
            actions=([{"type": "tour_move", **move}] if move else []),
            persona=persona, page=page, channel="tour", kind="tour_stop",
        )

    # ---- read -----------------------------------------------------------
    async def count(self, *, persona: Optional[str] = None) -> int:
        """How many turns are cached (the 'enough data' replay gate)."""
        try:
            sql = ("SELECT count(*) FROM conversation_cache "
                   "WHERE site_key=:s AND kind='turn'")
            params: dict[str, Any] = {"s": self.site_key}
            if persona:
                sql += " AND persona=:p"
                params["p"] = persona
            res = await self.db.execute(text(sql), params)
            return int(res.scalar() or 0)
        except Exception:
            return 0

    async def query(
        self, *, transcript: str, persona: Optional[str] = None,
        page: Optional[str] = None, top_k: int = 3, lang: str = "en",
    ) -> list[CachedAnswer]:
        """Ranked replay candidates: exact-question match first (score 1.0), then
        persona-compatible cosine neighbours. Only answers given in ``lang``
        (M2-7): a Hindi question never replays an English answer."""
        lang = "hi" if lang == "hi" else "en"
        out: list[CachedAnswer] = []
        seen: set = set()

        # 1. Exact normalised-question match (deterministic, mock-safe).
        try:
            res = await self.db.execute(text(
                "SELECT id, question, answer_text, components, actions, persona, page, "
                "grounding, status FROM conversation_cache "
                "WHERE site_key=:s AND kind='turn' AND q_norm=:qn AND status <> 'blocked' "
                "AND lang=:lang "
                "AND (persona IS NULL OR CAST(:p AS text) IS NULL OR persona=CAST(:p AS text)) "
                "ORDER BY (status = 'pinned') DESC, "
                "(persona IS NOT DISTINCT FROM CAST(:p AS text)) DESC, "
                "created_at DESC LIMIT 1"
            ), {"s": self.site_key, "qn": normalize_question(transcript), "p": persona,
                "lang": lang})
            row = res.first()
            if row is not None:
                out.append(self._row_to_answer(row, 1.0, "exact", row[7], row[8]))
                seen.add(row[0])
        except Exception as exc:
            logger.warning("episodic exact query failed: %s", exc)

        # 2. Semantic cosine search (meaningful with real embeddings).
        vec = await self._embed(transcript)
        if vec is not None:
            try:
                res = await self.db.execute(text(
                    "SELECT id, question, answer_text, components, actions, persona, "
                    "page, 1 - (embedding <=> CAST(:vec AS vector)) AS score, grounding, "
                    "status FROM conversation_cache "
                    "WHERE site_key=:s AND kind='turn' AND embedding IS NOT NULL "
                    "AND status <> 'blocked' AND lang=:lang "
                    "AND (persona IS NULL OR CAST(:p AS text) IS NULL OR persona=CAST(:p AS text)) "
                    "ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :k"
                ), {"s": self.site_key, "vec": json.dumps(vec), "p": persona, "k": top_k,
                    "lang": lang})
                for r in res.fetchall():
                    if r[0] in seen:
                        continue
                    out.append(self._row_to_answer(r, float(r[7]), "semantic", r[8], r[9]))
                    seen.add(r[0])
            except Exception as exc:
                logger.warning("episodic semantic query failed: %s", exc)
        return out

    async def mark_hit(self, question: str, persona: Optional[str]) -> None:
        try:
            await self.db.execute(text(
                "UPDATE conversation_cache SET hit_count = hit_count + 1 "
                "WHERE site_key=:s AND kind='turn' AND q_norm=:qn "
                "AND (persona IS NULL OR CAST(:p AS text) IS NULL OR persona=CAST(:p AS text))"
            ), {"s": self.site_key, "qn": normalize_question(question), "p": persona})
            await self.db.commit()
        except Exception:
            try:
                await self.db.rollback()
            except Exception:
                pass

    # ---- admin CRUD (dashboard: view/edit cached responses, req E) -------
    @staticmethod
    def _as_list(v: Any) -> list:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            return [v]
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []

    def _entry_dict(self, r: Any) -> dict:
        return {
            "id": str(r["id"]),
            "question": r["question"],
            "answer_text": r["answer_text"],
            "components": self._as_list(r["components"]),
            "actions": self._as_list(r["actions"]),
            "persona": r["persona"],
            "page": r["page"],
            "channel": r["channel"],
            "hit_count": r["hit_count"],
            "status": r["status"],
            "lang": r.get("lang", "en"),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }

    async def list_entries(
        self, *, kind: str = "turn", limit: int = 50, offset: int = 0,
        search: Optional[str] = None, status: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """Page through cached turns for the admin cache editor."""
        where = "site_key=:s AND kind=:k"
        params: dict[str, Any] = {"s": self.site_key, "k": kind}
        if search:
            where += " AND (question ILIKE :q OR answer_text ILIKE :q)"
            params["q"] = f"%{search}%"
        if status:
            where += " AND status=:st"
            params["st"] = status
        total = (await self.db.execute(
            text(f"SELECT count(*) FROM conversation_cache WHERE {where}"), params
        )).scalar() or 0
        res = await self.db.execute(
            text("SELECT id, question, answer_text, components, actions, persona, page, "
                 f"channel, hit_count, status, lang, created_at FROM conversation_cache "
                 f"WHERE {where} ORDER BY created_at DESC LIMIT :lim OFFSET :off"),
            {**params, "lim": limit, "off": offset},
        )
        return [self._entry_dict(r) for r in res.mappings().all()], int(total)

    async def get_entry(self, entry_id: uuid.UUID) -> Optional[dict]:
        res = await self.db.execute(
            text("SELECT id, question, answer_text, components, actions, persona, page, "
                 "channel, hit_count, status, lang, created_at FROM conversation_cache "
                 "WHERE id=:id AND site_key=:s"),
            {"id": entry_id, "s": self.site_key},
        )
        row = res.mappings().first()
        return self._entry_dict(row) if row else None

    async def update_entry(
        self, entry_id: uuid.UUID, *,
        question: Optional[str] = None,
        answer_text: Optional[str] = None,
        components: Optional[list[dict]] = None,
        actions: Optional[list[dict]] = None,
        status: Optional[str] = None,
    ) -> Optional[dict]:
        """Edit a cached response/actions in place (req E). Editing the question
        also refreshes its normalised key + embedding so replay stays correct."""
        sets: list[str] = []
        params: dict[str, Any] = {"id": entry_id, "s": self.site_key}
        if answer_text is not None:
            sets.append("answer_text=:a"); params["a"] = answer_text
        if components is not None:
            sets.append("components=CAST(:c AS jsonb)"); params["c"] = json.dumps(components)
        if actions is not None:
            sets.append("actions=CAST(:ac AS jsonb)"); params["ac"] = json.dumps(actions)
        if status is not None:
            sets.append("status=:st"); params["st"] = status
        if question is not None:
            sets.append("question=:q"); params["q"] = question[:2000]
            sets.append("q_norm=:qn"); params["qn"] = normalize_question(question)
            vec = await self._embed(question)
            if vec is not None:
                sets.append("embedding=CAST(:emb AS vector)"); params["emb"] = json.dumps(vec)
        if not sets:
            return await self.get_entry(entry_id)
        await self.db.execute(
            text(f"UPDATE conversation_cache SET {', '.join(sets)} "
                 "WHERE id=:id AND site_key=:s"),
            params,
        )
        await self.db.commit()
        return await self.get_entry(entry_id)

    async def delete_entry(self, entry_id: uuid.UUID) -> bool:
        res = await self.db.execute(
            text("DELETE FROM conversation_cache WHERE id=:id AND site_key=:s"),
            {"id": entry_id, "s": self.site_key},
        )
        await self.db.commit()
        return (res.rowcount or 0) > 0

    @staticmethod
    def _row_to_answer(row: Any, score: float, match: str,
                       grounding: Any = None, status: Any = None) -> CachedAnswer:
        def _as_list(v: Any) -> list:
            if v is None:
                return []
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                return [v]
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return CachedAnswer(
            question=row[1], answer_text=row[2],
            components=_as_list(row[3]), actions=_as_list(row[4]),
            persona=row[5], page=row[6], score=score, match=match,
            grounding=grounding if isinstance(grounding, dict) else None,
            pinned=status == "pinned",
        )
