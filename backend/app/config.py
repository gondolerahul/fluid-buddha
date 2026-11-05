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

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Namespace used to derive a stable per-site entity UUID from a short site key.
# Deterministic so ingestion and query always resolve to the same knowledge tree.
_SITE_NAMESPACE = uuid.UUID("a2a2a2a2-0000-0000-0000-00000000a2a2")

# The shipped dev JWT secret. It is fine for local work, but the app refuses to
# boot with it (or with an empty secret) when APP_ENV is not one of the dev
# environments below — so a real deployment cannot accidentally sign tokens with
# a secret that is public in this repo. See docs/defects.md D-2.
_DEV_JWT_SECRET = "dev-fluid-buddha-secret-change-me-in-production-0001"
_DEV_ENVS = {"local", "dev", "development", "test", "ci"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- Runtime ----
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    log_format: str = "text"                  # text | json (one object per line)
    # Public widget surface (/chat, /widget, ...): the sites embedding the widget.
    # :3000 = hirebuddha marketing site, :4000 = SDK demos, :3001 = the console
    # (its Install tab tests /widget/config). "*" is fine here — each request is
    # also checked against the website's own domain.
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:3001,http://127.0.0.1:3001,"
        "http://localhost:4000,http://127.0.0.1:4000"
    )
    # Admin API (/auth, /tenant): the console only (docs/defects.md D-21).
    admin_cors_origins: str = "http://localhost:3001,http://127.0.0.1:3001"

    # ---- Database ----
    # Host port 5434 matches docker-compose.yml, so a local `uvicorn` with no
    # .env connects to the compose Postgres out of the box.
    cortex_db_url: str = (
        "postgresql+asyncpg://cortex:cortex@localhost:5434/cortex"
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
    tts_voice_hi: str = "hi-IN-Neural2-A"   # legacy Cloud TTS voice for Hindi (M2-7)
    tts_gemini_voice: str = "Aoede"
    tts_sample_rate: int = 24000

    # ---- CORTEX grounding ----
    cortex_company_id: uuid.UUID = uuid.UUID(
        "11111111-1111-1111-1111-111111111111"
    )
    cortex_confidence_threshold: float = 0.45
    cortex_retrieval_top_k: int = 5

    # ---- Tenant auth (admin dashboard: register/login with JWT bearer) ----
    # The default below is for local/dev only; a non-dev APP_ENV must override it
    # (enforced in _require_strong_secret).
    jwt_secret: str = _DEV_JWT_SECRET
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

    # ---- Public-path abuse guard (docs/defects.md D-3) ----
    # Per-site limits on the unauthenticated /chat and /ws/voice turns, so a
    # loop against the public widget can't run up unbounded model/TTS spend.
    public_rate_limit_per_min: int = 120      # turns per site per minute; 0 = off
    public_daily_spend_cap_usd: float = 0.0   # USD per site per UTC day; 0 = off

    # ---- Trust layer (WS8) ----
    # How often visitor data past each site's retention window is deleted.
    retention_sweep_minutes: int = 60         # 0 = off

    # ---- Email (M2-0): plain SMTP, any provider ----
    # Without SMTP_HOST, dev environments log each email instead of sending it;
    # other environments refuse to queue email (so nothing is silently lost).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_security: str = "starttls"           # starttls | ssl | none
    smtp_from: str = "FluidBuddha <no-reply@localhost>"
    smtp_timeout_seconds: float = 20.0
    email_outbox_interval_seconds: int = 15   # how often queued email is sent; 0 = off
    # Insights v2 (M2-5): how often new visitor turns are classified, and how
    # often accounts are checked for a due weekly digest. 0 = off.
    insights_classify_seconds: int = 20
    # Where the widget's built files are served from (the recap page loads the
    # SDK's recap bundle from here, M2-6).
    widget_sdk_base: str = "http://localhost:4000/dist"
    digest_check_seconds: int = 600
    # Base URL of the console, for links in emails (invitations, digests).
    console_url: str = "http://localhost:3001"

    # ---- Teams and single sign-on (M2-1) ----
    # This backend's public base URL: SSO redirect URIs are built from it
    # (register <PUBLIC_API_URL>/auth/sso/callback with the identity provider).
    public_api_url: str = "http://localhost:8080"
    # "Sign in with Google" (a Google Cloud OAuth client, type Web application).
    google_client_id: str = ""
    google_client_secret: str = ""
    # Proving an SSO domain: TXT records are read over DNS-over-HTTPS.
    dns_over_https_url: str = "https://dns.google/resolve"
    # ---- Live takeover and voice handoff (M2-2) ----
    # STUN servers browsers use to find their public address (comma-separated).
    stun_urls: str = "stun:stun.l.google.com:19302"
    # Our coturn relay, e.g. "turn:turn.example.com:3478?transport=udp,
    # turn:turn.example.com:3478?transport=tcp", and the secret it shares with us.
    turn_urls: str = ""
    turn_secret: str = ""
    turn_ttl_seconds: int = 3600
    # Fernet key(s) for stored secrets (app/security/secrets.py); comma-separated
    # to rotate, newest first. Empty: derived from JWT_SECRET (dev only).
    secrets_key: str = ""

    # ---- Self-serve onboarding (WS9) ----
    crawl_max_pages: int = 50                 # hard cap per crawl
    crawl_max_depth: int = 3
    crawl_concurrency: int = 4
    # Dev only: let the crawler and URL sources reach localhost / private
    # addresses (to crawl a site running on your machine). Never in production.
    ingest_allow_private_urls: bool = False

    # ---- Production plumbing (F-3) ----
    # Shared state for running more than one backend: chat sessions and the
    # public rate limit. Unset = in-process (fine for one replica).
    redis_url: str = ""
    session_ttl_minutes: int = 30             # idle chat sessions are dropped after this
    session_cache_max: int = 10_000           # in-process store: most sessions kept
    # Prometheus metrics at /metrics; with a token, scrapers must send
    # "Authorization: Bearer <token>".
    metrics_enabled: bool = True
    metrics_token: str = ""
    # OpenTelemetry tracing: on when an OTLP/HTTP collector endpoint is set.
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "fluid-buddha-backend"
    # Sentry error reporting: on when a DSN is set.
    sentry_dsn: str = ""
    release: str = ""                         # e.g. the git sha, for Sentry

    # ---- Billing with Razorpay (WS12) ----
    # Test keys (rzp_test_…) for development. Without keys the console shows
    # the plans but checkout is off.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    # Razorpay API for customer payment actions (M2-8); a fake server in local checks.
    razorpay_api_base: str = "https://api.razorpay.com/v1"
    # How often unpaid payment links are checked with Razorpay (0 = off).
    action_payments_seconds: int = 300
    # Plan prices are in this currency's minor unit. INR is the default; USD
    # needs international payments enabled on the Razorpay account.
    billing_currency: str = "INR"
    # JSON overrides of app/billing/plans.py DEFAULT_CATALOG, merged per plan.
    billing_catalog: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.admin_cors_origins.split(",") if o.strip()]

    @property
    def is_dev_env(self) -> bool:
        return self.app_env.strip().lower() in _DEV_ENVS

    @model_validator(mode="after")
    def _require_strong_secret(self) -> "Settings":
        """Refuse to run a non-dev environment with the public dev secret.

        Local/dev/test/ci keep working with the shipped default; anything else
        must set its own JWT_SECRET. See docs/defects.md D-2.
        """
        if not self.is_dev_env and (
            not self.jwt_secret or self.jwt_secret == _DEV_JWT_SECRET
        ):
            raise ValueError(
                f"JWT_SECRET must be set to a non-default value when APP_ENV "
                f"is '{self.app_env}' (not one of {sorted(_DEV_ENVS)})."
            )
        return self


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
