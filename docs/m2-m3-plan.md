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
