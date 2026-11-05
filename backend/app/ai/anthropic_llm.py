"""
Claude as the agent's model, with the customer's own Anthropic key (M3-4).

Implements ``LLMClient`` with the official ``anthropic`` SDK (async client).
Notes that shape the requests:

* Current Claude models take no sampling parameters, so ``temperature`` is
  not sent. Depth is set with ``output_config.effort``; where the caller asks
  for no thinking (``thinking_budget=0``) the request uses ``low`` effort, and
  on models that allow it, turns thinking off (Claude Haiku 5.5:
  ``disabled``; Claude Sonnet 5.5: ``between_tools``). Claude Opus 5.5 always
  thinks, so ``max_tokens`` gets a floor that leaves room for it.
* A tool-calling turn's content blocks (thinking blocks included) are kept on
  ``LLMResponse.raw`` and replayed verbatim on the next request, as the API
  requires for tool loops.
* Safety refusals (``stop_reason == "refusal"``) come back as an empty answer
  with ``finish_reason="refusal"``; models that support it get the API's
  server-side fallback (beta ``server-side-fallback-2026-07-01``,
  ``fallbacks: "default"``) so most refusals are answered by another model.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, Optional

import anthropic

from app.ai.base import ChatMessage, LLMResponse, ToolCall, ToolSpec

logger = logging.getLogger(__name__)

PROVIDER = "anthropic"
DEFAULT_FAST_MODEL = "claude-haiku-5-5"
DEFAULT_THINKER_MODEL = "claude-opus-5-5"

# Models that accept the server-side fallback ("default" form, Claude API).
_FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_THINKING_ROOM = 2048   # max_tokens floor where the model may think first


def _thinking_params(model: str, thinking_budget: Optional[int]) -> dict[str, Any]:
    """``thinking`` / ``output_config`` for the model and how much thought the
    caller wants (``0`` = none: a quick routing or classification call)."""
    quick = thinking_budget is not None and thinking_budget <= 1
    if model.startswith("claude-haiku-5"):
        return ({"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}} if quick
                else {"output_config": {"effort": "medium"}})
    if model.startswith("claude-sonnet-5-5"):
        return ({"thinking": {"type": "between_tools"}, "output_config": {"effort": "low"}} if quick
                else {"output_config": {"effort": "medium"}})
    # Claude Opus 5.5 / Fable: thinking is always on; effort is the control.
    return {"output_config": {"effort": "low" if quick else "medium"}}


def _thinks(model: str, params: dict[str, Any]) -> bool:
    t = params.get("thinking", {}).get("type")
    return t not in ("disabled", "between_tools")


def _tool_result_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)[:20000]
    except (TypeError, ValueError):
        return str(value)[:20000]


def to_messages(messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    """Our provider-neutral history → Claude's alternating user/assistant turns.
    Tool results follow the assistant turn that called them, all in one user
    message, each matched to its call's id."""
    out: list[dict[str, Any]] = []
    pending: list[tuple[str, str]] = []   # (id, name) of the last turn's calls not yet answered
    synth = 0

    def push(role: str, content: Any) -> None:
        if out and out[-1]["role"] == role and role == "user":
            prev = out[-1]["content"]
            prev = prev if isinstance(prev, list) else [{"type": "text", "text": prev}]
            add = content if isinstance(content, list) else [{"type": "text", "text": content}]
            out[-1]["content"] = prev + add
        else:
            out.append({"role": role, "content": content})

    for m in messages:
        if m.role == "model":
            if isinstance(m.raw, dict) and m.raw.get("provider") == PROVIDER:
                content = m.raw["content"]
                pending = [(b["id"], b["name"]) for b in content if b.get("type") == "tool_use"]
            else:
                content = []
                if m.text:
                    content.append({"type": "text", "text": m.text})
                pending = []
                for c in m.tool_calls or []:
                    synth += 1
                    cid = c.id or f"toolu_fb_{synth}"
                    pending.append((cid, c.name))
                    content.append({"type": "tool_use", "id": cid, "name": c.name, "input": c.args or {}})
                if not content:
                    continue
            push("assistant", content)
        elif m.role == "tool":
            idx = next((i for i, (_, n) in enumerate(pending) if n == m.tool_name), 0 if pending else None)
            if idx is None:
                # A result with no call to attach to: keep it as context text.
                push("user", f"(result of {m.tool_name}: {_tool_result_content(m.tool_result)})")
                continue
            cid, _ = pending.pop(idx)
            push("user", [{"type": "tool_result", "tool_use_id": cid,
                           "content": _tool_result_content(m.tool_result)}])
        else:
            if m.text:
                push("user", m.text)
    # The conversation must start with a user turn.
    if out and out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": "(conversation continues)"})
    return out


def to_tools(tools: Optional[Sequence[ToolSpec]]) -> Optional[list[dict[str, Any]]]:
    if not tools:
        return None
    return [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]


class AnthropicLLMClient:
    """``LLMClient`` over the Claude API with an account's own key."""

    provider = PROVIDER

    def __init__(self, api_key: str, *, http_client: Any = None, max_retries: int = 2,
                 timeout: float = 60.0, default_model: str = DEFAULT_FAST_MODEL) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": max_retries, "timeout": timeout}
        if http_client is not None:
            kwargs["http_client"] = http_client
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self._default_model = default_model

    async def generate(self, *, system: str, messages: Sequence[ChatMessage],
                       tools: Optional[Sequence[ToolSpec]] = None, model: Optional[str] = None,
                       temperature: float = 0.7, max_output_tokens: Optional[int] = None,
                       thinking_budget: Optional[int] = None) -> LLMResponse:
        model = model or self._default_model
        params = _thinking_params(model, thinking_budget)
        max_tokens = max_output_tokens or 16000
        if _thinks(model, params):
            max_tokens = max(max_tokens, _THINKING_ROOM)
        req: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "system": system,
                               "messages": to_messages(messages), **params}
        tool_defs = to_tools(tools)
        if tool_defs:
            req["tools"] = tool_defs
        if model.startswith(_FALLBACK_MODELS):
            resp = await self._client.beta.messages.create(
                **req, betas=[_FALLBACK_BETA], fallbacks="default")
        else:
            resp = await self._client.messages.create(**req)
        return self._response(resp, model)

    def _response(self, resp: Any, model: str) -> LLMResponse:
        if resp.stop_reason == "refusal":
            logger.warning("claude refused a request (model=%s)", model)
            return LLMResponse(text="", model=getattr(resp, "model", model), finish_reason="refusal",
                               input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
                               provider=PROVIDER)
        texts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                texts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(name=block.name, args=dict(block.input or {}), id=block.id))
        raw = None
        if calls:
            # Replay this turn exactly (thinking blocks included) with its results.
            raw = {"provider": PROVIDER,
                   "content": [b.model_dump(mode="json", exclude_none=True) for b in resp.content]}
        return LLMResponse(
            text="".join(texts).strip(), tool_calls=calls, model=getattr(resp, "model", model),
            finish_reason="tool_calls" if calls else ("length" if resp.stop_reason == "max_tokens" else "stop"),
            input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
            provider=PROVIDER, raw=raw)

    async def generate_stream(self, *, system: str, messages: Sequence[ChatMessage],
                              model: Optional[str] = None, temperature: float = 0.7,
                              max_output_tokens: Optional[int] = None) -> AsyncIterator[str]:
        model = model or self._default_model
        params = _thinking_params(model, 0)
        max_tokens = max(max_output_tokens or 4096, _THINKING_ROOM if _thinks(model, params) else 0)
        async with self._client.messages.stream(model=model, max_tokens=max_tokens, system=system,
                                                messages=to_messages(messages), **params) as stream:
            async for text in stream.text_stream:
                yield text

    async def check(self, model: str) -> str:
        """A one-line round trip for "Test connection"; returns the model that answered."""
        resp = await self._client.messages.create(
            model=model, max_tokens=_THINKING_ROOM if _thinks(model, _thinking_params(model, 0)) else 32,
            messages=[{"role": "user", "content": "Reply with the single word: ok"}],
            **_thinking_params(model, 0))
        return getattr(resp, "model", model)
