"""
Lift of the agent over the holdout, with confidence intervals (WS11).

Each arm is a proportion: visitors who reached the site's goal / visitors
assigned. The headline is the absolute difference in conversion rate with a
95 % Newcombe hybrid-score interval (built from each arm's Wilson interval),
which behaves well with the small counts and rare conversions an early
experiment has. Relative lift gets a log-scale interval, and a pooled
two-proportion z-test gives the p-value.

Those are fixed-horizon numbers: they are only right if the test is read once,
at a size chosen in advance. People watch the dashboard every day and stop when
it turns green, which makes a false "win" far likelier than 5 %. So the verdict
comes from an **always-valid** interval (the mixture sequential probability
ratio test, mSPRT — Johari et al., "Always Valid Inference", 2017): it holds at
whatever moment the test is read or stopped. It is wider than the fixed-horizon
interval; when only the fixed-horizon one excludes zero the result is reported
as ``trending`` ("promising, keep it running"), not as a finding.

``sample_size`` plans how many visitors that verdict needs for a given lift.

Variant tests (M2-4) compare each of 2-4 variants with the control (variant
``a``). Each comparison is a ``lift`` at a split error budget (Bonferroni:
alpha / number of comparisons), so the chance of *any* false winner, however
often the results are read, stays at or under 5 %. ``variant_verdict`` turns
those comparisons into a winner, and ``sample_size_arms`` plans the run.

Standard library only.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Optional

Z95 = 1.959963984540054
# Below this many visitors in either arm, or this few conversions in both
# together, the result is reported as still collecting rather than as a finding
# (the normal approximation the intervals rest on isn't there yet).
MIN_VISITORS_PER_ARM = 30
MIN_CONVERSIONS = 10
ALPHA = 0.05
Z_POWER80 = 0.8416212335729143
# The mSPRT mixing scale, in conversion-rate points: the size of effect the
# test is tuned to find quickest. Any value keeps the guarantee; one far too
# small costs a lot of power, one too large only a little (it enters through a
# logarithm), so it errs large: 5 points.
SEQ_TAU = 0.05


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


def _pooled_variance(x1: int, n1: int, x2: int, n2: int) -> float:
    """Variance of p1 - p2 from the pooled rate. The per-arm (unpooled)
    estimate is far too small when a small holdout has few conversions, which
    in simulation let 31 % of no-effect tests "win" at a 2 % conversion rate;
    pooled, it stays at or under 5 %."""
    pooled = (x1 + x2) / (n1 + n2)
    return pooled * (1 - pooled) * (1 / n1 + 1 / n2)


def seq_half_width(var: float, alpha: float = ALPHA, tau: float = SEQ_TAU) -> float:
    """Half-width of the mSPRT always-valid interval for a difference whose
    estimate has variance ``var``."""
    t2 = tau * tau
    return math.sqrt(var * (var + t2) / t2 * (2 * math.log(1 / alpha) + math.log((var + t2) / var)))


def sequential_diff(x1: int, n1: int, x2: int, n2: int, alpha: float = ALPHA,
                    tau: float = SEQ_TAU) -> Optional[tuple[float, float, float]]:
    """``(low, high, p)``: the always-valid interval for p1 - p2 and the
    always-valid p-value (1 / the mixture likelihood ratio against "no
    difference"), or None while the variance is zero (no conversions yet, or
    everyone converted)."""
    if n1 <= 0 or n2 <= 0:
        return None
    var = _pooled_variance(x1, n1, x2, n2)
    if var <= 0:
        return None
    d = x1 / n1 - x2 / n2
    h = seq_half_width(var, alpha, tau)
    t2 = tau * tau
    log_lr = 0.5 * math.log(var / (var + t2)) + t2 * d * d / (2 * var * (var + t2))
    p = 1.0 if log_lr <= 0 else min(1.0, math.exp(-log_lr))
    return d - h, d + h, p


def sample_size(baseline: float, relative_mde: float, holdout_share: float,
                power_z: float = Z_POWER80, alpha: float = ALPHA,
                tau: float = SEQ_TAU) -> Optional[dict]:
    """Visitors needed (both arms together) for the always-valid interval to
    exclude zero with 80 % power, when the agent lifts a ``baseline``
    conversion rate by ``relative_mde`` (0.2 = +20 %). None when the inputs
    make no sense (a rate at or past 0 or 1)."""
    p_h = baseline
    p_a = baseline * (1 + relative_mde)
    if not (0 < p_h < 1 and 0 < p_a < 1 and 0 < holdout_share < 1) or p_a == p_h:
        return None
    delta = abs(p_a - p_h)

    pooled = holdout_share * p_h + (1 - holdout_share) * p_a

    def enough(total: float) -> bool:
        n_h, n_a = total * holdout_share, total * (1 - holdout_share)
        test_var = pooled * (1 - pooled) * (1 / n_a + 1 / n_h)   # what the verdict uses
        spread = p_a * (1 - p_a) / n_a + p_h * (1 - p_h) / n_h   # how the estimate varies
        return delta >= seq_half_width(test_var, alpha, tau) + power_z * math.sqrt(spread)

    lo, hi = 2.0, 2.0
    while not enough(hi):
        hi *= 2
        if hi > 1e10:
            return None
    while hi - lo > 1:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if enough(mid) else (mid, hi)
    total = math.ceil(hi)
    holdout = math.ceil(total * holdout_share)
    return {"total": total, "holdout": holdout, "agent": total - holdout}


@dataclass
class Arm:
    visitors: int
    converters: int
    rate: float
    rate_low: float
    rate_high: float


@dataclass
class Lift:
    # collecting | significant (always-valid interval excludes 0) |
    # trending (only the fixed-horizon one does: keep running) | not_significant
    status: str
    agent: Arm
    holdout: Arm
    diff: Optional[float] = None          # absolute, in rate points (0.012 = 1.2 pts)
    diff_low: Optional[float] = None
    diff_high: Optional[float] = None
    relative: Optional[float] = None      # 0.25 = +25 %
    relative_low: Optional[float] = None
    relative_high: Optional[float] = None
    p_value: Optional[float] = None
    # Always-valid (mSPRT) interval and p-value: safe to read at any time.
    seq_low: Optional[float] = None
    seq_high: Optional[float] = None
    seq_p_value: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _arm(x: int, n: int) -> Arm:
    lo, hi = wilson(x, n)
    return Arm(visitors=n, converters=x, rate=x / n if n else 0.0, rate_low=lo, rate_high=hi)


def lift(agent_x: int, agent_n: int, hold_x: int, hold_n: int, alpha: float = ALPHA) -> Lift:
    """``agent`` vs ``holdout`` (or a variant vs the control). ``alpha`` is the
    always-valid interval's error budget; a split one widens it."""
    out = Lift(status="collecting", agent=_arm(agent_x, agent_n), holdout=_arm(hold_x, hold_n))
    if agent_n == 0 or hold_n == 0:
        return out
    out.diff, out.diff_low, out.diff_high = newcombe_diff(agent_x, agent_n, hold_x, hold_n)
    rel = relative_lift(agent_x, agent_n, hold_x, hold_n)
    if rel:
        out.relative, out.relative_low, out.relative_high = rel
    out.p_value = two_proportion_p(agent_x, agent_n, hold_x, hold_n)
    seq = sequential_diff(agent_x, agent_n, hold_x, hold_n, alpha=alpha)
    if seq:
        out.seq_low, out.seq_high, out.seq_p_value = seq
    if min(agent_n, hold_n) < MIN_VISITORS_PER_ARM or agent_x + hold_x < MIN_CONVERSIONS:
        return out
    if seq and (out.seq_low > 0 or out.seq_high < 0):
        out.status = "significant"
    elif out.diff_low > 0 or out.diff_high < 0:
        out.status = "trending"
    else:
        out.status = "not_significant"
    return out


# ---- variant tests (M2-4) -------------------------------------------------------

def split_alpha(arms: int, alpha: float = ALPHA) -> float:
    """The error budget of each variant-vs-control comparison."""
    return alpha / max(1, arms - 1)


def sample_size_arms(baseline: float, relative_mde: float, arms: int,
                     holdout_share: float = 0.0) -> Optional[dict]:
    """Visitors needed (all arms, holdout included) for each variant-vs-control
    comparison to find a ``relative_mde`` lift at the split error budget with
    80 % power. Variants share the non-holdout traffic equally."""
    if arms < 2 or not 0 <= holdout_share < 1:
        return None
    pair = sample_size(baseline, relative_mde, 0.5, alpha=split_alpha(arms))
    if pair is None:
        return None
    per_arm = math.ceil(pair["total"] / 2)
    total = math.ceil(per_arm * arms / (1 - holdout_share))
    return {"total": total, "per_variant": per_arm, "holdout": total - per_arm * arms}


def variant_verdict(arms: list[tuple[str, int, int]], plan_reached: bool = False) -> dict:
    """``arms``: ``[(key, visitors, converters)]``, the control first. Returns
    each variant's comparison with the control and the run's verdict:

    * ``winner`` — a variant beat the control with the always-valid interval
      at the split budget (the best such one), or the control beat every
      variant;
    * ``no_difference`` — the planned sample is in and nothing separated;
    * ``keep_running`` — otherwise.
    """
    (ck, cn, cx), rest = arms[0], arms[1:]
    alpha = split_alpha(len(arms))
    comparisons: dict[str, dict] = {}
    better: list[tuple[float, str]] = []
    worse = 0
    for key, n, x in rest:
        cmp_ = lift(x, n, cx, cn, alpha=alpha)
        comparisons[key] = cmp_.to_dict()
        if cmp_.status == "significant":
            if (cmp_.diff or 0) > 0:
                better.append((x / n if n else 0.0, key))
            else:
                worse += 1
    if better:
        status, winner = "winner", max(better)[1]
    elif rest and worse == len(rest):
        status, winner = "winner", ck
    elif plan_reached:
        status, winner = "no_difference", None
    else:
        status, winner = "keep_running", None
    return {"status": status, "winner": winner, "alpha": alpha, "comparisons": comparisons}
