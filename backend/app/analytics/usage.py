"""
Per-turn usage events + the analytics aggregation behind the dashboard (req F, G).

Every agent turn (voice or text, generated or cache-replayed) writes one row to
``usage_events`` with the raw counts it produced and the USD cost of each stage
(ASR, TTS, Fast LLM, Thinker LLM, Tool calls). The analytics query rolls these up
by day / hour / session, broken down by category, with totals, latency
percentiles, and a generated-vs-cached split.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.pricing import Pricing, get_pricing

logger = logging.getLogger(__name__)


@dataclass
class TurnMetrics:
    """Raw per-turn counts; costs are derived at persist time from Pricing."""
    site_key: str
    session_id: Optional[str] = None
    channel: str = "text"            # 'text' | 'voice'
    intent: Optional[str] = "general"
    persona: Optional[str] = None
    page: Optional[str] = None
    served_from_cache: bool = False
    asr_ms: float = 0.0
    tts_chars: int = 0
    fast_in_tok: int = 0
    fast_out_tok: int = 0
    thinker_in_tok: int = 0
    thinker_out_tok: int = 0
    tool_calls: int = 0
    latency_ms: float = 0.0
    # Voice: question received → first byte of speech sent (F-3). None when
    # nothing was spoken (text turns, the Basic tier).
    ttfa_ms: Optional[float] = None

    def add_llm(self, *, kind: str, input_tokens: int, output_tokens: int,
                tool_calls: int = 0) -> None:
        """Attribute one LLM call's tokens to the Fast or Thinker bucket."""
        if kind == "thinker":
            self.thinker_in_tok += int(input_tokens)
            self.thinker_out_tok += int(output_tokens)
        else:
            self.fast_in_tok += int(input_tokens)
            self.fast_out_tok += int(output_tokens)
        self.tool_calls += int(tool_calls)


def _costs(m: TurnMetrics, p: Pricing) -> dict:
    asr = p.cost_asr(m.asr_ms)
    tts = p.cost_tts(m.tts_chars)
    fast = p.cost_fast(m.fast_in_tok, m.fast_out_tok)
    thinker = p.cost_thinker(m.thinker_in_tok, m.thinker_out_tok)
    tool = p.cost_tool(m.tool_calls)
    return {
        "asr_cost": asr, "tts_cost": tts, "fast_cost": fast,
        "thinker_cost": thinker, "tool_cost": tool,
        "total_cost": asr + tts + fast + thinker + tool,
    }


async def record_turn(db: AsyncSession, metrics: TurnMetrics,
                      pricing: Optional[Pricing] = None) -> None:
    """Persist one usage event. Best-effort: analytics must never break a turn."""
    pricing = pricing or get_pricing()
    try:
        costs = _costs(metrics, pricing)
        await db.execute(text(
            "INSERT INTO usage_events (id, site_key, session_id, channel, intent, "
            " persona, page, served_from_cache, asr_ms, tts_chars, fast_in_tok, "
            " fast_out_tok, thinker_in_tok, thinker_out_tok, tool_calls, asr_cost, "
            " tts_cost, fast_cost, thinker_cost, tool_cost, total_cost, latency_ms, ttfa_ms) "
            "VALUES (:id, :sk, :sid, :ch, :intent, :persona, :page, :cache, :asr_ms, "
            " :tts_chars, :fi, :fo, :ti, :to, :tc, :asr_cost, :tts_cost, :fast_cost, "
            " :thinker_cost, :tool_cost, :total_cost, :lat, :ttfa)"
        ), {
            "id": uuid.uuid4(), "sk": metrics.site_key, "sid": metrics.session_id,
            "ch": metrics.channel, "intent": metrics.intent, "persona": metrics.persona,
            "page": metrics.page, "cache": metrics.served_from_cache,
            "asr_ms": metrics.asr_ms, "tts_chars": metrics.tts_chars,
            "fi": metrics.fast_in_tok, "fo": metrics.fast_out_tok,
            "ti": metrics.thinker_in_tok, "to": metrics.thinker_out_tok,
            "tc": metrics.tool_calls, "lat": metrics.latency_ms,
            "ttfa": metrics.ttfa_ms, **costs,
        })
        await db.commit()
        from app.observability import metrics as prom
        path = "cached" if metrics.served_from_cache else "fresh"
        prom.TURNS.labels(metrics.channel, path).inc()
        prom.TURN_SECONDS.labels(metrics.channel, path).observe(metrics.latency_ms / 1000.0)
    except Exception as exc:
        logger.warning("usage record failed (site=%s): %s", metrics.site_key, exc)
        try:
            await db.rollback()
        except Exception:
            pass


# ---- analytics aggregation ------------------------------------------------
_BUCKET_SQL = {
    "day": "to_char(date_trunc('day', created_at), 'YYYY-MM-DD')",
    "hour": "to_char(date_trunc('hour', created_at), 'YYYY-MM-DD\"T\"HH24:00')",
    "session": "coalesce(session_id, 'unknown')",
}

_SUMS = (
    "sum(asr_cost) AS asr_cost, sum(tts_cost) AS tts_cost, "
    "sum(fast_cost) AS fast_llm_cost, sum(thinker_cost) AS thinker_llm_cost, "
    "sum(tool_cost) AS tool_cost, sum(total_cost) AS total_cost, "
    "count(*) AS turns, "
    "sum(CASE WHEN served_from_cache THEN 1 ELSE 0 END) AS cached_turns, "
    "sum(CASE WHEN served_from_cache THEN 0 ELSE 1 END) AS generated_turns, "
    "avg(latency_ms) AS avg_latency_ms"
)


def _round_row(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if v is None:
            out[k] = 0
        elif k.endswith("_cost"):
            out[k] = round(float(v), 6)
        elif k.endswith("latency_ms"):
            out[k] = round(float(v), 1)
        else:
            out[k] = int(v) if isinstance(v, (int, float)) and float(v).is_integer() else v
    return out


def _ms(v) -> Optional[float]:
    return None if v is None else round(float(v), 1)


async def analytics(
    db: AsyncSession, *, site_key: str, group_by: str = "day",
    frm: Optional[datetime] = None, to: Optional[datetime] = None,
) -> dict:
    """Cost/performance rollup for one site. ``group_by`` ∈ {day, hour, session}."""
    bucket = _BUCKET_SQL.get(group_by, _BUCKET_SQL["day"])
    where = "site_key = :sk"
    params: dict = {"sk": site_key}
    if frm is not None:
        where += " AND created_at >= :frm"; params["frm"] = frm
    if to is not None:
        where += " AND created_at < :to"; params["to"] = to

    # Time series grouped by the chosen bucket.
    series_res = await db.execute(text(
        f"SELECT {bucket} AS bucket, {_SUMS} FROM usage_events WHERE {where} "
        f"GROUP BY bucket ORDER BY bucket"
    ), params)
    series = [_round_row(dict(r)) for r in series_res.mappings().all()]

    # Range totals + latency percentiles + cache split.
    tot_res = await db.execute(text(
        f"SELECT {_SUMS}, "
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms, "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms, "
        "count(ttfa_ms) AS ttfa_turns, "
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY ttfa_ms) AS p50_ttfa_ms, "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY ttfa_ms) AS p95_ttfa_ms, "
        "coalesce(sum(total_cost) FILTER (WHERE served_from_cache), 0) AS cached_cost, "
        "coalesce(sum(total_cost) FILTER (WHERE NOT served_from_cache), 0) AS generated_cost "
        f"FROM usage_events WHERE {where}"
    ), params)
    tot = dict(tot_res.mappings().first() or {})
    totals = _round_row({k: tot.get(k) for k in (
        "asr_cost", "tts_cost", "fast_llm_cost", "thinker_llm_cost", "tool_cost",
        "total_cost", "turns", "cached_turns", "generated_turns", "avg_latency_ms",
    )})
    turns = totals["turns"] or 0
    cached = totals["cached_turns"] or 0
    performance = {
        "turns": turns,
        "avg_latency_ms": totals["avg_latency_ms"],
        "p50_latency_ms": round(float(tot.get("p50_latency_ms") or 0), 1),
        "p95_latency_ms": round(float(tot.get("p95_latency_ms") or 0), 1),
        "cache_hit_rate": round(cached / turns, 4) if turns else 0.0,
        # Time to first audio over spoken voice turns (null when there were none).
        "ttfa_turns": int(tot.get("ttfa_turns") or 0),
        "p50_ttfa_ms": _ms(tot.get("p50_ttfa_ms")),
        "p95_ttfa_ms": _ms(tot.get("p95_ttfa_ms")),
    }
    cache_split = {
        "cached": {"turns": cached, "cost": round(float(tot.get("cached_cost") or 0), 6)},
        "generated": {
            "turns": totals["generated_turns"] or 0,
            "cost": round(float(tot.get("generated_cost") or 0), 6),
        },
    }
    return {
        "site_key": site_key,
        "group_by": group_by,
        "series": series,
        "totals": totals,
        "performance": performance,
        "cache_split": cache_split,
        "pricing": get_pricing().to_dict(),
    }
