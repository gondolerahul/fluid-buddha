"""
Agent-TTS audio cache — byte-exact replay of synthesised speech.

The agent's spoken answers are deterministic given the text + voice, so once a
sentence segment has been synthesised we persist its PCM bytes and replay them
verbatim next time (instant, zero-cost, identical prosody). Keyed by a hash of
the segment text + the active voice/sample-rate so a voice change invalidates.

Privacy (Req 4.2): only the AGENT's synthesised output is stored here — the
visitor's microphone audio is never persisted.

Kept deliberately separate from the CORTEX ORM (raw DDL, like
``orchestrator/tour_store.py``) so it needs no migration and can't perturb the
knowledge schema.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings

logger = logging.getLogger(__name__)


def audio_key(seg_text: str, *, voice: str, sample_rate: int) -> str:
    """Stable cache key for one TTS segment under a given voice + sample rate."""
    norm = " ".join((seg_text or "").split())
    raw = f"{voice}|{sample_rate}|{norm}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class AnswerAudioCache:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.db = session
        self.settings = settings
        self.sample_rate = settings.tts_sample_rate
        self.voice = settings.tts_gemini_voice

    def key(self, seg_text: str) -> str:
        return audio_key(seg_text, voice=self.voice, sample_rate=self.sample_rate)

    async def get(self, text_hash: str) -> Optional[bytes]:
        try:
            res = await self.db.execute(
                text("SELECT pcm FROM answer_audio_cache WHERE text_hash = :h"),
                {"h": text_hash},
            )
            row = res.scalar()
        except Exception as exc:  # never let a cache miss-path break speech
            logger.warning("answer_audio_cache get failed: %s", exc)
            return None
        if row is None:
            return None
        return bytes(row)

    async def put(self, text_hash: str, site_key: str, pcm: bytes) -> None:
        if not pcm:
            return
        try:
            await self.db.execute(
                text(
                    "INSERT INTO answer_audio_cache (text_hash, site_key, sample_rate, pcm) "
                    "VALUES (:h, :s, :r, :p) ON CONFLICT (text_hash) DO NOTHING"
                ),
                {"h": text_hash, "s": site_key, "r": self.sample_rate, "p": pcm},
            )
            await self.db.commit()
        except Exception as exc:
            logger.warning("answer_audio_cache put failed: %s", exc)
