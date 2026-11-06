"""
M2-0: the email outbox (queue, send over SMTP, retry, give up, dedupe) and the
job scheduler's one-replica-at-a-time lock.

SMTP is a tiny in-process server speaking just enough of the protocol for
``smtplib``, so the real client code path runs.
"""
from __future__ import annotations

import asyncio
import email
import socketserver
import threading
import uuid
from email import policy

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.jobs.scheduler import Job, lock_key, run_locked
from app.notify import email as mailer
from app.notify import templates


class _SMTPHandler(socketserver.StreamRequestHandler):
    def handle(self):
        srv = self.server
        self.wfile.write(b"220 fake ESMTP\r\n")
        rcpts, data_mode, buf = [], False, []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            if data_mode:
                if line == b".\r\n":
                    srv.messages.append((rcpts[:], b"".join(buf)))
                    rcpts, buf, data_mode = [], [], False
                    self.wfile.write(b"250 queued\r\n")
                else:
                    buf.append(line[1:] if line.startswith(b"..") else line)
                continue
            cmd = line.decode(errors="replace").strip()
            up = cmd.upper()
            if up.startswith(("EHLO", "HELO")):
                self.wfile.write(b"250-fake\r\n250 8BITMIME\r\n")
            elif up.startswith("MAIL FROM"):
                self.wfile.write(b"250 ok\r\n")
            elif up.startswith("RCPT TO"):
                if "reject" in cmd.lower():
                    self.wfile.write(b"550 no such user\r\n")
                else:
                    rcpts.append(cmd.split(":", 1)[1].strip(" <>"))
                    self.wfile.write(b"250 ok\r\n")
            elif up == "DATA":
                data_mode = True
                self.wfile.write(b"354 go ahead\r\n")
            elif up == "QUIT":
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


@pytest.fixture
def smtp_server():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _SMTPHandler)
    server.daemon_threads = True
    server.messages = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    s = get_settings()
    s.smtp_host, s.smtp_port, s.smtp_security = "127.0.0.1", server.server_address[1], "none"
    s.smtp_username = ""
    s.smtp_from = "FluidBuddha <no-reply@fluidbuddha.test>"
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _run(coro_fn):
    """Run ``coro_fn(db)`` on a throwaway engine (not the app's shared one)."""
    async def go():
        engine = create_async_engine(get_settings().cortex_db_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, class_=AsyncSession,
                                          expire_on_commit=False)() as db:
                return await coro_fn(db, engine)
        finally:
            await engine.dispose()
    return asyncio.run(go())


async def _drain(db):
    """Send everything queued now (other tests' rows included)."""
    totals = {"sent": 0, "retried": 0, "failed": 0}
    while True:
        c = await mailer.deliver_due(db)
        for k in totals:
            totals[k] += c[k]
        if not any(c.values()):
            return totals


async def _row(db, outbox_id):
    return (await db.execute(text("SELECT * FROM email_outbox WHERE id = :i"),
                             {"i": outbox_id})).mappings().one()


def test_queued_email_is_sent_over_smtp_once(smtp_server):
    tag = uuid.uuid4().hex[:8]

    async def go(db, _):
        oid = await mailer.enqueue(db, mailer.Email(
            to=f"ana-{tag}@example.com", subject=f"Welcome {tag}", text="Hello in text",
            html=templates.layout("Welcome", templates.paragraph("Hello <b>in</b> html")),
            kind="test", headers={"List-Unsubscribe": "<https://x.example/u>"},
            idem_key=f"test:{tag}"))
        again = await mailer.enqueue(db, mailer.Email(
            to=f"ana-{tag}@example.com", subject="dup", text="dup", idem_key=f"test:{tag}"))
        await db.commit()
        assert oid and again is None
        await _drain(db)
        return await _row(db, oid)

    row = _run(go)
    assert row["status"] == "sent" and row["attempts"] == 1 and row["sent_at"]
    mine = [m for m in smtp_server.messages if m[0] == [f"ana-{tag}@example.com"]]
    assert len(mine) == 1
    msg = email.message_from_bytes(mine[0][1], policy=policy.default)
    assert msg["Subject"] == f"Welcome {tag}" and msg["List-Unsubscribe"]
    assert msg["From"] == "FluidBuddha <no-reply@fluidbuddha.test>"
    assert "Hello in text" in msg.get_body(("plain",)).get_content()
    assert "Hello &lt;b&gt;in&lt;/b&gt; html" in msg.get_body(("html",)).get_content()


def test_failed_send_is_retried_with_backoff_then_given_up(smtp_server):
    tag = uuid.uuid4().hex[:8]

    async def go(db, _):
        oid = await mailer.enqueue(db, mailer.Email(
            to=f"reject-{tag}@example.com", subject="x", text="x"))
        await db.commit()
        await _drain(db)
        first = await _row(db, oid)
        # Make it due again on its last attempt.
        await db.execute(text("UPDATE email_outbox SET next_attempt_at = now(), attempts = :a "
                              "WHERE id = :i"), {"a": mailer.MAX_ATTEMPTS - 1, "i": oid})
        await db.commit()
        await _drain(db)
        return first, await _row(db, oid)

    first, last = _run(go)
    assert first["status"] == "queued" and first["attempts"] == 1
    assert "550" in first["last_error"] and first["next_attempt_at"] > first["created_at"]
    assert last["status"] == "failed" and last["attempts"] == mailer.MAX_ATTEMPTS


def test_a_send_interrupted_mid_way_is_picked_up_again(smtp_server):
    tag = uuid.uuid4().hex[:8]

    async def go(db, _):
        oid = await mailer.enqueue(db, mailer.Email(to=f"s-{tag}@example.com",
                                                    subject="x", text="x"))
        await db.execute(text("UPDATE email_outbox SET status = 'sending', "
                              "claimed_at = now() - interval '1 hour' WHERE id = :i"), {"i": oid})
        await db.commit()
        await _drain(db)
        return await _row(db, oid)

    assert _run(go)["status"] == "sent"


def test_without_smtp_dev_logs_and_production_refuses():
    s = get_settings()
    s.smtp_host = ""

    async def dev(db, _):
        oid = await mailer.enqueue(db, mailer.Email(to="dev@example.com", subject="x", text="x"))
        await db.commit()
        await _drain(db)
        return await _row(db, oid)

    assert _run(dev)["status"] == "sent"   # logged, not sent

    s.app_env = "production"

    async def prod(db, _):
        with pytest.raises(mailer.EmailNotConfigured):
            await mailer.enqueue(db, mailer.Email(to="p@example.com", subject="x", text="x"))

    _run(prod)


def test_bad_addresses_and_header_injection_are_refused():
    async def go(db, _):
        for bad in (mailer.Email(to="not-an-address", subject="x", text="x"),
                    mailer.Email(to="a@b.co\nBcc: c@d.co", subject="x", text="x"),
                    mailer.Email(to="a@b.co", subject="hi\r\nBcc: c@d.co", text="x")):
            with pytest.raises(ValueError):
                await mailer.enqueue(db, bad)

    _run(go)
    with pytest.raises(ValueError):
        templates.button("Open", "javascript:alert(1)")


def test_a_job_runs_on_one_replica_at_a_time():
    ran: list[str] = []

    async def go(db, engine):
        async def work():
            ran.append("x")

        job = Job(f"test-{uuid.uuid4().hex[:6]}", 60, work)
        # Another replica holds the job's lock: this one skips.
        async with engine.connect() as other:
            await other.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_key(job.name)})
            await other.commit()
            skipped = await run_locked(job, engine)
            await other.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key(job.name)})
            await other.commit()
        ran_after = await run_locked(job, engine)
        return skipped, ran_after

    skipped, ran_after = _run(go)
    assert skipped is False and ran_after is True and ran == ["x"]
