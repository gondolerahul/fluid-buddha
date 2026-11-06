"""Engine selection based on the MOCK_AI flag."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai.base import ASREngine, LLMClient, TTSEngine
from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class AIEngines:
    llm: LLMClient
    asr: ASREngine
    tts: TTSEngine


def build_engines(settings: Settings) -> AIEngines:
    """The platform's engines; the LLM is wrapped so a website whose account
    brought its own model provider (M3-4) is answered by it."""
    from app.ai.providers import RoutingLLM

    engines = _platform_engines(settings)
    engines.llm = RoutingLLM(engines.llm, settings)
    return engines


def _platform_engines(settings: Settings) -> AIEngines:
    if settings.mock_ai:
        from app.ai.mock import MockASR, MockLLMClient, MockTTS

        logger.warning("MOCK_AI=true — using deterministic stub engines (no Vertex).")
        return AIEngines(
            llm=MockLLMClient(),
            asr=MockASR(),
            tts=MockTTS(sample_rate=settings.tts_sample_rate),
        )

    from app.ai.vertex import GeminiTTS, VertexASR, VertexLLMClient

    logger.info(
        "Using Vertex AI (project=%s, location=%s, tts=%s)",
        settings.google_cloud_project, settings.vertex_location, settings.tts_model,
    )
    return AIEngines(
        llm=VertexLLMClient(settings),
        asr=VertexASR(settings),
        tts=GeminiTTS(settings),
    )
