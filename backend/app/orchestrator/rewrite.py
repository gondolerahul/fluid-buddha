"""
Follow-up query rewriting before retrieval (WS5).

"How much is it?" retrieves nothing useful on its own: its subject is in the
previous turn. Before the lean path searches the knowledge base, a follow-up is
expanded with the visitor's earlier question(s) so retrieval sees the subject.

Follow-ups also depend on their conversation, so they are neither replayed
from nor recorded into the conversation cache (a cached "how much is it?" would
answer about whatever the first visitor was discussing).

Heuristic on purpose: no extra model call, so no added latency on the turn.
"""
from __future__ import annotations

import re
from typing import Sequence

from app.ai.base import ChatMessage

# A short question that leans on what came before: a pronoun or demonstrative
# standing in for the subject, or an opener that continues the last turn.
_REFERS_BACK = re.compile(
    r"\b(it|its|it's|that|that's|this|those|these|they|them|their|theirs|"
    r"same|else|former|latter)\b",
    re.I,
)
_CONTINUES = re.compile(
    r"^\s*(and|but|also|so|or|then|what about|how about|what else|"
    r"tell me more|more|why|why not|how come|really|example|for example|"
    r"such as|like what|which one)\b",
    re.I,
)
_MAX_FOLLOWUP_WORDS = 9
# How many earlier questions may be folded in (the previous one may itself
# have been a follow-up).
_MAX_LOOKBACK = 2


def is_followup(text: str) -> bool:
    words = re.findall(r"[\w'<>]+", text or "")
    if not words or len(words) > _MAX_FOLLOWUP_WORDS:
        return False
    return bool(_CONTINUES.search(text) or _REFERS_BACK.search(text))


def retrieval_query(text: str, history: Sequence[ChatMessage]) -> str:
    """The query to search the knowledge base with for ``text``."""
    if not is_followup(text):
        return text
    earlier: list[str] = []
    for m in reversed(history):
        if m.role != "user" or not (m.text or "").strip():
            continue
        if m.text.startswith("("):  # synthetic turns, e.g. the page welcome
            continue
        earlier.insert(0, m.text.strip())
        if len(earlier) >= _MAX_LOOKBACK or not is_followup(m.text):
            break
    if not earlier:
        return text
    return " ".join(earlier + [text.strip()])


def depends_on_history(text: str, history: Sequence[ChatMessage]) -> bool:
    """True for a follow-up asked mid-conversation: its answer is only right in
    this conversation, so it must not be replayed or cached."""
    return is_followup(text) and any(
        m.role == "user" and not (m.text or "").startswith("(") for m in history
    )
