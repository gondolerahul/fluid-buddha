# FluidBuddha — development handoff

*As of 4 November 2026 · `phase1/beta` is merged into `main`; follow-up work is on branch `phase1/finish` (local)*

This is the starting point for whoever continues the work. It says what exists,
how to run and check it, and what is left, in priority order. The detail behind
each item lives in three companion documents:

- [implementation-plan.md](implementation-plan.md) — every workstream, with a
  status row per Phase 1 item (what shipped, what's left).
- [defects.md](defects.md) — the 21 defects found in the original audit, all fixed,
  with how each was verified.
- [roadmap.md](roadmap.md) and [functionality-report.md](functionality-report.md) —
  the product direction and the original audit of the codebase.

---

## 1. Where things stand

FluidBuddha is a voice-first AI sales agent that a business embeds on its website
with one script tag. It has three parts in this repository:

| Part | Folder | What it is |
|---|---|---|
| Backend | [`backend/`](../backend) | FastAPI + Postgres/pgvector. The agent (router, lean and heavy thinkers), CORTEX knowledge memory, the voice WebSocket, the tenant/admin API, billing. |
| Widget SDK | [`fluid-buddha-sdk/`](../fluid-buddha-sdk) | The `<fluid-buddha>` web component (three design levels), voice capture and playback, the generated UI canvas. |
| Console | [`fluid-buddha-frontend/`](../fluid-buddha-frontend) | Next.js 16 / React 19 admin app: websites, knowledge, tours, insights, leads, analytics, experiments, billing. |

**Phase 0** ("safe and shippable to customer #2") is complete: tenant isolation,
public-surface security, data lifecycle, console activation, CI gate, dependency
upgrades — all 21 audited defects fixed.

**Phase 1** ("paid beta that proves ROI") is mostly complete. Done: trust layer
(WS8), insights (WS10), engine quality (WS5), self-serve onboarding (WS9), holdout
A/B (WS11), production plumbing (F-3). Partly done: revenue layer (WS7, the
integrations need real accounts) and billing (WS12, needs deployment and pricing
decisions). See §6 for everything left.

**Health at handoff:** backend 157 tests pass (2 Redis tests skip unless a Redis is
running), SDK typecheck, build and smoke tests all pass (core bundle 39.8 kB
gzipped against a 42 kB budget), console lint/typecheck/build clean, `pip-audit` and
`npm audit` clean.

---

## 2. Repository and branches

Remote: `github.com/gondolerahul/fluid-buddha`.

| Branch | Contents | Pushed? |
|---|---|---|
| `main` | Initial code + the four planning documents | Yes |
| `phase0/foundations` | `main` + 8 Phase 0 commits | **No** |
| `phase1/beta` | `phase0/foundations` + 16+ Phase 1 commits (current) | **No** |

`phase1/beta` contains all of Phase 0, so it is the branch to push and open a pull
request from. Each commit is one workstream (or one fix to it) with a descriptive
message; `git log --oneline main..phase1/beta` reads as a changelog.

Two working-tree items were deliberately left alone and should stay out of commits
until decided: the deleted `docs/website-copies/*.md` (see §6.2) and the untracked
`fluid-buddha-frontend/AGENTS.md` (written by `next dev`).

---

## 3. Running it locally

Prerequisites: Python 3.12, Node ≥ 20, Docker (for Postgres + pgvector).

```bash
# Database (Postgres + pgvector on host port 5434)
cd backend && docker compose up -d postgres

# Backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # bin/ on macOS/Linux
cp .env.example .env            # MOCK_AI=true runs with no Google Cloud account
.venv/Scripts/python -m uvicorn app.main:app --port 8080
# migrations apply automatically at startup (Alembic, under an advisory lock)

# Widget SDK — builds dist/ and serves the demos on :4000
cd fluid-buddha-sdk && npm install && npm run serve:demo

# Console on :3001
cd fluid-buddha-frontend && npm install
NEXT_PUBLIC_API_BASE=http://localhost:8080 npx next dev -p 3001
```

Gates (the same ones CI runs, [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)):

```bash
cd backend && .venv/Scripts/python -m pytest -q          # needs the Postgres above
cd fluid-buddha-sdk && npm run typecheck && npm run build && npm test
cd fluid-buddha-frontend && npm run lint && npx tsc --noEmit && npm run build
```

Notes from this machine:

- **Port 8080 is reserved on this Windows host**, so local runs here used **8081** for
  the backend (pass `NEXT_PUBLIC_API_BASE=http://localhost:8081` to the console).
- `next build` breaks a running `next dev` in the same folder — stop the dev server
  before building.
- The backend tests are hermetic: [`backend/tests/conftest.py`](../backend/tests/conftest.py)
  pins mock AI, empty payment keys, default prices etc., so a developer's `.env`
  can't change test results. Only the database URL comes from `.env`.
- The Redis tests run against `TEST_REDIS_URL` (default `redis://localhost:6380/15`):
  `docker run -d --rm -p 6380:6379 redis:7-alpine`.
- `MOCK_AI=true` uses deterministic engines (no model calls; retrieval quality is not
  meaningful). `MOCK_AI=false` needs Google Cloud credentials — see "Going live on
  Vertex AI" in [`backend/README.md`](../backend/README.md).

The backend README also documents each feature's operation: privacy, onboarding,
experiments, billing, and operations (metrics, tracing, Redis).

---

## 4. What has been built

### Phase 0 — foundations (branch `phase0/foundations`)

Tenant-aware brain (per-site agent profile, isolated knowledge trees), widget keys
with server-side site/tier resolution and an Origin check, rate limit and daily
spend cap, SSRF-safe URL fetching, true deletion (source and website), re-ingest
without duplication, console Install and Settings tabs, path-scoped CORS, secrets
hygiene, dependency upgrades, and a CI gate. Defect-by-defect status is in
[defects.md](defects.md).

### Phase 1 — paid beta (branch `phase1/beta`)

| Area | What it does now |
|---|---|
| **F-3 Migrations** | Alembic migrations `0001`–`0013` replace per-request DDL; applied at startup. |
| **WS8 Trust** | Answer citations in every design level; PII masked before the model and storage (leads still get the real email); microphone consent enforced server-side; per-site retention sweep and visitor erasure; pin/block cached answers. |
| **WS10 Insights** | Conversations and transcripts, top questions, knowledge gaps with "Answer this", visitor → engaged → lead funnel. |
| **WS7 Leads (v1)** | Leads from the enquiry form and the agent's `capture_lead` tool, with a score and summary; signed webhook delivery with retries; Slack alerts. |
| **WS5 Engine** | SPA-friendly navigation; AudioWorklet capture with pre-roll (first word not clipped); binary audio frames; streamed, pipelined TTS; Three.js only for Level 2 (core 612 → 141 kB); Level 2 reopens; follow-up questions use the previous question for retrieval. |
| **WS9 Onboarding** | "Crawl your website" (robots.txt, sitemap, depth/page limits, SSRF-guarded); PDF/DOCX uploads; personas from audience pages; brand colours/fonts from the site's CSS; preview bookmarklet. |
| **WS11 Holdout A/B** | A share of visitors get no widget; both groups measured on the site's own goal; Experiment tab with lift and an always-valid 95% interval (safe to check daily), a sample-size planner, and bots kept out. |
| **F-3 Plumbing** | Request ids in every response and log line; Prometheus `/metrics` incl. time to first audio; TTFA on Analytics; optional OpenTelemetry and Sentry (PII scrubbed); `REDIS_URL` shares chat sessions and the rate limit across replicas; per-site cost alerts (own threshold, 80 %/100 % of the daily cap) to Slack and the Analytics tab. |
| **WS12 Billing (Razorpay)** | Plans (Free / Growth / Scale / Enterprise), Razorpay subscriptions and Checkout, signed idempotent webhooks, Free cap, overage billing (add-on, or a payment link for UPI Autopay), plan changes (in place for cards, scheduled for the renewal for UPI), sync with Razorpay when webhooks are missing, cost per conversation. Razorpay was chosen over Stripe. |

New configuration introduced in Phase 1 is listed, commented, in
[`backend/.env.example`](../backend/.env.example) (retention sweep, crawl limits,
`INGEST_ALLOW_PRIVATE_URLS` for dev only, Redis, log format, metrics token,
OpenTelemetry, Sentry, Razorpay keys and webhook secret, billing currency and
catalog).

---

## 5. How it was verified

Beyond the automated gates, each workstream was exercised live on this machine
(mock AI, local Postgres) through the real console and widget:

- Trust layer: masked transcripts, consent dialog, pinned answers replaying.
- Engine: binary frames in the browser, Level 2 lazy load and reopen, in-app SPA
  navigation.
- Onboarding: a 6-page local test site crawled and ingested in 4 s; create → agent
  answering on the site in about a minute.
- Holdout: both arms seen in real widgets, a goal-page conversion counted, then 600
  simulated visitors giving a significant lift.
- Plumbing: two backend replicas sharing one Redis (session and rate limit crossed
  replicas), JSON logs with request ids, TTFA on Analytics.
- **Billing, against Razorpay test mode with your test keys:** plan and subscription
  created, Checkout paid, payment signature verified; renewal and overage simulated
  with locally signed webhooks; the UPI Autopay limits found and handled; a scheduled
  plan change created, its mandate approved by you, picked up without a webhook, and
  the old subscription cancelled at cycle end on Razorpay. The handover itself was
  simulated (it falls on 4 Dec).

---

## 6. Pending items

### 6.1 Before the first deployment (blocking)

1. **Push and review.** Phase 0 and Phase 1 are merged into `main` (CI green).
   Push `phase1/finish` and open a pull request for the follow-up work.
2. **Production configuration** (all in `.env.example`):
   - `APP_ENV` set to a non-dev value and a strong `JWT_SECRET` (startup refuses the
     default outside dev).
   - `CORS_ORIGINS=*` (or the customer origins) — the widget, leads and experiment
     calls come from customers' sites; `ADMIN_CORS_ORIGINS` = the console's URL.
   - `MOCK_AI=false` with Google Cloud credentials for Vertex.
   - `REDIS_URL` if running more than one backend replica.
   - `METRICS_TOKEN` (or restrict `/metrics` at the proxy); optionally
     `SENTRY_DSN` and `OTEL_EXPORTER_OTLP_ENDPOINT`.
3. **Razorpay:** live keys, and in Razorpay Dashboard → Webhooks add
   `<backend>/billing/razorpay/webhook` with the `subscription.*` events and
   `payment_link.paid`, then set `RAZORPAY_WEBHOOK_SECRET`. For USD prices,
   international payments must be enabled on the Razorpay account.
4. **Run against real Vertex once** before customers: streaming Gemini TTS, the LLM
   persona suggestion and real embedding quality have only run in mock mode.

### 6.2 Decisions (all made, 4 Nov 2026)

- **Billing numbers:** INR is the default catalog — Free 100 conversations,
  Growth ₹33,000 for 2,000 then ₹17 each, Scale ₹1,25,000 for 10,000 then ₹10.
  USD remains possible through `BILLING_CURRENCY` / `BILLING_CATALOG` once
  international payments are enabled on Razorpay.
- **Website copy:** `docs/website-copies/*` removed from the repo; the marketing
  site's text lives elsewhere and must follow the claims policy.
- **Product name:** written **FluidBuddha** everywhere customers see it; technical
  names (`<fluid-buddha>`, package and folder names) unchanged; the default agent
  is still "Pragya". New websites default to the widget gold `#c9a24a`.
- **UPI Autopay:** keep it (see the WS12 row of the implementation plan).

### 6.3 Remaining Phase 1 work

| Workstream | Left to do | Needs |
|---|---|---|
| WS7 Revenue | Native HubSpot, then Salesforce sync; inline meeting booking (Calendly / HubSpot Meetings); live takeover of a text chat by a human. | Real sandbox accounts for each service. |
| WS12 Billing | Real webhooks once deployed; tax (GST) invoices and a billing contact are on Razorpay's side; no payment-failure reminder emails of our own. | Deployment. |
| F-3 Plumbing | Time to first audio measured in the browser (network + playback), not just the server. | — |
| WS8 Trust | Detect names and street addresses (masking is pattern-based today); a privacy notice for visitors who only type; apply retention to the agent's long-term (CORTEX episodic) memory. | — |
| WS5 Engine | Split the widget stylesheet per design level (about a third of the core bundle); an optional model-based rewrite for follow-ups the heuristic misses. | — |
| WS9 Onboarding | Client-rendered sites yield little text (needs a headless-browser fetch); a re-crawl doesn't remove pages that disappeared. | — |
| WS11 Holdout | Comparing results across runs; bot filtering is by User-Agent and `navigator.webdriver` only (no behavioural signals). | — |
| WS10 Insights | The "meetings" stage of the funnel. | WS7 booking. |

### 6.4 Not yet verified

- Card payments in Razorpay Checkout from the console (the in-app test browser can't
  open Razorpay's bank popup; your own browser can).
- Allowing the microphone in a real browser (only declining was clicked through;
  allowing is covered by the SDK tests).
- A full `docker compose up` of the backend container (this host reserves port 8080).
- A real multi-day billing cycle, i.e. a renewal and handover arriving as real
  webhooks.

### 6.5 Known limitations and risks

- The SSRF guard checks addresses when resolving, so a DNS-rebinding host could still
  switch addresses before connecting; closing this needs an egress-restricted fetcher.
- With `REDIS_URL`, chat sessions hold the real values behind PII placeholders until
  they expire (`SESSION_TTL_MINUTES`, default 30), so a lead captured later in the
  conversation still gets the real email.
- If a customer site's origin isn't allowed by `CORS_ORIGINS`, the widget can't enrol
  visitors in an experiment and silently shows everyone the agent.
- Razorpay won't add charges to, or change the plan of, a UPI Autopay subscription;
  the workarounds (payment link, scheduled switch) are built, but a UPI customer
  pays overage through a separate link.

### 6.6 After Phase 1

Milestones M2 (repeatable growth: Insights v2, proactive triggers, CMS plugins,
RBAC/SSO, SOC 2 Type I…) and M3 (platform: generative landing pages, MCP endpoint,
omnichannel, enterprise deployment) are summarised in Part C of the
[implementation plan](implementation-plan.md) and detailed in the
[roadmap](roadmap.md).

---

## 7. State left on this development machine

These are not in the repository; they matter only to whoever continues on this
machine or this Razorpay test account.

- **Dev database** (Docker container `a2ui-cortex-db`, port 5434) holds test data: a
  "Trust Demo" tenant with the "Acme Robotics" website used for the live checks
  (crawled test site, experiment runs, simulated visitors), plus tenants created by
  the test suite. Safe to wipe with `docker compose down -v` if a clean start is
  wanted.
- **Razorpay test account:** the Trust Demo account is on Growth (UPI, active until
  4 Dec 2026) with a switch to Scale scheduled for 4 Dec (approved by card). One
  ₹34 overage payment link is unpaid. All test mode — no real money.
- **`backend/.env`** (git-ignored) currently has `MOCK_AI=false`, and the Google
  Cloud application-default login on this machine has expired
  (`gcloud auth application-default login` to renew). It also holds the Razorpay test
  keys and INR prices. The webhook secret is empty until deployment.
- No test credentials or keys are stored in the repository.

---

## 8. Working conventions

- One workstream per commit, staged file by file; commit messages explain the why.
- Every schema change is a new Alembic migration in `backend/migrations/versions/`;
  never edit a committed one.
- New behaviour comes with tests (backend pytest, SDK smoke checks); the backend
  suite must stay hermetic (see §3).
- The console has no test suite of its own: lint, typecheck and build are its gate,
  plus a live check in the browser.
- Billing is tested against an in-memory fake of the Razorpay API
  ([`backend/tests/test_billing.py`](../backend/tests/test_billing.py)) that mirrors
  Razorpay's request and response shapes, including its UPI Autopay refusals.
