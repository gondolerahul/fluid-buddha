"""
Hindi retrieval check (M2-7), with the real models.

The knowledge base is English. A question asked in Hindi (Devanagari) or
Hinglish (Hindi in Latin letters) should find the same passage as the English
question. This scores, on a labelled set (evals/hindi/), how often the right
passage is the first hit and in the top three for:

  en              the English question (the upper bound)
  hi / hinglish   the question as asked, embedded directly
  hi→en / hgl→en  the English query the fast router writes (what the agent
                  searches with; same model call as the spoken acknowledgement)

and, for comparison, the raw questions against the multilingual embedding
model (the alternative the plan mentions; it would mean re-embedding every
site's knowledge).

Needs Vertex AI (GOOGLE_CLOUD_PROJECT + credentials). Costs a few cents.

    cd backend && python -m evals.hindi_retrieval
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ["MOCK_AI"] = "false"

from app.config import get_settings  # noqa: E402
from app.i18n.detect import detect  # noqa: E402
from app.orchestrator.router import FastRouter  # noqa: E402

HERE = Path(__file__).parent / "hindi"
MULTILINGUAL = "text-multilingual-embedding-002"


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)


def _rank(q: list[float], docs: list[tuple[str, list[float]]]) -> list[str]:
    return [i for i, _ in sorted(docs, key=lambda d: -_cos(q, d[1]))]


async def _embed(embedder, texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):
        out.extend(await embedder.embed_texts(texts[i:i + 100]))
    return out


async def main() -> int:
    from app.ai.vertex import VertexEmbedder, VertexLLMClient

    settings = get_settings()
    if not settings.google_cloud_project:
        print("GOOGLE_CLOUD_PROJECT is not set: this check needs Vertex AI.")
        return 2
    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    try:   # fail fast and plainly (the router would otherwise fall back silently)
        await VertexEmbedder(settings).embed_texts(["ping"])
    except Exception as exc:
        print(f"Vertex AI is not reachable: {type(exc).__name__}: {str(exc)[:200]}")
        return 2
    router = FastRouter(VertexLLMClient(settings), settings)

    # The router's English queries (timed: this is the added work on a turn).
    translated: dict[tuple[int, str], str] = {}
    took: list[float] = []
    for n, q in enumerate(questions):
        for form in ("hi", "hinglish"):
            seen = detect(q[form])
            t0 = time.monotonic()
            r = await router.route(q[form], (), "eval-hindi", lang="hi" if seen == "hi" else "en",
                                   seen=seen)
            took.append(time.monotonic() - t0)
            translated[(n, form)] = r.query_en or q[form]

    results: dict[str, dict[str, float]] = {}
    for model in (settings.embed_model, MULTILINGUAL):
        os.environ["EMBED_MODEL"] = model
        get_settings.cache_clear()
        embedder = VertexEmbedder(get_settings())
        docs = list(zip([d["id"] for d in corpus],
                        await _embed(embedder, [f"{d['title']}. {d['text']}" for d in corpus])))
        variants = {"en": [q["en"] for q in questions], "hi": [q["hi"] for q in questions],
                    "hinglish": [q["hinglish"] for q in questions]}
        if model == settings.embed_model:
            variants["hi→en"] = [translated[(n, "hi")] for n in range(len(questions))]
            variants["hgl→en"] = [translated[(n, "hinglish")] for n in range(len(questions))]
        for name, texts in variants.items():
            vecs = await _embed(embedder, texts)
            ranks = [_rank(v, docs) for v in vecs]
            at1 = sum(r[0] == q["target"] for r, q in zip(ranks, questions)) / len(questions)
            at3 = sum(q["target"] in r[:3] for r, q in zip(ranks, questions)) / len(questions)
            results[f"{model} · {name}"] = {"hit@1": round(at1, 3), "hit@3": round(at3, 3)}
    os.environ.pop("EMBED_MODEL", None)
    get_settings.cache_clear()

    width = max(len(k) for k in results)
    print(f"{'query (embedding model · form)':<{width}}  hit@1  hit@3")
    for k, v in results.items():
        print(f"{k:<{width}}  {v['hit@1']:.2f}   {v['hit@3']:.2f}")
    took.sort()
    print(f"\nrouter call with the English query: median {took[len(took) // 2]:.2f}s, "
          f"max {took[-1]:.2f}s ({len(took)} calls)")
    print("\nrouter's English queries:")
    for n, q in enumerate(questions):
        print(f"  {q['hi']}  →  {translated[(n, 'hi')]}")
        print(f"  {q['hinglish']}  →  {translated[(n, 'hinglish')]}")
    (HERE / "results.json").write_text(json.dumps({
        "questions": len(questions), "passages": len(corpus), "scores": results,
        "router_seconds": {"median": round(took[len(took) // 2], 2), "max": round(took[-1], 2)},
        "queries": {f"{n}:{form}": translated[(n, form)] for (n, form) in translated},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
