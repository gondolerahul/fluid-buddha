"""
Site API registry (Extreme intelligence).

The website owner supplies per-site OpenAPI spec(s) describing enquiry / data
APIs. The Heavy Thinker can then call ``call_site_api(operation_id, params)`` to
pull live data or submit an enquiry while composing a runtime page.

Safety: only operations declared in the spec are callable; the live base URL and
auth header come from per-site env (never from the model). With no base URL
configured (or in mock mode) calls are *simulated* deterministically so the flow
is fully demonstrable offline.

Resolution mirrors the content/design pipelines:
  ``<SITE>_OPENAPI`` (path) — or ``OPENAPI_DIR/<site>.json``
  ``<SITE>_API_BASE_URL`` — live base URL (optional)
  ``<SITE>_API_AUTH`` — value for the Authorization header (optional)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.config import get_settings

logger = logging.getLogger(__name__)

_HTTP_METHODS = ("get", "post", "put", "patch", "delete")


@dataclass
class ApiOperation:
    operation_id: str
    method: str
    path: str
    summary: str


class SiteApiRegistry:
    def __init__(
        self, site_key: str, spec: dict[str, Any] | None,
        base_url: str = "", auth: str = "",
    ) -> None:
        self.site_key = site_key
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self._ops: dict[str, dict[str, Any]] = {}
        self._parse(spec or {})

    def _parse(self, spec: dict[str, Any]) -> None:
        paths = spec.get("paths") or {}
        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, op in methods.items():
                if method.lower() not in _HTTP_METHODS or not isinstance(op, dict):
                    continue
                op_id = op.get("operationId") or f"{method.lower()}_{path.strip('/').replace('/', '_')}"
                self._ops[op_id] = {
                    "method": method.upper(),
                    "path": path,
                    "summary": op.get("summary") or op.get("description") or "",
                }

    def operations(self) -> list[ApiOperation]:
        return [
            ApiOperation(op_id, o["method"], o["path"], o["summary"])
            for op_id, o in self._ops.items()
        ]

    def to_prompt(self) -> str:
        ops = self.operations()
        if not ops:
            return ""
        listed = "; ".join(f'{o.operation_id} ({o.method} {o.path}) — {o.summary}' for o in ops)
        return (
            "SITE APIS — call `call_site_api` with one of these EXACT operation_ids "
            "to pull data or submit an enquiry: " + listed + "."
        )

    async def call(self, operation_id: str, params: dict[str, Any] | None) -> dict[str, Any]:
        params = params or {}
        op = self._ops.get(operation_id)
        if not op:
            return {"ok": False, "error": "unknown_operation",
                    "available": list(self._ops.keys())}

        # Simulate when there is no live endpoint configured (offline / mock).
        if not self.base_url or get_settings().mock_ai:
            return {
                "ok": True, "simulated": True, "operation_id": operation_id,
                "echo": params,
                "note": "Simulated response — no live API base URL is configured "
                        "for this site.",
            }

        url = self.base_url + self._fill_path(op["path"], params)
        headers = {"Accept": "application/json"}
        if self.auth:
            headers["Authorization"] = self.auth
        try:
            import httpx  # local import keeps it optional

            async with httpx.AsyncClient(timeout=10.0) as client:
                method = op["method"]
                if method in ("POST", "PUT", "PATCH"):
                    resp = await client.request(method, url, json=params, headers=headers)
                else:
                    resp = await client.request(method, url, params=params, headers=headers)
            data: Any
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return {"ok": resp.is_success, "status": resp.status_code, "data": data}
        except Exception as exc:
            logger.warning("call_site_api %s failed: %s", operation_id, exc)
            return {"ok": False, "error": "request_failed", "detail": str(exc)}

    @staticmethod
    def _fill_path(path: str, params: dict[str, Any]) -> str:
        # Percent-encode each value (including "/", "?", "#") so a model-supplied
        # param can only fill its own path segment, never add segments, a query
        # or a fragment (e.g. "../../admin").
        out = path
        for k, v in params.items():
            out = out.replace("{" + k + "}", quote(str(v), safe=""))
        return out


def _env_key(site_key: str) -> str:
    return site_key.upper().replace("-", "_")


def _spec_path(site_key: str) -> Path | None:
    override = os.getenv(f"{_env_key(site_key)}_OPENAPI")
    if override:
        return Path(override)
    base = os.getenv("OPENAPI_DIR")
    if base:
        p = Path(base) / f"{site_key}.json"
        if p.exists():
            return p
    return None


@lru_cache(maxsize=16)
def get_site_apis(site_key: str) -> SiteApiRegistry:
    path = _spec_path(site_key)
    spec: dict[str, Any] = {}
    if path and path.exists():
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            logger.info("loaded OpenAPI spec for %s from %s", site_key, path)
        except Exception as exc:
            logger.warning("failed to read OpenAPI spec %s: %s", path, exc)
    base_url = os.getenv(f"{_env_key(site_key)}_API_BASE_URL", "")
    auth = os.getenv(f"{_env_key(site_key)}_API_AUTH", "")
    return SiteApiRegistry(site_key, spec, base_url=base_url, auth=auth)
