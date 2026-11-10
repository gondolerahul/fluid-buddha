# FluidBuddha — Technical Specification (version 2.0)

> **Basis.** Reverse-engineered from the code on branch `main` (commit `2306c72`,
> 10 November 2026, product version 2.0.0). File paths are relative to the repository root.
> Values are the coded defaults unless stated otherwise.
>
> **Changes since version 1.0.** Section 8 (Generative experience engine) and section 26
> (Marketing website) are new. Sections 8 to 24 of version 1.0 are now sections 9 to 25.
> Seven migrations (`0032` to `0038`) add 15 tables. Three route modules, one backend package
> (`app/experience/`), five on-demand SDK bundles and three npm packages are new. Additions
> elsewhere are marked **(2.0)**.
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
8. [Generative experience engine](#8-generative-experience-engine)
9. [Real-time transport protocol](#9-real-time-transport-protocol)
10. [HTTP API reference](#10-http-api-reference)
11. [Data model](#11-data-model)
12. [Widget SDK architecture](#12-widget-sdk-architecture)
13. [Admin console architecture](#13-admin-console-architecture)
14. [Install integrations](#14-install-integrations)
15. [Security architecture](#15-security-architecture)
16. [Privacy engineering](#16-privacy-engineering)
17. [Multi-tenancy and isolation](#17-multi-tenancy-and-isolation)
18. [Background jobs](#18-background-jobs)
19. [Observability](#19-observability)
20. [Reliability and scaling](#20-reliability-and-scaling)
21. [Deployment](#21-deployment)
22. [Configuration reference](#22-configuration-reference)
23. [Testing and quality gates](#23-testing-and-quality-gates)
24. [Statistics and algorithms](#24-statistics-and-algorithms)
25. [Known technical limitations and risks](#25-known-technical-limitations-and-risks)
26. [Marketing website](#26-marketing-website)

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
│  Triggers, Experiment, Live (WebRTC) │  /leads, /recap…  │  MCP/agent + views, experience, status     │
└──────────────────────────────────────┘                   │                                            │
                                                           │ Console API (/auth, /tenant/…)             │
 Admin console (Next.js 16 / React 19) ── cookie+CSRF ────►│  roles, audit, licence guard               │
   WS /tenant/live/events (live inbox)                     │ Scheduler (advisory-locked jobs)           │
                                                           └───────────┬──────────────┬─────────────────┘
                                                                       ▼              ▼
                                         Postgres 16 + pgvector (CORTEX trees,    Redis (optional):
                                         app tables, 38 Alembic migrations)       sessions, rate limit,
                                                                                  live event relay
            Vertex AI: Gemini fast + heavy, text-embedding-004 (768-d), Gemini TTS, Cloud Speech-to-Text
            Optional per account: Anthropic / OpenAI / Azure OpenAI (LLM only)
            Razorpay (billing + tenant payment links) · SMTP · Slack/webhooks · coturn (TURN) · OTLP · Sentry
```

**(2.0)** The generative experience adds a second way in: `<fb-region>` slots on the
customer's page call `POST /experience/regions`, and the customer's Next.js site or edge
worker (`@fluidbuddha/next`, `@fluidbuddha/edge`) calls `GET /experience/page` server to
server. Both are answered by the experience engine (§8): plan validator, manifest, bindings,
intent resolver, planners, SSR, fragments, bandit and agent views.

Three deployable applications:

| App | Folder | Runtime | Port |
|---|---|---|---|
| Backend ("A2UI Orchestrator") | `backend/` | Python 3.12, FastAPI + uvicorn | 8080 |
| Widget SDK | `fluid-buddha-sdk/` | Static JS bundles (served from `WIDGET_SDK_BASE`, e.g. Caddy `/sdk/`) | — |
| Admin console | `fluid-buddha-frontend/` | Node 24, Next.js 16 standalone | 3001 (dev) / 3000 (container) |

Also in the repository **(2.0)**: the npm packages under `integrations/js/packages/`
(`@fluidbuddha/react`, `vue`, `next`, `edge`, `components`), and the marketing website
(`fludi-buddha-website/web`, Next.js 16, port 3100 in development; §26). All product
components report version **2.0.0**: the FastAPI app (`app/main.py`), the SDK (`VERSION` in
`src/index.ts` and `package.json`), the console, the five npm packages and the WordPress
plugin.

---

## 2. Repository layout

```
backend/
  app/
    actions/        confirmable actions: fields, store, run, PDF, voice yes/no
    agents/         agent endpoint: MCP server, tools, tokens/traffic store, views (2.0)
    ai/             engine interfaces; Vertex, Anthropic, OpenAI, mock; RoutingLLM
    analytics/      pricing model, usage events + rollups, cost alerts
    apis/           per-site OpenAPI registry (Extreme tier; x-fb-* annotations, 2.0)
    audit.py        audit log + middleware
    auth/           passwords/JWT, sessions, MFA, roles, team, SSO
    billing/        plans, Razorpay client, billing store/rules
    campaigns/      landing-page composer, renderer, store
    cortex/         CORTEX bridge, query + guardrail, episodic cache, purge
    design/         design-system loader
    experience/     (2.0) generative experience: plan, manifest, binding, compose, store,
                    drafts, intent, regions, regions_store, planner, preview, entities,
                    resolvers, routes_store, page_planner, ssr, pages, patch, taste,
                    personal, bandit, freeform, agentview
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
    routes/         HTTP/WS routers (34 modules; experience, regions and pages are new)
    security/       security headers, secret encryption
    status/         status page store + renderer
    templates/      vertical template packs (YAML) + apply
    tenancy/        tenants/websites store, sources, SSRF-safe fetch, public access
    transport/      voice WebSocket, envelope, guard, session store, audio cache, drain
    trust/          PII, privacy settings, retention, medical safety
    config.py db.py main.py runtime.py shared_state.py cors.py logging_config.py
  migrations/       Alembic (0001–0038)
  ingestion/        CLI + markdown loader
  loadtest/         voice load test
  evals/            Hindi retrieval and voice evaluations
  scripts/          smoke tests, backup, restore drill, licence tool
  tests/            51 pytest modules (~440 tests)
fluid-buddha-sdk/   src/{audio,core,transport,ui,i18n}, src/core/{regions,patch,taste} (2.0),
                    src/composed.ts (2.0), demo/, test/
fluid-buddha-frontend/  src/{app,components,lib}
integrations/       wordpress, shopify, gtm, webflow, framer,
                    js/packages/{react,vue,next,edge,components}, js/shared/{loader,composed}
fludi-buddha-website/   web (Next.js marketing site), film (scroll-film frames), brand (logo)
deploy/selfhost/    compose, Caddyfile, bin/*.sh, web.Dockerfile
deploy/monitoring/  prometheus.yml, alerts.yml
docs/compliance/    SOC 2 control matrix and policies
docs/operations/    incident runbook, SLA
docs/product-docs/  version_1.0, version_2.0 (this set), strategy
docs/devdocs/       plans and build records (generative-experience-plan.md)
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
| Console | Next.js 16.4, React 19.3, recharts 3, qrcode, TypeScript 7 |
| Integrations | PHP (WordPress), Liquid (Shopify theme app extension), TypeScript (React/Vue/Framer; Next.js, edge worker and component authoring packages, 2.0) |
| Marketing website | Next.js 16.4 with Cache Components, React 19.3 |
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
  `ensure_design`, `ensure_extras`, and from 2.0 `ensure_manifest`), with a 30 s TTL.
- **(2.0)** `experience/*` depends on `apis/registry`, `design/system`, CORTEX and the
  manifest cache. `plan.py`, `binding.py`, `bandit.py`, `taste.py` and `agentview.py` hold
  pure logic with no database access in their core functions, so they are unit-tested
  directly. Route modules own the HTTP rules.
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
`used_hindi`), `visitor_id` and `memory_loaded`. From 2.0 it also holds `page_plan` and
`page_plan_id` (the composed page on screen: the plan the agent rendered, or the plan id a
served page reported, loaded before the next turn) and `taste` (the raw dict form of
`experience.taste.Taste`). It serialises to JSON for Redis (`to_dict` /
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
| `generate_page` | **(2.0)** `experience.compose.compose_page`: `regions` (or legacy `sections`, converted to `fb.<type>` regions) → `validate_plan` → `bind_plan` → `PageSpec` with `plan_id`, the validated plan and bound sections; `page_<hex10>` id | `{ok, sync_id, plan_id, region_count, regions[{id, component, state}], section_count, problems?, dropped?}`. Never bound values. |
| `patch_plan` **(2.0)** | Offered only at `extreme` when `state.page_plan` is set. `experience.patch.apply_ops` (≤ 8 ops) → validate → bind only added/replaced regions → `PlanPatch` | `{ok, plan_id, regions, problems?}` |
| `call_site_api` | `SiteApis.call(operation_id, params)` (declared ops only; simulated without base URL or in mock mode) | API response |
| `capture_lead` | PII unmasked; `LeadIn.cleaned()` | `{ok, note}` / validation error |
| `action_<name>` | PII unmasked; `validate_inputs(fields, args)`; one proposal per action per turn | `{ok, status: "waiting_for_the_visitor", note}` |

### 5.6 Tools by tier (`orchestrator/tools.py`)

```
basic   = query_cortex, navigate, scroll_to, capture_lead               + action tools
high    = basic + set_persona (enum = site personas; dropped if none)   + action tools
advance = high + render_component (+ site custom components) + patch_component + action tools
extreme = advance + generate_page + call_site_api (only if the site has OpenAPI operations) + action tools
          + patch_plan (2.0; added by the thinker only while a composed page is on screen)
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

**(2.0)** Thinker and lean prompts add a `VISITOR TASTE:` line when the state has a taste
("Shape the answer's length and format to it; never change facts or prices for it"). The
Extreme brief now lists `PAGE COMPONENTS` (the manifest's `to_prompt()`: ids, purpose, props
with their source rule) and `BINDABLE DATA` (read operations and the binding format). When a
composed page is on screen, the thinker prompt gets its outline (`patch.outline`).

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
| `pagegen.py` | `SECTION_TYPES` (14), `normalize_page`, `build_extreme_brief`, `bindable_prompt` (2.0). |
| `rewrite.py` | Follow-up detection and retrieval query expansion; `depends_on_history`. |
| `sitemap.py` | Route normalisation, validation, fuzzy snapping (`difflib`, cutoff 0.82), unique-leaf snapping, `sitemap_prompt`, `route_from_url`. |
| `tour.py` / `tour_store.py` | Planner with page catalogue (≤ 14 pages), JSON extraction, deterministic fallback; `site_tours(plan, edited)`. |
| `personas.py` | HireBuddha personas; `valid_personas`, `persona_fragment`. |
| `result.py` | `ClientAction`, `ComponentPayload`, `PageSpec` (2.0: `plan_id`, `plan` kept server side, `actions`, `bundle`), `PlanPatch` (2.0), `Grounding`, `ComponentPatch`, `TurnResult` (and `to_message_dict` for `/chat`). |

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

## 8. Generative experience engine

New in 2.0. Package `backend/app/experience/` (23 modules, about 5,900 lines), with HTTP rules
in `routes/experience.py`, `routes/regions.py` and `routes/pages.py`, and the agent side in
`agents/views.py` and `routes/agent_access.py`.

```
 signals (path, UTM, referrer, search) ──► intent.resolve_intent ──► goal (intent family)
                                                                        │
 manifest (approved version → file → default) ─┐                        ▼
 design system (console → file → extracted)    ├─► planner / page_planner / freeform
 CORTEX material + entities + API catalogue ───┘        │  (model tool call, or rules composer)
                                                        ▼
                                       plan.validate_plan  ◄── every source, every time
                                                        ▼
                               plan_cache / fragment_cache (auto | pinned | blocked)
                                                        ▼
                         binding.bind_plan (api: · entity: · content: · ctx.)  ── live data
                                                        ▼
        ┌───────────────┬────────────────────┬──────────────────────┬─────────────────────┐
   <fb-region> JSON   widget page       ssr.py HTML + head      agentview: fb.view/1,
   (regions.py)       (DATA/render_page) (pages.py, /g/, Next,   markdown, JSON-LD, tools
                                          edge)
```

### 8.1 Plan schema and validator (`experience/plan.py`)

- `SCHEMA = "fb.plan/1"`, `MAX_REGIONS = 12`, `MAX_ACTIONS = 8`, `MAX_STEPS = 5`,
  `CTX_PATHS = {currency, lang, page, persona, site_key}`, `CONFIRMS = (none, card, typed)`.
- Dataclasses: `Region(id, component, props, width)`, `PlanAction(id, ref, confirm)`,
  `Plan(plan_id, site_key, title, regions, actions, intent, layout, theme, policies,
  provenance, flow, schema)`, `PlanReport(plan, problems, dropped)` with `ok`.
- `new_plan_id()` = `pl_` + `secrets.token_hex(5)`. A supplied id is kept only if it matches
  `pl_[0-9a-f]{10}`.
- `validate_plan(raw, manifest, catalogue, site_key)` never raises:
  - title cut to 160 characters; `layout` kept only if `""`, `stack` or `split`;
  - actions: unique slug id; `ref` is `action:<name>` or `api:<op>`; an `api:` read operation
    is rejected ("bind it instead"); confirm is raised to the API's floor (`typed` for
    destructive, else the operation's `x-fb-confirm` or `card`);
  - regions: unknown component → dropped; id via `_region_id` (model's slug, else the
    component's short name, with `-2`, `-3` suffixes); `width` is `half` or `full`;
  - props (`_validate_props`): unknown props dropped; a binding on a `model_text` prop and a
    literal on a `binding_only` prop are problems; `action` must name a declared action;
    literals are coerced by type (`_coerce`: strings cut to `max_length` and checked against
    `enum`, numbers parsed with thousands separators removed, arrays cut to `max_items`);
    a missing required prop drops the region;
  - bindings (`_validate_binding`): `api:` must exist, be `read` and not `auth == "user"`;
    `ctx.` only from `CTX_PATHS`; `entity:` type matches `^[A-Z][A-Za-z0-9]{0,39}$`;
    `content:search` needs `params.query`; `path` matches the JSONPath subset
    `^\$(\.[A-Za-z0-9_]+|\[\d+\]|\[\*\])*$`; up to 20 plain params (`where` may be a
    flat object of up to 10 pairs for entities; `route.<name>` and `ctx.<name>` values are
    checked); `map` is up to 12 plain field names; up to 5 transforms matching
    `count|first|limit:<n>|sort_by(_desc)?:<key>`;
  - flow (`_validate_flow`): up to 5 steps with a unique slug and existing region ids; fewer
    than 2 valid steps → no flow;
  - `policies.must_include` components missing from the plan are reported.

### 8.2 Manifest (`experience/manifest.py`, `store.py`, `drafts.py`)

- `PropSpec(type, source, required, max_items, max_length, enum)`; `PROP_TYPES = string,
  number, boolean, array, object, any`; `SOURCES = model_text, binding_only, either`.
- `ManifestEntry(id, renderer, purpose, props, use_when, avoid_when, actions, version, ssr)`.
  Ids match `^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$`. `MAX_COMPONENTS = 200`, 40
  props per entry.
- Renderers: a built-in section (`BUILTIN_RENDERERS = SECTION_TYPES`) or `wc:<tag>`, where the
  tag matches `^[a-z][a-z0-9]*(-[a-z0-9]+)+$` and does not start with `fluid-buddha` or
  `fb-`. `clean_bundle` requires an `https://` URL (≤ 1,000 characters, no quote or angle
  characters) and an SRI string `sha(256|384|512)-…`.
- `default_entries()` builds `fb.<type>` entries from `pagegen.SECTION_TYPES` with the prop
  specs in `_DEFAULT_PROPS` (for example `fb.hero.title`: string, `model_text`, required, 160;
  `fb.pricing_table.tiers`: array, `either`, required, 6 items; `fb.faq.items`: 12 items;
  `fb.chart.data`: 48 items; `fb.comparison`: 6 columns, 24 rows).
- `parse_manifest(data)` returns the manifest and every refused entry with its reason
  (bad id, bad renderer, duplicate id, Web Component without a bundle, more than 200).
- Resolution (`load_manifest`): approved console version (`_approved` cache, 30 s,
  refreshed by `ensure_manifest`) → file (`<SITE>_COMPONENT_MANIFEST` or
  `COMPONENT_MANIFEST_DIR/<site>.json`, `lru_cache`) → default.
- Storage (`store.py`): `site_component_manifests` versions numbered per site under
  `pg_advisory_xact_lock(hashtext('manifest:<site>'))`; `approve_version` archives the
  previous approved row and approves the draft; a partial unique index allows one approved
  row per site. `site_design_systems` holds one row per site.
- Drafts (`drafts.py`): Storybook `index.json` (v7+) or `stories.json` (v6) → one
  `wc:<tag>` entry per story title, props from `argTypes` or a react-docgen JSON, callbacks
  skipped, prop names in `_TEXT_PROPS` become `model_text`; live site → section-level tags
  (`section, header, footer, aside, article, div, form`) whose class or id match
  `_RENDERER_HINTS`, counted over up to `MAX_SITE_PAGES = 8` pages. Both fetch through
  `tenancy/url_fetch.py`.

### 8.3 Bindings (`experience/binding.py`, `resolvers.py`, `entities.py`)

- `bind_plan(plan, manifest, registry, ctx, resolve)`:
  1. collect one call per distinct `(ref, resolved params)` (key = ref + sorted JSON params);
  2. run them with `asyncio.gather(return_exceptions=True)`: `api:` → `registry.call(op,
     params)`; `entity:` and `content:` → the `resolve` callback;
  3. per region and prop: `select(path)` → `apply_transforms` → `apply_map` → `_fit` to the
     prop spec; a failed required binding sets `state = "error"`, an empty required value
     sets `"empty"`.
- `BoundRegion.to_section()` yields the v1.0 `PageSection` shape (`type` = renderer, `props`)
  plus `id`, `component`, `state` and `width`.
- `make_resolver(db, rt, site_key, bridge)`: `entity:<Type>` → `resolve_entity_binding`
  (one record by `key`, or up to 500 rows filtered by string-equal `where`, `limit` 1–100,
  default 50; each record is `{key, …data}`); `content:search` → `bridge.search(query,
  top_k = limit or 4)`, keeping snippets at or above `CORTEX_CONFIDENCE_THRESHOLD`, as
  `{text (≤ 800 chars), label}`.
- Entities: `MAX_ENTITIES_PER_TYPE = 2000`, `MAX_RECORD_BYTES = 20_000`; keys are cleaned to
  `[a-z0-9-]`, up to 120 characters; upsert on `(site_key, type, key)`.
- Connectors: `KINDS = json_feed, wordpress`. `feed_url` appends `/wp-json/wp/v2/posts?
  per_page=50&_embed=1` for a bare WordPress address. `sync_connector` fetches JSON (10 MB
  cap), maps it (`map_feed`), upserts with `source = connector:<id>`, deletes that source's
  rows whose keys are not in the feed, and stores `last_status`.
- API catalogue (`apis/registry.py`): `ApiOperation` gains `effect`, `entity`, `cache`,
  `auth`, `pii`, `confirm`, `agent` and `input_schema` (body plus parameters);
  `operation(op_id)`, `bindable_operations()` (read and not user-auth). Simulated calls
  return the documented response example.

### 8.4 Design system (`design/system.py`, `routes/experience.py`)

- `design_source()` order: console row (`site_design_systems`) → file or environment →
  extracted (`site_design`) → default. Cached 30 s.
- Console input model `DesignIn`: `name`, `logo_url`, `colors` (≤ 24, hex), `typography`,
  `radius`, `brand_voice` (≤ 600), `tunables` (axes `density`, `scheme`, `motion`,
  `type_scale`; `allowed` ≤ 8, `default`), `schemes.{light,dark}`. Values are checked with
  `_HEX_RE` and `_CSS_VALUE_RE` (`^[\w\s.,#%()'"-]{0,200}$`).
- `personal.apply_tunables(design, taste)` returns token overrides and the applied axes:

| Axis | Tokens |
|---|---|
| density | `--ds-gap` / `--ds-pad`: airy 52px / 28px; balanced 34px / 20px; compact 18px / 14px |
| motion | `--ds-anim`: calm `0s`; standard `.6s`; lively `.9s` |
| type_scale | `--ds-base-size`: small 15px; standard 16px; large 18px (brand default only; not a taste dimension) |
| scheme | `--ds-color-<name>` from `schemes.light` or `schemes.dark` (hex only) |

  A value is used only if it is in the axis's `allowed` list; otherwise the axis's `default`.

### 8.5 Intent resolution (`experience/intent.py`)

- `Signals(page, utm_source, utm_medium, utm_campaign, utm_term, referrer, query, lang,
  persona)`; `text()` joins path words, campaign, term, query and referrer search terms
  (`q, query, p, search, text, wd`); `fingerprint(site)` = sha256 of the signal tuple, 32 hex.
- `resolve_intent`: rules by descending priority (`fnmatch` globs; `RULE_CONFIDENCE = 0.9`)
  → remembered model answer for the fingerprint (0.7, `_MODEL_TTL_S = 24 h`) → cosine
  similarity between the signal embedding and each family's embedding of
  `"label. description stage"` (`EMBED_THRESHOLD = 0.6`; family vectors cached by
  `(site, slug, updated_at)`) → `general`, scheduling one background fast-model
  classification per fingerprint (temperature 0, 20 tokens).
- The caches `_family_vectors`, `_model_answers` and `_model_inflight` are per process.
- `suggest_families(routes, personas)` maps route keywords to eight proposed families plus
  `for-<persona>` and `general` (priority −100).

### 8.6 Regions, G1 (`experience/regions.py`, `regions_store.py`, `planner.py`, `preview.py`)

- Cache key: `plan_cache_key` = sha256 of `[family, persona, lang, normalised page, sorted
  region names, content version, manifest version, taste bucket?]`, 40 hex. The content
  version is `campaigns.store.content_version` (the same one campaign pages use).
- `serve_regions`: enabled slots matching the names and page → `intent_for` → `pinned_plan`
  → `pick_arm` (arm 0, or the bandit) → miss: `_schedule_build` and `{pending: true,
  retry_after_ms: 2500}` (or an inline build with `wait`) → `render_plan` (re-validate,
  bind, keep `ready` sections) → tokens (`design.to_tokens()` + tunables), `why`, `bundle`.
- `_schedule(token, factory)` keeps one task per `"{site}:{key}"` in `_building` (per
  process) and holds task references in `_tasks`.
- `planner_llm` returns no model (so the rules compose) when `guard._limiter` refuses
  `region-build:<site>` (`BUILDS_PER_MIN = 20`), when `check_public_budget` says the daily
  spend cap is reached, or in mock mode without a BYO provider. It sets `current_site` so BYO
  routing applies.
- `planner.build_plan`: CORTEX material plus pinned answers → model tool call constrained to
  each slot's components → enforcement (id = slot name, allowed component, `_NUM_RE` numbers
  present in the material) → `validate_plan`; otherwise the rules composer. Returns `{plan,
  composer: model|rules, build_ms, problems, dropped}`. `FORMAT_RENDERERS` maps taste formats
  to preferred renderers.
- `set_plan_status`: pinning demotes any other pinned row for the same family, page and
  regions; blocking appends `#blocked#…` to the row's cache key to free it.
- `preview.py` renders built-in sections as script-free HTML for the console (`srcdoc`
  iframe); a `wc:` section is a labelled box with its props.

### 8.7 Pages, G2 (`experience/pages.py`, `routes_store.py`, `page_planner.py`, `ssr.py`)

- Routes: `PATTERN_RE` allows literal segments, `:name` and a trailing `/*`;
  `match_pattern` returns the parameters; `match_route` picks the most specific enabled
  route. Page plans live in `plan_cache` with `regions = ["@page"]` and `page = pattern`.
- `serve_page(db, rt, site_key, path, sig, fbv, bot, domain, api_base, public_key, taste,
  visitor, mode, wait)` returns `{status, route, params, html, css, data, head{title,
  description, canonical, robots, json_ld, markdown?}, plan_id, intent, tokens, bundle, why,
  served, pending, freeform?, scripts}` or `{status: 404, reason: no_route | no_plan}`.
- Robots: `index, follow` when `(bot or canonical plan) and not restored`, else
  `noindex, follow`.
- A first visitor served a quick rules page stores it under its own key, so a `?fbv` link to
  it still resolves after the background build replaces the main key (race fixed in 2.0).
- `page_planner.build_page_plan`: `MAX_CANDIDATES = 16`, `ALWAYS = fb.hero, fb.text, fb.cta`,
  component relevance by word overlap of purpose and `use_when` with the route purpose and
  intent; entity samples; up to 3 exemplar outlines; one repair round; fallbacks; the rules
  page uses `RULES_SLOTS`.
- `ssr.py`: `render_fragment` produces `<section data-fb-region data-fb-component
  data-fb-state [data-fb-width] [data-fb-step]>` with the `fbpage-*` classes;
  `INTERACTIVE = {chart, roi_calculator, enquiry_form}` are marked `data-fb-hydrate` and
  their props travel in `<script type="application/json" id="fb-page-data">`; a `wc:` section
  is its custom element with `<template shadowrootmode="open">` holding a fallback; a flow
  renders `ol.fb-steps`; the stylesheet uses `--ds-gap`, `--ds-pad`, `--ds-anim` and a
  two-column grid that collapses under 720 px; `mode` `agent` or `plain` sets
  `data-fb-mode` and expands every step and FAQ answer. `render_document` wraps a fragment
  as a full page for `/g/`.
- Forms in SSR post to `POST /experience/lead` (never a GET with personal data).

### 8.8 Plan patches (`experience/patch.py`)

`OPS = add, replace, remove, move`; `ANIMATIONS = fade, highlight, count_up`; `MAX_OPS = 8`.
`apply_ops(plan, ops)` edits a copy of the stored plan; the result goes through
`validate_plan`; only added and replaced regions are bound. The client message is
`DATA/plan_patch {plan_id, ops[]}` where each add or replace op carries its bound section.
`outline(plan)` is the text block the thinker sees.

### 8.9 Taste (`experience/taste.py`, `personal.py`)

- `DIMENSIONS` (7), `STEP = 0.15`, `HALF_LIFE_S = 14 days`, `CONFIDENT = 0.5`,
  `MAX_INTERESTS = 20`, `MAX_EVENTS = 30`.
- `Taste.apply(dim, value, explicit)`: explicit → `{confidence: 1, source: explicit}`; an
  implicit event never overrides an explicit value, and moves confidence by `STEP` towards
  the observed value (a different value first reduces confidence). `value(dim)` applies the
  decay and returns the value only at `CONFIDENT` or above.
- `bucket()`: confident density plus `FORMAT_GROUP[format]` (`text | tables | visual`), or
  `""`. `brief()`: one sentence for prompts.
- `from_text` (regex list `_SAID`) sets explicit values from what the visitor says;
  `apply_events` handles `set`, `reset`, `interest` and the named implicit events in
  `_EVENTS`.
- Storage: `save` writes `taste_profiles` only if `memory.store.get` finds a memory for the
  visitor; `resolve` merges the stored profile with the session's. `compact` /
  `from_compact` are the `fbtaste` cookie form (`density:compact,format:tables`; parsed
  values get confidence 0.6, implicit).
- `personal.explain(intent, sig, taste, served, applied)` returns up to 3 reasons.

### 8.10 Bandit (`experience/bandit.py`)

See §24.7.

### 8.11 Free-form, G3 (`experience/freeform.py`)

- Settings on `site_experience`: `freeform_enabled` (default true), `g3_daily_budget` (200),
  `g3_visitor_budget` (3), `review_sample_pct` (5), `g3_blocked_patterns`
  (`DEFAULT_BLOCKED`). Blocked patterns are `fnmatch` globs.
- Budget: `g3_usage(site_key, day, visitor, fresh)`; `budget_left` compares today's site
  total and the visitor's own count with the settings; `spend` increments on each fresh
  model plan.
- Fragments: `fingerprint(region)` = sha256 of `{component, props}` (40 hex), unique per
  site; `conditions = {family, stage, taste, lang}`; `status` auto, pinned or blocked;
  `source` model or seeded.
- Scoring and assembly: §24.8. `MIN_ASSEMBLED = 3`, `MAX_REGIONS = 8`, `PURPOSE_ORDER =
  hero, intro, highlights, plans, proof, compare, steps, faq, questions, next, cta`.
- Composer: tool `compose_page` with fragments offered as `{"use": "F#"}`, one repair round;
  pinned regions inserted at top or bottom unchanged.
- Stable plans are `plan_cache` rows with `regions = ["@g3"]` and `persona = "v:<hash of
  the visitor id>"`.
- `flags_for`: `validator`, `few regions`, `no call to action` (no `cta` or `enquiry_form`
  renderer and no `action` prop), `pinned region missing`. Flagged pages and a
  `review_sample_pct` share are written to `review_samples`.
- `serve_freeform` order: stable → assembled → schedule (or, with `wait`, run) a fresh model
  build if `budget_left` → `None` (the caller serves G2).

### 8.12 Agent views (`experience/agentview.py`, `agents/views.py`)

- `detect_agent(user_agent, headers, query)`: `?fbmode=agent` → `"declared"`; a
  `Signature-Agent` header → its value; else the `_AGENT_UA` pattern (GPTBot, ChatGPT-User,
  OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, PerplexityBot,
  Perplexity-User, Google-Extended, GoogleOther, Applebot-Extended, Meta-ExternalAgent,
  Amazonbot, Bytespider, cohere-ai, MistralAI-User, DuckAssistBot, YouBot and others).
- `agent_policy(confirm, op)`: `{none: auto, card: confirm, typed: never}`; destructive →
  `never`; `op.agent == never` or base `never` → `never`; else `op.agent or base`.
- `describe_actions`: `action:<name>` → the enabled site action's fields as inputs;
  `api:<op>` → the operation's `input_schema`.
- `json_ld`, the markdown renderer (per renderer), `build_view` (`fb.view/1`) and
  `VIEW_SCHEMA`.
- Confirmation codes: `agent_confirmations(code hash, site, plan, action, inputs digest,
  expires_at, used_at)`; `CONFIRM_TTL_S = 600`; a code is accepted once, for the same plan,
  action and inputs digest.
- `agents/views.py`: `list_views` (concrete paths link to views; patterns explain how to
  ask), `load_view(path | plan_id, html?)` (by path: the canonical page as crawlers get it),
  `run(site, plan_id, action, inputs, token, confirm_code)` → `{status: done |
  needs_confirmation | refused | failed, …}`.

---

## 9. Real-time transport protocol

### 9.1 Endpoint

`WS /ws/voice?key=<fbk_…>&site=<demo site>&intelligence=<tier>&audio=binary&visitor=<id>`

1. `resolve_public_site(key, site, intelligence, Origin)`. On failure: accept, send
   `EVENTS/error {reason}`, close **4403**.
2. Warm profile, design, site extras (actions and components) and, from 2.0, the approved
   manifest (`ensure_manifest`).
3. If the replica is draining: send `EVENTS/reconnect`, close **1013**.
4. Load privacy settings, create the `PiiVault`, recognise the visitor's memory, send
   `EVENTS/ready`, announce presence, start the live listener and a 30 s heartbeat.

### 9.2 Envelope

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

### 9.3 Client → server messages

| Channel / type | Payload | Handling |
|---|---|---|
| `AUDIO/start` | — | Reset utterance buffer (dropped before consent or during a call). |
| `AUDIO/chunk` | `{data: base64 PCM16 16 kHz}` (or binary frame) | Appended up to 60 s (1,920,000 bytes). |
| `AUDIO/end` | `{transcript?}` | Transcript, else server ASR over the buffer. |
| `EVENTS/text` | `{text}` | Typed utterance. |
| `EVENTS/hello` | `{page, section, sections, lang, exp, persona, visitor, tour}`; 2.0 adds `taste` and `plan_id` | Welcome flow (once). |
| `EVENTS/consent` | `{mic: true}` | Records consent time. |
| `EVENTS/tour_say` | `{index}` | Speak stored narration `index` (integer). |
| `EVENTS/call_answer \| call_ice \| call_decline \| call_hangup` | `{sdp?, candidate?}` | WebRTC signalling to the operator (only during a takeover). |
| `STATE/sync` | `{page, section \| viewport, sections, persona, intelligence}`; 2.0 adds `taste` (cleaned into the state) and `plan_id` of a served page (`pl_…`, ≤ 20 characters; its plan is loaded before the next turn) | Updates state. `intelligence` is ignored when tier-locked. |
| `STATE/barge_in` | — | Cancels the answer if it is speaking. |
| `STATE/…` with `{component_state: {sync_id, …}}` | Merges state and schedules a reaction. |

### 9.4 Server → client messages

| Channel / type | Payload |
|---|---|
| `EVENTS/ready` | `{session_id, privacy, config: {filler_delay_ms, sample_rate, audio_frames}}` |
| `STATE/transcript` | `{text}` (final visitor text) |
| `AUDIO/start` | `{text?, grounding?}` (full text and grounding on the first segment) |
| `AUDIO/chunk` | `{data}` or a binary frame |
| `AUDIO/end` | — |
| `DATA/render` | `{sync_id, component_type, initial_state, explanation_text}` |
| `DATA/render_page` | `{sync_id, title, sections[]}`; 2.0 adds `plan_id`, `actions[]`, `bundle?` and per section `id`, `component`, `state`, `width?` (additive: v1.0 widgets ignore them) |
| `DATA/plan_patch` **(2.0)** | `{plan_id, ops[]}`; each add/replace op carries its bound section |
| `EVENTS/taste` **(2.0)** | `{taste: {dims, interests}, compact}` after the visitor states a preference |
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

### 9.5 Session concurrency model

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

### 9.6 Drain (`transport/drain.py`)

SIGTERM → `draining = true` (`/readyz` 503, `fb_draining` 1) → each session: send `reconnect`,
wait for the current response (shielded, up to `DRAIN_SECONDS` = 25 s), close **1012**. New
sockets close **1013**. Uvicorn `--timeout-graceful-shutdown` 45 s; Compose grace 60 s.

### 9.7 Text path (`routes/chat.py`)

`POST /chat` — request `{message, session_id?, key?, site, intelligence?, icp?, page?, sections?,
exp?, lang?, visitor?}`; response `{text, ack, intent, persona, actions[], components[],
pages[], patches[], grounding, session_id, lang, proposals[]}` (2.0: `plan_patches[]` and the
additive page fields above; plus `takeover {name, after}`
or `memory: "forgotten"` in those cases). Errors: 403 `{detail: reason}`, 429 `{detail:
rate_limited | spend_cap_reached | plan_limit_reached}`.

`GET /chat/live?session_id&after&key|site` — long poll (25 s) for operator messages and takeover
state.

---

## 10. HTTP API reference

Auth column: **P** public (widget key and origin checked where relevant), **M** signed-in member
(role per §15.2), **T** bearer token as noted, **R** Razorpay signature.

### 10.1 Public widget and visitor APIs

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
| POST | `/experience/regions` **(2.0)** | P | `{key, visitor, page, regions[≤12], signals, lang, persona, taste, automated}` → `{regions{name: section}, plan_id, intent, cache, arm, tokens, why, bundle?, pending, retry_after_ms?, reason?, experiment_id?}`. Body ≤ 8 kB. 240/min/site |
| POST | `/experience/taste` **(2.0)** | P | `{key, visitor?, taste, events[≤30]}` → merged profile, `raw`, `compact`, `stored`. 30/min per visitor |
| POST | `/experience/feedback` **(2.0)** | P | `{key, visitor, event: engage\|convert, plan_id \| plan_ids[≤10]}` → `{counted}`. 600/min/site |
| GET | `/experience/page?key&path&fbv&visitor&taste&ua&utm_*&referrer&q&lang&persona&fbmode` **(2.0)** | P (server callers send no Origin; a browser Origin must be the site's) | Composed or free-form page as JSON. 600/min/site |
| POST | `/experience/lead` **(2.0)** | P | Form post from a served page → lead, then 303 back to the site |
| GET | `/g/{site_key}/{path}` **(2.0)** | P | Hosted shell: the full HTML document with a strict CSP; reads the `fbvid` and `fbtaste` cookies |
| GET | `/sites/{key}/views`, `/sites/{key}/views?path=`, `/sites/{key}/views/{plan_id}` **(2.0)** | P | Views as `fb.view/1` JSON, or markdown with `?format=md` / `Accept: text/markdown` (a `Link` header points to the text) |
| GET | `/sites/{key}/views.schema.json` **(2.0)** | P | JSON Schema of a view |
| POST | `/sites/{key}/views/{plan_id}/actions/{action}` **(2.0)** | T (`fbat_`, scope `actions`) | `{inputs, confirm_code?}` → outcome |
| POST | `/auth/sso/start` | P | `{provider: google|oidc, email?}` → `{url}` |
| GET | `/auth/sso/callback` | P | Completes SSO; redirects to the console with the token in the fragment |

### 10.2 Authentication and account (`/auth`)

`POST /register`, `POST /login`, `POST /login/mfa`, `POST /logout`, `GET /me`, `GET /accounts`,
`POST /switch`, `GET /sessions`, `DELETE /sessions/{id}`, `POST /sessions/revoke-others`,
`POST /password`, `GET /mfa`, `POST /mfa/setup`, `POST /mfa/enable`, `POST /mfa/disable`,
`POST /mfa/recovery-codes`, `GET /invitations/{token}`, `POST /invitations/{token}/accept`.

Sign-in responses: `{access_token, token_type: "bearer", tenant, role, user, csrf_token,
expires_at}` plus the `fb_session` cookie; or `{mfa_required: true, mfa_token}`.

### 10.3 Console API (`/tenant`)

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
| Agent access | `GET/PUT …/{id}/agent-access`; `POST …/agent-tokens`; `DELETE …/agent-tokens/{tid}`; `GET …/agent-views` (2.0) |
| Design system (2.0) | `GET/PUT/DELETE …/{id}/design-system` |
| Manifest (2.0) | `GET …/{id}/manifest`; `GET/POST …/manifest/versions`; `GET/PUT/DELETE …/manifest/versions/{v}`; `POST …/manifest/versions/{v}/approve` (Admin); `POST …/manifest/drafts/storybook`; `POST …/manifest/drafts/site` |
| Regions (2.0) | `GET/PUT …/{id}/regions/settings`; `GET …/regions`; `PUT/DELETE …/regions/{name}`; `GET …/intent-families`; `GET …/intent-families/suggest`; `PUT/DELETE …/intent-families/{slug}`; `POST …/intent/resolve`; `GET …/plans`; `POST …/plans/generate`; `GET/PUT/DELETE …/plans/{pid}` |
| Pages (2.0) | `GET/POST …/{id}/routes`; `PUT/DELETE …/routes/{rid}`; `PUT …/routes/{rid}/canonical`; `POST …/routes/{rid}/generate`; `GET …/entities`; `GET …/entities/{type}`; `PUT/DELETE …/entities/{type}/{key}`; `POST …/entities/import`; `GET/POST …/connectors`; `DELETE …/connectors/{cid}`; `POST …/connectors/{cid}/sync`; `GET/PUT …/freeform`; `GET …/fragments`; `PUT …/fragments/{fid}`; `GET …/reviews`; `PUT …/reviews/{rid}` |
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

## 11. Data model

All tables live in one Postgres database, created by Alembic migrations `0001_baseline` to
`0038_agent_ready`. Migrations `0032` to `0038` are new in 2.0 (§11.7). Per-site tables are keyed by `site_key`; account tables by `tenant_id`.

### 11.1 Accounts and identity

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

### 11.2 Websites, knowledge and configuration

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

### 11.3 Conversations and caches

| Table | Purpose |
|---|---|
| `conversations` | One per visitor session: site, session id, channel, persona, page, consent at, visitor id (only while memory exists), lead link, timestamps. |
| `conversation_turns` | Question (masked), answer, intent, persona, page, grounding, served from cache, components, language, and classification results (objections, competitors, feature request, buying signal). |
| `conversation_cache` | Replayable answers (§7.4). |
| `answer_audio_cache` | Agent speech PCM (§7.5). |
| `visitor_memories` | `site_key, visitor_id, opted_in_at, summary, topics, components, open_questions, persona, left_details, conversations, lang, built_at, last_seen_at`. |

### 11.4 Revenue

| Table | Purpose |
|---|---|
| `leads` | Contact fields, source (`form`, `conversation`, `recap`, `campaign`, `agent`, `payment`, `quote`, `trial`, `meeting`; `test` for integration test sends), score, reasons, summary, status, conversation id, delivery status/error. |
| `action_runs` | Proposed/confirmed/finished runs: inputs, summary, status, outcome, external id, lead link. |
| `recaps`, `recap_views` | Token, snapshot, expiry, conversation id; views per viewer. |
| `live_presence`, `live_takeovers`, `live_messages` | Live visitors, who holds a conversation, the people's messages. |
| `trigger_rules`, `trigger_events`, `trigger_messages` | Rules, reported events, composed openers per rule/page/language. |
| `campaigns`, `campaign_pages`, `campaign_events` | Briefs, composed page cache, views/engagement/conversions. |
| `agent_tokens`, `agent_requests` | Hashed scoped tokens; agent traffic log (2.0: `plan_id`, `action` per call). |

### 11.5 Measurement, billing and operations

| Table | Purpose |
|---|---|
| `usage_events` | One per turn: site, session, channel (voice, text, agent, background), intent, persona, page, served from cache, latency, ASR ms, TTS chars, fast/thinker tokens, tool calls, per-category cost, total cost, `byo_llm_cost`, provider, `ttfa_ms`. |
| `experiments`, `experiment_visitors`, `experiment_events` | Runs (holdout or test, subject, variants JSON, winner, bots ignored), assignments, conversions. 2.0: the subject check also allows `regions` and `freeform`. |
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

### 11.6 Data lifecycle

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
| Automatic plans and fragments (2.0) | Deleted when the site's caches are invalidated (re-ingest); pinned and blocked ones stay |
| Taste profiles (2.0) | With the visitor's memory (`ON DELETE CASCADE`) |
| Agent confirmation codes (2.0) | 10 minutes to use; purged with the site |
| Free-form usage, review samples (2.0) | Kept; purged with the site |

### 11.7 Generative experience tables (2.0)

| Migration | Table | Purpose / key columns |
|---|---|---|
| `0032_experience_config` | `site_design_systems` | `site_key` PK, `data` JSONB, `updated_at`, `updated_by`. |
| | `site_component_manifests` | `id, site_key, version, status (draft\|approved\|archived), source (manual\|storybook\|site\|file), data JSONB, notes, created_at/by, approved_at/by`; unique `(site_key, version)`; partial unique index: one approved per site. |
| `0033_adaptive_regions` | `site_experience` | `site_key` PK, `regions_enabled` (default true). Later migrations add `bandit_enabled` (false), `max_arms` (2), `explore_pct` (10), `freeform_enabled` (true), `g3_daily_budget` (200), `g3_visitor_budget` (3), `review_sample_pct` (5), `g3_blocked_patterns` (text[]). |
| | `site_regions` | Slots: `name`, `label`, `purpose`, `components text[]`, `pages text[]`, `enabled`. |
| | `site_intent_families` | `slug`, `label`, `description`, `stage`, `rules` JSONB, `priority`, `enabled`, `updated_at`. |
| | `plan_cache` | `id, site_key, cache_key, family, persona, lang, page, regions text[], content_version, manifest_version, plan JSONB, composer (model\|rules), status (auto\|pinned\|blocked), hit_count, build_ms, created_at, last_hit_at`; index `(site_key, family, page, regions, status)`. `0036` adds `taste`, `arm`, `base_key`, `rewards` and index `(site_key, base_key)`. |
| `0034_region_test_subject` | — | Adds `regions` to the experiments subject check. |
| `0035_composed_pages` | `site_routes` | `pattern`, `title`, `purpose`, `enabled`, `priority`, `canonical_plan` (FK to `plan_cache`). `0037` adds `mode (composed\|freeform)` and `pinned_regions` JSONB. |
| | `site_entities` | `id, site_key, type, key, data JSONB, source (manual\|import\|connector:<id>), updated_at`; unique `(site_key, type, key)`. |
| | `site_connectors` | `kind (json_feed\|wordpress), name, url, entity_type, config JSONB, last_sync_at, last_status`. |
| `0036_taste_profiles` | `taste_profiles` | `(site_key, visitor_id)` PK with FK to `visitor_memories` `ON DELETE CASCADE`; `dims` JSONB, `interests` JSONB, `updated_at`. |
| | `plan_feedback` | `(site_key, plan_row, visitor, event ∈ engage\|convert)`: one reward per visitor, plan and event. |
| `0037_freeform` | `fragment_cache` | `purpose, component, region JSONB, conditions JSONB, content_version, manifest_version, status, source, hit_count, rewards, fingerprint`; index `(site_key, purpose, status)`. |
| | `g3_usage` | `(site_key, day, visitor)` PK, `fresh`. |
| | `review_samples` | A sampled free-form page: plan row, `flags text[]`, `status (new\|ok\|flagged)`; index `(site_key, status, created_at DESC)`. Also adds the `freeform` experiment subject. |
| `0038_agent_ready` | `agent_confirmations` | One-time codes: hash, site, plan, action, inputs digest, expiry, used. Also adds `plan_id` and `action` to `agent_requests`. |

`cortex/purge.purge_site` deletes all of these with the site, in foreign-key order
(`review_samples` and `site_routes` before `plan_cache`). `invalidate_site_caches` also
deletes `auto` rows of `plan_cache` and `fragment_cache`.

---

## 12. Widget SDK architecture

### 12.1 Builds (`fluid-buddha-sdk/build.mjs`, esbuild)

| Output | Format | Purpose |
|---|---|---|
| `dist/fluid-buddha.global.js` | IIFE `window.FluidBuddha`, minified | Script-tag install; auto-injects |
| `dist/fluid-buddha-particles.global.js` | IIFE | Three.js smoke field, fetched only for Level 2 |
| `dist/fluid-buddha-hi.global.js` | IIFE | Hindi strings, fetched for Hindi visitors |
| `dist/fluid-buddha.mjs` + `dist/chunks/*` | ESM with code splitting | Bundlers |
| `dist/fluid-buddha.cjs` | CJS | Node/bundlers without splitting |
| `dist/fluid-buddha-recap.global.js` | IIFE | Recap page renderer |
| `dist/fluid-buddha-page.global.js` | IIFE | Campaign page interactive sections + engagement |
| `dist/fluid-buddha-components.global.js` | IIFE | Component renderers, loaded on demand |
| `dist/fluid-buddha-regions.global.js` **(2.0)** | IIFE | `<fb-region>` controller, fetched when a page has regions |
| `dist/fluid-buddha-patcher.global.js` **(2.0)** | IIFE | Page renderer and plan patcher, fetched when a page or patch arrives |
| `dist/fluid-buddha-prefs.global.js` **(2.0)** | IIFE `FluidBuddhaPrefs` | Preferences panel |
| `dist/fluid-buddha-composed.global.js` **(2.0)** | IIFE `FluidBuddhaComposed` | Served pages: hydration, fetch forms, patches, flow steps, "Why this?", page-declared tools |
| `dist/index.d.ts` | Types | |

CSS lives in template strings (`ui/styles.ts`) and is minified at build time. Component renderers
load on demand. Per the handoff record, the core bundle measured 39.8 kB gzipped against a 42 kB
budget in 1.0. In 2.0 the page renderer moved out of the core into the patcher chunk; per the
build record the core is **38.6 kB** gzipped with regions, taste and the `fbvid` cookie
included.

### 12.2 Public API (`src/index.ts`)

`init(options)`, `conversion(name)`, `VERSION`, `FluidBuddhaElement` (`<fluid-buddha>`: `ask`,
`openPanel`, `close`, `toggle`), `Session`, `HostBridge`, `Canvas`, `preloadComponents`,
`STRINGS`, `pickLang`, `prepareLang`, `consentCopy`, `consentPrompt`, `callPrompt`,
`pageMatches`, `SpeechGate`, `packAudio`, `unpackAudio`, and protocol types. **(2.0)**
`configureRegions`, `FbRegionElement` (the `<fb-region>` element is defined on load), and
`VERSION = '2.0.0'`. `conversion(name)` also rewards the plans shown on the page.

### 12.3 Module map

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
| `core/Regions.ts` **(2.0)** | `<fb-region>` element, configuration, interaction tracking (core part). |
| `core/regions/controller.ts` **(2.0)** | One `POST /experience/regions` per page; `<slot>` fallback; shadow-root rendering with tokens; the retry and morph rule (fill only if no interaction yet or below the fold); `fluidbuddha:region` event; form posts to `/leads`. |
| `core/patch/patcher.ts` **(2.0)** | Applies `plan_patch` ops to any element with the matching `data-fb-plan`, with fade or highlight. The core only relays the patch as a window event. |
| `core/taste.ts` **(2.0)** | Session taste (`sessionStorage`), implicit events (mic, typing, media queries), the `fbtaste` cookie, plan rewards (`/experience/feedback`). |
| `core/taste/panel.ts` **(2.0)** | The preferences panel. |
| `core/why.ts` **(2.0)** | "Why this?" control and engagement rewards on regions and served pages. |
| `core/agentTools.ts` **(2.0)** | With `navigator.modelContext` (feature-detected): registers `read_view` and one tool per `data-fb-action` that opens its step, scrolls and focuses, never presses. |
| `composed.ts` **(2.0)** | Entry of the composed-page script. |
| `ui/page/customComponents.ts` **(2.0)** | Loads the customer bundle once as `<script type="module" integrity crossorigin="anonymous">`, creates `wc:` elements, sets props as properties after `customElements.whenDefined`. |
| `ui/page/steps.ts` **(2.0)** | Flow steps: one at a time, Back / "Next: <step>", step list as tabs (`aria-current="step"`), `#step-…` hash on served pages; all steps open in agent or plain mode. |

### 12.4 Browser storage keys

| Key | Storage | Use |
|---|---|---|
| `fluidbuddha:vid` | localStorage | Anonymous visitor id |
| consent key per site | localStorage | Consent version given |
| `fluidbuddha:trg:muted`, `fluidbuddha:visits`, `fluidbuddha:visit` | local/session storage | Trigger caps, visit counting |
| experiment arm cache | localStorage | 6 h |
| session taste **(2.0)** | sessionStorage | Taste profile for the session |
| `fbvid` **(2.0)** | first-party cookie, 180 days | Mirror of the visitor id for server-side delivery |
| `fbtaste` **(2.0)** | first-party session cookie | Compact taste for server-rendered pages |

Rendered markup carries stable addresses **(2.0)**: `data-fb-plan` on the page root,
`data-fb-region`, `data-fb-component`, `data-fb-state` and `data-fb-width` on each section,
`data-fb-action` on action controls, `data-fb-step` on flow steps and `data-fb-mode` in agent
or plain mode.

### 12.5 Isolation

All UI is in a Shadow DOM with `all: initial`. The widget never injects HTML from the model:
every component and page section maps typed JSON to DOM/SVG built with `textContent`. Iframe
embeds use `sandbox="allow-scripts"` with no referrer, and only accept messages from their own
frame. **(2.0)** A filled `<fb-region>` renders in its own shadow root. Customer Web
Components are the one place third-party code runs in the page: only from the bundle named in
the approved manifest, and only if its integrity hash matches.

---

## 13. Admin console architecture

- **Framework**: Next.js 16 App Router, React 19, client components; recharts for charts;
  qrcode for MFA setup.
- **Routes**: `/login`, `/register`, `/invite`, `/sso`, `/dashboard`, `/live`, `/team`,
  `/audit`, `/billing`, `/model`, `/licence`, `/security`, and `/websites/[id]/{install,
  ingestion, tour, insights, leads, cache, analytics, experiment, tests, triggers, campaigns,
  design, components, regions, pages, actions, agent, settings}`. `design`, `components`,
  `regions` and `pages` are new in 2.0. Previews of plans and reviewed pages are shown in
  sandboxed `srcdoc` iframes without scripts.
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

## 14. Install integrations

| Surface | Implementation |
|---|---|
| Loader | `/widget/loader.js` (inline in `routes/widget.py`): copies `data-*`, maps allowed query params, sets `data-backend`/`data-api` from its own URL, fires `fluidbuddha:ready`, guards double loading. `Cache-Control: public, max-age=300`, `Cross-Origin-Resource-Policy: cross-origin`. |
| Install code | `https://fbk_…@<server>` parsed by plugins and wrappers (`integrations/js/shared/loader.ts`). |
| WordPress | `integrations/wordpress/fluidbuddha/`: settings page (install code, hide-on paths), `wp_enqueue_scripts` with `async` and `data-key` via `script_loader_tag`, resource hints, connection check, uninstall hook. PHP 7.4+, WP 5.8+. |
| Shopify | Theme app extension block (`fluidbuddha.liquid`) with settings: install code, position, language, and whether to show on the cart and account pages. |
| Google Tag Manager | `integrations/gtm.py` builds a template in GTM export format; its only permission is injecting this server's loader; key pattern `^fbk_[A-Za-z0-9_-]+$`; includes GTM tests. |
| React / Vue | `@fluidbuddha/react`, `@fluidbuddha/vue`: load via the loader with `data-auto="false"`, then `FluidBuddha.init` with props/hooks; render nothing in place. **(2.0)** `<FbRegion name>` renders an `<fb-region>` with the children as fallback. |
| Next.js **(2.0)** | `@fluidbuddha/next`: `fetchComposedPage(opts, {path, searchParams})` (never throws; answers `notFound` with 502/504 on errors), `createPageHandler({installCode, basePath?, onNotFound?})`, `<ComposedPage page>`, `composedMetadata(page)` (title, description, canonical, robots, `alternates.types` for markdown), `renderComposedDocument`. Forwards UTM tags, search terms, referrer, user agent and the `fbtaste` and `fbvid` cookies. Node and Edge runtimes. |
| Edge worker **(2.0)** | `@fluidbuddha/edge`: `createEdgeHandler({installCode, origin, routes?, visitorCookieDays?})` returns `(Request) => Promise<Response>`. Composes matching GET paths, passes everything else, any path without a page and any failure to the origin, and sets `fbvid` (`SameSite=Lax; Secure`, 180 days) on a first visit, never for crawlers. |
| Shared core **(2.0)** | `integrations/js/shared/composed.ts`: framework-free fetch, document rendering, handler and cookie reading used by both packages. |
| Component authoring **(2.0)** | `@fluidbuddha/components`: `defineFbComponent(View, {id, tag, purpose, useWhen, props, styles})` wraps a React component as a custom element (clearing a server-rendered declarative fallback on upgrade), `manifestEntryFor`, `buildManifest`, and the `fb-manifest` CLI (`--module`, `--bundle-file`, `--bundle-url`) that writes the manifest with the bundle's sha384 hash. |
| Framer | Code component (`integrations/framer/FluidBuddha.tsx`). |
| Webflow | Footer custom code guide. |

---

## 15. Security architecture

### 15.1 Authentication

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

### 15.2 Authorisation

`app/auth/roles.py`: the minimum role is computed from the HTTP method and the route template
(first matching rule; reads → viewer, changes → editor, plus explicit rules). **(2.0)** One
new explicit rule: `POST …/manifest/versions/{v}/approve` needs Admin. All other generative
experience routes follow the default. The check runs
inside the `current_member` dependency, so every `/tenant` route is covered automatically, and a
test walks every route against the table.

### 15.3 Public surface protection

- Widget key resolves site and tier server-side; client-requested tier is ignored
  (`tier_locked`). Registered sites cannot be reached by site key alone.
- Origin allow-list: the request origin's host must equal the site's domain or be a subdomain
  (skipped in development, for sites without a domain, and for the platform's own host serving
  campaign pages).
- Rate limit per site (fixed window, Redis `INCR` with expiry or in-process), daily spend cap,
  plan cap. Separate per-endpoint limits for leads, recaps, action confirmations, campaigns and
  the agent endpoint.
- `tour_say` speaks only stored narration (no free TTS relay).
- **(2.0)** Generative experience endpoints: the widget key and origin are checked as for
  every public call; `/experience/page` also accepts server-side callers without an `Origin`
  (the key is the credential, and the response holds only what a visitor to that page would
  see); bots get no generated regions; per-site limits of 240 (regions), 600 (pages), 600
  (feedback) and 30 per visitor (taste) requests a minute; request bodies capped at 8 kB;
  model builds capped at 20 a minute per site and subject to the daily spend cap.
- **(2.0)** `/experience/lead` redirects only to a URL on the site's own domain (or with no
  host); otherwise it answers a plain thank-you page.
- **(2.0)** Agent actions: bearer token with the `actions` scope; one-time confirmation codes
  stored as hashes and bound to the plan, action and a digest of the inputs; destructive
  operations refused.
- Action amounts only from the price list; inputs validated server-side.

### 15.4 Outbound request safety (SSRF)

`tenancy/url_fetch.py` is used for URL sources, the crawler, lead and action webhooks, SSO
discovery/keys/token exchange and DNS-over-HTTPS:

- `http`/`https` only, no credentials in URLs;
- literal IPs and every resolved address must be global unicast (IPv4-mapped IPv6 unwrapped);
- redirects followed manually (max 3) and re-validated (webhooks: no redirects);
- size cap 2 MB (crawler PDFs 10 MB), timeout 15 s, allowed content types;
- environment proxies ignored;
- `INGEST_ALLOW_PRIVATE_URLS` disables address checks (development only).

### 15.5 Secrets

Fernet encryption (`app/security/secrets.py`) with `SECRETS_KEY` (comma-separated, newest
first, for rotation; derived from the JWT secret in development). Encrypted: SSO client secrets,
BYO model keys, action secrets, lead webhook signing secrets, Slack URLs and MFA seeds. Agent
tokens and invitation/recap tokens are stored as hashes or random tokens.

### 15.6 Signatures

| Signature | Algorithm |
|---|---|
| Outbound lead/action webhooks | `X-FluidBuddha-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "t.body")>` |
| Razorpay Checkout | HMAC-SHA256(`payment_id|subscription_id`, key secret) |
| Razorpay webhooks | HMAC-SHA256(raw body, webhook secret), constant-time compare; event ids stored |
| TURN credentials | username `<expiry>:<label>`, password `base64(HMAC-SHA1(TURN_SECRET, username))` |
| Licence | Ed25519 over `FBL1.<payload>`; public keys built in (`fb-2026-1`) |
| SSO ID token | RS256/384/512, ES256/384, PS256 against the provider's JWKS; iss, aud, exp, nonce checked |

### 15.7 Content security on hosted pages

Recap pages: CSP allows scripts only from the SDK origin and frames only from the site's custom
component origins; all values escaped; JSON blocks escape `<`. Campaign pages: own CSP, scripts
from own origins only, `frame-ancestors` restricted for embed mode. Status page: no scripts
(`default-src 'none'`). **(2.0)** Hosted composed pages (`/g/…`): `default-src 'none'`;
`script-src` limited to the SDK origin, the API origin and the customer bundle's origin;
`connect-src` the API plus `ws:`/`wss:`; inline styles only; `form-action` the API;
`frame-ancestors 'none'`; `base-uri 'none'`; `Cache-Control: private, no-store`. SSR escapes
every model- or data-supplied value and accepts only https URLs. Customer bundles load with
subresource integrity and `crossorigin="anonymous"`.

### 15.8 Compliance artefacts

`docs/compliance/`: SOC 2 control matrix mapping controls to code and evidence, and policies for
information security, access control, change management, incident response, business
continuity, data classification and retention, vendor management, acceptable use and risk
assessment, plus a sub-processor list and DPA template. CI runs gitleaks, `pip-audit` and
`npm audit`; Dependabot is configured.

---

## 16. Privacy engineering

| Mechanism | Implementation |
|---|---|
| PII masking | `trust/pii.py` `PiiVault`: regexes for email, card (Luhn), SSN, IBAN, phone; non-overlapping spans with priority; stable placeholders `<KIND_n>`; `unmask` only for lead capture and actions; `spoken()` and `stored()` forms. Serialised with the session (Redis TTL applies). |
| No visitor audio stored | Only transcripts and the agent's own TTS are persisted. |
| Consent | Server drops audio until `EVENTS/consent`; `consent_at` stored on the conversation. |
| Telemetry hygiene | Logs redact PII in transcripts; metrics have no tenant labels; spans carry no visitor text; Sentry strips bodies, cookies, query strings, auth headers, users and local variables. |
| Retention and erasure | `trust/retention.py` sweeps per-site windows; `erase_visitor(email)` deletes leads, their conversations and memory. |
| Memory | Opt-in per site and per visitor; built from masked transcripts; deleted on forget, off, erasure, retention or site deletion. |
| Taste **(2.0)** | Seven fixed presentation dimensions and interests only. Anonymous visitors: browser session only, sent with requests, never stored. Remembered visitors: `taste_profiles`, cascading from `visitor_memories`. The `fbtaste` cookie holds confident values only, no interests. |
| Visitor id cookie **(2.0)** | `fbvid` is the same anonymous id the widget already keeps for experiments, mirrored first-party so server-side delivery can keep a visitor's page stable. Free-form stable plans store a hash of it (`v:<hash>`). |
| Model isolation **(2.0)** | Bound API and record values are never placed in a model prompt or tool result. |

---

## 17. Multi-tenancy and isolation

- **Knowledge**: one CORTEX tree per site (`site_entity_id`); retrieval is scoped by entity.
- **Data**: every per-site row carries `site_key`; console routes resolve `website_id` through
  the member's account (`tenancy/deps.py: owned_website`), returning 404 otherwise.
- **Public paths**: the widget key decides the site; sessions are bound to their site; cached
  answers and audio are per site.
- **Configuration**: profile, design, actions, components and BYO provider are per site or per
  account, cached per site key.
- **Billing**: aggregated per account across its sites.
- **Generative experience (2.0)**: manifests, design systems, slots, goals, plans, routes,
  entities, connectors, fragments and reviews are all keyed by `site_key`; plan and fragment
  cache keys include the site; plan ids are looked up within the site.
- **Self-hosted limits**: sites and seats counted install-wide.

---

## 18. Background jobs

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

**(2.0)** The generative experience adds no scheduled job. Plan, page, arm and free-form
builds, and background intent classifications, run as `asyncio` tasks started by the request
that missed the cache, de-duplicated per key in process memory (`regions._building`,
`intent._model_inflight`). Two replicas may therefore build the same key once each; the
second write updates the same `plan_cache` row. Connector syncs run on demand from the
console.

Email outbox: exponential backoff (1, 2, 4 … 32 min), 6 attempts, rows stuck in `sending` for
10 min are re-queued (the only double-send case), idempotency keys (one digest per account and
ISO week, one invitation per token).

---

## 19. Observability

### 19.1 Logging

Text (`HH:MM:SS LEVEL logger [request_id] | message`) or JSON lines (`LOG_FORMAT=json`, UTC).
Every line carries the request id; voice lines also carry the session id. `cortex_memory` is held
at WARNING.

### 19.2 Metrics (`/metrics`)

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

### 19.3 Tracing and errors

OpenTelemetry (when `OTEL_EXPORTER_OTLP_ENDPOINT` is set): a span per HTTP request, `voice.turn`
/ `chat.turn` spans and `stage.*` children; OTLP/HTTP export. Sentry (when `SENTRY_DSN` is set):
scrubbed events tagged with the request id and `RELEASE`.

### 19.4 Health

`/readyz` runs checks in parallel with a 2 s timeout each. Critical: `db`, `migrations` (at head),
`redis` (when configured), `draining`. Non-critical (`degraded`): `scheduler`, `models` (engine
errors in the last 5 minutes), `email` (configured and outbox not backing up). Results set
`fb_ready{check}`.

### 19.5 Alerting (`deploy/monitoring/alerts.yml`)

Recording rules for 5xx ratio over 5 m, 30 m, 1 h and 6 h. Alerts: `FluidBuddhaDown`,
`FluidBuddhaNotReady`, `FluidBuddhaErrorBudgetFastBurn` (14.4× of 0.1 % over 1 h and 5 m),
`FluidBuddhaErrorBudgetSlowBurn` (6× over 6 h and 30 m), `FluidBuddhaDraining`,
`FluidBuddhaSlowFirstAudio` (p95 > 1.5 s), `FluidBuddhaVerySlowFirstAudio` (p95 > 3 s),
`FluidBuddhaSlowTurns` (p95 > 8 s), `FluidBuddhaModelErrors`, `FluidBuddhaJobFailing`,
`FluidBuddhaCostCapReached`, `FluidBuddhaCostCapNear`, `FluidBuddhaCrawlsFailing`. Each links to
a section of `docs/operations/incident-runbook.md`.

---

## 20. Reliability and scaling

| Concern | Mechanism |
|---|---|
| Several replicas | `REDIS_URL`: chat sessions (`fb:chat:<sid>`, sliding TTL), rate-limit windows (`fb:rl:<site>:<window>`), live events (`fb:live:` pub/sub relay). Without Redis, all are in-process (correct for one replica). Redis outages degrade to fresh sessions and local counting. |
| Voice affinity | Voice state lives on the socket; no Redis needed. |
| Migrations | Advisory-locked at start-up; `/readyz` fails if the schema is not at head. |
| Deploys | Drain (§9.6); widget reconnects; Caddy `stream_close_delay 5m` for WebSockets on reload. |
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

## 21. Deployment

### 21.1 Development (`backend/docker-compose.yml`)

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

### 21.2 Self-hosted (`deploy/selfhost/`)

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

### 21.3 Hosted service expectations

Managed Postgres with point-in-time recovery, Redis for multiple replicas, a load balancer that
honours `/readyz`, Prometheus scraping `/metrics` with `METRICS_TOKEN`, SMTP with SPF/DKIM, and
`PUBLIC_API_URL`, `CONSOLE_URL`, `WIDGET_SDK_BASE` set to public addresses.

---

## 22. Configuration reference

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
| Extreme tier and generative experience | `<SITE>_DESIGN_SYSTEM` / `DESIGN_SYSTEM_DIR`, `<SITE>_OPENAPI` / `OPENAPI_DIR`, `<SITE>_API_BASE_URL`, `<SITE>_API_AUTH`, and **(2.0)** `<SITE>_COMPONENT_MANIFEST` / `COMPONENT_MANIFEST_DIR` (a console-approved manifest and a console design system take precedence over files) |
| Marketing website **(2.0)** | `NEXT_PUBLIC_FB_LOADER_URL`, `NEXT_PUBLIC_FB_KEY`, `NEXT_PUBLIC_CONSOLE_URL`, `SANDBOX_API_URL` |
| Ingestion CLI | `HIREBUDDHA_CONTENT_DIR`, `BUDDHA_COGNITIVE_LAB_CONTENT_DIR`, `FLUIDBUDDHA_CONTENT_DIR`, `INGEST_ON_START`, `INGEST_SITE` |
| Console build | `NEXT_PUBLIC_API_BASE`, `NEXT_PUBLIC_WIDGET_BACKEND` |

Built-in demo site keys: `hirebuddha`, `buddha-cognitive-lab`, `fluidbuddha`,
`chantingbuddha`.

---

## 23. Testing and quality gates

| Suite | Scope |
|---|---|
| Backend (`backend/tests`, ~440 tests in 51 modules) | Envelope and transport, tools by tier, engine paths, cache and replay, admin CRUD and isolation, ingestion, tours, analytics, citations, CORS, cost alerts, email jobs, experiments and variant tests, insights v1/v2, install surfaces, languages, leads, licence, lifecycle guard, live takeover, migrations (no DDL in app code), observability, onboarding, public access, recaps, reliability (drain, readiness, status), security (sessions, cookies, CSRF, MFA, lockout, headers), self-host bundle, SSO, SSRF and tour, teams and roles (every route), templates, triggers, trust (PII, consent, retention), visitor memory, actions, agent endpoint, BYO model, campaigns. **(2.0)** `test_experience.py` (plan schema, id stability, source rules, bindings, limits), `test_experience_console.py` (design system, manifest versions, drafts), `test_regions.py`, `test_pages.py` (routes, SSR, canonical, `?fbv` surviving a background build, entities, connectors, patches), `test_personal.py` (taste, tunables, why, bandit), `test_freeform.py` (blocked routes, fragments, assembly, budget, review, crawlers get G2), `test_agent_ready.py` (detection, policies, JSON-LD, markdown, views, confirmation codes, MCP view tools, funnel). The last recorded full run: 436 passed, 2 skipped (need Redis), 1 environmental failure in the status-page test. Hermetic: `conftest.py` pins mock AI, empty payment keys and default prices. Needs Postgres + pgvector; Redis tests use `TEST_REDIS_URL`. |
| SDK (`test/smoke.mjs`, ~250 assertions; `test/inject.mjs`) | **(2.0)** stable `data-fb-*` attributes, Web Component loading, `<fb-region>` fill and morph rule, lazy page renderer, plan patches on the widget surface and on served pages, composed hydration and fetch forms, taste events and cookie, "Why this?", rewards, preferences panel, half width, flow steps, `fbvid`, page-declared tools. jsdom: element and Shadow DOM, envelope routing, all components, interactive state reporting, tier UI gating, Level 2/3 mounting, Extreme surface, persona veil, i18n coverage, embed contract; script-tag auto-injection. |
| Integrations | React/Vue wrappers with the real loader in jsdom (2.0: `FbRegion`); **(2.0)** `components.test.mjs`, `next.test.mjs`, `edge.test.mjs` (26 tests in the JS suite); Shopify Liquid render; WordPress PHP functions and lint. |
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

## 24. Statistics and algorithms

### 24.1 Experiments (`experiments/stats.py`, standard library only)

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

### 24.2 Lead score

`min(100, 20 + 10·[name] + 10·[company] + 10·[phone] + min(30, 10·questions) + 10·[persona] +
15·[buying keyword])`, plus recap first view +5 and +10 per forward.

### 24.3 Cost model (`analytics/pricing.py`)

`cost = asr_ms/60000·0.016 + tts_chars/1000·0.016 + fast_in/1000·0.000075 +
fast_out/1000·0.0003 + thinker_in/1000·0.0003 + thinker_out/1000·0.0025 + tool_calls·0.0002`
(USD; env-overridable). Tokens are estimated at 4 characters per token when the provider
reports none. BYO model cost is computed from account or list prices and stored separately.

### 24.4 Feature-request grouping (`insights/store.py`)

Greedy grouping against each group's first item: embedding cosine ≥ 0.82 when embeddings are
available (not in mock mode), otherwise word-overlap Jaccard on stop-word-filtered tokens.

### 24.5 Language detection (`i18n/detect.py`)

Devanagari characters → `hi`; Latin text with common Hindi words → `hinglish`; otherwise `en`;
explicit "in Hindi" / "in English" phrases set a preference.

### 24.6 Campaign number verification (`campaigns/compose.py`)

Numbers are extracted with `\d[\d,]*(?:\.\d+)?` from each section and must appear in the cited
source snippets or the campaign's own copy; otherwise the section is dropped and recorded in
`dropped`.

---

### 24.7 Plan bandit (`experience/bandit.py`) (2.0)

- Arms are `plan_cache` rows sharing a `base_key` with `status = 'auto'`; pulls =
  `hit_count`, wins = `min(rewards, pulls)`.
- `choose_arm`: one arm → that arm; with probability `explore_pct` % → a uniform pick;
  otherwise sample `Beta(1 + wins, 1 + pulls − wins)` per arm and take the highest (Thompson
  sampling with a uniform prior). Randomness from `random.SystemRandom`.
- `wants_new_arm`: `0 < arms < max_arms` and every arm has at least `MIN_PULLS = 30` pulls.
  The new arm is built under the key `<key>#arm<n>` with the first arm's outline as the
  thing to differ from.
- `reward_rate` = rewards / pulls (4 decimals).

### 24.8 Fragment scoring and assembly (`experience/freeform.py`) (2.0)

`score(fragment, intent, bucket, lang)`: +10 if pinned; +2 if written for the same goal, and
−1 (excluded) if written for another specific goal; excluded if the language differs; +1 if
the taste bucket matches; and, once it has views, `5 × rewards / views + ln(1 + views) / 4`.
Candidates are the newest 400 non-blocked fragments for the current content version (pinned
ones regardless of version) whose component is still in the manifest. `assemble`
keeps the best fragment per purpose, orders them by `PURPOSE_ORDER`, keeps at most 8, and
renames each region id to its purpose. Fewer than 3 regions is not served.

### 24.9 Taste confidence (`experience/taste.py`) (2.0)

Explicit: confidence 1, never changed by an implicit event. Implicit: a first observation
starts at 0.15; an event that agrees with the current value adds 0.15 (capped at 0.95); an
event that disagrees lowers the current value's confidence by 0.15 while it is above 0.15,
and replaces the value (at 0.15) once it is not. Confidence decays at read time with a
14-day half-life. A value counts at 0.5 or above, so an implicit preference needs about four
agreeing events. `bucket()` is `d:<density>` (only airy or compact) joined with
`f:<group>` (only tables or visual), giving at most nine buckets including the empty one.

### 24.10 Number check for generated copy (`experience/planner.py`, `page_planner.py`) (2.0)

As for campaign pages (§24.6): numbers matched by `\d[\d,.]*` in model-written props must
appear in the retrieved material; otherwise the plan fails enforcement and the fallback
composer is used.

---

## 25. Known technical limitations and risks

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
| Extreme tier | OpenAPI specs are configured by environment or files per site, not yet through the console. (Design systems and manifests moved to the console in 2.0.) |
| Generative experience: verification (2.0) | The model composers (region, page, free-form, `patch_plan`) and bandit variants were exercised with fake models and in mock mode only. |
| Generative experience: per-process state (2.0) | Build de-duplication, remembered intent classifications and family vectors live in process memory, so replicas can duplicate a build and do not share classifications. |
| Bindings (2.0) | Server-side only, with site-level credentials. User-token (client-side) binding, cache partitioning by data scope and write safety (dry-run, undo) are not built. `x-fb-cache`, `x-fb-entity` and `x-fb-pii` are parsed but not yet enforced. |
| Entities (2.0) | List bindings read up to 500 rows per type and filter in memory by string equality. |
| Connectors (2.0) | On-demand sync only; two kinds. |
| Customer components (2.0) | No event contract back to the agent. Site-derived drafts map only onto built-in renderers. |
| Agent identity (2.0) | `Signature-Agent` values and user agents are trusted as sent; Web Bot Auth signatures are not verified. Confirmation relies on the assistant asking its person. |
| Page-declared tools (2.0) | `navigator.modelContext` is a proposal still changing; tested against a stub. |
| Edge package (2.0) | Tested with fakes, not deployed on a real Workers runtime. |
| Review feed (2.0) | Flagging blocks every fragment the page used, including shared ones. |
| Naming (2.0) | The backend's FastAPI title is still "A2UI Orchestrator" and the website folder is spelt `fludi-buddha-website`. |
| Legacy coupling | The built-in `hirebuddha` profile, sitemap and markdown loader paths remain in code as the flagship demo. |

---

## 26. Marketing website

`fludi-buddha-website/` is FluidBuddha's own marketing site. It is a customer of the product,
not part of it.

| Part | Content |
|---|---|
| `web/` | Next.js 16.4 (App Router, Cache Components), React 19.3. Development port 3100. |
| `web/src/content/` | All copy: `site.ts` (navigation, footer, plans), `pages.ts` (template and legal pages), `home.ts` (film chapters and demo content, English and Hindi). |
| `web/src/app/` | `/` (home with a scroll-scrubbed JPEG frame film on a canvas), `/demo`, `/pricing`, `/legal/[slug]`, `/[...slug]` (every template page from `pages.ts`; unknown paths 404), `/hi`, `/hi/demo`, `/hi/pricing` (Hindi), `/api/sandbox` (forwards to `${SANDBOX_API_URL}/sandbox/start`; 503 without it). |
| Agent | `AgentLoader` loads the widget when `NEXT_PUBLIC_FB_LOADER_URL` and `NEXT_PUBLIC_FB_KEY` are set; the ask bar hands each question to `document.querySelector("fluid-buddha").ask()`. Without them the ask bar runs a scripted preview. `fb:ask` and `fb:answered` window events drive the demo chips. |
| `film/` | The rendered scroll film (frames are git-ignored and copied into `web/public/film/`). |
| `brand/` | Logo build script and assets. |
| `docs/marketing-docs/mockups/` | Static HTML concept mock-ups. |

Note: no `/sandbox/start` route exists in the backend at this commit, so the sandbox form
answers "being connected" until one is added.
