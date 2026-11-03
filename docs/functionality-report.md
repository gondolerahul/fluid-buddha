# Fluid-Buddha — Built Functionality Report

> **Scope.** This report is based on a line-by-line read of every source, config, test and
> doc file in this repository (~16.3k lines of code) as of commit `83f4bcc` (2026-11-03): the FastAPI backend
> (`backend/`), the embeddable SDK (`fluid-buddha-sdk/`), the admin console
> (`fluid-buddha-frontend/`), and `docs/`. Lockfiles were not read. The `skills/` folder
> holds third-party AI-coding instructions (GSAP, design-taste, etc.), not product
> code, so it was skimmed rather than audited.
> **Nothing was executed:** dependencies are not installed and no Postgres is running
> in this checkout, so the test suites described in §9 were **not** run.

---

## 1. Executive summary

**What it is.** Fluid-Buddha is a voice-first AI website agent ("Pragya") delivered as one
`<script>` tag. A visitor talks to the website or types. The agent answers out loud,
grounds its answers in the site's own content, draws interactive diagrams and calculators
while it speaks, scrolls and navigates the page, silently re-themes the site for the
visitor's segment, and can run a narrated guided tour. At the top tier it can generate whole
pages at runtime from a brand design system and call the site's APIs.

**What is built.** There are three working subsystems:

| Subsystem | Stack | Size | Maturity |
|---|---|---|---|
| **A2UI Orchestrator** (backend) | Python 3.12, FastAPI, SQLAlchemy async, Postgres + pgvector, `hb-cortex-memory`, Google Vertex AI (Gemini LLM, embeddings, Gemini TTS, Cloud STT) | ~7.9k lines (incl. tests) | Strong prototype / early beta |
| **`fluid-buddha` SDK** (Web Component) | TypeScript, Shadow DOM, Web Audio, 2D canvas, Three.js | ~6.5k lines (incl. demos/tests) | Strong prototype, polished UX |
| **Admin Console** | Next.js 16, React 19, recharts | ~1.9k lines | Functional MVP |

**Verdict.** The core voice loop is unusually complete and well engineered: latency masking
with a dual model, a hybrid lean/heavy router, audio and UI kept in sync through a jitter
buffer, barge-in, a sentence-chunked TTS pipeline, a byte-exact audio cache, and episodic
answer replay. The generative-UI library (13 safe, typed components) and the three design
levels are distinctive.

The main weakness is that **the "brain" is still hard-wired to one customer (HireBuddha)**:
personas, prompts, sitemap and tour copy. The multi-tenant layer stores tenant settings but
**does not enforce them on the public endpoints**. Several features promised in the
marketing copy are not implemented (CRM sync, PDF ingestion, approval workflows, quoted
conversion statistics). §10 and §11 list these gaps and risks.

---

## 2. Repository map

```
fluid-buddha/
├── backend/                     FastAPI orchestrator ("the Brain")
│   ├── app/
│   │   ├── ai/                  Engine interfaces + Vertex + deterministic mocks
│   │   ├── analytics/           Pricing model + per-turn usage events + rollups
│   │   ├── apis/                Per-site OpenAPI registry (Extreme tier)
│   │   ├── auth/                bcrypt + JWT + current_tenant dependency
│   │   ├── cortex/              CORTEX bridge, query guardrail, episodic cache
│   │   ├── design/              Per-site design-system loader (Extreme tier)
│   │   ├── orchestrator/        Router, lean responder, thinker, tools, prompts,
│   │   │                        personas, sitemap, state, tour planner/store
│   │   ├── routes/              HTTP routes (chat, design, health, admin APIs)
│   │   ├── tenancy/             Tenants, websites, ingestion sources
│   │   └── transport/           WebSocket voice session, envelope, caches
│   ├── ingestion/               CLI + file loader (markdown → CORTEX)
│   ├── scripts/                 smoke_chat / smoke_ws
│   ├── tests/                   7 pytest modules (need live pgvector)
│   └── Dockerfile, docker-compose.yml, docker-entrypoint.sh
├── fluid-buddha-sdk/            <fluid-buddha> Web Component
│   ├── src/audio/               Mic capture + VAD, PCM player, jitter buffer
│   ├── src/core/                Config, Session, HostBridge, Tour, design tokens
│   ├── src/transport/           WebSocket client
│   ├── src/ui/                  Element, styles, Aura, L2 particles/shell,
│   │                            L3 shell, 13 components, page renderer
│   ├── demo/                    3 demo host pages
│   └── test/                    jsdom smoke + auto-inject tests
├── fluid-buddha-frontend/       Next.js tenant admin console
└── docs/
    ├── product-docs/            functional/technical spec, impl guide, marketing brief
    └── website-copies/          5 marketing pages (deleted in working tree, still in git)
```

---

## 3. System architecture

```
 Browser (any host site)                                Backend (FastAPI :8080)
┌─────────────────────────────────────┐   WS /ws/voice ┌──────────────────────────────────┐
│ <fluid-buddha> (Shadow DOM)         │◄──────────────►│ VoiceSession (per socket)        │
│  Session ── VoiceClient (WS)        │  JSON envelopes │  ├─ cache-first replay check     │
│   ├─ AudioCapture (16k PCM + VAD)   │  AUDIO/DATA/   │  ├─ FastRouter  → ack + persona  │
│   ├─ Web Speech API transcript      │  EVENTS/STATE  │  ├─ needs_heavy? ─┬─ LeanResponder│
│   ├─ JitterBuffer → AudioPlayer     │                │  │                └─ HeavyThinker │
│   ├─ TourController                 │  POST /chat    │  │     tool loop: query_cortex,  │
│   └─ HostBridge → host DOM / hooks  │◄──────────────►│  │     render_component, navigate│
│  UI: L1 panel | L2 smoke | L3 aura  │  (text fallbk) │  │     scroll_to, set_persona,   │
│  Canvas (13 components)             │                │  │     generate_page, call_api   │
│  PageRenderer (Extreme)             │ GET /design-   │  ├─ sentence-chunked TTS + cache │
└─────────────────────────────────────┘ system         │  └─ record turn + usage (async) │
                                                       │                                  │
 Admin Console (Next.js)  ── REST /auth, /tenant/... ──►│ Tenancy · Ingestion · Tours ·   │
                                                       │ Cache editor · Analytics         │
                                                       └───────────────┬──────────────────┘
                                                                       ▼
                                          Postgres + pgvector: CORTEX trees/nodes/edges,
                                          conversation_cache, answer_audio_cache,
                                          site_tours, usage_events, tenants,
                                          tenant_websites, tenant_sources
                                                       │
                                          Vertex AI: Gemini (fast + heavy), text-embedding-004,
                                          Gemini native TTS, Cloud Speech-to-Text
```

**Mock mode.** With `MOCK_AI=true` (the default), every engine is replaced by a
deterministic stub ([mock.py](../backend/app/ai/mock.py)). The full stack (DB, ingestion,
tool loop, WebSocket, analytics) then runs with no Google Cloud credentials. The mock LLM
drives the real function-calling loop: turn 1 grounds, turn 2 acts, turn 3 speaks.

---

## 4. Backend: built functionality

### 4.1 Configuration & runtime
- **Settings** ([config.py](../backend/app/config.py)) via pydantic-settings and `.env`:
  runtime, DB URL, `MOCK_AI`, Vertex project and location, model IDs (`fast_model`
  gemini-2.5-flash, `heavy_model` gemini-2.5-pro, `embed_model` text-embedding-004 at 768
  dimensions, `tts_model` gemini-3.1-flash-tts-preview with voice "Aoede"), CORTEX
  thresholds (confidence 0.45, top-k 5), JWT, filler delay (1500 ms), and conversation-cache
  knobs (replay ≥ 0.92, context ≥ 0.70, minimum 20 episodes, top-k 3).
- **Site registry**: `SITE_KEYS` lists 4 house sites (hirebuddha, buddha-cognitive-lab,
  fluidbuddha, chantingbuddha). Any string is mapped to an isolated knowledge tree via
  `uuid5(namespace, site_key)`.
- `vertex_model_id()` strips a `google/` prefix from gateway-style model IDs.
- **Runtime singletons** ([runtime.py](../backend/app/runtime.py)): engines, CORTEX
  providers, and the `CognitiveLoop`, plus factories for the per-request bridge, episodic
  cache and audio cache.
- **Startup** ([main.py](../backend/app/main.py)): creates the pgvector extension and CORTEX
  tables, builds the runtime, configures CORS (a wildcard switches to an `.*` regex), and
  mounts 10 routers.

### 4.2 AI engine layer (`app/ai/`)
| Engine | Real implementation | Mock |
|---|---|---|
| LLM (function calling) | `VertexLLMClient`: google-genai on Vertex. Merges consecutive tool responses into one turn, replays Gemini 3.x thought signatures, disables SDK auto-function-calling, supports `thinking_budget`, drops "thought" parts, reports token usage | Rule-based keyword router; ground → act → speak sequence |
| Embeddings | `VertexEmbedder` (768-dim) | cortex `HashEmbeddingProvider` (768-dim) |
| ASR | `VertexASR`: Cloud Speech streaming, LINEAR16 at 16 kHz, interim results | Returns empty (the client transcript is used) |
| TTS | `GeminiTTS`: Gemini native audio, raw PCM16 at 24 kHz, strips WAV header, ~200 ms chunks. `VertexTTS` (Cloud TTS Neural2) is kept as a legacy fallback | Silence sized to text length |

All Google imports are lazy, so CI and mock mode never need the SDKs.

### 4.3 Cognitive loop (`app/orchestrator/`)
**Observe → Plan → Act → Speak** ([loop.py](../backend/app/orchestrator/loop.py)):

1. **Fast Router** ([router.py](../backend/app/orchestrator/router.py)). Calls the fast
   model at temperature 0.2 with at most 120 tokens. It returns JSON `{intent, persona,
   persona_confidence, persona_explicit, ack}`. Intents are greeting, capability,
   pricing_roi, integration, navigation and general. The ack is a phrase of 12 words or
   fewer that is spoken immediately. JSON is extracted tolerantly, and any failure falls
   back to "Let me look that up for you."
2. **Hybrid routing** ([lean.py](../backend/app/orchestrator/lean.py) `needs_heavy`). A turn
   goes to the Heavy Thinker if its intent is pricing_roi, integration or navigation, or if
   it matches a keyword regex (show, diagram, chart, compare, roi, price, integrat,
   navigate, "take me", scroll, tour, demo, …). All other turns take the **Lean
   Responder**: one retrieval and one fast-model generation, 400 tokens, thinking off.
3. **Heavy Thinker** ([thinker.py](../backend/app/orchestrator/thinker.py)). A
   function-calling loop with at most 4 LLM iterations and **at most 1 CORTEX search**.
   Extra `query_cortex` calls are refused, and once the search budget is spent the tool is
   withdrawn from the offered set. Spoken text is captured from every iteration, because
   Gemini can bundle text with tool calls. If no text comes back, a forced answer pass runs
   with a nudge, followed by a canned fallback. Token and tool usage is tracked for cost.
4. **Adaptive persona** (Feature 1). `apply_persona` switches only on confidence ≥ 0.6. An
   explicit self-identification *locks* the persona, and a lock can only be overridden at
   ≥ 0.9. A `set_persona` tool call is treated as 0.8. `should_probe` weaves in one
   qualifying question at most every 3 turns while the read is weak (< 0.5) and the
   persona is not locked.
5. **Welcome**: an agent-initiated, page-aware greeting, grounded through the same loop.
6. **Live reaction** (`react`): one ungrounded sentence from the fast model when the
   visitor plays with a component.

**Tools and intelligence gating** ([tools.py](../backend/app/orchestrator/tools.py)):

| Tier | Tools offered to the Thinker |
|---|---|
| `basic` | `query_cortex`, `navigate`, `scroll_to` |
| `high` | + `set_persona` |
| `advance` (default) | + `render_component`, `patch_component` |
| `extreme` | + `generate_page`, + `call_site_api` (only if the site has an OpenAPI spec) |

**Prompts** ([prompts.py](../backend/app/orchestrator/prompts.py)) are assembled from:
non-negotiable grounding rules, a capability fragment per tier, page awareness (current
route and section), valid scroll anchors reported by the client, "related past answers"
from the cache, the persona probe directive, the Extreme brief, and the valid-routes
sitemap.

**Safety normalisers**
- `normalize_component` ([components.py](../backend/app/orchestrator/components.py)): an
  unknown type becomes `table`, and every list field is capped at 48 items.
- `normalize_page` ([pagegen.py](../backend/app/orchestrator/pagegen.py)): only 9 known
  section types are kept, at most 12 sections, and titles are capped at 160 characters.
- `resolve_route` ([sitemap.py](../backend/app/orchestrator/sitemap.py)): exact routes plus
  dynamic prefixes. A miss is snapped by fuzzy match (cutoff 0.82), then by a unique
  last-segment match, else the navigation is **dropped** so the visitor never lands on a
  404. The model is told `invalid_route`.

**Conversation state** ([state.py](../backend/app/orchestrator/state.py)): a 12-turn
sliding history, current page, viewport section, up to 40 scroll targets, persona
confidence/lock/probe counters, and a registry of the last 8 rendered components used for
live reactions.

### 4.4 Grounding: CORTEX (`app/cortex/`)
- `CortexBridge` wraps `cortex_memory.KnowledgeTreeService`. It keeps one entity-scoped
  tree per site with DOCUMENT → SECTION → CHUNK nodes and 768-dim embeddings.
- `query_cortex` ([query.py](../backend/app/cortex/query.py)) returns top-k snippets
  (document, section and score). `confidence` is the top-1 cosine score. Below 0.45 it sets
  `found=false`, returns only 2 snippets, and attaches a **guardrail** instruction: "do NOT
  invent… pivot or offer to connect with the team."
- Provider adapters ([providers.py](../backend/app/cortex/providers.py)) inject Vertex
  embeddings and LLM into cortex, or reference hash/echo providers in mock mode.

### 4.5 Conversation cache and episodic replay (Feature 2)
[episodic.py](../backend/app/cortex/episodic.py) and
[answer_audio.py](../backend/app/transport/answer_audio.py):
- **Records** every turn (question, answer, rendered components, actions, persona, page,
  channel and embedding) in `conversation_cache`. It also writes a best-effort CORTEX
  episodic tree entry (month → day → episode) for future consolidation.
- **Hybrid replay** first tries an *exact normalised-question* match (score 1.0), then
  persona-compatible cosine neighbours. Once ≥ 20 turns are cached for that persona:
  - a score ≥ 0.92 **replays the answer verbatim**, with components and byte-exact audio,
    and spends no LLM tokens;
  - a score ≥ 0.70 injects the match into the prompt as "related past answers";
  - otherwise the turn is answered fresh.
- **Audio cache**: the PCM of every synthesised sentence is stored under
  `sha256(voice|rate|text)`. Repeated sentences (acks, tour narration, replays) cost
  nothing and keep the same prosody.
- **Admin CRUD**: list, search, get, edit (editing the question re-keys and re-embeds it)
  and delete. Tour stops are recorded as `kind='tour_stop'` so they never replay as turns.
- **Privacy note in code**: visitor microphone audio is never persisted. Only transcripts
  and the agent's own audio are stored.

### 4.6 Extreme tier: generative site
- **Design system** ([system.py](../backend/app/design/system.py)): a per-site
  `design-system.json` supplying colours, typography, radius, logo and brand voice, merged
  over defaults. It is served as `--ds-*` CSS tokens at `GET /design-system?site=` and
  summarised into the prompt as "brand voice, don't invent colours".
- **Page generation** ([pagegen.py](../backend/app/orchestrator/pagegen.py)): section types
  are hero, feature_grid, text, pricing_table, chart, flowchart, enquiry_form, cta and
  media. The "Extreme brief" tells the model to build pages and ground all copy in CORTEX.
- **Site API registry** ([registry.py](../backend/app/apis/registry.py)): parses OpenAPI
  `paths` into operation IDs. Only declared operations can be called. The base URL and auth
  header come from env, never from the model. With no base URL, or in mock mode, calls are
  **simulated** and echo their parameters.

### 4.7 Guided tour (Req 5)
- **Planned once at ingestion** ([tour.py](../backend/app/orchestrator/tour.py)). The heavy
  model receives a page catalogue (up to 14 pages) and returns 6–9 stops of
  `{narration, move: navigate|scroll}`. The tour always ends on a concrete use-case stop
  with illustrative time-to-automate and monthly or yearly time and money savings. A
  deterministic fallback plan is used in mock mode or when the planner fails.
- **Stored** in `site_tours` ([tour_store.py](../backend/app/orchestrator/tour_store.py)).
  On `EVENTS/hello` it is sent to the client as `tour_plan`, unless `data-tour="false"`.
- **Played back with no LLM**. The client sends `tour_say`, the server speaks the stop and
  replies `tour_done`, and the client then performs the move. Speech and scroll stay
  exactly in sync. Each played stop is recorded.

### 4.8 Transport
**WebSocket `/ws/voice?site=&intelligence=`**
([websocket.py](../backend/app/transport/websocket.py)). Envelopes have the shape
`{channel, type, payload, sync_id, timestamp}` ([envelope.py](../backend/app/transport/envelope.py)).

| Direction | Channel / type | Meaning |
|---|---|---|
| C→S | `AUDIO/start · chunk · end` | Mic PCM (base64). `end.transcript` overrides server ASR |
| C→S | `EVENTS/text` | Typed message |
| C→S | `EVENTS/hello` | Visitor opened the agent: triggers the tour plan or a spoken welcome (once per session) |
| C→S | `EVENTS/tour_say` | Speak tour stop *n* |
| C→S | `STATE/sync` | page, section/viewport, sections, persona, intelligence, or `component_state` |
| C→S | `STATE/barge_in` | Visitor interrupted |
| S→C | `EVENTS/ready` | session_id, filler delay, sample rate |
| S→C | `STATE/transcript` | Echo of the final user text |
| S→C | `AUDIO/start · chunk · end` | TTS segments. `start` carries the full text and grounding |
| S→C | `DATA/render`, `DATA/render_page` | Component or full-page specs sharing the answer's `sync_id` |
| S→C | `EVENTS/navigate · scroll_to · set_persona` | DOM commands |
| S→C | `EVENTS/tour_plan · tour_done · interrupted · recalibrating · error` | Lifecycle |

`VoiceSession` behaviour:
- **Latency overlap.** The thinker task starts *before* the ack is spoken, so reasoning
  runs during the ack.
- **Sentence-chunked TTS** (`split_for_tts`, segments of at least 24 characters). The first
  segment carries the gating `sync_id`, and later segments play in FIFO order.
- **Utterance coalescing.** A new utterance that arrives within 10 s while a response is
  still in flight is merged with the previous one, which handles ASR/VAD splitting one
  thought into fragments.
- **Barge-in gating.** An interruption is honoured only while the *answer* is playing.
  Speech during the ack or thinking phase is treated as the visitor finishing their
  sentence.
- **Live component reactions**, debounced by 0.7 s. The agent never talks over an answer,
  an in-flight turn or a tour.
- **Basic tier**: still sends AUDIO start/end so text and grounding surface, but skips TTS.
- **Recording**: turn recording and usage metering run as fire-and-forget background tasks
  that are kept referenced.

**HTTP `POST /chat`** ([chat.py](../backend/app/routes/chat.py)) is the text path and the
WebSocket fallback. It goes through the same loop, cache-first replay, recording and
metering, and returns the Pragya `Message` shape: text, ack, intent, persona, actions,
components, pages, grounding and session_id. Sessions live in an in-process dict
([session_store.py](../backend/app/transport/session_store.py)).

### 4.9 Multi-tenant admin API
JWT bearer auth (HS256, 7-day expiry). Passwords are SHA-256 pre-hashed and then
bcrypt-hashed, which avoids bcrypt's 72-byte truncation ([security.py](../backend/app/auth/security.py)).
Every `/tenant/websites/{id}/…` route resolves through `owned_website`, so a site that
belongs to another tenant returns 404.

| Method & path | Function |
|---|---|
| `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | Self-service email/password accounts (409 on duplicate, 401 on bad password) |
| `GET/POST /tenant/websites`, `GET/PATCH/DELETE /tenant/websites/{id}` | Website CRUD. `site_key` is a unique slug of the name. Fields: intelligence (4 levels), design (`level1`/`level2` only), accent, domain, status |
| `GET /…/ingestion` | Sources, status counts, CORTEX document count |
| `POST /…/sources` (text \| url), `POST /…/sources/upload` (≤ 2 MB UTF-8 text), `DELETE /…/sources/{sid}` | Manage knowledge sources |
| `POST /…/ingestion/run[?wait=true]` | Ingest pending sources (background task). URLs are fetched and HTML-stripped. Each source is marked ingested or failed with a node count, then the tour is re-planned |
| `GET/PUT /…/tour`, `POST /…/tour/generate` | View, edit or regenerate the guided tour |
| `GET/PUT/DELETE /…/cache[/{eid}]` | Curate replayed answers and actions (search, paging, hit counts) |
| `GET /…/analytics?group_by=day\|hour\|session&from=&to=` | Cost and performance rollup |
| `GET /healthz`, `GET /readyz` | Liveness, plus DB / mock / model readiness |
| `GET /design-system?site=` | Brand tokens (public) |

### 4.10 Analytics and cost model
- **Usage events** ([usage.py](../backend/app/analytics/usage.py)): one `usage_events` row
  per turn (voice or text, generated or cached). It holds ASR ms, TTS characters, fast and
  thinker input/output tokens, tool calls, latency, and the USD cost of each stage.
- **Rate card** ([pricing.py](../backend/app/analytics/pricing.py)). Each rate can be
  overridden by env:

  | Item | Default rate |
  |---|---|
  | ASR | $0.016 / min |
  | TTS | $0.016 / 1k chars |
  | Fast model | $0.000075 in / $0.0003 out per 1k tokens |
  | Thinker model | $0.0003 in / $0.0025 out per 1k tokens |
  | Tool call | $0.0002 |

  Token counts are estimated at ~4 characters per token when the provider gives no usage.
  For voice, ASR duration is estimated at ~15 characters per second of transcript.
- **Rollup** groups by day, hour or session. It returns per-category sums, totals, average
  / p50 / p95 latency, cache hit rate, and generated-versus-cached cost split.

### 4.11 Data model (all raw DDL, created lazily with `IF NOT EXISTS`)
| Table | Purpose |
|---|---|
| CORTEX ORM tables (`cortex_trees`, `cortex_nodes`, `cortex_edges`, …) | Knowledge and episodic trees, `vector(768)` |
| `conversation_cache` | Replayable turns plus embeddings and hit counts |
| `answer_audio_cache` | Agent TTS PCM keyed by hash |
| `site_tours` | One tour plan per site |
| `usage_events` | Per-turn metering |
| `tenants`, `tenant_websites`, `tenant_sources` | Admin model |

### 4.12 Ingestion pipeline
- **CLI** `python -m ingestion.ingest --site <key> [--reset | --if-empty]`
  ([ingest.py](../backend/ingestion/ingest.py)): loads markdown copy, ingests it into
  CORTEX, then plans and saves the tour.
- **Loader** ([scraper.py](../backend/ingestion/scraper.py)): reads
  `<site>-website/docs/{website-copies,product-docs}/*.md`. Filenames map to routes
  (`NN-pricing.md` → `/pricing`; `loop-*`, `usecase-*`, `story-*`, `icp-*` patterns), and
  each document is prefixed with `[Page: /route]` so retrieved snippets are page-aware.

### 4.13 Operations
- **Dockerfile**: python:3.12-slim with a `/healthz` healthcheck.
- **docker-compose**: `pgvector/pgvector:pg16` on host port 5434, and the backend on 8080,
  which ingests HireBuddha on first boot (`--if-empty`). The content folders of three
  sibling websites are mounted read-only.
- Logging: a formatted stdlib logger, with `cortex_memory` held at WARNING.

---

## 5. SDK (`<fluid-buddha>`): built functionality

### 5.1 Distribution and configuration
- **Builds** ([build.mjs](../fluid-buddha-sdk/build.mjs)): an IIFE (`window.FluidBuddha`,
  minified), ESM, CJS and `.d.ts`. **Three.js is always bundled** (~590 kB minified per the
  README).
- **Install**:
  - one `<script data-backend=…>` tag, which auto-injects;
  - or `init({...})` programmatically;
  - or a `<fluid-buddha>` element in markup.
- **Options** ([config.ts](../fluid-buddha-sdk/src/core/config.ts)): `backend`, `api`
  (derived wss→https), `site`, `position`, `accent`, `greeting`, `auto`, `auto-start`,
  `intelligence` (4), `design` (level1/2/3), `tour`, and hooks
  `onNavigate`/`onScrollTo`/`onSetPersona`.
- **Public API**: `init`, `FluidBuddhaElement` (with `ask(text)`, `openPanel`, `close`,
  `toggle`), `Session`, `HostBridge`, `Canvas`, and the protocol types.

### 5.2 Session orchestration ([Session.ts](../fluid-buddha-sdk/src/core/Session.ts))
- Owns the WebSocket client, mic capture, Web Speech recognition (client-side transcript,
  en-US), jitter buffer and player.
- Routes every server envelope: DOM commands go to the HostBridge, DATA goes to the UI
  callbacks, and AUDIO goes to the jitter buffer. Segments whose `sync_id` starts with
  `ui_` are *gated* until their component renders. Acks (`ack_*`) are spoken but not shown
  as messages.
- **Barge-in** keys off actual playback. If the jitter buffer is playing or audio is
  pending, the client sends `barge_in`, flushes audio, and aborts the tour.
- **Text fallback**: if the socket is not open, `POST /chat` is used, and actions,
  components and pages from the response are applied.
- **Page awareness**: path, title, the section in view (heading near the top of the
  viewport), and up to 30 `[id]` sections with heading labels are sent on connect, on
  every typed turn, and in the hello message.
- **Autoplay**: the AudioContext is primed inside the user gesture, and audio is unlocked
  on the first pointer, key or touch.

### 5.3 Audio stack
- **AudioCapture**: `getUserMedia` with echo cancellation, noise suppression and AGC. A
  ScriptProcessor (4096 samples) downsamples to PCM16 at 16 kHz. **Energy VAD with
  hysteresis**: start threshold 0.03 sustained for 180 ms, continue threshold 0.018, end
  after 850 ms of hangover. Smoothed input level is exposed to the visuals.
- **AudioPlayer**: PCM16 to AudioBuffer playback through a gain node and a 256-point
  analyser for live output level. A soft 220 Hz filler tone is available.
- **JitterBuffer**: per-`sync_id` segments played FIFO. Gated segments wait for
  `markRendered`, with the filler tone if rendering exceeds 1.5 s. A generation counter
  lets `reset()` cancel cleanly on barge-in.

### 5.4 Transport ([VoiceClient.ts](../fluid-buddha-sdk/src/transport/VoiceClient.ts))
Typed senders for every client message. Reconnects with exponential backoff (0.5–8 s, 4
retries), then reports `failed` and the SDK falls back to text mode.

### 5.5 HostBridge ([HostBridge.ts](../fluid-buddha-sdk/src/core/HostBridge.ts))
- Every command dispatches a `fluidbuddha:*` CustomEvent and then runs the default
  behaviour, unless a hook takes over.
- **Navigate**: `location.assign`.
- **Scroll**:
  - relative directions scroll by ±85 % of the viewport, or to top/bottom;
  - a section is found by exact id, then id substring, then heading text (fuzzy).
- **Persona**: sets `data-fb-persona` on `<html>` behind a **300 ms blurred cross-fade
  veil**. The veil is skipped under reduced motion.

### 5.6 Guided tour playback ([Tour.ts](../fluid-buddha-sdk/src/core/Tour.ts))
For each stop: send `say`, wait for `tour_done` (20 s safety cap), wait for playback to
drain, then move (navigate if the path differs, or scroll), with a 450 ms beat between
stops. The tour aborts on barge-in, a typed question, close, or stopping voice.

### 5.7 Generative component library (`src/ui/components/`)
All components are built from typed JSON with `textContent` or SVG nodes. The LLM never
sends HTML. Reveals are staggered in sync with speech.

| Component | Rendering | Interactivity | Reports state to agent |
|---|---|---|---|
| flowchart | vertical DOM nodes | — | — |
| workflow | horizontal steps with start/decision/end shapes and branch labels | — | — |
| component_diagram | SVG grid of glass boxes and arrows | — | — |
| graph | SVG circular node-link, directed arrows | — | — |
| chart | SVG bar / line (with area) / pie with legend | — | — |
| roi_calculator | 3 sliders, net value and ROI % (fixed $45/hour) | live recompute | **no** |
| table | comparison table | — | — |
| mind_map | radial SVG tree | expand/collapse, pan/zoom | expanded branches |
| timeline | SVG axis, alternating labels | hover tooltips | — |
| sankey | weighted bands, auto column inference, cycle guard | hover values | — |
| configurator | sliders / toggles / selects, formula outputs | live recompute | values on commit |
| scenario_simulator | sliders driving proportional bars | live recompute | values on commit |
| tabs | tabbed text | click | active tab |

`evalExpr` ([interactive.ts](../fluid-buddha-sdk/src/ui/components/interactive.ts)) is a
hand-written shunting-yard/RPN arithmetic evaluator supporting `+ - * / ( )` and
variables. It never uses `eval`. Pan/zoom and tooltips are shared helpers.

### 5.8 Design levels (three scales of one "Aura")
- **L1 · Companion** (default) ([FluidBuddhaElement.ts](../fluid-buddha-sdk/src/ui/FluidBuddhaElement.ts)):
  - a breathing 2D-canvas Aura launcher with magnetic cursor lean;
  - a 392×580 "molten obsidian" glass panel with gold light-seam, a living avatar, a
    status word, editorial message styling, a "grounded · NN %" badge, a thinking
    indicator, 3 suggestion chips, and a mic button with a reactive energy ring;
  - full-screen layout on mobile.

  States: dormant (gold), listening (silver), thinking (shimmer), speaking (bright).
- **AuraCanvas** ([AuraCanvas.ts](../fluid-buddha-sdk/src/ui/aura/AuraCanvas.ts)): 7
  orbiting light lobes and a core drawn with additive blending, a 5.5 s breath, live
  energy, state tints, and a static frame under reduced motion.
- **L2 · Presence** ([Level2Shell.ts](../fluid-buddha-sdk/src/ui/level2/Level2Shell.ts),
  [ParticleField.ts](../fluid-buddha-sdk/src/ui/particles/ParticleField.ts)):
  - full-viewport Three.js GPU smoke: 8k–16k particles, divergence-free curl-noise flow
    (custom GLSL simplex), buoyancy, a continuously mutating organic blob, and turbulence
    bursts on transitions;
  - energy driven by live audio; tinted gold for the agent and silver for the user;
  - an "Awaken" ring, a reactive halo, a fading 6-line message stack, and a centred glass
    drawing surface.

  Degrades gracefully without WebGL.
- **L3 · Atmosphere** ([Level3Shell.ts](../fluid-buddha-sdk/src/ui/level3/Level3Shell.ts)):
  - no widget; a breathing edge rim-light;
  - a **spotlight** that dims the page and rings whatever section the agent scrolls to;
  - ephemeral glass captions (14 s lifetime, at most 4);
  - a ⌘K / Ctrl-K or light-mote **summon** with an Aura orb and prompt.

  The overlay is pointer-transparent.

### 5.9 Extreme page renderer ([PageRenderer.ts](../fluid-buddha-sdk/src/ui/page/PageRenderer.ts))
- A full-screen surface themed by the fetched `--ds-*` tokens and brand name.
- Renders all 9 section types with staggered reveal.
- Enquiry forms are sent back to the agent as a typed message ("Please submit this enquiry
  using <op>: {json}"). CTAs scroll to the form.

### 5.10 Styling and accessibility ([styles.ts](../fluid-buddha-sdk/src/ui/styles.ts))
- ~790 lines of Shadow-DOM-scoped CSS behind `all: initial`.
- An accent-derived colour spectrum via `color-mix`, a film-grain overlay, and a
  glass-material system.
- Focus-visible rings, `prefers-contrast` and `prefers-reduced-motion` handling, ARIA
  labels, and safe-area insets.

### 5.11 Demos
`demo/index.html` is a fictional "Halden Instruments" host page with a level switcher and
`?open` / `?spotlight` flags. `demo/level2.html` and `demo/level3.html` demonstrate the
other two design levels.

---

## 6. Admin console: built functionality

| Page | Path | What works |
|---|---|---|
| Auth | `/login`, `/register` | Email/password, JWT in `localStorage`, `/auth/me` restore, redirect guards |
| Dashboard | `/dashboard` | Website cards (name, domain or key, intelligence and design badges, status). **Add website** modal (name, domain, intelligence, design L1/L2, accent picker) |
| Ingestion | `/websites/[id]/ingestion` | Stats, sources table (status, nodes, preview, error), upload (.txt/.md/.html/.csv/.json), add text or URL, delete, **Run ingestion** with short polling |
| Tour | `/websites/[id]/tour` | Stop editor (narration, move type and target), reorder, add, delete, save, **✨ Generate from content** |
| Responses | `/websites/[id]/cache` | Search, table of cached turns with persona/channel badges, served-from-cache hit count, edit answer and actions JSON, delete |
| Analytics | `/websites/[id]/analytics` | KPIs (total cost, turns, cache hit rate, p95/p50 latency), stacked cost by stage over day/hour/session, cost breakdown donut, generated-versus-cached donut |

Design: a hand-built dark design system ([globals.css](../fluid-buddha-frontend/src/app/globals.css)),
Space Grotesk / Hanken Grotesk / JetBrains Mono, toasts, modals and skeletons.

---

## 7. Intelligence tier matrix: what actually changes

| Capability | basic | high | advance | extreme |
|---|:-:|:-:|:-:|:-:|
| Text chat (WS or `/chat`) | ✅ | ✅ | ✅ | ✅ |
| Grounded answers (CORTEX) | ✅ | ✅ | ✅ | ✅ |
| Navigate / scroll | ✅ | ✅ | ✅ | ✅ |
| Spoken TTS output | ❌ (skipped server-side) | ✅ | ✅ | ✅ |
| Mic button in L1 | hidden | ✅ | ✅ | ✅ |
| Silent persona switch tool | ❌ | ✅ | ✅ | ✅ |
| Generated components | ❌ | ❌ | ✅ | ✅ |
| Runtime page generation | ❌ | ❌ | ❌ | ✅ |
| Site API calls | ❌ | ❌ | ❌ | ✅ if spec present |

The Fast Router can still emit a persona switch in `basic` (persona is applied in the loop,
not tool-gated). The tier is chosen **by the client** (§11.1).

---

## 8. End-to-end: one voice turn

1. The visitor speaks. VAD onset (180 ms) sends `AUDIO/start`, and chunks stream while
   speech continues. The Web Speech API builds the transcript in parallel.
2. After 850 ms of silence the client sends `AUDIO/end {transcript}`.
3. The server checks the cache. A strong match replays components and cached PCM, and the
   turn ends.
4. Otherwise the Fast Router returns intent, persona and ack. The thinker (lean or heavy)
   starts *concurrently* while the ack is synthesised and spoken.
5. On a persona switch the server sends `EVENTS/set_persona`, and the client cross-fades
   the host site's theme.
6. `DATA/render` components arrive and render. Each calls `markRendered(sync_id)`.
7. The answer's TTS streams sentence by sentence. The first segment is gated on its
   component, and later ones play FIFO.
8. Navigate / scroll events are applied. In L3 the spotlight lands on the referenced
   section.
9. The turn is recorded to the conversation cache and `usage_events` in the background.
10. If the visitor drags a slider, `component_state` triggers a debounced one-line spoken
    reaction.

---

## 9. Test suite (present, not executed in this review)

| Suite | Coverage |
|---|---|
| `backend/tests/test_backend.py` | Envelope shape, tool gating per tier, intelligence normalisation, design tokens, page normaliser, API registry simulate/reject, Extreme page generation versus advance gating, guardrail below threshold, `/chat` shape, WS synced audio, **live reaction**, TTS sentence split, hybrid routing, WS tour plan and say |
| `test_cache.py` | Question normalisation, audio-key stability, audio cache round-trip, exact replay and persona scoping, persona switch on explicit signal, end-to-end `/chat` replay |
| `test_admin.py` | Password hashing, register/login/me/duplicate, website CRUD and tenant isolation |
| `test_ingestion_admin.py` | Text and file sources, synchronous run, status counts, delete, isolation |
| `test_tour_admin.py` | Get/put/validate tour, generate before ingest (409), generate after ingest |
| `test_cache_admin.py` | Cache list, edit, search, delete, isolation |
| `test_analytics_admin.py` | Cost math, breakdown, cache split, hit rate 0.2, groupings, isolation |
| `fluid-buddha-sdk/test/smoke.mjs` | ~50 jsdom assertions: element and Shadow DOM, envelope routing, all 13 components, configurator recompute and state report, tier UI gating, L2/L3 mounting, Extreme surface, persona veil |
| `fluid-buddha-sdk/test/inject.mjs` | Single-`<script>` auto-injection |
| Admin console | **No tests** |

Backend integration tests need a live pgvector database, and some need HireBuddha already
ingested.

---

## 10. Documented or marketed but **not built**

| Claim (source) | Reality in code |
|---|---|
| CRM sync, "applicant answers mapped directly to sales pipelines" (marketing brief, case studies) | No CRM, webhook or lead object exists anywhere |
| PDF / site-map ingestion (technical spec §5) | Upload is UTF-8 text only. URL ingestion fetches one page, with no crawler |
| "Manually approve cached items" (technical spec §5) | Edit and delete only. There is no approval state |
| Tour "pauses to wait for the visitor to complete a form" (functional spec §5.5) | Not implemented |
| "Dynamically updates form options" (HireBuddha case study) | Not implemented |
| `DATA/patch` updates an active card (technical spec §3.2) | The `patch_component` tool is acked but **never emitted** to the client ([thinker.py:263](../backend/app/orchestrator/thinker.py)) |
| "Base bundle ~35 kB gzipped" for L1/L3 (implementation guide, product page) | Three.js is always bundled. The lazy import is only a suggestion |
| "Under 300 ms", "zero hallucinations guaranteed", "0 % across 15,000 queries", "2.4×", "74 %", "80 %", "48 %", "$4,200 saved" (website copy) | No measurement or attribution code backs these figures. Testimonials come from the house brand (Buddha Cognitive Lab) |
| Gemini 1.5 Flash/Pro (website copy, `.env.example`) | Code defaults are 2.5 Flash/Pro, with comments referencing 3.x |
| Dedicated DB per tenant, SOC2 routing, 99.9 % SLA, Vertex billing passthrough (pricing copy) | Not present |
| Admin can choose design Level 3 | The backend accepts only `level1`/`level2` ([websites.py:21](../backend/app/routes/websites.py)), and the UI offers only those two |
| Admin website settings drive the embedded agent | The SDK never fetches tenant config. Intelligence, design and accent come only from the script tag |

---

## 11. Known issues and risks found during the read

### 11.1 Security and abuse
1. **Public endpoints are unauthenticated and tier-unenforced.** `/ws/voice` and `/chat`
   accept any `site` and any `intelligence` from the client
   ([websocket.py:739](../backend/app/transport/websocket.py), [chat.py:47](../backend/app/routes/chat.py)).
   Any visitor can query any tenant's knowledge base, or upgrade themselves to `extreme`.
   There is no rate limiting, origin or domain allow-list, or widget key.
2. **Free TTS relay.** `EVENTS/tour_say` will synthesise any text the client sends
   ([websocket.py:244](../backend/app/transport/websocket.py)).
3. **SSRF.** URL sources are fetched server-side with redirects and no host filtering
   ([sources.py:195](../backend/app/tenancy/sources.py)).
4. **Path injection.** `call_site_api` substitutes path parameters without URL-encoding
   ([registry.py:125](../backend/app/apis/registry.py)).
5. **Secrets and config.**
   - The JWT secret has a hard-coded default ([config.py:71](../backend/app/config.py)).
   - Compose defaults `CORS_ORIGINS` to `*` with credentials.
   - A real-looking GCP project ID is committed in [.env.example:30](../backend/.env.example).
   - The admin JWT is kept in `localStorage`.
6. **Privacy.**
   - Enquiry-form data (including personal details) is sent through the LLM as free text
     and recorded in the replay cache ([FluidBuddhaElement.ts:154](../fluid-buddha-sdk/src/ui/FluidBuddhaElement.ts)).
   - Cached answers are replayed across visitors.
   - There is no consent prompt for recording or microphone use.
7. **Remote images.** The `media` page section loads any URL the model supplies
   ([PageRenderer.ts:170](../fluid-buddha-sdk/src/ui/page/PageRenderer.ts)).

### 11.2 Multi-tenancy correctness (high impact)
1. **The brain is HireBuddha-specific.**
   - Router and Thinker prompts say "Pragya … on the HireBuddha website"
     ([prompts.py:9](../backend/app/orchestrator/prompts.py)).
   - The 4 personas are HireBuddha's ICPs ([personas.py:10](../backend/app/orchestrator/personas.py)).
   - The tour planner's closing use-case stop and its fallback copy talk about HireBuddha
     hiring automation ([tour.py:93](../backend/app/orchestrator/tour.py)).

   Every tenant inherits this.
2. **Navigation is impossible on tenant sites.** Only `hirebuddha` has a sitemap
   ([sitemap.py:52](../backend/app/orchestrator/sitemap.py)), so `resolve_route` returns
   `None` and every `navigate` call is dropped for all other sites.
3. **Generated tours cover only one page for tenant sites.** Tenant sources have
   `route=None`, so they collapse to "/", and `_page_catalog` de-duplicates by route
   ([tour.py:113](../backend/app/orchestrator/tour.py)).
4. **Re-ingesting overwrites the tour, including manual edits.** It is planned only from
   the *newly ingested* batch ([sources.py:220](../backend/app/tenancy/sources.py)).
5. **Knowledge cannot be removed.**
   - Deleting a source deletes the row but leaves its CORTEX nodes.
   - Deleting a website leaves its tree, cache, tours and usage behind.
   - The replay cache is never invalidated when content changes, so stale answers keep
     replaying.
6. The cache `query()` accepts `page` but ignores it ([episodic.py:234](../backend/app/cortex/episodic.py)),
   so a page-specific answer ("what's on this page?") can replay on another page.

### 11.3 Functional bugs and quality
- **First syllable lost for server ASR.** Mic chunks are sent only after VAD onset, so the
  first ~180 ms of speech are dropped ([Session.ts:243](../fluid-buddha-sdk/src/core/Session.ts)).
  This matters only when server ASR is used.
- **TTS is not truly streamed.** `GeminiTTS` synthesises each segment fully, then chunks
  it ([vertex.py:301](../backend/app/ai/vertex.py)).
- `thinking_budget=1` on the heavy model ([thinker.py:130](../backend/app/orchestrator/thinker.py))
  may be rejected by models that cannot disable thinking. Verify against the chosen model.
- **Retrieval ignores history.** It uses the raw utterance with no query rewriting, so
  follow-ups like "and for enterprise?" retrieve poorly.
- **The ROI calculator is weak.** It uses a fixed $45/hour, ignores `seats`, and never
  reports state, so the most common component gets no live reaction.
- **L2 cannot be reopened** after its close button is pressed
  ([Level2Shell.ts:316](../fluid-buddha-sdk/src/ui/level2/Level2Shell.ts)).
- **Deprecated and inefficient audio plumbing.** `ScriptProcessorNode` is deprecated, and
  audio travels as base64 inside JSON, adding ~33 % overhead.
- **Analytics are approximate.** ASR is estimated from transcript length, and TTS
  characters are billed even when cached PCM is replayed. Recorded tour stops always store
  `move=None`.
- **Single-node assumptions.**
  - Sessions are in-process and never evicted ([session_store.py](../backend/app/transport/session_store.py)).
  - Every request runs `CREATE TABLE IF NOT EXISTS`, and there are no migrations.
  - `/tour/generate` builds new engine clients on every call.
- **Language is hard-coded** to en-US, for both Web Speech and ASR.
- **Admin UX gaps.**
  - No website edit or delete UI, even though the API supports both.
  - **No embed snippet** is shown, so a tenant cannot see how to install the agent.
  - No date-range picker on analytics.
  - The cache editor cannot edit components or the question.
  - The tour editor drops `label`.
  - "Knowledge nodes" actually shows the document count.

### 11.4 Developer experience and ops drift
- **Port mismatches.**
  - The console runs on port 3002 ([package.json:6](../fluid-buddha-frontend/package.json)),
    but CORS and the README use 3001.
  - The console `.env.example` points at 8081, while the backend runs on 8080.
  - SDK demos L2/L3 use 8081, while the index demo uses 8080.
- **Seed paths point at folders that don't exist.**
  - Compose mounts `../../hirebuddha-website`, but the sibling folder is named
    `hire-buddha-website`.
  - `../fluidbuddha-website` does not exist.
  - The loader's default root is `fluid-buddha/`.

  As a result, first-boot seeding finds no documents in this layout.
- **Naming is inconsistent**: flUIdBuddha, Fluid-Buddha and fluid-buddha are all used, and
  the agent appears as both Pragya and Halden in the demo. Default accent colours also
  differ (`#c9a24a` in the SDK, `#ffd23f` in the console).
- `docs/website-copies/*` are deleted in the working tree but not committed.
- The `Geist` font is referenced but never loaded.

---

## 12. Bottom line

| Area | Score (1–5) | Notes |
|---|:-:|---|
| Voice and conversation engine | 4.5 | Latency overlap, hybrid routing, barge-in, sync, caching. Production-grade thinking |
| Grounding and safety | 3.5 | Real guardrail and normalisers. History-blind retrieval, no citations shown |
| Generative UI | 4 | 13 safe components, 3 design levels, interactive state loop |
| Multi-tenancy | 2 | CRUD and isolation work. The brain, sitemap, personas and tier enforcement are not tenant-aware |
| Security and compliance | 1.5 | Public endpoints open, SSRF, no rate limits, no consent |
| Revenue features (lead, CRM, booking) | 0.5 | Only a simulated enquiry path |
| Admin console | 3 | Clean MVP. Missing install snippet, settings and insights |
| Ops and scale | 2 | Docker works. Single-node session state, no migrations, no observability |

The engine is ahead of the product around it. The next step is less about inventing new
AI and more about **tenant-izing the brain, locking down the public surface, and
connecting conversations to revenue**. The companion roadmap
([roadmap.md](./roadmap.md)) covers this.
