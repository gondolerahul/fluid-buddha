"""
Adapters that satisfy cortex_memory's provider Protocols.

cortex injects host concerns (LLM + embeddings) through ``LLMProvider`` and
``EmbeddingProvider``. We give it Gemini-backed implementations in production
and the package's own deterministic reference providers in mock mode.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Optional

from cortex_memory.providers import EmbeddingResult, LLMResult

from app.config import Settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Real (Vertex-backed) cortex providers
# ---------------------------------------------------------------------------

class VertexEmbeddingProvider:
    """cortex EmbeddingProvider backed by Vertex text-embedding-004 (768-dim)."""

    def __init__(self, settings: Settings) -> None:
        from app.ai.vertex import VertexEmbedder

        self._embedder = VertexEmbedder(settings)
        self._model = settings.embed_model

    def dimension(self) -> int:
        return self._embedder.dimension()

    async def embed(
        self, texts: Sequence[str], *, model: Optional[str] = None
    ) -> EmbeddingResult:
        vectors = await self._embedder.embed_texts(list(texts))
        return EmbeddingResult(
            vectors=vectors,
            model=model or self._model,
            char_count=sum(len(t) for t in texts),
            cost_usd=0.0,
        )


class VertexCortexLLM:
    """cortex LLMProvider backed by Gemini (used for navigation summaries)."""

    def __init__(self, settings: Settings) -> None:
        from app.ai.vertex import VertexLLMClient
        from app.ai.base import ChatMessage  # noqa: F401 (typing aid)

        self._client = VertexLLMClient(settings)
        self._model = settings.fast_model

    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        task_type: Optional[str] = None,
    ) -> LLMResult:
        from app.ai.base import ChatMessage

        resp = await self._client.generate(
            system=system,
            messages=[ChatMessage(role="user", text=user)],
            model=model or self._model,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        return LLMResult(text=resp.text, model=resp.model)


# ---------------------------------------------------------------------------
# Container + factory
# ---------------------------------------------------------------------------

@dataclass
class CortexProviders:
    embedding: Any  # cortex EmbeddingProvider
    llm: Any        # cortex LLMProvider


def build_cortex_providers(settings: Settings) -> CortexProviders:
    if settings.mock_ai:
        from cortex_memory.providers_reference import (
            EchoLLMProvider,
            HashEmbeddingProvider,
        )

        # 768-dim hash embeddings match the cortex vector(768) column exactly.
        return CortexProviders(
            embedding=HashEmbeddingProvider(dim=settings.embed_dim),
            llm=EchoLLMProvider(),
        )
    return CortexProviders(
        embedding=VertexEmbeddingProvider(settings),
        llm=VertexCortexLLM(settings),
    )
