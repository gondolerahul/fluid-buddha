"""
Path-scoped CORS (docs/defects.md D-21): the public widget surface may be open
to any origin, but the admin API answers only the console's origins.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.cors import ScopedCORSMiddleware


def _client(public: list[str], admin: list[str]) -> TestClient:
    app = FastAPI()

    @app.post("/chat")
    def chat() -> dict:
        return {"ok": True}

    @app.get("/tenant/websites")
    def websites() -> dict:
        return {"ok": True}

    @app.post("/auth/login")
    def login() -> dict:
        return {"ok": True}

    app.add_middleware(ScopedCORSMiddleware, public_origins=public, admin_origins=admin)
    return TestClient(app)


def _preflight(client: TestClient, path: str, origin: str, method: str = "POST"):
    return client.options(path, headers={
        "Origin": origin, "Access-Control-Request-Method": method,
    })


CONSOLE = "http://localhost:3001"
STRANGER = "https://some-customer-site.example"


def test_open_widget_surface_does_not_open_admin_api():
    c = _client(["*"], [CONSOLE])
    # Any site may embed the widget.
    r = _preflight(c, "/chat", STRANGER)
    assert r.headers.get("access-control-allow-origin") == STRANGER
    assert "access-control-allow-credentials" not in r.headers
    # ...but the admin API refuses that origin and admits the console.
    for path, method in (("/tenant/websites", "GET"), ("/auth/login", "POST")):
        assert "access-control-allow-origin" not in _preflight(c, path, STRANGER, method).headers
        ok = _preflight(c, path, CONSOLE, method)
        assert ok.headers.get("access-control-allow-origin") == CONSOLE
        assert ok.headers.get("access-control-allow-credentials") == "true"


def test_explicit_public_list_is_enforced():
    c = _client(["http://localhost:4000"], [CONSOLE])
    assert "access-control-allow-origin" not in _preflight(c, "/chat", STRANGER).headers
    assert _preflight(c, "/chat", "http://localhost:4000").headers.get(
        "access-control-allow-origin") == "http://localhost:4000"
