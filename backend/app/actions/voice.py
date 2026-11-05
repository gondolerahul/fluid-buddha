"""
Answering an action's confirmation card by voice (M2-8 follow-up).

While a proposal is waiting on the visitor, a short spoken answer — "yes, go
ahead", "confirm", "haan", "ठीक है" or "no", "cancel", "nahin" — presses the
card's button for them. Only short, unambiguous answers count (a longer
sentence goes to the agent as usual), and the confirmation still runs through
the same server path as a click (one run, the price re-checked, audited).
"""
from __future__ import annotations

import re
from typing import Optional

_YES = re.compile(
    r"^(yes|yeah|yep|yup|sure|ok|okay|confirm|confirmed|go ahead|do it|please do|proceed|"
    r"haan|haa|han|ha|ji|ji haan|haan ji|theek hai|thik hai|kar do|karo|"
    r"हाँ|हां|जी|जी हाँ|हाँ जी|ठीक है|कर दो|करो|कन्फर्म)"
    r"( please| ji| go ahead| do it| confirm| kar do| करो| कर दो| please do it)*$")
_NO = re.compile(
    r"^(no|nope|nah|cancel|stop|don't|do not|not now|never mind|nahin|nahi|na|mat karo|rehne do|"
    r"नहीं|ना|मत करो|रहने दो|कैंसल)( thanks| thank you| please| ji| it| for now)*$")


def answer(text: str) -> Optional[bool]:
    """True for a spoken yes, False for a no, None for anything else."""
    t = re.sub(r"[.!?,।]+", " ", (text or "").lower())
    t = re.sub(r"\s+", " ", t).strip()
    if not t or len(t.split()) > 5:
        return None
    if _YES.match(t):
        return True
    if _NO.match(t):
        return False
    return None
