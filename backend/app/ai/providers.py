"""
Bring your own model: per-account providers and per-site routing (M3-4).

An account can set up its own model provider — Anthropic, OpenAI or Azure
OpenAI — with its API key (encrypted at rest) and the models for the two
roles the agent uses: *fast* (router, lean answers, labelling) and *thinker*
(the heavy, tool-using answer). Each of the account's websites uses it unless
switched back to the platform's model.

The agent's code keeps calling one ``LLMClient`` (``rt.engines.llm``). That
client is a ``RoutingLLM``: it reads the site the current request is for from
``current_site`` (a context variable set where a conversation, recap or job
starts) and sends the call to the site's provider, translating the
platform's model names to the account's (``heavy_model`` → thinker, anything
else → fast). If the account's provider fails, the call falls back to the
platform's model so the visitor still gets an answer, and the error is shown
in the console.

Voice (speech-to-text, text-to-speech) and embeddings stay on the platform.
"""
from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import text

from app.ai.base import ChatMessage, LLMClient, LLMResponse, ToolSpec
from app.config import Settings

logger = logging.getLogger(__name__)

PROVIDERS = ("anthropic", "openai", "azure_openai")
current_site: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("fb_current_site", default=None)

# USD per 1M tokens (input, output) for cost tracking, from the providers'
# published list prices; an account can enter its own prices instead (OpenAI
# and Azure prices vary by deployment, so they have no defaults here).
LIST_PRICES: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}

DEFAULT_MODELS = {
    "anthropic": ("claude-haiku-5-5", "claude-opus-5-5"),
    "openai": ("gpt-4.1-mini", "gpt-4.1"),
    "azure_openai": ("", ""),       # Azure needs the account's deployment names
}


@dataclass
class ProviderConfig:
    tenant_id: uuid.UUID
    provider: str
    fast_model: str
    thinker_model: str
    api_key: str
    endpoint: Optional[str] = None
    api_version: Optional[str] = None
    prices: dict[str, Any] = field(default_factory=dict)
    updated_at: float = 0.0

    def model_for(self, requested: Optional[str], settings: Settings) -> str:
        return self.thinker_model if requested and requested == settings.heavy_model else self.fast_model

    def price(self, model: str) -> tuple[float, float]:
        """(input, output) USD per 1M tokens for ``model``."""
        role = "thinker" if model == self.thinker_model else "fast"
        own = self.prices.get(role) or {}
        try:
            if own.get("in") is not None and own.get("out") is not None:
                return float(own["in"]), float(own["out"])
        except (TypeError, ValueError):
            pass
        return LIST_PRICES.get(model, (0.0, 0.0))


def build_client(cfg: ProviderConfig, *, http_client: Any = None) -> Any:
    if cfg.provider == "anthropic":
        from app.ai.anthropic_llm import AnthropicLLMClient
        return AnthropicLLMClient(cfg.api_key, http_client=http_client, default_model=cfg.fast_model)
    from app.ai.openai_llm import OpenAILLMClient
    return OpenAILLMClient(cfg.api_key, endpoint=cfg.endpoint if cfg.provider == "azure_openai" else None,
                           api_version=cfg.api_version, http_client=http_client,
                           default_model=cfg.fast_model)


# ---- loading, with a short cache ---------------------------------------------------

_TTL = 60.0
_by_site: dict[str, tuple[float, Optional[ProviderConfig]]] = {}
_clients: dict[tuple[uuid.UUID, float], Any] = {}
# Tests swap in a fake transport: a callable (provider) -> SDK HTTP client.
http_client_factory: Any = None


def forget(tenant_id: Optional[uuid.UUID] = None) -> None:
    """A provider or a site's switch changed: reload on the next call."""
    _by_site.clear()
    if tenant_id is not None:
        for k in [k for k in _clients if k[0] == tenant_id]:
            _clients.pop(k, None)


def cached_for_site(site_key: Optional[str]) -> Optional[ProviderConfig]:
    """The site's provider if it was looked up recently (sync, for usage records)."""
    hit = _by_site.get(site_key or "")
    return hit[1] if hit else None


async def config_for_site(site_key: Optional[str]) -> Optional[ProviderConfig]:
    if not site_key:
        return None
    hit = _by_site.get(site_key)
    if hit and time.monotonic() - hit[0] < _TTL:
        return hit[1]
    from app.db import session_scope
    from app.security import secrets as stored

    cfg: Optional[ProviderConfig] = None
    try:
        async with session_scope() as db:
            row = (await db.execute(text(
                "SELECT p.tenant_id, p.provider, p.fast_model, p.thinker_model, p.api_key_enc, p.endpoint, "
                "p.api_version, p.prices, extract(epoch FROM p.updated_at) AS ver "
                "FROM tenant_websites w JOIN model_providers p ON p.tenant_id = w.tenant_id "
                "WHERE w.site_key = :s AND w.byo_model AND p.enabled"), {"s": site_key})).mappings().first()
        if row:
            prices = row["prices"] if isinstance(row["prices"], dict) else json.loads(row["prices"] or "{}")
            cfg = ProviderConfig(tenant_id=row["tenant_id"], provider=row["provider"],
                                 fast_model=row["fast_model"], thinker_model=row["thinker_model"],
                                 api_key=stored.decrypt(row["api_key_enc"]), endpoint=row["endpoint"],
                                 api_version=row["api_version"], prices=prices,
                                 updated_at=float(row["ver"]))
    except Exception as exc:   # a broken lookup must never stop a conversation
        logger.warning("model provider lookup failed for %s: %s", site_key, exc)
        cfg = None
    _by_site[site_key] = (time.monotonic(), cfg)
    return cfg


def client_for(cfg: ProviderConfig) -> Any:
    key = (cfg.tenant_id, cfg.updated_at)
    client = _clients.get(key)
    if client is None:
        client = build_client(cfg, http_client=http_client_factory(cfg.provider) if http_client_factory else None)
        _clients[key] = client
    return client


async def record_error(tenant_id: uuid.UUID, error: Optional[str]) -> None:
    from app.db import session_scope
    try:
        async with session_scope() as db:
            await db.execute(text(
                "UPDATE model_providers SET last_error = :e, last_test_at = now(), "
                "last_test_ok = CAST(:e AS text) IS NULL WHERE tenant_id = :t"),
                {"e": (error or None) and error[:500], "t": tenant_id})
            await db.commit()
    except Exception as exc:
        logger.debug("could not record provider error: %s", exc)


class RoutingLLM:
    """The ``LLMClient`` the agent uses: the platform's engine, or the current
    site's own provider."""

    def __init__(self, default: LLMClient, settings: Settings) -> None:
        self._default = default
        self._settings = settings

    @property
    def default(self) -> LLMClient:
        return self._default

    async def _route(self) -> Optional[ProviderConfig]:
        return await config_for_site(current_site.get())

    async def generate(self, *, system: str, messages: Sequence[ChatMessage],
                       tools: Optional[Sequence[ToolSpec]] = None, model: Optional[str] = None,
                       temperature: float = 0.7, max_output_tokens: Optional[int] = None,
                       thinking_budget: Optional[int] = None) -> LLMResponse:
        cfg = await self._route()
        if cfg is not None:
            try:
                resp = await client_for(cfg).generate(
                    system=system, messages=messages, tools=tools, model=cfg.model_for(model, self._settings),
                    temperature=temperature, max_output_tokens=max_output_tokens,
                    thinking_budget=thinking_budget)
                return resp
            except Exception as exc:
                logger.warning("account model provider failed (%s), using the platform model: %s",
                               cfg.provider, exc)
                await record_error(cfg.tenant_id, f"{type(exc).__name__}: {exc}")
                # Replayed provider-native turns mean nothing to the platform engine.
                messages = [ChatMessage(role=m.role, text=m.text, tool_name=m.tool_name,
                                        tool_result=m.tool_result, tool_calls=m.tool_calls)
                            for m in messages]
        resp = await self._default.generate(
            system=system, messages=messages, tools=tools, model=model, temperature=temperature,
            max_output_tokens=max_output_tokens, thinking_budget=thinking_budget)
        if not resp.provider:
            resp.provider = "platform"
        return resp

    async def generate_stream(self, *, system: str, messages: Sequence[ChatMessage],
                              model: Optional[str] = None, temperature: float = 0.7,
                              max_output_tokens: Optional[int] = None) -> AsyncIterator[str]:
        cfg = await self._route()
        source = client_for(cfg) if cfg is not None else self._default
        use_model = cfg.model_for(model, self._settings) if cfg is not None else model
        async for chunk in source.generate_stream(system=system, messages=messages, model=use_model,
                                                  temperature=temperature, max_output_tokens=max_output_tokens):
            yield chunk
