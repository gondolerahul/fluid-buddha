"""
PII masking (WS8): visitor contact and payment details never reach the model or
the database in the clear.

Each conversation keeps a ``PiiVault``. ``mask`` swaps every detected value for a
stable placeholder (``<EMAIL_1>``) before the text goes to the router, the
thinker or the session history; the vault remembers the real value so the one
place that needs it — the ``capture_lead`` tool, saving a lead the visitor asked
for — can ``unmask`` its arguments. Everything shown, spoken or stored uses the
placeholder's plain-language form instead (``spoken``: "your email";
``stored``: "[email]"), so audio caches and transcripts never hold the value.

Detection is pattern based: emails, payment cards (Luhn-checked), US SSNs,
IBANs and phone numbers. Names and street addresses are not detected.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_CARD = re.compile(r"(?<![\w-])\d(?:[ -]?\d){12,18}(?![\w-])")
_SSN = re.compile(r"(?<![\w-])\d{3}-\d{2}-\d{4}(?![\w-])")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b")
_PHONE = re.compile(r"(?<![\w+])\+?\(?\d[\d ().-]{6,18}\d(?![\w-])")

# Detection order matters: a card or SSN would also look like a phone number.
KINDS: tuple[str, ...] = ("email", "card", "ssn", "iban", "phone")
# Never useful to keep anywhere, even in a lead the visitor submitted.
SENSITIVE: frozenset[str] = frozenset({"card", "ssn", "iban"})

_STORED = {"email": "[email]", "card": "[card number]", "ssn": "[id number]",
           "iban": "[bank account]", "phone": "[phone]"}
_SPOKEN = {"email": "your email", "card": "your card number", "ssn": "your ID number",
           "iban": "your bank account number", "phone": "your phone number"}
TOKEN_RE = re.compile(r"<(EMAIL|CARD|SSN|IBAN|PHONE)_(\d+)>", re.IGNORECASE)


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _is_phone(s: str) -> bool:
    digits = re.sub(r"\D", "", s)
    if not 9 <= len(digits) <= 15:
        return False
    if s.startswith("+"):
        return True
    # "100.000.000" is a number, not a phone; a bare 9-digit run is too ambiguous.
    seps = set(re.sub(r"[\d]", "", s))
    if seps <= {"."}:
        return False
    return bool(seps & {" ", "-", "(", ")"}) or len(digits) >= 10


def _matches(text: str, kinds: Iterable[str]) -> list[tuple[int, int, str]]:
    """Non-overlapping (start, end, kind) spans, earlier kinds winning."""
    spans: list[tuple[int, int, str]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= s or a >= e for s, e, _ in spans)

    for kind in KINDS:
        if kind not in kinds:
            continue
        pattern = {"email": _EMAIL, "card": _CARD, "ssn": _SSN,
                   "iban": _IBAN, "phone": _PHONE}[kind]
        for m in pattern.finditer(text):
            value = m.group(0)
            if kind == "card" and not _luhn(re.sub(r"\D", "", value)):
                continue
            if kind == "phone" and not _is_phone(value):
                continue
            if free(m.start(), m.end()):
                spans.append((m.start(), m.end(), kind))
    return sorted(spans)


def redact(text: str | None, kinds: Iterable[str] = KINDS) -> str:
    """Replace raw PII with its storage label — for text that never had a vault."""
    if not text:
        return text or ""
    kinds = set(kinds)
    out, last = [], 0
    for start, end, kind in _matches(text, kinds):
        out.append(text[last:start])
        out.append(_STORED[kind])
        last = end
    out.append(text[last:])
    return "".join(out)


def contains_pii(text: str | None) -> bool:
    return bool(text) and (bool(TOKEN_RE.search(text)) or bool(_matches(text, KINDS)))


class PiiVault:
    """One conversation's placeholders → real values. ``enabled=False`` (a site
    that turned masking off) makes every method a pass-through."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._values: dict[str, str] = {}   # "<EMAIL_1>" -> value
        self._tokens: dict[str, str] = {}   # value -> "<EMAIL_1>"
        self._counts: dict[str, int] = {}

    def to_dict(self) -> dict:
        """For a shared session store (F-3). Holds the real values."""
        return {"enabled": self.enabled, "values": dict(self._values),
                "counts": dict(self._counts)}

    @classmethod
    def from_dict(cls, data: dict) -> "PiiVault":
        vault = cls(enabled=bool(data.get("enabled", True)))
        vault._values = {str(k): str(v) for k, v in (data.get("values") or {}).items()}
        vault._tokens = {v: k for k, v in vault._values.items()}
        vault._counts = {str(k): int(v) for k, v in (data.get("counts") or {}).items()}
        return vault

    def mask(self, text: str) -> str:
        if not (self.enabled and text):
            return text
        out, last = [], 0
        for start, end, kind in _matches(text, KINDS):
            value = text[start:end]
            token = self._tokens.get(value)
            if token is None:
                n = self._counts[kind] = self._counts.get(kind, 0) + 1
                token = f"<{kind.upper()}_{n}>"
                self._tokens[value] = token
                self._values[token] = value
            out.append(text[last:start])
            out.append(token)
            last = end
        out.append(text[last:])
        return "".join(out)

    def unmask(self, text: str) -> str:
        """Placeholders back to real values (only for the lead the visitor gave)."""
        if not (self.enabled and text):
            return text
        return TOKEN_RE.sub(
            lambda m: self._values.get(f"<{m.group(1).upper()}_{m.group(2)}>", m.group(0)),
            text)

    def unmask_args(self, args: dict[str, Any]) -> dict[str, Any]:
        return {k: self.unmask(v) if isinstance(v, str) else v for k, v in args.items()}

    @staticmethod
    def spoken(text: str) -> str:
        """What the visitor hears and sees: "your email", never the placeholder."""
        return TOKEN_RE.sub(lambda m: _SPOKEN[m.group(1).lower()], text or "")

    def stored(self, text: str) -> str:
        """What is written to transcripts and caches. Raw PII that slipped past
        masking (masking off is the tenant's choice, so it is kept) is left alone."""
        out = TOKEN_RE.sub(lambda m: _STORED[m.group(1).lower()], text or "")
        return redact(out) if self.enabled else out
