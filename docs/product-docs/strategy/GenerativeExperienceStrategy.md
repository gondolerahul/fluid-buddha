# FluidBuddha — Generative Experience Strategy

> **Status:** Strategy draft with product decisions recorded (§10.1). Not yet a committed
> delivery plan.
> **Date:** 6 November 2026 (decisions recorded the same day).
> **Naming:** the backend formerly called the "A2UI Orchestrator" is now the **FluidBuddha
> Orchestrator** (decision D10, §11.4). "A2UI" in this document refers only to Google's
> external protocol of that name (§11.3).
> **Baseline:** FluidBuddha v1.0 as described in
> [FeatureList.md](../version_1.0/FeatureList.md),
> [FunctionalSpecification.md](../version_1.0/FunctionalSpecification.md) and
> [TechnicalSpecification.md](../version_1.0/TechnicalSpecification.md) (branch
> `m2/foundations`, commit `12e325e`).
>
> **Question this document answers:** How can FluidBuddha be adapted to fully support:
>
> 1. **Generative UI.** The whole UI is generated at runtime from the visitor's intent, using
>    a set of APIs, content and a design system that the website owner supplies.
> 2. **A completely personal experience.** The UI suits the taste of each individual user.
> 3. **An agent-ready UI.** The same UI works well for both humans and AI agents.
> 4. **SaaS applications.** Can a product built for websites serve the UI of a SaaS
>    application, or does that need major remodelling?
>
> Names marked *(proposed)* do not exist in the code today.

---

## Table of contents

1. [Summary](#1-summary)
2. [Where v1.0 stands](#2-where-v10-stands)
3. [The unifying architecture: Intent → Plan → Bind → Render](#3-the-unifying-architecture-intent--plan--bind--render)
4. [Pillar 1 — Generative UI](#4-pillar-1--generative-ui)
5. [Pillar 2 — Personal experience](#5-pillar-2--personal-experience)
6. [Pillar 3 — Agent-ready UI](#6-pillar-3--agent-ready-ui)
7. [Pillar 4 — Adapting to SaaS applications](#7-pillar-4--adapting-to-saas-applications)
8. [Cross-cutting concerns](#8-cross-cutting-concerns)
9. [Phased roadmap](#9-phased-roadmap)
10. [Decisions and open questions](#10-decisions-and-open-questions)
11. [Appendices](#11-appendices)

---

## 1. Summary

### 1.1 The short answer

FluidBuddha is closer to this vision than it first looks. The **Extreme tier** already does
the following:

- composes whole pages from typed sections themed with brand design tokens (`generate_page`,
  `orchestrator/pagegen.py`);
- calls the site's own APIs from its OpenAPI spec (`call_site_api`, `backend/app/apis/`);
- answers from the site's own content (CORTEX);
- personalises by segment (personas, silent re-theming);
- builds server-rendered landing pages personalised from link parameters, with number
  verification (campaigns);
- exposes itself to other AI assistants (MCP server, `llms.txt`, OpenAPI ask endpoint).

What is missing is mostly not new technology. It is **three changes in the product's core
assumptions**:

| From (v1.0) | To (vision) |
|---|---|
| An **overlay** that sits on top of the customer's website | The website's **renderer**: the page itself is generated |
| **Segments** (up to 6 personas per site) | **Individuals**, each with a taste profile |
| **Anonymous visitors** and one shared credential per site | **Known users** with their own identity, permissions and data |

### 1.2 One architecture serves all four ideas

The four ideas need the same thing at the centre: a typed, validated **Experience Plan**
*(proposed)*, meaning a description of what to show, built from the customer's own
components, with data **bound** to the customer's APIs rather than written by the model.

```
 intent signals ──► Intent ──► Plan ──► Bind ──┬──► Render for humans (SSR + hydrate)
 (URL, query, talk,          (typed,   (live    │
  memory, taste)              cached)   data)   └──► Serve to agents (plan + actions as tools)
```

- **Idea 1 (generative UI)** is the pipeline itself.
- **Idea 2 (personalisation)** is an input to the planner (the taste profile) plus brand-safe
  tunable settings in the design system.
- **Idea 3 (agent-ready)** comes from serving the same plan to agents as structured data
  and tools.
- **Idea 4 (SaaS)** adds a per-user identity and data-governance layer under the bind
  step. Because the plan holds *structure* and the bind step holds *data*, plans can be
  cached and shared across users while data stays per user.

### 1.3 Verdicts at a glance

| Idea | Fit with v1.0 | What exists | Main new work | Size* | Main risk |
|---|---|---|---|---|---|
| 1. Generative UI (sold as G3) | High | `generate_page`, `call_site_api`, design tokens, campaigns, answer cache | Customer component manifest, intent inference without conversation, data binding, plan and fragment caches, SSR-first rendering, governance console | L | Latency, cost, brand QA and SEO if done naively |
| 2. Personal experience | Medium | Personas, re-theming, opt-in visitor memory | Taste profile, brand-bounded tunables, consent and controls | M | Privacy, regulation, creepiness |
| 3. Agent-ready UI | High | MCP server, `llms.txt`, OpenAPI ask, scoped tokens, agent traffic analytics | Stable IDs, semantic layer, plan-as-API, actions as tools, agent mode | M | Generated layouts break agents that rely on brittle selectors |
| 4. SaaS | Medium | Whole orchestrator, components, tours, triggers, takeover, insights, React SDK | Delegated user auth, permission-aware calls, cache partitioning, app-context API, safe writes, new pricing | L | Cross-user data leaks through the cache or a shared credential |

\* Rough relative size (S/M/L), not an estimate.

**On SaaS specifically:** it does not need a rewrite. The cognitive loop, typed components,
message stream (envelopes), SDK, tours, triggers, takeover and insights carry over. The
**identity and trust layer** is the part that must be rebuilt (§7). SaaS ships as part of the
same product, SKU and price list as websites, and stays voice-first (§10.1, D7 and D9).

### 1.4 Key decisions

The full list is in §10.1. The ones that shape the product most:

- **Sell free-form generation (G3); start pilots on adaptive slots (G1).**
- **One platform, one SKU, one uniform price list** for websites and SaaS apps.
- **Voice-first everywhere**, including inside SaaS apps.
- **Web Components** as the runtime contract for customer components; **Next.js adapter**
  first for hosted pages.
- **Client-side data binding by default** in SaaS.
- Backend renamed to the **FluidBuddha Orchestrator**.

---

## 2. Where v1.0 stands

### 2.1 Assets we can reuse

| Asset in v1.0 | Where | Role in the vision |
|---|---|---|
| Whole-page generation (≤ 12 sections from 14 types, design tokens) | `orchestrator/pagegen.py`, `DATA/render_page`, SDK `PageRenderer` | Becomes the planner, but over the *customer's* components |
| Design-system loader | `backend/app/design/` (env or files per site) | Becomes the design-system package, managed in the console |
| Site API calls from OpenAPI | `backend/app/apis/`, `call_site_api` | Becomes the API catalogue and the data-binding source |
| 13 typed components plus custom components (template and iframe) | `components.py`, `custom_components.py` | Start of the component manifest |
| In-place patching (`patch_component`, animations) | `thinker.py`, `DATA/patch` | Becomes *plan patches*: the conversation edits the page |
| Answer cache with exact and semantic replay, pinned and blocked | `cortex/episodic.py` | Model for the **plan cache** and **pinned layouts** |
| Campaign composer (number verification, cached per arm/persona/question/language/content version, SSR) | `backend/app/campaigns/`, FR-CAMP-01…08 | Closest existing thing to "generate a page from intent at first load" |
| Personas, adaptive persona inference, silent re-theming | `orchestrator/loop.py`, `HostBridge` | Seed for personalisation (segment priors) |
| Returning-visitor memory (opt-in) | `backend/app/memory/`, `visitor_memories` | Seed for a persistent taste profile |
| Page awareness (page, section, anchors via `STATE/sync`) | `orchestrator/state.py` | Seed for the SaaS app-context API |
| Confirmable actions (visitor confirms; amounts from the price list) | `backend/app/actions/` | Safe-write pattern for agents and SaaS |
| MCP server, `llms.txt`, OpenAPI ask, scoped tokens, agent traffic | `backend/app/agents/` | Agent surface for idea 3 |
| Holdout and variant tests with always-valid statistics | `backend/app/experiments/` | Proves that generated beats static |
| Teams, roles, SSO, audit log, encrypted secrets, self-host | `auth/`, `audit.py`, `licence/` | Enterprise base for the SaaS version |
| React and Vue packages | `integrations/js/{react,vue}` | Delivery path for SaaS embedding and customer components |

### 2.2 Assumptions in v1.0 that block the vision

| # | v1.0 assumption | Why it blocks | Fixed in |
|---|---|---|---|
| A1 | FluidBuddha is a **guest** on the customer's page. Generated UI lives in a panel or an Extreme surface. | Generative UI needs FluidBuddha to *be* the page. | §4.7 |
| A2 | Intent comes from **what the visitor says or types**. | Most visitors never talk. The first page must come from silent signals. | §4.4 |
| A3 | Components and sections are **FluidBuddha's**. | The customer's design system must be the vocabulary. | §4.2 |
| A4 | API results go **back to the model**, which then writes the answer. | Numbers and records must reach the UI without passing through the model. | §4.6 |
| A5 | API base URL and auth are **one server credential per site** (`<SITE>_API_AUTH`). | SaaS calls must run as the user, with the user's permissions. | §7.3.1 |
| A6 | The answer cache is keyed by **site, persona, page and language**. | Personal or user-data answers must never replay to another person. | §7.3.4 |
| A7 | Personalisation is **segment-level** (≤ 6 personas). | "Suited to my taste" is individual. | §5 |
| A8 | Design systems and OpenAPI specs are **set by env or files**, not the console. | Customers must supply them self-serve. | §4.2 |
| A9 | Navigation snaps to a **flat list of sitemap routes**. | SaaS routes have parameters (`/projects/:id`), and generated views need their own URLs. | §4.10, §7.3.6 |
| A10 | Success means **leads and conversion lift**. | SaaS buyers judge activation, task completion and support deflection. | §7.3.10 |

---

## 3. The unifying architecture: Intent → Plan → Bind → Render

### 3.1 Pipeline

```
                    ┌──────────────────────── Customer-supplied inputs ────────────────────────┐
                    │ Design-system package │ API catalogue │ Content (CORTEX + entities) │ Policies │
                    └───────────┬───────────┴───────┬───────┴──────────────┬──────────────┴────┬─────┘
                                │                   │                      │                   │
 Signals ──► ① Intent ──► ② Plan lookup ──hit──► ④ Bind ──► ⑤ Validate ──► ⑥ Render ──► human (HTML + hydrate)
 URL, query,   resolver     (plan cache,  │        (live API    (schema,     SSR / SDK   ──► agent (plan JSON,
 referrer,     (rules +     pinned        │         data, CORTEX  a11y, brand,               JSON-LD, tools)
 UTM, talk,    embeddings   layouts)      miss      citations)    must/never)
 memory,       + small                    ▼
 taste,        model)            ③ Planner (fast model, constrained to the plan schema
 app context                         and the component manifest; fallback = default plan)
                                          │
 Conversation (voice/text) ─────────────► Plan patches (add / replace / remove regions, like patch_component)
```

### 3.2 Principles

1. **Never block first paint on a model call.** First paint comes from a cached plan, a
   pinned layout or the owner's default page. Fresh plans improve the page afterwards
   (§4.7.3).
2. **The model chooses; it does not write data.** The model picks components, order,
   wording and bindings. Prices, records, stock, dates and user data come from APIs or
   verified content at bind time. This generalises v1.0's rule that "amounts always come
   from the price list".
3. **Structure is shareable; data is personal.** Plans are cached and reused across
   visitors. Data is bound per request, with the requester's own credentials (§7.3.4).
4. **The customer's design system is the only vocabulary.** The planner can use only
   components the customer registered, with the props they declared.
5. **One plan, two audiences.** Every plan renders for humans and serves to agents from the
   same source (§6.2).
6. **Everything is checked before it ships.** Schema, accessibility, brand rules and
   must-show / never-show policies run on every plan, cached or fresh (§4.11).
7. **Prove it.** Every generative surface can run against a static control (holdout).

### 3.3 The Experience Plan *(proposed)*

A plan is a small JSON document. It is the contract between planner, renderer, cache,
agents and analytics.

```json
{
  "plan_id": "pl_7f3a9c21d0",
  "schema": "fb.plan/1",
  "site_key": "acme",
  "intent": {
    "goal": "compare_plans",
    "stage": "evaluate",
    "entities": ["plan:scale", "competitor:rivalco"],
    "confidence": 0.81,
    "signals": ["utm_campaign=pricing", "referrer_query~'acme vs rivalco'"]
  },
  "audience": {
    "persona": "hr_head",
    "taste": { "density": "compact", "format": "table", "detail": "high" }
  },
  "layout": "acme.layouts.TwoColumn",
  "theme": { "base": "brand", "tunables": { "density": "compact", "scheme": "dark" } },
  "regions": [
    {
      "id": "hero",
      "component": "acme.Hero",
      "props": {
        "headline": { "text": "Acme vs RivalCo, side by side", "cite": ["doc_12#s3"] },
        "primaryAction": { "action": "start_trial" }
      }
    },
    {
      "id": "plans",
      "component": "acme.PlanComparison",
      "props": {
        "plans": { "bind": "api:listPlans", "path": "$.plans[*]", "params": { "currency": "ctx.currency" } },
        "highlight": "scale"
      }
    },
    {
      "id": "faq",
      "component": "acme.FAQ",
      "props": { "items": { "bind": "content:faq", "query": "switching from rivalco", "limit": 5 } }
    }
  ],
  "actions": [
    { "id": "start_trial", "ref": "action:trial", "confirm": "card" },
    { "id": "talk_to_sales", "ref": "action:meeting", "confirm": "card" }
  ],
  "policies": { "must_include": ["acme.LegalFooter"], "applied": ["no_competitor_logos"] },
  "provenance": { "source": "cache|planner|pinned|default", "model": "fast", "content_version": "cv_0193" }
}
```

Notes:

- `bind` values are **references, not values**. They are resolved in step ④.
- `text` props written by the model must carry `cite` entries. Unverifiable factual text is
  dropped, as campaign pages already do (FR-CAMP-04).
- `actions` refer to existing v1.0 actions (payment link, quote, trial, meeting, webhook) or
  to write operations in the API catalogue.
- `regions[].id` values are **stable across plans** for the same intent family. Agents and
  analytics depend on that (§6.3).

### 3.4 How v1.0 modules map onto the pipeline

| Stage | v1.0 starting point | Change |
|---|---|---|
| ① Intent resolver | Fast Router intents, adaptive persona, campaign link parameters | New silent-signal resolver; intent families defined per site |
| ② Plan lookup | `conversation_cache` exact and semantic replay, campaign page cache | New `plan_cache` keyed by intent family, persona, taste bucket, language, content version and design-system version |
| ③ Planner | `generate_page` + `build_extreme_brief` | Constrained to the plan schema and the customer manifest; works without a conversation |
| ④ Bind | `call_site_api` (result to model) | Result goes straight to the UI; the model never sees bound values |
| ⑤ Validate | `normalize_page`, `validate_props`, campaign number checks | Adds accessibility, brand and policy checks |
| ⑥ Render | SDK `PageRenderer`, campaign SSR (`slots.ts`, `page.ts`) | SSR-first page renderer for customer components; agent serialiser |
| Patches | `patch_component`, `DATA/patch` | `DATA/plan_patch` *(proposed)* for region-level changes |

---

## 4. Pillar 1 — Generative UI

### 4.1 What "generative UI" should mean for customers

"Generate everything from scratch on every visit" is the most demanding reading and rarely
the best product. We propose three levels, all on the same pipeline, selectable per site
and per page area:

| Level | Name | What is generated | Good for |
|---|---|---|---|
| **G1** | *Adaptive slots* | Selected regions inside a fixed, hand-built page (hero, proof, CTA, FAQ) | **Where pilots start**; existing sites; lowest risk; fastest proof |
| **G2** | *Composed pages* | Whole pages composed from the customer's components; plans cached by intent | The stepping stone to G3; the fallback for regulated routes |
| **G3** | *Free-form* | Pages and flows composed on the fly per person, including new layouts | **What we sell**: the full product promise |

**Decision D1:** FluidBuddha **sells G3**, a UI generated at runtime for each person, and
**starts pilots on G1**. A typical customer journey is G1 (prove lift on a few regions) →
G2 (whole pages for chosen intent families) → G3 (free-form across the site), with any route
the owner marks as G1/G2-only staying there (Q14). The same engine powers all three levels,
so the levels are rollout stages and per-route settings, not separate products. §4.14
describes what G3 needs beyond G2.

### 4.2 What the customer supplies

#### 4.2.1 Design-system package *(proposed)*

Uploaded or synced through the console (replacing `<SITE>_DESIGN_SYSTEM` env and files,
assumption A8).

| Part | Content | Notes |
|---|---|---|
| **Tokens** | Colour, type scale, spacing, radius, elevation, motion, breakpoints | W3C Design Tokens format; brand extraction in onboarding can pre-fill it |
| **Tunables** | Which tokens may vary per person, and within what range (density, scheme, type scale, motion) | The brand-safe limits for personalisation (§5.4) |
| **Component manifest** | Every component the planner may use (see 4.2.2) | Heart of the package |
| **Layouts** | Page templates and region grids (`TwoColumn`, `Landing`, `Article`, `Dashboard`) | Planner picks a layout, then fills regions |
| **Composition rules** | "One hero per page", "pricing needs a disclaimer", "max 2 CTAs above the fold" | Enforced by the validator |
| **Component bundle** | The real component code, served from the customer's CDN or uploaded | Rendered by the SDK and by SSR. **Decision D2:** every component is delivered as a **Web Component** (the runtime contract). Customers author in React, Vue, Svelte or plain JS and use a FluidBuddha **framework adapter** to compile and wrap their components as Web Components with a manifest entry |

#### 4.2.2 Component manifest entry *(proposed)*

```yaml
id: acme.PlanComparison
version: 3
purpose: Compare 2–4 subscription plans feature by feature.
use_when: [compare_plans, pricing_question, evaluate_stage]
avoid_when: [support, existing_customer_billing]
props:
  plans:
    type: array
    max_items: 4
    items: { $ref: "#/entities/Plan" }
    source: binding_only         # the model may not write this; it must be bound
  highlight:
    type: string
    enum_from: "plans[*].id"
  caption:
    type: string
    max_length: 120
    source: model_text           # model may write; must carry a citation if factual
slots: [footnote]
actions: [select_plan]
a11y: { role: table, requires: [caption] }
agent:
  entity: Plan
  summary_template: "{count} plans compared; highlighted: {highlight}"
ssr: true
```

Key ideas:

- **`source` per prop** (`binding_only`, `model_text`, `either`) is what makes integrity
  rules enforceable.
- **`use_when` / `avoid_when`** give the planner guidance it can retrieve, instead of
  prompt-stuffing the whole catalogue.
- **`agent`** is how the same component describes itself to agents (§6).
- FluidBuddha's 13 built-in components and 14 section types become a **default manifest**
  for customers without their own design system.
- **Decision D8 — who writes it:** FluidBuddha **generates the draft manifest** from the
  customer's Storybook (stories, arg types and docs give purpose, props and examples) or, when
  there is no Storybook, from the live site (repeated DOM patterns, brand extraction, crawled
  pages). The customer reviews, edits and **approves** it in the console. Nothing in a draft is
  used by the planner until it is approved. Each approved version is immutable, and plans
  record the manifest version they used.

#### 4.2.3 API catalogue *(proposed extension of the OpenAPI registry)*

The OpenAPI spec stays the source, plus annotations FluidBuddha needs:

| Annotation | Values | Purpose |
|---|---|---|
| `x-fb-effect` | `read` · `write` · `destructive` | Decides confirmation and agent policy |
| `x-fb-entity` | `Plan`, `Product`, `Invoice`, … | Links responses to manifest entity types |
| `x-fb-cache` | `public:300s` · `per-user` · `none` | Bind-step caching |
| `x-fb-auth` | `site` · `user` · `none` | Site credential vs the user's own (SaaS, §7) |
| `x-fb-pii` | field paths | Masking and logging rules |
| `x-fb-confirm` | `none` · `card` · `typed` | Visitor confirmation before running |
| `x-fb-undo` | operation id | Undo for writes (SaaS) |
| `x-fb-dry-run` | operation id or param | Preview before running writes |

An "annotate my API" assistant in the console can propose these from the spec, for the
owner to review.

#### 4.2.4 Content

- **Unstructured:** today's CORTEX (crawl, files, text). No change.
- **Structured entities** *(new)*: catalogues, plans, case studies, locations, team, FAQs as
  typed records (from CSV, JSON, a CMS connector or an API), matching manifest entity
  types. Generative UI needs *records* to bind to, not only text to quote.
- **CMS connectors** (Contentful, Sanity, Strapi, WordPress, Shopify catalogue) bring
  entities in without re-crawling.

#### 4.2.5 Policies

Must-include, never-show, regulated wording, competitor rules, region and language rules,
the pages that may never be generated (checkout, legal), and the existing site rules and
medical safety mode.

### 4.3 The generation contract

The planner may:

- choose a layout and components from the manifest;
- order regions;
- write short copy (headlines, captions, transitions) **with citations**;
- choose bindings (which API or content query fills which prop) from the catalogue;
- choose actions from the declared set.

The planner may not:

- invent components, props, routes or actions;
- write values for `binding_only` props;
- emit HTML, CSS or script;
- call write operations at plan time (writes happen only through confirmed actions).

### 4.4 Intent without conversation

Assumption A2 is the biggest product change. A silent visitor still sends many signals:

| Signal | Example | Strength |
|---|---|---|
| Landing URL and path | `/pricing`, `/for/hospitals` | High |
| Campaign and UTM | `utm_campaign=switch-from-rivalco` | High |
| Referrer and search terms (where available) | Search query, partner site | Medium–high |
| Link parameters | `?persona=hr&q=…` (as campaigns use today) | High |
| Returning memory | Last topics, open questions | High (opt-in only) |
| Taste profile | Prefers tables, compact | Medium |
| Firmographics (optional, consented) | Company size from reverse-IP vendors | Medium |
| Device, locale, time | Mobile, Hindi, evening | Low–medium |
| Early behaviour | First scroll, hover, click on a region | Grows over the session |
| Conversation | Anything said or typed | Highest |

**Intent families** *(proposed)*: each site defines (or FluidBuddha proposes from its content
and analytics) 10–40 intent families, such as `compare_plans`, `understand_product`,
`industry_fit:healthcare`, `integration_question`, `existing_customer_support`. The resolver
outputs `{family, stage, entities, confidence}`.

**Resolver design:**

1. Deterministic rules first (path and UTM mappings that the owner can edit).
2. Embedding nearest-neighbour over intent-family descriptions plus past resolved sessions.
3. A small model only when 1 and 2 are not confident, run asynchronously, never blocking
   first paint.
4. When confidence is low: show the default plan for the page, and **ask with the UI**, not
   a chat question. For example, a "What brings you here?" region with 3–4 intent chips.
   This is the visual version of v1.0's "one qualifying question every 3 turns".

**Intent drift:** as behaviour accumulates, the resolver may re-plan *below the fold* or on
the next navigation. It never rearranges what the person is currently reading.

### 4.5 The planner

- **Model:** the fast model with structured output constrained to the plan schema.
  Component ids and props are enums built from the manifest.
- **Retrieval-augmented:** the prompt includes only the 10–20 components whose `use_when`
  matches the intent, 3–5 *exemplar plans* (pinned layouts and top-performing plans for that
  family), and the relevant API operations and entity types. This keeps prompts small as
  manifests grow.
- **Repair loop:** an invalid plan goes back once with validator errors (as
  `render_component` returns props errors with hints today). A second failure falls back to
  the nearest cached plan or the default.
- **Copy budget:** model-written text is short and cited. Long-form content comes from
  bound content regions.
- **Heavy thinker** is used only for conversational plan edits that need reasoning, tools
  or calculation, matching today's lean/heavy split.

### 4.6 Data binding and integrity

Binding resolves `bind` references after the plan is chosen:

| Binding kind | Example | Resolved by |
|---|---|---|
| `api:<operationId>` | `api:listPlans` | Server (public data) or client with the user's token (SaaS, §7) |
| `content:<collection>` | `content:faq` + query | CORTEX or entity store |
| `entity:<type>/<id>` | `entity:CaseStudy/cs_42` | Entity store |
| `ctx.<path>` | `ctx.currency`, `ctx.user.locale` | Request or app context |
| `profile.<path>` | `profile.taste.format` | Taste profile (§5) |

Rules:

- **Paths** use a small JSONPath subset. **Transforms** (format currency or date, count,
  sum, sort, top-n) reuse the safe arithmetic evaluator the configurator already uses. No
  arbitrary code.
- **Model isolation:** bound values never enter the model's context unless a later
  conversational turn needs them, and then they go through PII masking.
- **Empty and failure states:** each manifest component declares its empty and error
  states. A failed binding renders that state and never invents data.
- **Freshness:** per-binding cache from `x-fb-cache`. A plan can be served from cache while
  its data is always fresh.
- **Verification:** model-written text that states a number must match a bound value or a
  cited source. This extends the campaign rule ("every number on the page must appear in
  what it cites", FR-CAMP-04).

### 4.7 Rendering

#### 4.7.1 From overlay to renderer (assumption A1)

Two integration modes:

| Mode | How | When |
|---|---|---|
| **Embedded regions** | The customer places `<fb-region name="hero">` (or a React `<FbRegion>`) in their own templates. FluidBuddha fills them. | G1, and G2 on existing sites |
| **Hosted shell** | FluidBuddha serves the whole page (like campaign pages at `/p/{site}/{slug}` today) on the customer's domain. **Decision D4:** delivered first as a **framework adapter for Next.js** (a route handler / middleware package that fetches the plan, renders it on the server and hydrates it), later as **edge workers** for sites on other stacks. | G2/G3 sites built "generative-first" |

#### 4.7.2 Server-side first

- The plan and bound public data are rendered to HTML on the server (extending the campaign
  renderer). The SDK then hydrates interactive components.
- Customer components need an SSR path. Because Web Components are the runtime contract
  (D2), the server renders them with **declarative shadow DOM**. The framework adapter can
  also pre-render a component through its authoring framework (for example React server
  rendering) and emit the result inside the Web Component's shadow root. Components without
  SSR render as their declared skeleton.
- **Streaming:** regions stream in as their bindings resolve, with the slowest API not
  blocking the rest.

#### 4.7.3 Latency budget *(proposed targets)*

| Path | Target to first meaningful paint (server time) | How |
|---|---|---|
| Cached plan, cached public data | < 150 ms | Plan cache + bind cache + SSR |
| Cached plan, fresh data | < 400 ms + slowest API | Parallel binding, streaming regions |
| Cache miss | Same as default page, then improve | Serve default or nearest plan; plan fresh in the background; apply below the fold or on next view |
| Conversational plan patch | Spoken ack < 1 s (as today); patch < 2.5 s | Existing ack + lean/heavy pipeline |

**Morphing rule:** a fresh plan may replace the cached one *before the person interacts* or
*below the fold*. Visible content never jumps. This respects the cumulative layout shift
budget and readers' trust.

#### 4.7.4 Three design levels in a generative world

- **The Companion** (panel) stays: the conversational surface next to a generated page.
- **The Atmosphere** fits generative pages well: the page itself is the interface, with
  spotlight and captions.
- **The Presence** (full-screen smoke) is a showcase mode, and is unsuitable for agents and
  most SaaS use (§6.6, §7.3.8).

### 4.8 Plan cache and economics

v1.0 says answer costs fall as traffic grows. The same holds for layouts:

- **Key:** `(site, intent family, stage, persona, taste bucket, language, content version,
  design-system version, policy version)`. Taste is *bucketed* (for example 3 density × 3
  format) so the cache keeps a high hit rate.
- **Replay:** exact key first, then nearest by intent-embedding similarity within the site
  and persona, mirroring `conversation_cache` (`EPISODIC_REPLAY_THRESHOLD` 0.92).
- **Curation:** **pinned layouts** (always served for a family) and **blocked plans**, like
  pinned and blocked answers.
- **Invalidation:** re-ingested content, a new design-system or manifest version, or policy
  edits clear affected plans. Data does not need invalidation because it is bound live.
- **Expected effect:** after warm-up, most first paints are cache hits. The model is spent on
  new intents and conversations, not on rebuilding the same pricing page a thousand times.
- **Under G3** whole-plan hits become rarer because plans are composed per person. The
  **fragment cache** in §4.14.2 keeps the economics working.

### 4.9 The conversation edits the page

The conversational agent stays, and becomes the way to **steer** the generated page:

- "Show me only the healthcare plans" → `plan_patch` replaces the `plans` region binding
  params.
- "Compare with RivalCo" → adds a comparison region (only if the policy allows competitors).
- "Make it simpler" → updates the taste profile (`detail: low`) and re-plans the regions in
  view.

Proposed message: `DATA/plan_patch {plan_id, ops: [{op: add|replace|remove|move, region,
value?, animation?}]}`. Existing `DATA/patch` animations (fade, count-up, highlight) apply.
Audio/UI sync stays: speech waits until the patched region has rendered.

### 4.10 URLs, history, SEO and bots

- **Every generated view has a URL.** For example `/pricing?fbv=pl_7f3a9c21d0`, or a clean
  path in hosted-shell mode. Shared links reproduce the plan (data refreshed). Back and
  forward work.
- **Canonical pages for search engines:** each route has an owner-approved *canonical plan*
  served to crawlers and as `rel=canonical`. Generated variants are `noindex` or
  canonicalised to it. This avoids thin or duplicate-content penalties and cloaking concerns
  (crawlers see what a default visitor sees).
- **No-JS and low-end devices:** SSR output is complete HTML; hydration is progressive.
- **Route model:** the flat sitemap becomes a **route registry** with templates and
  parameters (`/products/:slug`), shared with SaaS (§7.3.6).

### 4.11 Governance and quality

| Control | What it does |
|---|---|
| **Validator** (every plan) | Schema and manifest conformity, composition rules, must-include / never-show, contrast and heading order, alt text, tap target sizes, copy length, citation presence |
| **Preview console** | Owners browse plans by intent family × persona × taste, see screenshots, pin, block or edit |
| **Simulation** | "Show me what a returning hospital admin from a Google ad sees on mobile" |
| **Review queue** (optional) | New plans for chosen families need approval before they serve beyond a small share |
| **Regulated mode** | Families or pages limited to pinned layouts only (healthcare, finance) |
| **Audit** | Every served plan is logged with provenance (source, model, versions) and can be replayed |
| **Visual regression** | Pinned layouts re-rendered and diffed when the design system changes |

### 4.12 Measurement

- **Holdout:** static site vs generative site on the owner's goal, using the existing
  always-valid statistics.
- **Per-family lift:** which intent families gain the most from generation.
- **Plan-level analytics:** region engagement, scroll depth, binding failures, morph rate,
  time to first paint.
- **Planner quality evals:** a fixed set of intents scored for validity, policy compliance,
  relevance and visual quality (human or model-graded), run on every planner change.

### 4.13 Risks and mitigations

| Risk | Mitigation |
|---|---|
| Slow first paint | Never block on a model; cache-first; SSR; streaming |
| Off-brand or broken layouts | Customer-only components, validator, pinned layouts, review queue |
| Hallucinated facts or prices | `binding_only` props, citations, number verification |
| SEO penalties | Canonical plans for crawlers, `noindex` variants, stable URLs |
| Cost at high traffic | Plan cache, bucketed taste, fast model, generation only on miss |
| Inconsistency ("the page looked different yesterday") | Stable region ids, pinned layouts for key pages, morph rules, shareable plan URLs |
| Customer effort to supply a manifest | Default manifest; generate a draft manifest from the customer's Storybook or live site for the customer to approve (D8); brand extraction; a G1 entry point |

### 4.14 What selling G3 requires

Decision D1 makes free-form generation (G3) the product we sell. G3 composes layouts and
flows per person instead of reusing a plan per intent family. The pipeline is the same; these
additions make it safe, fast and affordable at that level.

#### 4.14.1 What changes from G2 to G3

| Aspect | G2 (composed pages) | G3 (free-form) |
|---|---|---|
| Plan unit | One plan per intent family × persona × taste bucket | One plan per person and moment, built from reusable fragments |
| Layout | Chosen from the customer's layout templates | Templates **plus** free composition within the grid and composition rules |
| Flows | Single pages | Multi-step flows (compare → configure → book) assembled on the fly |
| Re-planning | On navigation or conversation | Continuous: each interaction may re-plan regions out of view |
| Cache | Whole-plan cache | Fragment cache + whole-plan cache for common cases |
| Governance | Pinned layouts per family | Pinned *regions* and *rules*; review by sampling |

#### 4.14.2 Fragment cache

- A **fragment** is a region with its component, props and bindings, plus the intent and taste
  conditions it suits. Fragments are cached and reused across people, like answers today.
- The G3 planner mostly **assembles** cached fragments and writes only the glue (order, short
  transitions, the few new regions a person needs). This keeps most planner calls short.
- Fragment keys: `(site, fragment purpose, entity, persona, taste bucket, language, content
  version, manifest version)`. Fragments can be pinned and blocked like answers.

#### 4.14.3 Generation budget (Q12)

- A per-site **generation budget**: fresh plans per session and per day, on top of the
  existing daily spend cap (`PUBLIC_DAILY_SPEND_CAP_USD` and per-site caps).
- When the budget runs out, the site falls back to G2 (cached family plans), then to the
  canonical page. Visitors always get a page; they never get an error.

#### 4.14.4 Guardrails specific to G3

- **G1/G2-only routes** (Q14): checkout, legal, pricing terms and regulated content default to
  pinned or composed layouts.
- **Pinned regions:** owners can lock regions (disclaimers, legal footer, key claims) that
  every G3 plan must include unchanged.
- **Sampling review:** a share of served G3 plans is screenshotted into a review feed, with
  automatic flags (validator warnings, unusual layouts, low engagement).
- **Stability for the person:** once someone has seen a region, it does not change shape
  without a cause (their request, new data). This prevents a "shifting" site.
- **Canonical plans for crawlers** stay mandatory (§4.10). G3 variants are never indexed.

#### 4.14.5 Pilot path (G1 first)

Pilots start on G1 (D1) because G1 proves lift without the customer rebuilding pages. Each
pilot should end with a plan to move up: G1 slots → G2 for the top intent families → G3 on
chosen routes. The holdout runs at every stage, so each step up is justified by measured lift.

---

## 5. Pillar 2 — Personal experience

### 5.1 From segments to individuals

| Level | Unit | v1.0 | Vision |
|---|---|---|---|
| P0 | Site | One experience | — |
| P1 | Segment | ✅ Personas (≤ 6), re-theming, persona-aware answers | Kept as the *prior* (starting point) |
| P2 | Session | Partly (adaptive persona during the session) | Taste and intent learned within the session |
| P3 | Person | Opt-in memory of topics only | **Taste profile** across visits, devices (when known) and apps |

### 5.2 The taste profile *(proposed)*

| Dimension | Values | Learned from (explicit / implicit) | Affects |
|---|---|---|---|
| Information density | airy · balanced · compact | Setting; scroll speed, zoom | Tunables, region count |
| Preferred format | prose · bullets · tables · charts · visuals | "Show me a table"; expands tables, skips prose | Component choice |
| Level of detail | summary · standard · deep | "Simpler please"; opens details | Copy length, depth regions |
| Modality | voice · text · silent browsing | Uses mic, types, never opens the agent | Agent opening, launcher prominence |
| Tone | formal · friendly · concise | Chosen; reply length to agent | Agent voice and microcopy |
| Pace and motion | calm · standard · lively | `prefers-reduced-motion`, setting | Motion tunables |
| Colour scheme | light · dark · auto | OS setting, toggle | Tunables |
| Language | en · hi · Hinglish | Detection, choice | Content and copy |
| Interests | Topics, products, entities | Questions, dwell, clicks | Planner retrieval, ordering |
| Journey stage | learning · evaluating · buying · customer | Intent history, login | Intent prior, CTA choice |

Each dimension stores a **value, confidence and last-updated time**. Implicit evidence
updates slowly and decays. Explicit choices override and are not overridden by inference.

### 5.3 Where personalisation applies

1. **Planner input:** taste bucket and interests go into the plan key and the prompt.
2. **Tunables:** density, scheme, motion and type scale adjust tokens *within the
   customer's declared limits* (§4.2.1).
3. **Agent behaviour:** tone, length, modality, language.
4. **Proactive behaviour:** whether and how the agent speaks first (a person who never
   engages gets fewer nudges).
5. **Content ordering:** interests reorder bound collections (case studies from your
   industry first).

### 5.4 Brand-safe personalisation

The customer decides **which axes may move** and **how far**. For example: density may
vary, colour scheme may switch between the two brand schemes, but brand colours,
logo, type families and legal regions never change. Personalisation can never produce a
design the brand team has not allowed.

### 5.5 Identity levels

| Level | Who | What can persist | Consent |
|---|---|---|---|
| Anonymous session | Any visitor | Session only (in memory or session storage) | None beyond privacy notice; no cross-visit tracking |
| Remembered device | Opted in ("Remember me", exists today) | Taste + topics on this device | Explicit opt-in; "Forget me" |
| Known person | Logged in (SaaS, or a site with accounts) | Taste across devices and the customer's apps | Customer's terms + FluidBuddha controls |

Personalisation works without tracking: session-level taste already makes a big difference,
and cross-visit memory stays opt-in, matching the v1.0 default (`memory_enabled` off).

**Storage (decision D5):** taste profiles are **stored by FluidBuddha by default**, next to
`visitor_memories`, isolated per site (and per end tenant in SaaS, §7.3.3), encrypted at rest,
and covered by the same retention, erasure and export controls. Syncing with a customer's
customer-data platform is not planned for now.

### 5.6 Privacy, consent and user controls

- **"Why am I seeing this?"** on generated regions: shows the signals used ("You came from
  a pricing ad and asked about integrations").
- **Profile panel:** people can see and edit their taste settings and wipe them.
- **Erasure:** extend the existing erasure flow to taste profiles and plan logs.
- **Regulation:** design for India's DPDP Act and GDPR from the start: purpose limitation,
  consent records (the microphone consent pattern), retention windows (`site_privacy`
  extended with `profile_days`), data processing agreement updates.
- **No sensitive inference:** never infer or use health, religion, caste, politics,
  sexuality or financial distress, even if signals exist. Medical safety mode stays.

### 5.7 Ethical guardrails (product rules, not options)

- **No personalised pricing.** Prices come from the price list or API, the same for
  everyone in the same market. Personalisation may change *emphasis*, never the *price*.
- **No dark patterns.** No fake scarcity, no hiding the cancel path, no pressure copy tuned
  to individual vulnerability.
- **Equal access.** Every piece of information is reachable by every visitor; personalisation
  reorders and emphasises, it does not hide.

### 5.8 Cold start and learning

- New visitors start from the **persona prior** (v1.0 personas) and site defaults.
- Within a session, a few clear signals (format choices, expansions) shift the taste bucket.
- **Contextual bandits** at the region level (which proof point, which CTA) can learn what
  works per intent family and taste bucket. Guardrails: the minimum exploration share and
  the holdout stay owner-controlled, and statistics use the existing always-valid method.

---

## 6. Pillar 3 — Agent-ready UI

### 6.1 Which agents visit

| Agent type | How it sees the site | What it needs |
|---|---|---|
| **API / MCP agents** (assistants calling tools) | Tool calls | Tools with clear schemas, auth scopes, confirmations |
| **DOM-reading browser agents** | HTML and the accessibility tree | Semantic markup, stable selectors, readable state |
| **Computer-use agents** | Screenshots and clicks | Conventional, predictable, low-motion UI with visible labels |
| **In-browser assistants** (browser built-ins) | Page content plus page-declared tools | Page-declared tools and structured data |
| **Crawlers for AI answers** | Static HTML, `llms.txt` | Canonical content, structured data |

### 6.2 Principle: the plan is the contract

Because every view is a typed plan bound to declared APIs, FluidBuddha can serve the
**same plan** two ways:

- **Humans:** rendered components (HTML + hydration).
- **Agents:** the plan as structured data, the bound entities as typed records, and the plan's
  actions as callable tools.

So "agent-friendly" stops being a parallel product. An agent sees exactly what a human would,
in a form it can use, and both views are always in sync.

### 6.3 Stable addressing (the core requirement)

Generated UI is naturally hostile to agents: layouts change per visit, and agents that rely on
fragile selectors ("the third button in the second card") break. The fix is identifiers that
stay the same whatever the layout:

| Attribute *(proposed)* | Example | Meaning |
|---|---|---|
| `data-fb-region` | `plans` | Stable region id from the plan |
| `data-fb-entity` | `Plan:scale` | The record a component shows |
| `data-fb-action` | `start_trial` | A declared action; same id in tools and analytics |
| `data-fb-field` | `Plan:scale.price` | A bound value (read-only) |
| `data-fb-state` | `expanded`, `loading`, `error` | Current component state |

Region and action ids are stable across plans for the same intent family, so an agent (or a
test, or analytics) can rely on them.

### 6.4 Semantic layer

- **Accessibility first:** correct roles, accessible names, labelled controls, logical heading
  order. Enforced by the validator (§4.11). Good accessibility is the best general-purpose
  agent interface.
- **Structured data per view:** schema.org JSON-LD generated from the bound entities
  (`Product`, `Offer`, `FAQPage`, `SoftwareApplication`, `Organization`).
- **Plan endpoint:** `GET /sites/{key}/views/{plan_id}` *(proposed)* returns the plan with bound
  values, citations and available actions.
- **Per-view `llms.txt` / markdown:** a text rendering of the current view, extending today's
  site-level `llms.txt`.

### 6.5 Actions as tools

- Every plan action and every catalogue operation (subject to `x-fb-effect` and scopes) can be
  exposed through the existing **MCP server**, with schemas generated from the catalogue.
- **Page-declared tools:** expose the current view's actions to in-browser agents through
  emerging browser standards (see §11.3). FluidBuddha can generate these declarations from
  the plan automatically, so customers get them for free.
- **Open UI protocols (decision D3):** the Experience Plan stays **our own schema**, designed
  so it can be **exported** to emerging open standards for agent-sent UI (Google's A2UI
  protocol, the MCP Apps extension, AG-UI; see §11.3). We revisit which standard to target
  after the §11.3 review. Export lets FluidBuddha's generated UI also render *inside* other
  assistants, a large distribution channel, without tying the core to a format we don't
  control.

### 6.6 Agent mode

- **Detection:** declared user agents, signed agent identity (HTTP message signatures, such as
  the Web Bot Auth proposals), MCP or API access tokens.
- **Plain rendering for agents:** no Presence/Atmosphere effects, no motion, no gated reveals,
  everything expanded or reachable, conventional controls with visible labels. Humans can opt
  into this too (it doubles as an accessibility and low-bandwidth mode).
- **Same content rule:** agents get the same facts as humans (no cloaking). Only the
  presentation changes.

### 6.7 Agent safety

| Concern | Control |
|---|---|
| Agents running purchases or writes | Confirmation policy per action for agent callers (`x-fb-confirm`): auto, needs the human's confirmation through the agent, or never for agents |
| Over-use | Per-agent rate limits and quotas; agent calls already excluded from conversation billing |
| Identity and audit | Agent identity recorded on every action and in the audit log |
| Prompt injection via the site | Generated UI never embeds unvetted user-generated text in agent-facing output without marking it as untrusted |
| Scope | Scoped tokens (exists) extended to entity- and operation-level scopes |

### 6.8 Measurement

Extend "Agent traffic" from *calls by tool and by assistant* to **task completion** (agent
found the plan, compared, booked), failure points (which action or view confused agents) and
agent-originated leads and revenue.

---

## 7. Pillar 4 — Adapting to SaaS applications

### 7.1 Verdict

**Adaptable without a rewrite. One layer needs real rebuilding: identity, authorisation and
data governance.** The rest carries over or needs moderate extension.

On a website, FluidBuddha talks to **anonymous visitors** about **public content** with
**one site credential**. In a SaaS app it talks to **known users** about **their private
data** and acts **on their behalf**. Most of the remodelling follows from that one sentence.

### 7.2 What carries over

| v1.0 capability | In a SaaS app it becomes |
|---|---|
| Cognitive loop (router, lean/heavy, tools) | Unchanged core |
| Voice and text conversation | In-app copilot, **voice-first** with text always available (D9, §7.3.12) |
| Generative components, patching | "Ask your data" answers, report and dashboard builders |
| Guided tour | Product onboarding and feature walkthroughs |
| Proactive triggers | In-app nudges (stuck on a step, unused feature, empty state) |
| Navigation, scroll, spotlight | Take me to the setting; highlight the field |
| CORTEX grounding | Help centre, docs, release notes |
| Live takeover, voice handoff | Support escalation inside the app |
| Insights (questions, gaps, feature requests, objections) | Product friction, feature demand, churn signals |
| Experiments and holdout | Activation and retention lift |
| Confirmable actions | Safe writes on the user's data |
| Teams, SSO, audit, self-host, BYO model | Enterprise base (very relevant for SaaS buyers) |
| React / Vue packages | Embedding path inside the app's own code |

### 7.3 What has to change

#### 7.3.1 Delegated user authentication (the biggest change)

Today `<SITE>_API_AUTH` holds one credential per site (assumption A5). In SaaS that is
unacceptable: an agent with a shared service credential can read or change any user's data.

**Design *(proposed)*:**

```ts
FluidBuddha.init({
  key: "fbk_…",
  getAccessToken: async () => auth.getToken({ audience: "fluidbuddha" }), // short-lived
  user: { id: "u_123", tenantId: "t_9", roles: ["billing_admin"] }        // signed claims
});
```

- **Token passthrough with audience restriction**, or **OAuth 2.0 token exchange** (RFC 8693)
  to get a FluidBuddha-scoped, short-lived token that the backend uses only for that user's
  calls.
- Tokens live for the request or the session in memory only. They are never stored,
  logged or cached.
- **Signed user claims** (a JWT signed by the SaaS backend) so the user and tenant cannot be
  spoofed from the browser.
- Two call paths. **Decision D6:** **client-side binding is the default**. The browser calls
  the SaaS API directly with the user's token, and the data never reaches FluidBuddha's
  servers. **Server-side binding** is used **only when the user asks the agent to reason over
  their data** ("why did revenue drop last month?"). FluidBuddha then calls with the exchanged
  token, sends only the fields the tool needs, and masks PII before the model sees it. The UI
  shows when data is being sent for the agent to reason over.
- `x-fb-auth: user` operations refuse to run without a user token.

#### 7.3.2 Authorisation-aware behaviour

- The agent can do only what the user can do. The SaaS API is the final authority (it
  checks the token), but FluidBuddha should also **filter tools and actions by role**
  before offering them, so the model never proposes something the user cannot do.
- A permissions endpoint or claims list (`can: ["invoice.read", "invoice.refund"]`) is passed
  into the tool registry, as tiers filter tools today (`orchestrator/tools.py`).

#### 7.3.3 Two levels of tenancy

Today: FluidBuddha account → websites. SaaS adds the **customer's customers** (their
tenants) and **their users**. Every stored record (conversations, profiles, insights,
caches) needs `end_tenant_id` and `end_user_id`, and every query must filter on them. Insights
roll up per end tenant, so the SaaS vendor can see "Customer X's admins keep asking how to
export".

#### 7.3.4 Cache partitioning (a must-fix before any SaaS pilot)

v1.0 replays answers across visitors by site, persona, page and language (assumption A6).
In SaaS that could show user A an answer containing user B's data.

| What | Cache scope |
|---|---|
| Plans (structure only, data bound later) | Shared across users: safe and keeps costs low |
| Answers from docs and help content only | Shared per site/persona/language (as today) |
| Answers that used any user data or user-scoped API | **Never shared**; per user at most, or not cached |
| Audio for shared answers | Shared (as today) |
| Bound data | Per `x-fb-cache` (`per-user` keyed by user and permission hash) |

This is where the **structure vs data** split (§3.2, principle 3) pays off: SaaS keeps the
plan cache's cost benefits without the data-leak risk.

#### 7.3.5 Grounding sources change

- **Docs and help:** CORTEX, as today.
- **Live app state and user data:** from APIs at bind or tool time, not ingested into CORTEX.
- **PII:** pattern masking (emails, phones, cards) is not enough when whole customer records
  go through the model. Add field-level rules from `x-fb-pii`, minimum-necessary fields per
  tool, and client-side binding as the default (§7.3.1, D6). A site can also lock itself to
  client-side only, so user data never leaves the browser.

#### 7.3.6 App-context API

Page awareness (page, section, anchors) becomes app awareness:

```ts
FluidBuddha.setContext({
  screen: "invoice.detail",
  route: { template: "/invoices/:id", params: { id: "inv_123" } },
  entities: [{ type: "Invoice", id: "inv_123" }],
  selection: [{ type: "LineItem", id: "li_7" }],
  formState: { dirty: true, invalidFields: ["gstin"] },
  featureFlags: ["new_reports"]
});
```

- Navigation snaps to the **route registry** with templates and parameters (§4.10) instead of
  a flat list.
- Spotlight and guidance target **app elements** by stable ids (`data-fb-*`, §6.3), not only
  page sections.
- Host hooks (`onNavigate`, events) already exist and carry over to SPA routers.

#### 7.3.7 Safe writes

SaaS actions change real data (refund, delete, change plan, invite user). On top of today's
confirmation cards:

- **Preview before run:** show the change ("3 invoices will be marked paid") using
  `x-fb-dry-run`.
- **Undo** where the API offers it (`x-fb-undo`), with a time-limited undo toast.
- **Typed confirmation** for destructive operations (`x-fb-confirm: typed`).
- **Audit in the host app:** writes carry `X-Actor: fluidbuddha-on-behalf-of:u_123` (or
  equivalent) so the SaaS's own audit log records them.
- **Bulk limits:** cap the number of records one action may affect without extra
  confirmation.

#### 7.3.8 Surfaces

| Surface | Fit for SaaS |
|---|---|
| The Companion panel / sidebar | ✅ Main surface, with the mic as the primary control |
| ⌘K command palette (exists in Level 3) | ✅ Hold-to-talk hotkey or type: "refund last order for Ravi" |
| Inline slots (`<FbRegion>` in the app) | ✅ Generative dashboards, empty states, onboarding cards |
| The Atmosphere (spotlight, captions) | ✅ For tours and guidance |
| The Presence (full-screen smoke) | ❌ Not for work tools |

#### 7.3.9 Where generative UI belongs in SaaS

People depend on muscle memory in core workflows, so **keep core screens stable** and
generate where variability helps:

- home and overview dashboards built from the user's role and goals;
- reports and "ask your data" views;
- onboarding checklists and first-run experiences;
- empty states ("you have no invoices yet; here's how to import");
- help and troubleshooting views;
- admin task flows that are rare and complex (the agent assembles the form you need).

#### 7.3.10 Commercial model and metrics

**Decision D7:** websites and SaaS apps are **one platform, one SKU, one uniform price
list**. A customer can use the same plan on its marketing site and inside its app, and usage
from both counts against the same allowance.

| | Website | SaaS app |
|---|---|---|
| Buyer | Marketing, growth | Product, customer success, support |
| Pricing | **Same plans and prices for both** (today: Free / Growth / Scale / Enterprise, per conversation) | **Same** |
| Billing unit | To be settled under Q11 (a unit that also covers generated-only sessions) | **Same unit** |
| Proof | Holdout on a goal page | Holdout on activation, time to value, feature adoption, retention, support tickets |
| Revenue layer | Leads, payment links, meetings | Upgrade and expansion prompts (seat limits, premium features), renewals |

What this means:

- **No separate SaaS packaging.** SaaS features (identity layer, app context, safe writes) are
  part of the product. Plan limits are the same everywhere; enterprise-only controls stay
  enterprise-only in both contexts.
- **Today's unit needs revisiting.** "Conversation" fits websites, but G3 generates pages for
  silent visitors and SaaS users have many short sessions. Q11 proposes an *experience
  session* unit for both contexts.
- **Measurement adapts to the context, not the price.** Website goals use conversion; app
  goals use activation, adoption and deflection, on the same experiment engine.
- **The revenue layer** mostly drops out in-app, except expansion and upsell.

#### 7.3.11 Compliance

SaaS vendors' customers will ask: where does my users' data go, which sub-processors see it,
how long is it kept, can it stay in my region? The SOC 2 pack, BYO model, self-host and
retention controls help. Add: data residency options, per-end-tenant retention and erasure,
a "no user data leaves the browser" mode (client-side binding only), and DPA terms for
processing on behalf of a controller's customers.

#### 7.3.12 Voice-first inside apps

**Decision D9:** FluidBuddha stays **voice-first** in SaaS apps, as on websites. Work
software brings conditions that websites don't, so voice-first in apps needs:

| Concern | Design |
|---|---|
| Shared offices and meetings (Q13) | **Push-to-talk by default** in apps (hold a hotkey or the mic button); hands-free listening is an opt-in per user. A visible mic state at all times. |
| Text parity | Everything said can be typed, and every spoken answer is also shown as text. Voice is the primary path, never the only one. |
| Voice commands on real data | Spoken commands go through the same tool, permission and confirmation layers as typed ones. |
| Confirming writes by voice | v1.0 already accepts a spoken "yes / haan" for action cards. In apps: spoken confirmation for ordinary writes; for destructive writes the agent **reads back** the change ("Delete 3 invoices for Ravi Traders?") and needs an explicit confirmation; the highest-risk operations (`x-fb-confirm: typed`) still need a tap or typed confirmation. |
| Names and domain terms | Speech recognition gets hints from the app context (entity names on screen, the customer's glossary) so "Ravi Traders" or product SKUs are recognised. |
| Privacy of what is spoken | Audio handling, consent and retention follow the existing microphone-consent rules; recordings of in-app speech are not kept by default. |
| Capacity | SaaS brings many concurrent users. The v1.0 load test missed the time-to-first-audio objective above ~50 concurrent voice sessions per replica, so voice capacity planning (more replicas, regional speech endpoints) is a prerequisite for SaaS pilots (§8.2). |
| Languages | English and Hindi as today; wider language support matters more in apps used all day. |

### 7.4 Product shape: one product for sites and apps

**Decision D7:** there is no separate SaaS product. The same FluidBuddha, same SKU and same
price list run on a customer's website and inside its app. In an app, the product adds
these capabilities (all part of the one product):

- **Onboarding copilot:** tours plus nudges plus "do it for me" setup actions.
- **Ask-your-data:** generated charts, tables and reports over the SaaS's own APIs, as the
  user.
- **Support deflection:** grounded answers from docs plus the user's own state ("your export
  failed because the GSTIN field is empty"), escalating to live takeover.
- **Task agent:** multi-step actions with preview, confirm and undo.
- **Product insights:** friction, feature demand and churn signals per end tenant.

### 7.5 Architecture changes for SaaS

```
 SaaS frontend                                   FluidBuddha backend
┌──────────────────────────────┐   WS + REST    ┌───────────────────────────────────────────┐
│ <FbProvider getAccessToken   │◄──────────────►│ Identity layer (NEW)                       │
│   user={signed claims}>      │                │  verify claims · token exchange · scopes   │
│  setContext(screen, route,   │                │ Tool registry filtered by role (CHANGED)   │
│   entities, selection)       │                │ Cognitive loop (SAME)                      │
│  <FbRegion name="home"/>     │                │ Plan cache (shared) / answer cache          │
│  ⌘K palette · sidebar        │                │   partitioned by data scope (CHANGED)       │
│  client-side binding ────────┼──► SaaS API    │ Server-side binding with user token (NEW)   │
└──────────────────────────────┘    (user token)│ Write safety: dry-run · undo · actor (NEW)  │
                                                │ end_tenant / end_user on all data (NEW)     │
                                                └───────────────────────────────────────────┘
```

---

## 8. Cross-cutting concerns

### 8.1 Security

- The planner can only emit manifest components; rendering never runs model-written markup
  or script (the v1.0 rule "the model never sends HTML" stays).
- Customer component bundles run in the customer's origin. In hosted-shell mode, use a
  strict CSP and subresource integrity for bundles.
- Bindings call only catalogue operations, through the existing SSRF-safe fetch path (and
  close the DNS-rebinding residual risk noted in v1.0 §24 before widening API use).
- Tokens never reach logs, caches, traces or model context.

### 8.2 Performance and capacity

- First paint served from cache and SSR is cheap; the heavy cost moves to the planner on
  cache misses and to conversations.
- The v1.0 load test missed the voice time-to-first-audio objective above ~50 concurrent
  sessions on one replica. Voice-first SaaS (D9) adds many concurrent users, so voice
  capacity must scale out before SaaS pilots. Generative pages add page-render load that is
  mostly CPU and cache, and should scale separately (a render tier behind the CDN).
- Edge caching for public plans and public bound data.

### 8.3 Cost model

| Cost driver | Website (sold as G3) | SaaS app |
|---|---|---|
| Planner calls | Fragment-cache misses and per-person glue; capped by the generation budget (§4.14.3) | Cache misses per role/goal (low variety) |
| Binding | Customer API load; cached per `x-fb-cache` | Per user; client-side by default (D6) |
| Conversation | Voice-first, as today | **Voice-first** (D9): same speech-to-text and text-to-speech costs as websites, and more sessions per user per day |
| Rendering | SSR CPU, CDN | Mostly client-side |

Because pricing is uniform (D7), the price list must cover the most expensive context.
Q11 (billing unit) and Q12 (G3 generation budget) need answers before pricing is final.

### 8.4 Quality and evaluation

- **Plan evals:** validity, policy compliance, relevance, visual quality per intent family.
- **Binding contract tests:** each catalogue operation against recorded responses.
- **Visual regression** for pinned layouts on design-system changes.
- **Agent evals:** scripted agents (MCP and browser) complete key tasks on generated views.
- **Security evals for SaaS:** cross-user and cross-tenant leak tests on caches, insights and
  memory, run in CI.

### 8.5 Developer and customer experience

- **Onboarding path:** crawl (today) → draft manifest from Storybook or the live site's
  components → annotate API → choose G1 regions → preview → holdout launch.
- **Local dev kit:** a CLI to validate manifests and catalogues, preview plans locally, and run
  plan evals in the customer's CI.
- **Console:** design-system, catalogue, intent families, plan browser, policies, taste
  settings, agent mode.

---

## 9. Phased roadmap

Phases are sequenced so each ships value on its own and de-risks the next. G3 is what we sell
(D1), and pilots start on G1. The phases are the delivery path from the first G1 pilot to
general availability of G3.

### Phase 0 — Foundations (enables everything)

- Experience Plan schema v1 and validator (own schema, export-ready, D3).
- Design-system package and component manifest; **console management** (fixes A8). Built-in
  components become the default manifest.
- **Web Component runtime contract** and the first **authoring adapter** (React) (D2).
- **Draft-manifest generator** from Storybook and from the live site, with a console approval
  flow (D8).
- API catalogue annotations (`x-fb-effect`, `x-fb-entity`, `x-fb-cache`, `x-fb-auth`).
- Data binding engine (server-side, public data) with `binding_only` enforcement.
- Stable `data-fb-*` addressing in the SDK renderer.
- **Exit:** the existing Extreme `generate_page` runs on the plan schema with bindings and
  passes the validator.

### Phase 1 — Adaptive slots (G1)

- `<fb-region>` / `<FbRegion>` embedding.
- Silent intent resolver (rules + embeddings) and intent families.
- Plan cache with pinned and blocked layouts.
- Preview console and holdout on slot regions.
- **Exit:** a pilot site shows measured lift from generated hero/proof/CTA regions with
  first paint unchanged.

### Phase 2 — Composed pages (G2)

- SSR page renderer for customer components (declarative shadow DOM); hosted-shell mode
  delivered through the **Next.js framework adapter** (D4).
- Planner over the customer manifest with exemplar retrieval and repair loop.
- Plan patches from conversation (`DATA/plan_patch`).
- Plan URLs, canonical plans for crawlers, route registry.
- Structured entities and the first CMS connectors.
- **Exit:** a pilot site serves generated pages for chosen intent families, with cache hit rate,
  latency and SEO targets met.

### Phase 3 — Personal experience

- Taste profile (session first, then opt-in persistent).
- Tunables in the design system; taste buckets in the plan key.
- "Why am I seeing this", profile panel, erasure extension.
- Region-level bandits within guardrails.
- **Exit:** measurable lift from taste-aware plans over persona-only plans.

### Phase 4 — Free-form (G3), the product we sell

Needs Phase 2 (composed pages) and Phase 3 (taste profiles).

- Fragment cache and the assembling G3 planner (§4.14.2).
- Free composition within layout grids; multi-step flows.
- Generation budget with graceful fallback to G2 and the canonical page (§4.14.3).
- Pinned regions, G1/G2-only routes, sampling review feed (§4.14.4).
- **Edge-worker** delivery of the hosted shell for non-Next.js sites (D4, second step).
- **Exit:** G3 runs on chosen routes of a pilot site within latency, cost and governance
  targets, and beats G2 in a holdout.

### Phase 5 — Agent-ready

- Plan endpoint, per-view JSON-LD and text rendering.
- Plan actions as MCP tools; page-declared tools; agent mode rendering.
- Plan export to an open agent-UI standard (after the §11.3 review).
- Agent task-completion analytics.
- **Exit:** scripted agents complete key tasks on generated views with no human-only steps.

### Phase 6 — SaaS apps (same product, same SKU)

Can start in parallel with Phase 2 once Phase 0 is done, because it mainly needs the
identity layer, not G2. It ships as part of the one product (D7), not as a separate offer.

- Identity layer: signed claims, `getAccessToken`, token exchange, role-filtered tools.
- Client-side binding as the default data path; server-side only for agent reasoning (D6).
- Two-level tenancy (`end_tenant_id`, `end_user_id`) across storage.
- **Cache partitioning by data scope** (blocking requirement).
- App-context API, route templates, element-level spotlight.
- Safe writes: dry-run, undo, voice read-back and typed confirmation, actor header.
- **Voice-first in apps** (D9): push-to-talk, context hints for speech recognition, and
  voice capacity scaled for many concurrent users (§7.3.12).
- **Uniform pricing** (D7): the billing unit from Q11 applied to sites and apps alike; SaaS
  goals (activation, adoption, deflection) in experiments.
- **Exit:** a pilot SaaS runs onboarding copilot, ask-your-data and support deflection by
  voice, passes the cross-user leak test suite, and is billed on the same price list as
  websites.

### Dependency view

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 (G3)
   │                       └──────► Phase 5 (agent-ready)
   └──────────────────────────────► Phase 6 (SaaS: identity + cache partitioning first)
```

---

## 10. Decisions and open questions

### 10.1 Decisions (recorded 6 November 2026)

The product owner answered the questions raised in the first draft. Where the decision
differed from the draft's leaning, the rest of this document has been updated to match.

| # | Question | Decision | Changed from draft? | Where it applies |
|---|---|---|---|---|
| D1 | Default generative level to sell | **Sell G3 (free-form); start pilots on G1 (adaptive slots).** G2 is the stepping stone between them and the fallback for regulated areas. | Yes (draft: sell G2) | §1.3, §4.1, §4.14, §8.3, §9 |
| D2 | Component technology for customer bundles | **Web Components are the runtime contract; framework adapters (React, Vue, …) are for authoring.** | No | §4.2.1, §4.7.2 |
| D3 | Plan format | **Own schema, designed to export to an open standard; revisit after the §11.3 review.** | No | §3.3, §6.5 |
| D4 | Hosted shell delivery | **Framework adapters first (Next.js), edge workers later.** | No | §4.7.1, §9 |
| D5 | Taste profile storage | **Stored by FluidBuddha by default.** | Partly (draft also planned a CDP sync; not in scope now) | §5.5 |
| D6 | SaaS data path default | **Client-side binding by default; server-side only when the user asks the agent to reason over their data.** | No | §7.3.1, §7.3.5 |
| D7 | Separate SaaS product or one product | **One platform, one SKU, one uniform price list** for websites and SaaS apps. | Yes (draft: separate SKU and pricing) | §7.3.10, §7.4, §9 |
| D8 | Who writes the manifest | **FluidBuddha generates a draft from the customer's Storybook or live site; the customer approves it.** | No | §4.2.2, §8.5 |
| D9 | Voice in SaaS | **Voice-first**, with text always available. | Yes (draft: text-first) | §7.2, §7.3.8, §7.3.12, §8.3 |
| D10 | Internal name | **Rename the "A2UI Orchestrator" to "FluidBuddha Orchestrator", and replace "A2UI" with "FluidBuddha" everywhere it names our own product.** | Yes (draft: consider renaming) | §11.4 |

### 10.2 Open questions raised by the decisions

| # | Question | Why it matters | Suggested direction |
|---|---|---|---|
| Q11 | What is the billing unit under uniform pricing? | Today's unit is a *conversation* (a session with at least one answered turn). G3 generates pages for visitors who never talk, and SaaS users have many short sessions. Both cost money but are not conversations. | One unit for both contexts, for example an *experience session*: a session that had an answered turn **or** was served a freshly generated plan. Cache-served sessions stay free, so the price falls as the cache warms. Needs a pricing review. |
| Q12 | How much per-person generation does G3 allow per visit? | G3 lowers cache hit rates, and cost is driven by planner calls on misses. | A per-site generation budget (fresh plans per session, daily cap) on top of the existing daily spend cap, with fragment caching (§4.14). |
| Q13 | Voice-first in shared workplaces | SaaS users sit in open offices and meetings. Always-on listening is unwelcome there. | Push-to-talk by default in apps, a hotkey, a visible mic state, and full text parity (§7.3.12). |
| Q14 | Which surfaces never run free-form (G3)? | Selling G3 must not mean checkout, legal or regulated pages change shape per person. | An owner-editable list of G1/G2-only routes, defaulting to checkout, legal, pricing terms and medical content. |

---

## 11. Appendices

### 11.1 Glossary

| Term | Meaning |
|---|---|
| **Experience Plan** | Typed JSON describing a view: layout, regions, components, props, bindings, actions |
| **Component manifest** | The customer's catalogue of components the planner may use, with prop schemas and rules |
| **Binding** | A reference in a plan to data from an API, content or context, resolved at render time |
| **Intent family** | A named kind of visitor goal used for planning and caching |
| **Pinned layout** | An owner-approved plan always served for an intent family |
| **Tunables** | Design tokens the customer allows personalisation to adjust, within limits |
| **Taste profile** | A person's preferences for format, density, detail, tone and modality |
| **Plan patch** | A region-level change to the current plan, usually from conversation |
| **Canonical plan** | The plan served to crawlers and used as `rel=canonical` for a route |
| **Data scope** | Whether an answer or value is public, per tenant or per user; decides cache sharing |

### 11.2 Mapping summary: v1.0 → vision

| v1.0 | Vision |
|---|---|
| `generate_page` + 14 section types | Planner + customer component manifest |
| `<SITE>_DESIGN_SYSTEM` (env or files) | Design-system package in the console |
| `call_site_api` → result to model | Bindings → result to UI; model isolated |
| `<SITE>_API_AUTH` | Site credential for public ops; user token for user ops |
| `patch_component` / `DATA/patch` | `plan_patch` / `DATA/plan_patch` |
| `conversation_cache` | Plan cache + data-scoped answer cache |
| Personas (≤ 6) | Persona prior + individual taste profile |
| `visitor_memories` | Taste profile (opt-in persistent) |
| `STATE/sync` page awareness | App-context API |
| Sitemap routes | Route registry with templates |
| MCP server, `llms.txt` | Plan endpoint, actions as tools, per-view structured data |
| Campaign pages | Hosted shell and SSR renderer |
| Holdout on goal page | Holdout on generative vs static, and on SaaS goals |

### 11.3 External standards to review before committing

This space is moving fast. The items below were known at the time of writing and **must be
checked for current status** before any design decision depends on them:

- **A2UI (Google):** an open format for agents to send declarative UI that clients render
  with their own components. Close to the Experience Plan idea, and a candidate export
  target (D3). The naming clash with our backend's former internal name is resolved by
  decision D10 (§11.4). This is the only meaning of "A2UI" left in this document.
- **MCP Apps (Model Context Protocol extension):** a way for MCP servers to provide
  interactive UI that renders inside AI assistants. Relevant for showing FluidBuddha's
  generated UI inside other assistants.
- **AG-UI (CopilotKit):** an event protocol between agent backends and frontends. Overlaps
  with FluidBuddha's envelope protocol.
- **WebMCP (W3C Web Machine Learning community group proposal):** lets a web page declare
  tools for in-browser agents. Relevant to §6.5.
- **Web Bot Auth (IETF drafts, HTTP message signatures):** a way for agents to identify
  themselves cryptographically. Relevant to §6.6.
- **W3C Design Tokens format:** for the design-system package (§4.2.1).
- **OAuth 2.0 Token Exchange (RFC 8693):** for delegated SaaS access (§7.3.1).
- **schema.org:** structured data per view (§6.4).
- **India DPDP Act 2023 and Rules, GDPR:** consent, purpose limitation, retention and
  erasure for taste profiles (§5.6).

### 11.4 Naming: "A2UI" becomes "FluidBuddha" (decision D10)

The backend's internal engineering name was the **"A2UI Orchestrator"** ("Agent-to-UI", the
voice-first agentic UI framework). It is renamed to the **FluidBuddha Orchestrator**, and
every use of "A2UI" that names **our own product** is replaced with "FluidBuddha". The reason
is that Google's open **A2UI** protocol (§11.3), which we may export to, uses the same name.

**What stays:** references to Google's A2UI protocol keep that name, because it is someone
else's standard.

**Where the old name appears in the repository today** (found by search on 6 November 2026;
the rename itself is separate work):

| Area | Files | Kind of change |
|---|---|---|
| Product docs | `version_1.0/FeatureList.md`, `version_1.0/TechnicalSpecification.md`, `old/functional_spec.md`, `docs/devdocs/handoff.md`, `docs/devdocs/functionality-report.md` | Text only |
| Backend text | `backend/README.md`, `backend/.env.example`, `backend/app/__init__.py`, `backend/app/main.py` (FastAPI title, startup log line), `backend/app/orchestrator/tools.py` (comment) | Text; the API title shows in the OpenAPI docs |
| SDK text | `fluid-buddha-sdk/README.md`, `fluid-buddha-sdk/src/core/config.ts` (comments), `fluid-buddha-sdk/package.json` (npm keyword) | Text and package metadata |
| Logger names | `backend/app/main.py` (`a2ui`), `backend/app/transport/websocket.py` (`a2ui.ws`), `backend/tests/test_observability.py` | **Operational:** log queries, dashboards or alert rules that filter on these logger names must change at the same time |
| Container names | `backend/docker-compose.yml` (`a2ui-cortex-db`, `a2ui-redis`, `a2ui-coturn`, `a2ui-backend`), `backend/scripts/backup.sh`, `backend/scripts/restore_drill.sh`, `backend/README.md` | **Operational:** running containers, backup and restore commands and developer habits change; plan it as a coordinated change with release notes |

Suggested new identifiers: `fluidbuddha` / `fluidbuddha.ws` for loggers and
`fluidbuddha-cortex-db`, `fluidbuddha-redis`, `fluidbuddha-coturn`, `fluidbuddha-backend` for
containers.
