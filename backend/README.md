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
  It reads "collecting" until each arm has 30 visitors and some conversions.
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
  visitor's leads and the conversations they came from.

Cached answers carry a `status`: `pinned` answers always replay for their
question (even before the "enough history" gate) and survive content
changes; `blocked` ones never replay and their question is not cached again.

## Billing (Razorpay)

Plans cover every website of an account; the unit is a **conversation** (a
visitor session with at least one answered turn, counted from `usage_events`).
Defaults (`app/billing/plans.py`, override with `BILLING_CATALOG` /
`BILLING_CURRENCY`): Free 100 a month (hard cap), Growth $399 for 2,000 then
$0.20 each, Scale $1,499 for 10,000 then $0.12, Enterprise by arrangement.

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
    `fb_crawl_jobs_total{status}`.
  Time to first audio is also stored per voice turn (`usage_events.ttfa_ms`)
  and shown per site on the console's Analytics tab (median and p95).
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
