"""
Hindi voice round trip (M2-7 acceptance), with the real models.

1. Speak a Hindi question with the agent's TTS (hi-IN).
2. Recognise it with speech-to-text listening for hi-IN, then en-IN.
3. Detect the language, route it (Hindi acknowledgement + English search
   query), answer it from an English knowledge base (evals/hindi/corpus.json),
   and check the answer is Hindi with English source titles.
4. Speak the answer (hi-IN).

Needs Vertex AI and Cloud Speech-to-Text (GOOGLE_CLOUD_PROJECT + credentials).

    cd backend && python -m evals.hindi_voice
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import struct
import sys
import time
from pathlib import Path

os.environ["MOCK_AI"] = "false"

from app.config import get_settings  # noqa: E402
from app.i18n.detect import detect, speech_code  # noqa: E402

HERE = Path(__file__).parent / "hindi"
QUESTION = "ग्रोथ प्लान की कीमत कितनी है और क्या फ्री ट्रायल मिलता है?"


def _resample(pcm: bytes, src: int, dst: int) -> bytes:
    """PCM16 mono, linear interpolation (enough for speech recognition)."""
    n = len(pcm) // 2
    s = struct.unpack(f"<{n}h", pcm[: n * 2])
    m = int(n * dst / src)
    out = []
    for i in range(m):
        x = i * src / dst
        j = int(x)
        f = x - j
        a = s[j] if j < n else 0
        b = s[j + 1] if j + 1 < n else a
        out.append(int(a + (b - a) * f))
    return struct.pack(f"<{m}h", *out)


class _Bridge:
    """In-memory stand-in for the knowledge base: the English corpus."""

    def __init__(self, embedder, corpus):
        self.embedder, self.corpus, self.vecs = embedder, corpus, None

    async def search(self, query: str, top_k: int = 5):
        if self.vecs is None:
            self.vecs = await self.embedder.embed_texts([f"{d['title']}. {d['text']}" for d in self.corpus])
        q = (await self.embedder.embed_texts([query]))[0]

        def cos(v):
            return sum(a * b for a, b in zip(q, v)) / (
                math.sqrt(sum(a * a for a in q)) * math.sqrt(sum(b * b for b in v)) or 1.0)
        scored = sorted(zip(self.corpus, self.vecs), key=lambda d: -cos(d[1]))[:top_k]
        return [{"content": d["text"], "score": cos(v), "document_title": d["title"],
                 "section_title": None, "source_ref": {}} for d, v in scored]


async def main() -> int:
    from app.ai.vertex import GeminiTTS, VertexASR, VertexEmbedder, VertexLLMClient
    from app.orchestrator.lean import LeanResponder
    from app.orchestrator.router import FastRouter

    settings = get_settings()
    try:
        await VertexEmbedder(settings).embed_texts(["ping"])
    except Exception as exc:
        print(f"Vertex AI is not reachable: {type(exc).__name__}: {str(exc)[:200]}")
        return 2
    tts, asr, llm = GeminiTTS(settings), VertexASR(settings), VertexLLMClient(settings)
    ok = True

    t0 = time.monotonic()
    pcm = b"".join([c async for c in tts.synthesize_stream(QUESTION, "hi-IN")])
    print(f"1. spoke the question: {len(pcm) / 2 / settings.tts_sample_rate:.1f}s of audio "
          f"({time.monotonic() - t0:.1f}s)")

    audio16 = _resample(pcm, settings.tts_sample_rate, 16000)

    async def chunks():
        for i in range(0, len(audio16), 6400):
            yield audio16[i:i + 6400]
    heard, lang = "", ""
    async for ev in asr.transcribe_stream(chunks(), ["hi-IN", "en-IN"]):
        if ev.is_final and ev.text:
            heard, lang = heard + ev.text, ev.language or lang
    seen = detect(heard)
    print(f"2. heard ({lang or 'language not reported'}): {heard!r} → detected {seen}")
    ok &= seen == "hi"

    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    route = await FastRouter(llm, settings).route(heard or QUESTION, (), "eval-hindi", lang="hi", seen=seen)
    print(f"3. acknowledgement: {route.ack!r}; English search: {route.query_en!r}")
    ok &= detect(route.ack) == "hi" and bool(route.query_en) and route.query_en.isascii()
    think = await LeanResponder(llm, settings).respond(
        user_text=heard or QUESTION, persona=None, bridge=_Bridge(VertexEmbedder(settings), corpus),
        site_key="eval-hindi", lang="hi", seen=seen, search=route.query_en)
    sources = [s.get("document") for s in think.grounding.to_dict().get("sources", [])]
    print(f"   answer: {think.answer_text}")
    print(f"   sources: {sources}")
    ok &= detect(think.answer_text) == "hi" and any(s in ("Pricing plans", "Free trial") for s in sources)

    t0 = time.monotonic()
    out = b"".join([c async for c in tts.synthesize_stream(think.answer_text, speech_code("hi"))])
    print(f"4. spoke the answer: {len(out) / 2 / settings.tts_sample_rate:.1f}s of audio "
          f"({time.monotonic() - t0:.1f}s)")
    ok &= len(out) > settings.tts_sample_rate  # at least a second of speech

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
