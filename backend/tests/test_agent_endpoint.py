"""
The site's agent endpoint (M3-2): MCP protocol conformance (initialize, list
tools, call, resources, errors), scoped tokens for leads and actions, origin
and rate limits, agent traffic, llms.txt, OpenAPI and REST ask.
"""
from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.main import app

PW = "supersecret1"


def _register(client):
    body = client.post("/auth/register", json={"email": f"mcp_{uuid.uuid4().hex[:10]}@example.com",
                                               "password": PW}).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _site(client, h, *, domain=None, enabled=True):
    site = client.post("/tenant/websites", json={"name": "Agent Co", **({"domain": domain} if domain else {})},
                       headers=h).json()
    if enabled:
        assert client.put(f"/tenant/websites/{site['id']}/agent-access", headers=h,
                          json={"enabled": True}).json() == {"enabled": True}
    return site


def rpc(client, key, method, params=None, id_=1, headers=None):
    body = {"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})}
    if id_ is not None:
        body["id"] = id_
    return client.post(f"/mcp/{key}", content=json.dumps(body),
                       headers={"Content-Type": "application/json",
                                "Accept": "application/json, text/event-stream", **(headers or {})})


def test_mcp_handshake_tools_and_a_grounded_answer():
    with TestClient(app) as client:
        h = _register(client)
        site = _site(client, h)
        key = site["public_key"]

        init = rpc(client, key, "initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "Claude Desktop", "version": "1.0"}})
        assert init.status_code == 200 and init.headers["content-type"].startswith("application/json")
        res = init.json()["result"]
        assert res["protocolVersion"] == "2025-06-18"
        assert set(res["capabilities"]) >= {"tools", "resources"} and "Agent Co" in res["serverInfo"]["name"]
        # An unknown version gets the server's latest.
        assert rpc(client, key, "initialize", {"protocolVersion": "1999-01-01"}).json()["result"][
            "protocolVersion"] == "2025-11-25"
        assert rpc(client, key, "notifications/initialized", id_=None).status_code == 202
        assert rpc(client, key, "ping").json() == {"jsonrpc": "2.0", "id": 1, "result": {}}

        listed = rpc(client, key, "tools/list", headers={"MCP-Protocol-Version": "2025-06-18"}).json()["result"]["tools"]
        names = [t["name"] for t in listed]
        assert names == ["search_knowledge", "get_page", "list_offerings", "list_views", "get_view"], \
            "no acting tools without a token"
        assert all(t["inputSchema"]["type"] == "object" for t in listed)
        assert listed[0]["annotations"]["readOnlyHint"] is True

        call = rpc(client, key, "tools/call", {"name": "search_knowledge",
                                                "arguments": {"question": "What do you offer?"}}).json()["result"]
        assert call["isError"] is False and call["content"][0]["type"] == "text" and call["content"][0]["text"]
        assert set(call["structuredContent"]) >= {"answer", "sources", "found"}
        offers = rpc(client, key, "tools/call", {"name": "list_offerings", "arguments": {}}).json()["result"]
        assert offers["isError"] is False and "price_lists" in offers["structuredContent"]

        # Traffic shows up in the console, with the client's name.
        t = client.get(f"/tenant/websites/{site['id']}/agent-access", headers=h).json()
        assert t["enabled"] and t["endpoints"]["mcp"].endswith(f"/mcp/{key}")
        tools_used = {x["tool"] for x in t["traffic"]["by_tool"]}
        assert {"search_knowledge", "list_offerings", "initialize"} <= tools_used
        assert any(c["client"] == "Claude Desktop 1.0" for c in t["traffic"]["by_client"])


def test_mcp_errors_and_transport_rules():
    with TestClient(app) as client:
        h = _register(client)
        site = _site(client, h, domain="agentco.example")
        key = site["public_key"]
        assert rpc(client, key, "no/such").json()["error"]["code"] == -32601
        bad = client.post(f"/mcp/{key}", content=b"{not json", headers={"Content-Type": "application/json"})
        assert bad.status_code == 400 and bad.json()["error"]["code"] == -32700
        assert client.post(f"/mcp/{key}", content=json.dumps([{"jsonrpc": "2.0", "id": 1, "method": "ping"}]),
                           headers={"Content-Type": "application/json"}).status_code == 400
        assert client.post(f"/mcp/{key}", content=json.dumps({"id": 1, "method": "ping"}),
                           headers={"Content-Type": "application/json"}).json()["error"]["code"] == -32600
        assert rpc(client, key, "tools/call", {"name": "nope", "arguments": {}}).json()["error"]["code"] == -32602
        assert rpc(client, key, "ping", headers={"MCP-Protocol-Version": "2020-01-01"}).status_code == 400
        assert client.get(f"/mcp/{key}").status_code == 405
        # Browsers may only call from the site's own domain (DNS rebinding).
        assert rpc(client, key, "ping", headers={"Origin": "https://evil.example"}).status_code == 403
        assert rpc(client, key, "ping", headers={"Origin": "https://www.agentco.example"}).status_code == 200
        # A tool error is a result, not a protocol error.
        empty = rpc(client, key, "tools/call", {"name": "search_knowledge", "arguments": {"question": " "}}).json()
        assert empty["result"]["isError"] is True

        # Not switched on, or not a key: the same 404.
        off = _site(client, h, enabled=False)
        assert rpc(client, off["public_key"], "ping").status_code == 404
        assert rpc(client, "fbk_nope_nope_nope", "ping").status_code == 404


def test_tokens_unlock_leads_and_actions_for_their_site_only():
    with TestClient(app) as client:
        h = _register(client)
        site = _site(client, h)
        key = site["public_key"]
        client.post(f"/tenant/websites/{site['id']}/actions", headers=h, json={
            "kind": "quote_request", "name": "get_quote", "label": "Request a quote", "enabled": True,
            "description": "A quote for a team.", "config": {}})
        assert client.post(f"/tenant/websites/{site['id']}/agent-tokens", headers=h,
                           json={"name": "x", "scopes": ["admin"]}).status_code == 422
        made = client.post(f"/tenant/websites/{site['id']}/agent-tokens", headers=h,
                           json={"name": "Shopping assistant", "scopes": ["leads", "actions"]}).json()
        token = made["token"]
        assert token.startswith("fbat_") and made["scopes"] == ["leads", "actions"]
        auth = {"Authorization": f"Bearer {token}"}

        # Without the token, acting is refused as a tool error.
        nope = rpc(client, key, "tools/call", {"name": "capture_lead", "arguments": {"email": "a@b.co"}}).json()
        assert nope["result"]["isError"] is True and "token" in nope["result"]["content"][0]["text"]

        names = [t["name"] for t in rpc(client, key, "tools/list", headers=auth).json()["result"]["tools"]]
        assert "capture_lead" in names and "action_get_quote" in names
        lead = rpc(client, key, "tools/call", {"name": "capture_lead", "arguments": {
            "email": "buyer@example.com", "name": "Asha", "message": "20 seats"}}, headers=auth).json()["result"]
        assert lead["isError"] is False and lead["structuredContent"]["lead_id"]
        leads = client.get(f"/tenant/websites/{site['id']}/leads", headers=h).json()
        rows = leads["items"]
        assert any(x["email"] == "buyer@example.com" and x["source"] == "agent" for x in rows)

        quote = rpc(client, key, "tools/call", {"name": "action_get_quote", "arguments": {
            "email": "buyer@example.com", "name": "Asha", "details": "20 seats, annual"}}, headers=auth).json()
        assert quote["result"]["isError"] is False, quote
        assert quote["result"]["structuredContent"]["status"] == "done"

        # A token for one site is no token for another; a revoked token is no token.
        other = _site(client, h)
        assert "capture_lead" not in [t["name"] for t in rpc(client, other["public_key"], "tools/list",
                                                            headers=auth).json()["result"]["tools"]]
        assert client.delete(f"/tenant/websites/{site['id']}/agent-tokens/{made['id']}", headers=h).status_code == 204
        assert "capture_lead" not in [t["name"] for t in rpc(client, key, "tools/list",
                                                            headers=auth).json()["result"]["tools"]]
        listed = client.get(f"/tenant/websites/{site['id']}/agent-access", headers=h).json()
        assert listed["tokens"] == [] and "token" not in json.dumps(listed["tokens"])


def test_llms_txt_openapi_and_rest_ask():
    with TestClient(app) as client:
        h = _register(client)
        site = _site(client, h, domain="agentco.example")
        key = site["public_key"]
        client.post(f"/tenant/websites/{site['id']}/sources", headers=h, json={
            "kind": "url", "name": "Pricing", "content": "https://agentco.example/pricing"})
        llms = client.get(f"/sites/{key}/llms.txt")
        assert llms.status_code == 200 and llms.headers["content-type"].startswith("text/markdown")
        body = llms.text
        assert body.startswith("# ") and f"/mcp/{key}" in body and "[Pricing](https://agentco.example/pricing)" in body
        doc = client.get(f"/sites/{key}/openapi.json").json()
        assert doc["openapi"].startswith("3.1") and f"/agent/{key}/ask" in doc["paths"]
        assert doc["paths"][f"/agent/{key}/ask"]["post"]["operationId"] == "askWebsite"
        r = client.post(f"/agent/{key}/ask", json={"question": "Do you integrate with HubSpot?"})
        assert r.status_code == 200 and set(r.json()) >= {"answer", "sources", "found"}
        assert client.post(f"/agent/{key}/ask", json={"question": ""}).status_code == 422

        res = rpc(client, key, "resources/list").json()["result"]["resources"]
        assert res and res[0]["uri"] == "https://agentco.example/pricing"
        read = rpc(client, key, "resources/read", {"uri": res[0]["uri"]}).json()["result"]["contents"][0]
        assert read["uri"] == res[0]["uri"] and read["text"]
        assert rpc(client, key, "resources/read", {"uri": "https://elsewhere.example/"}).json()["error"]["code"] == -32002

        # Viewers see, Admins change.
        assert client.get(f"/tenant/websites/{site['id']}/agent-access", headers=h).status_code == 200


def test_agent_calls_are_rate_limited(monkeypatch):
    from app.routes import agent_access

    monkeypatch.setattr(agent_access, "AGENT_RATE_PER_MIN", 3)
    with TestClient(app) as client:
        h = _register(client)
        key = _site(client, h)["public_key"]
        codes = [rpc(client, key, "ping").status_code for _ in range(5)]
        assert codes[:3] == [200, 200, 200] and codes[-1] == 429
