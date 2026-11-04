"""
The plan catalog (WS12).

A plan is a monthly price for a number of included **conversations** (a
visitor session with at least one answered turn, across all of an account's
websites), plus a price per conversation beyond that. Free has a hard cap;
paid plans keep answering and bill the overage on the next invoice.
Enterprise is arranged by hand (no self-serve checkout).

Amounts are in the currency's minor unit (cents, paise). The defaults below
are in USD; ``BILLING_CURRENCY`` and ``BILLING_CATALOG`` (JSON, same shape as
``DEFAULT_CATALOG``, merged per plan) override them — e.g. INR prices for a
Razorpay account without international payments.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Optional

PAID_PLANS = ("growth", "scale")


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    price: int                 # per month, minor units; 0 = free / by arrangement
    included: Optional[int]    # conversations a month; None = unlimited
    overage: Optional[int]     # minor units per extra conversation; None = hard cap
    self_serve: bool

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_CATALOG: dict[str, dict] = {
    "free":       {"name": "Free",       "price": 0,       "included": 100,   "overage": None, "self_serve": True},
    "growth":     {"name": "Growth",     "price": 39_900,  "included": 2_000, "overage": 20,   "self_serve": True},
    "scale":      {"name": "Scale",      "price": 149_900, "included": 10_000, "overage": 12,  "self_serve": True},
    "enterprise": {"name": "Enterprise", "price": 0,       "included": None,  "overage": None, "self_serve": False},
}


def catalog(settings=None) -> dict[str, Plan]:
    if settings is None:
        from app.config import get_settings
        settings = get_settings()
    merged = {k: dict(v) for k, v in DEFAULT_CATALOG.items()}
    raw = (getattr(settings, "billing_catalog", "") or "").strip()
    if raw:
        overrides = json.loads(raw)
        for key, fields in overrides.items():
            if key in merged and isinstance(fields, dict):
                merged[key].update(fields)
    return {k: Plan(key=k, **v) for k, v in merged.items()}


def plan(key: str, settings=None) -> Plan:
    return catalog(settings).get(key) or catalog(settings)["free"]


def currency(settings=None) -> str:
    if settings is None:
        from app.config import get_settings
        settings = get_settings()
    return (settings.billing_currency or "USD").upper()


def overage_amount(p: Plan, conversations: int) -> tuple[int, int]:
    """``(extra conversations, amount in minor units)`` for one period."""
    if p.included is None or p.overage is None:
        return 0, 0
    extra = max(0, conversations - p.included)
    return extra, extra * p.overage
