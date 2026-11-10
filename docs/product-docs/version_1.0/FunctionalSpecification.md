# FluidBuddha — Functional Specification (version 1.0)

> **Basis.** Reverse-engineered from the code on branch `m2/foundations` (commit `12e325e`,
> 6 November 2026). Every rule, limit and default below is taken from the implementation.
> Where the behaviour depends on configuration, the default value is given and the setting
> is named.
>
> **Companion documents:** [FeatureList.md](FeatureList.md) (what the product offers and why
> it is different) and [TechnicalSpecification.md](TechnicalSpecification.md) (how it is
> built).
>
> **Requirement IDs.** Each functional requirement has an ID such as `FR-VOICE-03`, so tests,
> tickets and future versions can refer to it.

---

## Table of contents

1. [Introduction](#1-introduction)
2. [Actors and roles](#2-actors-and-roles)
3. [Core concepts and glossary](#3-core-concepts-and-glossary)
4. [Visitor experience: the widget](#4-visitor-experience-the-widget)
5. [The agent's behaviour](#5-the-agents-behaviour)
6. [Revenue functions](#6-revenue-functions)
7. [Hosted public pages](#7-hosted-public-pages)
8. [Agent endpoint for AI assistants](#8-agent-endpoint-for-ai-assistants)
9. [Admin console](#9-admin-console)
10. [Account, identity and security](#10-account-identity-and-security)
11. [Billing](#11-billing)
12. [Self-hosted edition and licence](#12-self-hosted-edition-and-licence)
13. [Background processes and notifications](#13-background-processes-and-notifications)
14. [Permissions matrix](#14-permissions-matrix)
15. [Limits and defaults (reference)](#15-limits-and-defaults-reference)
16. [Non-functional requirements](#16-non-functional-requirements)
17. [Out of scope and known limitations](#17-out-of-scope-and-known-limitations)

---

## 1. Introduction

### 1.1 Purpose

This document describes, in full functional detail, what FluidBuddha does for each of its
users: website visitors, the business's team in the admin console, operators of the
platform, and outside AI assistants. It is the reference for product, QA, support,
sales engineering and future development.

### 1.2 Product summary

FluidBuddha is an embeddable, voice-first AI sales agent for websites, delivered as one
script tag and run as a multi-tenant SaaS (or self-hosted). The agent answers visitors by
voice or text from the site's own content, draws interactive visuals, controls the page,
captures and qualifies leads, proposes confirmable actions, and hands conversations to the
team. The console lets the business set up, train, measure and grow the agent.

### 1.3 Scope

In scope: every behaviour implemented in `backend/`, `fluid-buddha-sdk/`,
`fluid-buddha-frontend/`, `integrations/` and `deploy/`. Out of scope: the third-party AI
coding skills in `skills/` and the planning documents in `docs/devdocs/`.

### 1.4 Conventions

- "Site" or "website" means one website registered by an account (a row in
  `tenant_websites`). Each has a **site key** (a slug) and a **widget key** (`fbk_…`).
- "Turn" means one visitor question and the agent's answer.
- "Must" marks a rule the code enforces. "May" marks optional behaviour.
- Defaults are given as "default X (`SETTING_NAME`)".

---

## 2. Actors and roles

| Actor | Description | Interface |
|---|---|---|
| **Visitor** | An anonymous person on a customer's website. | The `<fluid-buddha>` widget, hosted recap and campaign pages. |
| **Account member** | A signed-in person who belongs to an account, with one role per account. | Admin console. |
| ↳ **Owner** | Full control, including billing, SSO, security policy and licence. | Console. |
| ↳ **Admin** | Team, integrations, privacy and erasure, site deletion and key rotation, audit log, model provider, agent access, actions, digest. | Console. |
| ↳ **Editor** | Site content and behaviour: knowledge, tours, profile, answers, experiments, triggers, campaigns, leads, live takeover. | Console. |
| ↳ **Viewer** | Read-only. | Console. |
| **Operator (live)** | An Editor (or above) who takes over a live conversation or calls a visitor. | Console → Live. |
| **AI assistant** | An external AI agent (for example an MCP client) querying a site. | MCP, `llms.txt`, REST. |
| **Platform operator / on-call** | Runs the service: deploys, monitors and posts incidents. | Status API, metrics, runbook. |
| **Self-host administrator** | Installs and runs the self-hosted bundle. | Shell scripts, `.env`, console. |
| **Payment provider (Razorpay)** | Sends subscription and payment webhooks. | Webhook endpoints. |
| **Identity provider** | Google or an account's OIDC provider. | SSO redirect flow. |

---

## 3. Core concepts and glossary

| Term | Meaning |
|---|---|
| **Account (tenant)** | A business. It owns websites, billing, settings and members. |
| **User** | A person (email, optional password). One user can belong to several accounts. |
| **Membership** | A user's role in an account. |
| **Website** | A site the agent runs on. Fields: name, domain, intelligence tier, design level, accent colour, status, site key, widget key. |
| **Widget key** | `fbk_` followed by a random token. Embedded on the site. It identifies the site and fixes its tier on the server. |
| **Install code** | `https://fbk_…@<server>`: the widget key and server in one string, used by plugins. |
| **Agent profile** | The site's "brain" settings: who the agent is, how it sounds, its personas, routes, rules and more. |
| **Persona** | A visitor segment (for example "Enterprise") with a focus, tone and landing page. |
| **Intelligence tier** | `basic`, `high`, `advance` or `extreme`. Decides which tools the agent may use. |
| **Design level** | `level1` (Companion), `level2` (Presence) or `level3` (Atmosphere). Decides how the widget looks. |
| **Knowledge source** | Text, URL or uploaded file that feeds the site's knowledge tree. |
| **Grounding** | The confidence and sources behind an answer. |
| **Component** | A typed visual the agent draws (chart, flowchart, calculator…). |
| **Conversation** | A visitor session with at least one answered turn. It is also the billing unit. |
| **Cached answer** | A stored turn that can be replayed. Status `auto`, `pinned` or `blocked`. |
| **Lead** | A contact who wants follow-up, with a score and status. |
| **Action** | Something the agent can do for the visitor after confirmation (payment link, quote, trial, meeting, webhook). |
| **Run** | One proposed or executed instance of an action. |
| **Recap** | A shareable page that summarises one conversation. |
| **Trigger** | A rule for when the agent speaks first. |
| **Experiment** | A holdout run or a variant A/B test. One per site at a time. |
| **Campaign** | A brief from which a hosted landing page is composed. |
| **Takeover** | A person from the team answering a conversation instead of the agent. |

---

## 4. Visitor experience: the widget

### 4.1 Loading the widget

- **FR-WID-01** The widget must load from one script tag. The recommended tag is
  `<script src="https://<server>/widget/loader.js" data-key="fbk_…" async></script>`.
- **FR-WID-02** The loader must add the widget bundle (`fluid-buddha.global.js` from the
  configured `WIDGET_SDK_BASE`), copy every `data-*` attribute, and set `data-backend`
  (WebSocket base) and `data-api` (HTTP base) from its own address. It must load once per
  page and fire a `fluidbuddha:ready` event on `window` when loaded.
- **FR-WID-03** Where attributes cannot be set (Google Tag Manager), the loader must accept the
  same settings in its query string: `key`, `position`, `lang`, `design`, `accent`, `auto`,
  `auto-start`, `tour`, `navigation`.
- **FR-WID-04** The loader script is the same for every site and may be cached for 5 minutes.
- **FR-WID-05** Supported embed options (attribute or `init()` option):

| Option | Values | Default | Effect |
|---|---|---|---|
| `key` | `fbk_…` | — | Identifies a customer site. Required for tenant sites. |
| `site` | site key | `hirebuddha` | Only for built-in demo sites without a key. |
| `backend` / `api` | URLs | from the loader | WebSocket and HTTP bases. |
| `position` | `bottom-right`, `bottom-left` | `bottom-right` | Launcher corner. |
| `accent` | colour | site setting, else `#c9a24a` | Brand colour. |
| `greeting` | text | — | Local greeting override. |
| `auto` | `true` / `false` | `true` for script tags | `false` loads without showing (framework wrappers). |
| `auto-start` | `true` / `false` | `false` | Open and greet as soon as loaded (audio waits for the first gesture). |
| `intelligence` | tier | `advance` | Ignored when a key is used (the server decides). |
| `design` | level | site setting | Design level. |
| `tour` | `true` / `false` | `true` | `false` opts out of the guided tour. |
| `navigation` | `auto`, `spa`, `reload` | `auto` | How page changes are made. |
| `lang` | `auto`, `en`, `hi` | `auto` | Widget language. |

- **FR-WID-06** Programmatic use must be possible: `FluidBuddha.init(options)` returns the
  element. Hooks `onNavigate(path)`, `onScrollTo({sectionId, direction})` and
  `onSetPersona(persona)` replace the default page behaviour.
- **FR-WID-07** Before drawing, a keyed widget must enrol the visitor
  (`POST /experiment/enroll`, timeout 1.5 s). The response gives the visitor's experiment arm
  and variant overrides, and the site's defaults: greeting (and Hindi greeting), design level,
  accent, languages, widget language, starter questions (English and Hindi), agent name and
  memory status. If the visitor is in a **holdout**, the widget must not render.
- **FR-WID-08** The visitor id is a random string in `localStorage` (`fluidbuddha:vid`). If
  storage is unavailable, the visitor is not part of experiments and gets the agent. The
  arm is cached for 6 hours and refreshed in the background.
- **FR-WID-09** The widget's language is the embed's `data-lang` if the site allows it, else
  the site's widget-language setting, else the browser language (on `auto`). A site without
  Hindi is always English. The Hindi word table is fetched only for Hindi visitors. If it fails
  to load, the widget falls back to English.

### 4.2 Opening the agent and the welcome

- **FR-WEL-01** When the visitor opens the agent, the widget sends `hello` with the page path,
  title, section in view, up to 30 section anchors with labels, language, experiment variant,
  persona, visitor id and tour opt-out.
- **FR-WEL-02** The welcome runs once per conversation.
- **FR-WEL-03** The opening language is Hindi only when the widget is Hindi and the site has
  Hindi switched on.
- **FR-WEL-04** The greeting is chosen in this order:
  1. a returning visitor who opted into memory: the "welcome back" line;
  2. the visitor's A/B variant greeting;
  3. the site's fixed greeting (or Hindi greeting for a Hindi conversation);
  4. otherwise a grounded, page-aware welcome written by the agent (one or two sentences that
     name the agent, say what the page is about and invite a question or a tour).
- **FR-WEL-05** If the site has a usable guided tour, the tour is enabled (site and variant)
  and the visitor did not opt out, the server sends the tour plan instead of the welcome.
  A visitor welcomed back by memory never gets the tour.
- **FR-WEL-06** The starting persona is the variant's persona, else the site's default persona.
- **FR-WEL-07** Audio autoplay: the widget primes audio inside the opening gesture. If audio is
  still blocked, the welcome plays on the visitor's first click, tap or key press.

### 4.3 Microphone consent

- **FR-CON-01** When the site requires consent (default on), the widget must show a consent
  dialog before the first voice turn. It explains that the agent listens only while voice is
  on, that audio is not stored, that emails, phone and card numbers are masked, how long
  transcripts are kept, and links the privacy policy. Choices: *Allow microphone* or *Type
  instead*.
- **FR-CON-02** The choice is remembered per site in the browser. A wording change (consent
  version bump) asks again.
- **FR-CON-03** The server must discard all microphone audio until the widget reports consent.
  If audio arrives first, the server sends `consent_required` once.
- **FR-CON-04** The consent time is stored on the conversation.

### 4.4 A voice turn (end to end)

- **FR-VOICE-01** Voice activity detection: speech starts after energy above the start
  threshold (0.03) for 180 ms, continues above 0.018, and ends after 850 ms of silence. A 400 ms
  pre-roll is sent so the first word is kept. Audio is sent as 16 kHz mono PCM16.
- **FR-VOICE-02** One utterance may be at most 60 seconds of audio. Extra audio is ignored.
- **FR-VOICE-03** The transcript is taken from the client (browser speech recognition) when
  supplied, else from server speech recognition (expected language first, then the other of
  `en-IN` / `hi-IN`).
- **FR-VOICE-04** The server must then process the utterance in this order, stopping at the
  first step that handles it:
  1. A team member has taken over → the words go to that person (§6.6).
  2. Rate limit, daily spend cap or plan limit reached → a spoken refusal (§5.12).
  3. An utterance within 10 s of the previous one, while its reply is still running, is merged
     with it, and the earlier reply is cancelled.
  4. PII is masked (§5.10). A turn that contained PII is "personal".
  5. A short follow-up that depends on the conversation is marked as such (§5.3).
  6. The reply language is chosen (§5.9).
  7. An action card is open (within 15 minutes) and the utterance is a short yes or no → the
     card is answered (§6.3).
  8. "Forget me" → memory is deleted and confirmed aloud (§6.8).
  9. "Send me this" / "email me a recap" → the widget creates a recap (§6.5).
  10. Medical safety mode and a medical-advice or emergency question → fixed safe answer (§5.11).
  11. Not personal and not a follow-up, and a cached answer matches → replay (§5.7).
  12. Otherwise a fresh answer.
- **FR-VOICE-05** A fresh answer must proceed as follows:
  1. Echo the final transcript to the widget.
  2. Get the fast route: intent, persona signal and acknowledgement.
  3. Apply the persona rules (§5.4) and decide whether to ask a qualifying question.
  4. Start the answer (lean or heavy, §5.2) **concurrently**.
  5. Speak the acknowledgement.
  6. If the persona switched, tell the widget to re-theme.
  7. When the answer is ready, send components, generated pages and component patches.
  8. Send page commands (navigate, scroll) and any action cards.
  9. Speak the answer. Its first segment is linked to the first component, so the audio waits
     until that component has rendered.
  10. Record the turn in the background (transcript, usage and, where allowed, the answer cache).
- **FR-VOICE-06** The answer is spoken in sentence segments (at least 24 characters each). The
  first segment carries the full text and grounding (so the message and citations appear at
  once). The next segment is synthesised while the current one plays.
- **FR-VOICE-07** At the `basic` tier no speech is synthesised. The text and grounding still
  appear.
- **FR-VOICE-08** **Barge-in.** If the visitor starts speaking while the *answer* (not the
  acknowledgement) is playing, the answer stops, queued audio is cleared, any tour stops, and
  the widget shows "Re-calibrating…". Speech during the acknowledgement or thinking is treated
  as the visitor finishing their sentence and does not cancel the turn.
- **FR-VOICE-09** On an error the widget shows a short error message in the conversation
  language, and the turn ends.

### 4.5 A text turn

- **FR-TEXT-01** Typed questions go over the WebSocket when connected, else to `POST /chat`.
- **FR-TEXT-02** `/chat` must run the same pipeline as voice: takeover check, forget me,
  medical safety, replay, fresh answer. It returns the answer text, acknowledgement, intent,
  persona, page actions, components, pages, patches, grounding, session id, language and
  action cards.
- **FR-TEXT-03** A text conversation must keep its state between turns for 30 minutes of
  inactivity (`SESSION_TTL_MINUTES`). A session id is only valid on the site that created it.
- **FR-TEXT-04** While a person has taken over a text conversation, the widget long-polls
  `/chat/live` (up to 25 s per poll) for that person's replies.

### 4.6 Connection handling

- **FR-CONN-01** The widget reconnects with exponential backoff (0.5 s to 8 s, 4 attempts),
  then switches to text mode and says "Voice link unavailable — using text mode."
- **FR-CONN-02** When the server closes with code 1012 (restart) or 1013 (try again later), or
  sends `reconnect`, the widget reconnects quietly after about 2 s without counting a failure.
  A reconnected session repeats a consent already given.
- **FR-CONN-03** If the site is not reachable with the given key (`invalid_widget_key`,
  `origin_not_allowed`, `widget_key_required`), the socket returns an error and closes with
  code 4403, and `/chat` returns 403.

### 4.7 Design levels

- **FR-DES-01 Level 1 — The Companion.** A floating launcher showing the living Aura (breathing
  light that reacts to voice), opening a glass panel with the agent's avatar and status word,
  the messages (each grounded answer with a "grounded · NN % match" badge and Sources), a
  thinking indicator, up to 4 suggestion chips (the site's starter questions, else "Show me
  pricing", "How do you integrate?", "Give me a quick tour"), a text box and a mic button.
  Full-screen on mobile.
- **FR-DES-02 Level 2 — The Presence.** A full-screen smoke field tinted gold for the agent and
  silver for the visitor, driven by live audio. Includes an "Awaken" ring, a status word, a
  fading column of recent turns and a central surface for components. Closing leaves a small
  orb to reopen. Without WebGL it degrades gracefully.
- **FR-DES-03 Level 3 — The Atmosphere.** No widget. A breathing edge light, captions that last
  14 s (at most 4 on screen), a spotlight that dims the page and rings the referenced section
  for about 4.2 s, and a summon (⌘K / Ctrl-K or a light mote) with a prompt. The overlay does
  not block clicks on the page.
- **FR-DES-04** All levels show the same states (dormant, listening, thinking, speaking) and
  respect reduced-motion and high-contrast preferences.

### 4.8 Widget messages and offers

- **FR-OFF-01** After the third answer in a keyed site's conversation, the widget offers a
  "recap" chip once.
- **FR-OFF-02** After the first answer, if the site offers memory and the visitor has not opted
  in, the widget asks once per browser whether to remember the conversation. A remembered
  visitor sees a "Forget me" chip.
- **FR-OFF-03** Text shown by the widget is available in English and Hindi.

---

## 5. The agent's behaviour

### 5.1 Grounding and the guardrail

- **FR-GRD-01** Every factual claim must come from the site's knowledge base. The heavy
  thinker must call the knowledge search before any claim about capabilities, pricing,
  integrations, security or how the product works.
- **FR-GRD-02** Retrieval returns the top 5 snippets (`CORTEX_RETRIEVAL_TOP_K`). Confidence is
  the top snippet's similarity score.
- **FR-GRD-03** When confidence is below 0.45 (`CORTEX_CONFIDENCE_THRESHOLD`), the answer is
  "not found": only 2 snippets are passed on, with an instruction not to invent and to pivot to
  the closest supported capability or offer to connect the visitor with the team.
- **FR-GRD-04** Each answer carries citations: one per source document, best first, with a
  readable label (file names and URLs turned into titles) and the page route when known.
  Ungrounded answers show no sources.
- **FR-GRD-05** The agent knows which page the visitor is on. "This page" or "here" refers to
  that page, and the agent should not navigate away to answer about it.
- **FR-GRD-06** The site's rules (guardrails) override every other instruction.

### 5.2 Lean and heavy answers

- **FR-RTE-01** The fast router classifies intent as `greeting`, `capability`, `pricing_roi`,
  `integration`, `navigation` or `general`, infers a persona from the site's list, rates its
  confidence and whether it was stated outright, and writes an acknowledgement of 12 words or
  fewer. On failure, a default acknowledgement is used ("Let me look that up for you.", or its
  Hindi form).
- **FR-RTE-02** A turn goes to the **heavy** thinker when any of these is true:
  - the intent is `pricing_roi`, `integration` or `navigation`;
  - it mentions show, diagram, chart, graph, table, compare, calculate, ROI, pricing, price,
    cost, quote, integrate, navigate, take me, go to, scroll, walk me, draw, visual, generate,
    build me, demo, tour, pay, buy, purchase, subscribe, checkout, trial, book, schedule,
    meeting or sign me up;
  - a component is on screen and the visitor corrects something ("actually…", "change…",
    "make it…");
  - it contains an email address (so a lead can be captured).
  Otherwise it takes the **lean** path.
- **FR-RTE-03** Lean path: one retrieval, then one answer from the fast model in 2–4 short
  spoken sentences, using only the retrieved snippets, never reading out URLs or markup.
- **FR-RTE-04** Heavy path: up to 4 model rounds with tools. At most one knowledge search per
  turn. Extra searches are refused and the tool is withdrawn. Spoken text is kept from any
  round. If no answer was produced, one more round is forced ("answer in 2–3 sentences"), then
  a fixed fallback ("I want to get this exactly right — let me connect you with the team.").
- **FR-RTE-05** Spoken answers are kept to 2–4 sentences. Complex information should be shown
  as a component, not described at length.

### 5.3 Conversation memory within a session

- **FR-CTX-01** The agent keeps the last 12 question/answer pairs.
- **FR-CTX-02** A follow-up of 9 words or fewer that refers back ("it", "that", "they"…) or
  continues ("and…", "what about…", "tell me more") is searched together with up to two
  earlier questions. Such follow-ups are never replayed from or saved to the answer cache.
- **FR-CTX-03** The last 8 rendered components are remembered so the visitor can interact with
  them and the agent can patch them.

### 5.4 Personas

- **FR-PER-01** The agent may switch only to a persona defined in the site's profile. A site
  with none never switches.
- **FR-PER-02** A switch needs a confidence of at least 0.6. A visitor who states their
  segment outright locks the persona. A locked persona changes only on another explicit
  statement or a confidence of at least 0.9. A deliberate switch by the heavy thinker counts as
  0.8.
- **FR-PER-03** When the persona is unknown or weak (below 0.5), not locked, and at least 3
  turns have passed since the last one, the agent weaves one short qualifying question (team
  size, role or goal) into its answer.
- **FR-PER-04** On a switch, the widget re-themes the host page silently (§5.6) and later
  answers use that persona's focus and tone.

### 5.5 Components

- **FR-CMP-01** At `advance` and `extreme` tiers the agent may draw these components:

| Component | Data | Interactive |
|---|---|---|
| flowchart | nodes, edges | — |
| workflow | steps (start, process, decision, end), labelled transitions | — |
| component_diagram | boxes, connections | — |
| graph | nodes, edges, directed | — |
| chart | bar, line or pie; title; unit; data | — |
| roi_calculator | seats, monthly cost, hours saved, hourly value (default ₹500 for INR, else 45) | sliders, live result |
| table | headers, rows | — |
| mind_map | topic, branches with children | expand/collapse, pan/zoom; state reported |
| timeline | dated events with detail | hover details |
| sankey | nodes (optional column), weighted links | hover values |
| configurator | sliders, toggles, selects; outputs from arithmetic formulas | live outputs; state reported |
| scenario_simulator | sliders; series from formulas | live bars; state reported |
| tabs | label and body per tab | active tab reported |

- **FR-CMP-02** Formulas may use only control keys, numbers and `+ - * / ( )`. They are
  evaluated without `eval`.
- **FR-CMP-03** An unknown component type is drawn as a table. Every list in a component is
  capped at 48 items. Money components use the site's currency.
- **FR-CMP-04** When the visitor changes an interactive component, the agent waits 0.7 s for
  the visitor to settle, then speaks one short insight about the new values (never reading
  the numbers back). It stays silent if it is already speaking, a turn is running, or it has
  nothing useful to say.
- **FR-CMP-05** When a visitor corrects a value while a component is on screen, the agent must
  patch that component (only the changed fields, optional fade, count-up or highlight)
  instead of drawing a duplicate. Only components visible in this conversation can be patched.
- **FR-CMP-06** **Custom components.** A site's own components appear to the agent alongside
  the built-in ones (§9.14). The agent supplies props. The server checks them against the
  component's schema and tells the agent what is wrong if they do not fit.
- **FR-CMP-07** **Generated pages (`extreme` only).** The agent may compose a page from up to 12
  sections of these types: hero, feature_grid, text, pricing_table, chart, flowchart,
  enquiry_form, cta, media, testimonials, logos, faq, comparison, roi_calculator. All copy must
  come from retrieved content. Styling comes from the brand's design tokens. A page title is at
  most 160 characters. Unknown sections are dropped. An enquiry form on such a page becomes a
  lead.
- **FR-CMP-08** **Site API calls (`extreme` only).** The agent may call operations declared in
  the site's OpenAPI spec, by operation id. Undeclared operations are refused. Without a
  configured base URL the call is simulated.

### 5.6 Page control

- **FR-NAV-01** The agent may only navigate to the site's known routes (its sitemap) or paths
  under its dynamic prefixes. A guess is snapped to a close route (similarity of at least 0.82,
  or a unique match on the last path segment), otherwise the navigation is dropped and the
  agent is told the route is invalid.
- **FR-NAV-02** Navigation in `auto` mode pushes the route to history and fires `popstate` so a
  single-page app can render it. If nothing changes within 600 ms, a normal page load is made.
  `spa` never reloads. `reload` always loads the page.
- **FR-NAV-03** Scrolling supports `down` and `up` (about 85 % of the viewport), `top`,
  `bottom`, or a named section. A section is found by exact id, then id substring, then heading
  text.
- **FR-NAV-04** Persona re-theming sets `data-fb-persona` on `<html>` behind a 300 ms blurred
  cross-fade (instant under reduced motion), unless the host's `onSetPersona` hook handles it.
- **FR-NAV-05** Every command fires a `fluidbuddha:navigate`, `fluidbuddha:scroll_to` or
  `fluidbuddha:set_persona` event on `window`. Cancelling the navigate event lets the host
  route it.
- **FR-NAV-06** Routes are learned automatically from crawled and URL sources, and can be
  edited in the agent profile.

### 5.7 Answer replay (conversation cache)

- **FR-CCH-01** Every answered turn that is not personal, not a follow-up, did not patch a
  component, did not capture a lead and did not propose an action is recorded with its
  question, answer, components, page actions, persona, page, language and sources.
- **FR-CCH-02** On a new question the cache is searched for the same persona and language:
  first an exact match of the normalised question, then by meaning.
- **FR-CCH-03** Replay rules:
  - a **pinned** answer that matches replays always;
  - otherwise at least 20 recorded turns for the persona are needed
    (`EPISODIC_MIN_EPISODES`);
  - a match score of at least 0.92 (`EPISODIC_REPLAY_THRESHOLD`) replays the stored answer,
    components and audio verbatim, after a short acknowledgement;
  - a score of at least 0.70 (`EPISODIC_CONTEXT_THRESHOLD`) passes up to 3 past answers to the
    agent as context for a fresh answer;
  - **blocked** questions never replay and are never re-cached.
- **FR-CCH-04** Each replay increments the entry's hit count.
- **FR-CCH-05** When a site's knowledge changes, its automatic cached answers and audio are
  cleared. Pinned and blocked entries stay.
- **FR-CCH-06** Spoken sentences are cached as audio by text, voice and language, so repeated
  sentences cost nothing and sound the same.

### 5.8 Guided tour

- **FR-TOUR-01** A tour is planned once from the site's pages (up to 14) after ingestion: 6 to
  9 stops, each with a 1–3 sentence narration and an optional move (navigate to a route, or
  scroll down/top/bottom/to a section). It opens with a one-sentence welcome, walks 2–4 key
  pages and ends with a concrete use case: a realistic manual task, how the product would
  automate it, setup time, and illustrative monthly and yearly time and money saved.
- **FR-TOUR-02** If the site has a tour outline (from a template), the planner follows it.
- **FR-TOUR-03** If planning fails, a fallback tour is built from the homepage and up to three
  other pages, ending with the site's closing use case.
- **FR-TOUR-04** Playback: for each stop the widget asks the server to speak stop *n*. The
  server speaks only the stored narration for that index (never arbitrary text). After all
  audio for the stop has been sent and played, the widget performs the move, waits 450 ms and
  continues. A safety cap of 20 s applies if the "done" signal is lost.
- **FR-TOUR-05** The tour stops on barge-in, a typed question, closing the widget or turning
  voice off.
- **FR-TOUR-06** Each played stop is recorded (never replayed as an answer).
- **FR-TOUR-07** Re-ingesting replans the tour unless an owner has edited it. "Generate" in the
  console always replaces it.

### 5.9 Languages

- **FR-LANG-01** The agent answers in English, or in Hindi when the site has switched Hindi on.
- **FR-LANG-02** Language choice per turn:
  1. A site without Hindi always answers in English.
  2. "Reply in Hindi" or "English please" (in either language) sets the preference for the
     rest of the conversation.
  3. A question in Devanagari is answered in Hindi. A plain English question is answered in
     English unless Hindi was asked for.
  4. Hinglish (Hindi in Latin letters) gets clear, Indian-friendly English, unless the visitor
     prefers Hindi (asked for it, the widget is Hindi, or they wrote Devanagari earlier).
- **FR-LANG-03** For non-English questions the router also writes an English search query, so
  the English knowledge base is searched correctly at no extra model cost.
- **FR-LANG-04** Speech recognition listens for the expected language first, then the other of
  Indian English and Hindi. Speech synthesis is pinned to Hindi for Hindi answers.
- **FR-LANG-05** Cached answers are kept per language.

### 5.10 Privacy in conversations

- **FR-PII-01** When masking is on (default), emails, phone numbers, card numbers (Luhn-valid),
  US SSNs and IBANs are replaced by placeholders (`<EMAIL_1>`, …) before the router, the thinker
  or the history see the message.
- **FR-PII-02** The agent never reads a placeholder aloud. It says "your email", "your phone
  number" and so on.
- **FR-PII-03** Transcripts store labels such as `[email]`. Turns with PII are never cached.
- **FR-PII-04** Only lead capture and actions receive the real values back.
- **FR-PII-05** Visitor microphone audio is never stored.

### 5.11 Medical safety mode

- **FR-SAFE-01** For a site in medical safety mode (the Healthcare template), a question that
  asks for a diagnosis, treatment, medicine or dose gets a fixed polite refusal with an offer to
  book an appointment. A question that sounds like an emergency gets the emergency numbers.
- **FR-SAFE-02** These answers are given before any model call, recognised in English, Hindi
  and Hinglish, and are never cached.

### 5.12 Refusals and limits

| Condition | Visitor is told | Code |
|---|---|---|
| More than 120 turns per minute on the site (`PUBLIC_RATE_LIMIT_PER_MIN`) | "I'm getting a lot of questions right now. Please try again in a minute." | `rate_limited` |
| The site's AI spend today reached the daily cap (`PUBLIC_DAILY_SPEND_CAP_USD`, default off) | "I'm not available for the rest of today. Please try again tomorrow." | `spend_cap_reached` |
| Free plan allowance used and this would start a new conversation | "I'm not available right now. Please contact the team directly." | `plan_limit_reached` |

- **FR-LIM-01** A conversation already under way on the Free plan may finish.
- **FR-LIM-02** Spend from the account's own model provider is not counted towards the daily
  spend cap.

---

## 6. Revenue functions

### 6.1 Lead capture in conversation

- **FR-LEAD-01** When a visitor gives an email or asks to be contacted, booked or sent details,
  the agent saves a lead with email (required), name, company and interest, exactly as the
  visitor said them. It must never invent an email.
- **FR-LEAD-02** The agent asks for an email only when the visitor wants follow-up, and never
  for more than name, email and company, plus any extra lead fields the site's profile lists.
- **FR-LEAD-03** After saving, the agent confirms that someone will follow up.
- **FR-LEAD-04** A lead is linked to its conversation.

### 6.2 Enquiry forms

- **FR-FORM-01** Forms in the widget (generated pages) and on campaign pages post directly to
  the server. Contact details never pass through the model.
- **FR-FORM-02** Accepted fields: email, name, company, phone, message, interest, and up to 20
  extra values. Field lengths are capped (name 200, email 320, company 200, phone 50, message
  4,000, interest 500).
- **FR-FORM-03** At most 20 form leads per minute per site.

### 6.3 Lead scoring, delivery and pipeline

- **FR-SCORE-01** Lead score (0–100): 20 for a reachable email; +10 each for name, company and
  phone; +10 per question asked (up to 30); +10 for a known persona; +15 if any question or the
  message is about buying (pricing, cost, quote, demo, trial, buy, purchase, plan, contract,
  onboarding, integration). Recap views add 5 (first view) and 10 per forward, capped at 100.
- **FR-SCORE-02** The lead carries a summary of what the visitor asked.
- **FR-DEL-01** New leads are sent to the site's webhook (if set) as a signed POST, retried
  after 0.5 s and 1.5 s, with a 5 s timeout. The outcome is recorded on the lead.
- **FR-DEL-02** Leads at or above the hot-lead score (default 60) are also posted to the site's
  Slack webhook.
- **FR-DEL-03** Lead status is one of new, contacted, qualified, won or lost.

### 6.4 Actions (visitor-confirmed)

- **FR-ACT-01** An action is offered to the agent only when enabled for the site. The agent
  uses it when the visitor asks for it or agrees to it.
- **FR-ACT-02** Calling an action never runs it. The server checks the inputs against the
  action's fields (unknown inputs dropped; missing ones make the agent ask for them), stores a
  proposed run, and the widget shows a confirmation card with a summary of each input and the
  amount. The agent must tell the visitor to check and press Confirm, and never say it is done.
- **FR-ACT-03** Only the visitor of the same conversation can confirm, within 15 minutes, by
  pressing Confirm or by a short spoken "yes" (for example "yes, go ahead", "confirm", "haan",
  "ठीक है"). "No", "cancel", "nahin" and similar cancel it. Longer sentences go to the agent as
  normal.
- **FR-ACT-04** A confirmed run executes once (never retried) and its outcome (message and an
  optional link) is shown on the card. The agent is told the outcome.
- **FR-ACT-05** Action kinds:

| Kind | Inputs | On confirm |
|---|---|---|
| `payment_link` | Plan (from the owner's price list), visitor details | A Razorpay Payment Link on the tenant's own Razorpay account for the listed amount. Razorpay emails it. The run becomes `paid` from the webhook or a poll. |
| `quote_request` | Visitor details, request details | A lead (source `quote`) delivered like any lead, emailed to the site's owners, downloadable as a one-page PDF. |
| `trial` | Visitor details | A signed POST to the tenant's backend, which returns a login link. |
| `meeting_link` | Visitor details | The tenant's booking page (Calendly, Cal.com or plain) with the details pre-filled. No outbound call. |
| `webhook` | Fields defined by the tenant (up to 8: text, email, number, integer, boolean, choice) | A signed POST of the inputs. A `message` in the JSON response is shown. |

- **FR-ACT-05a** Every built-in kind except `webhook` also saves the visitor as a lead (source
  `payment`, `quote`, `trial` or `meeting`), delivered like any other lead. A paid payment link
  marks its run and lead as paid.
- **FR-ACT-06** Money is never an input. The amount always comes from the price list (up to 20
  prices), shown with Indian digit grouping (for example ₹1,49,999.50).
- **FR-ACT-07** Limits: 10 proposals per conversation per hour, a per-action hourly run limit,
  and 30 confirmations per minute per site.

### 6.5 Recap pages

- **FR-RCP-01** A visitor who types or says "send me this", "email me a recap", or the Hindi or
  Hinglish equivalents, gets a recap link instead of an agent turn. A spoken email ("name at
  example dot com") is understood.
- **FR-RCP-02** A recap needs at least one question in the conversation ("Ask me something
  first…"). Asking again refreshes the snapshot and keeps the link.
- **FR-RCP-03** With an email, the link is emailed and the email becomes a lead.
- **FR-RCP-04** The recap page shows a summary, the answers (masked as stored), the components
  redrawn and still interactive, the sources and the site's call to action. It works without
  JavaScript.
- **FR-RCP-05** Links expire after the site's recap period (default 90 days; 7, 30, 90, 180
  or 365). Expired and unknown links look the same. A recap is deleted with its conversation.
- **FR-RCP-06** Views are counted per viewer (cookie). Each viewer after the first is a
  forward. Link-preview bots are not counted.
- **FR-RCP-07** At most 30 recap requests per minute per site.

### 6.6 Live takeover and voice handoff

- **FR-LIVE-01** The console lists who is talking to the agent now on the account's sites,
  with the last question, lead score and takeover state. A visitor counts as live for 120 s
  after their last heartbeat (every 30 s).
- **FR-LIVE-02** Operators see every question and answer stream in.
- **FR-LIVE-03** An Editor may take over. Only one person can hold a conversation. The agent
  stops mid-answer and the visitor is told "<Name> from the team joined the conversation."
- **FR-LIVE-04** While taken over, the visitor's messages go to the operator (stored masked).
  The operator's replies appear in the widget.
- **FR-LIVE-05** On hand-back the visitor is told, and the agent's history is updated with what
  was said so it does not repeat or contradict it.
- **FR-LIVE-06** If the visitor leaves, the takeover ends and the operator is told.
- **FR-LIVE-07** **Voice call.** The operator holding a voice conversation may call the visitor
  (WebRTC). The visitor sees an accept dialog. During the call the agent does not listen.
  Either side may hang up. The call duration is noted in the conversation.
- **FR-LIVE-08** Relay credentials for calls expire after `TURN_TTL_SECONDS` (default 1 hour).

### 6.7 Proactive triggers

- **FR-TRG-01** A site may have up to 20 trigger rules. Each has a name, enabled flag, kind,
  pages, message, compose flag, action, daily cap and priority:

| Kind | Parameter | Range |
|---|---|---|
| `time_on_page` | seconds | 3–600 |
| `scroll_depth` | percent | 10–100 |
| `exit_intent` | — | Desktop: pointer leaves through the top. Touch: a fast flick up after scrolling at least a screen, after a few seconds on the page. |
| `return_visit` | visits, within days | 2–50 visits within 1–90 days |

- **FR-TRG-02** Pages are glob patterns (up to 20). `/pricing*` matches `/pricing` and
  `/pricing/teams`. No patterns means every page.
- **FR-TRG-03** The message is at most 280 characters. With *compose* on, the agent writes a
  short opener (up to 160 characters) for each page and language, cached server-side. The
  rule's own message is the fallback (model unavailable, bot, page outside the rule's pages,
  or more than 200 cached pages for the rule).
- **FR-TRG-04** The action is `nudge` (a bubble next to the launcher; × dismisses it) or
  `open` (opens the agent with the message as its opener).
- **FR-TRG-05** Caps: at most one trigger per page view (highest priority wins a tie);
  `max_per_day` (1–10) per visitor per rule; nothing more this visit after a dismissal or once
  the visitor starts talking; never while the agent is open.
- **FR-TRG-06** The widget reports `shown`, `clicked`, `dismissed` and `engaged` (asked a
  question after clicking). At most 5 events per visitor per day are counted. Bots are ignored.
- **FR-TRG-07** Rules are cached in the browser for 10 minutes.

### 6.8 Returning-visitor memory (opt-in)

- **FR-MEM-01** Off by default. A site switches it on in Privacy settings and chooses how long
  memories are kept after the last visit (30, 90, 180 or 365 days; default 180).
- **FR-MEM-02** The visitor opts in by choosing "Remember me". From then on the visitor's
  conversations on that site (voice or text, including the current one) are linked to their
  anonymous visitor id.
- **FR-MEM-03** A memory is rebuilt after a conversation has been quiet for 10 minutes, from the
  visitor's newest three conversations (already PII-masked): latest questions, components
  explored, what the agent could not answer, and whether they left their details.
- **FR-MEM-04** On the next visit the agent greets them, for example: "Welcome back! Last time
  you asked: '…?' Want to pick up where we left off?" (English or Hindi). The agent has the
  notes at the start of the conversation. The guided tour is skipped.
- **FR-MEM-05** "Forget me" (chip, typed or spoken, including Hindi) deletes the memory and
  unlinks the conversations, confirmed with "Done — I've forgotten our past conversations…".
  If nothing was stored, the agent says so.
- **FR-MEM-06** Memory is also removed by erasure by email, retention, switching the setting off
  or deleting the site. A memory belongs to one site.

---

## 7. Hosted public pages

### 7.1 Campaign landing pages

- **FR-CAMP-01** A live campaign is served at `/p/{site_key}/{slug}`. Drafts open only through
  the console's preview link (not counted, no agent on the page).
- **FR-CAMP-02** Link parameters personalise the page:

| Parameter | Effect |
|---|---|
| `persona` (or `utm_content` naming a persona) | Which persona the page is composed for. |
| `q` (or `utm_term`) | A question answered first. |
| `account` | "Prepared for <account>", pre-filled in the form. Applied at render time and never costs a composition. |
| `lang=hi` | Hindi. |
| `utm_source` | Reported as the traffic source. |
| `embed=1` | Iframe mode, allowed only from the site's domain and the campaign's listed origins. |

- **FR-CAMP-03** The page always has a hero (the first key message is the headline) and a call
  to action. It may use only the sections the campaign allows: feature grid, text, pricing
  table, testimonials, logos, FAQ, comparison, ROI calculator, chart, enquiry form and image.
- **FR-CAMP-04** Composition rules (applied whatever composed the page):
  - factual sections must cite real sources from the site's knowledge;
  - every number on the page must appear in what it cites or in the campaign brief;
  - testimonials and logos appear only as supplied, never invented;
  - pinned answers are quoted word for word, and blocked questions are never answered;
  - the enquiry form is always the same safe form;
  - anything that fails is dropped and listed on the cached page spec.
- **FR-CAMP-05** The account's own model (if set) or the platform's model composes the page. In
  mock mode, past 20 compositions per minute per site, or past the daily spend cap, a
  rule-based composer that only quotes the material is used.
- **FR-CAMP-06** Pages are cached per campaign version, arm, persona, question, language and
  content version. Editing the campaign or re-ingesting content composes afresh.
- **FR-CAMP-07** An optional version B (headline, messages, call to action) is shown to half
  the visitors.
- **FR-CAMP-08** The enquiry form posts to `/p/…/lead` (a lead with source `campaign`, and a
  conversion; 10 per minute). The call to action goes through `/p/…/go` (a conversion, then a
  redirect).
- **FR-CAMP-09** Numbers are per unique visitor, credited to the arm, persona and source of
  their first view: views, engaged (scrolled past half, 15 s visible, or used a component or the
  agent) and converted. Bots are not counted. With a version B, the verdict uses the same
  always-valid test as experiments.
- **FR-CAMP-10** The site's widget is on the page. The page reads fully without JavaScript.

### 7.2 Recap page

See §6.5.

### 7.3 Status page

- **FR-STAT-01** `/status` (and `/status.json`) shows each component (API, widget and console;
  answers and voice agent; background jobs; email), its current state, 90 days of daily bars and
  uptime, and incidents. No sign-in is needed. The page refreshes itself and uses no scripts.
- **FR-STAT-02** Components are sampled every 60 s from the readiness checks. An open incident
  makes a component worse (major → degraded, critical → down).
- **FR-STAT-03** The on-call engineer posts incidents and updates with the status token. Impacts:
  minor, major, critical, maintenance. Statuses: investigating, identified, monitoring,
  resolved, scheduled. `resolved` closes an incident.

### 7.4 Digest unsubscribe page

- **FR-UNSUB-01** The link in each digest opens a page with an Unsubscribe button (opening the
  link alone does not unsubscribe, because link scanners open links). Mail clients' one-click
  unsubscribe works. An unsubscribed address is never mailed again unless that person
  resubscribes from the console.

---

## 8. Agent endpoint for AI assistants

- **FR-AGT-01** Off by default. An Admin switches it on per site.
- **FR-AGT-02** With the site's widget key in the path, assistants can use:
  - `POST /mcp/{key}`: an MCP server (JSON-RPC 2.0 over HTTP, stateless, answers as JSON;
    protocol versions 2025-11-25, 2025-06-18, 2025-03-26 and 2024-11-05);
  - `GET /sites/{key}/llms.txt`: what the site is and how to ask it;
  - `GET /sites/{key}/openapi.json`: the REST endpoints below;
  - `POST /agent/{key}/ask` `{question}` (up to 1,000 characters): a grounded answer with
    sources;
  - `GET /agent/{key}/offerings`: plans and prices.
- **FR-AGT-03** Tools for anyone with the key: `search_knowledge` (one grounded turn of the
  site's agent with the same guardrails: citations, pinned and blocked answers, medical safety),
  `get_page` (a grounded summary of one page) and `list_offerings` (from knowledge and the
  site's payment price lists). Resources are the site's crawled pages.
- **FR-AGT-04** With a customer-issued token (`Authorization: Bearer fbat_…`): `capture_lead`
  (scope `leads`) and `action_<name>` (scope `actions`). The token is the authorisation, so
  actions run at once (amounts still come from the price list). Tokens are shown once and
  belong to one site.
- **FR-AGT-05** Limits: 30 requests per minute per site and client address; the site's daily
  spend cap applies; a browser `Origin` must be the site's domain.
- **FR-AGT-06** Every call is logged as agent traffic (by tool and by assistant). Usage from
  these calls is never billed as a conversation.

---

## 9. Admin console

The console is a web app. Its navigation has global pages (Dashboard, Live, Team, Audit log,
Billing, AI model, Licence, Security) and, per website, tabs: Install, Ingestion, Tour,
Insights, Leads, Responses, Analytics, Holdout, A/B tests, Triggers, Campaigns, Actions,
Agent access and Settings. Pages and buttons are shown according to the member's role.

### 9.1 Dashboard and websites

- **FR-CON-WEB-01** The dashboard lists the account's websites with name, domain or key, tier
  and design badges, and status.
- **FR-CON-WEB-02** *Add a website*: name (required, up to 120 characters), domain, intelligence
  tier, design level, accent colour, and optionally a starting template (B2B SaaS, Education,
  Real estate, Healthcare). The site key is a unique slug of the name (with `-2`, `-3`… on
  clashes). A widget key is generated.
- **FR-CON-WEB-03** A website can be edited (name, domain, tier, design, accent, status).
- **FR-CON-WEB-04** *Rotate key* (Admin) issues a new widget key. The old key stops working at
  once.
- **FR-CON-WEB-05** *Delete* (Admin) removes the website and all of its data: knowledge,
  profile, tour, caches, usage, conversations, leads, integrations, privacy settings, design,
  experiments, alerts, live state, triggers, recaps, actions, components, memories, agent
  tokens and traffic, and campaigns.
- **FR-CON-WEB-06** On a self-hosted install, adding a website beyond the licence's site count
  is refused.

### 9.2 Install

- **FR-CON-INS-01** Shows the install snippet and install code, with per-platform instructions
  for the plain snippet, WordPress, Shopify, Google Tag Manager, Webflow, Framer, React and Vue.
- **FR-CON-INS-02** *Test connection* checks the key with `/widget/config` (site, tier, design,
  accent, agent and company names, languages, privacy) without running an agent turn.
- **FR-CON-INS-03** A *Preview on your site* bookmarklet drops the widget onto any page.
- **FR-CON-INS-04** The Google Tag Manager template can be downloaded, generated for this server.

### 9.3 Ingestion and onboarding

- **FR-CON-ING-01** *Crawl your website*: URL (defaults to the site's domain), maximum pages
  (default 25, capped at 50) and depth (default 2, capped at 3). Progress shows the phase
  (crawling, ingesting, personas, design, done), pages found, ingested and skipped, personas
  added, whether design was found, errors and duration. A job not finished in 30 minutes is
  treated as stale.
- **FR-CON-ING-02** The crawler must obey `robots.txt` for its user agent (a 401/403 robots file
  means stay out), honour a crawl delay up to 2 s, seed from up to 5 sitemaps (one level of
  sitemap index), stay on the same site, skip assets and `noindex` pages, read linked PDFs (up to
  10 MB), and treat each path (without query or fragment) as one page.
- **FR-CON-ING-03** Each crawled page becomes a URL source (a re-crawl refreshes it, never
  duplicates) and a navigable route.
- **FR-CON-ING-04** If the site has no personas, audience URLs (`/for/…`, `/solutions/…`,
  `/industries/…`, `/use-cases/…`, `/customers/…`, `/teams/…`, `/roles/…`, `/segments/…`,
  `/verticals/…`, `/sectors/…`, and similar) become personas (up to 6). With a real model and
  no such URLs, 2–4 are proposed from page titles. Existing personas are never changed.
- **FR-CON-ING-05** Brand design (colours, fonts, radius, logo, name) is read from the homepage
  and its same-site stylesheets.
- **FR-CON-ING-06** Sources can also be added by hand: pasted text (name and content), a URL, or
  an uploaded file (PDF, DOCX, Markdown, TXT, HTML, CSV, JSON; up to 10 MB). PDFs up to 300 pages
  are read. A scanned PDF with no text is refused with a clear message.
- **FR-CON-ING-07** *Run ingestion* ingests pending sources in the background. Each source
  shows its status (pending, ingested, failed), node count, a preview and any error. The tour
  is replanned (unless edited) and cached answers are cleared.
- **FR-CON-ING-08** Deleting a source deletes the knowledge built from it.
- **FR-CON-ING-09** URL fetching must refuse private, loopback, link-local and other non-public
  addresses, URLs with credentials and non-http(s) schemes. Every redirect (up to 3) is checked.
  Responses are capped at 2 MB (10 MB for crawled PDFs) and 15 s.

### 9.4 Tour editor

- **FR-CON-TOUR-01** View the tour's stops. Edit each narration, its move (navigate route, or
  scroll target) and label. Add, delete and reorder stops. Save.
- **FR-CON-TOUR-02** *Generate from content* replans the tour from ingested sources and replaces
  the current one (refused before anything is ingested).
- **FR-CON-TOUR-03** A saved tour is marked as edited, so re-ingestion does not overwrite it.

### 9.5 Insights

- **FR-CON-INSI-01** Headline numbers, top questions, knowledge gaps (questions the agent could
  not ground, each a source worth adding), and the funnel from visitors to engaged visitors (2 or
  more turns).
- **FR-CON-INSI-02** A conversations list and a transcript viewer for each conversation.
- **FR-CON-INSI-03** *Deal signals*: objections by type (price, security and privacy,
  integrations, implementation effort, trust, timing) with a trend against the previous period;
  competitor mentions (the profile's list plus those the model spots); feature requests grouped
  by meaning; buying signals (including Hindi). Each example opens its conversation.
- **FR-CON-INSI-04** A feature request can be sent to the site's Slack, its signed webhook
  (event `feature_request`) or an email address, with up to 5 examples.
- **FR-CON-INSI-05** *Answer a visitor question*: from a knowledge gap, the owner writes the
  answer in their own words, and it is added as a text source (named after the question).

### 9.6 Leads

- **FR-CON-LEAD-01** A list of leads with contact details, score and reasons, summary, source,
  status, delivery outcome and recap views and forwards. Status can be changed.
- **FR-CON-LEAD-02** *Shared recaps*: recent recap links with views and forwards. A link can be
  taken down.

### 9.7 Responses (answer cache)

- **FR-CON-CCH-01** Search and page through cached answers with persona and channel badges, hit
  counts and status.
- **FR-CON-CCH-02** Edit the question (it is re-indexed), the answer, components and page
  actions. Set the status to auto, pinned or blocked. Delete an entry.

### 9.8 Analytics

- **FR-CON-ANA-01** For a date range, grouped by day, hour or session: total cost; cost by stage
  (speech-to-text, text-to-speech, fast model, thinker model, tool calls); turns; cache hit rate;
  generated versus cached cost; average, p50 and p95 latency; and time to first audio (median
  and p95). Spend on the account's own model provider is shown separately.
- **FR-CON-ANA-02** Recent cost alerts for the site.

### 9.9 Holdout

- **FR-CON-HOLD-01** Switch the holdout on or off, set the holdout share (1–50 %, default 10 %)
  and the goal page. Changing the share starts a new run. Changing the goal page does not.
  *Restart* starts a fresh run with the same settings.
- **FR-CON-HOLD-02** Results per arm: visitors, conversions and rate with a 95 % Wilson interval;
  the difference with a Newcombe interval; relative lift with a log-scale interval; the
  p-value; and the verdict: `collecting` (until each arm has 30 visitors and both together have
  10 conversions), `trending` (only the fixed-horizon interval excludes zero: keep it running)
  or `significant` (the always-valid interval excludes zero). Bots turned away are counted.
- **FR-CON-HOLD-03** Planner: visitors needed for 80 % power to detect a relative lift (default
  20 %) over a baseline (the holdout's own rate once it has 30 visitors, else 3 %), and the days
  left at current traffic.
- **FR-CON-HOLD-04** Leads captured by the agent are not counted as conversions (the holdout
  cannot produce them).

### 9.10 A/B tests

- **FR-CON-AB-01** Create a test with a name, a subject (greeting, trigger, tour, persona or
  design), 2–4 variants (`a` is the control) with labels and overrides, an optional holdout
  (0–50 %) and a goal page.
- **FR-CON-AB-02** Only one experiment (holdout or test) runs per site. Starting a test stops a
  running one.
- **FR-CON-AB-03** Results compare each variant with the control at a split error budget
  (5 % divided by the number of comparisons), so the chance of any false winner stays at or
  below 5 % however often the results are read. With a holdout, the agent overall is also
  compared with the holdout.
- **FR-CON-AB-04** *Make default* applies the winner and ends the test: the greeting, starting
  persona and tour switch go to the agent profile; the design level to the website; for a
  trigger test the winning variant's triggers are switched on and the other tested ones off.
- **FR-CON-AB-05** A planner estimates the visitors needed.

### 9.11 Triggers

- **FR-CON-TRG-01** Create, edit, enable/disable and delete trigger rules (§6.7).
- **FR-CON-TRG-02** Each rule shows its last 30 days: distinct visitors shown, clicked,
  dismissed and engaged, and the rates.

### 9.12 Campaigns

- **FR-CON-CAMP-01** Create and edit a campaign: name, slug (lowercase letters, digits and
  hyphens, up to 60), status (draft, live, paused), goal, audience, persona, key messages,
  allowed sections, call-to-action label and https link, testimonials, logos, optional version
  B and embed origins.
- **FR-CON-CAMP-02** Preview link for drafts and edited live campaigns (changes with every edit).
- **FR-CON-CAMP-03** Analytics (§7.1, FR-CAMP-09) and the cache, with *Clear cache*.

### 9.13 Actions

- **FR-CON-ACT-01** Admins create, edit, enable and delete actions: kind, name (tool name),
  label, description, settings (price list, booking style and URL, endpoint URL, custom
  fields) and secrets (Razorpay key id and secret, webhook secret).
- **FR-CON-ACT-02** Secrets are never shown again. The console only shows whether each is set.
  Admins can read the signing secret and the Razorpay webhook URL for an action.
- **FR-CON-ACT-03** Recent runs list each run's status and outcome. A confirmed quote request
  downloads as a PDF.
- **FR-CON-ACT-04** A template's suggested actions are listed in its preview in Settings (to be
  set up under Actions).

### 9.14 Custom components

- **FR-CON-COMP-01** Register a component with a name (2–40 lowercase letters, digits or `_`,
  not a built-in name), label, description, kind and props schema.
- **FR-CON-COMP-02** The props schema has 1–20 props of type string (optional enum of 1–30
  values), number or integer (optional minimum and maximum), boolean or array (of strings,
  numbers or flat objects with 1–10 properties; up to 48 items). Props may have defaults, which
  must themselves be valid.
- **FR-CON-COMP-03** **Template** kind: a built-in base component and a state using `{{prop}}`
  placeholders (up to 20 KB). Only declared props may be used.
- **FR-CON-COMP-04** **Iframe** kind: an https URL. It runs in a sandbox (scripts only: no
  same-origin access, no top navigation, no forms, no popups, no referrer). The widget sends
  `fb:init` with props. The frame may send `fb:resize` (80–800 px) and `fb:state` (up to 2 KB,
  passed to the agent).
- **FR-CON-COMP-05** *Preview* shows what the widget would draw for given props.

### 9.15 Agent access

- **FR-CON-AGT-01** Switch agent access on or off (Admin), see the endpoint URLs, issue tokens
  (name, scopes `leads` and/or `actions`; shown once), revoke tokens, and see agent traffic by
  tool and by assistant.

### 9.16 Settings

- **FR-CON-SET-01 Website:** name, domain, intelligence tier, design level, accent colour.
- **FR-CON-SET-02 Agent profile:**

| Setting | Rule |
|---|---|
| Agent name | 1–40 characters (default "Pragya"). |
| Company | 1–80 characters (default: the website's name). |
| Voice (brand voice) | 1–300 characters. |
| Visitor personas | Up to 8; slug, label (up to 60), focus and tone (up to 200 each), landing page. |
| Start conversations as | One of the personas, or none. |
| Greeting / Greeting in Hindi | Empty means a page-aware welcome. |
| Closing use case for the tour | Up to 800 characters. |
| Pages the agent can open | Routes (normalised), and sections with many pages (dynamic prefixes). |
| Competitors | Up to 30 names. |
| Next step button | Label (up to 60) and https link, for recap pages. |
| Languages | English, plus Hindi. Widget buttons and labels: auto, English or Hindi. |
| Starter questions | Up to 4 (and up to 4 in Hindi), up to 80 characters each. |
| Rules the agent always follows | Up to 10, up to 300 characters each. |
| Preferred components | Up to 8 built-in components. |
| Lead fields | Up to 6 extra details to ask for. |
| Tour outline | Up to 9 points. |
| Currency | ISO 4217 code (default INR). |
| Safety | Normal or medical. |

- **FR-CON-SET-03 Template:** apply a vertical template with a preview of what would change.
  Values the owner edited by hand are kept and listed. Personas are added by slug (existing
  ones unchanged) and triggers by name.
- **FR-CON-SET-04 Privacy & data (Admin to change):** PII masking; microphone consent; privacy
  policy link; keep transcripts for 0 (until deleted), 30, 90 (default), 180 or 365 days; keep
  leads for 0 (until deleted, default), 90, 180, 365 or 730 days; recap links work for 7, 30,
  90 (default), 180 or 365 days; remember returning visitors (off) and for how long.
- **FR-CON-SET-05 Delete a visitor's data (Admin):** by email: their leads, the conversations
  they came from and any memory linked to them.
- **FR-CON-SET-06 Lead integrations (Admin):** webhook URL (https outside development), Slack
  incoming webhook (must start with `https://hooks.slack.com/`), hot-lead score (0–100, default
  60), daily cost alert in USD, signing secret (shown; can be rotated) and a test send.
- **FR-CON-SET-07 Model:** use the account's own model provider for this site, or the
  platform's (Admin).

### 9.17 Live

- **FR-CON-LIVE-01** A live inbox (§6.6) fed by a WebSocket that streams a snapshot then every
  event on the account's sites. Takeover, message, hand back and call controls for Editors.

### 9.18 Weekly digest settings

- **FR-CON-DIG-01** Admins switch the digest on or off, choose up to 20 recipients (default: the
  Owners), set the time zone (default Asia/Kolkata), preview it and send a test to themselves.
  The next send time is shown.

---

## 10. Account, identity and security

### 10.1 Sign-up and sign-in

- **FR-AUTH-01** *Register* with email, password (8–256 characters) and optional name. This
  creates the person, a new account and an Owner membership.
- **FR-AUTH-02** *Sign in* with email and password. Wrong credentials return "Invalid email or
  password." without saying which part was wrong.
- **FR-AUTH-03** With two-factor on, sign-in returns a challenge. The person enters a 6-digit
  code or a recovery code within 5 minutes.
- **FR-AUTH-04** After 10 wrong passwords or codes in a row (`LOGIN_MAX_ATTEMPTS`), the person
  is locked out for 15 minutes (`LOGIN_LOCKOUT_MINUTES`).
- **FR-AUTH-05** If an account requires SSO, passwords from its verified domains are refused,
  except the Owner's (so a broken identity provider cannot lock everyone out).
- **FR-AUTH-06** A person in several accounts can list and switch accounts.

### 10.2 Sessions

- **FR-SES-01** Every sign-in creates a session. A session ends after 60 minutes without a
  request (`SESSION_IDLE_MINUTES`) or 12 hours in total (`SESSION_ABSOLUTE_HOURS`), on sign-out,
  on "sign out everywhere", on a password change, or when the person is removed from the team.
- **FR-SES-02** The console keeps the session in an httpOnly, Secure, SameSite cookie. Requests
  that change something must carry the CSRF token. API clients may use a bearer token instead.
- **FR-SES-03** *Security* page: list where you are signed in, end one session, sign out
  everywhere else, change password (other sessions end; an SSO-only person can set a first
  password).

### 10.3 Two-factor authentication

- **FR-MFA-01** Set up with an authenticator app (QR code). Codes are 6 digits on 30 s steps,
  with one step of clock drift allowed. A used code cannot be reused.
- **FR-MFA-02** Ten one-time recovery codes are shown once when two-factor is switched on. A new
  set can be generated with a valid code.
- **FR-MFA-03** Disabling needs a code (and the password).
- **FR-MFA-04** An Owner can require two-factor for the account, but only after turning it on
  for themselves. People without it are sent to set it up at their next request. SSO sign-ins
  count as two-factor.

### 10.4 Team and invitations

- **FR-TEAM-01** Anyone can see the team. Admins invite people by email with a role. The invite
  is emailed and also shown as a single-use link, valid for 7 days. A new invitation to the same
  address revokes older ones.
- **FR-TEAM-02** Accepting an invitation: an existing person signs in; a new person sets a name
  and password.
- **FR-TEAM-03** Admins change roles and remove members. Only an Owner can make or unmake an
  Owner. The last Owner cannot be removed or demoted.
- **FR-TEAM-04** On a self-hosted install, members and pending invitations beyond the licence's
  seat count are refused.
- **FR-TEAM-05** *Access review* (Admin): a CSV of everyone with access (kind, email, name, role,
  since, last sign-in, last active, password, two-factor, note).

### 10.5 Single sign-on

- **FR-SSO-01** *Sign in with Google* signs in people who already belong to an account (or have
  accepted an invitation). It never creates memberships.
- **FR-SSO-02** An account (Owner) can configure its own OIDC provider: issuer URL, client ID,
  client secret (stored encrypted), default role for new people (admin, editor or viewer),
  "require SSO", enabled.
- **FR-SSO-03** Domains: the account adds an email domain and publishes a DNS TXT record
  `fluidbuddha-verify=<token>`. After verification, people of that domain can sign in through
  the account's provider and join with the default role on first sign-in. Unverified domains are
  refused.
- **FR-SSO-04** The sign-in uses the authorization-code flow with PKCE. The returned ID token's
  signature, issuer, audience, expiry and nonce are checked. A sign-in attempt expires after 10
  minutes.

### 10.6 Audit log

- **FR-AUD-01** Every successful change made through the console API is recorded with who, what
  (the operation), the target, the method and route, the role, IP address, user agent, request
  id and time. Request bodies are never stored.
- **FR-AUD-02** Sign-ins (successful and failed), sign-ups, invitation acceptance and SSO
  sign-ins are recorded too.
- **FR-AUD-03** Admins can search by action and actor, page through, and export CSV. Entries are
  kept one year.

---

## 11. Billing

- **FR-BIL-01** Plans (defaults; prices in INR):

| Plan | Monthly price | Conversations included | Each extra conversation | Self-serve |
|---|---|---|---|---|
| Free | ₹0 | 100 | Not allowed (hard cap) | Yes |
| Growth | ₹33,000 | 2,000 | ₹17 | Yes |
| Scale | ₹1,25,000 | 10,000 | ₹10 | Yes |
| Enterprise | By arrangement | Unlimited | — | No (set by hand) |

- **FR-BIL-02** A conversation is a visitor session with at least one answered turn in the
  period, across all of the account's websites. It is counted from usage records, which
  retention and erasure do not delete.
- **FR-BIL-03** The period is the subscription's billing cycle on paid plans and the calendar
  month (UTC) on Free.
- **FR-BIL-04** The Billing page (Admins see, Owners change) shows the plan, period, usage against
  the allowance, per-website cost and billed overage history.
- **FR-BIL-05** *Choose a plan* creates a Razorpay subscription and opens Razorpay Checkout. The
  payment signature is verified on the server before the plan changes.
- **FR-BIL-06** Upgrades apply now. Downgrades apply at the end of the cycle. Cancelling keeps
  the plan until the end of the paid period.
- **FR-BIL-07** The account is on its paid plan while the subscription is authenticated, active
  or pending (a renewal being retried). Halted, cancelled, completed or expired subscriptions
  fall back to Free limits.
- **FR-BIL-08** Overage: when a new cycle is charged, the previous cycle's extra conversations
  are added to the subscription as an add-on, billed on the next invoice and listed in the
  console. Each period is billed once.
- **FR-BIL-09** UPI Autopay subscriptions cannot take add-ons or plan changes. Their overage is
  sent as a Razorpay Payment Link (emailed, with a *Pay now* button in the console). A plan
  change becomes a new subscription that starts at renewal, whose mandate the customer approves
  now (Razorpay takes a refundable ₹5). Once approved, the current subscription is cancelled at
  cycle end without dropping the account to Free. Cancelling withdraws a scheduled switch.
- **FR-BIL-10** Overage that could not be billed stays pending and is retried on the next
  subscription event.
- **FR-BIL-11** Razorpay webhooks are verified and each event is applied once. Without webhooks,
  the Billing page asks Razorpay directly about subscriptions awaiting payment and unpaid links.
- **FR-BIL-12** Without Razorpay keys, the plans are shown but checkout is off.

---

## 12. Self-hosted edition and licence

- **FR-SH-01** The whole product runs on one Linux host with Docker Compose: Caddy (TLS and
  routing), backend, console, the widget's files, Postgres with pgvector, Redis and an optional
  TURN relay. `install.sh` writes secrets, builds, starts and waits for health (about 20
  minutes). The first account created is the Owner.
- **FR-SH-02** Scripts cover backup (base backup plus WAL archive for point-in-time recovery,
  and a logical dump), restore, upgrade (migrations run themselves), and image export/import for
  air-gapped hosts.
- **FR-LIC-01** The licence is a signed text key checked offline. It names the customer, website
  count, seat count (install-wide, pending invitations included), features, expiry and grace
  period (default 14 days).
- **FR-LIC-02** Licence states: valid; expiring (30 days or fewer left, banner shown); grace
  (expired but inside the grace period, everything works with a banner); expired, missing or
  invalid (the console is read-only).
- **FR-LIC-03** When read-only, console changes return 402 with "This install's FluidBuddha
  licence has expired, so the console is read-only. Visitors aren't affected…". Installing a
  licence is always allowed.
- **FR-LIC-04** Features not in the licence (`byo_model`, `agent_access`, `campaigns`, `sso`,
  `voice_handoff`) are refused with 402.
- **FR-LIC-05** Visitors are never affected: the widget, hosted pages and the agent endpoint
  keep answering.
- **FR-LIC-06** An Owner installs a licence in Account → Licence, or the administrator sets
  `LICENCE_KEY` or `LICENCE_FILE`. One installed in the console wins.
- **FR-LIC-07** On the hosted service no licence is enforced.

### 12.1 Bring your own model

- **FR-BYO-01** Owners and Admins can set the account's own provider: Anthropic, OpenAI or Azure
  OpenAI, with a fast model (routing, quick answers, labelling) and a thinking model (grounded
  answers with tools), the API key (stored encrypted, never shown again), and for Azure the
  endpoint and API version (models are deployment names). Optional own prices per 1M tokens.
- **FR-BYO-02** Defaults: Anthropic `claude-haiku-5-5` (fast) and `claude-opus-5-5` (thinking);
  OpenAI `gpt-4.1-mini` and `gpt-4.1`; Azure needs deployment names.
- **FR-BYO-03** *Test connection* makes a one-line call with each model.
- **FR-BYO-04** Each website uses the account's provider unless switched back to the platform's.
- **FR-BYO-05** If the provider fails, the call falls back to the platform's model so the
  visitor still gets an answer, and the error is shown in the console.
- **FR-BYO-06** Speech and embeddings stay on the platform.
- **FR-BYO-07** Model cost is priced at the account's prices (or the provider's list price where
  known), shown separately in Analytics and excluded from the daily spend cap.

---

## 13. Background processes and notifications

| Process | Interval (default) | What it does |
|---|---|---|
| Retention sweep | 60 min (`RETENTION_SWEEP_MINUTES`) | Deletes transcripts, automatic cached answers, leads, recaps and knowledge-tree episodes past each site's window. |
| Email outbox | 15 s | Sends queued email with retries. |
| Outbox clean-up | periodic | Deletes sent and failed email after 30 days. |
| Audit retention | periodic | Deletes audit entries older than 1 year. |
| Live sweep | periodic | Clears visitors no longer live. |
| Insights classification | 20 s | Labels the last week's unlabelled visitor questions. |
| Weekly digest | 10 min check | Sends each account's digest on Monday at 09:00 local time. |
| Action payments | 5 min | Checks unpaid payment links with Razorpay. |
| Access review | 6 h check | Sends each account's quarterly access review once. |
| Session clean-up | periodic | Deletes sessions ended more than 30 days ago. |
| Visitor memory | 2 min | Rebuilds memories of visitors whose conversation went quiet. |
| Status probe | 60 s | Samples components for the status page. |

- **FR-JOB-01** Only one server replica runs a given job at a time.
- **FR-MAIL-01** Emails sent by the product: team invitations, recap links, quote requests to
  site owners, weekly digests, quarterly access reviews and feature-request forwards.
- **FR-MAIL-02** Emails are branded plain HTML with a text version, with no images or tracking
  pixels.
- **FR-MAIL-03** A failed send is retried with backoff (1 to 32 minutes, 6 attempts). Without an
  SMTP server, development logs emails instead, and production refuses to queue them.
- **FR-DIG-01** The weekly digest covers the last seven days across the account's websites:
  conversations, leads, top questions, new knowledge gaps, objections, competitor mentions, A/B
  results and model cost. A week with no conversations and no leads sends nothing. A missed
  Monday is skipped, not sent late.
- **FR-ACR-01** The quarterly access review email lists who can get in and with what role, who
  has not signed in for 90 days, who has no two-factor, and pending invitations, with a link to
  the Team page.
- **FR-ALERT-01** Cost alerts: when the site's own daily threshold is passed, or 80 % or 100 % of
  the daily spend cap is reached. Each kind goes out at most once per site per UTC day, to the
  site's Slack webhook and the Analytics tab.

---

## 14. Permissions matrix

Reads need Viewer and changes need Editor, unless the table says otherwise.

| Area | Viewer | Editor | Admin | Owner |
|---|:-:|:-:|:-:|:-:|
| See websites, knowledge, insights, analytics, leads, tests, campaigns, triggers | ✅ | ✅ | ✅ | ✅ |
| Change knowledge, tours, profile, answers, experiments, triggers, campaigns, leads | — | ✅ | ✅ | ✅ |
| Live takeover, messages, calls | — | ✅ | ✅ | ✅ |
| See the team | ✅ | ✅ | ✅ | ✅ |
| Invite, change roles, remove (not Owners) | — | — | ✅ | ✅ |
| Grant or remove Owner | — | — | — | ✅ |
| Access review CSV, audit log | — | — | ✅ | ✅ |
| Integrations (webhook, Slack, secrets) — even to read | — | — | ✅ | ✅ |
| Change privacy settings, erase a visitor | — | — | ✅ | ✅ |
| Delete a website, rotate its widget key | — | — | ✅ | ✅ |
| Change actions; read action secrets | — | — | ✅ | ✅ |
| See actions and runs | ✅ | ✅ | ✅ | ✅ |
| Model provider (even to read); per-site model switch | — | — | ✅ | ✅ |
| Agent access switch and tokens | — | — | ✅ | ✅ |
| Weekly digest settings | — | — | ✅ | ✅ |
| See billing | — | — | ✅ | ✅ |
| Pay, change or cancel a plan | — | — | — | ✅ |
| See SSO and security settings | — | — | ✅ | ✅ |
| Change SSO, require two-factor | — | — | — | ✅ |
| Install a licence (self-hosted) | — | — | — | ✅ |
| See licence state | ✅ | ✅ | ✅ | ✅ |

---

## 15. Limits and defaults (reference)

| Item | Value |
|---|---|
| Public turns per site per minute | 120 |
| Daily spend cap per site | off (0) |
| Text session idle timeout | 30 min |
| In-memory text sessions kept | 10,000 |
| Conversation history kept by the agent | 12 turns |
| Components remembered | 8 |
| Utterance length | 60 s |
| Utterance merge window | 10 s |
| Retrieval top-k / confidence threshold | 5 / 0.45 |
| Replay / context thresholds / minimum turns | 0.92 / 0.70 / 20 |
| Filler tone delay | 1,500 ms |
| Heavy thinker rounds / searches | 4 / 1 |
| Component list items | 48 |
| Generated page sections / campaign sections | 12 / 10 |
| Upload size | 10 MB |
| URL fetch size / timeout / redirects | 2 MB / 15 s / 3 |
| Crawl pages / depth (default; cap) | 25; 50 / 2; 3 |
| Personas per site / derived | 8 / 6 |
| Trigger rules per site | 20 |
| Lead form rate / recap rate / action confirm rate / agent endpoint rate | 20 / 30 / 30 / 30 per minute |
| Campaign compositions / campaign leads | 20 / 10 per minute per site |
| Action proposals per conversation | 10 per hour |
| Action confirmation window | 15 min |
| Invitation validity | 7 days |
| Login lockout | 10 attempts → 15 min |
| Session idle / absolute | 60 min / 12 h |
| MFA challenge validity | 5 min |
| SSO attempt validity | 10 min |
| Audit retention | 365 days |
| Email retries | 6 attempts, 1–32 min |
| Digest recipients | 20 |
| Live window / heartbeat | 120 s / 30 s |
| TURN credential lifetime | 1 h |
| Licence expiring warning / default grace | 30 days / 14 days |
| Drain time on shutdown | 25 s |

---

## 16. Non-functional requirements

| Area | Requirement (as implemented or targeted) |
|---|---|
| **Responsiveness** | The acknowledgement is spoken while the answer is prepared. Target p95 time to first audio below 1.5 s and whole turn below 8 s (service-level objectives). |
| **Availability** | Target 99.9 % of requests without a server error over 30 days, and 99.9 % of minutes with the API component up. |
| **Graceful degradation** | Model failures fall back (router default ack, thinker fallback answer, BYO to platform model). Cache, analytics and recording failures never break a turn. Voice falls back to text. |
| **Zero-downtime deploys** | Replicas drain voice sessions on shutdown; widgets reconnect to healthy replicas. |
| **Scalability** | Stateless HTTP; shared sessions, rate limits and live events in Redis for several replicas; jobs coordinated by database locks. |
| **Security** | Tenant isolation on every console route; server-side site and tier resolution from the widget key; origin checks; SSRF-safe outbound requests; encrypted secrets; security headers; CSRF protection. |
| **Privacy** | PII masked before models and storage; no visitor audio stored; consent before listening; retention and erasure; telemetry never carries what visitors said. |
| **Accessibility** | Keyboard focus rings, ARIA labels, reduced-motion and high-contrast support, safe-area insets, a focus-trapped consent dialog. |
| **Isolation on host sites** | The widget lives in a Shadow DOM and does not affect the host page's styles or scripts. |
| **Performance budget** | The core widget bundle stays small (Three.js only for Level 2; Hindi strings and component renderers load on demand). |
| **Localisation** | English and Hindi in the widget, the agent and speech. |
| **Observability** | Request ids on every response and log line; Prometheus metrics; optional tracing and error reporting. |

---

## 17. Out of scope and known limitations

- Languages other than English and Hindi.
- Detection of names and street addresses as PII.
- OCR for scanned PDFs.
- Model providers other than Vertex AI (platform), Anthropic, OpenAI and Azure OpenAI; voice
  and embeddings on a customer's own provider.
- Native CRM connectors (delivery is by signed webhook, so Zapier, Make or a CRM's webhook
  intake is used instead).
- Retries for action executions (by design, so a trial is never created twice).
- Full DNS-rebinding protection for fetched URLs (residual risk noted in the code).
- Voice capacity beyond what the recorded load tests show for one replica (p95 time to first
  audio 1.62 s at 50 concurrent sessions, 5.93 s at 100).
