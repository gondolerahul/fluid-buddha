"""
Medical safety (M2-9): for a site in ``safety: medical`` mode (the Healthcare
template), questions asking for medical advice — a diagnosis, a treatment, a
medicine or a dose — get a fixed, polite refusal with an offer to book an
appointment, and anything that sounds like an emergency gets the emergency
numbers. Both are answered *before* any model call, so no prompt can talk the
agent into advice, and neither is cached or replayed.

Rules, not a model: they're predictable and testable (English, Hindi and
Hinglish), and erring towards a refusal is the safe side here. The prompt
carries the same rules for everything the patterns don't catch.
"""
from __future__ import annotations

import re
from typing import Optional

_I = re.IGNORECASE

# Sounds like an emergency: point to 112 / 108 straight away.
_URGENT = re.compile(
    r"\b(chest pain|heart attack|can'?t breathe|cannot breathe|difficulty breathing|"
    r"short(ness)? of breath|stroke|unconscious|passed out|fainted|not breathing|"
    r"severe(ly)? bleeding|bleeding (a lot|heavily|won'?t stop)|seizure|convulsion|"
    r"overdose|poison(ed|ing)?|suicid\w*|kill (myself|himself|herself)|end my life|self[- ]harm|"
    r"seene (me|mein|mai) dard|saans nahi|saans lene me|behosh)\b"
    r"|सीने में दर्द|छाती में दर्द|साँस नहीं|सांस नहीं|साँस लेने में|बेहोश|आत्महत्या|दौरा पड़|खून बह",
    _I)

# Asks for advice a doctor must give: doses, medicines, diagnoses, treatment.
_ADVICE = re.compile(
    r"\b(dos(e|age|ing)|how (much|many) (mg|ml|tablets?|pills?|capsules?|drops)|"
    r"\d+\s?(mg|ml)\b|(should|can|could) i (take|give|stop|increase|double)|"
    r"what (medicine|medication|tablet|drug|antibiotic)s?|which (medicine|medication|tablet|drug|antibiotic)s?|"
    r"(medicine|medication|tablet|cure|remedy) for|how (do|can|should) i treat|"
    r"diagnos\w*|do i have (an? )?(disease|infection|cancer|diabetes|fever|covid|\w+itis)|"
    r"is it (cancer|serious|normal)|what('?s| is) wrong with me|"
    r"prescri\w*|side effects? of|paracetamol|ibuprofen|antibiotic|insulin|"
    r"kitni (goli|dawa|dawai)|kaunsi (dawa|dawai|goli)|kya (dawa|dawai) (lu|loon|le)|"
    r"dawa kitni|ilaj kya)\b"
    r"|खुराक|कितनी गोली|कितनी दवा|दवा कितनी|कौन सी दवा|कौनसी दवा|कौन सी गोली|क्या दवा|इलाज क्या|"
    r"इलाज बताइए|निदान|मुझे क्या बीमारी",
    _I)

_SAY = {
    "en": {
        "urgent": ("This sounds like it could be an emergency. Please call 112 now (ambulance: 108) "
                   "or go to the nearest emergency department. I can't help with this here."),
        "advice": ("I'm sorry, I can't give medical advice, diagnoses or medicine doses — a doctor "
                   "needs to look at that. I can help you find the right doctor or book an appointment."),
    },
    "hi": {
        "urgent": ("यह आपात स्थिति लग रही है। कृपया अभी 112 पर कॉल करें (एम्बुलेंस: 108) या सबसे पास "
                   "के इमरजेंसी विभाग में जाएँ। मैं यहाँ इसमें मदद नहीं कर सकती।"),
        "advice": ("माफ़ कीजिए, मैं इलाज की सलाह, बीमारी की पहचान या दवा की खुराक नहीं बता सकती — यह "
                   "डॉक्टर ही बता सकते हैं। मैं सही डॉक्टर ढूँढने या अपॉइंटमेंट बुक करने में मदद कर सकती हूँ।"),
    },
}


def check(text: str) -> Optional[str]:
    """'urgent', 'advice', or None (fine to answer)."""
    text = text or ""
    if _URGENT.search(text):
        return "urgent"
    if _ADVICE.search(text):
        return "advice"
    return None


def reply(verdict: str, lang: str = "en") -> str:
    return (_SAY.get(lang) or _SAY["en"])[verdict]
