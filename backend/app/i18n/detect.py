"""
Which language a visitor is using, and which one to answer in (M2-7).

Detection is by script first: Devanagari letters mean Hindi. Hindi typed in
Latin letters ("pricing kya hai?") is *Hinglish*, spotted by common Hindi words
that don't occur in English. No model call, so it adds nothing to a turn.

The reply language (``choose``):

1. A site that hasn't switched Hindi on always answers in English.
2. "Reply in Hindi" / "English please" (in either language) sets the
   visitor's preference for the rest of the conversation.
3. A question in Devanagari is answered in Hindi; one in plain English, in
   English (unless the visitor asked for Hindi).
4. Hinglish gets a Hindi-friendly English answer, unless the visitor prefers
   Hindi: they asked for it, their widget is in Hindi, or they have written in
   Devanagari earlier in the conversation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional

LANGS = ("en", "hi")
UI_LANGS = ("auto", "en", "hi")

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_LATIN = re.compile(r"[A-Za-z]")
_WORD = re.compile(r"[A-Za-z]+")

# Romanised Hindi words that are not also common English words ("the", "me",
# "to", "hi", "main", "do" and the like are left out on purpose).
_HINGLISH = frozenset("""
hai hain kya kyaa kaise kaisa kaisi kitna kitne kitni nahi nahin mujhe mujhko
humein hume hamein aap aapka aapke aapki apna apne apni mera meri mere tum tumhara
yeh ye woh wo kaun kab kahan kahaan kyun kyon kyunki chahiye chahte chahta chahti
batao bataiye bataye bataen samjhao samjhaiye dikhao dikhaiye karna karta
karte karti karo kariye karein karenge hoga hogi honge raha rahe rahi sakta sakte
sakti wala wale wali accha acha achha theek thik bahut bohot zyada jyada kuch kuchh
sabse lekin aur bhi sirf abhi liye mein matlab jaise agar toh tha thi hum hamara
hamare unka unke iska iske uska uske ka ke ki ko se pe wahi yahi bolo boliye chalega
milega milta milti lagega lagta paisa paise daam kimat keemat rupaye rupay saal
mahina mahine hafte kaam logon baat baare sath saath pata
""".split())

# "Reply in Hindi", "hindi mein bolo", "हिंदी में बताइए" — and back to English.
_ASK_HINDI = re.compile(
    r"(\b(in|into)\s+hindi\b|\bhindi\s+(me|mein|mai|main|men)\b|\bhindi\s+please\b|"
    r"\bspeak\s+hindi\b|हिंदी\s*में|हिन्दी\s*में)", re.I)
_ASK_ENGLISH = re.compile(
    r"(\b(in|into)\s+english\b|\benglish\s+(me|mein|mai|main|men)\b|\benglish\s+please\b|"
    r"\bspeak\s+english\b|इंग्लिश\s*में|अंग्रेज़ी\s*में|अंग्रेजी\s*में)", re.I)


def detect(text: str) -> str:
    """'hi' (Devanagari), 'hinglish' (Hindi in Latin letters) or 'en'."""
    text = text or ""
    deva = len(_DEVANAGARI.findall(text))
    latin = len(_LATIN.findall(text))
    if deva and deva >= 0.3 * (deva + latin):
        return "hi"
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return "en"
    hits = sum(1 for w in words if w in _HINGLISH)
    if hits >= 2 and hits / len(words) >= 0.25:
        return "hinglish"
    if hits == 1 and len(words) <= 2:      # "kaise?", "pricing kya"
        return "hinglish"
    return "en"


def asked_for(text: str) -> Optional[str]:
    """The language the visitor explicitly asked to be answered in, if any."""
    if _ASK_HINDI.search(text or ""):
        return "hi"
    if _ASK_ENGLISH.search(text or ""):
        return "en"
    return None


def clean_languages(langs: Iterable[str] | None) -> list[str]:
    """The site's languages: always English, plus Hindi if switched on."""
    picked = {str(x).lower() for x in (langs or [])}
    return [x for x in LANGS if x == "en" or x in picked]


def clean_ui(v: Optional[str]) -> str:
    return v if v in UI_LANGS else "auto"


@dataclass
class Choice:
    reply: str        # 'en' | 'hi': the language to answer in
    seen: str         # 'en' | 'hi' | 'hinglish': what the visitor wrote


def choose(text: str, *, enabled: Iterable[str], pref: Optional[str] = None,
           ui: Optional[str] = None, used_hindi: bool = False) -> tuple[Choice, Optional[str]]:
    """The reply language for ``text``, and the visitor's (possibly updated)
    preference to keep for the next turn."""
    seen = detect(text)
    if "hi" not in clean_languages(enabled):
        return Choice("en", seen), pref
    asked = asked_for(text)
    if asked:
        return Choice(asked, seen), asked
    if seen == "hi":
        return Choice("hi", seen), pref
    if pref in LANGS:
        return Choice(pref, seen), pref
    if seen == "hinglish" and (ui == "hi" or used_hindi):
        return Choice("hi", seen), pref
    return Choice("en", seen), pref


def speech_code(lang: str) -> str:
    """BCP-47 code for speech recognition and synthesis (Indian English/Hindi)."""
    return "hi-IN" if lang == "hi" else "en-IN"
