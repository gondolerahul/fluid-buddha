# Fluid-Buddha — Defect List (from a local install, run and test)

**Date:** 2026-11-03
**Author:** Durwanku Rai Lab (durwankurailab@gmail.com), with Claude Code
**Scope:** This list records defects found by **actually installing, running and exercising** the three subsystems on this machine — not by reading code alone. Each entry says how it was observed, the file/line behind it, and how to reproduce. It complements the two existing docs:

- [docs/functionality-report.md](functionality-report.md) — what is built.
- [docs/roadmap.md](roadmap.md) — where the product should go.

Severity key: **S1 Critical** (security, data loss, or blocks a second customer) · **S2 High** (breaks a feature or the test gate) · **S3 Medium** (wrong/degraded behaviour) · **S4 Low** (polish, hygiene).

---

## 0. How this run was set up

| Thing | Value |
|---|---|
| OS | Windows 11, Git-Bash + PowerShell |
| Python | 3.12.14 (venv under `backend/.venv`) |
| Node | 23.7.0 |
| Postgres + pgvector | `pgvector/pgvector:pg16` via Docker Desktop, host port **5434** |
| AI mode | `MOCK_AI=true` (deterministic stubs — no Vertex credentials on this box) |
| Backend | `uvicorn app.main:app` |
| Console | `next dev` |
| SDK demo | built bundle served statically, widget injected into the demo host page |

**What worked end to end (verified live):**
- `docker compose up -d postgres` → healthy; schema auto-created on first boot.
- Ingestion of the 9 HireBuddha docs → **334 nodes**, 8 tour stops planned.
- Backend `/healthz` + `/readyz` → `{"status":"ok","db":true,"mock_ai":true}`.
- `POST /chat` and `WS /ws/voice` → acknowledgement, grounded answer, synced component render, live reaction to a slider change.
- Backend pytest on a **fresh** DB → **28 passed**.
- SDK `tsc` typecheck clean; `build` produced all three bundles; the jsdom suite → **57/57 PASS** (after a Node-23 shim, see D-12).
- Console `next build` → compiled, 10 routes, TypeScript clean.
- Console in the browser: register → auth → dashboard → add website → website detail with Ingestion/Tour/Responses/Analytics tabs all rendered and talked to the backend.
- SDK widget in the browser: L1 panel injected into a foreign host page, streamed an answer, and rendered a **live interactive ROI calculator** inside its Shadow DOM over the WebSocket. L2 (Three.js particle field) mounted.

Everything below is what went wrong, degraded, or is unsafe.

---

## S1 — Critical

### D-1 · Public widget endpoints are unauthenticated and let the client pick site + capability tier
**Observed:** `POST /chat` with no token, body `{"message":"…","site":"fluidbuddha","intelligence":"extreme"}`, returned a full extreme-tier answer (generated a page). `WS /ws/voice?site=…&intelligence=extreme` behaves the same.
**Why:** the WS route reads `site` and `intelligence` straight from query params with a `hirebuddha`/`advance` default and no auth ([backend/app/transport/websocket.py:736](../backend/app/transport/websocket.py)); `/chat` takes `site`/`intelligence` from the request body with no tenant check ([backend/app/routes/chat.py:43](../backend/app/routes/chat.py)).
**Impact:** any visitor can talk to **any** tenant's knowledge base and silently select the most expensive model path. There is no per-site key, no origin binding, and (see D-3) no rate or spend limit.
**Fix direction:** issue a public widget key per website, bind it to the site's allowed origin(s), resolve `site` + `intelligence` **server-side** from that key, and ignore client-supplied tier.

### D-2 · Default JWT secret is shipped in config — tenant tokens are forgeable
**Observed:** registered a real tenant, read its id from `/auth/me`, then minted a valid token for that same id **offline** using the default secret and called `/auth/me` with it — it returned the tenant's account. (Shown only against an account created for this test.)
**Why:** `jwt_secret` defaults to the literal `dev-fluid-buddha-secret-change-me-in-production-0001` ([backend/app/config.py:71](../backend/app/config.py)); `.env.example` ships the same value, and nothing refuses to boot on the default.
**Impact:** anyone who knows the default (it is in the repo) can impersonate any tenant on any deployment that didn't override it — full access to every website, source, tour, cache and analytics API.
**Fix direction:** no default — fail fast at startup if `JWT_SECRET` is unset or equals the known dev value; rotate; document secret provisioning.

### D-3 · No rate limiting or spend cap on the public paths
**Observed:** 40 back-to-back `POST /chat` calls all returned `200` with no throttling. In mock mode each is free, but in Vertex mode each is a real LLM + TTS spend.
**Why:** no limiter middleware anywhere; `usage_events` records cost **after the fact** but nothing enforces a ceiling.
**Impact:** a trivial loop against an unauthenticated endpoint (D-1) runs up unbounded Vertex and TTS cost. This is the "negative-margin per conversation" risk in the roadmap turned into an abuse vector.
**Fix direction:** per-key and per-IP rate limits; a per-website monthly spend ceiling that trips to text-only or a cached response.

### D-4 · A new tenant can claim the built-in `hirebuddha` site key and serve/alter its knowledge
**Observed:** a freshly-registered tenant created a website named `hirebuddha` and received `site_key = "hirebuddha"` — the same key the seeded flagship site uses. (A second attempt collided and got `hirebuddha-2`, confirming first-come-first-served.) Because the public widget resolves knowledge purely by `site_key` (D-1), that tenant's widget now answers from — and their ingestion/tour edits now write into — the shared `hirebuddha` CORTEX tree.
**Why:** `site_key` is slugified from the tenant-chosen name with only a numeric-suffix collision check against `tenant_websites`; the built-in seed sites (`hirebuddha`, `fluidbuddha`, `buddha-cognitive-lab`) are **not** reserved, and CORTEX trees are keyed by `site_key` with no tenant scoping.
**Impact:** cross-tenant knowledge disclosure and poisoning of the demo/flagship site.
**Fix direction:** reserve the built-in keys; namespace CORTEX trees by `tenant_id` (or a random site id), never by a human-chosen slug; resolve the public widget by key, not by slug.

### D-5 · SSRF: URL sources are fetched server-side with no allowlist and redirects followed
**Observed (code path, not fired at an internal target):** adding a `url` source and running ingestion makes the server `GET` the URL with `follow_redirects=True` and a 20s timeout, then ingests the body ([backend/app/tenancy/sources.py:195](../backend/app/tenancy/sources.py)).
**Impact:** an authenticated tenant can make the backend fetch internal addresses (cloud metadata, internal services) and read the response back via the ingested text / error messages. Redirect-following defeats a naive host check.
**Fix direction:** block private/link-local/metadata IP ranges, disable redirects (or re-validate each hop), enforce scheme/size/content-type, and fetch from an egress-restricted worker.

### D-6 · Deleting a source or a website leaves all of its knowledge, tours, cache and usage behind
**Observed (code):** `delete_source` only does `DELETE FROM tenant_sources …` ([backend/app/tenancy/sources.py:127](../backend/app/tenancy/sources.py)); `delete_website` only does `DELETE FROM tenant_websites …` ([backend/app/tenancy/store.py:255](../backend/app/tenancy/store.py)). Neither touches the CORTEX nodes/edges, `site_tours`, `conversation_cache`, `answer_audio_cache`, or `usage_events`.
**Impact:** "delete" does not delete. The agent keeps answering from removed content, cached answers keep being replayed, and — combined with D-4's slug reuse — the orphaned knowledge can be inherited by a later site with the same name. This is a correctness **and** a privacy/compliance problem (no real data deletion).
**Fix direction:** cascade deletion across CORTEX + all per-site tables inside one transaction; add a "purge knowledge" action; key everything by a stable site id so orphans can be found and swept.

---

## S2 — High

### D-7 · Test suite hangs on every run after the first (shared cache state → replay with no `ack` → WebSocket test blocks forever)
**Observed:** on a **fresh** DB volume the backend suite is `28 passed`. On **any subsequent run**, or when an admin/analytics/cache module runs before `test_backend.py`, the suite **hangs indefinitely** at `tests/test_backend.py::test_ws_voice_turn_streams_synced_audio` (and the live-reaction test). Reproduced repeatedly; needed `pytest-timeout` / manual kill.
**Root cause (traced):**
1. All tests share one process → one `app.state.runtime` singleton and one Postgres DB.
2. `test_analytics_breakdown_and_cache_split` (and `test_cache`) set `runtime.settings.episodic_min_episodes = 1` and **never restore it**.
3. `conversation_cache` accumulates rows across tests (23 rows observed).
4. A later WS test asks a question close to a cached one; with the threshold lowered and rows present, `_maybe_replay` replays ([backend/app/transport/websocket.py:575](../backend/app/transport/websocket.py)).
5. The **replay path emits no acknowledgement segment** — only `STATE/transcript`, optional `DATA/render`, and one answer `AUDIO start/end` ([backend/app/transport/websocket.py:604](../backend/app/transport/websocket.py)). The test loops until it sees **two** `AUDIO end`s (ack + answer); it only ever gets one, so `ws.receive_json()` blocks forever.
**Impact:** the automated test gate is **not reliably runnable** — CI as written would hang, not fail. Masks regressions.
**Fix direction:** (a) restore mutated settings via fixture teardown and isolate the DB per test (transaction rollback or a throwaway schema); (b) decide the product contract — either the replay path should emit an ack too, or clients/tests must not assume a fixed ack+answer count; (c) add an overall suite timeout so a stall surfaces as a failure.

### D-8 · Replay turns skip the acknowledgement — client UX diverges between fresh and cached answers
**Observed:** live WS probe of a question that hit the cache produced `STATE/transcript` → `AUDIO start/end` (answer only), **no `ack_*` segment**. A fresh answer to the same question produces `ack_*` then the answer.
**Why:** `_replay` speaks only `best.answer_text` and never sends the ack ([backend/app/transport/websocket.py:604](../backend/app/transport/websocket.py)).
**Impact:** the "instant, warm acknowledgement" that defines the product's feel is absent exactly when the answer is fastest (cache hit). Any client logic keyed on an ack arriving first (the SDK surfaces `ack_*` differently from answers) behaves inconsistently. This is the client-visible half of D-7.
**Fix direction:** emit a short ack on the replay path too (it can itself be cached audio), or formally document that replays have no ack and make the SDK/tests tolerate it.

### D-9 · Tenant (non-HireBuddha) sites can never navigate — every `navigate` action is dropped
**Observed (code + live):** the smoke/analytics flow logged `navigate dropped — invalid path '/pricing'` for a fresh tenant site. `_SITEMAPS` contains **only** `hirebuddha` ([backend/app/orchestrator/sitemap.py:53](../backend/app/orchestrator/sitemap.py)); for any other `site_key`, `resolve_route` has zero candidates and no dynamic prefixes, so it returns `None` and the action is discarded.
**Impact:** "she walks you through the site" — a headline capability — works **only** for HireBuddha. Every other customer gets an agent that can talk but never move the page.
**Fix direction:** build the sitemap per tenant from ingested routes/sources (store the route with each document) instead of a hardcoded dict.

### D-10 · Re-running ingestion duplicates knowledge and silently overwrites a hand-edited tour
**Observed (code):** the admin `run_ingestion` calls `ingest_documents`, which **appends** nodes every time ([ingestion/ingest.py:62](../backend/ingestion/ingest.py)) — there is no per-source reset outside the CLI's `--reset`. It then calls `plan_and_save_tour`, which **replaces** the stored tour.
**Impact:** pressing "Run ingestion" again (a natural thing to do after editing a source) duplicates every chunk in CORTEX, skewing retrieval and cost, and throws away any tour a tenant edited by hand in the console.
**Fix direction:** make per-source ingestion idempotent (delete that source's prior nodes before re-adding); treat the tour as regenerate-on-demand vs. preserve-manual-edits, with an explicit choice.

### D-11 · `patch_component` is defined, prompted and documented but never emitted
**Observed (code):** the tool exists ([backend/app/orchestrator/tools.py:87](../backend/app/orchestrator/tools.py)) and the system prompt tells the model to use it, but the thinker's handler for it just returns `{"ok": True, "target_sync_id": …}` without appending any patch to the result ([backend/app/orchestrator/thinker.py:263](../backend/app/orchestrator/thinker.py)), so no `DATA/patch` envelope is ever sent. The SDK's `applyPatch` path is therefore dead in practice.
**Impact:** the agent cannot update a component it already rendered (e.g. correct a slider after a clarification); it can only render a new one. A documented capability is non-functional.
**Fix direction:** have the handler emit a patch payload on the DATA channel targeting the given `sync_id`, and cover it with a WS test.

---

## S3 — Medium

### D-12 · SDK `npm test` fails out of the box on Node ≥ 20 (read-only `navigator`)
**Observed:** `npm test` crashes immediately: `TypeError: Cannot set property navigator of #<Object> which has only a getter` at [fluid-buddha-sdk/test/smoke.mjs:14](../fluid-buddha-sdk/test/smoke.mjs). With a one-line shim (`Object.defineProperty(globalThis,'navigator',…)`) the suite runs and **all 57 checks pass**.
**Why:** `globalThis.navigator` is a getter-only property in modern Node; the test assigns to it directly. `package.json` doesn't pin a Node version.
**Impact:** the SDK's test command is red on any current Node — contributors and CI can't run it unmodified.
**Fix direction:** use `Object.defineProperty` (or `vm`/`jsdom` globals) in the test harness; add an `engines` field.

### D-13 · Port drift across the three apps — nothing lines up by default
**Observed:** backend documents/uses `:8080`; the L1 demo points at `ws://localhost:8080` ([fluid-buddha-sdk/demo/index.html](../fluid-buddha-sdk/demo/index.html)) but the L2/L3 demos point at `ws://localhost:8081` ([demo/level2.html](../fluid-buddha-sdk/demo/level2.html), [demo/level3.html](../fluid-buddha-sdk/demo/level3.html)); the console runs on `:3002` (`package.json` `dev`) while `.env.example` `CORS_ORIGINS` lists `:3000` and `:3001` but **not** `:3002`; the README's `serve:demo` uses `:4000`.
**Impact:** following the docs, the console's origin isn't in CORS, and half the demos point at a port the backend isn't on. I had to override `CORS_ORIGINS` and rewrite the demo URL to get a clean run. First-run friction for the exact second customer the roadmap targets.
**Fix direction:** pick one port map, make `.env.example` CORS match the console's real port, and make the demos read the backend URL from one place.

### D-14 · `docker-compose.yml` volume paths don't match the repo on disk
**Observed:** compose mounts `../../hirebuddha-website/docs` and `../fluidbuddha-website`, but on this machine the folders are `hire-buddha-website` (hyphenated) and there is **no** `fluidbuddha-website` at all (the `fluidbuddha` content/design/OpenAPI the Extreme tier needs is absent). Ingestion also expects `docs/website-copies/` + `docs/product-docs/`, but in this repo those copies live at `docs/website-copies/*` (now deleted in the working tree) and `docs/product-docs/*` — the scraper found **zero** docs until I pointed `HIREBUDDHA_CONTENT_DIR` at a staged copy.
**Why:** hardcoded sibling-folder assumptions in [ingestion/scraper.py:23](../backend/ingestion/scraper.py) and the compose mounts.
**Impact:** `docker compose up` as documented seeds nothing for HireBuddha and cannot build the Extreme "container app" site. The one-command quickstart doesn't produce a working agent without manual path fixing.
**Fix direction:** reconcile folder names, commit (or generate) the `fluidbuddha-website` assets, and make content locations configurable with sane in-repo defaults.

### D-15 · Default HostBridge navigation does a hard page load, breaking SPA hosts
**Observed:** clicking a chip that triggers a `navigate` sent the **host browser** to `http://localhost:4001/pricing` (a full navigation, 404 on the static demo), rather than an in-app route change.
**Impact:** on a real single-page host site, the agent's "walk you to pricing" would blow away the page (and the widget's own session) instead of routing within the app. The host-side integration needs a custom `onNavigate`, which isn't obvious.
**Fix direction:** default to History API / `pushState` where available, emit the event for the host to intercept, and document the SPA integration hook prominently.

### D-16 · Console has no install/embed snippet and no per-site settings page
**Observed:** the website detail page has exactly four tabs — Ingestion, Tour, Responses, Analytics. There is nowhere that shows the `<script>` tag to embed the widget, and no screen to change a site's name/domain/intelligence/design/accent after creation (the API has `PATCH /tenant/websites/{id}`, but the UI never calls it).
**Impact:** a tenant can configure knowledge but is never told **how to put the agent on their site**, and can't edit site settings. The core onboarding step is missing from the product.
**Fix direction:** add an "Install" tab with a copy-paste snippet pre-filled with the site's public key and options, and a Settings tab wired to the existing PATCH.

---

## S4 — Low / hygiene

### D-17 · A real GCP project id is committed in `.env.example`
`GOOGLE_CLOUD_PROJECT=weighty-actor-459318-p2` is checked in ([backend/.env.example:30](../backend/.env.example)). Harmless alone, but it leaks a real project identifier and invites accidental use. Replace with a placeholder.

### D-18 · `.env.example` model ids don't match the compose defaults or the docs
`.env.example` sets `FAST_MODEL=gemini-2.0-flash` / `HEAVY_MODEL=gemini-1.5-pro`, while `docker-compose.yml` defaults to `gemini-2.5-flash` / `gemini-2.5-pro` and the functionality report describes 2.5. Pick one source of truth; mismatched model ids change cost and behaviour silently in Vertex mode.

### D-19 · Console lint is red; `next lint` is broken; effects call setState directly
`eslint` via the project's own flat config throws (`Converting circular structure to JSON`); run against the resolved Next config it reports **8 errors + 6 warnings** — four `react-hooks/set-state-in-effect` (e.g. [WebsiteContext.tsx:20](../fluid-buddha-frontend/src/components/WebsiteContext.tsx), analytics/cache pages), two `@typescript-eslint/no-explicit-any` ([lib/api.ts:64](../fluid-buddha-frontend/src/lib/api.ts)), plus unused vars. None break the build, but the lint gate is unusable as shipped. Fix the config and the set-state-in-effect patterns (they can cause cascading renders).

### D-20 · Dependency vulnerabilities, including a critical in the console's Next.js
`npm audit`: SDK = 2 moderate (`fflate`, `esbuild`); console = **25 (16 moderate, 8 high, 1 critical)** — the critical and several highs are the pinned `next@16.2.7` (multiple RCE/SSRF/cache-poisoning advisories), plus `zod`, `postcss`, `nanoid`, `sharp`. Schedule a dependency bump; the Next.js advisories matter most for any internet-facing console.

**Status (2026-11-03, branch `phase0/foundations`): resolved.** Console on `next@16.4.4` + `eslint-config-next@16.4.4` with transitive fixes: **0 vulnerabilities in production dependencies**, no high/critical anywhere. SDK: `esbuild@0.28`, `@types/three` moved to devDependencies (it was shipping `fflate` to every consumer), `fflate` overridden to 0.8.x: **0 vulnerabilities**. Backend: `pip-audit` reports none. Gates: `npm run audit` in both packages, `pip-audit` in the backend venv.
*Accepted residual:* 16 moderate advisories in the console's ESLint toolchain, all from `minimatch` < 11.0.1 (GHSA-g3hv-75wg-m249). No patched 3.x/10.x release exists and the ESLint plugins need the 3.x API; it is lint-time only and needs attacker-controlled glob patterns, so it is not exploitable here. Revisit when the plugins move to `minimatch` 11.

### D-21 · `CORS_ORIGINS=*` in compose becomes allow-all (regex `.*`) with credentials behaviour to double-check
Compose defaults `CORS_ORIGINS` to `*`, which `main.py` turns into `allow_origin_regex=".*"` ([backend/app/main.py:48](../backend/app/main.py)). For an unauthenticated public widget that's arguably fine, but combined with the admin API on the same app it's too broad. Split widget vs. admin origins, or scope CORS per router.

---

## Quick triage view

| ID | Sev | One line | Area |
|---|---|---|---|
| D-1 | S1 | Unauthenticated widget endpoints; client picks site + tier | backend/transport |
| D-2 | S1 | Default JWT secret → forgeable tenant tokens | backend/auth |
| D-3 | S1 | No rate limit / spend cap on public paths | backend |
| D-4 | S1 | New tenant can seize the `hirebuddha` site key | backend/tenancy |
| D-5 | S1 | SSRF via URL sources (redirects followed) | backend/ingestion |
| D-6 | S1 | Delete leaves knowledge, tours, cache, usage behind | backend/tenancy |
| D-7 | S2 | Test suite hangs on reruns (shared state → replay) | backend/tests |
| D-8 | S2 | Replay turns skip the acknowledgement | backend/transport |
| D-9 | S2 | Non-HireBuddha sites can never navigate | backend/orchestrator |
| D-10 | S2 | Re-ingestion duplicates knowledge, overwrites tour | backend/ingestion |
| D-11 | S2 | `patch_component` never emitted | backend/orchestrator |
| D-12 | S3 | SDK `npm test` fails on modern Node | sdk/test |
| D-13 | S3 | Port drift across apps/docs | all |
| D-14 | S3 | Compose/ingestion folder paths wrong; no fluidbuddha assets | backend |
| D-15 | S3 | Default navigation hard-reloads SPA hosts | sdk |
| D-16 | S3 | Console: no install snippet, no settings page | console |
| D-17 | S4 | Real GCP project id committed | backend |
| D-18 | S4 | Model ids inconsistent across config | backend |
| D-19 | S4 | Console lint red; setState-in-effect | console |
| D-20 | S4 | Dependency CVEs incl. critical Next.js | console/sdk |
| D-21 | S4 | `CORS *` → allow-all on the admin app too | backend |

**Headline:** the engine is real and demos beautifully end to end, but it is **single-tenant in disguise** (D-4, D-9, D-10, D-14), **open to the public with no guard rails** (D-1, D-2, D-3, D-5), **doesn't truly delete** (D-6), and its **own test gate can't be trusted to run** (D-7). These are the gates to a credible second customer.

---

## Resolution status (branch `phase0/foundations`, 2026-11-03)

| ID | Status | How |
|---|---|---|
| D-1 | ✅ fixed | Per-website public widget key; `/chat` + `/ws/voice` resolve site and tier server-side; Origin checked against the site's domain |
| D-2 | ✅ fixed | Startup refuses the default/empty `JWT_SECRET` outside dev envs |
| D-3 | ✅ fixed | Per-site rate limit + daily spend cap on public turns |
| D-4 | ✅ fixed | Built-in site keys reserved; registered sites unreachable without their key |
| D-5 | ✅ fixed | SSRF-safe fetch (global IPs only, re-checked redirects, size/type caps); `call_site_api` path params URL-encoded; `tour_say` speaks stored narration only. Residual: DNS rebinding between check and connect |
| D-6 | ✅ fixed | Source delete removes its CORTEX nodes; website delete purges tree, tour, profile, caches, usage |
| D-7 | ✅ fixed | Per-test settings restore + cache truncation; `pytest-timeout`; green on reruns and on an empty DB |
| D-8 | ✅ fixed | Replays speak a short, audio-cacheable `ack_*` segment before the cached answer |
| D-9 | ✅ fixed | Per-site agent profile: name, personas, brand voice, routes (ingested URLs become routes) |
| D-10 | ✅ fixed | Re-ingest deletes a source's prior nodes first; a hand-edited tour is flagged and never overwritten by re-ingestion (only an explicit "Generate" replaces it) |
| D-11 | ✅ fixed | Thinker sees on-screen components; `patch_component` emits `DATA/patch` to a live `sync_id` (unknown ids refused); corrections route to the heavy path; patched turns aren't cached |
| D-12 | ✅ fixed | SDK smoke runs on Node ≥ 20 |
| D-13 | ✅ fixed | One port map: backend 8080, console 3001, demos 4000 |
| D-14 | ✅ fixed | Content paths configurable (`HIREBUDDHA_DOCS`, `BCL_DOCS`, `FLUIDBUDDHA_DOCS`) with defaults that match the real sibling layout; fluidbuddha copy comes from this repo; design-system/OpenAPI optional. Local discovery verified (46 HireBuddha docs); a full `docker compose up` was not run here (host port 8080 is reserved on this machine) |
| D-15 | ⏳ open (M1) | SPA-friendly `pushState` navigation — WS5 |
| D-16 | ✅ fixed | Console Install tab (snippet + connection test) and Settings tab (site, tiers incl. Level 3, agent profile, delete) |
| D-17 | ✅ fixed | Placeholder GCP project id |
| D-18 | ✅ fixed | Model ids reconciled |
| D-19 | ✅ fixed | Console lint clean (ESLint 9 flat config, no setState-in-effect) |
| D-20 | ✅ fixed | See status note under D-20 |
| D-21 | ✅ fixed | Path-scoped CORS: `CORS_ORIGINS` for the widget surface, `ADMIN_CORS_ORIGINS` (console only) for `/auth` + `/tenant` |

**Gate:** `.github/workflows/ci.yml` runs backend pytest (twice, against an ephemeral pgvector) + `pip-audit`, SDK typecheck/build/smoke + `npm audit --audit-level=high`, console lint/tsc/build + audit, on every push to `main` and every PR.

**Still open from Phase 0 (needs a decision, not code):** the claims policy is applied to `docs/product-docs/marketing_brief.md`, but `docs/website-copies/*` (the fluidbuddha site copy, which carries most of the 2.4× / 74 % / "0 % hallucination" claims) is deleted in the working tree and was left untouched — restore and rewrite it, or remove it from the repo. Product-name unification (Fluid-Buddha / fluid-buddha / FluidBuddha) is a brand call. Alembic migrations, Redis sessions and observability (F-3) remain, ahead of the M1 billing/conversation tables.
