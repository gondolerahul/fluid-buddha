"""
Central configuration (pydantic-settings).

All runtime knobs come from environment / ``.env``. The single most important
flag is ``MOCK_AI``: when true the orchestrator wires deterministic stub engines
(no Google Cloud needed) so the full stack — DB, ingestion, cognitive loop,
WebSocket transport — runs and is testable locally.
"""
from __future__ import annotations

import uuid
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Namespace used to derive a stable per-site entity UUID from a short site key.
# Deterministic so ingestion and query always resolve to the same knowledge tree.
_SITE_NAMESPACE = uuid.UUID("a2a2a2a2-0000-0000-0000-00000000a2a2")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Runtime ----
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    # :3000 = hirebuddha marketing site; :3001 = fluid-buddha-frontend admin app.
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001"
    )

    # ---- Database ----
    cortex_db_url: str = (
        "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex"
    )

    # ---- AI provider ----
    mock_ai: bool = True
    google_cloud_project: str = ""
    vertex_location: str = "us-central1"
    google_application_credentials: str = ""

    fast_model: str = "gemini-2.5-flash"
    heavy_model: str = "gemini-2.5-pro"
    embed_model: str = "text-embedding-004"
    embed_dim: int = 768  # fixed by the cortex schema — do not change
    asr_language: str = "en-US"
    # TTS: Gemini native TTS (natural prosody) replaces the older Cloud TTS
    # Neural2 voices. ``tts_voice`` is the legacy Cloud TTS voice (kept for the
    # fallback engine); ``tts_gemini_voice`` is a Gemini prebuilt voice name.
    tts_model: str = "gemini-3.1-flash-tts-preview"
    tts_voice: str = "en-US-Neural2-F"
    tts_gemini_voice: str = "Aoede"
    tts_sample_rate: int = 24000

    # ---- CORTEX grounding ----
    cortex_company_id: uuid.UUID = uuid.UUID(
        "11111111-1111-1111-1111-111111111111"
    )
    cortex_confidence_threshold: float = 0.45
    cortex_retrieval_top_k: int = 5

    # ---- Tenant auth (admin dashboard: register/login with JWT bearer) ----
    # Override JWT_SECRET in production — the default is for local/dev only.
    jwt_secret: str = "dev-fluid-buddha-secret-change-me-in-production-0001"
    jwt_algorithm: str = "HS256"
    jwt_expire_min: int = 60 * 24 * 7  # access token lifetime (7 days)

    # ---- Sync / UX ----
    ui_filler_delay_ms: int = 1500

    # ---- Conversation cache (episodic replay) ----
    # Records every turn (transcript + answer + components + actions) per-persona
    # and, once enough data exists, replays a close match instead of re-thinking.
    # See app/cortex/episodic.py + app/transport/answer_audio.py.
    conversation_cache_enabled: bool = True   # record + replay turns
    episodic_memory_enabled: bool = True      # best-effort CORTEX episode side-record
    audio_cache_enabled: bool = True          # persist + replay agent TTS PCM bytes
    # Cosine similarity gates for the hybrid replay (an exact normalised-question
    # match always scores 1.0 and replays verbatim regardless of these):
    episodic_replay_threshold: float = 0.92   # >= this -> replay the cached answer
    episodic_context_threshold: float = 0.70  # >= this -> inject as grounding context
    episodic_min_episodes: int = 20           # need this many cached turns before replay
    episodic_top_k: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# ---------------------------------------------------------------------------
# Site registry — one knowledge-tree "entity" per target website.
# The framework targets 4 sites (1 company + 3 products). Each has its own
# isolated memory scope so the agent never leaks one product's facts into
# another's conversation.
# ---------------------------------------------------------------------------
SITE_KEYS = ("hirebuddha", "buddha-cognitive-lab", "fluidbuddha", "chantingbuddha")


def site_entity_id(site_key: str) -> uuid.UUID:
    """Deterministic entity UUID for a site's knowledge tree."""
    return uuid.uuid5(_SITE_NAMESPACE, site_key)


def vertex_model_id(name: str) -> str:
    """Normalize a model id for the Vertex ``google-genai`` SDK.

    Accepts gateway-style ids like ``google/gemini-3.1-flash-lite`` (as used in
    some ``.env`` files) and returns the bare ``gemini-3.1-flash-lite`` the SDK
    expects — it prepends ``publishers/google/models/`` itself, so a literal
    ``google/`` prefix would 404.
    """
    return name.split("/", 1)[1] if name.startswith("google/") else name


@lru_cache
def get_settings() -> Settings:
    return Settings()
