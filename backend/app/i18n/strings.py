"""
Fixed words the agent says itself (M2-7): the short acknowledgements before a
replayed answer, the fallback acknowledgement, and the fallback answers. The
prompt fragment that makes the model answer in Hindi lives here too.
"""
from __future__ import annotations

_STRINGS: dict[str, dict[str, object]] = {
    "en": {
        "replay_acks": ("Sure.", "Good question.", "Happy to explain."),
        "ack": "Let me look that up for you.",
        "lean_found": "Here's what I can tell you — want me to go deeper on any part?",
        "lean_missing": "I want to get this exactly right — let me connect you with the team.",
        "error": "Something went wrong.",
    },
    "hi": {
        "replay_acks": ("ज़रूर।", "अच्छा सवाल है।", "मैं समझाती हूँ।"),
        "ack": "एक पल, मैं देखती हूँ।",
        "lean_found": "यह रही जानकारी — किसी हिस्से के बारे में और जानना चाहेंगे?",
        "lean_missing": "मैं इसका सही जवाब देना चाहती हूँ — चलिए आपको टीम से जोड़ देती हूँ।",
        "error": "कुछ गड़बड़ हो गई।",
    },
}


def say(key: str, lang: str = "en"):
    table = _STRINGS.get(lang) or _STRINGS["en"]
    return table.get(key, _STRINGS["en"][key])


_HINDI = (
    "LANGUAGE: Answer in natural, conversational Hindi written in Devanagari, the "
    "way people speak it in India. Keep product names, feature names, plan names, "
    "company names, prices, numbers and the titles of sources exactly as they are "
    "written in English (do not translate or transliterate them). Everyday English "
    "words Indians use in Hindi (demo, pricing, team, integration) may stay in "
    "English. Labels inside any component you render stay in English."
)
_HINGLISH = (
    "LANGUAGE: The visitor writes Hindi in Latin letters (Hinglish). Answer in "
    "simple, clear English that an Indian reader finds natural; a short Hindi "
    "phrase is fine, but keep the substance in English."
)


def language_fragment(reply: str, seen: str) -> str:
    """The prompt line for this turn's language ('' for plain English)."""
    if reply == "hi":
        return _HINDI
    if seen == "hinglish":
        return _HINGLISH
    return ""
