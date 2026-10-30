"""Process-wide singletons, built once at startup and stored on app.state."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import AIEngines, build_engines
from app.config import Settings, get_settings
from app.cortex.bridge import CortexBridge
from app.cortex.episodic import EpisodicCache
from app.cortex.providers import CortexProviders, build_cortex_providers
from app.orchestrator.loop import CognitiveLoop
from app.transport.answer_audio import AnswerAudioCache


@dataclass
class Runtime:
    settings: Settings
    engines: AIEngines
    providers: CortexProviders
    loop: CognitiveLoop

    def bridge(self, session: AsyncSession, site_key: str = "hirebuddha") -> CortexBridge:
        return CortexBridge(session, self.settings, self.providers, site_key=site_key)

    def episodic(self, session: AsyncSession, site_key: str = "hirebuddha") -> EpisodicCache:
        """Conversation cache (record + hybrid replay) for a site."""
        return EpisodicCache(session, self.settings, self.providers, site_key=site_key)

    def audio_cache(self, session: AsyncSession) -> AnswerAudioCache:
        """Byte-exact agent-TTS audio cache."""
        return AnswerAudioCache(session, self.settings)


def build_runtime() -> Runtime:
    settings = get_settings()
    engines = build_engines(settings)
    providers = build_cortex_providers(settings)
    loop = CognitiveLoop(engines, settings)
    return Runtime(settings=settings, engines=engines, providers=providers, loop=loop)
