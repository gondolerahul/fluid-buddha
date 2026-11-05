# A2UI Backend Orchestrator

The "Brain" of the Voice-First Agentic UI Framework (A2UI) — a FastAPI service
that turns the **Pragya** widget on the HireBuddha site into a grounded, voice-first
SDR agent. It runs the dual-model cognitive loop, grounds every answer in the
**CORTEX** memory engine (`hb-cortex-memory`, Postgres + pgvector), and speaks +
draws dynamic UI over a single multiplexed WebSocket.

> **Mock mode is the default.** With `MOCK_AI=true` the entire stack — DB,
> ingestion, cognitive loop, voice transport — runs with **zero** Google Cloud
> setup using deterministic stub engines. Flip to `false` for real Vertex AI.

## Quickstart

### One command (Docker)

```bash
cd backend
docker compose up -d --build
```

This builds the orchestrator image and starts everything: Postgres + pgvector,
then the backend — which **auto-creates the schema and seeds CORTEX memory** from
the mounted website docs on first boot (idempotent via `--if-empty`). API on
`http://localhost:8080`, DB on host `:5434`.

```bash
curl localhost:8080/readyz
docker compose logs -f backend
docker compose down            # add -v to also wipe the DB volume
```

Default is mock mode. For Vertex: set `MOCK_AI=false` + `GOOGLE_CLOUD_PROJECT` in
`backend/.env`, uncomment the gcloud ADC volume/credentials lines in
`docker-compose.yml`, then `docker compose up -d --build`.

### Local (venv) — for iterating on the code

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                 # MOCK_AI=true by default

docker compose up -d postgres        # just the DB on :5434
.venv/bin/python -m ingestion.ingest --site hirebuddha   # seed CORTEX memory

.venv/bin/uvicorn app.main:app --reload --port 8080      # serve
# smoke tests:
.venv/bin/python -m scripts.smoke_chat
.venv/bin/python -m scripts.smoke_ws
.venv/bin/python -m pytest -q
```

### Schema migrations

The schema lives in Alembic migrations (`migrations/versions/`). The app applies
them on startup (`init_db`, advisory-locked so several replicas can boot at
once), and so do ingestion and the test suite. To change the schema, add a
revision — never DDL in application code (a test enforces this):

```bash
.venv/bin/alembic revision -m "add leads table"   # then edit the new file
.venv/bin/alembic upgrade head
```

### Onboarding: crawl a website

Console → Ingestion → *Crawl your website* (or
`POST /tenant/websites/{id}/crawl {url?, max_pages, max_depth}`; the URL defaults
to the website's domain). One job (`app/onboarding/jobs.py`, progress in
`crawl_jobs`) does it all:

1. **Crawl** (`app/onboarding/crawler.py`): obeys `robots.txt` for
   `FluidBuddhaIngest` (a 401/403 robots file means stay out; `Crawl-delay` up to
   2 s), seeds from the sitemap, then follows same-site links breadth-first to
   the depth and page limits (capped by `CRAWL_MAX_PAGES` / `CRAWL_MAX_DEPTH`).
   Every request, redirect, robots file, sitemap and stylesheet goes through the
   SSRF-guarded fetch. `noindex` pages and assets are skipped; linked PDFs are
   read.
2. **Ingest**: each page becomes a URL source (a re-crawl refreshes the same
   sources) and is ingested from the text already fetched. Pages become
   navigable routes.
3. **Personas**, only if the site has none: audience URLs (`/for/…`,
   `/solutions/…`, `/industries/…`) become personas with that page as landing;
   with a real model, it proposes 2-4 from page titles when the URLs don't say.
4. **Design tokens** (`app/onboarding/design.py`): brand colours, fonts, radius,
   logo and name from the homepage's CSS variables, `body`/heading rules,
   `theme-color` and colour frequency; stored in `site_design` and used by
   `/design-system` unless a `design-system.json` is configured.

Uploads accept PDF and DOCX (text extracted; scanned PDFs are refused with a
message) as well as text formats, up to 10 MB. The console's Install tab has
a *Preview on your site* bookmarklet that drops the widget onto any page.

To crawl a site running on your own machine, set `INGEST_ALLOW_PRIVATE_URLS=true`
(dev only: it turns the private-address guard off).

### Holdout experiment (A/B)

Console → Experiment, or `PUT /tenant/websites/{id}/experiment
{enabled, holdout_pct, goal_path}`. While a run is on, a share of visitors (the
holdout, 10% by default) never sees the widget; the rest get the agent. Both
groups are measured on the site's own goal: a visit to `goal_path` (matched by
the widget in both arms) or a `FluidBuddha.conversion("name")` call from the
host page. Leads the agent captures are deliberately not counted, since only
one arm can produce them.

- The widget enrols each anonymous visitor id with `POST /experiment/enroll`;
  the arm is a hash of the run id and visitor id, stored on first sight, so a
  visitor keeps their arm. Conversions go to `POST /experiment/convert` (both
  accept a JSON body sent as `text/plain`, so the widget can use
  `sendBeacon`). Keys and the site's domain are checked as on `/chat`.
- These calls come from the customer's site, so its origin must pass
  `CORS_ORIGINS` (use `*` in production; each request is still checked
  against the website's domain). If the browser blocks enrolment, the visitor
  simply gets the agent and isn't counted.
- Results (`GET …/experiment/results`, `app/experiments/stats.py`): each arm's
  rate with a Wilson 95% interval; the difference with Newcombe's hybrid score
  interval; relative lift with a log-scale interval; a two-proportion z-test.
  It reads "collecting" until each arm has 30 visitors and both together have
  10 conversions.
- **Peeking is safe.** The verdict comes from an always-valid 95% interval
  (mSPRT, pooled variance): it stays correct however often the dashboard is
  read, so stopping the day it turns green doesn't inflate false wins (in
  simulation, ≤ 5% against 38% for the plain interval read every 200 visitors).
  When only the plain interval excludes zero the result is `trending`
  ("promising, keep it running"), not `significant`.
- **Planner** (`GET …/experiment/plan?baseline=&mde=&holdout_pct=`): visitors
  needed for 80% power to show a relative lift `mde` over `baseline` (default:
  the holdout's own rate once it has 30 visitors, else 3%), and the days left at
  the run's traffic so far.
- **Bots** aren't enrolled (`app/experiments/bots.py`): a crawler, monitor,
  HTTP-library or headless User-Agent, or the widget reporting
  `navigator.webdriver`. They get the widget, aren't counted, and each run
  shows how many were turned away.
- Changing the holdout share starts a new run (results are per run); changing
  the goal page doesn't.

### Privacy (trust layer)

Each website has privacy settings (console → Settings → Privacy & data, or
`/tenant/websites/{id}/privacy`):

- **PII masking** (on by default): emails, phone, card, SSN and IBAN numbers
  are swapped for placeholders (`<EMAIL_1>`) before the router, the thinker
  and the session history see the message (`app/trust/pii.py`). Transcripts
  store `[email]`-style labels; turns that carried PII are never cached for
  replay. Only `capture_lead` gets the real values back, so leads keep the
  email the visitor gave.
- **Microphone consent** (on by default): `/ws/voice` drops mic audio until the
  widget sends `EVENTS/consent`; the widget asks once per site and browser.
  The time of consent is stored on the conversation.
- **Retention**: transcripts (and auto-cached answers) default to 90 days,
  leads are kept until deleted; a sweep runs every
  `RETENTION_SWEEP_MINUTES` (default 60, 0 = off). Pinned and blocked cached
  answers are never swept.
- **Erasure**: `POST /tenant/websites/{id}/privacy/erase {email}` deletes that
  visitor's leads, the conversations they came from and any visitor memory
  linked to them (M3-3).

Cached answers carry a `status`: `pinned` answers always replay for their
question (even before the "enough history" gate) and survive content
changes; `blocked` ones never replay and their question is not cached again.

## Billing (Razorpay)

Plans cover every website of an account; the unit is a **conversation** (a
visitor session with at least one answered turn, counted from `usage_events`).
Defaults (`app/billing/plans.py`, override with `BILLING_CATALOG` /
`BILLING_CURRENCY`): Free 100 a month (hard cap), Growth ₹33,000 for 2,000 then
₹17 each, Scale ₹1,25,000 for 10,000 then ₹10, Enterprise by arrangement.
Prices are in INR; USD (e.g. $399 / $1,499) needs international payments
enabled on the Razorpay account and a `BILLING_CATALOG` override.

1. Set `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` (test keys in development).
   The Razorpay plans are created on first checkout, one per key, plan, currency
   and price.
2. In Razorpay Dashboard → Webhooks, add `<backend>/billing/razorpay/webhook`
   with the `subscription.*` events and `payment_link.paid`, and a secret; set
   `RAZORPAY_WEBHOOK_SECRET` to it. Webhooks are verified and applied once each.
   Until webhooks are set up (e.g. on a laptop), the Billing page asks Razorpay
   directly about a subscription awaiting payment and about unpaid links.
3. Console → Billing: choosing a plan creates a subscription and opens
   Razorpay Checkout; the payment signature is verified server-side before the
   plan changes. Upgrades apply now, downgrades at the cycle end; cancelling
   keeps the plan to the end of the paid period.

- **Free cap**: once the month's allowance is used, public turns that would
  start a new conversation get `429 plan_limit_reached` (the widget says the
  agent isn't available); conversations already under way may finish.
- **Overage**: when Razorpay charges a new cycle (`subscription.charged`), the
  last cycle's extra conversations are added to the subscription as an add-on,
  billed on the next invoice, and listed in the console.
- **UPI Autopay**: Razorpay refuses add-ons and plan changes on subscriptions
  paid by UPI. Their overage is sent as a Razorpay Payment Link (emailed, with a
  "Pay now" button in the console; `payment_link.paid` marks it paid). A plan
  change is scheduled instead: a new subscription for the new plan starting at
  the renewal (`start_at`), whose mandate the customer approves in Checkout now
  (Razorpay takes a refundable ₹5). Once approved, the current subscription is
  cancelled at the cycle end; its cancellation doesn't drop the account to Free,
  and the new one's first charge hands the account over (and bills the old
  cycle's overage). Cancelling withdraws a scheduled switch.
  Overage that couldn't be billed at all stays pending and is retried on the
  next subscription event.
- A failed renewal keeps the plan while Razorpay retries (`pending`); once it
  gives up (`halted`) the account is on Free limits until it subscribes again.

## Teams, roles and single sign-on

People (users) are separate from accounts. Roles: **Owner** (everything, incl.
billing and SSO), **Admin** (team, integrations, privacy, deleting a site or
rotating its key, audit log), **Editor** (sites, knowledge, tours, answers,
experiments, leads), **Viewer** (read-only). The rule is applied in one place
(`app/auth/roles.py`) from the method and route, so every `/tenant` route is
covered. Invitations are emailed (M2-0) and also returned as a single-use link.

Single sign-on (`app/auth/sso.py`): set `PUBLIC_API_URL` and register
`<PUBLIC_API_URL>/auth/sso/callback` with the provider. "Sign in with Google"
needs `GOOGLE_CLIENT_ID/SECRET` and only signs in existing members. An account's
own OIDC provider (Console → Team → Single sign-on) signs in people of the email
domains the account has proven with a DNS TXT record, with a default role.
Client secrets are encrypted with `SECRETS_KEY`.

The audit log (`app/audit.py`) records every successful change through the
console API plus sign-ins; Console → Audit log, CSV export, kept a year.

## Security controls (M2-11)

- **Sessions** (`app/auth/sessions.py`): every sign-in is a row in
  `user_sessions`; tokens name it, so sessions end when idle
  (`SESSION_IDLE_MINUTES`), at an absolute limit (`SESSION_ABSOLUTE_HOURS`), on
  sign-out, "sign out everywhere", a password change, or removal from the
  team. Tokens from before this release ask the person to sign in again.
- **Console cookie**: the console holds the session in an httpOnly, Secure,
  SameSite cookie; cookie requests that change something need `X-CSRF-Token`
  (from sign-in and `/auth/me`). The live inbox socket takes the CSRF token in
  its first message. Bearer tokens keep working for API clients.
- **Two-factor** (`app/auth/mfa.py`, RFC 6238, no extra dependency): setup with
  a QR code, ten one-time recovery codes (hashed), codes can't be replayed.
  An Owner can require it for the account (`/tenant/security`); password
  sessions without it are held at the setup page. SSO sign-ins count as
  two-factor (the identity provider's).
- **Lockout**: `LOGIN_MAX_ATTEMPTS` wrong passwords or codes in a row lock the
  person out for `LOGIN_LOCKOUT_MINUTES`.
- **Stored secrets** encrypted with `SECRETS_KEY`: SSO client secrets, action
  keys, lead webhook signing secrets and Slack webhook URLs (migration 0024
  converted the existing ones), two-factor seeds.
- **Access review**: `/tenant/team/access-review.csv` (Admin+), and each
  quarter Owners and Admins get an email summary to review.
- **Security headers** on every response (`app/security/headers.py`):
  nosniff, `DENY` framing, referrer policy, `no-store` on `/auth` and
  `/tenant`, HSTS outside dev. The console sets its own CSP
  (`fluid-buddha-frontend/next.config.ts`).
- **Backups**: `scripts/backup.sh` (pg_dump, SHA-256, optional `age`
  encryption, retention, `backup-log.jsonl`) and `scripts/restore_drill.sh`
  (restores into a scratch database, checks it, writes `drills/*.json`).
  Both work against a server URL or through the Postgres container
  (`PG_CONTAINER=a2ui-cortex-db PGUSER=cortex PGDATABASE=cortex`).

Policies and the SOC 2 control matrix are in [`docs/compliance/`](../docs/compliance).

## Proactive triggers

Website → Triggers: rules for when the agent speaks up first — after time on
a page, past a scroll depth, when the visitor is about to leave (desktop),
or on a return visit — on chosen pages, as a bubble by the launcher or by
opening the agent. The widget fetches them from `GET /widget/triggers?key=`
(key and domain checked), evaluates them in the browser with caps (one per
page view, a daily cap per visitor and rule, silence for the visit after a
dismiss or once the visitor talks) and reports shown / clicked / dismissed /
engaged to `POST /widget/triggers/event`; the tab shows each rule's numbers.

## A/B tests

Website → A/B tests: try 2-4 versions of the greeting, the proactive
triggers, the guided tour, the starting persona or the design level (with an
optional holdout). Visitors are assigned by `POST /experiment/enroll`, which
returns their version's `overrides` and the site's `defaults`; the widget
applies them and sends `exp: {id, arm}` with the conversation, so the server
speaks the version's greeting as written and starts in its persona. Results
(`GET /tenant/websites/{id}/tests/{tid}`) compare each version with the
control using the always-valid interval at a split error budget, so checking
daily never inflates false winners. "Make default" (`.../promote`) writes the
winner into the agent profile, the website's design level, or the trigger
switches, and ends the test. One experiment (test or holdout) runs per site.

## Insights v2 and the weekly digest

A background job (`INSIGHTS_CLASSIFY_SECONDS`, default 20) labels each visitor
question: objections by type, competitors (the site's list in the agent
profile, plus what the model spots), feature requests and buying signals —
keyword rules with `MOCK_AI=true`, the fast model otherwise. Insights shows
them with quotes, and a feature request can be sent to Slack, the signed
webhook (`feature_request`) or an email address.

The weekly digest (`DIGEST_CHECK_SECONDS`, default 600) goes out on Monday at
9:00 in each account's time zone (Team page: recipients, time zone, preview,
test send). It needs SMTP outside a dev environment; each email carries a
one-click `List-Unsubscribe` link served by `/digest/unsubscribe`, so set
`PUBLIC_API_URL` to the backend's public address.

## Recap pages

A visitor who types "send me this" (or "email me a recap at …") gets a link to
`/r/{token}`: a recap of their conversation with the components redrawn,
sources and the site's call to action (agent profile). The page loads
`fluid-buddha-recap.global.js` from `WIDGET_SDK_BASE` (where the widget's
`dist/` is served) and is only allowed scripts from that origin. Links expire
per site (Privacy settings, default 90 days) and go with their conversation.
Views and forwards show on the lead and in Leads → Shared recaps.

## Self-hosted installs and the licence (M3-5)

`deploy/selfhost/` is the whole product for one Linux host: Caddy (TLS, routing,
the widget's files at `/sdk/`), backend, console, Postgres+pgvector, Redis,
optional coturn — with health checks, rotated logs, `bin/install.sh`,
`backup.sh` (base backup + WAL archive for point-in-time recovery, and a
logical dump), `restore.sh`, `upgrade.sh` and `export-images.sh` /
`import-images.sh` for air-gapped hosts. Its README is the runbook.

With `SELF_HOSTED=true` the backend checks a licence: an Ed25519-signed token
(`FBL1.<payload>.<signature>`) verified offline against `PUBLIC_KEYS` in
`app/licence/core.py` — no phone-home. It names the customer, websites, seats
(install-wide, pending invitations included), features (`*` or
`byo_model`, `agent_access`, `campaigns`, `sso`, `voice_handoff`), expiry and
grace period. From the console (Account → Licence, Owner; `PUT /tenant/licence`),
`LICENCE_KEY` or `LICENCE_FILE`. 30 days before expiry, and in the grace
period, the console shows a banner; after it (or with none / an invalid one)
`/tenant` changes return 402 — reads still work, and visitors (widget, hosted
pages, agent endpoint) are never affected. Issue licences with
`scripts/licence_tool.py` (`keygen`, `issue`, `verify`); the private key lives
outside the repo (`.licence-keys/`, gitignored).

## Generative landing pages: campaigns (M3-1)

Console → website → Campaigns. A campaign is a brief: goal, audience, key
messages (the first is the headline), which sections the page may use
(feature cards, text, pricing, testimonials, logos, FAQ, comparison, ROI
calculator, chart, enquiry form, image; a hero and a call to action always),
the call to action and its link, and the proof the customer supplies —
testimonials and logos, which the page quotes but never invents. Optionally a
version B (headline, messages, CTA) shown to half the visitors.

Live at `GET /p/{site_key}/{slug}`. The link steers the page:
`?persona=` (or `utm_content`), `?q=` (or `utm_term`) — answered first,
`?account=` ("Prepared for Acme", and pre-filled in the form), `?lang=hi`,
`utm_source` (reported). Drafts open only with the preview link from the
console (not counted, no agent on the page).

Composition (`app/campaigns/compose.py`): the site's knowledge retrieved for
the messages, the persona's focus and the question (above the grounding
threshold), the pinned answers (word for word) and the blocked questions
(never answered). The account's own model (M3-4) or the platform's composes
typed sections that cite their sources; in mock mode, past the composition
rate (20 a minute per site) or past the daily spend cap, a rule-based composer
that only quotes the material does. Whatever composed it, the checks run:
only the campaign's sections; factual sections cite real sources; every
number appears in what it cites (or in the brief); testimonials and logos only
as supplied; the enquiry form is always the same safe one. Failures are
dropped and listed on the cached spec (`dropped`).

Pages are cached per campaign version, arm, persona, question, language and
content version (re-ingesting composes afresh); `?account=` is drawn at
render time and never costs a composition. The `Server-Timing` header says
`cache`, `rules` or `model`. The page is server-rendered (no script needed to
read it or paint the hero); `fluid-buddha-page.global.js` draws the ROI
calculator and charts and reports engagement once; the site's widget is on
the page (the widget accepts our own origin for hosted pages).

Numbers per unique visitor, credited to the arm, persona and source of their
first view: views, engaged (scrolled past half, 15 s visible, or used a
component or the agent), converted (the page's form — a lead with source
`campaign` — or the call to action through `/p/…/go`). Bots aren't counted.
With a version B, the A/B verdict uses the same always-valid test as M2-4.
Embedding: `?embed=1` in an iframe, allowed from the site's domain and the
origins listed on the campaign.

## Returning-visitor memory (M3-3)

Off by default. A website switches it on in Privacy settings ("Remember
returning visitors who ask to be remembered", kept 30–365 days after the last
visit, default 180). Then, after its first answer, the widget asks the visitor
once per browser whether to remember the conversation; "Remember me" calls
`POST /memory {key, visitor, remember: true}` with the widget's anonymous
visitor id (the same id A/B tests use). From then on that visitor's
conversations on that site, text or voice, including the one they opted in
during, are linked to the id (`conversations.visitor_id`; the record links
only while a memory row exists). Every `MEMORY_BUILD_SECONDS` (default 120,
0 = off) a job rebuilds the memory of visitors whose conversation has been
quiet for 10 minutes: their latest questions, components explored, what the
agent couldn't answer, whether they left their details — from the stored,
PII-masked transcript, newest three conversations (`app/memory/store.py`).

Next visit, `/experiment/enroll` returns `memory.welcome_back` (English and
Hindi) and the widget greets with it ("Welcome back! Last time you asked:
“…?” Want to pick up where we left off?"); the voice welcome says the same
and skips the guided tour; the agent gets the notes at the start of the
conversation's history. A memory belongs to one site: the same visitor id
elsewhere is a stranger.

"Forget me" — the widget's chip, or typed / said ("forget me", "मुझे भूल
जाओ") — deletes the memory and unlinks the conversations. So do erasure by
email (through the visitor's conversations), retention, switching the
setting off, and deleting the site. Retention now also sweeps CORTEX episodic
memory older than the transcript window (the WS8 leftover).

## Agent endpoint: MCP + llms.txt (M3-2)

A website can let AI assistants ask it directly (Console → website → Agent
access, off by default; Admins switch it on). With the site's public widget
key in the path:

- `POST /mcp/{key}` — an MCP server over streamable HTTP (JSON-RPC 2.0,
  answered as JSON; stateless; protocol versions 2025-11-25 back to
  2024-11-05). Tools: `search_knowledge` (the site's own agent, one grounded
  turn with sources and the same guardrails), `get_page`, `list_offerings`
  (knowledge + payment price lists). Resources: the site's crawled pages.
  `capture_lead` and the site's actions (`action_<name>`) appear only for a
  token the customer issued with the `leads` / `actions` scope
  (`Authorization: Bearer fbat_…`, stored hashed); the token is the
  authorisation, so actions run at once (amounts still from the price list).
- `GET /sites/{key}/llms.txt`, `GET /sites/{key}/openapi.json`,
  `POST /agent/{key}/ask`, `GET /agent/{key}/offerings` — for assistants that
  read llms.txt or call OpenAPI tools.

Rate-limited per site and client address (30/min), under the site's daily
spend cap, browser `Origin`s limited to the site's domain (MCP's DNS-rebinding
rule), and every call logged in `agent_requests` (the console's agent
traffic: by tool, by assistant). Usage from these calls is recorded with
channel `agent` and no session, so it never counts as a billed conversation.

## Bring your own model (M3-4)

An account can run its agent on its own **Anthropic**, **OpenAI** or **Azure
OpenAI** account (Console → AI model, Owners/Admins). It sets the provider, its
API key (encrypted with `SECRETS_KEY`, never returned), a *fast* model (routing,
quick answers, labelling) and a *thinking* model (grounded answers with tools),
and Azure's endpoint + API version (models are deployment names there). "Test
connection" makes a one-line call with each model. Each website uses the
account's provider unless switched back to the platform's.

`rt.engines.llm` is a `RoutingLLM` (`app/ai/providers.py`): the site of the
current request comes from a context variable set where a conversation, recap,
tour plan or labelling task starts, and calls go to that site's provider
(`app/ai/anthropic_llm.py` with the official `anthropic` SDK,
`app/ai/openai_llm.py` with the official `openai` SDK). The platform's
`HEAVY_MODEL` maps to the thinking model, everything else to the fast one. If
the provider fails the call falls back to the platform model and the error
shows in the console. Voice and embeddings stay on Google.

Claude requests send no sampling parameters, set depth with
`output_config.effort` (low for quick calls; thinking off where the model
allows it), replay a tool turn's content blocks (thinking included) verbatim,
handle `refusal`, and use the server-side fallback (`fallbacks: "default"`) on
the models that support it.

Usage records the provider; that model cost is priced at the account's
prices (or the provider's list price where known), shown separately on
Analytics (`byo_llm_cost`) and left out of the daily spend cap.

## Install surfaces

Every way of installing the agent — the plain snippet, the WordPress plugin, the
Shopify app embed, Google Tag Manager, Webflow, Framer, `@fluidbuddha/react` and
`@fluidbuddha/vue` (all in [`integrations/`](../integrations)) — loads one script:

```html
<script src="https://<this server>/widget/loader.js" data-key="fbk_…" async></script>
```

The loader adds the widget from `WIDGET_SDK_BASE` with the same `data-*`
settings (or the same settings from its query string, for GTM) and points it
back at the server it came from, so a page needs only the key. Design, colour,
greeting and tier come from the console. `data-auto="false"` loads the widget
without showing it (the framework wrappers create it themselves);
`fluidbuddha:ready` fires on `window` when it's loaded. It's the same for every
site, cached for 5 minutes.

`/widget/gtm-template.tpl` is a GTM custom template whose only permission is to
inject this server's loader (built from `PUBLIC_API_URL`).

Plugins take the server and key as one *install code*, `https://fbk_…@<server>`,
shown in the console's Install tab.

## Live takeover and voice handoff

Console → Live lists who is talking to the agent right now on the account's
sites and streams each conversation. An Editor can **take over** (the agent
pauses; the visitor is told who joined), reply, and **hand back** (the agent
gets what was said). Voice visitors can be **called** in the browser (WebRTC;
the visitor accepts; the agent stops listening). Events travel over an
in-process bus, or Redis pub/sub across replicas with `REDIS_URL`; operators
receive them on `WS /tenant/live/events`; text-mode widgets long-poll
`/chat/live`.

Calls need STUN and, behind strict networks, our TURN relay: run
`TURN_SECRET=… docker compose --profile voice up -d coturn` on a host with a
public IP (ports 3478 UDP/TCP and 49160–49200 UDP), then set `TURN_URLS` and
the same `TURN_SECRET` on the backend. Credentials are minted per call and
expire after `TURN_TTL_SECONDS` (coturn `use-auth-secret`).

## Operations

- **Request ids.** Every response carries `X-Request-ID` (the caller's, if it
  sent a plain one), and every log line written while handling it shows that
  id; voice log lines also carry the session. `LOG_FORMAT=json` writes one JSON
  object per line.
- **Metrics** at `/metrics` (Prometheus; `METRICS_TOKEN` to require a bearer
  token, `METRICS_ENABLED=false` to turn it off). Labels are route templates and
  stages, never site keys or ids:
  - `fb_time_to_first_audio_seconds{path}`: question received to the first byte
    of speech sent, usually the ack; `fb_time_to_first_answer_audio_seconds`
    for the answer itself (`path` = `fresh` or `cached`);
  - `fb_turns_total` / `fb_turn_seconds{channel,path}`,
    `fb_stage_seconds{stage}` (route, retrieval, think_lean, think_heavy, tts),
    `fb_engine_errors_total{engine}`, `fb_http_requests_total` /
    `fb_http_request_seconds{method,route}`, `fb_ws_connections`,
    `fb_crawl_jobs_total{status}`, `fb_cost_alerts_total{level}`.
  Time to first audio is also stored per voice turn (`usage_events.ttfa_ms`)
  and shown per site on the console's Analytics tab (median and p95).
- **Email** (`app/notify/email.py`): plain SMTP (`SMTP_*`). Everything is queued
  in `email_outbox` and sent by a background job: retried with backoff
  (1 → 32 minutes, 6 attempts), claimed with `SKIP LOCKED` so replicas never
  double-send, deduplicated by an idempotency key, and deleted 30 days after
  sending. Without `SMTP_HOST`, dev logs each email; production refuses to queue.
  Set up SPF and DKIM for the sending domain at your provider.
- **Background jobs** (`app/jobs/`): retention sweep, email outbox and cleanup
  run on one scheduler; each run holds a Postgres advisory lock, so only one
  replica runs a job at a time (`fb_job_runs_total{job,outcome}`).
- **Cost alerts** (`app/analytics/alerts.py`): each site can set a daily AI-cost
  alert (Console → Settings → Lead integrations, USD); with a daily spend cap
  (`PUBLIC_DAILY_SPEND_CAP_USD`) every site is also alerted at 80% and 100% of
  it. Each kind goes out at most once per site per UTC day: posted to the
  site's Slack webhook, listed on its Analytics tab (`GET …/cost-alerts`),
  logged and counted. The check runs with the spend cap before a public turn
  and sends in the background, so a turn never waits on Slack.
- **Tracing** (optional): set `OTEL_EXPORTER_OTLP_ENDPOINT` to an OTLP/HTTP
  collector. Each HTTP request is a span, with the turn (`voice.turn`,
  `chat.turn`) and its stages (`stage.route`, `stage.retrieval`,
  `stage.think_*`, `stage.tts`) below it. Spans never hold what visitors said.
- **Errors** (optional): set `SENTRY_DSN`. Events carry the request id; request
  bodies, cookies, query strings, auth headers, users and local variables are
  stripped first (`app/observability/errors.py`).
  OpenTelemetry and Sentry come from `requirements-observability.txt`
  (installed in the Docker image; inert unless configured).
- **More than one replica**: set `REDIS_URL`. Chat sessions (with their PII
  placeholders, expiring after `SESSION_TTL_MINUTES` idle) and the public
  per-minute rate limit then live in Redis, so any replica can take the next
  turn. Without it both stay in process, which is right for one replica.
  A voice WebSocket keeps its state on the connection and needs no Redis; if
  Redis is unreachable, sessions start fresh and the rate limit falls back to
  the replica's own count. `docker compose --profile scale` starts a Redis.

## Going live on Vertex AI

1. `gcloud auth application-default login` (or set `GOOGLE_APPLICATION_CREDENTIALS`).
2. In `.env`: `MOCK_AI=false`, set `GOOGLE_CLOUD_PROJECT` / `VERTEX_LOCATION`.
3. Re-run ingestion so chunks are embedded with `text-embedding-004` (768-dim).

Models are configurable: `FAST_MODEL` (Fast Router), `HEAVY_MODEL` (Heavy Thinker),
`EMBED_MODEL`, `TTS_VOICE`, `ASR_LANGUAGE`.

## API

### `POST /chat` — text path / WebSocket fallback (Req 4.3)
Request: `{ "message", "session_id?", "site?", "icp?", "page?" }`
Response: `{ text, ack, intent, persona, actions[], components[], grounding, session_id }`

### `WS /ws/voice?site=hirebuddha` — multiplexed voice transport
JSON envelopes: `{ channel, type, payload, sync_id, timestamp }` on channels
`AUDIO | DATA | EVENTS | STATE`. Client → server: `AUDIO/start|chunk|end`
(`end.payload.transcript` overrides ASR), `EVENTS/text`, `STATE/sync`,
`STATE/barge_in`. Server → client: `EVENTS/ready`, `AUDIO/*` (TTS),
`DATA/render|patch` (UI), `EVENTS/navigate|scroll_to|set_persona`,
`STATE/transcript`. **Correlated `DATA` + `AUDIO` share a `sync_id`** so the
frontend jitter buffer holds audio until its UI renders (Req 3.2.3/3.2.4).

With `?audio=binary` (the widget always asks; `ready.config.audio_frames`
confirms), audio chunks travel as binary WebSocket frames instead of base64
JSON, in both directions: byte 0 = `0x01`, byte 1 = sync_id length N, then N
bytes of sync_id, then PCM16 LE mono (`app/transport/envelope.py`). Mic audio
is capped at one minute per utterance.

Speech is synthesised one sentence ahead of the one being sent, and Gemini
TTS is streamed (falling back to the one-shot call if streaming fails), so
long answers play without gaps. A short follow-up ("how much is it?") is
searched together with the question it follows, and is never replayed from
or saved to the answer cache (`app/orchestrator/rewrite.py`).

## How it maps to the architecture

| Component | Code |
|---|---|
| Fast Router (intent/persona/ack) | `app/orchestrator/router.py` |
| Heavy Thinker (grounded reasoning + tools) | `app/orchestrator/thinker.py` |
| `query_cortex` + grounding guardrail (says so when it does not know) | `app/cortex/query.py` |
| CORTEX bridge (ingest + cosine retrieval) | `app/cortex/bridge.py` |
| Gemini ↔ cortex provider adapters | `app/cortex/providers.py` |
| Vertex LLM / ASR / TTS engines | `app/ai/vertex.py` |
| Deterministic mock engines | `app/ai/mock.py` |
| Multiplexed WebSocket + barge-in | `app/transport/websocket.py` |
| Message envelope | `app/transport/envelope.py` |
| Ingestion pipeline (semantic scrape + DOM anchors) | `ingestion/` |

The framework targets 4 sites; each gets an isolated CORTEX knowledge tree keyed
by a deterministic per-site entity id (`app/config.py:site_entity_id`).
