"""
Microsoft 365 email through Microsoft Graph (EMAIL_TRANSPORT=graph): the
client-credentials sign-in, the MIME message posted to sendMail, reusing the
token, readable errors, and the outbox sending through it.

Graph is an httpx.MockTransport, so the real client code path runs.
"""
from __future__ import annotations

import asyncio
import base64
import email
import uuid
from email import policy
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import Settings, get_settings
from app.notify import email as mailer
from app.notify import graph_mail

TENANT = "contoso.onmicrosoft.com"
CLIENT = "11111111-2222-3333-4444-555555555555"
SECRET = "not-a-real-secret"
SENDER = "no-reply@fluidbuddha.test"


class FakeGraph:
    """The two Microsoft endpoints the sender talks to."""

    def __init__(self):
        self.token_requests: list[tuple[str, dict]] = []
        self.sent: list[tuple[str, str, str, bytes]] = []   # sender, auth, type, MIME
        self.token_status = 200
        self.send_status = 202
        self.send_error = {"error": {"code": "ErrorAccessDenied", "message": "Access is denied."}}

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "login.microsoftonline.com":
            self.token_requests.append((request.url.path, parse_qs(request.content.decode())))
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={
                    "error": "invalid_client",
                    "error_description": "AADSTS7000215: Invalid client secret provided."})
            return httpx.Response(200, json={"token_type": "Bearer", "expires_in": 3599,
                                             "access_token": f"tok-{len(self.token_requests)}"})
        if request.url.host == "graph.microsoft.com" and request.url.path.endswith("/sendMail"):
            if self.send_status != 202:
                return httpx.Response(self.send_status, json=self.send_error)
            sender = request.url.path.split("/users/", 1)[1].rsplit("/sendMail", 1)[0]
            self.sent.append((sender, request.headers["authorization"],
                              request.headers["content-type"], base64.b64decode(request.content)))
            return httpx.Response(202)
        return httpx.Response(404)


@pytest.fixture
def graph(monkeypatch):
    fake = FakeGraph()
    monkeypatch.setattr(graph_mail, "_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(graph_mail, "_token", None)
    s = get_settings()   # restored by conftest
    s.email_transport = "graph"
    s.graph_tenant_id, s.graph_client_id, s.graph_client_secret = TENANT, CLIENT, SECRET
    s.smtp_host = ""
    s.smtp_from = f"FluidBuddha <{SENDER}>"
    return fake


def _message(**kw) -> dict:
    row = {"id": 1, "to_addr": "ana@example.com", "subject": "Welcome",
           "text_body": "Hello in text", "html_body": "<p>Hello in html</p>",
           "headers": {"List-Unsubscribe": "<https://x.example/u>"}}
    row.update(kw)
    return row


def _run(coro_fn):
    """Run ``coro_fn(db)`` on a throwaway engine (not the app's shared one)."""
    async def go():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, class_=AsyncSession,
                                          expire_on_commit=False)() as db:
                return await coro_fn(db)
        finally:
            await engine.dispose()
    return asyncio.run(go())


async def _drain(db):
    while any((await mailer.deliver_due(db)).values()):
        pass


async def _outbox_row(db, outbox_id):
    return (await db.execute(text("SELECT * FROM email_outbox WHERE id = :i"),
                             {"i": outbox_id})).mappings().one()


def test_graph_sends_the_mime_message_as_the_sender_mailbox(graph):
    asyncio.run(mailer.send_now(_message()))

    [(path, form)] = graph.token_requests
    assert path == f"/{TENANT}/oauth2/v2.0/token"
    assert form["grant_type"] == ["client_credentials"] and form["client_id"] == [CLIENT]
    assert form["client_secret"] == [SECRET]
    assert form["scope"] == ["https://graph.microsoft.com/.default"]

    [(sender, auth, ctype, mime)] = graph.sent
    assert sender == SENDER and auth == "Bearer tok-1" and ctype == "text/plain"
    assert b"\r\n" in mime   # MIME line endings
    msg = email.message_from_bytes(mime, policy=policy.default)
    assert msg["From"] == f"FluidBuddha <{SENDER}>" and msg["To"] == "ana@example.com"
    assert msg["Subject"] == "Welcome" and msg["List-Unsubscribe"] == "<https://x.example/u>"
    assert "Hello in text" in msg.get_body(("plain",)).get_content()
    assert "Hello in html" in msg.get_body(("html",)).get_content()


def test_the_token_is_reused_and_dropped_after_a_401(graph):
    async def go():
        await mailer.send_now(_message(id=1))
        await mailer.send_now(_message(id=2))
        assert len(graph.token_requests) == 1   # one sign-in for both
        graph.send_status = 401
        graph.send_error = {"error": {"code": "InvalidAuthenticationToken",
                                      "message": "Access token has expired."}}
        with pytest.raises(graph_mail.GraphSendError, match="401"):
            await mailer.send_now(_message(id=3))
        graph.send_status = 202
        await mailer.send_now(_message(id=4))
        assert len(graph.token_requests) == 2   # signed in again

    asyncio.run(go())
    assert [auth for _, auth, _, _ in graph.sent] == ["Bearer tok-1", "Bearer tok-1", "Bearer tok-2"]


def test_refusals_say_why_without_the_secret(graph):
    graph.send_status = 403
    with pytest.raises(graph_mail.GraphSendError) as refused:
        asyncio.run(mailer.send_now(_message()))
    assert "403" in str(refused.value) and "ErrorAccessDenied" in str(refused.value)

    graph.token_status = 401
    graph_mail._token = None
    with pytest.raises(graph_mail.GraphSendError) as bad_secret:
        asyncio.run(mailer.send_now(_message()))
    assert "invalid_client" in str(bad_secret.value) and "AADSTS7000215" in str(bad_secret.value)
    for err in (refused.value, bad_secret.value):
        assert SECRET not in str(err)
    assert graph.sent == []


def test_graph_is_configured_only_with_all_three_settings(graph):
    s = get_settings()
    assert mailer.configured(s)
    s.graph_client_secret = ""
    assert not mailer.configured(s)
    s.app_env = "production"

    async def go(db):
        with pytest.raises(mailer.EmailNotConfigured, match="GRAPH_CLIENT_SECRET"):
            await mailer.enqueue(db, mailer.Email(to="p@example.com", subject="x", text="x"))

    _run(go)


def test_an_unknown_transport_stops_the_start():
    with pytest.raises(ValueError, match="EMAIL_TRANSPORT"):
        Settings(email_transport="sendgrid")


def test_the_outbox_sends_through_graph_and_retries_its_failures(graph):
    tag = uuid.uuid4().hex[:8]

    async def go(db):
        ok = await mailer.enqueue(db, mailer.Email(to=f"g-{tag}@example.com",
                                                   subject=f"Hi {tag}", text="x"))
        await db.commit()
        await _drain(db)
        sent = await _outbox_row(db, ok)
        graph.send_status = 503
        graph.send_error = {"error": {"code": "ServiceUnavailable", "message": "Try later."}}
        bad = await mailer.enqueue(db, mailer.Email(to=f"h-{tag}@example.com",
                                                    subject="x", text="x"))
        await db.commit()
        await _drain(db)
        return sent, await _outbox_row(db, bad)

    sent, retried = _run(go)
    assert sent["status"] == "sent" and sent["attempts"] == 1
    assert retried["status"] == "queued" and "503" in retried["last_error"]
    assert any(f"Hi {tag}".encode() in mime for _, _, _, mime in graph.sent)
