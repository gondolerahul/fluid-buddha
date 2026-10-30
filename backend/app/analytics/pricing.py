"""
Per-unit pricing for the cost analytics (req F).

Costs are computed from the raw counts each turn produces (audio seconds, TTS
characters, LLM tokens, tool calls) using these rates. Defaults approximate the
Gemini / Google Cloud Speech price sheet; override any of them via env, e.g.
``PRICE_THINKER_OUT_PER_1K=0.0030``. This is a *pricing model*, not GCP billing
reconciliation (out of scope).
"""
from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from functools import lru_cache

# Categories surfaced in the dashboard breakdown.
CATEGORIES = ("asr", "tts", "fast_llm", "thinker_llm", "tool")


def _f(env: str, default: float) -> float:
    try:
        return float(os.getenv(env, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Pricing:
    asr_per_min: float            # speech-to-text, USD / audio minute
    tts_per_1k_chars: float       # text-to-speech, USD / 1000 chars
    fast_in_per_1k: float         # Fast (router/lean) LLM input, USD / 1000 tok
    fast_out_per_1k: float        # Fast LLM output, USD / 1000 tok
    thinker_in_per_1k: float      # Heavy Thinker input, USD / 1000 tok
    thinker_out_per_1k: float     # Heavy Thinker output, USD / 1000 tok
    tool_per_call: float          # per tool/function call, USD

    def cost_asr(self, ms: float) -> float:
        return (ms / 60000.0) * self.asr_per_min

    def cost_tts(self, chars: int) -> float:
        return (chars / 1000.0) * self.tts_per_1k_chars

    def cost_fast(self, in_tok: int, out_tok: int) -> float:
        return (in_tok / 1000.0) * self.fast_in_per_1k + \
               (out_tok / 1000.0) * self.fast_out_per_1k

    def cost_thinker(self, in_tok: int, out_tok: int) -> float:
        return (in_tok / 1000.0) * self.thinker_in_per_1k + \
               (out_tok / 1000.0) * self.thinker_out_per_1k

    def cost_tool(self, calls: int) -> float:
        return calls * self.tool_per_call

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache
def get_pricing() -> Pricing:
    return Pricing(
        asr_per_min=_f("PRICE_ASR_PER_MIN", 0.016),
        tts_per_1k_chars=_f("PRICE_TTS_PER_1K_CHARS", 0.016),
        fast_in_per_1k=_f("PRICE_FAST_IN_PER_1K", 0.000075),
        fast_out_per_1k=_f("PRICE_FAST_OUT_PER_1K", 0.00030),
        thinker_in_per_1k=_f("PRICE_THINKER_IN_PER_1K", 0.00030),
        thinker_out_per_1k=_f("PRICE_THINKER_OUT_PER_1K", 0.0025),
        tool_per_call=_f("PRICE_TOOL_PER_CALL", 0.0002),
    )


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token) for the mock engine and any path
    that lacks provider usage metadata."""
    return math.ceil(len(text or "") / 4)
