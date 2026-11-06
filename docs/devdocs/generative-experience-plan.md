# FluidBuddha — Generative Experience: implementation plan

**Date:** 2026-11-06 · **Builds on:**
[GenerativeExperienceStrategy.md](../product-docs/strategy/GenerativeExperienceStrategy.md)
(the "§" references below point at it, and "D1–D10" / "Q11–Q14" at its §10),
[TechnicalSpecification.md](../product-docs/version_1.0/TechnicalSpecification.md) (v1.0
baseline, branch `m2/foundations`, commit `12e325e`).

This turns the strategy's §9 roadmap (Phases 0–6) into buildable epics. Each epic lists
**what to build** (with the code it touches), **acceptance**, and **tests**. Phase 0 is
broken down to task level because it is being built now. Later phases are at epic level and
get their own breakdown when they start.

Legend: ✅ done · 🟡 in progress · ⬜ not started · ⏱️ effort S/M/L (rough).

---

## Part A — Ground rules for the build

1. **Backwards compatible on the wire.** `DATA/render_page` keeps its v1.0 shape
   (`{sync_id, title, sections[]}`). New fields are additive, so old widgets keep working
   and new widgets accept old payloads.
2. **One validator, every path.** Every plan, whether from the model, the cache, a pinned
   layout or the mock engine, passes `validate_plan` before it reaches a client (§3.2.6).
3. **Model isolation.** Bound values (API data) never go back into the model's tool result.
   The model gets `{ok, sync_id, regions, problems}` only (§4.6).
4. **Config first by file and env, console later.** New per-site inputs (component
   manifest) follow the existing pattern (`<SITE>_…` env or `…_DIR/<site>.json`), as the
   design system and OpenAPI spec do today. Console management is its own epic (P0-7).
5. **Mock mode stays fully demonstrable.** `MOCK_AI=true` exercises the new paths
   end to end.
6. **Tests with every epic.** Backend: pytest in `backend/tests/`. SDK: assertions in
   `fluid-buddha-sdk/test/smoke.mjs`.

---

## Part B — Phase 0: Foundations (enables everything)

Goal (§9 Phase 0): the existing Extreme `generate_page` runs on the Experience Plan schema
with bindings and passes the validator.

New backend package: `backend/app/experience/` (plan, manifest, binding, compose).

### P0-1 · Experience Plan schema v1 and validator ✅ ⏱️M

**Build** (`app/experience/plan.py`):
- Plan model `fb.plan/1` (§3.3): `plan_id`, `schema`, `site_key`, `title`, `intent`,
  `layout`, `theme`, `regions[]` (`id`, `component`, `props`), `actions[]` (`id`, `ref`,
  `confirm`), `policies`, `provenance`.
- `validate_plan(raw, manifest, catalogue) → PlanReport(plan, problems, dropped)`:
  - unknown components are dropped (recorded in `dropped`);
  - region ids are slugs, unique, and **stable**: a missing id derives from the component's
    short name (`hero`, `hero-2`), so the same plan shape gives the same ids (§6.3);
  - props are checked against the manifest prop specs (type, required, `max_items`,
    `max_length`, `enum`) and the **`source` rule**: `binding_only` props must be a binding,
    `model_text` props must be literal, `either` accepts both;
  - bindings are checked against the catalogue: `api:<op>` must exist and be a `read`
    operation; `ctx.<path>` only from an allow-list; unknown kinds are rejected;
  - at most 12 regions (as `normalize_page` today); unknown props dropped;
  - `policies.must_include` components missing from the plan are reported.
- `plan_id` = `pl_<hex10>`.

**Acceptance:** malformed model output always yields a safe plan (possibly empty) plus a
list of problems the model can act on; a valid plan passes unchanged.

**Tests:** `tests/test_experience.py` (schema, id stability, source rules, bindings,
limits, must-include).

### P0-2 · Component manifest and default manifest ✅ ⏱️M

**Build** (`app/experience/manifest.py`):
- `ManifestEntry`: `id`, `version`, `purpose`, `use_when`, `avoid_when`, `props`
  (`PropSpec`: `type`, `source`, `required`, `max_items`, `max_length`, `enum`),
  `actions`, `renderer` (the SDK section type that draws it), `a11y`, `agent`, `ssr`.
- `default_manifest()`: the 14 built-in section types (`pagegen.SECTION_TYPES`) as
  `fb.<type>` entries with prop specs. Props that carry facts customers own (pricing tiers,
  logos, testimonials) are `either`, so they can be bound to an API.
- Per-site manifest from `<SITE>_COMPONENT_MANIFEST` or `COMPONENT_MANIFEST_DIR/<site>.json`,
  merged over the default (customer entries win; a customer can disable defaults with
  `"include_defaults": false`).
- `to_prompt()` for the planner: component ids, purpose, props with their source rule.

**Acceptance:** without configuration the catalogue is exactly today's 14 sections;
with a manifest file the planner sees the customer's components.

### P0-3 · API catalogue annotations ✅ ⏱️S

**Build** (`app/apis/registry.py`):
- Parse `x-fb-effect` (`read` · `write` · `destructive`; default from the HTTP method:
  GET/HEAD → read, DELETE → destructive, else write), `x-fb-entity`, `x-fb-cache`,
  `x-fb-auth` (`site` · `user` · `none`; default `site`), `x-fb-pii` (field paths),
  `x-fb-confirm` (`none` · `card` · `typed`) on each operation (§4.2.3).
- `operation(op_id)` accessor; `bindable_operations()` = read operations not needing a
  user token (user auth comes in Phase 6).
- Prompt lists effect next to each operation.

**Acceptance:** existing specs without annotations behave as before; annotations are
exposed on `ApiOperation`.

### P0-4 · Data binding engine (server-side, public data) ✅ ⏱️M

**Build** (`app/experience/binding.py`):
- Binding reference: `{"bind": "api:<op>" | "ctx.<path>", "path": "$…", "params": {…},
  "transform": [...]}` (§4.6).
- JSONPath subset: `$`, `.key`, `[n]`, `[*]`.
- Transforms: `count`, `first`, `limit:<n>`, `sort_by:<key>`, `sort_by_desc:<key>`.
  No arbitrary code.
- Params may reference `ctx.<path>` (resolved from the request context).
- Calls run in parallel, one per distinct `(op, params)`; per-call failure isolates to its
  regions.
- Each region gets a state: `ready`, `empty` (binding resolved to nothing) or `error`.
  Required props that end up empty make the region `empty`; the renderer shows nothing
  rather than invented data.
- Only `read` operations; the registry's existing simulation applies in mock mode.

**Acceptance:** a plan whose `pricing_table.tiers` is bound to `api:listPlans` renders the
API's tiers; the model's tool result contains no bound values.

### P0-5 · `generate_page` on the plan pipeline ✅ ⏱️M

**Build** (`app/experience/compose.py`, `orchestrator/thinker.py`, `orchestrator/tools.py`,
`orchestrator/pagegen.py`, `orchestrator/result.py`, `ai/mock.py`):
- `generate_page` accepts `regions` (new, with bindings) **or** `sections` (v1.0); sections
  are converted to regions (`fb.<type>`).
- `compose_page(args, site_key, ctx)` → validate → bind → `PageSpec` with `plan_id`, the
  validated `plan`, and render-ready `sections` (each with `id`, `component`, `state`).
- Tool result to the model: `{ok, sync_id, plan_id, region_count, problems, dropped}`.
- `build_extreme_brief` lists the manifest and the bindable operations and explains the
  binding format.
- `PageSpec.to_dict` adds `plan_id`, `actions` and per-section `id` / `component` /
  `state` (additive). The validated plan stays server side (`PageSpec.plan`).
- Offline/mock mode: a simulated API call returns the operation's documented OpenAPI
  response example, so bound regions render realistic data without a live API. The mock
  engine keeps emitting the legacy `sections` form, which exercises the conversion path.

**Acceptance:** an Extreme turn in mock mode sends `DATA/render_page` with `plan_id` and
stable section ids; the old `sections` form still works.

### P0-6 · Stable `data-fb-*` addressing in the SDK renderer ✅ ⏱️S

**Build** (`fluid-buddha-sdk/src/protocol.ts`, `src/ui/page/PageRenderer.ts`):
- `PageSpec.plan_id?`, `PageSection.id?`, `component?`, `state?`.
- Each section element gets `data-fb-region`, `data-fb-component`, `data-fb-state`, and
  the page root `data-fb-plan`. CTA buttons get `data-fb-action` when the props carry
  `action`. Sections with state `empty`/`error` are not drawn.

**Tests:** smoke assertions for the attributes and for skipping empty regions.

### P0-7 · Design-system package and manifest in the console ✅ ⏱️L

- Tables `site_design_systems` and `site_component_manifests` (versioned, immutable once
  approved), migration `0032`.
- Console API: `GET/PUT …/sites/{id}/design-system`, `GET/POST …/manifest/versions`,
  `POST …/manifest/versions/{v}/approve`. Roles: Editor drafts, Admin approves.
- Loader order becomes: approved DB version → file/env → extracted design → default.
- Tunables block in the design system (§4.2.1) stored, not yet applied (Phase 3).
- Console pages: Design system, Components (manifest browser, diff, approve).

### P0-8 · Web Component runtime contract and React authoring adapter ✅ ⏱️L (D2)

- SDK: a customer-component registry; manifest entries with `renderer: "wc:<tag-name>"`
  render the customer's custom element, setting props as properties; bundle URL per site
  (allow-listed origin, SRI hash).
- New package `integrations/js/packages/components` (`@fluidbuddha/components`, React
  adapter): wraps a React component as a Web Component and emits its manifest entry from
  the same typed declaration (the declared props are checked against the component's
  props type). An `fb-manifest` CLI writes the manifest with the bundle's sha384 hash.
- Declarative-shadow-DOM SSR hook reserved for Phase 2.

### P0-9 · Draft-manifest generator ✅ ⏱️L (D8)

- From Storybook: read `index.json` / `stories.json` (titles, args, argTypes, docs) → draft
  entries.
- From the live site: repeated DOM patterns from the crawler plus brand extraction → draft
  entries mapped onto default renderers.
- Drafts land as unapproved manifest versions (P0-7). The planner never sees a draft.

**Phase 0 exit:** P0-1…P0-6 deliver the engineering exit criterion. P0-7…P0-9 complete the
customer-supplied side. All nine are done (2026-11-06); Phase 1 (G1 pilots) can start.

---

## Part C — Later phases (epic level)

### Phase 1 — Adaptive slots (G1), where pilots start (D1) ✅

Goal: a customer's existing page gets a few generated regions (hero, proof, CTA…) chosen
for the visitor's intent before they say anything, without slowing first paint, and the
lift is measured against the page's own content.

**Data (migration `0033_adaptive_regions`)**
- `site_experience` — per-site switch `regions_enabled` (promoted by a region test).
- `site_regions` — the slots an owner declares: `name` (slug, what `<fb-region name>`
  uses), `label`, `purpose`, allowed `components` (manifest ids; empty = any), `pages`
  (path globs; empty = any), `enabled`.
- `site_intent_families` — `slug`, `label`, `description`, `stage`, `rules`
  (`paths`, `utm_source`, `utm_medium`, `utm_campaign`, `referrer_hosts`,
  `query_terms`, globs), `priority`, `enabled`.
- `plan_cache` — one G1 plan per cache key: `(family, persona, lang, page, region set,
  content version, manifest version)` hashed; `plan` (bindings as references), `composer`
  (`model` | `rules`), `status` (`auto` | `pinned` | `blocked`), hits.

#### P1-1 · Region embedding ⏱️M
- Public `POST /experience/regions {key, visitor, page, regions[], signals, lang, persona,
  automated}` → `{regions: {name: section}, plan_id, intent, cache, tokens, bundle,
  pending, retry_after_ms}`. Widget key and origin checked like every public call; public
  rate limit applies.
- Order: switch off → nothing; bots → nothing (crawlers see the host's own content);
  experiment arm without generated regions → nothing; filter to enabled slots for this
  page; resolve intent; pinned plan → cached plan → bind live data → answer.
- **Cache miss never blocks:** the answer is `pending` with `retry_after_ms`; the plan is
  built in the background (one build per key at a time) and stored.
- SDK: `<fb-region name="hero">fallback</fb-region>`. Regions on a page are fetched in one
  request. The host's own children stay (via `<slot>`) until a region is filled. A filled
  region renders in its own shadow root with the page styles and design tokens, and
  carries `data-fb-region` / `data-fb-plan` / `data-fb-state`.
- **Morph rule:** after a pending answer the SDK asks once more; it fills a region then only
  if the visitor hasn't interacted yet or the region is below the fold.
- `<FbRegion>` in `@fluidbuddha/react` and `@fluidbuddha/vue`.

#### P1-2 · Silent intent resolver ⏱️M
- `resolve_intent(site, signals)`: (1) owner rules, highest priority first (confidence
  0.9); (2) embedding nearest neighbour between the signal text (path words, UTM campaign
  and term, search query, referrer search terms) and each family's label + description
  (threshold 0.6); (3) otherwise the `general` family, and, if a model is available, a
  background classification with the fast model whose answer is remembered for that
  signal fingerprint (24 h) — the next visitor with the same signals gets it, nobody waits.
- Console: families CRUD, suggestions from the site's routes, and a "try signals" tester.

#### P1-3 · Plan cache and the G1 region planner ⏱️M
- Planner: retrieves site content for the family and page (CORTEX), then the model writes
  one region per slot from the slot's allowed components (tool call constrained to the
  manifest), with citations. Enforcement after the shared validator: region ids equal the
  slot names, components within the slot's list, and any number in model-written text must
  appear in the cited material. On failure, mock mode, or past the rate/spend limits, a
  rules composer fills hero / text / CTA / feature grid / FAQ only from site material.
- Cache lookup: pinned plan for (family, page, region set) first, then the exact key.
  Blocking a plan frees its key, so the next visitor triggers a fresh build.
- Invalidation: re-ingest and manifest approval change the key (content / manifest
  version); stale `auto` rows are deleted with the site's other caches.

#### P1-4 · Preview console and region holdout ⏱️M
- Console **Regions** tab: the switch, slots, intent families (with tester and suggestions),
  and a plan browser by family × persona × page with a server-rendered, script-free
  preview; generate now, pin, block, delete.
- Experiments get the subject `regions` (variants turn generated regions on or off), so
  the existing variant-test machinery (enrolment, goal tracking, always-valid verdict,
  promote) measures generated regions against the page's own content. Promoting sets
  `regions_enabled`.

**Phase 1 exit:** a pilot page can show generated regions for its intent families, first
paint is unchanged (cache-first, background builds), and a region test reports lift.

### Phase 2 — Composed pages (G2) ✅

Goal: whole pages composed from the customer's components for an intent family on a
route, rendered on the server, served through the customer's own Next.js site (D4), with
stable URLs, canonical pages for search engines, data from the customer's own records,
and a conversation that can edit the page in place.

**Data (migration `0035_composed_pages`)**
- `site_routes` — the route registry: `pattern` (`/pricing`, `/products/:slug`,
  `/guides/*`), `title`, `purpose`, `enabled`, `canonical_plan` (a `plan_cache` row) and
  `priority` (more specific patterns win).
- `site_entities` — structured records: `type` (`Product`, `Plan`, `CaseStudy`…), `key`
  (slug), `data` (JSON), `source` (`manual` | `import` | `connector:<id>`).
- `site_connectors` — content feeds that fill entities: `kind` (`json_feed` |
  `wordpress`), `url`, `entity_type`, field mapping, `last_sync_at`, `last_status`.
- Page plans live in `plan_cache` with the region set `@page`, so pinning, blocking,
  previews and invalidation work as in Phase 1.

#### P2-6 · Entities, connectors and new bindings ⏱️M
- Bindings `entity:<Type>` (a list; `params.where` equality filter, `params.limit`) and
  `entity:<Type>` with `params.key` (one record; `route.<name>` resolves a route
  parameter), and `content:search` (`params.query`; site knowledge snippets
  `{text, label}`). Request context gains `route.*` parameters.
- Import JSON or CSV in the console; connectors: a generic JSON feed (items path, key
  field, field map) and a WordPress preset (`/wp-json/wp/v2/posts|pages`). Fetching uses
  the SSRF-safe fetcher. Syncing upserts by key and removes records the feed no longer has.

#### P2-5 · Route registry, canonical plans, plan URLs ⏱️S
- Path → route match with parameters (`:name` one segment, `*` the rest).
- Every served page carries `<link rel="canonical">` to its clean URL. Crawlers get the
  route's **canonical plan** (pinned by the owner) or, without one, the default plan, and
  `index, follow`; generated variants get `noindex`.
- `?fbv=<plan_id>` restores a specific plan (shared links, back/forward); data is bound
  fresh.

#### P2-3 · Page planner ⏱️M
- Retrieves material for the route's purpose and the intent; offers the model the
  manifest components most relevant to them (`use_when` / purpose overlap, at most 16),
  the entity types it can bind, and up to 3 exemplar outlines (pinned or most-served page
  plans of the same family).
- Validated with the shared validator plus the number check; **one repair round** sends
  the problems back to the model; then the fallbacks: the nearest cached plan for the
  route → the route's canonical plan → a rules page (hero, intro, highlights, FAQ, CTA).

#### P2-1 · Server-side rendering and page endpoints ⏱️M
- `ssr.py` renders a bound plan to semantic HTML with the generated-page classes and a
  token-themed stylesheet; interactive sections render a readable fallback plus their
  data for hydration. Customer Web Components render as the custom element with a
  **declarative shadow root** holding a readable fallback, replaced when the element
  upgrades (the React adapter clears it).
- `GET /experience/page?key=&path=&fbv=&…signals` → `{status, html, head{title,
  description, canonical, robots, json_ld}, plan_id, route, intent, tokens, bundle,
  pending}`; misses never block (default/canonical plan or the route's fallback content,
  background build). `GET /g/{site_key}/{path}` serves the same as a full page (preview
  and non-Next sites).
- `fluid-buddha-composed.global.js` hydrates interactive sections of a served page and
  applies plan patches to it.

#### P2-4 · Plan patches ⏱️M
- Thinker tool `patch_plan {ops: [{op: add|replace|remove|move, region, component?,
  props?, before?, animation?}]}`, offered when a page plan is on screen (rendered by the
  agent, or reported by the served page via `plan_id`).
- The patched plan is validated and bound; the client gets `DATA/plan_patch {plan_id,
  ops}` with each new or replaced region as a bound section. The core widget only
  forwards the patch (a window event) and loads the patcher on demand, which applies it
  to any element with that `data-fb-plan` (the agent's page surface or a served page),
  with the fade / highlight animations.

#### P2-2 · Next.js adapter (`@fluidbuddha/next`) ⏱️M
- `fetchComposedPage()` (server), `createPageHandler()` (a catch-all Route Handler that
  returns the full HTML page), `<ComposedPage>` (a server component that renders the
  fragment plus the hydrate script) and `composedMetadata()` (title, description,
  canonical, robots for `generateMetadata`).

#### Console
- **Pages** tab: routes (pattern, purpose, canonical plan, generate and preview,
  open the served page), entities (browse, add, import JSON/CSV, delete) and connectors
  (add, sync now, status).

**Phase 2 exit:** a pilot route serves a composed page through Next.js with SSR, a
canonical page for crawlers, data from the customer's records, and in-place edits from
the conversation.

### Phase 3 — Personal experience

Taste profile (session, then opt-in persistent; stored by FluidBuddha, D5), tunables applied
within brand limits, taste bucket in the plan key, "why am I seeing this", profile panel,
erasure extension, region-level bandits.

### Phase 4 — Free-form (G3), the product we sell (D1)

Fragment cache and assembling planner (§4.14.2), free composition and multi-step flows,
generation budget with fallback to G2 (Q12), pinned regions and G1/G2-only routes (Q14),
sampling review feed, edge-worker hosted shell (D4 second step).

### Phase 5 — Agent-ready

Plan endpoint `GET /sites/{key}/views/{plan_id}`, per-view JSON-LD and text rendering, plan
actions as MCP tools, page-declared tools, agent-mode rendering, plan export to an open
agent-UI standard after the §11.3 review (D3), agent task-completion analytics.

### Phase 6 — SaaS apps (same product, same SKU, D7)

Identity layer (signed claims, `getAccessToken`, token exchange, role-filtered tools),
client-side binding by default (D6), two-level tenancy, **cache partitioning by data scope**
(blocking), app-context API and route templates, safe writes (dry-run, undo, voice read-back,
typed confirmation, actor header), voice-first in apps with push-to-talk (D9), uniform
billing unit (Q11), voice capacity scale-out.

---

## Part D — Build order

```
P0-1 ─┬─► P0-4 ─► P0-5 ─► P0-6        (this iteration: engineering exit of Phase 0)
P0-2 ─┤
P0-3 ─┘
P0-7 ─► P0-9                           (customer-supplied side, before G1 pilots)
P0-8
then Phase 1 → 2 → 3 → 4, Phase 5 after 2, Phase 6 in parallel after Phase 0
```

Not in this plan: the repo-wide "A2UI" → "FluidBuddha" rename (D10) is a separate change
(see strategy §11.4).

---

## Part E — Progress log

| Date | Change |
|---|---|
| 2026-11-06 | Plan written. P0-1…P0-6 implemented (see the record below). |
| 2026-11-06 | P0-7…P0-9 implemented; Phase 0 complete (second record below). |
| 2026-11-06 | Phase 1 (P1-1…P1-4) implemented (third record below). |
| 2026-11-06 | Phase 2 (P2-1…P2-6) implemented (fourth record below). |

### Record: P0-1…P0-6 (2026-11-06)

- New package `backend/app/experience/` (`plan.py`, `manifest.py`, `binding.py`,
  `compose.py`).
- `app/apis/registry.py`: `x-fb-*` annotations, `operation()`, `bindable_operations()`;
  simulated calls return the documented response example.
- `generate_page` (tool schema in `orchestrator/tools.py`, handler in
  `orchestrator/thinker.py`) accepts `regions` with bindings and `actions`; the old
  `sections` form is still accepted. The thinker passes `ctx` (site, currency, persona,
  page, lang) for bindings.
- `orchestrator/pagegen.py`: the Extreme brief lists the manifest (`PAGE COMPONENTS`) and
  the bindable operations (`BINDABLE DATA`); the unused `sections_prompt` was removed
  (`normalize_page` and `SECTION_TYPES` stay).
- `DATA/render_page` payload gains `plan_id`, `actions`, and per-section `id`, `component`,
  `state`.
- SDK `PageRenderer` writes `data-fb-plan`, `data-fb-region`, `data-fb-component`,
  `data-fb-state`, `data-fb-action`; skips empty/error regions. `protocol.ts` gains the
  optional fields and `PageAction`.
- `backend/.env.example`: documents `<SITE>_COMPONENT_MANIFEST` /
  `COMPONENT_MANIFEST_DIR` and the `x-fb-*` annotations.
- Tests: `backend/tests/test_experience.py` (26 tests); 5 new SDK smoke assertions.
  Full backend suite: 372 passed, 2 skipped (need Redis). SDK typecheck and smoke: pass.

**Known gaps carried to the next epics:** manifests and design systems are still file/env
only (P0-7); customer Web Component renderers are refused until P0-8; bindings resolve on
the server only (client-side, user-token binding is Phase 6); plans are not cached yet
(P1-3).

### Record: P0-7…P0-9 (2026-11-06)

**P0-7 — console-managed design system and manifest versions**
- Migration `0032_experience_config`: `site_design_systems` (one current row per site) and
  `site_component_manifests` (versions `draft` → `approved` → `archived`; at most one
  approved per site, enforced by a partial unique index). Both are purged with the site
  (`cortex/purge.py`).
- `app/experience/store.py`; console routes in `app/routes/experience.py`:
  `GET/PUT/DELETE …/design-system`, `GET …/manifest`, `GET/POST …/manifest/versions`,
  `PUT/DELETE …/manifest/versions/{v}` (drafts only), `POST …/versions/{v}/approve`.
  Approval refuses a draft whose check lists problems. Role rule: approving needs Admin
  (`auth/roles.py`); everything else follows the default (read = Viewer, change = Editor).
- Loaders: design system = console → file → extracted → default
  (`design/system.py`, `design_source()`); manifest = approved console version → file →
  default (`experience/manifest.py`, `ensure_manifest()` called next to `ensure_design()`
  in `/chat` and the voice socket). Caches hold for 30 s, so another replica picks up an
  approval within 30 s.
- Design-system input is validated (hex colours, https logo, CSS-safe font values, radius
  units, tunable axes `density` / `scheme` / `motion` / `type_scale`). Tunables are stored
  and served (`tunables` in `GET /design-system`), not yet applied (Phase 3).
- Console: **Design** tab (brand, colours, type, tunables, live preview, tokens) and
  **Components** tab (in-use summary, versions, draft editor with problems and a diff
  against the approved version, approve, delete, generate from Storybook or the live
  site). The website tab row now scrolls sideways instead of widening the page.

**P0-8 — customer Web Components**
- Manifest entries may use `renderer: "wc:<tag>"` (valid custom-element name; tags starting
  `fluid-buddha` or `fb-` are reserved). They need the manifest's `bundle`
  `{url (https), integrity (sha256/384/512 SRI)}`; without it the entry is refused.
- A generated page carries `bundle` only when it draws a WC section. The SDK
  (`src/ui/page/customComponents.ts`) loads it once as a module script with `integrity`
  and `crossorigin=anonymous`, creates the element, and sets props as properties after the
  element is defined. An invalid bundle is never loaded; its regions are hidden and marked
  `error`.
- `@fluidbuddha/components`: `defineFbComponent`, `manifestEntryFor`, `buildManifest`, and
  the `fb-manifest` CLI.

**P0-9 — draft generation**
- `app/experience/drafts.py`: Storybook `index.json` (v7+) / `stories.json` (v6) → one
  `wc:` entry per story title; props from `argTypes`, or from an uploaded
  react-docgen / react-docgen-typescript JSON; callbacks are skipped; story names become
  `use_when`. Live site → section-level class/id patterns counted over up to 8 pages,
  mapped onto built-in renderers with their props. Fetching uses the SSRF-safe fetcher.
- Drafts are saved as `draft` versions with notes explaining what to check (for Storybook
  drafts: add the bundle before approving).

**Verification**
- Backend: `tests/test_experience_console.py` (13 tests) plus the earlier
  `tests/test_experience.py`; full suite 382 passed, 2 skipped (need Redis).
- SDK: 5 more smoke assertions for Web Components (216 PASS lines in total).
- `integrations/js`: `test/components.test.mjs` (4 tests; 15 in the JS suite).
- Console: typecheck and lint clean; checked in the browser against a local backend
  (design save with a tunable, draft with problems → fix → approve, Storybook draft with
  diff).

**Known gaps carried forward**
- OpenAPI specs are still configured by file/env, not in the console (the other half of
  assumption A8); a console catalogue editor belongs with P1 or P2.
- Customer components can't yet send events back to the agent (for example a selected
  plan); an event contract is needed with P2-4 (plan patches).
- Declarative-shadow-DOM SSR for Web Components is Phase 2 (P2-1).
- Storybook drafts get props only from `argTypes` or an uploaded docgen file; site drafts
  map only onto built-in renderers.

### Record: Phase 1 — adaptive regions, G1 (2026-11-06)

**Backend**
- Migrations `0033_adaptive_regions` (`site_experience`, `site_regions`,
  `site_intent_families`, `plan_cache`) and `0034_region_test_subject` (adds `regions` to
  the experiment subject check). New tables are purged with the site; `auto` plans are
  cleared with the other caches on re-ingest.
- `app/experience/regions_store.py` (slots, families, plan cache with pinned / blocked),
  `intent.py` (rules → embeddings → general + remembered background classification;
  family suggestions from routes and personas), `planner.py` (CORTEX material, model
  composer constrained to each slot's components, enforcement, rules composer),
  `regions.py` (serve / build / render, background builds de-duplicated per key),
  `preview.py` (script-free preview HTML).
- Routes `app/routes/regions.py`: public `POST /experience/regions`; console settings,
  slots, intent families (+ suggest, try), plans (list, generate, view with preview, pin /
  block, delete).
- Experiments: subject `regions` (`{"regions": bool}` per variant); promoting sets
  `site_experience.regions_enabled`. The public endpoint enrols the visitor and leaves
  out the arm without regions, the agent holdout, unidentified visitors during a region
  test, and bots.

**SDK and packages**
- `<fb-region name>`: core part in `src/core/Regions.ts` (element, config, interaction
  tracking); the controller (`src/core/regions/controller.ts`) loads on demand
  (`dist/fluid-buddha-regions.global.js` for the script tag, a split chunk for ESM), so
  the script-tag core stays under its 42 kB gzip budget (41.9 kB). One request per page,
  fallback via `<slot>`, morph rule on the retry, `fluidbuddha:region` event, enquiry
  forms post to `/leads`.
- `<FbRegion>` in `@fluidbuddha/react` and `@fluidbuddha/vue`.

**Console**
- **Regions** tab: on/off switch, slots (dialog with component and page pickers), visitor
  goals (dialog with rule fields, suggestions, a "try it" resolver), plans (filter by
  goal, generate a preview, sandboxed preview iframe, pin / block / unpin / delete).
- **A/B tests**: new subject "Generated regions".

**Verification**
- Backend: `tests/test_regions.py` (13 tests); full suite 395 passed, 2 skipped (need Redis).
- SDK: 9 new smoke assertions for `<fb-region>`; all pass; core 41.9 kB gzipped.
- `integrations/js`: FbRegion tests for React and Vue (17 tests in the suite).
- Console: typecheck and lint clean; checked in the browser (add a region, add a goal,
  try signals → rule match, generate and preview a plan, test subject listed).

**Known gaps carried forward**
- The core bundle is 0.1 kB under its gzip budget: the next core feature needs room made
  (or more of it loaded on demand).
- Low-confidence visitors get the general plan; the "ask with the UI" intent chooser
  (strategy §4.4) is not built yet.
- Background model classification answers are remembered in-process (per replica, 24 h).
- The rules composer covers hero, text, CTA, feature grid and FAQ; other components are
  filled only by the model.
- The live-site preview of a filled region needs knowledge ingested first (the console
  shows "Nothing to show" otherwise).

### Record: Phase 2 — composed pages, G2 (2026-11-06)

**Backend**
- Migration `0035_composed_pages` (`site_routes`, `site_entities`, `site_connectors`);
  page plans live in `plan_cache` with the region set `@page`. New tables are purged with
  the site.
- P2-6 `app/experience/entities.py` (records, JSON/CSV import, JSON-feed and WordPress
  connectors with sync that removes records the feed dropped) and `resolvers.py`.
  Bindings gained `entity:<Type>` (`params.key` / `where` / `limit`), `content:search`,
  `route.<name>` parameters, and a `map` option that renames record fields to a prop's
  shape (records rarely match a component exactly — found while testing).
- P2-5 `routes_store.py`: patterns with `:param` and `*`, most-specific match, canonical
  plan per route (pinned with the same one-pin rule as "Pin").
- P2-3 `page_planner.py`: relevant components (≤ 16), entity samples, exemplar outlines,
  one repair round, fallbacks (nearest cached plan → canonical → rules page headed by the
  route title).
- P2-1 `ssr.py` (semantic HTML, `fbpage-*` classes, token stylesheet, declarative shadow
  roots for customer Web Components, interactive sections marked for hydration, forms
  that post to the server without JavaScript — never a GET with personal data) and
  `pages.py` (serve: `?fbv` restore → crawler canonical → visitor pinned/cached → miss
  serves the best available page now and builds in the background).
- Routes `app/routes/pages.py`: `GET /experience/page` (server-side callers send no Origin;
  browsers must be on the site), `POST /experience/lead` (form posts; redirects only back
  to the site), `GET /g/{site}/{path}` (full document with a strict CSP), console routes,
  canonical, generate, entities, import, connectors.
- P2-4 `patch.py` + thinker tool `patch_plan` (offered when a composed page is on screen;
  the page outline goes into the prompt), `PlanPatch` / `DATA/plan_patch`, session state
  `page_plan` (set when the agent renders a page, or loaded from the `plan_id` a served
  page reports). Only added / replaced regions are bound and sent.

**SDK and packages**
- The page renderer moved out of the core into the on-demand patcher chunk
  (`fluid-buddha-patcher.global.js`): the script-tag core went from 42.1 kB to **37.4 kB**
  gzipped. The core only relays `plan_patch` as a window event.
- `src/composed.ts` → `fluid-buddha-composed.global.js`: hydration, fetch forms, patches.
- Widget page context reports `plan_id` of a served page.
- `@fluidbuddha/next`: `fetchComposedPage`, `createPageHandler`, `<ComposedPage>`,
  `composedMetadata`, `renderComposedDocument`.
- `@fluidbuddha/components` clears a server-rendered declarative fallback on upgrade.

**Console**
- **Pages** tab: routes (add, edit, compose a preview for a goal, plans with "make
  canonical", open the served page), records (types, browse, add / edit JSON, import
  JSON / CSV, delete), content feeds (connect, sync now, status, remove).

**Verification**
- Backend: `tests/test_pages.py` (13 tests); full suite 408 passed, 2 skipped (need Redis).
- SDK: 8 new smoke assertions (lazy page renderer, patches on the widget surface,
  composed hydration, fetch form, patches on a served page); all pass.
- `integrations/js`: Next.js adapter (4 tests) and the declarative-fallback test (22 in
  the suite).
- Console typecheck and lint clean. Browser: ingested sample content, added a `/` route,
  composed a preview from site content, made it canonical, opened `/g/acme-verify/`
  (server-rendered, brand tokens, composed script and the agent loaded under the CSP;
  crawler and visitor both got the canonical page with `index, follow`), imported records.

**Known gaps carried forward**
- No live model was used in testing (mock mode): the model composer, repair round and
  `patch_plan` are covered with fake models only.
- Connectors sync on demand only (no schedule yet); two kinds (JSON feed, WordPress).
- Edge-worker delivery is Phase 4; only the Next.js adapter and the hosted `/g/` shell exist.
- Structured data per view is a basic `WebPage` JSON-LD; richer schema.org output is Phase 5.
- A plan's region ids from the model aren't checked against exemplars for stability across
  regenerations beyond the validator's slug rules.

