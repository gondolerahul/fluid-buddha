# FluidBuddha — Milestones 2 & 3: detailed plan

**Date:** 2026-11-04 · **Builds on:** [implementation-plan.md](implementation-plan.md) (M0/M1, done),
[roadmap.md](roadmap.md) Phases 2–3 and Bets 1–7, [handoff.md](handoff.md) (current state).

M2 ("repeatable growth") and M3 ("platform and vision") turned into buildable epics. Each epic
lists **why**, **what to build** (with the code it touches), **acceptance**, **tests**, and **what
it needs from outside** (accounts, keys, people). Part D gives the build order.

---

## Part A — Scope and decisions

### Out of scope (decided 2026-11-04)

| Roadmap item | Decision |
|---|---|
| Omnichannel (phone/Twilio, WhatsApp, email follow-up as a channel) | **Not building.** |
| Partner programme / white-label | **Not building.** |
| Reverse-IP firmographics (company-from-IP) | **Skipped.** Proactive triggers use on-site behaviour only. |
| EU / multi-region data residency | **India only for now.** Code keeps no region assumptions that would block adding one later. |
| SAML SSO | Not now (Google + generic OIDC only). |
| Kubernetes / Helm | Not now (Docker Compose self-host only). |

### Decisions that shape the build

| Topic | Decision | Consequence |
|---|---|---|
| Email | **Plain SMTP**, any provider | One `SMTP_*` config; an outbox table with retries; no vendor SDK. |
| Team login / SSO | **Google + generic OIDC** (Okta, Microsoft Entra, Auth0, Keycloak…) | OIDC authorization-code flow with PKCE; per-account SSO config; optional "SSO required". |
| Bring-your-own model | **Anthropic, OpenAI, Azure OpenAI** (alongside Vertex) | New engines behind `app/ai/base.py`; per-account encrypted keys. |
| Languages | **English + Hindi (incl. Hinglish)** first | Language detection, Hindi prompts, Hindi voices, widget strings in both; mechanism extends to more later. |
| Install surfaces | **WordPress, Shopify, Webflow + Framer, GTM + React/Vue** | Built in a new `integrations/` folder; store listings need your developer accounts. |
| Live voice handoff | **Self-hosted coturn** relay | Compose service + time-limited TURN credentials (`use-auth-secret`). |
| Payment action | **Razorpay first** (customer's own keys) | Agent creates a Payment Link for the visitor; Stripe can follow the same interface. |
| SOC 2 | **Technical controls + policy documents in the repo** | `docs/compliance/` + controls in code; certification itself needs an auditor (you). |
| Self-hosting | **Docker Compose only** + licence key | Offline-verifiable signed licence; backup/restore and upgrade runbooks. |
| Vertical templates | **B2B SaaS, Education/admissions, Real estate, Healthcare clinics** | Template packs applied at site creation; healthcare has a "no medical advice" guardrail. |

---

## Part B — Milestone 2: "Repeatable growth"

Exit gate: *a customer's team (several people, SSO) runs the agent in English or Hindi, gets a
weekly email of what visitors asked and objected to, A/B tests greetings and proactive
triggers against conversion, takes over hot conversations live, and installs from their CMS
in minutes; visitors leave with a shareable recap.*

### M2-0 · Platform foundations: email + scheduled jobs 🔴 ⏱️S
**Why:** digests, recaps, invitations and alerts all need email; digests need a scheduler.
Today nothing sends email and the only background loop is the retention sweep
(`app/trust/retention.py`, started in `app/main.py` lifespan).

- `app/notify/email.py`: SMTP sender (`SMTP_HOST/PORT/USERNAME/PASSWORD/FROM`, STARTTLS or
  implicit TLS), plain-text + HTML bodies, `List-Unsubscribe` for digests. With no SMTP
  configured, emails are written to the log in dev (and refused in production with a clear error).
- `email_outbox` table (migration): queued → sent / failed, attempts, last error, next attempt
  (exponential backoff), idempotency key. Senders enqueue; a worker loop delivers. Survives restarts.
- `app/jobs/scheduler.py`: one small in-process scheduler for periodic jobs (retention sweep
  moves onto it; digest, outbox and recap-expiry jobs register on it), with a Postgres advisory
  lock per job so only one replica runs each.
- Email templates (`app/notify/templates/`): one base layout with the FluidBuddha brand, safe
  escaping, no tracking pixels.
- **Acceptance:** an enqueued email is delivered by SMTP, retried on failure, never sent twice;
  two replicas never both run the same job.
- **Tests:** outbox delivery against an in-process fake SMTP server; retry/backoff; advisory-lock
  single-runner.

### M2-1 · Teams, roles, SSO, audit log 🔴 ⏱️M
**Why:** today an account *is* one email + password (`tenants.email/password_hash`,
`app/auth/security.py`, `app/routes/auth.py`), so a customer can't add a colleague, and there's
no record of who changed what — a blocker for team use, SSO and SOC 2.

- **Data model (migration):** `users` (email, name, password_hash nullable for SSO-only,
  created_at, last_login_at), `memberships` (user, tenant, role), `invitations` (email, role,
  token hash, expiry, invited_by). Existing tenants migrate to one Owner user each, keeping
  their password — nobody has to re-register.
- **Roles:** Owner (billing, delete account, SSO), Admin (team, all sites, integrations),
  Editor (sites, knowledge, tours, experiments; no team/billing), Viewer (read-only). Enforced
  server-side by a `require_role(...)` dependency on every tenant route (`app/tenancy/deps.py`
  grows a `current_member`); the console hides what a role can't do.
- **Sessions:** JWT carries user + tenant + role; switch between accounts if a user belongs to
  several. Plan item WS2.5: move the console to an **httpOnly, SameSite cookie** with CSRF
  protection instead of a token in `localStorage`.
- **Invitations:** Admin invites by email (M2-0 outbox); link valid 7 days, single use.
- **SSO:** "Sign in with Google", plus per-account **OIDC** config (issuer URL, client id/secret,
  allowed email domains, default role, "require SSO"). Authorization-code flow with PKCE, state
  and nonce, ID-token signature checked against the issuer's JWKS. Just-in-time membership for
  allowed domains.
- **Audit log:** append-only `audit_events` (who, account, action, target, before/after summary,
  IP, user agent, request id, time) written for every change: sites, knowledge, tours, cache
  pins, experiments, integrations, privacy, billing, team, SSO, logins. Console "Audit log"
  page with filters and CSV export. Retained 1 year by default.
- Console: Team page (members, roles, invites), account switcher, SSO settings, Audit log page.
- **Acceptance:** an Owner invites an Editor who accepts, signs in and edits a tour but can't
  open Billing or Team; an Okta/Google user from an allowed domain joins via SSO; every change
  above appears in the audit log with the right person.
- **Tests:** role matrix over every tenant route (generated from the route table so new routes
  can't skip it); invitation lifecycle; OIDC flow against a local fake issuer (JWKS, bad
  signature, wrong nonce, disallowed domain); migration keeps existing logins working.
- **Needs from you:** a Google OAuth client id/secret for "Sign in with Google" in production.

### M2-2 · Live takeover: text first, then voice 🔴 ⏱️M
**Why:** Bet 1's human handoff. A hot lead talking to the agent should reach a salesperson
while they're still on the site. (The text part was the last WS7 item that needs no outside
account.)

- **Operator inbox** (console): live conversations now, with persona, page, lead score and a
  hot flag; Slack hot-lead alert (`app/leads/delivery.py`) links straight into it.
- **Text takeover:** operator clicks "Take over" → the agent pauses for that session, the
  visitor sees "Priya from Acme joined", operator and visitor chat; "Hand back" resumes the
  agent with the human part in its context. Works on `/ws/voice` sessions and `/chat`
  (`app/transport/websocket.py`, `app/routes/chat.py`); routing across replicas via Redis
  pub/sub when `REDIS_URL` is set. Operator presence and an "a person is available" badge.
- **Voice handoff (WebRTC):** operator clicks "Join by voice" → visitor is asked to accept →
  a peer-to-peer audio call (signalling over the existing WebSocket; SDK and console use
  `RTCPeerConnection`). Relay through **self-hosted coturn**: a `coturn` service in
  `docker-compose.yml`, `TURN_URLS` + `TURN_SECRET`, and short-lived credentials minted per call
  (coturn `use-auth-secret`). The agent stays muted during the call; a note is added to the
  transcript.
- **Acceptance:** an operator takes over a live text conversation and hands it back; a voice
  call connects between two browsers through coturn with UDP blocked; all of it is in the
  transcript and the audit log.
- **Tests:** takeover state machine (pause, resume, timeouts, operator disconnect); cross-replica
  routing with Redis; TURN credential generation/expiry; SDK smoke for the takeover UI.
- **Needs from you:** a server with a public IP for coturn in production (ports 3478 + a UDP
  range).

### M2-3 · Proactive engagement 🟠 ⏱️S–M
**Why:** most visitors never open a chat. The agent should speak up at the right moment.

- Per-site **trigger rules** (console): time on page, pricing-page dwell, scroll depth, exit
  intent (desktop: cursor leaves the top; mobile: fast scroll-up / back), return visit (n-th
  visit within N days, from the anonymous visitor id already used by experiments), page match
  (glob). Each rule has a message (or "let the agent compose one for this page"), a design
  (nudge bubble / open panel / voice greeting only after an earlier interaction), and caps
  (once per session, max N per day, quiet after dismiss).
- SDK trigger engine (`fluid-buddha-sdk/src/core/Triggers.ts`), cheap and passive: no work until
  a rule could fire; respects `prefers-reduced-motion` and never auto-plays audio.
- Events (shown, clicked, dismissed, led to conversation) recorded per rule; rule performance on
  Insights.
- **Acceptance:** a pricing-dwell rule fires once, opens a nudge with the configured text, and
  its conversion shows in the console; dismissing silences it for the session.
- **Tests:** rule evaluation unit tests (SDK), caps, exit-intent heuristics; backend rule CRUD
  and event recording.

### M2-4 · Experimentation engine 🟠 ⏱️M
**Why:** Bet 5. The holdout (WS11) proves the agent works; this finds *what works best*.

- Generalise experiments from 2 arms (agent/holdout) to **N variants** of one thing:
  greeting/opener, proactive trigger rule (M2-3), tour on/off/variant, default persona, design
  level. A run can still keep a holdout arm.
- Assignment, enrolment, bot filter and conversion tracking reuse `app/experiments/*` and
  `fluid-buddha-sdk/src/core/Experiment.ts`; the SDK applies the variant's overrides.
- Statistics: each variant vs control with the always-valid interval (WS11), with a
  multiple-comparison correction (α split across variants); planner extended to N arms.
- Console: create a test by picking what to vary and writing the variants; results table with
  a clear "winner / keep running / no difference" per variant; "make the winner the default".
- Later (not in M2): bandit allocation.
- **Acceptance:** a 3-greeting test runs, picks a winner with the always-valid rule, and
  promoting it changes the site's default greeting.
- **Tests:** multi-arm stats (simulation: false-win rate ≤ 5 % overall); variant overrides in the
  SDK; promotion.

### M2-5 · Insights v2 + weekly digest 🟠 ⏱️M
**Why:** Bet 4. What visitors say is the stickiest value for marketers.

- Classify each visitor turn (in the background, after the turn): **objection** (price,
  security, integration, implementation effort, trust, timing…), **competitor mention** (from a
  per-site competitor list + model detection), **feature request**, **buying signal**. Stored
  per turn (`conversation_turns`, `app/insights/store.py`); deterministic keyword rules in mock
  mode, the lean model otherwise; PII stays masked.
- Console Insights: objections (by type, trend, example quotes), competitors (mentions, context),
  feature requests (dedupe by similarity, count, "send to product" via webhook/Slack/email).
- **Weekly digest email** (M2-0) to chosen recipients per account: conversations, leads, top
  questions, new knowledge gaps, top objections, competitor mentions, experiment results,
  cost — Monday 9:00 in the account's time zone, one-click unsubscribe.
- **Acceptance:** a conversation mentioning a competitor and a price objection appears under both
  within a minute; the digest arrives with the week's numbers.
- **Tests:** classifier contract tests (mock rules + model output parsing); digest content and
  scheduling (time zone, once per week per account).

### M2-6 · Shareable recap pages 🟠 ⏱️S–M
**Why:** Bet 7. A recap forwarded inside the buying committee spreads the product in the account.

- After a conversation (or on the visitor's request — "send me this"), build a **recap**:
  summary, the components shown (charts, ROI model, diagrams re-rendered from their specs),
  cited sources, suggested next steps (book a meeting, the CTA), branded with the site's
  design tokens.
- Unguessable link (`/r/{token}`), served by the backend as a static-friendly page using the
  SDK renderers; optional email capture ("email me this", via M2-0); expiry per site (default
  90 days) and retention/erasure aware (WS8); visitor's PII masked unless they entered it.
- Views and forwards (new viewers) tracked; a recap view counts toward the lead score.
- **Acceptance:** a visitor gets a recap link, opens it on another device, forwards it; the
  console shows the views on the lead.
- **Tests:** recap build from a transcript; token secrecy and expiry; erasure removes recaps.

### M2-7 · Multilingual: English + Hindi 🟠 ⏱️M
**Why:** India-first pricing; many visitors ask in Hindi or Hinglish.

- Per-site languages (default English; enable Hindi); detect the visitor's language per turn
  (script + model hint; Hinglish counts as Hindi-friendly English reply unless the visitor
  prefers Hindi).
- Prompts: answer in the visitor's language, keep product names and citations as-is
  (`app/orchestrator/prompts.py`); retrieval stays on the English knowledge using a multilingual
  embedding (or a query translation step) — measured on a Hindi question set.
- Voice: ASR language codes `en-IN`/`hi-IN`, Hindi TTS voices (`app/ai/vertex.py`); widget UI
  strings in a small i18n table (`fluid-buddha-sdk/src/i18n/`), chosen by site setting or
  browser language; replay cache keyed by language.
- **Acceptance:** a Hindi spoken question gets a correct Hindi spoken answer with English
  citations; the widget's buttons read in Hindi when the site allows it.
- **Tests:** language detection set (Hindi, Hinglish, English); cache separation by language;
  SDK string coverage check.

### M2-8 · Actions marketplace + custom components 🟠 ⏱️M–L
**Why:** Bet 6. The agent should *do* things, not just explain. Today `call_site_api` is
simulated (`app/apis/registry.py`).

- **Actions framework:** per-site action catalog with a typed input schema, a confirmation step
  shown to the visitor before anything happens, rate limits, audit (M2-1) and an outcome stored
  on the conversation. The agent sees enabled actions as tools.
- **First actions:** Razorpay Payment Link (customer's own keys, encrypted; amount/plan from a
  configured price list, never from the model), quote request (structured, delivered by
  webhook/email, optional PDF), trial provisioning (signed webhook to the customer's backend
  returning a login link), meeting link (customer's booking URL with pre-filled details), generic
  signed webhook.
- **Custom component SDK:** tenants register their own components as a declarative spec
  (JSON schema for props + a template built from the existing primitives) — no arbitrary
  JavaScript on the visitor's page; a sandboxed-iframe component type for advanced cases with a
  strict postMessage contract. Registered components appear in the agent's component catalog
  (`app/orchestrator/components.py`).
- **Acceptance:** the agent offers to take a payment, the visitor confirms, a Razorpay link opens,
  and the paid status comes back to the lead; a tenant-defined "configurator" component renders
  from the agent's call.
- **Tests:** action schema validation; confirmation required; the model can't change amounts;
  Razorpay connector against a fake; component spec validation and sandbox message contract.

### M2-9 · Vertical templates 🟢 ⏱️S
**Why:** faster time-to-value; a new customer starts from something that fits.

- Template packs (`backend/app/templates/{saas,education,real_estate,healthcare}.yaml`):
  personas, opener, tour skeleton, starter questions, proactive rules (M2-3), preferred
  components, lead fields, guardrails, suggested actions (M2-8).
- **Healthcare guardrail:** never gives medical advice, diagnosis or dosage; urgent symptoms →
  "please contact a doctor / emergency services"; appointment booking only.
- Pick a template when creating a site (console) or apply later (with a preview of what changes;
  never overwrites hand-edited items, like tours today).
- **Acceptance:** a new "Education" site starts with student/parent/international personas and
  admissions questions; a healthcare site refuses a dosage question politely.
- **Tests:** template schema validation; apply/merge semantics; healthcare guardrail eval set.

### M2-10 · Install everywhere 🟢 ⏱️M
**Why:** distribution. Each install surface is also a marketplace listing.

- New top-level `integrations/` folder:
  - **WordPress plugin** (PHP): settings page for the widget key and options, injects the script,
    excludes admin pages; WordPress.org-ready readme.
  - **Shopify app**: theme app extension (app embed block) with key + options; minimal app
    backend only if the listing requires it.
  - **Webflow + Framer:** step-by-step embed guides; a Framer code component.
  - **Google Tag Manager** custom template (`.tpl`) with permissions declared.
  - **React and Vue wrappers** (`@fluidbuddha/react`, `@fluidbuddha/vue`) over the web component,
    typed props and events.
- Console Install tab gains a tab per platform.
- **Acceptance:** on a local WordPress, a Shopify dev store and a React app, the agent appears
  after pasting the key only.
- **Tests:** wrapper unit tests and build; GTM template tests (GTM's own test format); a
  WordPress PHP lint + a scripted local install in CI where feasible.
- **Needs from you:** WordPress.org, Shopify Partner, Webflow and npm accounts to publish.

### M2-11 · Compliance: SOC 2 controls + policies, DPA 🟢 ⏱️M
**Why:** enterprise deals ask for SOC 2 and a DPA.

- **Policies in `docs/compliance/`:** information security, access control, change management,
  incident response, business continuity / disaster recovery, vendor management, data
  classification and retention, acceptable use, risk assessment, plus a **DPA template** and a
  sub-processor list (Google Cloud, Razorpay, your SMTP provider, …).
- **Technical controls:** audit log (M2-1); MFA (TOTP) for password logins; session timeouts;
  quarterly access-review export; encryption of stored secrets (integration secrets, OIDC client
  secrets, BYO keys) with a key from config; backups + a restore drill script; dependency and
  secret scanning in CI; branch protection + required CI (you enable it on GitHub); security
  headers on the console.
- A control matrix mapping each SOC 2 criterion to the code/doc that satisfies it, ready for
  Vanta/Drata or an auditor.
- **Acceptance:** each SOC 2 Common Criterion has an owner, a policy and evidence source.
- **Needs from you:** an auditor (and optionally Vanta/Drata) for the actual certificate; legal
  review of the DPA.

---

## Part C — Milestone 3: "Platform and vision"

Exit gate: *a campaign link opens a page composed for that visitor's account and question; an
AI assistant can query a customer's site through its agent endpoint; returning visitors who
opted in are remembered; an enterprise runs FluidBuddha on their own server with their own
model keys.*

### M3-1 · Generative landing pages (Extreme GA) 🟢 ⏱️L
**Why:** Bet 7's "every visitor gets their own website". The Extreme tier already composes
pages from typed sections (`app/orchestrator/pagegen.py`,
`fluid-buddha-sdk/src/ui/page/PageRenderer.ts`).

- **Campaigns** (console): a goal, audience, key messages, allowed sections, CTA, and a hosted
  URL (`/p/{site}/{campaign}`) or an embed on the customer's page; URL parameters
  (`utm_*`, `?account=`, `?q=`) steer the composition.
- Composition is grounded (citations, golden answers, blocked topics) and cached per
  (campaign, persona, account, question) so most visits cost nothing; the agent is present on
  the page.
- Section library extended (testimonials, logos, FAQ, comparison, ROI calculator) and styled by
  the site's design tokens; Core Web Vitals budget (LCP < 2.5 s from cache).
- Campaign analytics: views, engagement, conversions; campaigns can run as experiments (M2-4).
- **Acceptance:** two links for two personas produce two different, grounded pages; the second
  view of each is served from cache in under a second.
- **Tests:** page spec validation, grounding enforcement, cache keys, renderer snapshot tests.

### M3-2 · Agent endpoint (MCP) + llms.txt 🟢 ⏱️M
**Why:** AI assistants increasingly research and buy for people; the customer's site should
answer them too.

- Per-site **MCP server** (streamable HTTP, `/mcp/{site}`): tools `search_knowledge` (grounded
  answer + citations), `get_page`, `list_offerings` / pricing (from knowledge), `capture_lead`
  and enabled **actions** (M2-8) behind scoped tokens; resources for key pages.
- Public read access with the site's key, rate limits and the spend cap; action tools need a
  token the customer issues; every call logged and counted as "agent traffic" in analytics.
- `llms.txt` and an OpenAPI description served per site; console page to enable it and copy the
  endpoint.
- **Acceptance:** an MCP client (e.g. Claude Desktop) connects, asks a product question and gets
  a grounded, cited answer; action tools refuse without a token.
- **Tests:** MCP protocol conformance (initialize, list tools, call); auth scopes; rate limits.

### M3-3 · Returning-visitor memory (opt-in) 🟢 ⏱️M
**Why:** "Welcome back — last time we looked at SSO."

- Visitor opts in (clear prompt; off by default; per-site setting); memory keyed by the
  anonymous visitor id, never shared across sites.
- After a conversation, store a short memory: topics, persona, components explored, open
  questions, lead status — built from the CORTEX episodic tree already populated
  (`app/cortex/episodic.py`); PII masked.
- On return, the agent greets with context and can resume; "forget me" in the widget; erasure,
  retention (WS8) and the leftover WS8 item "retention for CORTEX episodic memory" applied.
- **Acceptance:** an opted-in visitor returns a day later and the agent recalls the topic; "forget
  me" removes it everywhere.
- **Tests:** opt-in gating; memory build; erasure cascade; isolation between sites.

### M3-4 · Bring your own model: Anthropic, OpenAI, Azure OpenAI 🟢 ⏱️M
**Why:** enterprises want their own AI contracts; also removes single-vendor risk.

- New LLM engines behind `app/ai/base.py` (`LLMEngine.generate`, `generate_stream`, tool calls):
  `app/ai/anthropic.py`, `app/ai/openai.py` (also serves Azure OpenAI with endpoint +
  deployment names). Embeddings: OpenAI/Azure embeddings or keep Vertex; voice (ASR/TTS) stays
  on Google unless the customer also picks OpenAI's speech models.
- Per-account provider settings (console, Owner/Admin): provider, models for fast/thinker
  roles, keys **encrypted at rest** (M2-11), "test connection"; the platform default stays
  Vertex.
- Cost tracking per provider (`app/analytics/pricing.py` price tables) so cost per conversation
  stays right; BYO-key accounts aren't billed our model margin.
- **Acceptance:** a site switched to Claude or GPT answers with the same grounding, tools and
  citations; usage shows the right provider and cost.
- **Tests:** engine contract tests against recorded responses (tools, streaming, errors);
  key encryption; provider switch per site.
- **Needs from you:** test API keys for Anthropic, OpenAI and an Azure OpenAI deployment.

### M3-5 · Enterprise self-host (Docker Compose) + licence 🟢 ⏱️M
**Why:** VPC / on-prem buyers.

- `deploy/selfhost/`: production Compose file (backend, console, Postgres+pgvector, Redis,
  coturn, Caddy for TLS), `.env` template, health checks, log rotation.
- **Licence key:** a signed token (account, seats/sites, expiry, features) verified offline with
  a public key in the build; grace period and clear console banner on expiry; no phone-home
  required.
- Runbooks: install, upgrade (migrations run automatically), backup/restore (scripted), air-gapped
  install (images as tarballs), BYO model (M3-4) configuration.
- **Acceptance:** a clean Linux VM goes from zero to a working console + widget with the bundle
  and a licence in under 30 minutes; an expired licence shows the banner and degrades gracefully.
- **Tests:** licence verification (valid, expired, tampered); compose config check in CI.

### M3-6 · Reliability for a 99.9 % SLA 🟢 ⏱️S–M
- Health/readiness endpoints for every dependency, graceful shutdown that drains voice sessions,
  database backups with point-in-time recovery, alert rules on the existing Prometheus metrics
  (error rate, TTFA, cost), a public status page, an incident runbook, and load tests for the
  voice path. SOC 2 **Type II** is these controls operating for 3–12 months under audit.

---

## Part D — Build order

Dependencies first, then value:

1. **M2-0** email + jobs → 2. **M2-1** teams/roles/SSO/audit (everything after writes to the audit
   log and checks roles) → 3. **M2-2** live takeover (text, then voice) → 4. **M2-3** proactive
   triggers → 5. **M2-4** experimentation engine (tests greetings + triggers) → 6. **M2-5**
   insights v2 + digest (needs email) → 7. **M2-6** recap pages → 8. **M2-7** Hindi →
   9. **M2-8** actions + custom components → 10. **M2-9** vertical templates (uses triggers,
   actions) → 11. **M2-10** install surfaces → 12. **M2-11** compliance.
2. Then M3: **M3-4** BYO model (small, de-risks vendor) → **M3-2** MCP endpoint → **M3-3** visitor
   memory → **M3-1** generative landing pages → **M3-5** self-host → **M3-6** reliability.

Each epic lands as its own commits with tests, on a branch merged through a PR with CI green
(the same conventions as [handoff.md §8](handoff.md)).

## Part E — Things only you can provide (collected)

| For | What | When needed |
|---|---|---|
| M2-0 | An SMTP account (any provider) and a sending domain with SPF/DKIM | Before production email |
| M2-1 | Google OAuth client (and an Okta/Entra dev tenant to test OIDC, optional) | Before enabling SSO in production |
| M2-2 | A public server for coturn (ports 3478 + UDP range) | Before production voice handoff |
| M2-8 | A Razorpay test account for a *customer* site (can reuse your test keys) | While building |
| M2-10 | WordPress.org, Shopify Partner, Webflow, npm accounts | To publish |
| M2-11 | Auditor (+ optional Vanta/Drata); legal review of DPA and policies | For certification |
| M3-4 | Anthropic, OpenAI, Azure OpenAI test keys | While building |
| M2-7 | A fresh Google Cloud login on the dev machine (`gcloud auth application-default login`) so the real-model Hindi checks can run (`python -m evals.hindi_retrieval`, `python -m evals.hindi_voice`) | To call M2-7 measured |

---

## Progress

| Epic | Status | What shipped / what's left |
|---|---|---|
| M2-0 Email + jobs | ✅ | SMTP outbox (retries with backoff, `SKIP LOCKED` claims, idempotency keys, header-injection checks, 30-day cleanup; dev logs instead of sending, production refuses without SMTP). One scheduler runs every periodic job under a Postgres advisory lock (`fb_job_runs_total`). Migration `0014`. |
| M2-1 Teams, roles, SSO, audit | ✅ | Users separate from accounts (existing logins became Owners, old tokens still work); invitations (single use, 7 days, hashed); Owner/Admin/Editor/Viewer enforced centrally for every `/tenant` route (a test walks them all); account switching. Audit log of every successful console change + sign-ins/failed sign-ins (middleware, no bodies), filter + CSV, 1-year retention. Google + per-account OIDC with PKCE, ID tokens checked against the provider's keys, domains proven by DNS TXT, client secrets encrypted (`SECRETS_KEY`), "require SSO" with Owner break-glass. Console: Team (members, invites, SSO, domains), Audit log, invitation and SSO pages, account switcher. Migrations `0015`–`0016`. Checked live: sign-in, invite, accept as a new person, editor view, audit trail. **Left:** httpOnly-cookie console session (moved to M2-11 with MFA); hiding edit controls from Viewers on the website pages (the server already refuses); a real Google/Okta run needs your OAuth clients. |
| M2-2 Live takeover | ✅ | Live inbox of visitors on the account's sites (voice and text) with hot-lead flags; every question and answer streamed to the console; take over (agent pauses, visitor told who joined), reply, hand back (agent's history gets what was said), one holder at a time, Admin release, visitor leaving ends it. Text visitors get replies by long poll. Voice handoff over WebRTC with visitor consent, signalled through the backend, short-lived coturn credentials (`use-auth-secret`), coturn in docker-compose (`--profile voice`) with private ranges blocked. In-process bus, Redis pub/sub across replicas. Audit-logged, role-checked, retention/erasure/deletion aware. Slack hot-lead alerts link to the inbox. Migration `0017`. Checked live with a scripted visitor. **Left:** a real two-browser call through coturn hasn't been run (needs a public coturn host and two machines/networks); the Slack link opens the inbox, not the exact conversation (leads don't carry the session yet); the widget is at 41.5 / 42 kB, so the stylesheet split is due before the next widget feature. |
| Widget size (WS5 carry-over) | ✅ | Stylesheet minified at build (comments and whitespace stripped from the CSS strings) and split so each widget parses only its level's rules: core 41.6 → 39.1 kB gzipped before M2-3, 40.9 kB with it. Checked visually on all three levels. |
| M2-3 Proactive triggers | ✅ | Up to 20 rules per site: time on page, scroll depth, exit intent (desktop), return visit; page globs; nudge bubble or open; per-visitor daily cap; priority. Widget arms rules per page view (SPA-aware), one per page view, never while the agent is open or after the visitor talks, dismiss mutes the visit, and a trigger's message replaces the welcome. Shown/clicked/dismissed/engaged reported (bots ignored, capped); console Triggers tab with presets and 30-day numbers. Migration `0018`. Checked live on the demo page. **Left:** exit intent on mobile (no reliable signal yet; desktop only); "let the agent compose the message for this page" (a fixed message for now); testing rules against each other is M2-4. |
| M2-4 Experimentation engine | ✅ | A/B tests of 2–4 versions of one setting: greeting, proactive triggers (which are on), guided tour on/off, starting persona, design level; optional holdout alongside. Same enrolment as the holdout (deterministic, bots kept out, conversions on the site's goal); the widget applies design/tour/greeting/triggers, the server applies the greeting (spoken as written, no model call), persona and tour from the variant it looks up itself. Each version vs the control with the always-valid interval at a split budget (Bonferroni): simulated false-win rate with 3 versions read every 300 visitors ≤ 5 %, ~80 %+ power at a doubled rate. Verdict winner / keep running / no difference; planner for N arms; "Make default" writes the agent profile (new greeting, starting persona, tour switch — also editable in Settings), the website's design level, or switches the winning triggers on and the other tested ones off, then ends the test. One experiment per site at a time (starting a test ends a holdout run; the holdout can't restart while a test runs). Console A/B tests tab; Experiment tab renamed Holdout. Migration `0019`. Widget 41.2 / 42 kB. Checked live: 3-greeting test with 1,200 simulated visitors called "Fit", promoted it, and a fresh widget opened with it once (shown and spoken). **Left:** bandit allocation (later, as planned); a promoted design level only reaches embeds that don't set `data-design` themselves; the widget is 0.8 kB under budget, so the next widget feature needs room made first. |
| M2-5 Insights v2 + weekly digest | ✅ | Every visitor turn is labelled in the background (job every 20 s, newest first, up to 8 model calls at once, 15 s per run, `SKIP LOCKED`): objections (price, security, integrations, effort, trust, timing), competitors (the site's list by whole-word match + the model's), feature request, buying signal — keyword rules in mock mode and whenever the model's JSON is unusable. Stored on `conversation_turns`; text is the already-masked question. Insights: objections and competitors with trend vs the previous period and quotes that open the conversation, feature requests grouped by word overlap with "Send to product" (Slack, the signed webhook as event `feature_request`, or email), buying signals; competitor list editable there. Weekly digest per account (Team page): Monday 9:00 in the account's time zone, once per ISO week (`digest_runs` + outbox idempotency), Owners by default, quiet weeks skipped; conversations, leads, top questions, new gaps, objections, competitors, A/B tests, model cost; preview and test send; RFC 8058 one-click unsubscribe with a random token (no address in the link), the GET page needs a click so link scanners can't unsubscribe anyone, only the person can resubscribe. `tzdata` added. Migration `0020`. Checked live: a new question naming a competitor and a price worry showed under both in 18 s; request emailed; digest previewed, sent and unsubscribed. **Left:** classification cost isn't counted in usage/cost yet; feature-request grouping is word overlap, not embeddings; the digest's "new gaps" are per-site first sightings, so a site without content lists everything. |
| M2-6 Shareable recap pages | ✅ | A visitor types "send me this" / "email me a recap at …" (any design level) and gets a link `/r/{token}` (32 random bytes) to a snapshot of the conversation: a summary (model, or the plain "you asked…" in mock mode), each question and answer as stored (already PII-masked), the components shown (specs now saved per turn) redrawn by a separate SDK bundle (`fluid-buddha-recap.global.js`, 14.8 kB gz, widget untouched), sources, and next steps (the profile's new CTA button + "ask a follow-up" back to the page on the site's domain). Branded with the site's design tokens; no inline script (CSP allows the SDK origin only), `no-referrer`, `noindex`, everything escaped. Asking again refreshes it and keeps the link; with an email the link is sent through the outbox and the address becomes a `recap` lead. Expiry per site (Privacy: 7–365 days, default 90); goes with its conversation (retention, erasure, site deletion) and expired ones are swept; unknown, malformed and expired links look the same. Views counted per viewer cookie, link-preview bots ignored; each new viewer after the first is a forward (+10 lead score, first view +5). Console: Leads shows each lead's recap views/forwards and a Shared recaps list (open, conversation, take down); profile gets the CTA; Privacy gets the expiry. `WIDGET_SDK_BASE` setting. Migration `0021`. Widget 41.7 / 42 kB. Checked live: recap made on the demo page, opened with the ROI calculator drawn and adjustable, emailed, opened by a "colleague" — the lead shows 2 views, 1 forward. **Left:** asking by voice (typed only for now); no automatic offer at the end of a conversation; the widget is 0.3 kB under budget, so the next widget feature needs room made first. |
| M2-7 English + Hindi | 🟡 | Per site (Settings → Agent profile): Hindi on/off (English always on), widget labels (match the browser / always English / always Hindi) and an optional Hindi greeting. Each turn's language is detected without a model call (`app/i18n/detect.py`): Devanagari → Hindi; Hindi in Latin letters (Hinglish, spotted by common Hindi words) → a simple-English answer unless the visitor prefers Hindi (asked for it, Hindi widget, or wrote Devanagari earlier); "reply in Hindi" / "English please" in either language sticks for the conversation. Prompts answer in Hindi keeping product names, prices and source titles as written; the fast router's existing call also returns the Hindi ack and an English search query, so retrieval stays on the English knowledge with no extra round trip (the heavy thinker is told to search in English). Voice: ASR listens for the conversation's language with the other as an alternative (`en-IN`/`hi-IN`, Hindi sites only), TTS pins `hi-IN` for Hindi text, `।` ends a sentence for TTS chunks, the widget's own recogniser follows the server's `language` event. Answer cache and audio cache keyed by language; transcript turns record en/hi/hinglish; Insights shows "Asked in"; Hindi words in the objection/buying rules; cache editor tags Hindi answers. Widget: 72 strings in an i18n table (`src/i18n/`), Hindi fetched only for a Hindi widget (`fluid-buddha-hi.global.js`, 2.3 kB gz), `data-lang`; Hindi "send me this" makes a recap. Room made first: component renderers now load when a conversation starts (`fluid-buddha-components.global.js`, 8.5 kB gz; ESM chunk), core 41.7 → 35.8 kB, 37.2 kB with M2-7. Migration `0022`. Tests: 20-sentence detection set, reply rules, cache separation, a Hindi site by text and voice, SDK string coverage. Checked live (mock AI): Hindi widget, Hindi question → Hindi answer, English → English with the ROI calculator loaded on demand, Hinglish → English, settings saved from the console, Hindi greeting spoken once, Insights split. **Left:** the real-model checks are written but not run — Google credentials on this machine need a fresh login: a labelled Hindi/Hinglish retrieval set (`evals/hindi/`, 30 passages × 20 questions; router query vs raw Hindi vs the multilingual embedding model) and a voice round trip (Hindi TTS → ASR → Hindi answer with English sources → Hindi TTS). Hindi uses the feminine for the agent; the agent name "Pragya" is still fixed in the widget. Browser recognition (Chrome) listens in one language at a time, so a Hindi speaker on an English widget is heard as English until the first Hindi turn. |
| M2-8 Actions + custom components | ✅ | Per-site actions (console Actions tab, Admin-only to change: they hold payment keys): Razorpay payment link on the tenant's own account (key id + key secret and webhook secret, Fernet-encrypted, never read back; price list in paise), quote request (a `quote` lead delivered like any lead + owners emailed), trial (signed POST to the tenant's endpoint, which returns a login link), meeting link (Calendly/Cal.com page with name, email and topic filled in), generic signed webhook with tenant-defined fields. Each has typed inputs (`app/actions/fields.py`) that become the agent's tool (every tier) and are re-checked on the server; amounts are never inputs — the agent picks a plan key, the price comes from the list, and a price changed after the proposal fails the confirmation instead of charging. A call only *proposes*: the run is stored with a summary and the widget shows a confirmation card (all design levels, English + Hindi); nothing runs until the visitor confirms for the same conversation within 15 min (`/actions/confirm`, `/actions/cancel`; double clicks run once). Limits: 10 proposals per conversation per hour, a per-action hourly cap. Outbound calls use the lead-delivery SSRF checks, are signed and carry the run id as an idempotency key, and aren't retried. Outcome on the run (status, link, error), told to the agent (voice via the live bus, text via the session), audit-logged (`action.run`), turns with a proposal never cached. Paid status: Razorpay's signed `payment_link.paid` webhook per action, plus a 5-minute poll of unpaid links; the run turns `paid` and the lead gets `paid_at`/`paid_amount` and score ≥ 90. Runs go with retention, erasure and site deletion. Custom components (`app/orchestrator/custom_components.py`): a template — props schema (JSON-schema subset) + a built-in base component whose state uses `{{prop}}` — expanded on the server, so the widget only ever draws built-ins; or the tenant's page in a scripts-only sandboxed iframe with a fixed postMessage contract. Both join `render_component` with their props; console editor with preview. Widget 38.0 / 42 kB. Migration `0023`. Checked live (mock AI, a local fake Razorpay): asked to pay for the Growth plan → card with ₹14,999 → Confirm → payment page link; the fake received one link for 1499900 paise; a signed paid webhook marked the run paid and the lead "paid ₹14,999" (score 90); "show me plan builder for 25" drew the tenant's configurator. **Left:** not tried against a real Razorpay test account (needs one, Part E); quote PDFs; the built-in configurator's currency format shows $ (needs a ₹ format for India); an embed can't show on recap pages (their CSP blocks frames); voice confirmation (the card needs a click). |
| M2-9 Vertical templates | ✅ | Four packs (`app/templates/{saas,education,real_estate,healthcare}.yaml`), checked against a schema when loaded (bad component names, duplicate personas, unknown action kinds fail the import and the tests): voice, greeting (+ Hindi), 3 personas, starter questions, rules the agent always follows, preferred components, details to ask for on follow-up, what the tour covers, optional medical safety, triggers (M2-3) and suggested actions (M2-8). New profile fields, all editable in Settings: starter questions become the widget's chips (English widgets), rules and lead fields go into every prompt, preferred components into the thinker's, the outline into the tour planner. Pick a template when adding a website, or later from Settings with a preview of what it will set, add and keep. Merge: a setting is set only if empty or still exactly what an earlier template set (recorded on the profile), so hand edits are never overwritten; personas added by slug, triggers by name, never duplicated. Healthcare: a deterministic guard (`app/trust/safety.py`, English, Hindi, Hinglish) answers requests for doses, medicines, diagnoses or treatment with a fixed, polite refusal plus an offer to book, and anything that sounds urgent with 112 / ambulance 108 — before any cache or model call, never cached, voice and text; the prompt carries the same rules. Guardrail eval set: 22 sentences (13 to refuse or escalate, 9 ordinary questions that must pass, e.g. "do you offer treatment for knee pain?", "do I have to bring my reports?"). `PyYAML` added. Checked live: a new site "Vidya College" from Education has Student/Parent/International personas and admissions questions; the Real estate preview listed what it would set, add and keep; a Healthcare site refused a paracetamol dose politely over the voice socket and showed its starter chips. **Left:** starter chips for Hindi widgets (they show the built-in Hindi chips); the guard is pattern-based, so unusual phrasings fall to the prompt rules; packs are in English only beyond the Hindi greeting. |
| M2-10 Install everywhere | ✅ | One script behind every surface: `GET /widget/loader.js` adds the widget (from `WIDGET_SDK_BASE`) with the embed's `data-*` settings, or the same settings from its query string where attributes can't be set (GTM), and points it back at the server it came from — so an install carries only the key, and design, colour, greeting and tier come from the console (the widget now also takes the site's accent from the server when the embed doesn't set one; key-only embeds also pick up a promoted design). Runs once per page, `data-auto="false"` loads without showing, `fluidbuddha:ready` when loaded, cached 5 min. Plugins take an **install code** `https://fbk_…@server` (key + server, DSN-style), shown per website. New `integrations/`: **WordPress** plugin (Settings → FluidBuddha: install code, position, language, pages to hide it on by path pattern, hide from logged-in staff; async footer script on public pages only — never wp-admin, feeds, AJAX, customizer; connection check against `/widget/config`; WordPress.org `readme.txt` with the external-service section; GPL-2.0-or-later as WordPress.org requires; local `docker compose` WordPress); **Shopify** theme app extension (app embed: install code, position, language, cart/account page switches; no scopes, no backend); **GTM** template generated by the server for its own address (`/widget/gtm-template.tpl`, one permission: inject that loader; GTM tests inside) plus a Custom HTML route; **Webflow** guide; **Framer** code component (placeholder on the canvas) + custom-code guide; **`@fluidbuddha/react`** and **`@fluidbuddha/vue`** (MIT; load the widget from the server rather than bundling it; typed props, hooks as callbacks/events without re-creating the widget, StrictMode-safe, `conversion()`). Console Install tab: a tab per platform with its steps and the snippet / install code / template download. CI job `integrations` (wrapper typecheck/build/tests, Shopify Liquid rendered with LiquidJS, PHP lint + unit tests in a `php` container). Tests: loader + GTM template (backend), the backend's real loader run in jsdom, React/Vue against a fake server, 25 Liquid checks, 23 PHP checks. Checked live: a plain page with only the key got the widget in the site's colour and an answer; a React app mounted it once and the agent's navigation stayed in the router; a local WordPress (Docker) showed the agent bottom-left per the plugin and answered, hid it on an excluded path, kept it out of login and the feed; the settings page's three connection states; console tabs. **Left:** a Shopify development store run and the store listings (need your Partner, WordPress.org, npm and Webflow accounts — Part E); the GTM template hasn't been imported into a real GTM container; there's no production server address yet, so the install code and GTM template use whatever `PUBLIC_API_URL`/`NEXT_PUBLIC_WIDGET_BACKEND` say; licences for the published packages (MIT for npm, GPL for WordPress) are a default to confirm; a customer site's origin must be allowed by `CORS_ORIGINS` (`*` in production) or the widget can't talk to the server. |
| M2-11 Compliance | ✅ | **Sessions:** every sign-in is a server-side session (`user_sessions`): 60 min idle / 12 h absolute (`SESSION_*`), revoked on sign-out, "sign out everywhere", a password change or removal from the team; tokens from before ask to sign in again. **Console cookie:** httpOnly, Secure, SameSite session cookie, `X-CSRF-Token` on changes (also the live inbox socket), SSO lands with the cookie (no token in the URL), nothing in `localStorage`; bearer tokens still work for API clients. **Two-factor:** TOTP (RFC 6238, no new dependency) with QR setup, 10 hashed one-time recovery codes, replay-proof, password + code to turn off; an Owner can require it for the account (and must have it first); password sessions without it are held at the setup page; SSO counts as two-factor. **Lockout** after 10 wrong passwords/codes for 15 min; password change. **Stored secrets:** lead webhook signing secrets and Slack URLs now encrypted like SSO and action secrets (migration `0024` converted existing ones). **Access review:** CSV (Admin+) and a quarterly email to Owners/Admins. **Headers:** nosniff, DENY framing, referrer policy, `no-store` on the console API, HSTS outside dev; a CSP and security headers on every console page. **CI:** gitleaks over the full history, Dependabot weekly. **Backups:** `scripts/backup.sh` (pg_dump + SHA-256, optional `age`, retention, `backup-log.jsonl`) and `scripts/restore_drill.sh` (scratch restore, checks, `drills/*.json`; a corrupted copy is refused). **Docs:** `docs/compliance/` — information security, access control, change management, incident response (72 h customers, CERT-In 6 h), continuity/DR (RPO 24 h, RTO 4 h), vendors, sub-processors, data classification and retention, acceptable use, risk register, a DPA template with technical and organisational measures, and a SOC 2 control matrix (CC1–CC9, A1, C1 → control, owner, policy, evidence). Console: Security page (two-factor, password, sessions), Team page (two-factor column, require two-factor, access-review download). Migration `0024`. Checked live: sign-up by cookie (nothing readable by page scripts), two-factor set up from the QR flow, "require two-factor" switched on, sign-out, sign-in with password + code, live inbox connected over the cookie, no CSP violations, backup + restore drill on the dev database. **Left:** naming the owners, leadership approval and a lawyer's review of the DPA; enabling branch protection on GitHub; an auditor (Part E); production secret store, off-site encrypted backups and managed PITR at deployment. |

### M2 follow-ups (the "left" items above, closed 5 Nov 2026)

| From | Item | Status |
|---|---|---|
| M2-1 | httpOnly-cookie console session | ✅ with M2-11 |
| M2-1 | Hiding edit controls from Viewers on the website pages | ✅ `EditOnly` / `Editable` (`src/components/Permission.tsx`) on ingestion, tour, cache, insights, holdout, install, settings; a "view-only" note for Viewers; integrations, privacy changes and deleting a site shown to Admins only |
| M2-1 | A real Google / Okta sign-in | Needs your OAuth clients (Part E) |
| M2-2 | Slack hot-lead link opens the exact conversation | ✅ `/live?session=…` (leads already carried the session) |
| M2-2 | Two-browser call through coturn | Needs a public coturn host (Part E) |
| M2-3 | Exit intent on mobile | ✅ after reading a screen down, a fast flick back to the top (touch devices) |
| M2-3 | "Let the agent compose the message for this page" | ✅ per rule (`compose`): one opener per page and language, written once and cached (`trigger_messages`, migration `0025`), only for the rule's pages, capped at 200 pages, the fixed message as fallback and for bots; deterministic in mock mode; model cost recorded |
| M2-4 | Bandit allocation | Later, as planned (not in M2) |
| M2-5 | Classification cost in usage/cost | ✅ recorded as session-less "background" usage per site: in cost totals, never a turn or a billed conversation |
| M2-5 | Feature requests grouped by meaning | ✅ embeddings (cosine ≥ 0.82, cached per text) with word overlap kept; word overlap only in mock mode |
| M2-5 | Digest "new gaps" for sites without content | ✅ such sites are listed as "no content yet" instead of every question being a gap |
| M2-6 | Asking for a recap by voice | ✅ the server recognises it (English/Hindi/Hinglish, spoken email addresses) and the widget makes the recap; no agent turn |
| M2-6 | Offering a recap automatically | ✅ a "Send me a recap" chip after three answers (panel design, registered sites) |
| M2-7 | Agent name fixed as "Pragya" in the widget | ✅ the site's agent name in every label and the default greetings |
| M2-7 | Real-model Hindi checks | Needs a fresh Google Cloud login (Part E) |
| M2-8 | Quote PDFs | ✅ one-page PDF per confirmed quote request (console: Actions → Recent runs → PDF); Latin text and ₹ (as "Rs."), other scripts print as "?" |
| M2-8 | ₹ format in the configurator | ✅ a per-site currency (default INR) put into calculators and configurators by the server; rupees with Indian grouping |
| M2-8 | Embeds on recap pages | ✅ the recap CSP allows frames from exactly the https origins of the embeds it shows |
| M2-8 | Voice confirmation | ✅ a short spoken yes/no while a card is open presses the card's button (same confirm path) |
| M2-8 | Real Razorpay test account for a customer site | Needs the account (Part E) |
| M2-9 | Starter chips for Hindi widgets | ✅ `starter_questions_hi` in the profile and the four packs |
| M2-10 | Shopify development store, GTM import, store listings | Need your accounts (Part E) |

### M3 progress

| Epic | Status | What shipped / what's left |
|---|---|---|
| M3-4 Bring your own model | ✅ | Per-account provider (Console → AI model, Owner/Admin): **Anthropic**, **OpenAI** or **Azure OpenAI**, its API key (Fernet-encrypted, shown only as `…1234`), a fast and a thinking model (defaults Claude Haiku 5.5 / Claude Opus 5.5 for Anthropic; Azure takes deployment names, endpoint and API version), optional prices, "Test connection" (one line per model), and a per-website switch back to the platform's model. Engines behind `LLMClient`: `app/ai/anthropic_llm.py` (official `anthropic` SDK: no sampling parameters, depth by `output_config.effort`, thinking off for quick calls where the model allows it — `disabled` on Haiku 5.5, `between_tools` on Sonnet 5.5 — a `max_tokens` floor where the model always thinks, tool turns replayed with their thinking blocks, `refusal` handled, server-side fallback `fallbacks: "default"` on Opus 5.5 / Sonnet 5.5 / Fable 5.1 / Opus 5) and `app/ai/openai_llm.py` (official `openai` SDK, Chat Completions, Azure via the resource endpoint; retries once without `max_completion_tokens`/`temperature` when a model refuses them, and remembers). `rt.engines.llm` is a `RoutingLLM`: the current site (a context variable set where voice sessions, `/chat`, recaps, trigger messages, tour plans, persona suggestions and labelling start) picks the provider; `HEAVY_MODEL` → thinking model, the rest → fast; a failing provider falls back to the platform model and the error shows in the console. Voice and embeddings stay on Google. Usage records the provider; its model cost uses the account's prices or the list price, shows as `byo_llm_cost` on Analytics, and is left out of the daily spend cap. Migration `0026`. Tests (fake transports with recorded-style responses, no network): Claude request shape, tool loop with thinking-block replay, quick calls on Haiku/Sonnet, refusal, streaming, auth errors; OpenAI request shape, tool ids, parameter retries; Azure URL/key; settings (roles, key encrypted, never returned, test connection); a site answering with its account's model and usage priced per provider; a switched-off site on the platform; a broken key falling back with the error recorded. Checked live: the AI model page, saving (key hint only), the per-site list. **Left:** runs against real Anthropic / OpenAI / Azure accounts (Part E keys); OpenAI and Azure have no built-in prices (accounts enter theirs); embeddings stay on Vertex. |
| M3-2 Agent endpoint (MCP) + llms.txt | ✅ | Per site, off until an Admin switches it on (website → Agent access). **MCP server** at `POST /mcp/{widget key}`: streamable HTTP, JSON-RPC 2.0 answered as JSON, stateless (no session to share across replicas), protocol versions 2025-11-25 back to 2024-11-05 (a client asking for another gets 2025-11-25); `initialize`, `ping`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `resources/templates/list`, `prompts/list`; notifications 202; `GET` 405; batches, bad JSON, unknown methods and unsupported `MCP-Protocol-Version` refused with the right JSON-RPC codes. Tools: `search_knowledge` (one stateless, grounded turn of the site's own agent — same citations, pinned/blocked answers and medical safety; PII masked), `get_page` (grounded summary of a page), `list_offerings` (knowledge + payment price lists); tool failures are `isError` results. Resources: the site's crawled pages. **Acting tools behind customer tokens**: `capture_lead` (scope `leads`, lead source `agent`) and the site's enabled actions as `action_<name>` (scope `actions`, run at once since the token is the authorisation; amounts still only from the price list); tokens `fbat_…` shown once, stored hashed, per site, revocable, last-used tracked. Also `GET /sites/{key}/llms.txt` (company, pages, how to ask), `GET /sites/{key}/openapi.json` (OpenAPI 3.1) and `POST /agent/{key}/ask` / `GET /agent/{key}/offerings`. Limits: 30 calls/min per site and client address, the site's daily spend cap on model calls, browser `Origin`s only from the site's domain; disabled and unknown sites both 404. Every call logged (`agent_requests`) and counted as agent traffic (console: by tool, by assistant); its usage recorded as channel `agent` without a session, so never a billed conversation. Console: Agent access tab (switch, endpoints to copy, tokens with scopes, traffic). Migration `0027`. Tests: handshake and version negotiation, tool list/call, errors and transport rules, origin check, token scopes per site and revocation, leads and a quote action through MCP, llms.txt, OpenAPI, REST ask, resources, rate limit. Checked live with the official MCP Python SDK (2.3) as the client: initialize (negotiated 2025-11-25), list tools, `search_knowledge`, `capture_lead` refused without a token and accepted with one; the console tab showed the endpoints, tokens and traffic. **Left:** a run from Claude Desktop itself (needs the backend reachable over HTTPS); the assistant's name is known only from `initialize` (stateless server), so later calls show the HTTP client; MCP's newer `2026-07-28` protocol isn't offered yet; page text comes back as a grounded summary, not the raw page (crawled text lives in the knowledge tree). |
| M3-3 Returning-visitor memory (opt-in) | ✅ | Per-site Privacy switch (off by default) and how long to keep a memory (30–365 days after the last visit, default 180). The widget asks once per browser, after its first answer, whether to remember the conversation; **Remember me** → `POST /memory` with the anonymous visitor id (the A/B test id). An opted-in visitor's conversations on that site — text and voice, including the one they opted in during — are linked to the id (the record links only while a memory exists; the socket gets the id on its URL, voice welcome or not). A job (`MEMORY_BUILD_SECONDS`, default 120) rebuilds memories 10 minutes after a conversation goes quiet: latest questions, components explored, unanswered questions, whether they left details, language — from the PII-masked transcript, newest three conversations. Built from transcripts rather than the CORTEX episodic tree: episodes are per site, not per visitor. Next visit: `memory.welcome_back` (English/Hindi) from `/experiment/enroll`, shown as the greeting ("Welcome back! Last time you asked: “…?”"), spoken by the voice welcome instead of the guided tour, and the notes go at the start of the agent's history. Never across sites. **Forget me**: widget chip, typed or spoken ("forget me", "मुझे भूल जाओ"); also erasure by email (through the visitor's conversations), retention, switching the setting off, site deletion. WS8 leftover done: retention now sweeps CORTEX episodic memory past the transcript window. Migration `0028`. Tests: opt-in gating (site and visitor), linking incl. mid-conversation opt-in over `/chat` and the socket, memory build, welcome back by text and voice, isolation between sites, forget typed and by button, erasure, retention, switching off, CORTEX episode retention; widget smoke (ask once, Remember me, Forget me, welcome back, spoken forget). Checked live: Privacy switch saved, the widget asked, opted in, memory built, reload greeted with the last question and Forget me removed memory and links. **Left:** the memory is extractive (the visitor's own questions), not an LLM summary; the visitor id lives in the browser's storage, so a new browser or cleared storage is a new visitor. |
| M3-1 Generative landing pages (Extreme GA) | ✅ | **Campaigns** (website → Campaigns, Editor): goal, audience, default persona, key messages, allowed sections, CTA label and https link, customer-supplied testimonials and logos, optional version B (headline / messages / CTA, 50/50 by a first-party viewer cookie), embed origins; draft / live / paused; edits bump a version and clear the page cache. **Hosted** at `/p/{site_key}/{slug}`, steered by `?persona=` (or `utm_content`), `?q=` (or `utm_term`, answered first), `?account=` (render-time only: "Prepared for …", form pre-filled), `?lang=hi`, `utm_source`; previews of drafts by a signed link (not counted); `?embed=1` for iframes with `frame-ancestors` = the site's domain + listed origins. **Composition grounded**: retrieval for messages, persona focus and question above the grounding threshold; pinned answers word for word; blocked questions never answered; the account's model (M3-4) or the platform's composes typed sections with citations (one tool call); a rule-based composer (only quotes the material) in mock mode, past 20 compositions/min per site or the daily spend cap, or when the model's page fails the checks. `enforce()` checks every page: allowed sections only, factual sections cite real sources, every number must appear in its sources or the brief, testimonials/logos/images only as supplied, a fixed safe enquiry form; drops are recorded on the spec. **Cache** per (campaign version, arm, persona, question, language, knowledge version); bots get an already-composed page; `Server-Timing` shows cache/rules/model. **Sections** added: testimonials, logos, FAQ, comparison, ROI calculator — in the hosted page (server-rendered, themed by the site's design tokens) and in the widget's Extreme pages (`PageRenderer`). Page script `fluid-buddha-page.global.js` draws the ROI calculator/charts and reports engagement once; the site's widget runs on the page (our own origin is accepted for the site key). **Analytics** per unique visitor, credited to their first view's arm, persona and UTM source: views, engaged, converted (form → lead with source `campaign`; CTA via `/go`), daily series, cache hit rate and build time, A/B verdict (M2-4 statistics). Migration `0029`. Tests: validation and CRUD, two personas → two different cited pages and the second view from cache in < 1 s, the question answered, account without recomposing, edits recompose, enforcement (sources, numbers, fake testimonials/logos, blocked and pinned answers, disallowed sections, form fields), the model path checked like the rules with fallback, cache-key parts, conversions/engagement/bots/analytics/variant, drafts/previews/embeds/site deletion; widget smoke (new sections, page script). Checked live: campaign created in the console with a testimonial and version B; pages for Clinic owners and Hospital IT differ (persona subtitle and features), a question adds its answer, cached refetch ~30 ms, ROI calculator drawn, widget on the page, no CSP errors; the form made a lead and the console showed views, engagement, conversion, cache and the A/B status. **Left:** LCP measured only as server time (cached ~30 ms, composed ~50–150 ms with the rules); a real-model run needs Part E keys; pages are noindex (ad landing pages); campaign A/B is per campaign, not through the site-wide M2-4 engine. |
