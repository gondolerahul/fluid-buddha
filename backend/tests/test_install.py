"""
Install surfaces (M2-10): the loader script every plugin points at, and the
site settings a key-only install picks up from the server.
"""
from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.routes.widget import loader_script


def _register(client: TestClient) -> dict:
    tok = client.post("/auth/register", json={
        "email": f"inst_{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_loader_is_a_cacheable_script_pointing_at_the_widget():
    with TestClient(app) as client:
        r = client.get("/widget/loader.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "max-age=300" in r.headers["cache-control"]
    # Script tags from any site may load it.
    assert r.headers["cross-origin-resource-policy"] == "cross-origin"
    sdk = get_settings().widget_sdk_base.rstrip("/") + "/fluid-buddha.global.js"
    assert json.dumps(sdk) in r.text
    # Copies the embed's data-* attributes, derives the backend from its own
    # address, and says when the widget code has arrived.
    for part in ("data-", "data-backend", "data-api", "fluidbuddha:ready", "__fluidBuddhaLoader"):
        assert part in r.text


def test_loader_cannot_be_broken_out_of_by_the_configured_url():
    js = loader_script('https://cdn.example.com/x"</script><script>alert(1)//')
    assert "</script>" not in js
    assert '\\"' in js  # the quote stays inside the string literal


def test_enrol_defaults_carry_the_sites_accent_for_key_only_installs():
    with TestClient(app) as client:
        h = _register(client)
        site = client.post("/tenant/websites", json={
            "name": "Accent Co", "accent": "#123abc", "design": "level3"}, headers=h).json()
        r = client.post("/experiment/enroll", content=json.dumps(
            {"key": site["public_key"], "visitor": "visitor-accent-1"}),
            headers={"Content-Type": "text/plain"})
        assert r.status_code == 200, r.text
        d = r.json()["defaults"]
        assert d["accent"] == "#123abc" and d["design"] == "level3"


def _sections(tpl: str) -> dict:
    import re
    parts = re.split(r"^___([A-Z_]+)___\n", tpl, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def test_gtm_template_may_only_inject_this_servers_loader():
    from app.integrations.gtm import build_template
    tpl = build_template("https://api.example.com/")
    s = _sections(tpl)
    assert list(s) == ["TERMS_OF_SERVICE", "INFO", "TEMPLATE_PARAMETERS",
                       "SANDBOXED_JS_FOR_WEB_TEMPLATE", "WEB_PERMISSIONS", "TESTS", "NOTES"]
    info = json.loads(s["INFO"])
    assert info["type"] == "TAG" and info["containerContexts"] == ["WEB"]
    params = {p["name"]: p for p in json.loads(s["TEMPLATE_PARAMETERS"])}
    assert set(params) == {"widgetKey", "position", "lang"}
    assert {"type": "NON_EMPTY"} in params["widgetKey"]["valueValidators"]
    perms = json.loads(s["WEB_PERMISSIONS"])
    assert len(perms) == 1  # nothing beyond injecting the loader
    inject = perms[0]["instance"]
    assert inject["key"]["publicId"] == "inject_script"
    urls = [i["string"] for i in inject["param"][0]["value"]["listItem"]]
    assert urls == ["https://api.example.com/widget/loader.js*"]
    code = s["SANDBOXED_JS_FOR_WEB_TEMPLATE"]
    assert "'https://api.example.com/widget/loader.js'" in code
    assert "encodeUriComponent(data.widgetKey)" in code
    assert "scenarios:" in s["TESTS"] and "runCode" in s["TESTS"]


def test_gtm_template_refuses_an_unusable_server_address():
    import pytest
    from app.integrations.gtm import build_template
    for bad in ("ftp://x.example", "api.example.com", "https://x.example/'+alert(1)+'"):
        with pytest.raises(ValueError):
            build_template(bad)


def test_gtm_template_download():
    with TestClient(app) as client:
        r = client.get("/widget/gtm-template.tpl")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert get_settings().public_api_url.rstrip("/") + "/widget/loader.js*" in r.text
