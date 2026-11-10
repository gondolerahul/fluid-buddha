# FluidBuddha — Technical Specification (version 1.0)

> **Basis.** Reverse-engineered from the code on branch `m2/foundations` (commit `12e325e`,
> 6 November 2026). File paths are relative to the repository root. Values are the coded
> defaults unless stated otherwise.
>
> **Companion documents:** [FeatureList.md](FeatureList.md) and
> [FunctionalSpecification.md](FunctionalSpecification.md) (requirement IDs `FR-…` are
> referenced here where useful).

---

## Table of contents

1. [System overview](#1-system-overview)
2. [Repository layout](#2-repository-layout)
3. [Technology stack](#3-technology-stack)
4. [Backend architecture](#4-backend-architecture)
5. [The agent pipeline](#5-the-agent-pipeline)
6. [AI engine layer](#6-ai-engine-layer)
7. [Knowledge and grounding (CORTEX)](#7-knowledge-and-grounding-cortex)
8. [Real-time transport protocol](#8-real-time-transport-protocol)
9. [HTTP API reference](#9-http-api-reference)
10. [Data model](#10-data-model)
11. [Widget SDK architecture](#11-widget-sdk-architecture)
12. [Admin console architecture](#12-admin-console-architecture)
13. [Install integrations](#13-install-integrations)
14. [Security architecture](#14-security-architecture)
15. [Privacy engineering](#15-privacy-engineering)
16. [Multi-tenancy and isolation](#16-multi-tenancy-and-isolation)
17. [Background jobs](#17-background-jobs)
18. [Observability](#18-observability)
19. [Reliability and scaling](#19-reliability-and-scaling)
20. [Deployment](#20-deployment)
21. [Configuration reference](#21-configuration-reference)
22. [Testing and quality gates](#22-testing-and-quality-gates)
23. [Statistics and algorithms](#23-statistics-and-algorithms)
24. [Known technical limitations and risks](#24-known-technical-limitations-and-risks)

---

## 1. System overview

```
 Customer website (any stack)                               FluidBuddha backend (FastAPI, Python 3.12)
┌──────────────────────────────────────┐   WS /ws/voice    ┌────────────────────────────────────────────┐
│ /widget/loader.js → fluid-buddha.js  │◄─────────────────►│ VoiceSession (one per socket)              │
│ <fluid-buddha> Web Component         │ JSON envelopes +  │  PII mask → language → intents → replay?   │
│  Session ─ VoiceClient               │ binary PCM frames │  FastRouter (ack) ║ Lean / HeavyThinker   │
│  AudioCapture → SpeechGate (VAD)     │                   │  sentence TTS (+audio cache) → record      │
│  JitterBuffer → AudioPlayer          │  POST /chat       │ Text path (/chat) – same CognitiveLoop     │
│  HostBridge (navigate/scroll/persona)│◄─────────────────►│                                            │
│  Canvas (13 components + embeds)     │  /experiment,     │ Public APIs: widget, leads, recap, actions,│
│  Level 1/2/3 shells, PageRenderer    │  /widget/triggers,│  memory, triggers, experiments, campaigns, │
│  Triggers, Experiment, Live (WebRTC) │  /leads, /recap…  │  MCP/agent, status                         │
└──────────────────────────────────────┘                   │                                            │
                                                           │ Console API (/auth, /tenant/…)             │
 Admin console (Next.js 16 / React 19) ── cookie+CSRF ────►│  roles, audit, licence guard               │
   WS /tenant/live/events (live inbox)                     │ Scheduler (advisory-locked jobs)           │
                                                           └───────────┬──────────────┬─────────────────┘
                                                                       ▼              ▼
                                         Postgres 16 + pgvector (CORTEX trees,    Redis (optional):
                                         app tables, 31 Alembic migrations)       sessions, rate limit,
                                                                                  live event relay
            Vertex AI: Gemini fast + heavy, text-embedding-004 (768-d), Gemini TTS, Cloud Speech-to-Text
            Optional per account: Anthropic / OpenAI / Azure OpenAI (LLM only)
            Razorpay (billing + tenant payment links) · SMTP · Slack/webhooks · coturn (TURN) · OTLP · Sentry
```

Three deployable applications:

| App | Folder | Runtime | Port |
|---|---|---|---|
| Backend ("A2UI Orchestrator") | `backend/` | Python 3.12, FastAPI + uvicorn | 8080 |
| Widget SDK | `fluid-buddha-sdk/` | Static JS bundles (served from `WIDGET_SDK_BASE`, e.g. Caddy `/sdk/`) | — |
| Admin console | `fluid-buddha-frontend/` | Node 24, Next.js 16 standalone | 3001 (dev) / 3000 (container) |

---

## 2. Repository layout

```
backend/
  app/
    actions/        confirmable actions: fields, store, run, PDF, voice yes/no
    agents/         agent endpoint: MCP server, tools, tokens/traffic store
    ai/             engine interfaces; Vertex, Anthropic, OpenAI, mock; RoutingLLM
    analytics/      pricing model, usage events + rollups, cost alerts
    apis/           per-site OpenAPI registry (Extreme tier)
    audit.py        audit log + middleware
    auth/           passwords/JWT, sessions, MFA, roles, team, SSO
    billing/        plans, Razorpay client, billing store/rules
    campaigns/      landing-page composer, renderer, store
    cortex/         CORTEX bridge, query + guardrail, episodic cache, purge
    design/         design-system loader
    experiments/    holdout + variant tests, stats, bot filter
    i18n/           language detection, fixed strings
    insights/       conversation store, classification
    integrations/   GTM template generator
    jobs/           scheduler + job list
    leads/          lead store, scoring, delivery
    licence/        offline licence + guard middleware
    live/           live bus, presence/takeover store, TURN creds, visitor side
    memory/         returning-visitor memory
    notify/         email outbox, templates, digest, access review
    observability/  request context, metrics, tracing, Sentry, health
    onboarding/     crawler, HTML/PDF/DOCX extraction, design + persona derivation, jobs
    orchestrator/   cognitive loop, router, lean, thinker, tools, prompts, profile,
                    personas, sitemap, state, components, custom components, pagegen,
                    rewrite, tour planner/store
    recaps/         recap store, page renderer, intent
    routes/         HTTP/WS routers (34 modules)
    security/       security headers, secret encryption
    status/         status page store + renderer
    templates/      vertical template packs (YAML) + apply
    tenancy/        tenants/websites store, sources, SSRF-safe fetch, public access
    transport/      voice WebSocket, envelope, guard, session store, audio cache, drain
    trust/          PII, privacy settings, retention, medical safety
    config.py db.py main.py runtime.py shared_state.py cors.py logging_config.py
  migrations/       Alembic (0001–0031)
  ingestion/        CLI + markdown loader
  loadtest/         voice load test
  evals/            Hindi retrieval and voice evaluations
  scripts/          smoke tests, backup, restore drill, licence tool
  tests/            46 pytest modules (~290 tests)
fluid-buddha-sdk/   src/{audio,core,transport,ui,i18n}, demo/, test/
fluid-buddha-frontend/  src/{app,components,lib}
integrations/       wordpress, shopify, gtm, webflow, framer, js/{react,vue}
deploy/selfhost/    compose, Caddyfile, bin/*.sh, web.Dockerfile
deploy/monitoring/  prometheus.yml, alerts.yml
docs/compliance/    SOC 2 control matrix and policies
docs/operations/    incident runbook, SLA
```

---

## 3. Technology stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI ≥ 0.115, uvicorn[standard], websockets, pydantic v2, pydantic-settings |
| Database | PostgreSQL 16 with pgvector; SQLAlchemy 2 async + asyncpg; Alembic migrations |
| Knowledge engine | `hb-cortex-memory` 0.1.0 (KnowledgeTreeService, EpisodicTreeService) |
| LLM (platform) | Google Gen AI SDK on Vertex AI: `gemini-2.5-flash` (fast), `gemini-2.5-pro` (heavy) |
| Embeddings | `text-embedding-004`, 768 dimensions (fixed by the CORTEX schema) |
| Speech-to-text | Google Cloud Speech-to-Text v1 streaming (LINEAR16, 16 kHz) |
| Text-to-speech | Gemini native TTS `gemini-3.1-flash-tts-preview`, voice `Aoede`, PCM16 24 kHz; Cloud TTS Neural2 as legacy fallback |
| BYO LLM | `anthropic` ≥ 2.5, `openai` ≥ 3.46 (OpenAI and Azure OpenAI) |
| Auth and crypto | PyJWT (HS256), bcrypt, cryptography (Fernet, Ed25519, OIDC signature verification) |
| HTTP client | httpx |
| Cache / pub-sub | redis-py asyncio (optional) |
| Documents | pypdf; DOCX via standard-library XML |
| Observability | prometheus-client; OpenTelemetry SDK + OTLP/HTTP exporter; sentry-sdk |
| Other | PyYAML, tzdata, email-validator |
| Widget | TypeScript, Web Components + Shadow DOM, Web Audio (AudioWorklet), 2D canvas, Three.js (Level 2 only), esbuild |
| Console | Next.js 16.4, React 19.2, recharts, qrcode |
| Integrations | PHP (WordPress), Liquid (Shopify theme app extension), TypeScript (React/Vue/Framer) |
| Edge | Caddy 2 (TLS, routing, static SDK) |
| Voice relay | coturn 4.6 (`use-auth-secret`) |
| Payments | Razorpay REST API (subscriptions, add-ons, payment links, webhooks) |

---

## 4. Backend architecture

### 4.1 Application start-up (`app/main.py`)

1. Load settings (`app/config.py`), configure logging (text or JSON), optional Sentry and
   OpenTelemetry.
2. Lifespan:
   - `init_db()` runs `alembic upgrade head` inside a transaction (migrations take an advisory
     lock, so several replicas can start at once);
   - `build_runtime()` builds the AI engines, CORTEX providers and the `CognitiveLoop`;
   - start the job scheduler;
   - install the SIGTERM/SIGINT drain hook.
3. Shutdown: drain voice sessions (up to `DRAIN_SECONDS`), stop the scheduler, dispose of the
   engine.

### 4.2 Middleware stack (outermost first)

| Middleware | Responsibility |
|---|---|
| `ObservabilityMiddleware` | Request id (sanitised caller `X-Request-ID` or new), `X-Request-ID` response header, per-route HTTP metrics, request span, open-WebSocket gauge. |
| `AuditMiddleware` | Records successful (2xx) non-GET `/tenant/*` requests by a signed-in member to `audit_events`. |
| `SecurityHeadersMiddleware` | `nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY` + `frame-ancestors 'none'`, `Cache-Control: no-store` on `/auth` and `/tenant`, HSTS outside development. Headers set by a route are kept. |
| `ScopedCORSMiddleware` | Two CORS policies by path: `CORS_ORIGINS` for public widget paths, `ADMIN_CORS_ORIGINS` for `/auth` and `/tenant`. `*` becomes an any-origin regex with credentials off. Exposes `X-Request-ID`. |
| `LicenceGuard` | Only when `SELF_HOSTED=true`: refuses `/tenant` changes with 402 when the licence is unusable or the feature is unlicensed. Inside CORS so refusals carry CORS headers. |

### 4.3 Runtime singletons (`app/runtime.py`)

`Runtime` holds `settings`, `engines` (llm, asr, tts), CORTEX `providers` and the `loop`. It
creates per-request objects: `bridge(session, site_key)` (knowledge search),
`episodic(session, site_key)` (answer cache) and `audio_cache(session)`.

### 4.4 Database access (`app/db.py`)

One async engine (`pool_pre_ping=True`) and `async_sessionmaker`. `session_scope()` commits on
success and rolls back on error. All application SQL is raw parameterised SQL through
`sqlalchemy.text`. Schema changes are made only in migrations; a test enforces that no DDL lives
in application code.

### 4.5 Module dependency rules

- `orchestrator/*` depends only on `ai/base` interfaces, CORTEX and the profile cache. Prompt
  builders are synchronous and read in-process caches (`profile_for`, `components_for`,
  `actions_for`, design cache). Request entry points warm them first (`ensure_profile`,
  `ensure_design`, `ensure_extras`), with a 30 s TTL.
- Per-site BYO routing uses a context variable (`app.ai.providers.current_site`) set at every
  entry point (socket connect, `/chat`, recap, tour planning, classification, campaigns, agent
  endpoint).
- Optional dependencies (Google SDKs, OpenTelemetry, Sentry, Redis) are imported lazily, so mock
  mode and CI need none of them.

---

## 5. The agent pipeline

### 5.1 Conversation state (`orchestrator/state.py`)

`ConversationState` fields: `site_key`, `persona`, `intelligence`, `page`, `viewport`,
`sections` (up to 40 `{id, label}`), `history` (last 12 user/model pairs), persona confidence,
probe counter, lock flag, `components` (last 8, `sync_id → {component_type, state}`), `pii`
(`PiiVault`), `live_seen`, language fields (`lang`, `lang_seen`, `lang_pref`, `ui_lang`,
`used_hindi`), `visitor_id` and `memory_loaded`. It serialises to JSON for Redis (`to_dict` /
`from_dict`). The voice socket keeps state on the connection. `/chat` uses the session store.

### 5.2 Cognitive loop (`orchestrator/loop.py`)

```
route(text)            → FastRouter: {intent, persona, persona_confidence, persona_explicit, ack, query_en}
apply_persona(...)     → switch ≥ 0.6; explicit locks; locked needs explicit or ≥ 0.9; thinker set_persona = 0.8
should_probe(state)    → not locked ∧ (persona unknown ∨ conf < 0.5) ∧ turns_since_probe ≥ 3
needs_heavy(text, intent, has_components)
think_lean(...)        → LeanResponder
think(...)             → HeavyThinker
react(entry)           → one-sentence reaction (fast model, 80 tokens)
welcome(state)         → HeavyThinker with a greeting directive
run_turn(...)          → the synchronous HTTP version of the whole turn
```

### 5.3 Fast Router (`orchestrator/router.py`)

- Model: `FAST_MODEL`, temperature 0.2, max 120 output tokens (240 when the visitor wrote Hindi
  or Hinglish, or the reply is Hindi).
- The system prompt asks for JSON only. Optional `query_en` (an English search query) is added
  for non-English turns, and a Hindi acknowledgement for Hindi replies.
- Tolerant JSON extraction (strips code fences, takes the outermost `{…}`). Invalid personas are
  dropped and confidence is clamped to 0–1. On failure the acknowledgement falls back to
  `i18n.say("ack")`.

### 5.4 Lean responder (`orchestrator/lean.py`)

- `needs_heavy`: heavy intents (`pricing_roi`, `integration`, `navigation`), the heavy keyword
  regex, the correction regex while a component is on screen, or an email (or `<EMAIL_n>`)
  placeholder.
- Lean turn: retrieval query = router `query_en`, else `rewrite.retrieval_query(text, history)`;
  `query_cortex(top_k=5, threshold=0.45)`; one `generate` with `build_lean_system` (snippets
  injected), fast model, temperature 0.5, 400 tokens, `thinking_budget=0`. Empty output falls
  back to `say("lean_found" | "lean_missing")`.
- Tokens are taken from provider usage, or estimated at 4 characters per token.

### 5.5 Heavy thinker (`orchestrator/thinker.py`)

- Loop of at most `_MAX_TURNS = 4` model calls with tools (`HEAVY_MODEL`, temperature 0.5, 1,024
  tokens, `thinking_budget=1`).
- `_MAX_CORTEX = 1`: after one `query_cortex` the tool is removed from the offered set, and
  further calls are answered `{"ok": false, "note": "Search budget reached…"}`. A round with
  only refused searches ends the loop.
- Text is captured from every round (Gemini can bundle the answer with tool calls). If no text,
  a forced round with a nudge (512 tokens, `thinking_budget=0`), then a fixed fallback.
- The model's tool-call turn is replayed in history before its results (`ChatMessage(role=
  "model", tool_calls, raw)`), as Vertex, Claude and OpenAI require.
- Tool handling:

| Tool | Server action | Result to model |
|---|---|---|
| `query_cortex` | Retrieval; sets `result.grounding` | snippets, confidence, found, guardrail |
| `render_component` | `normalize_component` (custom components validated/expanded); new `ui_<hex10>` sync id | `{ok, sync_id}` or props error with hint |
| `patch_component` | Only sync ids in ON-SCREEN COMPONENTS; non-empty patch; animation ∈ fade/count_up/highlight | `{ok, target_sync_id}` / `unknown_sync_id` |
| `navigate` | `resolve_route`; dropped if invalid | `{ok}` / `invalid_route` with hint |
| `scroll_to` | direction or section id | `{ok}` |
| `set_persona` | only site personas | `{ok}` |
| `generate_page` | `normalize_page` (≤ 12 known sections); `page_<hex10>` id | `{ok, sync_id, section_count}` |
| `call_site_api` | `SiteApis.call(operation_id, params)` (declared ops only; simulated without base URL or in mock mode) | API response |
| `capture_lead` | PII unmasked; `LeadIn.cleaned()` | `{ok, note}` / validation error |
| `action_<name>` | PII unmasked; `validate_inputs(fields, args)`; one proposal per action per turn | `{ok, status: "waiting_for_the_visitor", note}` |

### 5.6 Tools by tier (`orchestrator/tools.py`)

```
basic   = query_cortex, navigate, scroll_to, capture_lead               + action tools
high    = basic + set_persona (enum = site personas; dropped if none)   + action tools
advance = high + render_component (+ site custom components) + patch_component + action tools
extreme = advance + generate_page + call_site_api (only if the site has OpenAPI operations) + action tools
```

Action tools are one `ToolSpec` per enabled site action, with a JSON schema built from the
action's fields. Payment-link descriptions list the price keys and amounts.

### 5.7 Prompt assembly (`orchestrator/prompts.py`)

| Prompt | Parts (in order) |
|---|---|
| Router | Template (agent, company, intents, persona rule with allowed slugs, ack rule) + `query_en` rule + Hindi ack rule |
| Thinker | Identity + grounding rules + interaction rules + page-awareness rules; `CONTEXT: site, persona fragment`; capability fragment for the tier; site rules (guardrails, lead fields, preferred components); page fragment; scroll targets; related past answers (up to 3); persona probe; Extreme brief (design system, section catalogue, site APIs); valid routes; language fragment ("write query_cortex queries in English"); on-screen components block when patching is available |
| Lean | Identity; persona fragment; site rules (no components); page fragment; related past answers; probe; context snippets; language fragment |
| Reaction | Agent, company, component type and state (≤ 500 chars JSON), "one sentence or empty", persona, Hindi instruction |
| Tour planner | Tour director instructions (6–9 stops, scroll/navigate moves, use-case close) + tour outline |

### 5.8 Agent profile (`orchestrator/profile.py`)

Stored as JSONB in `site_profiles` keyed by `site_key`, overlaid on a default (HireBuddha's
built-in profile for `hirebuddha`, otherwise a neutral profile named after the website). All
fields are cleaned on load (lengths, counts, https-only CTA, ISO currency, known components).
Cached in-process with a 30 s TTL (`remember`, `invalidate`, `ensure_profile`).

### 5.9 Supporting modules

| Module | Function |
|---|---|
| `components.py` | `KNOWN_COMPONENTS` (13); unknown → `table`; lists capped at 48; money components get the profile currency. |
| `custom_components.py` | Schema validation (`clean_schema`, `validate_props`), template expansion (`{{prop}}` placeholders), iframe → `embed` component; registry per site in `site_components`. |
| `pagegen.py` | `SECTION_TYPES` (14), `normalize_page`, `build_extreme_brief`. |
| `rewrite.py` | Follow-up detection and retrieval query expansion; `depends_on_history`. |
| `sitemap.py` | Route normalisation, validation, fuzzy snapping (`difflib`, cutoff 0.82), unique-leaf snapping, `sitemap_prompt`, `route_from_url`. |
| `tour.py` / `tour_store.py` | Planner with page catalogue (≤ 14 pages), JSON extraction, deterministic fallback; `site_tours(plan, edited)`. |
| `personas.py` | HireBuddha personas; `valid_personas`, `persona_fragment`. |
| `result.py` | `ClientAction`, `ComponentPayload`, `PageSpec`, `Grounding`, `ComponentPatch`, `TurnResult` (and `to_message_dict` for `/chat`). |

---

## 6. AI engine layer

### 6.1 Interfaces (`ai/base.py`)

```python
LLMClient.generate(system, messages, tools?, model?, temperature, max_output_tokens?, thinking_budget?) -> LLMResponse
LLMClient.generate_stream(system, messages, model?, temperature, max_output_tokens?) -> AsyncIterator[str]
ASREngine.transcribe_stream(audio: AsyncIterator[bytes], languages) -> AsyncIterator[TranscriptEvent]
TTSEngine.synthesize_stream(text, language) -> AsyncIterator[bytes]   # PCM16 frames; .sample_rate
```

`ChatMessage(role ∈ user|model|tool, text, tool_name, tool_result, tool_calls, raw)`;
`ToolCall(name, args, thought_signature, id)`; `LLMResponse(text, tool_calls, model,
finish_reason, input_tokens, output_tokens, provider, raw)`.

### 6.2 Engine selection (`ai/factory.py`)

- `MOCK_AI=true` (default): `MockLLMClient` (deterministic: the router uses keywords; the
  thinker grounds in round 1, acts in round 2 and speaks in round 3), `MockASR` (empty; the
  client transcript is used), `MockTTS` (silence sized to the text).
- Otherwise `VertexLLMClient`, `VertexASR`, `GeminiTTS`.
- The LLM is always wrapped in `RoutingLLM`.

### 6.3 Vertex engines (`ai/vertex.py`)

- **LLM**: `google.genai.Client(vertexai=True)`. Consecutive tool results are merged into one
  tool turn (Gemini needs as many function responses as calls). Gemini 3.x thought signatures
  are replayed. Automatic function calling is disabled. `thinking_budget` maps to
  `ThinkingConfig`. Thought parts are skipped. Usage metadata gives token counts.
  `vertex_model_id` strips a `google/` prefix.
- **Embedder**: `embed_content` with `output_dimensionality=768`.
- **ASR**: streaming recognise, LINEAR16, 16 kHz, primary language plus up to 3 alternatives,
  automatic punctuation, interim results, per-result language code.
- **TTS**: `generate_content_stream` with `response_modalities=["AUDIO"]`, prebuilt voice,
  optional `language_code`. Falls back to a one-shot call if streaming fails before any audio.
  `PcmFramer` cuts output into ~200 ms frames (`rate × 2 / 5` bytes), strips a RIFF header and
  never splits a sample.

### 6.4 Bring-your-own-model routing (`ai/providers.py`)

- `config_for_site(site_key)`: `model_providers` joined to `tenant_websites` where
  `byo_model` and `enabled`. The API key is decrypted. Results are cached per site for 60 s;
  clients are cached per `(tenant_id, updated_at)`.
- Model mapping: a request for `HEAVY_MODEL` uses the account's thinker model; anything else
  uses the fast model.
- On any provider exception: log, store `last_error` on the provider, strip provider-native
  `raw` turns, and call the platform engine.
- `LIST_PRICES` (USD per 1M tokens): `claude-fable-5-1` 10/50, `claude-opus-5-5` 4/20,
  `claude-opus-5` 5/25, `claude-sonnet-5-5` 2/10, `claude-sonnet-5` 2/10, `claude-haiku-5-5`
  0.10/0.50. Account prices per role override them.

### 6.5 Anthropic client (`ai/anthropic_llm.py`)

- No sampling parameters are sent. Depth uses `output_config.effort` (`low` for quick calls,
  `medium` otherwise). Quick calls disable thinking on Haiku 5.x (`disabled`) and use
  `between_tools` on Sonnet 5.5. Opus 5.5 and Fable always think, so `max_tokens` has a floor of
  2,048.
- History conversion (`to_messages`): alternating user/assistant turns; tool results grouped in
  one user message and matched to `tool_use` ids (synthetic ids where needed); a tool-calling
  assistant turn's content blocks (thinking included) are replayed verbatim from `raw`.
- `stop_reason == "refusal"` → empty text with `finish_reason="refusal"`. Server-side fallback
  (beta `server-side-fallback-2026-07-01`, `fallbacks: "default"`) on Fable 5.1, Opus 5.5, Opus 5
  and Sonnet 5.5.
- `check(model)` is used by "Test connection".

### 6.6 OpenAI / Azure OpenAI client (`ai/openai_llm.py`)

Chat Completions with function tools. Azure uses `endpoint` + `api_version` and deployment names.
A request refused for `max_completion_tokens` is retried with `max_tokens`; one refused for
`temperature` (reasoning models) is retried without it.

---

## 7. Knowledge and grounding (CORTEX)

### 7.1 Knowledge trees

- `CortexBridge` wraps `cortex_memory.KnowledgeTreeService` with company id
  `CORTEX_COMPANY_ID` and the site's entity id `uuid5(a2a2a2a2-…-a2a2, site_key)`.
- Ingestion: `ingest_document(tree_id, document_id, content, filename, entity_id)` builds
  DOCUMENT → SECTION → CHUNK nodes with 768-d embeddings in `cortex_nodes` (and
  `cortex_edges`). Tenant sources use their own id as `document_id`, so their nodes can be
  deleted precisely (`source_ref->>'document_id'`).
- Provider adapters (`cortex/providers.py`) plug the Vertex embedder and LLM into CORTEX, or the
  reference hash embedder in mock mode.

### 7.2 Retrieval and guardrail (`cortex/query.py`)

```
rows = bridge.search(query, top_k)
snippets = [{text, score, document, section, filename}]
confidence = snippets[0].score
found = confidence ≥ threshold (0.45)
result = {query, found, confidence, snippets if found else snippets[:2], guardrail if not found}
```

`citations(snippets)` → one entry per source (filename or document), with `document`, `section`,
`score`, a readable `label` (leading icons, numeric prefixes and extensions stripped; URL leaf)
and `route` (from the URL, or from the markdown filename mapping in `ingestion/scraper.py`).

### 7.3 Ingestion paths

| Path | Code | Notes |
|---|---|---|
| Console sources | `tenancy/sources.py` → `ingestion.ingest.ingest_documents` | Text, URL (SSRF-safe fetch, HTML stripped; PDFs read but not routed), files (PDF/DOCX/text). Marks status and node counts, merges routes into the profile, replans the tour unless edited, invalidates caches. |
| Crawl job | `onboarding/jobs.py` | Crawl → `upsert_url_source` per page → ingest with prefetched text → personas → design. Progress in `crawl_jobs`. |
| CLI | `python -m ingestion.ingest --site X [--reset|--if-empty]` | Loads markdown copy from configured content folders (`*_CONTENT_DIR`), prefixes each document with `[Page: /route]`, plans the tour. |

### 7.4 Answer cache (`cortex/episodic.py`)

- Table `conversation_cache(id, site_key, persona, page, kind ∈ turn|tour_stop, q_norm, question,
  answer_text, components, actions, channel, embedding vector(768), grounding, lang, status ∈
  auto|pinned|blocked, hit_count, created_at)`.
- `q_norm` = lower-cased question with whitespace collapsed.
- `record`: skipped if a curated (non-auto) row exists for the same `q_norm` and language.
  Also writes a best-effort episode to the CORTEX episodic tree (month → day → episode).
- `query`: exact `q_norm` match (pinned first, then persona-compatible), else cosine similarity
  `1 - (embedding <=> :vec)` within the site, persona and language, excluding blocked rows.
- Thresholds are applied by the caller (§5 of the functional spec, FR-CCH-03).

### 7.5 Audio cache (`transport/answer_audio.py`)

`answer_audio_cache(text_hash PK, site_key, sample_rate, pcm bytea)`;
`text_hash = sha256("{voice}[@{lang}]|{rate}|{normalised text}")`. Insert-or-ignore; failures
never break speech.

### 7.6 Purge (`cortex/purge.py`)

- `delete_document_nodes(site, document_id)`.
- `invalidate_site_caches(site)`: delete `auto` cache rows and all audio for the site.
- `purge_site(site)`: delete the CORTEX tree (nodes and edges cascade) and every row keyed by the
  site in 26 per-site tables (child tables cascade).

---

## 8. Real-time transport protocol

### 8.1 Endpoint

`WS /ws/voice?key=<fbk_…>&site=<demo site>&intelligence=<tier>&audio=binary&visitor=<id>`

1. `resolve_public_site(key, site, intelligence, Origin)`. On failure: accept, send
   `EVENTS/error {reason}`, close **4403**.
2. Warm profile, design and site extras (actions and components).
3. If the replica is draining: send `EVENTS/reconnect`, close **1013**.
4. Load privacy settings, create the `PiiVault`, recognise the visitor's memory, send
   `EVENTS/ready`, announce presence, start the live listener and a 30 s heartbeat.

### 8.2 Envelope

```json
{ "channel": "AUDIO|DATA|EVENTS|STATE", "type": "…", "payload": {}, "sync_id": "ui_ab12cd34ef", "timestamp": 1730860000000 }
```

Binary audio frame (both directions when `audio=binary` and `ready.config.audio_frames ==
"binary"`):

```
byte 0      0x01 (AUDIO_CHUNK)
byte 1      N = length of sync_id (0–255)
bytes 2..   sync_id (ASCII), then PCM16 little-endian mono
```

Sync id prefixes: `ack_`, `ui_`, `page_`, `utt_`, `welcome_`, `tour_`, `react_`, `evt_`.
Audio whose segment id begins `ui_` is held by the widget until that component has rendered.

### 8.3 Client → server messages

| Channel / type | Payload | Handling |
|---|---|---|
| `AUDIO/start` | — | Reset utterance buffer (dropped before consent or during a call). |
| `AUDIO/chunk` | `{data: base64 PCM16 16 kHz}` (or binary frame) | Appended up to 60 s (1,920,000 bytes). |
| `AUDIO/end` | `{transcript?}` | Transcript, else server ASR over the buffer. |
| `EVENTS/text` | `{text}` | Typed utterance. |
| `EVENTS/hello` | `{page, section, sections, lang, exp, persona, visitor, tour}` | Welcome flow (once). |
| `EVENTS/consent` | `{mic: true}` | Records consent time. |
| `EVENTS/tour_say` | `{index}` | Speak stored narration `index` (integer). |
| `EVENTS/call_answer \| call_ice \| call_decline \| call_hangup` | `{sdp?, candidate?}` | WebRTC signalling to the operator (only during a takeover). |
| `STATE/sync` | `{page, section \| viewport, sections, persona, intelligence}` | Updates state. `intelligence` is ignored when tier-locked. |
| `STATE/barge_in` | — | Cancels the answer if it is speaking. |
| `STATE/…` with `{component_state: {sync_id, …}}` | Merges state and schedules a reaction. |

### 8.4 Server → client messages

| Channel / type | Payload |
|---|---|
| `EVENTS/ready` | `{session_id, privacy, config: {filler_delay_ms, sample_rate, audio_frames}}` |
| `STATE/transcript` | `{text}` (final visitor text) |
| `AUDIO/start` | `{text?, grounding?}` (full text and grounding on the first segment) |
| `AUDIO/chunk` | `{data}` or a binary frame |
| `AUDIO/end` | — |
| `DATA/render` | `{sync_id, component_type, initial_state, explanation_text}` |
| `DATA/render_page` | `{sync_id, title, sections[]}` |
| `DATA/patch` | `{target_sync_id, patch, animation?}` |
| `EVENTS/navigate` | `{path}` |
| `EVENTS/scroll_to` | `{sectionId?, direction?}` |
| `EVENTS/set_persona` | `{persona}` |
| `EVENTS/tour_plan` | `{stops: [{narration, move?, label?}]}` |
| `EVENTS/tour_done` | `{index}` |
| `EVENTS/action_proposal` | card `{id, label, summary[], …}` |
| `EVENTS/action_answer` | `{run_id, confirm}` (a spoken yes/no) |
| `EVENTS/recap_request` | `{email?}` |
| `EVENTS/memory_forgotten` | — |
| `EVENTS/consent_required` | `{privacy}` |
| `EVENTS/operator_joined \| operator_message \| operator_left` | `{name, text?}` |
| `EVENTS/call_offer \| call_ice \| call_hangup` | `{name, sdp?, candidate?, ice_servers?}` |
| `EVENTS/interrupted`, `EVENTS/recalibrating` | — |
| `EVENTS/reconnect` | `{reason: "server_restart"}` |
| `EVENTS/error` | `{reason}` or `{message}` |

### 8.5 Session concurrency model

- One `asyncio.Task` per response (`_response_task`). A new utterance or barge-in cancels it; the
  `finally` block cancels any thinker started in parallel.
- Background work (recording, usage, audio cache writes) runs in referenced tasks
  (`_bg_tasks`), so cancellation of the turn does not lose them.
- Speech pipeline: `split_for_tts(text, min_chars=24)` → for segment *i*, an
  `asyncio.Queue` filled by `_synthesize` (audio cache lookup, else TTS stream, then cache
  write); segment *i+1* starts synthesising when *i* starts sending.
- `_answer_speaking` gates barge-in and live reactions.
- Time to first audio: measured from the utterance's arrival to the first audio byte (ack) and
  to the first answer byte; stored on `usage_events.ttfa_ms` and in Prometheus histograms.

### 8.6 Drain (`transport/drain.py`)

SIGTERM → `draining = true` (`/readyz` 503, `fb_draining` 1) → each session: send `reconnect`,
wait for the current response (shielded, up to `DRAIN_SECONDS` = 25 s), close **1012**. New
sockets close **1013**. Uvicorn `--timeout-graceful-shutdown` 45 s; Compose grace 60 s.

### 8.7 Text path (`routes/chat.py`)

`POST /chat` — request `{message, session_id?, key?, site, intelligence?, icp?, page?, sections?,
exp?, lang?, visitor?}`; response `{text, ack, intent, persona, actions[], components[],
pages[], patches[], grounding, session_id, lang, proposals[]}` (plus `takeover {name, after}`
or `memory: "forgotten"` in those cases). Errors: 403 `{detail: reason}`, 429 `{detail:
rate_limited | spend_cap_reached | plan_limit_reached}`.

`GET /chat/live?session_id&after&key|site` — long poll (25 s) for operator messages and takeover
state.

---

## 9. HTTP API reference

Auth column: **P** public (widget key and origin checked where relevant), **M** signed-in member
(role per §14), **T** bearer token as noted, **R** Razorpay signature.

### 9.1 Public widget and visitor APIs

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/healthz` | P | Liveness |
| GET | `/readyz` | P | Readiness (503 on critical failure or drain) |
| GET | `/metrics` | T (`METRICS_TOKEN`, optional) | Prometheus |
| WS | `/ws/voice` | P | Voice transport |
| POST | `/chat` | P | Text turn |
| GET | `/chat/live` | P | Takeover long-poll |
| GET | `/widget/config?key=` | P (no origin check) | Display settings for a key |
| GET/HEAD | `/widget/loader.js` | P | Loader script |
| GET | `/widget/gtm-template.tpl` | P | GTM template |
| GET | `/widget/triggers?key=` | P | Enabled trigger rules |
| GET | `/widget/triggers/message?key&rule_id&page&title&lang` | P | Composed opener |
| POST | `/widget/triggers/event` | P | `{key, visitor, rule_id, event, page?}` (text/plain JSON accepted) |
| GET | `/design-system?site=` | P | Brand tokens (`--ds-*`) |
| POST | `/experiment/enroll` | P | `{key, site?, visitor, automated?}` → `{experiment_id, arm, goal_path, overrides, defaults}` |
| POST | `/experiment/convert` | P | `{key, visitor, experiment_id, name, value?}` (202; sendBeacon) |
| POST | `/leads` | P | Enquiry form lead (20/min/site) |
| POST | `/recap` | P | `{key, session_id, email?}` → `{url, expires_at, emailed}` |
| GET | `/r/{token}` | P | Recap page |
| POST | `/actions/confirm` | P | `{key, session_id, run_id}` → outcome |
| POST | `/actions/cancel` | P | `{key, session_id, run_id}` |
| POST | `/actions/razorpay/{action_id}/webhook` | R (per-action secret) | Payment link paid |
| POST | `/memory` | P | `{key, visitor, remember}` |
| GET | `/p/{site_key}/{slug}` | P | Campaign page |
| POST | `/p/{site_key}/{slug}/lead` | P | Campaign form |
| GET | `/p/{site_key}/{slug}/go` | P | CTA redirect + conversion |
| POST | `/p/{site_key}/{slug}/event` | P | Engagement |
| POST | `/mcp/{key}` | P (+ T `fbat_` for write tools) | MCP JSON-RPC |
| GET | `/mcp/{key}` | — | 405 |
| GET | `/sites/{key}/llms.txt` | P | llms.txt |
| GET | `/sites/{key}/openapi.json` | P | OpenAPI for REST ask |
| POST | `/agent/{key}/ask` | P | `{question}` → grounded answer |
| GET | `/agent/{key}/offerings` | P | Plans and prices |
| GET | `/status`, `/status.json` | P | Status page |
| POST | `/status/incidents`, `/status/incidents/{id}/updates` | T (`STATUS_TOKEN`) | Incidents |
| GET/POST | `/digest/unsubscribe?t=` | P (token) | Unsubscribe page / action |
| POST | `/billing/razorpay/webhook` | R (`RAZORPAY_WEBHOOK_SECRET`) | Subscription and payment-link events |
| POST | `/auth/sso/start` | P | `{provider: google|oidc, email?}` → `{url}` |
| GET | `/auth/sso/callback` | P | Completes SSO; redirects to the console with the token in the fragment |

### 9.2 Authentication and account (`/auth`)

`POST /register`, `POST /login`, `POST /login/mfa`, `POST /logout`, `GET /me`, `GET /accounts`,
`POST /switch`, `GET /sessions`, `DELETE /sessions/{id}`, `POST /sessions/revoke-others`,
`POST /password`, `GET /mfa`, `POST /mfa/setup`, `POST /mfa/enable`, `POST /mfa/disable`,
`POST /mfa/recovery-codes`, `GET /invitations/{token}`, `POST /invitations/{token}/accept`.

Sign-in responses: `{access_token, token_type: "bearer", tenant, role, user, csrf_token,
expires_at}` plus the `fb_session` cookie; or `{mfa_required: true, mfa_token}`.

### 9.3 Console API (`/tenant`)

| Area | Endpoints |
|---|---|
| Websites | `GET/POST /tenant/websites`; `GET/PATCH/DELETE /tenant/websites/{id}`; `POST …/{id}/rotate-key` |
| Ingestion | `GET …/{id}/ingestion`; `POST …/sources`; `POST …/sources/upload`; `DELETE …/sources/{sid}`; `POST …/ingestion/run[?wait=true]` |
| Onboarding | `POST/GET …/{id}/crawl`; `GET …/{id}/design` |
| Profile | `GET/PUT …/{id}/profile` |
| Templates | `GET /tenant/templates`; `GET …/websites/{id}/template`; `GET …/template/preview?template=`; `POST …/template` |
| Tour | `GET/PUT …/{id}/tour`; `POST …/tour/generate` |
| Cache | `GET …/{id}/cache`; `GET/PUT/DELETE …/cache/{eid}` |
| Analytics | `GET …/{id}/analytics?group_by=day|hour|session&from&to`; `GET …/cost-alerts` |
| Insights | `GET …/{id}/insights`; `GET …/conversations`; `GET …/conversations/{cid}`; `GET …/insights/signals`; `POST …/insights/requests/send` |
| Leads | `GET …/{id}/leads`; `PATCH …/leads/{lid}`; `GET/PUT …/integrations`; `POST …/integrations/test` |
| Privacy | `GET/PUT …/{id}/privacy`; `POST …/privacy/erase` |
| Experiments | `GET/PUT …/{id}/experiment`; `POST …/experiment/restart`; `GET …/experiment/results`; `GET …/experiment/plan` |
| A/B tests | `GET/POST …/{id}/tests`; `GET …/tests/plan`; `GET …/tests/{tid}`; `POST …/tests/{tid}/stop`; `POST …/tests/{tid}/promote` |
| Triggers | `GET/POST …/{id}/triggers`; `PUT/DELETE …/triggers/{rid}` |
| Recaps | `GET …/{id}/recaps`; `DELETE …/recaps/{rid}` |
| Actions | `GET/POST …/{id}/actions`; `PUT/DELETE …/actions/{aid}`; `GET …/actions/{aid}/secret`; `GET …/action-runs`; `GET …/action-runs/{rid}/quote.pdf` |
| Components | `GET/POST …/{id}/components`; `PUT/DELETE …/components/{cid}`; `POST …/components/preview` |
| Campaigns | `GET/POST …/{id}/campaigns`; `GET/PUT/DELETE …/campaigns/{cid}`; `GET …/campaigns/{cid}/analytics`; `POST …/campaigns/{cid}/cache/clear` |
| Agent access | `GET/PUT …/{id}/agent-access`; `POST …/agent-tokens`; `DELETE …/agent-tokens/{tid}` |
| Model | `GET/PUT/DELETE /tenant/model-provider`; `POST /tenant/model-provider/test`; `PUT …/websites/{id}/model` |
| Live | `GET /tenant/live`; `GET /tenant/live/ice`; `GET …/websites/{id}/live/{session}`; `POST …/live/{session}/takeover|message|release|call`; `WS /tenant/live/events` |
| Team | `GET /tenant/team`; `POST /tenant/team/invitations`; `DELETE …/invitations/{iid}`; `PATCH/DELETE /tenant/team/members/{uid}`; `GET /tenant/team/access-review.csv`; `GET/PUT /tenant/security`; `GET /tenant/audit`; `GET /tenant/audit.csv` |
| SSO | `GET/PUT/DELETE /tenant/sso`; `POST /tenant/sso/domains`; `POST …/domains/{domain}/verify`; `DELETE …/domains/{domain}` |
| Billing | `GET /tenant/billing`; `POST /tenant/billing/checkout|verify|cancel` |
| Digest | `GET/PUT /tenant/digest`; `GET /tenant/digest/preview`; `POST /tenant/digest/send-test` |
| Licence | `GET/PUT /tenant/licence` |

Every `/tenant/websites/{website_id}/…` route resolves the website through the member's account
(404 for another account's site).

---

## 10. Data model

All tables live in one Postgres database, created by Alembic migrations `0001_baseline` to
`0031_status_page`. Per-site tables are keyed by `site_key`; account tables by `tenant_id`.

### 10.1 Accounts and identity

| Table | Purpose / key columns |
|---|---|
| `tenants` | Accounts (name, created). |
| `users` | People: email, name, optional password hash, `totp_secret_enc` / `totp_pending_enc` (encrypted), `totp_enabled_at`, `totp_last_step`, `recovery_codes` (hashes), `failed_attempts`, `locked_until`, `password_changed_at`, last login. (`tenants.require_mfa` holds the account policy.) |
| `memberships` | `(user_id, tenant_id, role)`. |
| `invitations` | Email, role, token hash, status, expiry. |
| `user_sessions` | One row per sign-in: method (password, mfa, sso), created, last seen, ended, IP, user agent. |
| `tenant_sso` | Issuer, client id, encrypted client secret, default role, require SSO, enabled. |
| `sso_domains` | Domain, TXT token, verified at. |
| `sso_logins` | State, nonce, PKCE verifier, provider (single-use, 10 min). |
| `audit_events` | Append-only: actor, action, target, details JSONB, IP, UA, request id, time. |

### 10.2 Websites, knowledge and configuration

| Table | Purpose |
|---|---|
| `tenant_websites` | `id, tenant_id, site_key (unique), public_key (unique, fbk_…), name, domain, intelligence, design, accent, status, byo_model, agent_access, created_at`. |
| `tenant_sources` | `id, website_id, kind (text|url|file), name, content, status, error, nodes, created_at, ingested_at`. |
| `crawl_jobs` | Crawl progress (phase, counts, error, timing). |
| `site_profiles` | `site_key, profile JSONB, updated_at`. |
| `site_tours` | `site_key, plan JSONB, edited, updated_at`. |
| `site_design` | Extracted brand tokens. |
| `site_privacy` | `redact_pii, consent_required, privacy_policy_url, transcript_retention_days, lead_retention_days, recap_days, memory_enabled, memory_days`. |
| `site_integrations` | Webhook URL, encrypted signing secret, encrypted Slack URL, hot-lead score, cost alert USD. |
| `site_components` | Custom components (kind, props schema, template, iframe URL, enabled). |
| `site_actions` | Actions (kind, name, label, description, config JSONB, encrypted secrets, enabled). |
| CORTEX tables | `cortex_trees`, `cortex_nodes` (`vector(768)`), `cortex_edges`, … (owned by `hb-cortex-memory`, created in the baseline). |

### 10.3 Conversations and caches

| Table | Purpose |
|---|---|
| `conversations` | One per visitor session: site, session id, channel, persona, page, consent at, visitor id (only while memory exists), lead link, timestamps. |
| `conversation_turns` | Question (masked), answer, intent, persona, page, grounding, served from cache, components, language, and classification results (objections, competitors, feature request, buying signal). |
| `conversation_cache` | Replayable answers (§7.4). |
| `answer_audio_cache` | Agent speech PCM (§7.5). |
| `visitor_memories` | `site_key, visitor_id, opted_in_at, summary, topics, components, open_questions, persona, left_details, conversations, lang, built_at, last_seen_at`. |

### 10.4 Revenue

| Table | Purpose |
|---|---|
| `leads` | Contact fields, source (`form`, `conversation`, `recap`, `campaign`, `agent`, `payment`, `quote`, `trial`, `meeting`; `test` for integration test sends), score, reasons, summary, status, conversation id, delivery status/error. |
| `action_runs` | Proposed/confirmed/finished runs: inputs, summary, status, outcome, external id, lead link. |
| `recaps`, `recap_views` | Token, snapshot, expiry, conversation id; views per viewer. |
| `live_presence`, `live_takeovers`, `live_messages` | Live visitors, who holds a conversation, the people's messages. |
| `trigger_rules`, `trigger_events`, `trigger_messages` | Rules, reported events, composed openers per rule/page/language. |
| `campaigns`, `campaign_pages`, `campaign_events` | Briefs, composed page cache, views/engagement/conversions. |
| `agent_tokens`, `agent_requests` | Hashed scoped tokens; agent traffic log. |

### 10.5 Measurement, billing and operations

| Table | Purpose |
|---|---|
| `usage_events` | One per turn: site, session, channel (voice, text, agent, background), intent, persona, page, served from cache, latency, ASR ms, TTS chars, fast/thinker tokens, tool calls, per-category cost, total cost, `byo_llm_cost`, provider, `ttfa_ms`. |
| `experiments`, `experiment_visitors`, `experiment_events` | Runs (holdout or test, subject, variants JSON, winner, bots ignored), assignments, conversions. |
| `cost_alerts` | One per site, UTC day and level. |
| `tenant_billing` | Plan, pending plan, status, subscription id, period, cancel at cycle end, next subscription/plan/status. |
| `razorpay_plans` | Razorpay plan ids per key, plan, currency and price. |
| `billing_events` | Processed webhook event ids (idempotency). |
| `billing_overage` | Per-period overage, add-on or payment-link id, paid state. |
| `email_outbox` | Queued email: recipients, subject, bodies, idempotency key, attempts, next attempt, status. |
| `digest_settings`, `digest_runs`, `digest_tokens`, `digest_unsubscribes` | Weekly digest configuration and delivery. |
| `model_providers` | Account's BYO provider, encrypted key, models, endpoint, version, prices, enabled, last test/error. |
| `install_licence` | Single row (id = 1): installed token, by whom and when. |
| `status_samples`, `status_incidents`, `status_updates` | Status page. |

### 10.6 Data lifecycle

| Data | Lifetime |
|---|---|
| Transcripts and automatic cached answers | Site transcript window (default 90 days) |
| Leads | Site lead window (default: until deleted) |
| Recaps | Site recap window (default 90 days); deleted with their conversation |
| Visitor memories | `memory_days` after last visit; immediately on forget/off/erasure |
| CORTEX episodes | Transcript window |
| Usage events | Kept (needed for billing) |
| Audit events | 365 days |
| Sent/failed email | 30 days |
| Ended sessions | 30 days |
| Status samples | 100 days (90 shown) |

---

## 11. Widget SDK architecture

### 11.1 Builds (`fluid-buddha-sdk/build.mjs`, esbuild)

| Output | Format | Purpose |
|---|---|---|
| `dist/fluid-buddha.global.js` | IIFE `window.FluidBuddha`, minified | Script-tag install; auto-injects |
| `dist/fluid-buddha-particles.global.js` | IIFE | Three.js smoke field, fetched only for Level 2 |
| `dist/fluid-buddha-hi.global.js` | IIFE | Hindi strings, fetched for Hindi visitors |
| `dist/fluid-buddha.mjs` + `dist/chunks/*` | ESM with code splitting | Bundlers |
| `dist/fluid-buddha.cjs` | CJS | Node/bundlers without splitting |
| `dist/fluid-buddha-recap.global.js` | IIFE | Recap page renderer |
| `dist/fluid-buddha-page.global.js` | IIFE | Campaign page interactive sections + engagement |
| `dist/index.d.ts` | Types | |

CSS lives in template strings (`ui/styles.ts`) and is minified at build time. Component renderers
load on demand. Per the handoff record, the core bundle measured 39.8 kB gzipped against a 42 kB
budget.

### 11.2 Public API (`src/index.ts`)

`init(options)`, `conversion(name)`, `VERSION`, `FluidBuddhaElement` (`<fluid-buddha>`: `ask`,
`openPanel`, `close`, `toggle`), `Session`, `HostBridge`, `Canvas`, `preloadComponents`,
`STRINGS`, `pickLang`, `prepareLang`, `consentCopy`, `consentPrompt`, `callPrompt`,
`pageMatches`, `SpeechGate`, `packAudio`, `unpackAudio`, and protocol types.

### 11.3 Module map

| Module | Responsibility |
|---|---|
| `core/config.ts` | Options, defaults, `data-*` parsing, `wss→https` API derivation. |
| `core/Session.ts` | Owns VoiceClient, capture, speech recognition, jitter buffer, player; routes envelopes; consent; text fallback; recap; leads; actions; tour host; page context reporting. |
| `transport/VoiceClient.ts` | WebSocket with typed senders, binary frames, backoff 0.5–8 s × 4, quiet reconnect on 1012/1013/`reconnect`. |
| `audio/AudioCapture.ts` | `getUserMedia` (echo cancellation, noise suppression, AGC), AudioWorklet from a Blob URL (ScriptProcessor fallback), 1,024-sample frames. |
| `audio/SpeechGate.ts` | Energy VAD (start 0.03 for 180 ms, continue 0.018, hangover 850 ms), 400 ms pre-roll ring, fractional resampler to 16 kHz PCM16 with averaging low-pass, smoothed level. |
| `audio/JitterBuffer.ts` | Per-sync-id segments, FIFO, gating until `markRendered`, filler after `filler_delay_ms`, generation counter for clean reset. |
| `audio/AudioPlayer.ts` | PCM16 → AudioBuffer → gain → analyser (output level) → speakers; filler tone. |
| `core/HostBridge.ts` | `fluidbuddha:*` events; SPA-aware navigation (600 ms render wait); scroll resolution; persona veil. |
| `core/Tour.ts` | Speak → await `tour_done` (≤ 20 s) → await playback drain → move → 450 ms. |
| `core/Triggers.ts` | Rule arming per page view, exit-intent detection, caps in storage, event reporting, 10 min cache. |
| `core/Experiment.ts` | Visitor id, enrolment (1.5 s timeout, 6 h cache), goal-page polling (1 s), `conversion()` via sendBeacon. |
| `core/Live.ts` | Operator events, WebRTC call (RTCPeerConnection with server-supplied ICE servers), text-mode long poll. |
| `core/designSystem.ts` | Fetch and apply `--ds-*` tokens. |
| `ui/FluidBuddhaElement.ts` | The custom element: experiment gate, defaults, language, Level 1 UI, chips, memory and recap offers, routing events to shells. |
| `ui/level2/*`, `ui/particles/*` | Level 2 shell and Three.js curl-noise particle field (8k–16k particles, GLSL simplex noise). |
| `ui/level3/Level3Shell.ts` | Edge aura, spotlight (4.2 s), captions (14 s, max 4), summon. |
| `ui/aura/AuraCanvas.ts` | 2D additive-blend light form (7 lobes, ~5.5 s breath). |
| `ui/components/*` | 13 renderers + `embed` (sandboxed iframe) + shared helpers (`evalExpr` shunting-yard evaluator, pan/zoom, money formatting). |
| `ui/page/PageRenderer.ts` | Full-page renderer for Extreme pages. |
| `ui/consent.ts`, `call.ts`, `actionCard.ts`, `nudge.ts`, `citations.ts` | Dialogs, cards and rows. |
| `i18n/*` | English and Hindi tables; `t()`; language picking. |
| `slots.ts`, `recap.ts`, `page.ts` | Server-rendered slot drawing for recap and campaign pages. |

### 11.4 Browser storage keys

| Key | Storage | Use |
|---|---|---|
| `fluidbuddha:vid` | localStorage | Anonymous visitor id |
| consent key per site | localStorage | Consent version given |
| `fluidbuddha:trg:muted`, `fluidbuddha:visits`, `fluidbuddha:visit` | local/session storage | Trigger caps, visit counting |
| experiment arm cache | localStorage | 6 h |

### 11.5 Isolation

All UI is in a Shadow DOM with `all: initial`. The widget never injects HTML from the model:
every component and page section maps typed JSON to DOM/SVG built with `textContent`. Iframe
embeds use `sandbox="allow-scripts"` with no referrer, and only accept messages from their own
frame.

---

## 12. Admin console architecture

- **Framework**: Next.js 16 App Router, React 19, client components; recharts for charts;
  qrcode for MFA setup.
- **Routes**: `/login`, `/register`, `/invite`, `/sso`, `/dashboard`, `/live`, `/team`,
  `/audit`, `/billing`, `/model`, `/licence`, `/security`, and `/websites/[id]/{install,
  ingestion, tour, insights, leads, cache, analytics, experiment, tests, triggers, campaigns,
  actions, agent, settings}`.
- **API client** (`src/lib/api.ts`): `fetch` with `credentials: "include"` (session cookie) and
  `X-CSRF-Token` on changes. The CSRF token is held in memory only. A "session ended" response
  fires a window event and returns to sign-in. A 403 for missing two-factor redirects to setup.
  Legacy `localStorage` tokens are removed.
- **Auth context** (`src/lib/auth.tsx`): current member, role, account list, `can(role)`
  helper for gating pages and buttons (`components/Permission.tsx`).
- **Live calls** (`src/lib/operatorCall.ts`): WebRTC offer/answer/ICE through
  `/tenant/websites/{id}/live/{session}/call`, ICE servers from `/tenant/live/ice`.
- **Security headers** (`next.config.ts`): CSP `default-src 'self'`; scripts self + inline +
  `checkout.razorpay.com`; `connect-src` self, API origin, widget WS origin, `*.razorpay.com`;
  frames self + Razorpay; `frame-ancestors 'none'`; `upgrade-insecure-requests` in production.
- **Build**: `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_WIDGET_BACKEND`; Docker multi-stage on
  `node:24-alpine`, `output: standalone`, non-root user, port 3000.

---

## 13. Install integrations

| Surface | Implementation |
|---|---|
| Loader | `/widget/loader.js` (inline in `routes/widget.py`): copies `data-*`, maps allowed query params, sets `data-backend`/`data-api` from its own URL, fires `fluidbuddha:ready`, guards double loading. `Cache-Control: public, max-age=300`, `Cross-Origin-Resource-Policy: cross-origin`. |
| Install code | `https://fbk_…@<server>` parsed by plugins and wrappers (`integrations/js/shared/loader.ts`). |
| WordPress | `integrations/wordpress/fluidbuddha/`: settings page (install code, hide-on paths), `wp_enqueue_scripts` with `async` and `data-key` via `script_loader_tag`, resource hints, connection check, uninstall hook. PHP 7.4+, WP 5.8+. |
| Shopify | Theme app extension block (`fluidbuddha.liquid`) with settings: install code, position, language, and whether to show on the cart and account pages. |
| Google Tag Manager | `integrations/gtm.py` builds a template in GTM export format; its only permission is injecting this server's loader; key pattern `^fbk_[A-Za-z0-9_-]+$`; includes GTM tests. |
| React / Vue | `@fluidbuddha/react`, `@fluidbuddha/vue`: load via the loader with `data-auto="false"`, then `FluidBuddha.init` with props/hooks; render nothing in place. |
| Framer | Code component (`integrations/framer/FluidBuddha.tsx`). |
| Webflow | Footer custom code guide. |

---

## 14. Security architecture

### 14.1 Authentication

- Passwords: `bcrypt(sha256(password).hexdigest())` (avoids bcrypt's 72-byte truncation).
- Tokens: HS256 JWT with `sub` (user), `tid` (account), `sid` (session). Only tokens that name a
  live session are accepted. The role is read from the database on every request.
- The app refuses to start outside development (`local`, `dev`, `development`, `test`, `ci`)
  with an empty or the shipped JWT secret.
- Cookie `fb_session`: httpOnly, Secure (outside development by default), SameSite `lax`
  (configurable), optional domain. CSRF token = HMAC of the session id; required on cookie
  requests that change something. The live-events WebSocket takes the bearer token or the CSRF
  token in its first message (never in the URL).
- MFA: RFC 6238 TOTP implemented in-house (SHA-1, 6 digits, 30 s, ±1 step), last-used step stored
  to prevent replay, recovery codes stored as hashes.
- Lockout counters on the user row.

### 14.2 Authorisation

`app/auth/roles.py`: the minimum role is computed from the HTTP method and the route template
(first matching rule; reads → viewer, changes → editor, plus explicit rules). The check runs
inside the `current_member` dependency, so every `/tenant` route is covered automatically, and a
test walks every route against the table.

### 14.3 Public surface protection

- Widget key resolves site and tier server-side; client-requested tier is ignored
  (`tier_locked`). Registered sites cannot be reached by site key alone.
- Origin allow-list: the request origin's host must equal the site's domain or be a subdomain
  (skipped in development, for sites without a domain, and for the platform's own host serving
  campaign pages).
- Rate limit per site (fixed window, Redis `INCR` with expiry or in-process), daily spend cap,
  plan cap. Separate per-endpoint limits for leads, recaps, action confirmations, campaigns and
  the agent endpoint.
- `tour_say` speaks only stored narration (no free TTS relay).
- Action amounts only from the price list; inputs validated server-side.

### 14.4 Outbound request safety (SSRF)

`tenancy/url_fetch.py` is used for URL sources, the crawler, lead and action webhooks, SSO
discovery/keys/token exchange and DNS-over-HTTPS:

- `http`/`https` only, no credentials in URLs;
- literal IPs and every resolved address must be global unicast (IPv4-mapped IPv6 unwrapped);
- redirects followed manually (max 3) and re-validated (webhooks: no redirects);
- size cap 2 MB (crawler PDFs 10 MB), timeout 15 s, allowed content types;
- environment proxies ignored;
- `INGEST_ALLOW_PRIVATE_URLS` disables address checks (development only).

### 14.5 Secrets

Fernet encryption (`app/security/secrets.py`) with `SECRETS_KEY` (comma-separated, newest
first, for rotation; derived from the JWT secret in development). Encrypted: SSO client secrets,
BYO model keys, action secrets, lead webhook signing secrets, Slack URLs and MFA seeds. Agent
tokens and invitation/recap tokens are stored as hashes or random tokens.

### 14.6 Signatures

| Signature | Algorithm |
|---|---|
| Outbound lead/action webhooks | `X-FluidBuddha-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "t.body")>` |
| Razorpay Checkout | HMAC-SHA256(`payment_id|subscription_id`, key secret) |
| Razorpay webhooks | HMAC-SHA256(raw body, webhook secret), constant-time compare; event ids stored |
| TURN credentials | username `<expiry>:<label>`, password `base64(HMAC-SHA1(TURN_SECRET, username))` |
| Licence | Ed25519 over `FBL1.<payload>`; public keys built in (`fb-2026-1`) |
| SSO ID token | RS256/384/512, ES256/384, PS256 against the provider's JWKS; iss, aud, exp, nonce checked |

### 14.7 Content security on hosted pages

Recap pages: CSP allows scripts only from the SDK origin and frames only from the site's custom
component origins; all values escaped; JSON blocks escape `<`. Campaign pages: own CSP, scripts
from own origins only, `frame-ancestors` restricted for embed mode. Status page: no scripts
(`default-src 'none'`).

### 14.8 Compliance artefacts

`docs/compliance/`: SOC 2 control matrix mapping controls to code and evidence, and policies for
information security, access control, change management, incident response, business
continuity, data classification and retention, vendor management, acceptable use and risk
assessment, plus a sub-processor list and DPA template. CI runs gitleaks, `pip-audit` and
`npm audit`; Dependabot is configured.

---

## 15. Privacy engineering

| Mechanism | Implementation |
|---|---|
| PII masking | `trust/pii.py` `PiiVault`: regexes for email, card (Luhn), SSN, IBAN, phone; non-overlapping spans with priority; stable placeholders `<KIND_n>`; `unmask` only for lead capture and actions; `spoken()` and `stored()` forms. Serialised with the session (Redis TTL applies). |
| No visitor audio stored | Only transcripts and the agent's own TTS are persisted. |
| Consent | Server drops audio until `EVENTS/consent`; `consent_at` stored on the conversation. |
| Telemetry hygiene | Logs redact PII in transcripts; metrics have no tenant labels; spans carry no visitor text; Sentry strips bodies, cookies, query strings, auth headers, users and local variables. |
| Retention and erasure | `trust/retention.py` sweeps per-site windows; `erase_visitor(email)` deletes leads, their conversations and memory. |
| Memory | Opt-in per site and per visitor; built from masked transcripts; deleted on forget, off, erasure, retention or site deletion. |

---

## 16. Multi-tenancy and isolation

- **Knowledge**: one CORTEX tree per site (`site_entity_id`); retrieval is scoped by entity.
- **Data**: every per-site row carries `site_key`; console routes resolve `website_id` through
  the member's account (`tenancy/deps.py: owned_website`), returning 404 otherwise.
- **Public paths**: the widget key decides the site; sessions are bound to their site; cached
  answers and audio are per site.
- **Configuration**: profile, design, actions, components and BYO provider are per site or per
  account, cached per site key.
- **Billing**: aggregated per account across its sites.
- **Self-hosted limits**: sites and seats counted install-wide.

---

## 17. Background jobs

`app/jobs/scheduler.py`: one in-process scheduler per replica. Each job runs every
`interval_s` (0 disables it) and inside `pg_try_advisory_lock(lock_key(name))`, so only one
replica runs a job at a time. Outcomes are counted in `fb_job_runs_total{job, outcome ∈ ok,
error, skipped}`.

| Job | Default interval | Code |
|---|---|---|
| `retention` | 60 min | `trust/retention.purge_expired` (+ episodes, recaps) |
| `outbox` | 15 s | `notify/email.deliver_due` (claims with `FOR UPDATE SKIP LOCKED`) |
| `outbox_cleanup` | periodic | `notify/email.purge_old` (30 days) |
| `audit_retention` | periodic | `audit.purge_old` (365 days) |
| `live_sweep` | periodic | `live/store.sweep` |
| `classify_turns` | 20 s | `insights/classify.run_job` (batch 50, concurrency 8, 15 s budget, last 7 days) |
| `weekly_digest` | 600 s | `notify/digest.send_due` |
| `action_payments` | 300 s | `routes/actions.check_payments` |
| `access_review` | 6 h | `notify/access_review.send_due` |
| `session_cleanup` | periodic | ended > 30 days |
| `visitor_memory` | 120 s | `memory/store.build_due` (quiet 10 min) |
| `status_probe` | 60 s | `status/store.probe` |

Email outbox: exponential backoff (1, 2, 4 … 32 min), 6 attempts, rows stuck in `sending` for
10 min are re-queued (the only double-send case), idempotency keys (one digest per account and
ISO week, one invitation per token).

---

## 18. Observability

### 18.1 Logging

Text (`HH:MM:SS LEVEL logger [request_id] | message`) or JSON lines (`LOG_FORMAT=json`, UTC).
Every line carries the request id; voice lines also carry the session id. `cortex_memory` is held
at WARNING.

### 18.2 Metrics (`/metrics`)

| Metric | Labels |
|---|---|
| `fb_http_requests_total` | method, route (template), status class |
| `fb_http_request_seconds` | method, route |
| `fb_ws_connections` | — |
| `fb_turns_total`, `fb_turn_seconds` | channel, path (fresh/cached) |
| `fb_time_to_first_audio_seconds`, `fb_time_to_first_answer_audio_seconds` | path |
| `fb_stage_seconds` | stage (route, retrieval, think_lean, think_heavy, tts) |
| `fb_engine_errors_total` | engine |
| `fb_crawl_jobs_total` | status |
| `fb_job_runs_total` | job, outcome |
| `fb_ready` | check |
| `fb_draining` | — |
| `fb_cost_alerts_total` | level |

Latency buckets: 0.05 s to 30 s. No site keys, visitor ids or raw paths are used as labels.

### 18.3 Tracing and errors

OpenTelemetry (when `OTEL_EXPORTER_OTLP_ENDPOINT` is set): a span per HTTP request, `voice.turn`
/ `chat.turn` spans and `stage.*` children; OTLP/HTTP export. Sentry (when `SENTRY_DSN` is set):
scrubbed events tagged with the request id and `RELEASE`.

### 18.4 Health

`/readyz` runs checks in parallel with a 2 s timeout each. Critical: `db`, `migrations` (at head),
`redis` (when configured), `draining`. Non-critical (`degraded`): `scheduler`, `models` (engine
errors in the last 5 minutes), `email` (configured and outbox not backing up). Results set
`fb_ready{check}`.

### 18.5 Alerting (`deploy/monitoring/alerts.yml`)

Recording rules for 5xx ratio over 5 m, 30 m, 1 h and 6 h. Alerts: `FluidBuddhaDown`,
`FluidBuddhaNotReady`, `FluidBuddhaErrorBudgetFastBurn` (14.4× of 0.1 % over 1 h and 5 m),
`FluidBuddhaErrorBudgetSlowBurn` (6× over 6 h and 30 m), `FluidBuddhaDraining`,
`FluidBuddhaSlowFirstAudio` (p95 > 1.5 s), `FluidBuddhaVerySlowFirstAudio` (p95 > 3 s),
`FluidBuddhaSlowTurns` (p95 > 8 s), `FluidBuddhaModelErrors`, `FluidBuddhaJobFailing`,
`FluidBuddhaCostCapReached`, `FluidBuddhaCostCapNear`, `FluidBuddhaCrawlsFailing`. Each links to
a section of `docs/operations/incident-runbook.md`.

---

## 19. Reliability and scaling

| Concern | Mechanism |
|---|---|
| Several replicas | `REDIS_URL`: chat sessions (`fb:chat:<sid>`, sliding TTL), rate-limit windows (`fb:rl:<site>:<window>`), live events (`fb:live:` pub/sub relay). Without Redis, all are in-process (correct for one replica). Redis outages degrade to fresh sessions and local counting. |
| Voice affinity | Voice state lives on the socket; no Redis needed. |
| Migrations | Advisory-locked at start-up; `/readyz` fails if the schema is not at head. |
| Deploys | Drain (§8.6); widget reconnects; Caddy `stream_close_delay 5m` for WebSockets on reload. |
| Concurrency | `WEB_CONCURRENCY` uvicorn workers; async I/O throughout. |
| Backups | `backend/scripts/backup.sh` (custom-format `pg_dump`, SHA-256, optional `age` encryption, 30-day retention, `backup-log.jsonl`); `restore_drill.sh` (restore into a scratch DB, check revision and core tables, write `drills/*.json`). Self-host: base backup + WAL archiving (PITR) + logical dump. |
| Status | Public status page with minute samples and incidents. |

**SLOs** (`docs/operations/sla.md`): availability 99.9 % (30 days), readiness 99.9 %, p95 time
to first audio < 1.5 s, p95 whole turn < 8 s.

**Recorded voice load test** (`loadtest/voice.py`, one replica):

| Concurrent sessions | Turns | Failed | p50 / p95 TTFA | p95 whole turn |
|---|---|---|---|---|
| 50 | 150 | 0 | 0.63 s / 1.62 s | 2.3 s |
| 100 | 300 | 0 | 1.92 s / 5.93 s | 8.7 s |
| 200 | 587 | 5 (timeouts) | 5.99 s / 15.2 s | 22.2 s |

---

## 20. Deployment

### 20.1 Development (`backend/docker-compose.yml`)

| Service | Image | Notes |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | Host port 5434 |
| `redis` | `redis:7-alpine` | Profile `scale` |
| `coturn` | `coturn/coturn:4.6` | Profile `voice`; 3478 UDP/TCP, 49160–49200 UDP |
| `backend` | built from `backend/Dockerfile` | Port 8080 |

Backend image: `python:3.12-slim`, installs `requirements.txt` + `requirements-observability.txt`,
health check on `/healthz`, entrypoint optionally ingests a site (`INGEST_ON_START`), then runs
uvicorn with `--workers $WEB_CONCURRENCY --timeout-graceful-shutdown 45 --proxy-headers`.

Local commands: backend `uvicorn app.main:app --port 8080`; SDK `npm run serve:demo` (port
4000); console `next dev -p 3001`.

### 20.2 Self-hosted (`deploy/selfhost/`)

| Service | Image |
|---|---|
| `web` | Caddy 2 with the built SDK in `/srv/sdk` (`web.Dockerfile`) |
| `backend` | `fluidbuddha/backend:${FB_VERSION}` |
| `console` | `fluidbuddha/console:${FB_VERSION}` |
| `postgres` | `pgvector/pgvector:pg16` |
| `redis` | `redis:7-alpine` |
| `coturn` | `coturn/coturn:4.6` (profile `voice`) |

Caddy routes `API_DOMAIN` (`/sdk/*` static with CORS `*`, everything else → `backend:8080`) and
`CONSOLE_DOMAIN` (→ `console:3000`), with automatic TLS, zstd/gzip and JSON logs. JSON-file log
rotation for containers. Host sizing: 4 vCPU, 8 GB RAM, 40 GB disk to start.
Scripts: `install.sh`, `backup.sh`, `restore.sh`, `upgrade.sh`, `export-images.sh`,
`import-images.sh`.

### 20.3 Hosted service expectations

Managed Postgres with point-in-time recovery, Redis for multiple replicas, a load balancer that
honours `/readyz`, Prometheus scraping `/metrics` with `METRICS_TOKEN`, SMTP with SPF/DKIM, and
`PUBLIC_API_URL`, `CONSOLE_URL`, `WIDGET_SDK_BASE` set to public addresses.

---

## 21. Configuration reference

All backend settings come from environment variables or `backend/.env` (pydantic-settings,
case-insensitive).

| Group | Variables (default) |
|---|---|
| Runtime | `APP_ENV` (local), `HOST`, `PORT` (8080), `LOG_LEVEL` (INFO), `LOG_FORMAT` (text), `WEB_CONCURRENCY`, `SHUTDOWN_GRACE_SECONDS` (45) |
| CORS | `CORS_ORIGINS` (localhost 3000/3001/4000), `ADMIN_CORS_ORIGINS` (localhost 3001) |
| Database | `CORTEX_DB_URL` (`postgresql+asyncpg://cortex:cortex@localhost:5434/cortex`) |
| AI | `MOCK_AI` (true), `GOOGLE_CLOUD_PROJECT`, `VERTEX_LOCATION` (us-central1), `GOOGLE_APPLICATION_CREDENTIALS`, `FAST_MODEL` (gemini-2.5-flash), `HEAVY_MODEL` (gemini-2.5-pro), `EMBED_MODEL` (text-embedding-004), `ASR_LANGUAGE` (en-US), `TTS_MODEL` (gemini-3.1-flash-tts-preview), `TTS_GEMINI_VOICE` (Aoede), `TTS_VOICE` (en-US-Neural2-F), `TTS_VOICE_HI` (hi-IN-Neural2-A), `TTS_SAMPLE_RATE` (24000) |
| Grounding | `CORTEX_COMPANY_ID`, `CORTEX_CONFIDENCE_THRESHOLD` (0.45), `CORTEX_RETRIEVAL_TOP_K` (5) |
| Cache | `CONVERSATION_CACHE_ENABLED`, `EPISODIC_MEMORY_ENABLED`, `AUDIO_CACHE_ENABLED` (all true), `EPISODIC_REPLAY_THRESHOLD` (0.92), `EPISODIC_CONTEXT_THRESHOLD` (0.70), `EPISODIC_MIN_EPISODES` (20), `EPISODIC_TOP_K` (3), `UI_FILLER_DELAY_MS` (1500) |
| Auth | `JWT_SECRET` (dev default; required outside dev), `JWT_ALGORITHM` (HS256), `SESSION_IDLE_MINUTES` (60), `SESSION_ABSOLUTE_HOURS` (12), `SESSION_COOKIE_SAMESITE` (lax), `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_DOMAIN`, `LOGIN_MAX_ATTEMPTS` (10), `LOGIN_LOCKOUT_MINUTES` (15), `SECRETS_KEY` |
| Public guard | `PUBLIC_RATE_LIMIT_PER_MIN` (120), `PUBLIC_DAILY_SPEND_CAP_USD` (0) |
| Sessions/state | `REDIS_URL`, `SESSION_TTL_MINUTES` (30), `SESSION_CACHE_MAX` (10000) |
| Jobs | `RETENTION_SWEEP_MINUTES` (60), `EMAIL_OUTBOX_INTERVAL_SECONDS` (15), `INSIGHTS_CLASSIFY_SECONDS` (20), `DIGEST_CHECK_SECONDS` (600), `ACTION_PAYMENTS_SECONDS` (300), `ACCESS_REVIEW_CHECK_SECONDS` (21600), `MEMORY_BUILD_SECONDS` (120), `STATUS_PROBE_SECONDS` (60) |
| Email | `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SECURITY` (starttls), `SMTP_FROM`, `SMTP_TIMEOUT_SECONDS` (20) |
| URLs | `PUBLIC_API_URL` (http://localhost:8080), `CONSOLE_URL` (http://localhost:3001), `WIDGET_SDK_BASE` (http://localhost:4000/dist) |
| SSO | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `DNS_OVER_HTTPS_URL` (https://dns.google/resolve) |
| Live | `STUN_URLS` (stun:stun.l.google.com:19302), `TURN_URLS`, `TURN_SECRET`, `TURN_TTL_SECONDS` (3600) |
| Onboarding | `CRAWL_MAX_PAGES` (50), `CRAWL_MAX_DEPTH` (3), `CRAWL_CONCURRENCY` (4), `INGEST_ALLOW_PRIVATE_URLS` (false) |
| Observability | `METRICS_ENABLED` (true), `METRICS_TOKEN`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `SENTRY_DSN`, `RELEASE` |
| Billing | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `RAZORPAY_API_BASE`, `BILLING_CURRENCY` (INR), `BILLING_CATALOG` (JSON) |
| Pricing model | `PRICE_ASR_PER_MIN` (0.016), `PRICE_TTS_PER_1K_CHARS` (0.016), `PRICE_FAST_IN_PER_1K` (0.000075), `PRICE_FAST_OUT_PER_1K` (0.0003), `PRICE_THINKER_IN_PER_1K` (0.0003), `PRICE_THINKER_OUT_PER_1K` (0.0025), `PRICE_TOOL_PER_CALL` (0.0002) |
| Self-host | `SELF_HOSTED` (false), `LICENCE_KEY`, `LICENCE_FILE`, `DRAIN_SECONDS` (25) |
| Status | `STATUS_TITLE` (FluidBuddha), `STATUS_TOKEN` |
| Extreme tier | `<SITE>_DESIGN_SYSTEM` / `DESIGN_SYSTEM_DIR`, `<SITE>_OPENAPI` / `OPENAPI_DIR`, `<SITE>_API_BASE_URL`, `<SITE>_API_AUTH` |
| Ingestion CLI | `HIREBUDDHA_CONTENT_DIR`, `BUDDHA_COGNITIVE_LAB_CONTENT_DIR`, `FLUIDBUDDHA_CONTENT_DIR`, `INGEST_ON_START`, `INGEST_SITE` |
| Console build | `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_WIDGET_BACKEND` |

Built-in demo site keys: `hirebuddha`, `buddha-cognitive-lab`, `fluidbuddha`,
`chantingbuddha`.

---

## 22. Testing and quality gates

| Suite | Scope |
|---|---|
| Backend (`backend/tests`, ~290 tests in 46 modules) | Envelope and transport, tools by tier, engine paths, cache and replay, admin CRUD and isolation, ingestion, tours, analytics, citations, CORS, cost alerts, email jobs, experiments and variant tests, insights v1/v2, install surfaces, languages, leads, licence, lifecycle guard, live takeover, migrations (no DDL in app code), observability, onboarding, public access, recaps, reliability (drain, readiness, status), security (sessions, cookies, CSRF, MFA, lockout, headers), self-host bundle, SSO, SSRF and tour, teams and roles (every route), templates, triggers, trust (PII, consent, retention), visitor memory, actions, agent endpoint, BYO model, campaigns. Hermetic: `conftest.py` pins mock AI, empty payment keys and default prices. Needs Postgres + pgvector; Redis tests use `TEST_REDIS_URL`. |
| SDK (`test/smoke.mjs`, ~200 assertions; `test/inject.mjs`) | jsdom: element and Shadow DOM, envelope routing, all components, interactive state reporting, tier UI gating, Level 2/3 mounting, Extreme surface, persona veil, i18n coverage, embed contract; script-tag auto-injection. |
| Integrations | React/Vue wrappers with the real loader in jsdom; Shopify Liquid render; WordPress PHP functions and lint. |
| Evaluations | `evals/hindi_retrieval.py` (top-1/top-3 for English, Hindi, Hinglish and router queries), `evals/hindi_voice.py` (Hindi TTS → ASR → answer → TTS round trip). Need Vertex AI. |
| Load | `loadtest/voice.py` (gates on failures and `--max-p95-ttfa`). |
| Smoke | `scripts/smoke_chat.py`, `scripts/smoke_ws.py`. |

CI (`.github/workflows/ci.yml`), on every push and pull request:
backend tests twice against an ephemeral pgvector (reruns must be deterministic) and
`pip-audit`; SDK typecheck, build, tests, `npm audit --audit-level=high` and gitleaks;
integrations; console lint, `tsc --noEmit`, build and audit; self-host compose config,
Caddyfile, shell scripts (`bash -n`) and alert-rule validation. Dependabot keeps dependencies
current.

---

## 23. Statistics and algorithms

### 23.1 Experiments (`experiments/stats.py`, standard library only)

- Arm assignment: deterministic hash of run id and visitor id; holdout takes the first
  `holdout_pct` %, the rest is the agent or split equally among variants; stored on first sight.
- Per arm: Wilson 95 % interval (z = 1.95996).
- Difference: Newcombe hybrid score interval (method 10).
- Relative lift: log-scale interval (undefined when an arm has no conversions).
- p-value: pooled two-proportion z-test.
- **Always-valid verdict**: mixture SPRT (Johari et al., 2017) with pooled variance and mixing
  parameter τ = 0.05; always-valid p-value = 1 / mixture likelihood ratio. Verdicts:
  `collecting` (< 30 visitors per arm or < 10 conversions in total), `trending` (only the
  fixed-horizon interval excludes zero), `significant`.
- Variant tests: each variant vs control at α / k (Bonferroni); winner = best variant whose
  always-valid interval excludes zero.
- Planner: visitors for 80 % power (z = 0.84162) for a relative MDE over a baseline, at the
  (split) error budget; days left from observed traffic.
- Bots: user-agent patterns (crawlers, monitors, HTTP libraries, headless, missing UA) or the
  widget's `navigator.webdriver` flag.

### 23.2 Lead score

`min(100, 20 + 10·[name] + 10·[company] + 10·[phone] + min(30, 10·questions) + 10·[persona] +
15·[buying keyword])`, plus recap first view +5 and +10 per forward.

### 23.3 Cost model (`analytics/pricing.py`)

`cost = asr_ms/60000·0.016 + tts_chars/1000·0.016 + fast_in/1000·0.000075 +
fast_out/1000·0.0003 + thinker_in/1000·0.0003 + thinker_out/1000·0.0025 + tool_calls·0.0002`
(USD; env-overridable). Tokens are estimated at 4 characters per token when the provider
reports none. BYO model cost is computed from account or list prices and stored separately.

### 23.4 Feature-request grouping (`insights/store.py`)

Greedy grouping against each group's first item: embedding cosine ≥ 0.82 when embeddings are
available (not in mock mode), otherwise word-overlap Jaccard on stop-word-filtered tokens.

### 23.5 Language detection (`i18n/detect.py`)

Devanagari characters → `hi`; Latin text with common Hindi words → `hinglish`; otherwise `en`;
explicit "in Hindi" / "in English" phrases set a preference.

### 23.6 Campaign number verification (`campaigns/compose.py`)

Numbers are extracted with `\d[\d,]*(?:\.\d+)?` from each section and must appear in the cited
source snippets or the campaign's own copy; otherwise the section is dropped and recorded in
`dropped`.

---

## 24. Known technical limitations and risks

| Area | Limitation (from the code and its comments) |
|---|---|
| SSRF | Addresses are validated at resolve time; the connection re-resolves, so DNS rebinding remains a residual risk until IP pinning or an egress-restricted fetch worker is added. |
| PII | Pattern-based; names and street addresses are not detected. Masking can be switched off per site. |
| Languages | English and Hindi only; retrieval is in English (Hindi queries are translated by the router). |
| BYO model | Only the LLM is replaced; ASR, TTS and embeddings stay on Vertex AI. |
| Capacity | One-replica load tests miss the TTFA SLO above ~50 concurrent voice sessions; scale out with Redis-backed replicas. |
| Mock mode | `MOCK_AI=true` (default) gives deterministic, not meaningful, answers and retrieval. |
| Thinker latency | Heavy turns may take up to 4 model rounds plus a forced answer; `thinking_budget=1` keeps reasoning minimal and may need tuning per model. |
| Email | SMTP cannot be made idempotent; a replica crash mid-send can deliver one email twice. |
| Licence | Public keys are compiled into the build; rotating the signing key requires a new release. |
| Extreme tier | Design systems and OpenAPI specs are configured by environment or files per site, not yet through the console. |
| Legacy coupling | The built-in `hirebuddha` profile, sitemap and markdown loader paths remain in code as the flagship demo. |
