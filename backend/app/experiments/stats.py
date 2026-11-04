"""
Lift of the agent over the holdout, with confidence intervals (WS11).

Each arm is a proportion: visitors who reached the site's goal / visitors
assigned. The headline is the absolute difference in conversion rate with a
95 % Newcombe hybrid-score interval (built from each arm's Wilson interval),
which behaves well with the small counts and rare conversions an early
experiment has. Relative lift gets a log-scale interval, and a pooled
two-proportion z-test gives the p-value.

Standard library only.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Optional

Z95 = 1.959963984540054
# Below this many visitors in either arm, or with no conversions at all, the
# result is reported as still collecting rather than as a finding.
MIN_VISITORS_PER_ARM = 30


def wilson(x: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = x / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def newcombe_diff(x1: int, n1: int, x2: int, n2: int) -> tuple[float, float, float]:
    """``(p1 - p2, low, high)``: Newcombe's hybrid score interval (method 10)."""
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1)
    l2, u2 = wilson(x2, n2)
    d = p1 - p2
    low = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    high = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, low, high


def relative_lift(x1: int, n1: int, x2: int, n2: int) -> Optional[tuple[float, float, float]]:
    """``(lift, low, high)`` for p1/p2 - 1, or None when either arm has no
    conversions (the ratio is undefined or unbounded)."""
    if x1 == 0 or x2 == 0:
        return None
    p1, p2 = x1 / n1, x2 / n2
    log_rr = math.log(p1 / p2)
    se = math.sqrt((1 - p1) / x1 + (1 - p2) / x2)
    return (p1 / p2 - 1, math.exp(log_rr - Z95 * se) - 1, math.exp(log_rr + Z95 * se) - 1)


def two_proportion_p(x1: int, n1: int, x2: int, n2: int) -> Optional[float]:
    """Two-sided p-value of the pooled z-test; None when it is undefined."""
    pooled = (x1 + x2) / (n1 + n2)
    var = pooled * (1 - pooled) * (1 / n1 + 1 / n2)
    if var <= 0:
        return None
    z = (x1 / n1 - x2 / n2) / math.sqrt(var)
    return math.erfc(abs(z) / math.sqrt(2))


@dataclass
class Arm:
    visitors: int
    converters: int
    rate: float
    rate_low: float
    rate_high: float


@dataclass
class Lift:
    status: str              # collecting | significant | not_significant
    agent: Arm
    holdout: Arm
    diff: Optional[float] = None          # absolute, in rate points (0.012 = 1.2 pts)
    diff_low: Optional[float] = None
    diff_high: Optional[float] = None
    relative: Optional[float] = None      # 0.25 = +25 %
    relative_low: Optional[float] = None
    relative_high: Optional[float] = None
    p_value: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _arm(x: int, n: int) -> Arm:
    lo, hi = wilson(x, n)
    return Arm(visitors=n, converters=x, rate=x / n if n else 0.0, rate_low=lo, rate_high=hi)


def lift(agent_x: int, agent_n: int, hold_x: int, hold_n: int) -> Lift:
    out = Lift(status="collecting", agent=_arm(agent_x, agent_n), holdout=_arm(hold_x, hold_n))
    if agent_n == 0 or hold_n == 0:
        return out
    out.diff, out.diff_low, out.diff_high = newcombe_diff(agent_x, agent_n, hold_x, hold_n)
    rel = relative_lift(agent_x, agent_n, hold_x, hold_n)
    if rel:
        out.relative, out.relative_low, out.relative_high = rel
    out.p_value = two_proportion_p(agent_x, agent_n, hold_x, hold_n)
    if min(agent_n, hold_n) < MIN_VISITORS_PER_ARM or agent_x + hold_x == 0:
        return out
    out.status = ("significant" if out.diff_low > 0 or out.diff_high < 0
                  else "not_significant")
    return out
