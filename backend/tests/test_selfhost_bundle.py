"""
The self-hosted bundle (M3-5) stays consistent: every service restarts, is
health-checked and rotates its logs; only the edge and the TURN relay are
reachable from outside; the backend runs as a licensed production install
with its secrets required; every variable the Compose file reads is in the
.env template; the scripts are strict and LF. CI also runs
``docker compose config`` on it.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "deploy" / "selfhost"


def _compose() -> dict:
    return yaml.safe_load((BUNDLE / "docker-compose.yml").read_text(encoding="utf-8"))


def test_every_service_restarts_is_checked_and_rotates_logs():
    services = _compose()["services"]
    assert set(services) >= {"web", "backend", "console", "postgres", "redis", "coturn"}
    image_checks = {"backend": ROOT / "backend" / "Dockerfile", "console": ROOT / "fluid-buddha-frontend" / "Dockerfile"}
    for name, svc in services.items():
        assert svc.get("restart") == "unless-stopped", name
        opts = (svc.get("logging") or {}).get("options") or {}
        assert opts.get("max-size") and opts.get("max-file"), f"{name} rotates its logs"
        if name in image_checks:
            assert "HEALTHCHECK" in image_checks[name].read_text(encoding="utf-8"), name
        else:
            assert svc.get("healthcheck", {}).get("test"), f"{name} has a health check"


def test_only_the_edge_and_the_relay_are_exposed():
    services = _compose()["services"]
    exposed = {n for n, s in services.items() if s.get("ports")}
    assert exposed == {"web", "coturn"}
    assert services["coturn"].get("profiles") == ["voice"]


def test_the_backend_is_a_licensed_production_install():
    env = _compose()["services"]["backend"]["environment"]
    assert env["APP_ENV"] == "production" and env["SELF_HOSTED"] == "true"
    for secret in ("JWT_SECRET", "SECRETS_KEY"):
        assert ":?" in env[secret], f"{secret} must be set"
    assert ":?" in env["CORTEX_DB_URL"] and env["SESSION_COOKIE_SECURE"] == "true"
    assert _compose()["services"]["backend"]["stop_grace_period"], "voice sessions drain on stop"


def test_every_variable_is_in_the_env_template():
    text = (BUNDLE / "docker-compose.yml").read_text(encoding="utf-8")
    used = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", text))
    template = (BUNDLE / ".env.example").read_text(encoding="utf-8")
    defined = set(re.findall(r"^([A-Z_][A-Z0-9_]*)=", template, re.M))
    assert used - defined == set(), f"missing from .env.example: {sorted(used - defined)}"
    caddy = (BUNDLE / "Caddyfile").read_text(encoding="utf-8")
    assert "{$API_DOMAIN}" in caddy and "{$CONSOLE_DOMAIN}" in caddy and "/srv/sdk" in caddy


def test_scripts_are_strict_and_lf():
    scripts = sorted((BUNDLE / "bin").glob("*.sh"))
    assert {p.name for p in scripts} >= {"install.sh", "backup.sh", "restore.sh", "upgrade.sh",
                                         "export-images.sh", "import-images.sh"}
    for p in scripts:
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"{p.name} has CRLF line endings"
        assert raw.startswith(b"#!/usr/bin/env bash") and b"set -euo pipefail" in raw, p.name
    gitattributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in gitattributes
    assert "\\r$//" in (ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")


def test_the_runbooks_cover_the_acceptance():
    readme = (BUNDLE / "README.md").read_text(encoding="utf-8")
    for section in ("## Install", "## Licence", "## Models", "## Upgrade", "## Backups", "## Restore",
                    "## Point-in-time recovery", "## Air-gapped", "## TLS"):
        assert section in readme, section
