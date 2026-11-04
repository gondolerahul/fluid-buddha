# Fluid-Buddha — Comprehensive Implementation Plan

**Date:** 2026-11-03
**Author:** Durwanku Rai Lab (durwankurailab@gmail.com), with Claude Code
**Status:** Planning. Nothing here is built yet.

## What this document is

A single, sequenced engineering backlog that unifies everything found so far:

- **[functionality-report.md](functionality-report.md)** — what exists today (the "F-§" references below point at its sections).
- **[roadmap.md](roadmap.md)** — the product/GTM direction (the "Bet N" and "Phase N" references point at its §3 and §4).
- **[defects.md](defects.md)** — what is broken, degraded or unsafe (the "D-N" references).

Each epic states its **sources** (which report gap, which roadmap bet/phase, which defect IDs it closes), concrete **tasks** with `file:line` anchors, **acceptance criteria**, and **tests**. Part E is a coverage matrix proving every defect and every Phase-0/1 roadmap item lands in an epic. Part F is the first two-week sprint.

Legend: 🔴 blocks customer #2 · 🟠 needed for paid beta · 🟢 growth/vision · ⏱️ effort S/M/L.

---

## Part A — Guiding sequence

The dependency order is non-negotiable in one respect: **the security and multi-tenancy gates (M0) must land before any new customer touches the system, and before any revenue feature is worth building.** A beautiful lead-capture flow on an endpoint anyone can impersonate (D-1, D-2) is wasted work.

```
M0  Safe & multi-tenant  ──►  M1  Paid-beta value  ──►  M2  Repeatable growth  ──►  M3  Platform & vision
(weeks 0–4, Phase 0)          (months 1–3, Phase 1)      (months 3–6, Phase 2)      (months 6–12, Phase 3)
   │                              │
   ├─ WS1 Tenant brain            ├─ WS7 Revenue layer
   ├─ WS2 Public-surface security ├─ WS8 Trust layer
   ├─ WS3 Data lifecycle          ├─ WS9 Self-serve onboarding
   ├─ WS4 Console activation      ├─ WS10 Insights v1
   ├─ WS6 Test/CI/quality gate    ├─ WS11 Holdout A/B
   └─ WS15 Marketing hygiene      ├─ WS12 Pricing/billing
                                  └─ WS5 Protocol/engine quality
```

WS5 (protocol/engine quality) spans M0→M1: the parts that are correctness bugs (D-8, D-11) ride with M0; the experience upgrades (AudioWorklet, streaming TTS, lazy Three.js) ride with M1.

---

## Part B — Cross-cutting foundations (do these first inside M0)

These unblock everything and several are prerequisites for trustworthy delivery.

### F-1 · Trustworthy test & CI gate 🔴 ⏱️M — closes **D-7, D-12**, enables all
The suite currently hangs on reruns and the SDK test fails on modern Node, so no change can be verified. Fix this before building on top.

- Isolate backend tests: wrap each in a transaction rolled back at teardown, **or** give each module a throwaway schema; stop relying on a shared seeded DB.
- Restore any mutated runtime settings in fixture teardown — the leak of `episodic_min_episodes` (set in `test_analytics_*`/`test_cache`) is the direct trigger of the D-7 hang.
- Add a hard per-test timeout (`pytest-timeout`) so a WebSocket stall becomes a failure, never an infinite hang.
- Fix the SDK harness: replace `globalThis.navigator = …` with `Object.defineProperty(globalThis,'navigator',…)` ([fluid-buddha-sdk/test/smoke.mjs:14](../fluid-buddha-sdk/test/smoke.mjs)); add an `engines` field to `package.json`.
- Stand up CI: backend pytest against an **ephemeral pgvector** service, SDK `tsc` + smoke, console `lint` + `build`.
- **Acceptance:** `pytest -q` is deterministic and green on repeated runs with a non-empty DB; `npm test` (SDK) green on Node ≥ 20 unmodified; CI runs all three on PR.

### F-2 · Config, secrets & environment hygiene 🔴 ⏱️S — closes **D-2, D-13, D-14, D-17, D-18, D-21**
- Make `JWT_SECRET` required outside local; refuse to boot on the known dev value ([backend/app/config.py:71](../backend/app/config.py)).
- Replace the committed GCP project id with a placeholder ([backend/.env.example:30](../backend/.env.example)); reconcile model ids across `.env.example` and `docker-compose.yml` (pick one: the report describes Gemini 2.5).
- One canonical port map (propose: backend 8080, console 3001, demos 4000) applied to `.env.example` CORS, console `package.json`, and all three demo files ([demo/index.html](../fluid-buddha-sdk/demo/index.html), [level2.html](../fluid-buddha-sdk/demo/level2.html), [level3.html](../fluid-buddha-sdk/demo/level3.html)). Centralise the backend URL in the demos.
- Fix compose content mounts and the hardcoded sibling-folder assumptions ([ingestion/scraper.py:23](../backend/ingestion/scraper.py)); commit or generate the missing `fluidbuddha-website` assets; make content dirs configurable with in-repo defaults.
- Split CORS: wide-open is acceptable for the public widget, not for the admin API on the same app ([backend/app/main.py:48](../backend/app/main.py)) — scope per router or per deployment.
- **Acceptance:** a clean checkout runs `docker compose up` and seeds HireBuddha with no manual path/CORS edits; startup fails loudly if the secret is default in a non-local env.

### F-3 · Schema migrations & production plumbing 🟠 ⏱️M — enables M1 scale (roadmap Phase 0 "Production plumbing")
- Introduce Alembic; replace per-request `CREATE TABLE IF NOT EXISTS` (`ensure_table`/`ensure_tables` patterns across `app/tenancy/*`, `app/cortex/episodic.py`).
- Redis for session state (today `store.get_or_create` is in-process, so the server can't scale horizontally — F-§ runtime).
- Observability: OpenTelemetry spans per turn (router/thinker/TTS), Sentry, **time-to-first-audio** metric, per-tenant cost alerts.
- **Acceptance:** schema changes ship as migrations; two backend replicas share sessions; a turn produces a trace.

### F-4 · Dependency remediation 🟠 ⏱️S — closes **D-20**
- Bump `next` off the vulnerable `16.2.7` (critical RCE + SSRF advisories) and the flagged `zod`/`postcss`/`nanoid`/`sharp`; address the SDK `fflate`/`esbuild` moderates.
- Add `npm audit` (high+ fails) to CI.
- **Acceptance:** `npm audit` reports no critical/high in either JS package; CI enforces it.

---

## Part C — Milestone M0: "Safe & shippable to customer #2" (weeks 0–4, roadmap Phase 0)

Exit gate for the whole milestone: *an unrelated company installs from a console snippet; their agent uses their name, personas, sitemap and tour; a red-team pass cannot read another tenant's knowledge, raise its own tier, or run up spend.*

### WS1 · Tenant-aware brain 🔴 ⏱️M
**Sources:** F-§ multi-tenancy gaps · roadmap Phase 0 "De-HireBuddha the brain" · **D-4, D-9, D-10**

1. **Per-site agent profile** (stored, console-editable): agent name/voice, company name, brand voice, personas (label, focus, tone, landing route), closing use-case template. Replace the hard-coded prompt text ([prompts.py:9](../backend/app/orchestrator/prompts.py)), `VALID_PERSONAS` ([personas.py:10](../backend/app/orchestrator/personas.py)), and tour copy ([tour.py:93](../backend/app/orchestrator/tour.py)).
2. **Per-tenant CORTEX isolation (D-4):** key trees by a stable site id / `tenant_id`, not a human slug; **reserve** the built-in keys (`hirebuddha`, `fluidbuddha`, `buddha-cognitive-lab`) so a tenant can't claim them.
3. **Per-site sitemap (D-9):** auto-derive routes at ingestion and store a route per source; drop the hardcoded `_SITEMAPS` dict ([sitemap.py:53](../backend/app/orchestrator/sitemap.py)) in favour of a per-site lookup; add a console editor.
4. **Idempotent re-ingestion (D-10):** delete a source's prior nodes before re-adding ([ingestion/ingest.py:62](../backend/ingestion/ingest.py)); make tour re-planning explicit so it never silently overwrites a hand-edited tour.
- **Acceptance:** a second site answers in its own voice/personas, navigates its own pages, and re-ingesting a source neither duplicates nodes nor clobbers an edited tour. A tenant cannot create or read the `hirebuddha` tree.
- **Tests:** two-tenant isolation test (no cross-tree retrieval); navigation test for a non-HireBuddha site; re-ingest-idempotency test.

### WS2 · Public-surface security 🔴 ⏱️M
**Sources:** F-§ known issues/security · roadmap Phase 0 "Lock down the public surface" + Bet 3 security · **D-1, D-2, D-3, D-5, D-21**

1. **Public widget key per website.** `/ws/voice` ([websocket.py:736](../backend/app/transport/websocket.py)) and `/chat` ([chat.py:43](../backend/app/routes/chat.py)) resolve `site` from the key — never from client input — check `Origin` against the website's domain allow-list, and **enforce the tenant's configured intelligence/design tier server-side** (ignore client `intelligence`).
2. **Rate limits** per IP/session/site + a per-site daily **spend cap** with alerts (D-3). Trip to text-only or cached response at the ceiling.
3. **`tour_say` lockdown:** speak only narration present in the stored plan, matched by index + hash ([websocket.py:244](../backend/app/transport/websocket.py)) — removes the free-TTS-relay.
4. **SSRF guard (D-5):** block private/link-local/metadata ranges, disable or re-validate redirects, cap size/time/content-type on URL sources ([sources.py:195](../backend/app/tenancy/sources.py)); URL-encode `call_site_api` path params ([registry.py:136](../backend/app/apis/registry.py)).
5. **Secret + CORS** handled in F-2 (D-2, D-21); plan an httpOnly-cookie session for the console.
- **Acceptance:** a red-team checklist passes — no cross-tenant read via `site`, no client tier escalation, no unbounded spend, no internal fetch via a URL source, no arbitrary TTS via `tour_say`.
- **Tests:** auth/authorization tests per public route; an SSRF unit test with a blocked target; a tier-enforcement test; a rate-limit test.

### WS3 · Data lifecycle correctness 🔴 ⏱️S
**Sources:** F-§ data lifecycle · roadmap Phase 0 "Data lifecycle correctness" · **D-6, D-10**
- Deleting a source removes its CORTEX nodes; deleting a website purges (or archives on a retention schedule) its tree, `site_tours`, `conversation_cache`, `answer_audio_cache`, `usage_events` — one transaction ([sources.py:127](../backend/app/tenancy/sources.py), [store.py:255](../backend/app/tenancy/store.py)).
- Version-stamp knowledge per ingestion; invalidate/re-validate cached answers on change; filter replay by `page` ([episodic.py](../backend/app/cortex/episodic.py)).
- **Acceptance:** after deleting a source the agent no longer cites it and no cached answer replays it; deleting a website leaves zero orphan rows; a stale cached answer is invalidated when its source changes.
- **Tests:** delete-source-purges-knowledge; delete-website-cascade; cache-invalidation-on-reingest.

### WS4 · Console activation 🔴 ⏱️S
**Sources:** F-§ admin console · roadmap Phase 0 "Activation basics" · **D-16, D-19**
- **Install tab:** copy-paste `<script>` snippet pre-filled with the site's public key + options, plus a "test connection" check.
- **Settings tab:** edit name/domain/accent/intelligence/design (**add Level 3** to the design options) and the agent profile — wire the unused `PATCH /tenant/websites/{id}`.
- Fix the lint gate and the `set-state-in-effect` patterns ([WebsiteContext.tsx:20](../fluid-buddha-frontend/src/components/WebsiteContext.tsx), analytics/cache pages) and the `no-explicit-any` in [lib/api.ts:64](../fluid-buddha-frontend/src/lib/api.ts) (D-19).
- **Acceptance:** a new tenant copies the snippet and sees their agent live; they can rename the agent and change tiers from the UI; `next lint` runs clean.
- **Tests:** console build + lint in CI; an e2e that creates a site and asserts the snippet contains the key.

### WS15 · Marketing & naming hygiene 🔴 ⏱️S
**Sources:** roadmap §2.3–2.4 · F-§ overclaims
- Apply the claims policy (remove/replace 2.4×, 74 %, 80 %, "0 % hallucination", "< 300 ms", CRM-sync and PDF-ingestion claims until built); unify the product name and default accent; commit or restore `docs/website-copies` (currently deleted in the working tree).
- **Acceptance:** no public claim lacks instrumentation or a shipped feature behind it.

---

## Part C — Milestone M1: "Paid beta that proves ROI" (months 1–3, roadmap Phase 1)

Exit gate: *≥5 paying design partners, ≥1 with a statistically supported lift vs. a holdout, time-to-live < 15 min.*

### WS5 · Protocol & engine quality 🟠 ⏱️M
**Sources:** F-§ engine/SDK · roadmap Phase 1 "Experience quality" · **D-8, D-11, D-15** (+ ASR clip, L2 reopen, lazy Three.js)
- **D-11:** make `patch_component` emit a real `DATA/patch` targeting the given `sync_id` ([thinker.py:263](../backend/app/orchestrator/thinker.py)); wire the SDK `applyPatch` path end to end with a test.
- **D-8:** emit a short (cacheable) ack on the replay path, or formally document ack-less replays and make SDK/tests tolerant ([websocket.py:604](../backend/app/transport/websocket.py)).
- **D-15:** default HostBridge navigation to History API/`pushState` and prominent host-intercept hook, so SPA hosts aren't hard-reloaded.
- AudioWorklet capture with a pre-roll buffer (first ~180 ms not lost — [Session.ts:243](../fluid-buddha-sdk/src/core/Session.ts)); binary WS audio frames; true streaming TTS.
- Lazy-load Three.js only for Level 2 (ship the ~35 kB L1/L3 core the docs promise); let L2 reopen after close ([Level2Shell.ts](../fluid-buddha-sdk/src/ui/level2/Level2Shell.ts)).
- Query rewriting with conversation history before retrieval (fixes follow-ups).
- **Acceptance:** a correction updates an existing component in place; cache hits feel identical to fresh answers; L1 bundle meets the size budget; L2 reopens; first-word audio isn't clipped.

### WS7 · Revenue layer 🟠 ⏱️M
**Sources:** roadmap Bet 1 / Phase 1
- Conversational lead capture + a `Lead` object (contact, score, persona, summary, transcript link); replace the simulated `enquiry_form`→LLM path with a validated, PII-safe submission ([FluidBuddhaElement.ts:154](../fluid-buddha-sdk/src/ui/FluidBuddhaElement.ts)).
- Inline booking (Calendly, HubSpot Meetings); HubSpot CRM sync first, then Salesforce; generic webhooks + Zapier; replace simulated `call_site_api` with real connectors ([registry.py](../backend/app/apis/registry.py)).
- Slack hot-lead alerts + text live-takeover from the console.
- **Acceptance:** a conversation produces a scored lead in HubSpot with summary + transcript link, and a booked meeting; an operator can take over by text.

### WS8 · Trust layer 🟠 ⏱️S–M
**Sources:** roadmap Bet 3 / Phase 1
- Show citations in every design level (data already in `grounding.sources`); mic/recording consent UX; PII redaction before storage and before the LLM; retention settings; a "golden answers" approval toggle on cached responses.
- **Acceptance:** every answer shows sources; consent is captured before mic use; a cached answer can be pinned/blocked.

### WS9 · Self-serve onboarding 🟠 ⏱️M–L
**Sources:** roadmap Bet 2 / Phase 1
- Real sitemap crawler (robots.txt, depth limits, the SSRF guard from WS2); PDF/DOCX extraction; auto-derived personas + anchors; design-token extraction from site CSS; hosted "preview on your site" link (bookmarklet).
- **Acceptance:** paste-URL → crawl → ingest → preview in < 15 min, measured.

### WS10 · Insights v1 🟠 ⏱️M
**Sources:** roadmap Bet 4 / Phase 1
- Transcript viewer; top questions; unanswered/low-confidence questions (guardrail already flags `found=false`) with one-click "add source"; funnel (visitors→engaged→leads→meetings). Add a **conversation**-level table.
- **Acceptance:** the console shows a knowledge-gap list and a funnel for a live site.

### WS11 · Holdout A/B 🟠 ⏱️S
**Sources:** roadmap Bet 5 / Phase 1
- Agent-off for ~10 % of traffic; measure causal lift in demo bookings/leads; feed the first honest case study.
- **Acceptance:** a dashboard shows lift vs. holdout with a confidence interval.

### WS12 · Pricing & billing 🟠 ⏱️S–M
**Sources:** roadmap §5 / Phase 1
- Razorpay billing (chosen over Stripe) on the new plan structure (Free / Growth $399 / Scale $1,499 / Enterprise); plan caps + overage on top of `usage_events` ([pricing.py](../backend/app/analytics/pricing.py)); surface **cost per conversation** and **time-to-first-audio** on the analytics page.
- **Acceptance:** a plan enforces its conversation allowance and bills overage; margin per conversation is visible.

---

## Part C — Milestones M2 & M3 (roadmap Phases 2–3, summarized)

These inherit the roadmap's detail; listed here so the backlog is complete.

**M2 · Repeatable growth (months 3–6, Phase 2)** 🟢
Insights v2 (objection/competitor mining, weekly CMO digest) · experimentation engine · proactive triggers (pricing dwell, exit intent, return) · shareable recap pages · CMS plugins (WordPress/Webflow/Framer/Shopify) + GTM + React/Vue wrappers · custom-component SDK + actions marketplace · team/RBAC/SSO/audit log · vertical templates · voice handoff (WebRTC) · SOC 2 Type I + EU residency + DPA.

**M3 · Platform & vision (months 6–12, Phase 3)** 🟢
Generative landing pages (Extreme GA) · agent/MCP endpoint · returning-visitor memory (opt-in) · omnichannel (Twilio/WhatsApp/email) · enterprise (VPC/on-prem, BYO-model via `app/ai/base.py`, SOC 2 Type II, SLA) · partner/white-label programme.

---

## Part D — Sequencing & dependencies

**Critical path to customer #2 (M0):** F-1 (test gate) → F-2 (config/secrets) → WS1 (tenant brain) + WS2 (security) in parallel → WS3 (lifecycle) → WS4 (console activation). WS15 and F-4 run alongside. WS6 CI (in F-1) gates everything.

**Hard dependencies:**
- WS2's widget key is a prerequisite for WS4's install snippet and for WS7/WS9 (anything the public widget does).
- WS1's per-tenant isolation must precede any onboarding of real tenant data (WS9) and any revenue data (WS7) — otherwise you store customer leads against a shared slug.
- F-3 migrations should land before WS12 billing schema and WS10's conversation table.
- WS11 holdout depends on WS7's lead/meeting events existing.

**Parallelizable:** WS5 engine fixes are independent of the tenancy/security work and can proceed in a separate stream; WS8 citations need only existing `grounding` data.

---

## Part E — Coverage matrix (every defect lands somewhere)

| Defect | Sev | Addressed by |
|---|---|---|
| D-1 unauthenticated widget / client picks site+tier | S1 | WS2.1 |
| D-2 default JWT secret | S1 | F-2 |
| D-3 no rate/spend limit | S1 | WS2.2 |
| D-4 tenant can claim `hirebuddha` key | S1 | WS1.2 |
| D-5 SSRF via URL sources | S1 | WS2.4 |
| D-6 delete leaves knowledge | S1 | WS3 |
| D-7 test suite hangs on reruns | S2 | F-1 |
| D-8 replay skips ack | S2 | WS5 |
| D-9 non-HireBuddha sites can't navigate | S2 | WS1.3 |
| D-10 re-ingest dup + tour overwrite | S2 | WS1.4 / WS3 |
| D-11 `patch_component` never emitted | S2 | WS5 |
| D-12 SDK npm test fails on modern Node | S3 | F-1 |
| D-13 port drift | S3 | F-2 |
| D-14 compose/ingestion paths wrong | S3 | F-2 |
| D-15 default nav hard-reloads SPA | S3 | WS5 |
| D-16 console: no install/settings | S3 | WS4 |
| D-17 real GCP id committed | S4 | F-2 |
| D-18 model ids inconsistent | S4 | F-2 |
| D-19 console lint red / setState-in-effect | S4 | WS4 / F-1 |
| D-20 dependency CVEs | S4 | F-4 |
| D-21 `CORS *` on admin app | S4 | F-2 / WS2.5 |

All 21 defects are covered; all roadmap Phase-0 checklist items map to WS1–WS4 + WS15 + F-1/F-2/F-3.

---

## Part F — First two-week sprint (concrete start)

A focused slice of M0 that makes the gate reachable and de-risks the rest.

**Week 1 — make the ground trustworthy**
1. F-1: isolate tests (per-test transaction/rollback), restore mutated settings, add `pytest-timeout`; fix the SDK `navigator` shim. Green, deterministic reruns. *(closes D-7, D-12)*
2. F-2: require `JWT_SECRET`, scrub the GCP id, reconcile model ids, pick the port map, fix compose mounts. Clean `docker compose up` seeds HireBuddha. *(closes D-2, D-13, D-14, D-17, D-18)*
3. Stand up CI running backend/SDK/console against an ephemeral pgvector.

**Week 2 — the security + tenancy spine**
4. WS2.1: introduce the public widget key; make `/chat` and `/ws/voice` resolve site server-side and enforce tier; add an Origin check. *(starts closing D-1)*
5. WS2.2: a basic per-site rate limit + daily spend cap. *(closes D-3)*
6. WS1.2: reserve the built-in site keys and key CORTEX trees by stable id. *(closes D-4)*
7. WS3 (first half): cascade source deletion into CORTEX. *(starts closing D-6)*

**End-of-sprint demo:** a second tenant, created through the console, gets a widget key; its widget answers only from its own (empty-then-ingested) tree; it cannot select a higher tier or the `hirebuddha` knowledge; the test suite is green on a seeded DB in CI.

---

## Appendix — environment the plan assumes (verified this session)

Python 3.12 venv, Node ≥ 20, Postgres+pgvector on 5434 (Docker), `MOCK_AI=true` for local/CI. All three subsystems build and run locally today; the backend seeds 334 nodes from the 9 HireBuddha docs and the full voice→UI round-trip works end to end in mock mode. See [defects.md §0](defects.md) for the exact run setup and what passed.

---

## Progress — Phase 1 (branch `phase1/beta`, 2026-11-03)

| Item | Status | What shipped / what's left |
|---|---|---|
| F-3 migrations + plumbing | ✅ | Alembic (`backend/migrations/`), applied at startup under an advisory lock; no DDL left on the request path (a test enforces it). Request ids on every response and log line (JSON logs optional); Prometheus `/metrics` with time to first audio (and to first answer audio), turn and stage timings, engine errors; TTFA stored per voice turn and shown on Analytics (median, p95). Optional OpenTelemetry spans per turn stage and Sentry with visitor text scrubbed. `REDIS_URL` shares chat sessions and the rate limit between replicas (checked live with two replicas); the in-process store now expires idle sessions and is capped, and a session id only works on its own site. **Left:** per-tenant cost alerts; TTFA as heard in the browser (network + playback) isn't measured; Redis sessions hold PII placeholder values until they expire. |
| WS8 trust layer | ✅ | Citations in all three design levels, kept on replays. PII masking before the model and before storage (placeholders the model can pass to `capture_lead`; transcripts store labels; PII turns never cached). Mic consent prompt in every design level, enforced server-side, time of consent stored. Per-site retention with an hourly sweep, and visitor erasure by email. Golden answers: pin (always replay, survives content changes and retention) or block (never replay). **Left:** name/address detection (pattern-based only today), consent notice for text-only chats, CORTEX episodic-tree retention. |
| WS10 Insights v1 | ✅ | Conversation + turn store; top questions, knowledge gaps (closing once answered) with one-click "Answer this", visitors → engaged → leads funnel, transcript viewer. **Left:** meetings stage (needs booking). |
| WS7 revenue layer | 🟡 | Leads from the enquiry form (no LLM) and the `capture_lead` tool; transparent score + summary; signed webhook (Zapier/Make/CRM) with retries; Slack hot-lead alerts; Leads tab + integrations settings. **Left:** native HubSpot then Salesforce sync, inline booking (Calendly/HubSpot Meetings), text live-takeover — all need real accounts to build against. |
| WS5 engine quality | ✅ | D-15: SPA-friendly navigation (pushState + popstate, page load only if nothing re-renders, cancelable event, `navigation` option). AudioWorklet mic capture (ScriptProcessor fallback) with a 400 ms pre-roll so the first word reaches ASR, and drift-free resampling. Binary audio frames both ways, negotiated per socket. TTS synthesised one sentence ahead; Gemini TTS streamed with a one-shot fallback. Three.js loaded only for Level 2 (script-tag core 612 → 141 kB, 39 kB gzipped; size budget in the SDK test). Level 2 reopens after close. Follow-up questions retrieved with the question they follow, and kept out of the answer cache. **Left:** split the stylesheet per design level (about a third of the core); streaming TTS not yet tried against live Vertex; an optional LLM query rewrite for follow-ups the heuristic misses. |
| WS9 self-serve onboarding | ✅ | "Crawl your website" in the console: robots.txt (incl. Crawl-delay, 401/403 = keep out), sitemap seeding, same-site BFS with depth/page limits, every fetch SSRF-guarded; pages ingested from the fetched text and added as routes; linked PDFs read. PDF/DOCX uploads (10 MB). Personas from audience URLs (or a real model's suggestion), only when the site has none. Design tokens from the homepage CSS, used by `/design-system`, with one-click "use as widget accent". Preview-on-your-site bookmarklet. Creating a site with a domain goes straight to the crawl. Measured locally: a 6-page site crawled and ingested in 4 s, and from create to the agent answering on the site in about a minute. **Left:** client-rendered sites with no server HTML yield little (needs a headless-browser fetch); a re-crawl doesn't remove pages that disappeared; section anchors come from the live page at runtime rather than the crawl; LLM persona suggestion untested against a real model; DNS-rebinding residual risk of the guarded fetch remains. |
| WS11 holdout A/B | ✅ | Per-site holdout runs (1-50%, default 10%): the widget enrols an anonymous visitor id, held-out visitors get no widget, and both arms are measured on the site's own goal (goal page or `FluidBuddha.conversion()`), not on agent-captured leads (only one arm can make those). Experiment tab: Wilson rates per arm, difference with a Newcombe 95% CI, relative lift, p-value, trend by day, goals. Checked live on a local site, then 600 simulated visitors gave +9.4 pts (95% CI +4.7 to +14.1). **Left:** no sequential-testing correction (don't stop the moment it turns green); no sample-size planner; bots aren't filtered; a run's results are per run with no comparison across runs; CORS must allow the customer's origin or nobody is enrolled. |
| WS12 pricing & billing | 🟡 | Razorpay subscriptions (instead of Stripe): plan catalog (Free 100 / Growth $399 for 2,000 / Scale $1,499 for 10,000 conversations, overage $0.20 / $0.12; Enterprise by arrangement; currency and prices configurable), Razorpay plans created on first use per API key, Checkout with signature verification, upgrades now / downgrades at cycle end, cancel at cycle end, signed idempotent webhooks, last cycle's overage added to the subscription as an add-on at renewal. Free caps new conversations (ongoing ones finish). Console Billing page with usage meter, plans, per-site cost and cost per conversation (also on Analytics). Tested against a faked Razorpay. **Left:** a run against Razorpay test mode with real keys and a webhook URL; included allowances and overage rates are placeholders to confirm; GST/tax invoices and a billing contact are Razorpay-side; no dunning emails of our own. |
