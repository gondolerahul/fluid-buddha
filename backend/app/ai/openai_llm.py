"""
OpenAI or Azure OpenAI as the agent's model, with the customer's own key (M3-4).

Implements ``LLMClient`` over the Chat Completions API with the official
``openai`` SDK. Azure OpenAI is the same API at the customer's resource
(``endpoint`` + ``api_version``), where the "model" is the deployment name.

Parameter differences between model families are handled by retrying once
without what the model refused: ``max_completion_tokens`` falls back to
``max_tokens`` for older deployments, and ``temperature`` is dropped for
reasoning models that take only the default.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, Optional

import openai

from app.ai.base import ChatMessage, LLMResponse, ToolCall, ToolSpec

logger = logging.getLogger(__name__)

DEFAULT_FAST_MODEL = "gpt-4.1-mini"
DEFAULT_THINKER_MODEL = "gpt-4.1"


def _result_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)[:20000]
    except (TypeError, ValueError):
        return str(value)[:20000]


def to_messages(system: str, messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
    pending: list[tuple[str, str]] = []
    synth = 0
    for m in messages:
        if m.role == "model":
            msg: dict[str, Any] = {"role": "assistant", "content": m.text or None}
            pending = []
            if m.tool_calls:
                calls = []
                for c in m.tool_calls:
                    synth += 1
                    cid = c.id or f"call_fb_{synth}"
                    pending.append((cid, c.name))
                    calls.append({"id": cid, "type": "function",
                                  "function": {"name": c.name, "arguments": json.dumps(c.args or {})}})
                msg["tool_calls"] = calls
            elif not m.text:
                continue
            out.append(msg)
        elif m.role == "tool":
            idx = next((i for i, (_, n) in enumerate(pending) if n == m.tool_name), 0 if pending else None)
            if idx is None:
                out.append({"role": "user", "content": f"(result of {m.tool_name}: {_result_text(m.tool_result)})"})
                continue
            cid, _ = pending.pop(idx)
            out.append({"role": "tool", "tool_call_id": cid, "content": _result_text(m.tool_result)})
        elif m.text:
            out.append({"role": "user", "content": m.text})
    return out


def to_tools(tools: Optional[Sequence[ToolSpec]]) -> Optional[list[dict[str, Any]]]:
    if not tools:
        return None
    return [{"type": "function", "function": {"name": t.name, "description": t.description,
                                              "parameters": t.parameters}} for t in tools]


class OpenAILLMClient:
    """``LLMClient`` over OpenAI, or Azure OpenAI when ``endpoint`` is given."""

    def __init__(self, api_key: str, *, endpoint: Optional[str] = None,
                 api_version: Optional[str] = None, http_client: Any = None,
                 max_retries: int = 2, timeout: float = 60.0,
                 default_model: str = DEFAULT_FAST_MODEL) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": max_retries, "timeout": timeout}
        if http_client is not None:
            kwargs["http_client"] = http_client
        if endpoint:
            self.provider = "azure_openai"
            self._client = openai.AsyncAzureOpenAI(azure_endpoint=endpoint,
                                                   api_version=api_version or "2024-10-21", **kwargs)
        else:
            self.provider = "openai"
            self._client = openai.AsyncOpenAI(**kwargs)
        self._default_model = default_model
        # Learned per model: what it refuses, so later calls skip the retry.
        self._legacy_max: set[str] = set()
        self._fixed_temperature: set[str] = set()

    async def _create(self, req: dict[str, Any]) -> Any:
        model = req["model"]
        for _ in range(3):
            body = dict(req)
            if model in self._legacy_max and "max_completion_tokens" in body:
                body["max_tokens"] = body.pop("max_completion_tokens")
            if model in self._fixed_temperature:
                body.pop("temperature", None)
            try:
                return await self._client.chat.completions.create(**body)
            except openai.BadRequestError as exc:
                msg = str(exc).lower()
                if "max_completion_tokens" in msg and model not in self._legacy_max:
                    self._legacy_max.add(model)
                    continue
                if "temperature" in msg and model not in self._fixed_temperature:
                    self._fixed_temperature.add(model)
                    continue
                raise
        return await self._client.chat.completions.create(**req)

    async def generate(self, *, system: str, messages: Sequence[ChatMessage],
                       tools: Optional[Sequence[ToolSpec]] = None, model: Optional[str] = None,
                       temperature: float = 0.7, max_output_tokens: Optional[int] = None,
                       thinking_budget: Optional[int] = None) -> LLMResponse:
        model = model or self._default_model
        req: dict[str, Any] = {"model": model, "messages": to_messages(system, messages),
                               "temperature": temperature,
                               "max_completion_tokens": max_output_tokens or 4096}
        tool_defs = to_tools(tools)
        if tool_defs:
            req["tools"] = tool_defs
        resp = await self._create(req)
        choice = resp.choices[0]
        msg = choice.message
        calls: list[ToolCall] = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except ValueError:
                args = {}
            calls.append(ToolCall(name=tc.function.name, args=args if isinstance(args, dict) else {}, id=tc.id))
        usage = resp.usage
        finish = choice.finish_reason or "stop"
        if finish == "content_filter":
            logger.warning("%s filtered a response (model=%s)", self.provider, model)
        return LLMResponse(
            text=(msg.content or "").strip(), tool_calls=calls, model=resp.model or model,
            finish_reason={"tool_calls": "tool_calls", "length": "length",
                           "content_filter": "refusal"}.get(finish, "stop"),
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            provider=self.provider)

    async def generate_stream(self, *, system: str, messages: Sequence[ChatMessage],
                              model: Optional[str] = None, temperature: float = 0.7,
                              max_output_tokens: Optional[int] = None) -> AsyncIterator[str]:
        model = model or self._default_model
        stream = await self._create({"model": model, "messages": to_messages(system, messages),
                                     "temperature": temperature,
                                     "max_completion_tokens": max_output_tokens or 4096, "stream": True})
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def check(self, model: str) -> str:
        resp = await self._create({"model": model, "max_completion_tokens": 16,
                                   "messages": [{"role": "user", "content": "Reply with the single word: ok"}]})
        return resp.model or model
