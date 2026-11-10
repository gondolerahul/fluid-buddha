"""Generative experience, Phase 0 (docs/devdocs/generative-experience-plan.md):
plan schema + validator, component manifest, x-fb-* API annotations, data
binding, and generate_page on the plan pipeline."""
from __future__ import annotations

import asyncio
import json

import pytest

from app.apis.registry import SiteApiRegistry, get_site_apis
from app.experience.binding import apply_transforms, bind_plan, select
from app.experience.compose import compose_page, regions_from_sections
from app.experience.manifest import (
    default_manifest,
    clear_manifest_cache,
    load_manifest,
    manifest_from_dict,
)
from app.experience.plan import validate_plan
from app.orchestrator.pagegen import SECTION_TYPES

SPEC = {
    "paths": {
        "/plans": {"get": {
            "operationId": "listPlans", "summary": "Subscription plans",
            "x-fb-entity": "Plan", "x-fb-cache": "public:300s",
            "responses": {"200": {"content": {"application/json": {"example": {
                "plans": [
                    {"name": "Starter", "price": "₹999", "features": ["1 seat"], "rank": 2},
                    {"name": "Scale", "price": "₹9,999", "features": ["50 seats"], "rank": 1},
                ],
            }}}}},
        }},
        "/me/invoices": {"get": {"operationId": "myInvoices", "x-fb-auth": "user"}},
        "/enquiries": {"post": {"operationId": "submitEnquiry", "x-fb-confirm": "card"}},
        "/account": {"delete": {"operationId": "deleteAccount"}},
        "/broken": {"get": {"operationId": "broken"}},
    }
}


def registry() -> SiteApiRegistry:
    return SiteApiRegistry("acme", SPEC)


def run(coro):
    return asyncio.run(coro)


# ---- P0-3: API catalogue annotations ----------------------------------------

def test_annotations_and_defaults():
    reg = registry()
    plans = reg.operation("listPlans")
    assert (plans.effect, plans.entity, plans.cache, plans.auth) == ("read", "Plan", "public:300s", "site")
    assert reg.operation("submitEnquiry").effect == "write"
    assert reg.operation("submitEnquiry").confirm == "card"
    assert reg.operation("deleteAccount").effect == "destructive"
    assert reg.operation("myInvoices").auth == "user"
    bindable = {o.operation_id for o in reg.bindable_operations()}
    assert bindable == {"listPlans", "broken"}  # reads without a user token
    assert reg.operation("nope") is None


def test_simulated_call_returns_documented_example():
    res = run(registry().call("listPlans", {}))
    assert res["simulated"] and res["data"]["plans"][0]["name"] == "Starter"
    # No example → no data (as before).
    assert "data" not in run(registry().call("broken", {}))


# ---- P0-2: manifest ---------------------------------------------------------

def test_default_manifest_covers_builtin_sections():
    m = default_manifest()
    assert sorted(m.ids()) == sorted(f"fb.{t}" for t in SECTION_TYPES)
    assert m.get("fb.hero").renderer == "hero"
    assert m.get("fb.hero").props["title"].required
    assert "fb.pricing_table" in m.to_prompt()


def test_customer_manifest_merges_and_rejects_bad_entries():
    m = manifest_from_dict({"components": [
        {"id": "acme.PlanTable", "renderer": "pricing_table", "purpose": "Plans",
         "use_when": ["compare_plans"],
         "props": {"tiers": {"type": "array", "source": "binding_only", "required": True}}},
        {"id": "nodots", "renderer": "hero"},
        {"id": "acme.Fancy", "renderer": "wc:acme-fancy"},
    ]})
    assert m.get("acme.PlanTable").props["tiers"].source == "binding_only"
    assert m.get("fb.hero") is not None
    assert m.get("nodots") is None and m.get("acme.Fancy") is None
    only = manifest_from_dict({"include_defaults": False, "components": [
        {"id": "acme.Hero", "renderer": "hero"}]})
    assert only.ids() == ["acme.Hero"]


def test_manifest_loads_from_env_file(tmp_path, monkeypatch):
    f = tmp_path / "m.json"
    f.write_text(json.dumps({"components": [{"id": "acme.X", "renderer": "text"}]}), encoding="utf-8")
    monkeypatch.setenv("ACME_ENV_COMPONENT_MANIFEST", str(f))
    clear_manifest_cache()
    try:
        assert load_manifest("acme-env").get("acme.X") is not None
    finally:
        clear_manifest_cache()


# ---- P0-1: plan validator ---------------------------------------------------

def validate(raw, manifest=None):
    return validate_plan(raw, manifest=manifest or default_manifest(), catalogue=registry(),
                         site_key="acme")


def test_valid_plan_passes_with_stable_ids():
    rep = validate({"title": "Pricing", "regions": [
        {"component": "fb.hero", "props": {"title": "Hi"}},
        {"component": "fb.hero", "props": {"title": "Again"}},
        {"id": "Our Plans!", "component": "fb.pricing_table",
         "props": {"tiers": {"bind": "api:listPlans", "path": "$.plans[*]"}}},
    ]})
    assert rep.ok, rep.problems
    assert [r.id for r in rep.plan.regions] == ["hero", "hero-2", "our-plans"]
    assert rep.plan.plan_id.startswith("pl_") and rep.plan.schema == "fb.plan/1"
    # Same shape → same ids.
    rep2 = validate({"regions": [{"component": "fb.hero", "props": {"title": "x"}}]})
    assert rep2.plan.regions[0].id == "hero"


def test_unknown_components_and_missing_required_props_are_dropped():
    rep = validate({"regions": [
        {"component": "fb.bogus"},
        {"component": "fb.text", "props": {"title": "No body"}},
        "junk",
        {"component": "fb.text", "props": {"body": "ok", "extra": 1}},
    ]})
    assert [r.component for r in rep.plan.regions] == ["fb.text"]
    assert "extra" not in rep.plan.regions[0].props
    assert any("unknown component" in d for d in rep.dropped)
    assert any("missing required props body" in p for p in rep.problems)


def test_region_limit_and_coercion():
    rep = validate({"regions": [{"component": "fb.text", "props": {"body": "x" * 5000}}] * 20})
    assert len(rep.plan.regions) == 12
    assert len(rep.plan.regions[0].props["body"]) == 2000
    bad = validate({"regions": [{"component": "fb.chart",
                                 "props": {"chart_type": "donut", "data": [{"label": "a", "value": 1}]}}]})
    assert "chart_type" not in bad.plan.regions[0].props
    assert any("chart_type" in p for p in bad.problems)


def test_source_rules():
    m = manifest_from_dict({"components": [{
        "id": "acme.PlanTable", "renderer": "pricing_table",
        "props": {"title": {"type": "string", "source": "model_text"},
                  "tiers": {"type": "array", "source": "binding_only", "required": True}}}]})
    typed = validate({"regions": [{"component": "acme.PlanTable",
                                   "props": {"tiers": [{"name": "Made up", "price": "₹1"}]}}]}, m)
    assert typed.plan.regions == [] and any("must be a binding" in p for p in typed.problems)
    bound_title = validate({"regions": [{"component": "acme.PlanTable", "props": {
        "title": {"bind": "api:listPlans"},
        "tiers": {"bind": "api:listPlans", "path": "$.plans[*]"}}}]}, m)
    assert len(bound_title.plan.regions) == 1
    assert "title" not in bound_title.plan.regions[0].props
    assert any("must be written, not bound" in p for p in bound_title.problems)


@pytest.mark.parametrize("binding,expect", [
    ({"bind": "api:nope"}, "unknown operation"),
    ({"bind": "api:submitEnquiry"}, "only read operations"),
    ({"bind": "api:myInvoices"}, "signed-in user"),
    ({"bind": "ctx.secret"}, "not available"),
    ({"bind": "http://evil"}, "must be 'api:"),
    ({"bind": "api:listPlans", "path": "plans.0"}, "path"),
    ({"bind": "api:listPlans", "transform": ["eval:1+1"]}, "unsupported transform"),
    ({"bind": "api:listPlans", "params": {"q": "ctx.password"}}, "unknown context"),
])
def test_bad_bindings_are_refused(binding, expect):
    rep = validate({"regions": [{"component": "fb.pricing_table", "props": {"tiers": binding}}]})
    assert rep.plan.regions == []
    assert any(expect in p for p in rep.problems), rep.problems


def test_actions():
    rep = validate({
        "actions": [
            {"id": "enquire", "ref": "api:submitEnquiry", "confirm": "none"},
            {"id": "wipe", "ref": "api:deleteAccount"},
            {"id": "trial", "ref": "action:trial"},
            {"id": "peek", "ref": "api:listPlans"},
            {"id": "bad", "ref": "javascript:alert(1)"},
        ],
        "regions": [
            {"component": "fb.cta", "props": {"title": "Go", "cta_label": "Start", "action": "trial"}},
            {"component": "fb.cta", "props": {"title": "Go", "cta_label": "x", "action": "ghost"}},
        ],
    })
    confirms = {a.id: a.confirm for a in rep.plan.actions}
    assert confirms == {"enquire": "card", "wipe": "typed", "trial": "card"}
    assert rep.plan.regions[0].props["action"] == "trial"
    assert "action" not in rep.plan.regions[1].props
    assert any("bind it instead" in p for p in rep.problems)
    assert any("unknown action" in p for p in rep.problems)


def test_must_include_policy():
    rep = validate({"policies": {"must_include": ["fb.faq"]},
                    "regions": [{"component": "fb.hero", "props": {"title": "x"}}]})
    assert any("must include component fb.faq" in p for p in rep.problems)


def test_garbage_input_never_raises():
    for raw in (None, "x", [], {"regions": "nope"}, {"regions": [None, 1, {"component": None}]}):
        rep = validate(raw)
        assert rep.plan.regions == []


# ---- P0-4: binding ----------------------------------------------------------

def test_select_and_transforms():
    data = {"a": {"b": [{"n": 2}, {"n": 1}, {"m": 0}]}}
    assert select(data, "$.a.b[0].n") == 2
    assert select(data, "$.a.b[*].n") == [2, 1]
    assert select(data, "$.missing") is None
    assert select(data, "$") is data
    items = select(data, "$.a.b[*]")
    assert apply_transforms(items, ["sort_by:n"])[0] == {"n": 1}
    assert apply_transforms(items, ["sort_by_desc:n", "limit:1"]) == [{"n": 2}]
    assert apply_transforms(items, ["count"]) == 3
    assert apply_transforms(items, ["first"]) == {"n": 2}
    assert apply_transforms([], ["first"]) is None


def test_bind_plan_states_and_isolation():
    calls = []

    class Reg:
        def operation(self, op):
            return registry().operation(op)

        async def call(self, op, params):
            calls.append((op, params))
            if op == "broken":
                return {"ok": False, "error": "request_failed"}
            return await registry().call(op, params)

    m = default_manifest()
    rep = validate_plan({"regions": [
        {"id": "plans", "component": "fb.pricing_table", "props": {
            "title": "Plans",
            "tiers": {"bind": "api:listPlans", "path": "$.plans[*]",
                      "params": {"currency": "ctx.currency"}, "transform": ["sort_by:rank"]}}},
        {"id": "again", "component": "fb.pricing_table", "props": {
            "tiers": {"bind": "api:listPlans", "path": "$.plans[*]",
                      "params": {"currency": "ctx.currency"}}}},
        {"id": "nothing", "component": "fb.faq", "props": {
            "items": {"bind": "api:listPlans", "path": "$.faqs[*]"}}},
        {"id": "down", "component": "fb.faq", "props": {"items": {"bind": "api:broken"}}},
        {"id": "lang", "component": "fb.media", "props": {"src": {"bind": "ctx.lang"}}},
    ]}, manifest=m, catalogue=Reg(), site_key="acme")
    assert rep.ok, rep.problems
    bound = run(bind_plan(rep.plan, manifest=m, registry=Reg(), ctx={"currency": "INR", "lang": "hi"}))
    by_id = {b.id: b for b in bound}
    assert [t["name"] for t in by_id["plans"].props["tiers"]] == ["Scale", "Starter"]
    assert by_id["plans"].state == "ready"
    assert by_id["nothing"].state == "empty"
    assert by_id["down"].state == "error"
    assert by_id["lang"].props["src"] == "hi"
    # One call per distinct (operation, params); ctx resolved into params.
    assert calls.count(("listPlans", {"currency": "INR"})) == 1
    assert by_id["plans"].to_section()["type"] == "pricing_table"


# ---- P0-5: generate_page on the plan pipeline -------------------------------

def test_regions_from_sections():
    assert regions_from_sections([{"type": "hero", "props": {"title": "x"}}, "junk", {"props": {}}]) == [
        {"component": "fb.hero", "props": {"title": "x"}}]


def test_compose_page_binds_and_hides_values_from_the_model(tmp_path, monkeypatch):
    spec = tmp_path / "acme.json"
    spec.write_text(json.dumps(SPEC), encoding="utf-8")
    monkeypatch.setenv("ACME_COMPOSE_OPENAPI", str(spec))
    get_site_apis.cache_clear()
    try:
        page, result = run(compose_page({
            "title": "Pricing",
            "regions": [
                {"component": "fb.hero", "props": {"title": "Plans for you", "action": "trial"}},
                {"id": "plans", "component": "fb.pricing_table",
                 "props": {"tiers": {"bind": "api:listPlans", "path": "$.plans[*]"}}},
            ],
            "actions": [{"id": "trial", "ref": "action:trial"}],
        }, site_key="acme-compose", sync_id="page_abc", ctx={"currency": "INR"}))
    finally:
        get_site_apis.cache_clear()
    wire = page.to_dict()
    assert wire["plan_id"] == result["plan_id"] and wire["sync_id"] == "page_abc"
    assert [s["id"] for s in wire["sections"]] == ["hero", "plans"]
    assert wire["sections"][1]["props"]["tiers"][1]["name"] == "Scale"
    assert wire["sections"][1]["type"] == "pricing_table" and wire["sections"][1]["state"] == "ready"
    assert wire["actions"] == [{"id": "trial", "ref": "action:trial", "confirm": "card"}]
    assert "plan" not in wire  # the plan stays server side
    # Model isolation: the tool result carries no bound values.
    assert "Scale" not in json.dumps(result) and "₹" not in json.dumps(result)
    assert result["region_count"] == 2 and result["ok"]


def test_compose_page_accepts_legacy_sections():
    page, result = run(compose_page({"title": "Hi", "sections": [
        {"type": "hero", "props": {"title": "H"}}, {"type": "bogus"},
        {"type": "text", "props": {"body": "b"}}]}, site_key="nosuchsite", sync_id="page_1"))
    assert [s["type"] for s in page.sections] == ["hero", "text"]
    assert result["section_count"] == 2 and result["dropped"]


def test_extreme_brief_lists_components_and_bindable_data(tmp_path, monkeypatch):
    from app.orchestrator.pagegen import build_extreme_brief

    spec = tmp_path / "acme.json"
    spec.write_text(json.dumps(SPEC), encoding="utf-8")
    monkeypatch.setenv("ACME_BRIEF_OPENAPI", str(spec))
    get_site_apis.cache_clear()
    try:
        brief = build_extreme_brief("acme-brief")
    finally:
        get_site_apis.cache_clear()
    assert "PAGE COMPONENTS" in brief and "fb.pricing_table" in brief
    assert "BINDABLE DATA" in brief and "listPlans" in brief
    assert "myInvoices" not in brief.split("BINDABLE DATA", 1)[1].split("SITE APIS", 1)[0]
