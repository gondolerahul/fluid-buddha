"""
Bring your own model (M3-4): the Anthropic and OpenAI/Azure engines against
recorded-style API responses (fake transports, no network), the per-account
provider settings (key encrypted, never returned), routing a site's turns to
its provider, usage and cost per provider, and the fallback to the platform.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import anthropic
import httpx2
import openai
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.ai import providers
from app.ai.anthropic_llm import AnthropicLLMClient
from app.ai.base import ChatMessage, ToolSpec
from app.ai.openai_llm import OpenAILLMClient
from app.config import get_settings
from app.main import app

PW = "supersecret1"

# ---- recorded-style responses ----------------------------------------------------------

def claude_message(content, *, model="claude-haiku-5-5", stop="end_turn", usage=(120, 30)):
    return {"id": f"msg_{uuid.uuid4().hex[:8]}", "type": "message", "role": "assistant", "model": model,
            "content": content, "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": usage[0], "output_tokens": usage[1]}}


def openai_completion(message, *, model="gpt-4.1-mini", finish="stop", usage=(90, 25)):
    return {"id": "chatcmpl-1", "object": "chat.completion", "created": 1, "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", **message}, "finish_reason": finish}],
            "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1], "total_tokens": sum(usage)}}


class FakeClaude:
    """A stand-in for api.anthropic.com: records requests, answers from a script."""

    def __init__(self, replies=None, fail=False):
        self.requests: list[dict] = []
        self.replies = list(replies or [])
        self.fail = fail

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append({"url": str(request.url), "headers": dict(request.headers), "body": body})
        if self.fail:
            return httpx2.Response(401, json={"type": "error", "error": {
                "type": "authentication_error", "message": "invalid x-api-key"}})
        if body.get("stream"):
            events = [
                ("message_start", {"type": "message_start", "message": claude_message([], usage=(10, 0))}),
                ("content_block_start", {"type": "content_block_start", "index": 0,
                                         "content_block": {"type": "text", "text": ""}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                         "delta": {"type": "text_delta", "text": "Hello "}}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                         "delta": {"type": "text_delta", "text": "there."}}),
                ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn",
                                                                      "stop_sequence": None},
                                   "usage": {"output_tokens": 3}}),
                ("message_stop", {"type": "message_stop"}),
            ]
            sse = "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events)
            return httpx2.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})
        reply = self.replies.pop(0) if self.replies else claude_message(
            [{"type": "text", "text": "Our Growth plan is ₹14,999 a month."}], model=body["model"])
        return httpx2.Response(200, json=reply)

    def client(self):
        return anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(self.handler))


class FakeOpenAI:
    def __init__(self, replies=None, reject=None):
        self.requests: list[dict] = []
        self.replies = list(replies or [])
        self.reject = set(reject or ())

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append({"url": str(request.url), "headers": dict(request.headers), "body": body})
        for param in list(self.reject):
            if param in body:
                return httpx2.Response(400, json={"error": {
                    "message": f"Unsupported parameter: '{param}' is not supported with this model.",
                    "type": "invalid_request_error", "param": param, "code": "unsupported_parameter"}})
        reply = self.replies.pop(0) if self.replies else openai_completion({"content": "Hi from GPT."})
        return httpx2.Response(200, json=reply)

    def client(self):
        # The openai SDK (3.x) is built on httpx2 too.
        return openai.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(self.handler))


TOOLS = [ToolSpec(name="query_cortex", description="Search the site's knowledge.",
                  parameters={"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]})]


# ---- the Anthropic engine -----------------------------------------------------------------

def test_claude_request_shape_tool_loop_and_replay():
    fake = FakeClaude(replies=[
        claude_message([{"type": "thinking", "thinking": "", "signature": "sig-abc"},
                        {"type": "text", "text": "Let me check."},
                        {"type": "tool_use", "id": "toolu_1", "name": "query_cortex", "input": {"q": "pricing"}}],
                       model="claude-opus-5-5", stop="tool_use"),
        claude_message([{"type": "text", "text": "Growth is ₹14,999."}], model="claude-opus-5-5"),
    ])
    llm = AnthropicLLMClient("sk-ant-test", http_client=fake.client())

    async def go():
        first = await llm.generate(system="Be grounded.", messages=[ChatMessage(role="user", text="Price?")],
                                   tools=TOOLS, model="claude-opus-5-5", temperature=0.5,
                                   max_output_tokens=1024, thinking_budget=1)
        history = [ChatMessage(role="user", text="Price?"),
                   ChatMessage(role="model", tool_calls=first.tool_calls, raw=first.raw),
                   ChatMessage(role="tool", tool_name="query_cortex", tool_result={"hits": ["₹14,999"]})]
        second = await llm.generate(system="Be grounded.", messages=history, tools=TOOLS,
                                    model="claude-opus-5-5", thinking_budget=1)
        return first, second

    first, second = asyncio.run(go())
    assert first.tool_calls[0].name == "query_cortex" and first.tool_calls[0].id == "toolu_1"
    assert first.tool_calls[0].args == {"q": "pricing"} and first.provider == "anthropic"
    assert (first.input_tokens, first.output_tokens) == (120, 30)
    assert second.text == "Growth is ₹14,999." and not second.tool_calls

    req1 = fake.requests[0]
    body = req1["body"]
    assert req1["url"].endswith("/v1/messages") and req1["headers"]["authorization"] == "Bearer sk-ant-test"
    assert "temperature" not in body, "current Claude models take no sampling parameters"
    assert body["output_config"] == {"effort": "low"} and "thinking" not in body   # Opus 5.5 always thinks
    assert body["max_tokens"] >= 2048, "room for thinking before the answer"
    assert body["tools"][0] == {"name": "query_cortex", "description": "Search the site's knowledge.",
                                "input_schema": TOOLS[0].parameters}
    assert body["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in req1["headers"]["anthropic-beta"]

    turns = fake.requests[1]["body"]["messages"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user"]
    assert turns[1]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig-abc"}, \
        "the thinking block is replayed verbatim"
    assert turns[2]["content"] == [{"type": "tool_result", "tool_use_id": "toolu_1",
                                    "content": json.dumps({"hits": ["₹14,999"]})}]


def test_claude_quick_calls_on_haiku_and_sonnet_turn_thinking_off():
    fake = FakeClaude()
    llm = AnthropicLLMClient("k", http_client=fake.client())

    async def go():
        await llm.generate(system="s", messages=[ChatMessage(role="user", text="hi")],
                           model="claude-haiku-5-5", max_output_tokens=120, thinking_budget=0)
        await llm.generate(system="s", messages=[ChatMessage(role="user", text="hi")],
                           model="claude-sonnet-5-5", max_output_tokens=120, thinking_budget=0)
    asyncio.run(go())
    haiku, sonnet = (r["body"] for r in fake.requests)
    assert haiku["thinking"] == {"type": "disabled"} and haiku["output_config"] == {"effort": "low"}
    assert haiku["max_tokens"] == 120 and "fallbacks" not in haiku
    assert sonnet["thinking"] == {"type": "between_tools"} and sonnet["fallbacks"] == "default"


def test_claude_refusal_and_streaming_and_errors():
    fake = FakeClaude(replies=[claude_message([], stop="refusal", model="claude-opus-5-5")])
    llm = AnthropicLLMClient("k", http_client=fake.client())

    async def go():
        refused = await llm.generate(system="s", messages=[ChatMessage(role="user", text="x")],
                                     model="claude-opus-5-5")
        chunks = [c async for c in llm.generate_stream(system="s", messages=[ChatMessage(role="user", text="x")],
                                                        model="claude-haiku-5-5")]
        return refused, chunks
    refused, chunks = asyncio.run(go())
    assert refused.finish_reason == "refusal" and refused.text == ""
    assert "".join(chunks) == "Hello there."

    bad = AnthropicLLMClient("wrong", http_client=FakeClaude(fail=True).client(), max_retries=0)
    with pytest.raises(anthropic.AuthenticationError):
        asyncio.run(bad.generate(system="s", messages=[ChatMessage(role="user", text="x")]))


# ---- the OpenAI / Azure engine ------------------------------------------------------------

def test_openai_request_shape_tools_and_parameter_retries():
    fake = FakeOpenAI(reject={"max_completion_tokens", "temperature"}, replies=[
        openai_completion({"content": None, "tool_calls": [{"id": "call_9", "type": "function", "function": {
            "name": "query_cortex", "arguments": json.dumps({"q": "pricing"})}}]}, finish="tool_calls"),
        openai_completion({"content": "Growth is ₹14,999."}),
    ])
    llm = OpenAILLMClient("sk-test", http_client=fake.client())

    async def go():
        first = await llm.generate(system="Be grounded.", messages=[ChatMessage(role="user", text="Price?")],
                                   tools=TOOLS, model="gpt-4.1", max_output_tokens=500)
        second = await llm.generate(system="Be grounded.", tools=TOOLS, model="gpt-4.1", messages=[
            ChatMessage(role="user", text="Price?"), ChatMessage(role="model", tool_calls=first.tool_calls),
            ChatMessage(role="tool", tool_name="query_cortex", tool_result={"hits": 1})])
        return first, second
    first, second = asyncio.run(go())
    assert first.tool_calls[0].id == "call_9" and first.tool_calls[0].args == {"q": "pricing"}
    assert second.text == "Growth is ₹14,999." and second.provider == "openai"
    ok = [r["body"] for r in fake.requests if "max_tokens" in r["body"] and "temperature" not in r["body"]]
    assert ok, "retried with max_tokens and without temperature after the model refused them"
    last = fake.requests[-1]["body"]
    assert last["messages"][0] == {"role": "system", "content": "Be grounded."}
    assert last["messages"][2]["tool_calls"][0]["id"] == "call_9"
    assert last["messages"][3] == {"role": "tool", "tool_call_id": "call_9", "content": json.dumps({"hits": 1})}
    assert last["tools"][0]["function"]["name"] == "query_cortex"
    assert fake.requests[-1]["headers"]["authorization"] == "Bearer sk-test"
    # What a model refused is remembered: later calls don't retry.
    assert sum(1 for r in fake.requests if "temperature" in r["body"]) <= 2


def test_azure_openai_uses_the_resource_deployment_and_key():
    fake = FakeOpenAI()
    llm = OpenAILLMClient("az-key", endpoint="https://acme.openai.azure.com", api_version="2024-10-21",
                          http_client=fake.client())
    resp = asyncio.run(llm.generate(system="s", messages=[ChatMessage(role="user", text="hi")], model="fb-fast"))
    req = fake.requests[0]
    assert req["url"].startswith("https://acme.openai.azure.com/openai/deployments/fb-fast/chat/completions")
    assert "api-version=2024-10-21" in req["url"] and req["headers"]["api-key"] == "az-key"
    assert resp.provider == "azure_openai" and resp.text == "Hi from GPT."


# ---- settings, routing, usage --------------------------------------------------------------

def _register(client):
    body = client.post("/auth/register", json={"email": f"byo_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": PW}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def _join(client, owner_h, role):
    email = f"byo_{uuid.uuid4().hex[:10]}@example.com"
    inv = client.post("/tenant/team/invitations", headers=owner_h, json={"email": email, "role": role}).json()
    body = client.post(f"/auth/invitations/{inv['link'].split('token=')[1]}/accept", json={"password": PW}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _sql(q, p=None):
    async def run():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                return (await conn.execute(text(q), p or {})).mappings().all()
        finally:
            await engine.dispose()
    return asyncio.run(run())


@pytest.fixture
def fakes(monkeypatch):
    claude, gpt = FakeClaude(), FakeOpenAI()
    monkeypatch.setattr(providers, "http_client_factory",
                        lambda provider: claude.client() if provider == "anthropic" else gpt.client())
    providers.forget()
    yield claude, gpt
    providers.forget()


def test_provider_settings_keys_roles_and_test_connection(fakes):
    claude, _ = fakes
    with TestClient(app) as client:
        h, _ = _register(client)
        editor_h = _join(client, h, "editor")
        assert client.get("/tenant/model-provider", headers=editor_h).status_code == 403
        g = client.get("/tenant/model-provider", headers=h).json()
        assert g["configured"] is False and g["defaults"]["anthropic"]["thinker_model"] == "claude-opus-5-5"
        assert client.put("/tenant/model-provider", headers=h, json={
            "provider": "anthropic", "fast_model": "claude-haiku-5-5", "thinker_model": "claude-opus-5-5"}
        ).status_code == 422   # needs a key
        assert client.put("/tenant/model-provider", headers=h, json={
            "provider": "azure_openai", "fast_model": "a", "thinker_model": "b", "api_key": "k"}).status_code == 422
        r = client.put("/tenant/model-provider", headers=h, json={
            "provider": "anthropic", "fast_model": "claude-haiku-5-5", "thinker_model": "claude-opus-5-5",
            "api_key": "sk-ant-secret-1234"})
        assert r.status_code == 200, r.text
        cfg = r.json()
        assert cfg["key_hint"] == "…1234" and "sk-ant" not in json.dumps(cfg)
        tenant = _sql("SELECT api_key_enc FROM model_providers WHERE api_key_enc IS NOT NULL ORDER BY updated_at DESC LIMIT 1")
        assert tenant[0]["api_key_enc"].startswith("gAAAAA")
        t = client.post("/tenant/model-provider/test", headers=h).json()
        assert t["ok"] and [x["model"] for x in t["results"]] == ["claude-haiku-5-5", "claude-opus-5-5"]
        assert client.get("/tenant/model-provider", headers=h).json()["last_test_ok"] is True
        # Saving without a key keeps the stored one.
        assert client.put("/tenant/model-provider", headers=h, json={
            "provider": "anthropic", "fast_model": "claude-sonnet-5-5", "thinker_model": "claude-opus-5-5"}
        ).json()["key_hint"] == "…1234"
        assert claude.requests[-1]["headers"]["authorization"] == "Bearer sk-ant-secret-1234"


def test_a_site_answers_with_its_accounts_model_and_usage_shows_the_provider(fakes):
    claude, _ = fakes
    with TestClient(app) as client:
        h, _ = _register(client)
        site = client.post("/tenant/websites", json={"name": "BYO Co"}, headers=h).json()
        other = client.post("/tenant/websites", json={"name": "Platform Co"}, headers=h).json()
        client.put("/tenant/model-provider", headers=h, json={
            "provider": "anthropic", "fast_model": "claude-haiku-5-5", "thinker_model": "claude-opus-5-5",
            "api_key": "sk-ant-secret-5678", "prices": {"fast": {"in": 1.0, "out": 5.0}}})
        assert client.put(f"/tenant/websites/{other['id']}/model", headers=h,
                          json={"byo_model": False}).json()["byo_model"] is False

        r = client.post("/chat", json={"message": f"How much is Growth? {uuid.uuid4().hex[:4]}",
                                       "key": site["public_key"]})
        assert r.status_code == 200, r.text
        assert claude.requests, "the account's provider answered"
        assert all(q["headers"]["authorization"] == "Bearer sk-ant-secret-5678" for q in claude.requests)
        assert {q["body"]["model"] for q in claude.requests} <= {"claude-haiku-5-5", "claude-opus-5-5"}

        before = len(claude.requests)
        assert client.post("/chat", json={"message": f"Hello {uuid.uuid4().hex[:4]}",
                                          "key": other["public_key"]}).status_code == 200
        assert len(claude.requests) == before, "a site switched to the platform model doesn't use it"

    rows = _sql("SELECT provider, byo_llm_cost, total_cost FROM usage_events WHERE site_key = :s",
                {"s": site["site_key"]})
    assert rows and rows[-1]["provider"] == "anthropic"
    assert rows[-1]["byo_llm_cost"] > 0 and rows[-1]["total_cost"] >= rows[-1]["byo_llm_cost"]
    plat = _sql("SELECT provider, byo_llm_cost FROM usage_events WHERE site_key = :s", {"s": other["site_key"]})
    assert plat and plat[-1]["provider"] == "platform" and plat[-1]["byo_llm_cost"] == 0

    from app.transport.guard import spent_today_usd

    async def spent():
        from sqlalchemy.ext.asyncio import AsyncSession
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with AsyncSession(engine) as db:
                return await spent_today_usd(db, site["site_key"])
        finally:
            await engine.dispose()
    total = sum(r["total_cost"] for r in rows)
    assert asyncio.run(spent()) < total, "the account's own model spend is out of the platform cap"


def test_a_failing_provider_falls_back_to_the_platform_and_shows_the_error(monkeypatch):
    broken = FakeClaude(fail=True)
    monkeypatch.setattr(providers, "http_client_factory", lambda provider: broken.client())
    providers.forget()
    try:
        with TestClient(app) as client:
            h, _ = _register(client)
            site = client.post("/tenant/websites", json={"name": "Broken Key Co"}, headers=h).json()
            client.put("/tenant/model-provider", headers=h, json={
                "provider": "anthropic", "fast_model": "claude-haiku-5-5", "thinker_model": "claude-opus-5-5",
                "api_key": "sk-ant-revoked-0000"})
            r = client.post("/chat", json={"message": f"Hi {uuid.uuid4().hex[:4]}", "key": site["public_key"]})
            assert r.status_code == 200 and r.json()["text"], "the visitor still gets an answer"
            g = client.get("/tenant/model-provider", headers=h).json()
            assert g["last_test_ok"] is False and "AuthenticationError" in (g["last_error"] or "")
            assert broken.requests
    finally:
        providers.forget()
