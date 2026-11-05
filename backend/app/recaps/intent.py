"""
"Send me this" by voice (M2-6 follow-up).

The widget catches a typed request itself; a spoken one arrives here as a
transcript, so the server recognises the same phrases (English, Hindi,
Hinglish — kept in step with ``RECAP_RE`` in fluid-buddha-sdk/src/core/Session.ts)
and tells the widget to make the recap, instead of running an agent turn.
"""
from __future__ import annotations

import re
from typing import Optional

RECAP_RE = re.compile(
    r"\b(send|email|mail|share|give) me (this|that|a (recap|summary|copy)|the (recap|summary|conversation))\b"
    r"|\brecap (link|please)\b|रीकैप|(यह|ये|इसे|इसको)\s*(मुझे\s*)?(भेज|ईमेल)"
    r"|\b(ye|yeh|ise|isko) (mujhe )?(bhej|email|mail)",
    re.IGNORECASE)
# Speech recognisers write an address as "asha at example dot com".
_SPOKEN_EMAIL = re.compile(r"([\w.+-]+)\s+(?:at|@)\s+([\w-]+(?:\s+(?:dot|\.)\s+[\w-]+)+)", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def wants_recap(text: str) -> bool:
    return bool(RECAP_RE.search(text or ""))


def email_in(text: str) -> Optional[str]:
    m = _EMAIL.search(text or "")
    if m:
        return m.group(0)
    m = _SPOKEN_EMAIL.search(text or "")
    if m:
        domain = re.sub(r"\s+(?:dot|\.)\s+", ".", m.group(2), flags=re.IGNORECASE)
        return f"{m.group(1)}@{domain}".lower()
    return None
