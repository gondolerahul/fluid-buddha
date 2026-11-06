"""
Region-level bandits (P3-6).

Each plan cache key can hold up to ``max_arms`` alternative plans ("arms").
Serving picks one by Thompson sampling on its rewards per pull, with a floor of
uniform exploration (``explore_pct``) so a new arm always gets traffic. A new
arm is built once every existing arm has been served ``MIN_PULLS`` times.
Pinned plans and experiment arms never go through the bandit.
"""
from __future__ import annotations

import random
from typing import Any, Optional

MIN_PULLS = 30


def choose_arm(arms: list[dict[str, Any]], *, explore_pct: int, rng: Optional[random.Random] = None) -> dict[str, Any]:
    rng = rng or random.SystemRandom()
    if len(arms) == 1:
        return arms[0]
    if rng.random() * 100 < explore_pct:
        return rng.choice(arms)
    best, best_score = arms[0], -1.0
    for a in arms:
        pulls = max(0, int(a.get("hit_count") or 0))
        wins = max(0, min(int(a.get("rewards") or 0), pulls))
        score = rng.betavariate(1 + wins, 1 + pulls - wins)
        if score > best_score:
            best, best_score = a, score
    return best


def wants_new_arm(arms: list[dict[str, Any]], max_arms: int, min_pulls: int = MIN_PULLS) -> bool:
    return 0 < len(arms) < max_arms and all(int(a.get("hit_count") or 0) >= min_pulls for a in arms)


def outline(plan: dict[str, Any]) -> list[str]:
    return [f"{r.get('id')}:{r.get('component')}" for r in (plan.get("regions") or []) if isinstance(r, dict)]


def reward_rate(row: dict[str, Any]) -> Optional[float]:
    pulls = int(row.get("hit_count") or 0)
    return round(int(row.get("rewards") or 0) / pulls, 4) if pulls else None
