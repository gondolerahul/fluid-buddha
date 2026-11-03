"""
Answer citations (WS8): grounding sources are deduplicated per document, carry a
readable label, and link to the site page they came from when it is known.
"""
from __future__ import annotations

from app.cortex.query import citations


def _snip(filename: str, score: float, document: str | None = None, section: str = "S") -> dict:
    return {"text": "t", "score": score, "filename": filename,
            "document": document or f"📄 {filename}", "section": section}


def test_citations_label_route_and_dedupe():
    out = citations([
        _snip("07-pricing.md", 0.91, section="Plans"),
        _snip("07-pricing.md", 0.88, section="FAQ"),        # same document → once
        _snip("product_technical_documentation.md", 0.7),
        _snip("https://acme.example/docs/getting-started/", 0.6),
    ])
    assert [c["label"] for c in out] == [
        "Pricing", "Product technical documentation", "Getting started"]
    assert out[0]["route"] == "/pricing" and out[0]["section"] == "Plans"
    assert "route" not in out[1]                     # no known page for a spec doc
    assert out[2]["route"] == "/docs/getting-started"


def test_citations_fall_back_to_document_title():
    out = citations([{"text": "t", "score": 0.5, "document": "📄 Onboarding notes",
                      "section": None}])
    assert out == [{"document": "📄 Onboarding notes", "section": None, "score": 0.5,
                    "label": "Onboarding notes"}]
