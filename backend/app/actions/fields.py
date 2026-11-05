"""
Action kinds, their settings, and their typed inputs (M2-8).

Every action has a list of input *fields*. Most kinds have fixed fields; a
generic webhook action lets the tenant define its own. The same fields give:

* the tool the agent sees (a JSON schema),
* the server-side check of what the agent passed (``validate_inputs``) — the
  agent's arguments are never trusted, and
* the lines shown to the visitor on the confirmation card (``summary``).

Money is never an input: a payment action's amount comes from the tenant's
price list, picked by a ``plan`` key the agent can only choose from.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from app.leads.store import EMAIL_RE

KINDS = ("payment_link", "quote_request", "trial", "meeting_link", "webhook")
FIELD_TYPES = ("text", "email", "number", "integer", "boolean", "choice")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,30}$")
URL_MAX = 500
MAX_FIELDS = 8
MAX_PRICES = 20
TEXT_MAX = 300
DETAILS_MAX = 1000
BOOKING_STYLES = ("calendly", "cal", "plain")


class ActionConfigError(ValueError):
    """The tenant's action settings are invalid (shown in the console)."""


class InputError(ValueError):
    """The agent's arguments don't fit the action (told back to the model)."""


def _field(key: str, label: str, type_: str = "text", required: bool = False,
           options: Optional[list[str]] = None, max_len: int = TEXT_MAX) -> dict[str, Any]:
    f: dict[str, Any] = {"key": key, "label": label, "type": type_, "required": required}
    if options is not None:
        f["options"] = options
    if type_ == "text":
        f["max"] = max_len
    return f


def fields_for(kind: str, config: dict[str, Any]) -> list[dict[str, Any]]:
    """The inputs an action of ``kind`` takes, given its settings."""
    email = _field("email", "Email", "email", True)
    name = _field("name", "Name")
    if kind == "payment_link":
        plans = [p["key"] for p in config.get("prices") or []]
        return [_field("plan", "Plan", "choice", True, plans), email, name]
    if kind == "quote_request":
        return [email, name, _field("company", "Company"),
                _field("details", "What they need", "text", True, max_len=DETAILS_MAX),
                _field("quantity", "Quantity", "integer")]
    if kind == "trial":
        return [email, name, _field("company", "Company")]
    if kind == "meeting_link":
        return [email, name, _field("topic", "Topic")]
    return list(config.get("fields") or [])


# ---- settings (console) ---------------------------------------------------

def _https(url: Any, what: str) -> str:
    url = str(url or "").strip()
    if not url.startswith("https://") or len(url) > URL_MAX or any(c in url for c in " \"'<>\r\n\t"):
        raise ActionConfigError(f"{what} must be an https:// link")
    return url


def _clean_fields(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_FIELDS:
        raise ActionConfigError(f"a webhook action needs 1 to {MAX_FIELDS} fields")
    out, seen = [], set()
    for f in raw:
        if not isinstance(f, dict):
            raise ActionConfigError("each field needs a key, a label and a type")
        key, type_ = str(f.get("key") or ""), str(f.get("type") or "text")
        if not KEY_RE.match(key) or key in seen:
            raise ActionConfigError(f"field key {key!r}: lowercase letters, digits and _, unique")
        if type_ not in FIELD_TYPES:
            raise ActionConfigError(f"field {key}: type must be one of {', '.join(FIELD_TYPES)}")
        label = " ".join(str(f.get("label") or key).split())[:60]
        options = None
        if type_ == "choice":
            options = [str(o).strip()[:60] for o in f.get("options") or [] if str(o).strip()]
            if not 1 <= len(options) <= 20:
                raise ActionConfigError(f"field {key}: a choice needs 1 to 20 options")
        seen.add(key)
        out.append(_field(key, label, type_, bool(f.get("required")), options,
                          max_len=min(DETAILS_MAX, int(f.get("max") or TEXT_MAX))))
    return out


def clean_config(kind: str, config: Any) -> dict[str, Any]:
    """Check and normalise an action's settings (secrets are kept apart)."""
    if kind not in KINDS:
        raise ActionConfigError(f"kind must be one of {', '.join(KINDS)}")
    c = config if isinstance(config, dict) else {}
    out: dict[str, Any] = {"max_per_hour": max(1, min(500, int(c.get("max_per_hour") or 20)))}
    if kind == "payment_link":
        key_id = str(c.get("key_id") or "").strip()
        if not re.match(r"^rzp_(test|live)_[A-Za-z0-9]{6,40}$", key_id):
            raise ActionConfigError("Razorpay key id looks like rzp_test_… or rzp_live_…")
        prices = c.get("prices")
        if not isinstance(prices, list) or not 1 <= len(prices) <= MAX_PRICES:
            raise ActionConfigError(f"add 1 to {MAX_PRICES} prices")
        clean, keys = [], set()
        for p in prices:
            if not isinstance(p, dict):
                raise ActionConfigError("each price needs a key, a label and an amount")
            key = str(p.get("key") or "")
            if not KEY_RE.match(key) or key in keys:
                raise ActionConfigError(f"price key {key!r}: lowercase letters, digits and _, unique")
            try:
                amount = int(p.get("amount"))
            except (TypeError, ValueError):
                raise ActionConfigError(f"price {key}: the amount is in paise, a whole number")
            if not 100 <= amount <= 50_000_000:
                raise ActionConfigError(f"price {key}: between ₹1 and ₹5,00,000")
            keys.add(key)
            clean.append({"key": key, "label": " ".join(str(p.get("label") or key).split())[:80],
                          "amount": amount, "currency": "INR"})
        out.update(key_id=key_id, prices=clean)
    elif kind == "trial":
        out["url"] = _https(c.get("url"), "The trial webhook")
    elif kind == "webhook":
        out["url"] = _https(c.get("url"), "The webhook")
        out["fields"] = _clean_fields(c.get("fields"))
    elif kind == "meeting_link":
        out["booking_url"] = _https(c.get("booking_url"), "The booking link")
        style = c.get("style") or "plain"
        out["style"] = style if style in BOOKING_STYLES else "plain"
    return out


def clean_name(name: Any) -> str:
    name = str(name or "").strip()
    if not NAME_RE.match(name):
        raise ActionConfigError("name: 2-40 lowercase letters, digits or _, starting with a letter")
    return name


# ---- the agent's arguments ------------------------------------------------

def tool_parameters(fields: list[dict[str, Any]]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for f in fields:
        t = f["type"]
        if t == "choice":
            p: dict[str, Any] = {"type": "string", "enum": list(f.get("options") or [])}
        elif t == "number":
            p = {"type": "number"}
        elif t == "integer":
            p = {"type": "integer"}
        elif t == "boolean":
            p = {"type": "boolean"}
        else:
            p = {"type": "string"}
        p["description"] = f["label"]
        props[f["key"]] = p
    return {"type": "object", "properties": props,
            "required": [f["key"] for f in fields if f.get("required")]}


def validate_inputs(fields: list[dict[str, Any]], args: Any) -> dict[str, Any]:
    """The agent's arguments, checked against the fields; unknown keys dropped."""
    if not isinstance(args, dict):
        raise InputError("arguments must be an object")
    out: dict[str, Any] = {}
    for f in fields:
        key, t = f["key"], f["type"]
        v = args.get(key)
        if v is None or (isinstance(v, str) and not v.strip()):
            if f.get("required"):
                raise InputError(f"{f['label']} is required")
            continue
        if t == "email":
            v = str(v).strip().lower()
            if not EMAIL_RE.match(v):
                raise InputError(f"{f['label']} is not a valid email address")
        elif t == "choice":
            if str(v) not in (f.get("options") or []):
                raise InputError(f"{f['label']} must be one of: {', '.join(f.get('options') or [])}")
            v = str(v)
        elif t in ("number", "integer"):
            if isinstance(v, bool):
                raise InputError(f"{f['label']} must be a number")
            try:
                v = int(v) if t == "integer" else float(v)
            except (TypeError, ValueError):
                raise InputError(f"{f['label']} must be a number")
            if t == "integer" and not 0 <= v <= 1_000_000:
                raise InputError(f"{f['label']} is out of range")
        elif t == "boolean":
            if not isinstance(v, bool):
                raise InputError(f"{f['label']} must be true or false")
        else:
            v = " ".join(str(v).split())
            if len(v) > int(f.get("max") or TEXT_MAX):
                raise InputError(f"{f['label']} is too long")
        out[key] = v
    return out


def price(config: dict[str, Any], plan: str) -> Optional[dict[str, Any]]:
    return next((p for p in config.get("prices") or [] if p["key"] == plan), None)


def rupees(paise: int) -> str:
    """₹14,999 / ₹1,49,999.50 (Indian grouping)."""
    whole, frac = divmod(int(paise), 100)
    s = str(whole)
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join(re.findall(r"\d{1,2}", head[::-1]))[::-1]
        s = f"{head},{tail}"
    return f"₹{s}" + (f".{frac:02d}" if frac else "")


def summary(kind: str, fields: list[dict[str, Any]], config: dict[str, Any],
            inputs: dict[str, Any]) -> list[dict[str, str]]:
    """What the visitor is asked to confirm: each input, and the amount."""
    lines = []
    for f in fields:
        if f["key"] not in inputs:
            continue
        v = inputs[f["key"]]
        if kind == "payment_link" and f["key"] == "plan":
            p = price(config, str(v)) or {}
            lines.append({"label": "Plan", "value": p.get("label") or str(v)})
            lines.append({"label": "Amount", "value": rupees(p.get("amount") or 0)})
            continue
        if isinstance(v, bool):
            v = "Yes" if v else "No"
        lines.append({"label": f["label"], "value": str(v)})
    return lines
