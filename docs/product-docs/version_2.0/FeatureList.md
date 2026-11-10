# FluidBuddha — Feature List (version 2.0)

> **How this document was made.** It was reverse-engineered from the source code on branch
> `main` (last commit `2306c72`, 10 November 2026, product version 2.0.0): the FastAPI backend
> (`backend/`), the `<fluid-buddha>` widget SDK (`fluid-buddha-sdk/`), the admin console
> (`fluid-buddha-frontend/`), the install integrations and framework packages
> (`integrations/`), the marketing website (`fludi-buddha-website/`) and the deployment
> bundles (`deploy/`). It lists what the code actually does, not what earlier plans or
> marketing copy promised. Where a feature has a known limit in the code, the limit is stated.
>
> **What changed since version 1.0.** Version 2.0 adds the **generative experience**: the
> product no longer only talks *on* a website, it composes parts of the website itself. New
> in 2.0: the Experience Plan and component manifest, data bindings, a console-managed design
> system, the customer's own Web Components, adaptive regions (`<fb-region>`), composed pages
> served through Next.js or an edge worker, structured records and content feeds, taste
> profiles with a visitor preferences panel, "Why this?" explanations, plan bandits,
> free-form per-visitor pages with budgets and a review feed, and agent-ready views with
> actions that AI assistants can run under the owner's confirmation rules. New items are
> marked **(2.0)**. [Section 8](#8-what-is-new-in-version-20) lists them in one place.
>
> Companion documents: [FunctionalSpecification.md](FunctionalSpecification.md) (behaviour and
> business rules in detail) and [TechnicalSpecification.md](TechnicalSpecification.md)
> (architecture, APIs, data model, operations).

---

## 1. What the product is

**FluidBuddha** turns a business website into a live, voice-first AI sales agent. The
business adds one `<script>` tag. A visitor can then talk to the website or type to it.
The agent (default name **Pragya**, renamable per site):

- answers out loud and in text, using only the site's own content, and cites its sources;
- draws diagrams, charts, comparison tables and interactive calculators while it speaks;
- moves the visitor around the site: it navigates, scrolls and spotlights sections;
- quietly re-themes the page for the visitor's segment (persona switching);
- gives a narrated guided tour;
- captures leads, proposes actions (payment links, quotes, trials, meetings) and hands hot
  conversations to a person on the team, including by live voice call.

From version 2.0 the same engine also **generates the website's own surface**. From the
business's approved components, design system and data it composes:

- **adaptive regions**: slots on existing pages (hero, proof, call to action) filled for the
  visitor's goal before they say anything;
- **composed pages**: whole pages for a route and a visitor goal, rendered on the server and
  served from the customer's own domain;
- **free-form pages**: a page for one visitor and one moment, assembled from reusable
  fragments within a budget and the owner's governance;
- **agent-ready views**: the same page as structured data, text and callable tools for AI
  assistants.

Around the agent sits a multi-tenant SaaS platform: self-serve onboarding by crawling the
site, an admin console with teams and SSO, insights into what visitors ask, causal A/B
measurement, billing, generated landing pages, an MCP endpoint for other AI assistants,
bring-your-own-model, and a self-hosted enterprise edition.

The internal engineering name of the backend is the **A2UI Orchestrator** ("Agent-to-UI",
the voice-first agentic UI framework). The written brand is **FluidBuddha**. The first
customer, and the built-in demo profile, is **HireBuddha**.

---

## 2. Main product pillars

| # | Pillar | One-line promise | Main capabilities |
|---|---|---|---|
| 1 | **Talks** — voice-first conversation | A natural spoken conversation with sub-second acknowledgement. | Streaming speech in and out, instant spoken ack while the answer is prepared, barge-in, sentence-streamed speech, English and Hindi. |
| 2 | **Shows** — generative UI | The agent draws what it explains. | 13 safe, typed components (flowcharts to ROI calculators), tenant-defined custom components, full runtime-generated pages (Extreme tier), live spoken reactions when the visitor plays with a component. |
| 3 | **Acts on the page** — agentic website control | The website moves with the conversation. | Navigation, scrolling, section spotlight, silent persona re-theming, narrated guided tours, proactive triggers. |
| 4 | **Never makes things up** — grounding and trust | Every factual answer comes from the site's own content. | CORTEX knowledge retrieval with a confidence guardrail, citations, PII masking, microphone consent, retention and erasure, medical safety mode, curated (pinned/blocked) answers. |
| 5 | **Turns traffic into revenue** — the revenue layer | Conversations become qualified pipeline. | Lead capture and scoring, signed webhooks and Slack alerts, confirmable actions (payment link, quote, trial, meeting, webhook), recap pages, live human takeover and voice handoff, generative landing pages. |
| 6 | **Proves its value** — measurement and insight | A dashboard that shows lift and what buyers want. | Holdout experiments with always-valid statistics, variant A/B tests, insights (top questions, knowledge gaps, objections, competitors, feature requests, buying signals), weekly digest, cost and latency analytics. |
| 7 | **Gets cheaper as it learns** — the economics engine | Repeat questions cost almost nothing. | Conversation cache with exact and semantic replay, byte-exact audio cache, lean/heavy hybrid routing, per-site spend caps and cost alerts. |
| 8 | **Composes the site itself** — generative experience **(2.0)** | The right page for each visitor, built only from approved parts. | Experience Plans checked by one validator, component manifest with source rules, data bindings to APIs and records, adaptive regions, composed pages with SSR and canonical URLs, free-form pages with budgets and review, taste profiles within brand limits, "Why this?", plan bandits. |
| 9 | **Readable and usable by AI agents** — agent-ready **(2.0)** | What a person sees, an assistant can read and act on. | Views as JSON (`fb.view/1`) and markdown, JSON-LD, MCP view tools, actions with `auto` / `confirm` / `never` policies and one-time confirmation codes, agent mode rendering, page-declared tools, task-completion analytics. |
| 10 | **Enterprise-ready platform** | Fits a security review and an enterprise rollout. | Teams and roles, OIDC SSO with domain proof, MFA, audit log, SOC 2 controls and policies, BYO model (Anthropic, OpenAI, Azure OpenAI), self-hosted edition with offline licence, 99.9 % SLA tooling, status page. |

---

## 3. Unique selling propositions (USPs)

1. **It talks, shows and acts at the same time.** Most website agents are text chat boxes.
   FluidBuddha speaks, draws an interactive diagram that is held in sync with the speech (the
   audio for an explanation waits until its diagram has rendered), and scrolls or navigates
   the page in the same turn. One multiplexed WebSocket carries audio, UI, page commands and
   state together.

2. **Latency masking by design.** A fast model writes a short spoken acknowledgement in well
   under a second while the grounded answer is prepared at the same time. Most turns take a
   *lean* path (one retrieval plus one fast generation). Only turns that need a diagram,
   navigation, numbers or an action go to the *heavy*, tool-using thinker. Speech is
   synthesised one sentence ahead of what is playing, so long answers have no gaps.

3. **Grounded, cited and guard-railed.** Answers come from a per-site knowledge tree
   (CORTEX on Postgres + pgvector). When retrieval confidence is below the threshold, the
   agent says it does not know and offers to connect the visitor with the team. Each answer
   carries its sources, which visitors can click to open the source page.

4. **The answer economics improve with traffic.** Every answered turn is cached. A repeat
   or near-identical question replays the stored answer, components and exact audio at
   near-zero model cost. Owners can pin "golden" answers and block questions.

5. **Three design levels from one script.** The same agent can appear as *The Companion* (a
   floating panel with a living light-form launcher), *The Presence* (an immersive,
   full-screen GPU smoke field) or *The Atmosphere* (no widget: the page itself glows,
   spotlights and captions).

6. **Measured causal lift, safe to read daily.** A built-in holdout keeps a share of visitors
   away from the agent and measures both groups on the site's own goal. The verdict uses an
   always-valid (mSPRT) interval, so checking the dashboard every day does not inflate false
   wins.

7. **From conversation to booked revenue, with the visitor in control.** The agent can
   propose a payment link, a quote, a trial or a meeting. Nothing runs until the visitor
   confirms on a card (or says "yes" out loud). Amounts always come from the owner's price
   list, never from the model.

8. **Built for India first, and global.** It supports English and Hindi (including Hinglish
   detection), Indian-English and Hindi speech, INR pricing with Razorpay subscriptions and
   UPI Autopay handling, and rupee formatting in calculators.

9. **Open to the agent ecosystem.** Each site can expose an MCP server, `llms.txt` and an
   OpenAPI "ask" endpoint, so other AI assistants can query the site's grounded agent.

10. **Enterprise optionality.** Customers can bring their own model provider, sign in with
    their own identity provider, and run the whole product on their own host with an offline,
    signed licence. Visitor-facing paths keep working even if the licence lapses.

11. **Generative pages that cannot go off-brand or off-fact (2.0).** The model never writes
    HTML or free-form UI. It writes a *plan*: an ordered list of components from the
    customer's approved manifest. One validator checks every plan from every source. Each
    prop has a source rule: `model_text` (the model may write short copy), `binding_only`
    (the value must come from the customer's API or records, so prices and plans are never
    typed by a model) or `either`. Numbers in model-written text must appear in the cited
    site material. Bound values never go back to the model.

12. **Personalisation that never slows the page (2.0).** A cache miss never waits for a
    model. The visitor gets the host's own content, the canonical page or a rules-composed
    page at once, and their plan is built in the background for the next view. Crawlers
    always get the host's content or the canonical page.

13. **One plan, three audiences (2.0).** The same Experience Plan is rendered for people
    (the widget, `<fb-region>`, server-rendered pages), for search engines (canonical pages
    with `index, follow` and JSON-LD) and for AI agents (structured views, markdown and
    tools). All three get the same facts, so there is no cloaking.

14. **Personal, with the visitor in charge (2.0).** Taste is limited to seven presentation
    dimensions (density, format, detail, modality, tone, motion, colour scheme). It is kept
    in the browser for the session and stored only for visitors who chose "Remember me".
    Visitors can open "Why this?" and a preferences panel, change any setting or reset it.
    Prices are never personalised.

15. **Agents may act, under the owner's rules (2.0).** Every action on a page has an agent
    policy: `auto`, `confirm` (the assistant must get its person's approval and return a
    one-time code bound to the same inputs within 10 minutes) or `never` (only a person on
    the page). Destructive operations are never open to agents.

---

## 4. Full feature catalogue

Each feature lists the module it lives in. "M2-x", "M3-x", "WSx" and "F-x" are the
engineering work-package tags used in the code comments.

### 4.1 Conversational agent (voice and text)

| Feature | What it does | Where |
|---|---|---|
| Voice conversation | Streams microphone audio over a WebSocket. The server or browser transcribes it, the agent answers with streamed speech. | `backend/app/transport/websocket.py`, `fluid-buddha-sdk/src/core/Session.ts` |
| Text chat and fallback | `POST /chat` runs the same agent loop. Used for typed questions and as the fallback when the socket fails. | `backend/app/routes/chat.py` |
| Instant spoken acknowledgement | The Fast Router returns intent, persona and an acknowledgement of 12 words or fewer, spoken at once. | `orchestrator/router.py` |
| Hybrid lean/heavy routing | Ordinary turns use one retrieval plus one generation. Turns about pricing, integrations or navigation, or that ask to show, compare, calculate, buy, book or tour, use the tool-using Heavy Thinker. | `orchestrator/lean.py`, `orchestrator/thinker.py` |
| Concurrent thinking | The answer is computed while the acknowledgement is being spoken. | `websocket.py` (`_respond_fresh`) |
| Sentence-streamed speech | Answers are split into sentences. The next sentence is synthesised while the current one plays. | `websocket.py` (`_speak`) |
| Barge-in | The visitor can interrupt the spoken answer. Speech during the acknowledgement is treated as the visitor finishing their sentence. | `websocket.py`, `audio/JitterBuffer.ts` |
| Utterance coalescing | A fragment that arrives within 10 s while a reply is still running is merged with the previous one. | `websocket.py` |
| Follow-up understanding | Short follow-ups ("how much is it?") are searched together with the earlier question. They are never cached. | `orchestrator/rewrite.py` |
| Page awareness | The agent knows the current page, the section in view and the page's scroll anchors. | `orchestrator/state.py`, `prompts.py` |
| Agent-initiated welcome | When opened, the agent greets the visitor about the current page, or speaks a fixed greeting. | `thinker.py` (`welcome`) |
| Adaptive persona | Infers the visitor's segment, switches only on a confident read, locks on self-identification, and asks at most one qualifying question every 3 turns. | `orchestrator/loop.py` |
| Live component reactions | When the visitor drags a slider or changes a tab, the agent says one short insight after a 0.7 s pause. | `websocket.py`, `thinker.py` (`react`) |
| Intelligence tiers | `basic`, `high`, `advance` (default) and `extreme` decide which tools the agent may use. The tier is set per website and enforced on the server. | `orchestrator/tools.py`, `tenancy/public_access.py` |
| English and Hindi | Script-based language detection, Hinglish detection, "reply in Hindi" preference, Hindi greetings and UI, Indian-English and Hindi speech recognition and synthesis. | `backend/app/i18n/`, `fluid-buddha-sdk/src/i18n/` |
| Binary audio frames | Audio travels as compact binary WebSocket frames instead of base64 JSON. | `transport/envelope.py`, `protocol.ts` |
| Voice activity detection with pre-roll | Energy VAD with hysteresis, plus a 400 ms pre-roll, so the first word is not clipped. Uses an AudioWorklet off the main thread. | `audio/SpeechGate.ts`, `audio/AudioCapture.ts` |

### 4.2 Generative UI

| Feature | What it does |
|---|---|
| 13 built-in components | flowchart, workflow, component diagram, graph, chart (bar/line/pie), ROI calculator, comparison table, mind map, timeline, sankey, configurator, scenario simulator, tabs. All are built from typed JSON. The model never sends HTML. |
| Interactive components | Mind map (expand/collapse, pan/zoom), configurator and scenario simulator (sliders, toggles and selects with live computed outputs using a safe arithmetic evaluator), tabs, timeline tooltips and sankey hover values. Interactions are reported to the agent. |
| Audio/UI sync | Speech for an explanation waits for its component to render. A soft filler tone plays if rendering takes more than 1.5 s. |
| In-place correction | When a component is on screen and the visitor corrects a number, the agent patches the component (with fade, count-up or highlight) instead of drawing a new one. |
| Site currency | Money components show the site's currency (default INR, ₹ with Indian grouping). |
| Custom components (tenant-defined) | **Template**: a props schema over a built-in base component. **Iframe**: the tenant's own https page in a locked-down sandbox with a fixed postMessage contract. |
| Runtime page generation (Extreme tier) | The agent composes a whole page as an Experience Plan **(2.0)**: up to 12 regions, each one component from the site's manifest (by default the 14 built-in sections: hero, feature grid, text, pricing table, chart, flowchart, enquiry form, CTA, media, testimonials, logos, FAQ, comparison, ROI calculator), themed with the brand's design tokens. The v1.0 `sections` form is still accepted. |
| Live data in generated pages **(2.0)** | A prop can be *bound* instead of written: `api:<operationId>` (a read operation), `entity:<Type>` (the site's records), `content:search` (knowledge snippets) or `ctx.<name>`. A small JSONPath subset, transforms (`count`, `first`, `limit`, `sort_by`) and a field map shape the result. A region whose required data is missing is not drawn. |
| Editing the page in conversation **(2.0)** | With a composed page on screen, the agent uses `patch_plan` to add, replace, remove or move regions by id (up to 8 operations) instead of building a new page. Only the changed regions are sent, with fade, highlight or count-up. |
| Site API calls (Extreme tier) | The agent can call operations declared in the site's OpenAPI spec. The base URL and auth come from server configuration. Calls are simulated when no base URL is set (using the spec's documented response example **(2.0)**). Operations may carry `x-fb-effect`, `x-fb-entity`, `x-fb-cache`, `x-fb-auth`, `x-fb-pii`, `x-fb-confirm` and `x-fb-agent` annotations **(2.0)**. |
| Citations | Every grounded answer shows a "Sources" row. Sources with a known page are clickable. |

### 4.3 Agentic page control

| Feature | What it does |
|---|---|
| Navigation | The agent sends the visitor to a real route. Guessed paths are snapped to the closest valid route or dropped, so the visitor never lands on a 404. SPA-aware (History API plus `popstate`, with a full page load as fallback). |
| Scrolling | Relative scrolling (down, up, top, bottom) or a jump to a named section. Sections are found by id, id substring or heading text. |
| Persona re-theming | Sets `data-fb-persona` on `<html>` behind a 300 ms blurred cross-fade, or calls the host's own hook. |
| Host hooks and events | `onNavigate`, `onScrollTo`, `onSetPersona` hooks. Every command also fires a cancelable `fluidbuddha:*` window event. |
| Guided tour | A 6–9 stop narrated tour, planned once from the site's pages. It opens with a welcome and ends on a concrete use-case with an illustrative time and money saving. Each move happens only after its narration finishes. Owners can edit or regenerate it. |
| Spotlight (Level 3) | Dims the page and rings the section the agent refers to. |
| Proactive triggers | Rules for when the agent speaks first: time on page, scroll depth, exit intent (desktop pointer and mobile fling) and return visit. Shown as a nudge bubble or by opening the agent. The agent can write the opener for each page. Capped per page view, per day and after a dismissal. |

### 4.4 Generative experience (2.0)

All of this section is new in version 2.0. The code lives in `backend/app/experience/`,
`backend/app/routes/{experience,regions,pages}.py`, the SDK's `core/regions`, `core/patch`,
`core/taste` and `composed.ts`, and the `@fluidbuddha/{components,next,edge}` packages.

**Foundations**

| Feature | What it does |
|---|---|
| Experience Plan (`fb.plan/1`) | The single description of a view: a plan id (`pl_…`), title, up to 12 ordered regions (id, component, props, optional half width), up to 8 actions (`action:<name>` or `api:<operationId>` with a confirm level of none, card or typed), an optional `split` layout and an optional flow of 2–5 steps. Region ids are stable slugs (`hero`, `hero-2`). |
| One validator for every source | Plans from the model, a cache, a pinned layout or the mock engine all pass the same validator. It never raises: it returns the safest plan it can build, the regions it dropped and problems worded so the model can fix its next call. |
| Component manifest | The only vocabulary a plan may use. Each entry has an id (`acme.PlanTable`), purpose, `use_when` / `avoid_when` hints, typed props with a source rule (`model_text`, `binding_only`, `either`), limits (required, max items, max length, enum) and a renderer. Up to 200 components and 40 props each. The default manifest is the 14 built-in sections as `fb.<type>`. |
| Manifest versions in the console | Drafts → approved (by an Admin) → archived. One approved version per site. Approved versions cannot be edited. A draft with problems cannot be approved. The console shows a diff against the approved version. |
| Draft manifests written for you | From a published **Storybook** (`index.json` v7+ or `stories.json` v6, with props from `argTypes` or an uploaded react-docgen file) or from the **live site** (section patterns counted across up to 8 pages and mapped to built-in renderers). Drafts never reach the planner until approved. |
| Customer Web Components | A manifest entry may use `renderer: "wc:<custom-element-tag>"`. The manifest names one https bundle with a subresource-integrity hash. The widget loads it once, creates the element and sets props as properties. A bundle whose hash does not match is never run. |
| `@fluidbuddha/components` | Wraps a React component as that Web Component and writes its manifest entry from the same typed declaration. The `fb-manifest` CLI writes the manifest with the bundle's sha384 hash. |
| Design system in the console | Brand name, logo, colours, typography, radius, brand voice, **tunables** (which of density, colour scheme, motion and type scale may vary, and to which values) and optional light and dark palettes. Loader order: console → file or environment → extracted from the site → default. |
| Data bindings | See §4.2. Calls run in parallel, one per distinct operation and parameters. A failed call affects only its own regions. Only read operations that do not need a signed-in user can be bound. |
| Structured records (entities) | Typed JSON records (`Product`, `Plan`, `CaseStudy`…) keyed by a slug. Added by hand, by importing JSON or CSV, or by a content feed. Up to 2,000 per type, 20 kB each. |
| Content feeds (connectors) | A generic **JSON feed** (items path, key field, field map) and a **WordPress** preset (`/wp-json/wp/v2/posts` or `pages`). Syncing upserts by key and removes records the feed no longer has. Sync is on demand. |

**Adaptive regions (G1)**

| Feature | What it does |
|---|---|
| `<fb-region name="hero">` | A slot on the customer's existing page. The host's own content stays as the fallback until a region is filled. All regions on a page are fetched in one request. A filled region renders in its own shadow root with the brand tokens. Also `<FbRegion>` for React and Vue. |
| Region slots | The owner declares each slot: name, label, purpose, allowed components and page patterns. |
| Silent intent resolver | Maps a visitor's signals (landing path, UTM tags, referrer, search terms) to one of the site's *visitor goals* (intent families) without waiting for a model: owner rules first (confidence 0.9), then embedding similarity (threshold 0.6), then the `general` goal, with a background model classification remembered for 24 hours for the next visitor with the same signals. |
| Goal suggestions and tester | The console suggests goals from the site's routes and personas, and a "try it" tool shows which goal a set of signals resolves to and why. |
| Region planner | The model writes one region per slot from that slot's allowed components, citing site material. A rules composer (hero, text, CTA, feature grid, FAQ) is used in mock mode, past 20 builds a minute or past the daily spend cap. It costs nothing and only quotes the material. |
| Plan cache | One plan per goal, persona, language, page, set of regions, content version, manifest version and taste bucket. Owners can **pin** a plan (always served for that goal and page) or **block** it. Re-ingesting content or approving a manifest starts fresh plans. |
| Never blocks first paint | On a cache miss the answer is "pending" with a retry time of 2.5 s and the plan is built in the background. The widget asks once more and fills a region then only if the visitor has not interacted yet or the region is below the fold. |
| Preview console | A plan browser by goal, persona and page with a script-free preview, plus generate, pin, block and delete. |

**Composed pages (G2)**

| Feature | What it does |
|---|---|
| Route registry | Patterns such as `/pricing`, `/products/:slug` and `/guides/*`, each with a title, purpose and priority. The most specific pattern wins. |
| Page planner | Composes a whole page for a route and a visitor goal from the most relevant manifest components (up to 16), the entity types it can bind and up to 3 exemplar outlines. One repair round sends problems back to the model. Fallbacks: the nearest cached plan → the route's canonical plan → a rules page (hero, intro, highlights, FAQ, call to action). |
| Server-side rendering | Semantic HTML that reads fully without JavaScript, themed by the design tokens. Interactive sections (chart, ROI calculator, enquiry form) render a readable fallback and are hydrated by a small script. Customer Web Components render with a declarative shadow root. |
| Canonical pages and SEO | Each route can have a **canonical plan**. Crawlers get it with `index, follow`. Generated variants get `noindex`. Every page carries `<link rel="canonical">` to its clean URL and JSON-LD built from its regions. |
| Shareable plan links | `?fbv=<plan_id>` restores one specific plan (shared links, back and forward), with data bound fresh. |
| Delivery through the customer's site | `@fluidbuddha/next` (a catch-all Route Handler, a `<ComposedPage>` server component and metadata helper), `@fluidbuddha/edge` (a standard `fetch` handler for Cloudflare Workers, Vercel or Netlify Edge, Deno and Bun that passes everything else to the origin) or the hosted shell `/g/{site}/{path}`. If FluidBuddha is slow or down, the origin's page is served. |
| Forms without JavaScript | Enquiry forms on a served page post to the server and return to the page. |

**Personal experience**

| Feature | What it does |
|---|---|
| Taste profile | Seven dimensions: density (airy, balanced, compact), format (prose, bullets, tables, charts, visuals), detail (summary, standard, deep), modality (voice, text, silent), tone, motion and colour scheme, plus up to 20 interests. Explicit choices have confidence 1 and are never overridden. Implicit evidence moves confidence by 0.15 per event and decays with a 14-day half-life. |
| Taste signals | Browser settings (reduced motion, colour scheme), how the visitor uses the agent (mic or typing), what they open (tables, charts, FAQ) and what they say ("keep it short", "show me a table", "more detail", "less clutter"). |
| Storage by identity level | Anonymous visitors: the profile lives in the browser for the session and travels with each request. Remembered visitors: stored on the server and deleted with their memory. |
| Tunables within brand limits | Taste changes design tokens only on axes the design system allows and only to allowed values: spacing for density, animation for motion, and the brand's own light or dark palette. |
| Taste-aware answers and plans | The planners and the agent get a short taste brief ("prefers tables, compact, short answers"). It shapes length and format, never facts or prices. |
| "Why this?" | Every served region and page carries up to three plain-language reasons ("You arrived from the 'pricing' campaign…", "You asked for short summaries"). A small control opens them and the preferences panel. |
| Preferences panel | "Your preferences" in the widget: see and change each setting, reset, and a link to "Forget me". Loaded on demand. |
| Plan bandits | Per cache key, up to 3 alternative plans. Serving picks one by Thompson sampling on rewards per view, with an exploration floor (default 10 %). A new alternative is built once each existing one has 30 views. Rewards are CTA clicks, form submits and `FluidBuddha.conversion()`, counted once per visitor and plan. Off by default. |

**Free-form pages (G3)**

| Feature | What it does |
|---|---|
| Per-visitor pages | A route set to *free-form* composes a page for one person and moment. Order: the visitor's stable page → a page **assembled** from cached fragments (no model) → a fresh model composition within budget → the composed (G2) page. |
| Fragment cache | Every region the model writes is stored as a reusable fragment, deduplicated by content and scored by goal, language, taste and reward rate. Owners can pin or block fragments. |
| Multi-step flows and split layouts | A plan may define a flow of 2–5 steps and half-width regions in a two-column grid. Without JavaScript every step is shown. With it, one step at a time with Back and Next. |
| Budgets | Fresh model pages are limited per site per day (default 200) and per visitor per day (default 3). Past the budget, visitors get an assembled page or the G2 page. |
| Governance | Free-form only on routes set to it, never on blocked patterns (default `/checkout*`, `/cart*`, `/legal*`, `/terms*`, `/privacy*`). **Pinned regions** (up to 6 per route, top or bottom) appear unchanged on every page. Crawlers and visitors without an id always get the G2 page. |
| Stability | A visitor's page for a route changes only when their goal, taste or the content changes. The widget mirrors its visitor id into a first-party `fbvid` cookie (180 days) so server-side delivery can keep it stable. |
| Review feed | A share of served pages (default 5 %) plus every page with an automatic flag (validator problems, dropped regions, fewer than 3 regions, no call to action, a missing pinned region). "Flag" blocks the page and its new fragments. |

### 4.5 Design levels (widget appearance)

| Level | Name | Experience |
|---|---|---|
| `level1` | **The Companion** (default) | A breathing "liquid light" launcher drawn on a 2D canvas, and a 392×580 molten-obsidian glass panel with avatar, status word, grounded badge, suggestion chips and a mic button with an energy ring. Full-screen on mobile. |
| `level2` | **The Presence** | A full-viewport Three.js curl-noise smoke field (8k–16k particles) that reacts to voice, an "Awaken" ring, a fading message column and a central glass drawing surface. Three.js loads only for this level. |
| `level3` | **The Atmosphere** | No widget. A breathing edge rim-light, page spotlight, ephemeral glass captions, and a ⌘K / Ctrl-K or light-mote summon. Pointer-transparent. |

All levels share one state-of-light language (dormant, listening, thinking, speaking) and
honour reduced motion, contrast preferences, focus rings and safe-area insets.

### 4.6 Knowledge and onboarding

| Feature | What it does |
|---|---|
| Crawl my website | Paste a URL. The crawler obeys `robots.txt`, seeds from the sitemap and follows same-site links breadth-first (default 25 pages, depth 2; hard caps 50 and 3). It reads linked PDFs and skips `noindex` pages. |
| One-job onboarding | Crawl → ingest → derive personas → extract brand design tokens, with live progress in the console. |
| Knowledge sources | Pasted text, URLs, uploaded files (PDF, DOCX, Markdown, TXT, HTML, CSV, JSON; up to 10 MB). Scanned PDFs are refused with a clear message. |
| Per-site knowledge tree | DOCUMENT → SECTION → CHUNK nodes with 768-dimension embeddings, isolated per site. |
| True deletion | Deleting a source removes its knowledge. Deleting a site removes all of its data. Changed knowledge clears cached answers (pinned and blocked ones stay). |
| Persona discovery | Audience URLs (`/for/…`, `/solutions/…`, `/industries/…`, and similar) become personas. With a real model, 2–4 are proposed from page titles. Up to 6. Never overwrites existing personas. |
| Brand extraction | Colours, fonts, corner radius, logo and name are read from the homepage CSS and metadata. |
| Agent profile | Agent name, company, brand voice, personas, sitemap routes, greeting (English and Hindi), starting persona, tour switch, competitors, recap call to action, languages, starter questions, site rules (guardrails), preferred components, lead fields, tour outline, currency and safety mode. |
| Vertical templates | B2B SaaS, Education, Real estate, Healthcare. One click sets voice, greeting, personas, starter questions, rules, triggers and suggested actions, without overwriting hand edits. |
| Install preview bookmarklet | Drops the widget onto any live page to preview it. |

### 4.7 Revenue layer

| Feature | What it does |
|---|---|
| Lead capture in conversation | The agent saves name, email, company and interest when the visitor asks to be contacted. The real email reaches the lead even though the model only saw a placeholder. |
| Enquiry forms | Forms post directly to the server and never pass through the model. |
| Lead scoring | A transparent 0–100 score (contact details, number of questions, known persona, buying intent), with a summary of what was asked. |
| Lead pipeline | Statuses new, contacted, qualified, won, lost. |
| Lead delivery | Signed webhook (HMAC-SHA256 with a timestamp) to Zapier, Make, a CRM or any endpoint. Slack alert for hot leads (score threshold, default 60). Test send. |
| Actions marketplace | Payment link (Razorpay on the tenant's own account), quote request (with a downloadable PDF), trial (signed call to the tenant's backend), meeting link (Calendly, Cal.com or plain URL, pre-filled) and generic signed webhook. Visitor-confirmed, rate-limited, run once. |
| Voice confirmation | A spoken "yes", "confirm", "haan" or "no", "cancel", "nahin" answers an open action card. |
| Recap pages | "Send me this" (typed or spoken) creates a branded, shareable page with the conversation's answers, redrawn components, sources and a call to action. It can be emailed. Views and forwards are counted and raise the lead score. |
| Live takeover | The team sees live visitors, watches conversations stream in, takes over (the agent pauses), replies and hands back (the agent learns what was said). |
| Voice handoff | The operator can call a voice visitor in the browser (WebRTC with a TURN relay). The visitor accepts, and the agent stops listening during the call. |
| Returning-visitor memory (opt-in) | Visitors who choose "Remember me" are welcomed back with what they asked last time. "Forget me" deletes it. Off by default per site. |
| Generative landing pages (campaigns) | A campaign brief becomes a hosted, server-rendered landing page composed from the site's knowledge, personalised by link parameters (persona, question, account, language, UTM), with an optional B version. Numbers and quotes are verified against sources. |

### 4.8 Measurement and insight

| Feature | What it does |
|---|---|
| Holdout experiment | Keeps 1–50 % of visitors (default 10 %) away from the agent and measures both groups on a goal page or a `FluidBuddha.conversion()` call. Bots are excluded. |
| Always-valid statistics | Wilson and Newcombe intervals, relative lift, z-test, and an mSPRT always-valid verdict ("significant", "trending" or "collecting"). Includes a sample-size planner. |
| Variant A/B tests | 2–4 versions of the greeting, triggers, tour, starting persona or design level, and from 2.0 **generated regions on or off** and **free-form pages on or off**, with an optional holdout and Bonferroni-split error budget. "Make default" promotes the winner. |
| Region and free-form tests **(2.0)** | A "Generated regions" test measures generated regions against the page's own content. A "Free-form pages" test measures per-visitor pages against composed pages. Both use the same enrolment, goal tracking and always-valid verdict. |
| Plan results **(2.0)** | Each cached plan shows its taste bucket, version (arm), views and reward rate. |
| Insights v1 | Conversations and transcripts, top questions, knowledge gaps (questions the agent could not ground), and the visitor-to-engaged funnel. |
| Insights v2 (deal signals) | Background classification of objections (price, security, integration, effort, trust, timing), competitor mentions, grouped feature requests (sendable to Slack, a webhook or email) and buying signals, with trends and linked examples. |
| Weekly digest | Monday 09:00 email in the account's time zone with the week's conversations, leads, top questions, gaps, objections, competitors, test results and cost. One-click unsubscribe. |
| Cost and performance analytics | Cost per stage (speech-to-text, text-to-speech, fast model, thinker model, tool calls) by day, hour or session. Latency p50/p95, cache hit rate, generated versus cached, and time to first audio. |
| Cost alerts | A per-site daily threshold, plus 80 % and 100 % of the daily spend cap. Sent to Slack and shown in the console once per day per kind. |
| Campaign analytics | Unique views, engaged and converted visitors by arm, persona and source, with a daily series and A/B verdict. |
| Agent traffic | Calls from AI assistants by tool and by assistant. |
| Agent task funnel **(2.0)** | Per assistant: read the site → opened a view → started an action → completed. Failure points by view and action, and leads that came from agents. |

### 4.9 Trust, privacy and safety

| Feature | What it does |
|---|---|
| PII masking | Emails, phone numbers, Luhn-valid card numbers, US SSNs and IBANs are replaced by placeholders before the model, the history or storage sees them. The agent says "your email" instead of reading it out. |
| Microphone consent | The widget explains what listening means, and the server drops microphone audio until consent is given. The consent time is stored. |
| Retention | Per-site windows for transcripts (default 90 days) and leads (kept until deleted by default). Recap links expire per site (default 90 days). An hourly sweep enforces them. |
| Erasure | Deletes one visitor's leads, conversations and memory by email. |
| Curated answers | Pin an approved answer (always replayed) or block a question (always answered fresh, never cached). |
| Medical safety mode | For healthcare sites, requests for diagnosis, treatment or dosage get a fixed polite refusal with an offer to book. Emergencies get emergency numbers. Rule-based, before any model call, in English, Hindi and Hinglish. |
| Site rules | Owner-written guardrails that override all other instructions. |
| Generation guardrails **(2.0)** | Source rules per prop, number checks against cited material, approval before a manifest is used, pin and block for plans and fragments, blocked route patterns, pinned regions, a review feed, and budgets for fresh model pages. |
| Visitor-held personalisation **(2.0)** | No taste is stored for anonymous visitors. No sensitive attributes are inferred. Prices are never personalised. Stored taste is deleted with the visitor's memory. |
| Abuse guard | Per-site rate limit (default 120 turns per minute), per-site daily spend cap, and Free-plan conversation cap. |
| Widget key and origin check | A site's widget key fixes its site and tier on the server, and the request origin must match the site's domain. |

### 4.10 Platform, security and administration

| Feature | What it does |
|---|---|
| Accounts, teams and roles | People are separate from accounts. Roles are Owner, Admin, Editor and Viewer, enforced centrally on every console route. Emailed invitations. Account switching. |
| Single sign-on | "Sign in with Google" for existing members. Each account can add its own OIDC provider (Okta, Entra, Auth0, Keycloak…) for email domains it proves with a DNS TXT record, with a default role and an optional "require SSO". |
| Sessions | Server-side sessions in an httpOnly cookie with a CSRF token. 60-minute idle and 12-hour absolute timeouts. Sign out everywhere. |
| Two-factor | TOTP with QR setup, replay protection and 10 recovery codes. An Owner can require it for the account. |
| Lockout | 10 wrong passwords or codes lock the person out for 15 minutes. |
| Audit log | Every successful console change plus sign-ins, kept one year, searchable, CSV export. |
| Access review | CSV of everyone with access, and a quarterly email to Owners and Admins. |
| Encrypted secrets | SSO client secrets, model keys, action keys, webhook and Slack secrets and 2FA seeds are encrypted with rotatable Fernet keys. |
| Billing | Free, Growth, Scale and Enterprise plans, priced per conversation, with Razorpay subscriptions, Checkout, overage add-ons and UPI Autopay handling. |
| Bring your own model | Anthropic, OpenAI or Azure OpenAI, with fast and thinker models, test connection, per-site switch, own prices and automatic fallback to the platform model. Voice and embeddings stay on Google. |
| Agent endpoint for AI assistants | MCP server (JSON-RPC over streamable HTTP), `llms.txt`, OpenAPI, REST ask and offerings. Scoped tokens for lead capture and actions. |
| Agent-ready views **(2.0)** | Each page as an `fb.view/1` JSON view (regions in order with stable ids and bound values, actions with their agent policy, JSON-LD, links) or as markdown, with a JSON Schema. MCP tools `list_views`, `get_view` (text, structured view and an embedded HTML resource) and, with an actions token, `run_view_action`. `llms.txt` lists every view. |
| Agent policies and confirmation **(2.0)** | `auto`, `confirm` or `never` per action, from the plan's confirm level and the API's `x-fb-agent` annotation. `confirm` returns a summary and a one-time code that works once, for the same inputs, within 10 minutes. |
| Agent mode and plain mode **(2.0)** | AI agents (known user agents, a `Signature-Agent` header or `?fbmode=agent`) get the canonical page rendered plainly: no motion, every flow step and FAQ answer shown. People can ask for the same with `?fbmode=plain`. |
| Page-declared tools **(2.0)** | Where a browser offers `navigator.modelContext`, a served page registers `read_view` and one tool per action that scrolls to and focuses the control. The person still presses it. |
| Self-hosted edition | One-host Docker Compose bundle (Caddy, backend, console, Postgres, Redis, optional TURN), backups with point-in-time recovery, upgrade scripts, air-gapped image transfer and an offline Ed25519-signed licence. |
| Reliability | Readiness checks, graceful voice drain on deploys, multi-replica state in Redis, a public status page with incidents, Prometheus metrics, alert rules with a runbook, optional OpenTelemetry tracing and Sentry. |
| Compliance pack | SOC 2 control matrix and policies (information security, access control, change management, incident response, business continuity, data classification and retention, vendor management, acceptable use, risk assessment), sub-processor list and DPA template. |

### 4.11 Install surfaces

| Surface | How |
|---|---|
| Plain snippet | `<script src="https://<server>/widget/loader.js" data-key="fbk_…" async></script>` |
| WordPress plugin | Settings → FluidBuddha → paste the install code. Never shown in wp-admin. Path patterns hide it on chosen pages. |
| Shopify | Theme app extension (App embeds): install code, position, language, and show or hide on cart and account pages. |
| Google Tag Manager | A server-generated custom template, or a Custom HTML tag. |
| Webflow, Framer | Guide plus a Framer code component. |
| React and Vue | `@fluidbuddha/react` and `@fluidbuddha/vue` components with navigation hooks, and `<FbRegion>` for generated regions **(2.0)**. |
| Next.js **(2.0)** | `@fluidbuddha/next`: composed and free-form pages served from the customer's own Next.js site (Node and Edge runtimes). |
| Edge worker **(2.0)** | `@fluidbuddha/edge`: a `fetch` handler in front of any site, no framework needed. |
| Component authoring **(2.0)** | `@fluidbuddha/components` and the `fb-manifest` CLI. |
| Region tag **(2.0)** | `<fb-region name="…">fallback</fb-region>` anywhere on a page that has the widget script. |
| Programmatic | `FluidBuddha.init({...})` or a `<fluid-buddha>` element. |

Everything except the key (tier, design, colour, greeting, languages, knowledge, triggers,
tests) is controlled from the console, so the site never needs editing again.

---

## 5. Intelligence tier matrix

| Capability | basic | high | advance (default) | extreme |
|---|:-:|:-:|:-:|:-:|
| Grounded answers with citations | ✅ | ✅ | ✅ | ✅ |
| Navigate and scroll | ✅ | ✅ | ✅ | ✅ |
| Lead capture and site actions | ✅ | ✅ | ✅ | ✅ |
| Spoken answers (TTS) | ❌ (text only) | ✅ | ✅ | ✅ |
| Silent persona switching tool | ❌ | ✅ | ✅ | ✅ |
| Generated and custom components, patching | ❌ | ❌ | ✅ | ✅ |
| Whole-page generation in the conversation | ❌ | ❌ | ❌ | ✅ |
| Editing a composed page in the conversation (`patch_plan`) **(2.0)** | ❌ | ❌ | ❌ | ✅ |
| Site API calls | ❌ | ❌ | ❌ | ✅ (if the site has an OpenAPI spec) |

Adaptive regions, composed pages, free-form pages, taste and agent-ready views **(2.0)** are
site-level switches, not tier features. They work at every tier because they are served by
their own endpoints (`/experience/…`, `/sites/{key}/views…`), not by the conversation's tool
set.

---

## 6. Commercial packaging (as coded)

| Plan | Price (INR, monthly) | Included conversations | Overage | Notes |
|---|---|---|---|---|
| Free | ₹0 | 100 | None (hard cap) | New conversations are refused once used. Ongoing ones may finish. |
| Growth | ₹33,000 | 2,000 | ₹17 each | Self-serve checkout. |
| Scale | ₹1,25,000 | 10,000 | ₹10 each | Self-serve checkout. |
| Enterprise | By arrangement | Unlimited | — | Set by hand. |

A *conversation* is a visitor session with at least one answered turn, counted across all of
an account's websites. Calls from AI assistants through the agent endpoint are not counted.
Prices and currency can be overridden by configuration.

Self-hosted licences can include or exclude these features: `byo_model`, `agent_access`,
`campaigns`, `sso` and `voice_handoff`. The generative experience has no licence feature of
its own in the code: regions, pages and free-form are available on every install, and
agent-ready views follow the `agent_access` feature.

Fresh free-form pages and generated plans use model calls that count towards the site's
daily spend cap. They are not billed as conversations.

---

## 7. Known limits worth stating to customers

- PII masking is pattern-based. Names and street addresses are not detected.
- With bring-your-own-model, speech and embeddings still run on Google Cloud (Vertex AI).
- Only English and Hindi are supported. The knowledge base is searched in English.
- The URL fetcher checks addresses at resolve time. A DNS-rebinding host could still switch
  addresses between the check and the connection (noted as residual risk in the code).
- The recorded load test met the 1.5 s p95 time-to-first-audio objective at 50 concurrent
  voice sessions (1.62 s, just above it) but not at 100 (5.93 s) or 200 (15.2 s) on the
  measured setup. Capacity planning should use more replicas.
- With `MOCK_AI=true` (the default for development) every model is a deterministic stub, so
  answer quality is not meaningful.
- **Generative experience (2.0):**
  - The model composers (regions, pages, free-form, `patch_plan`) were tested with fake
    models only. The recorded verification ran in mock mode.
  - OpenAPI specs are still configured by file or environment, not in the console.
  - Bindings resolve on the server with site-level credentials only. Operations that need a
    signed-in user cannot be bound, so pages cannot yet show a logged-in user's own data.
  - Content feeds sync on demand (no schedule) and there are two kinds (JSON feed, WordPress).
  - Background intent classifications and in-flight build tracking are held per replica.
  - Customer Web Components cannot yet send events back to the agent.
  - Agent identity is the user agent or `Signature-Agent` header as sent. Signatures are not
    verified yet. The confirmation step relies on the assistant asking its person.
  - Page-declared tools follow a browser proposal (`navigator.modelContext`) that is still
    changing, and were tested against a stub.
  - The edge package was tested with fakes, not on a real Workers runtime.
  - Flagging a reviewed page blocks every fragment it used, including ones other pages share.

---

## 8. What is new in version 2.0

| Area | New in 2.0 | Where |
|---|---|---|
| Plan and validator | `fb.plan/1`, one validator, stable region ids, flows, split layout | `experience/plan.py` |
| Manifest | Source rules, versions with approval, draft generation, Web Components | `experience/manifest.py`, `store.py`, `drafts.py` |
| Data | Bindings, entities, connectors, `x-fb-*` API annotations | `experience/binding.py`, `entities.py`, `apis/registry.py` |
| Design | Console-managed design system, tunables, light and dark palettes | `routes/experience.py`, `design/system.py` |
| Regions (G1) | `<fb-region>`, slots, visitor goals, region planner, plan cache, pin and block | `experience/regions.py`, `intent.py`, `planner.py` |
| Pages (G2) | Routes, page planner, SSR, canonical plans, `?fbv`, hosted shell | `experience/pages.py`, `page_planner.py`, `ssr.py` |
| Conversation edits | `patch_plan` tool and `DATA/plan_patch` | `experience/patch.py`, `orchestrator/thinker.py` |
| Personal | Taste, tunables, "Why this?", preferences panel, bandits | `experience/taste.py`, `personal.py`, `bandit.py` |
| Free-form (G3) | Fragments, assembling planner, budgets, pinned regions, review feed | `experience/freeform.py` |
| Agent-ready | Views, markdown, JSON-LD, policies, confirmation codes, agent mode, task funnel | `experience/agentview.py`, `agents/views.py` |
| Experiments | Subjects `regions` and `freeform` | `experiments/store.py` |
| SDK | On-demand chunks for regions, patcher, preferences and the composed-page script. Core bundle 38.6 kB gzipped | `fluid-buddha-sdk/` |
| Packages | `@fluidbuddha/components`, `@fluidbuddha/next`, `@fluidbuddha/edge`, `<FbRegion>` | `integrations/js/` |
| Console | Design, Components, Regions and Pages tabs. Agent access shows views, policies and the task funnel | `fluid-buddha-frontend/` |
| Marketing website | Next.js site with a scroll film, an ask bar wired to the agent, and Hindi pages | `fludi-buddha-website/` |
| Version | Backend, SDK, console, framework packages and WordPress plugin report 2.0.0 | — |
