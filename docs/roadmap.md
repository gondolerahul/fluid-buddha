# FluidBuddha — Product & Go-to-Market Roadmap

> Written from two seats at once: the **visionary founder**, who asks what this becomes, and
> the **expert marketer**, who asks who pays for it, why now, and how they find out.
> Every recommendation is anchored in the current code. See
> [functionality-report.md](./functionality-report.md) for the evidence and the
> `file:line` references.
> Prepared 2026-11-03.

---

## 0. The one-paragraph thesis

Websites are about to stop being documents and become **conversations**. FluidBuddha
already has something most "AI chat widget" companies don't:

- an agent that **talks, shows, and acts on the page at the same time**: voice, generated
  diagrams and calculators, scrolling and spotlighting, and silent personalisation;
- an economics engine that **replays answers for near-zero cost**.

What it lacks is everything that turns a stunning demo into a business:

- tenant-aware intelligence;
- a locked-down public surface;
- a five-minute self-serve setup;
- a direct line from conversation to **pipeline**.

The next level is not a smarter model. It is **becoming the system that turns website
traffic into qualified, booked revenue, and proving it on a dashboard a CMO will screenshot.**

---

## 1. Where we stand (honest diagnosis)

### Strengths to build the moat on
| Asset | Why it matters commercially |
|---|---|
| **Voice and UI sync engine**: jitter buffer, sync IDs, sentence-chunked TTS, ack overlap, barge-in gating | The hard 20 % that competitors skip. It makes the agent feel *present*, not like a bot |
| **Generative UI library**: 13 typed, safe components including configurators and simulators, plus live reactions | "She doesn't just answer, she *shows*." This is the visual hook in every demo video |
| **Acts on the host page**: navigate, scroll, spotlight (L3), persona cross-fade | Chat widgets sit in a corner. This one drives the site. The category-defining behaviour |
| **Episodic replay + audio cache** | A real cost moat. Repeated questions cost about $0, which is the margin story for investors |
| **Grounding guardrail** | Brand safety is the #1 objection from enterprise buyers |
| **Pre-planned narrated tours** | Turns any landing page into an interactive product demo |
| **Distinctive brand craft** (Aura, molten-obsidian, 3 design levels) | Premium perception and shareability ("what *is* that?") |

### Gaps blocking revenue
| Gap | Consequence |
|---|---|
| The brain is HireBuddha-specific (prompts, personas, tour copy). Navigation works only on hirebuddha | Every new customer gets someone else's agent. **Unshippable to customer #2** |
| Public endpoints are open: any site or tier can be chosen by the client, there are no rate limits, and there are TTS-relay and SSRF holes | One abusive visitor or one competitor can run up the Vertex bill or read a tenant's knowledge base |
| No lead capture, CRM, booking or human handoff | No way to prove ROI, so no renewals |
| No install snippet or website settings in the console; admin settings don't reach the widget | The self-serve funnel breaks at the activation step |
| Marketing claims run ahead of the code (CRM sync, "0 % hallucination", 2.4×, 74 %, 80 %, house-brand testimonials) | Credibility and legal risk the first time a sophisticated buyer asks for proof |
| Pricing is underwater (see §5) | The more a customer uses it, the more money is lost |

---

## 2. Positioning reset

### 2.1 Pick a beachhead, not "every website"
**Primary ICP: B2B SaaS, Series A–C, $15k–$150k ACV, with a complex or technical product
and a small sales team.**

- Their bottleneck is the *demo*. High-intent visitors land on pricing, integrations and
  security pages, have nuanced questions, and won't book a call to get them answered.
- FluidBuddha's exact strengths map onto that bottleneck: integration flowcharts, ROI
  configurators, security grounding, guided product tours, and enterprise-vs-startup
  persona switching.
- Value is **measurable in pipeline dollars**, which justifies premium pricing.

**Secondary ICPs (later):** high-consideration B2C (university admissions, real estate,
premium travel), agencies reselling to their clients, and developer-docs portals (L3
Atmosphere is ideal there).

### 2.2 Category and message
- **Category to own:** *"The Agentic Website"*. It is not a chatbot, not an interactive-demo
  tool, and not a voice bot. It is the website itself becoming an agent.
- **Positioning statement:** *For B2B SaaS teams whose buyers want answers before they'll
  talk to sales, FluidBuddha turns your website into a live solutions engineer: it talks,
  shows, and personalises the page in real time, grounded only in your content, and hands
  you qualified, booked pipeline.*
- **Headline candidates** (test these):
  1. "Your website just learned to give the demo."
  2. "Stop making buyers book a call to get an answer."
  3. "The website that talks, shows, and sells."
- **Proof pillars:** *Shows, not tells* (generative UI) · *Acts on your site* (navigate,
  spotlight, personalise) · *Never makes things up* (grounded with citations) · *Gets
  cheaper as it learns* (replay cache).

### 2.3 Naming and brand hygiene
- **This is a voice product, so its name must survive being said out loud.** "flUIdBuddha"
  fails that test. Standardise on **Fluid Buddha** (or a shorter platform name) and keep
  **Pragya** as the default agent persona, renamable per tenant.
  *Decided 2026-11-04: the written brand is **FluidBuddha** (one word), matching the
  `FluidBuddha` JavaScript API; technical names such as the `<fluid-buddha>` tag stay.*
- One spelling everywhere (code, docs, console, site), and one default accent (the SDK uses
  `#c9a24a` but the console uses `#ffd23f`).
- **Review the "Buddha" name before expanding globally.** Some markets consider religious
  names in commercial branding sensitive. This is a strategic call, not urgent, but worth a
  conscious decision before spending on brand.

### 2.4 Claims policy (do this now)
Remove or rewrite every number that is not measured by our own instrumentation: 2.4×, 74 %,
80 %, 48 %, "0 % across 15,000 queries", "< 300 ms", "$4,200 saved". Replace sister-company
testimonials with **design-partner** results gathered through the A/B holdout in §4 Phase 1.
Change "zero hallucinations guaranteed" to **"grounded answers with sources, and it says so
when it doesn't know."** That is defensible, and it is what the guardrail actually does.

---

## 3. Strategic bets (the "next level")

Ranked by impact on revenue and defensibility.

### Bet 1: From answers to outcomes ("the revenue layer")
The agent must *convert*, not just converse.
- **Lead capture in conversation.** Pragya asks for an email at the moment of highest
  value ("Want me to send you this ROI model?"). This is native, not a form.
- **Qualification** using configurable frameworks (BANT / MEDDICC-lite). Scores are stored
  per conversation.
- **Meeting booking**: Calendly, HubSpot Meetings, Chili Piper, Google Calendar, inline.
- **CRM sync**: HubSpot, Salesforce, Pipedrive. A contact plus a conversation summary,
  persona, pages viewed, components explored, and a lead score.
- **Human handoff**: alert Slack or Teams when a hot lead is live ("Enterprise visitor
  asking about SSO on /pricing"), then **live takeover** by text, and later by voice.
- **Attribution**: conversation → lead → meeting → opportunity → closed-won, via CRM
  write-back.

*Builds on:* the existing `enquiry_form` and `call_site_api` paths (replace the simulated
call with real connectors), `set_persona`, and `usage_events`.

### Bet 2: Live in five minutes (the self-serve magic moment)
**Target: under 15 minutes from sign-up to "Pragya speaking on my own homepage".**
1. Paste your URL.
2. Crawl the sitemap. This is a *real* crawler with robots.txt, depth limits and an SSRF
   guard.
3. Auto-ingest the content, auto-derive the **sitemap** (fixes navigation for tenants),
   auto-derive **section anchors**, auto-extract **design tokens** from the site's CSS,
   auto-propose **personas** from the content, and auto-plan the **tour**.
4. Preview on your own site through a bookmarklet, a browser extension, or a hosted proxy
   preview.
5. Copy one snippet, which carries a public widget key.

This flow is also the **#1 sales and marketing asset**: "Enter your URL, hear your
website talk."

### Bet 3: Trust layer (wins enterprise)
- **Visible citations** on every answer. The data is already in `grounding.sources`; we
  just need to show it.
- **Answer governance**: an approval queue for cached answers, pinned "golden answers",
  blocked topics, competitor-mention policy, and per-topic escalation.
- **Compliance**:
  - recording and microphone consent UX;
  - two-party-consent and GDPR notices;
  - PII redaction before storage and before the LLM;
  - configurable data retention, data residency (EU/US) and a DPA;
  - a SOC 2 Type I → II track.
- **Security**: widget keys and origin allow-lists, server-enforced tiers, rate limits and
  spend caps, and audit logs.

### Bet 4: "Voice of the Visitor" insights (makes it sticky for marketers)
Even when only 5–15 % of visitors talk, *what they say* is gold:
- the **top questions** asked, by page and persona;
- **knowledge gaps**: low-confidence or unanswered questions, with one-click "add a
  source". The guardrail already marks these as `found=false`;
- **objection mining** (price, security, integrations), **competitor mentions**, and
  **feature requests** routed to the product team;
- funnel views: visitors → engaged → leads → meetings, by design level and intelligence
  tier;
- a **weekly digest email** to the CMO and Head of Sales. This is a retention engine and a
  word-of-mouth engine.

### Bet 5: Self-optimising agent
- A/B test greetings, tours, personas, design levels and proactive triggers against
  conversion.
- A **holdout group** (no agent) for causal lift. This produces the *defensible* ROI
  numbers marketing needs.
- Later: bandit optimisation of openers and the timing of the lead ask.

### Bet 6: Platform and distribution
- **Install surfaces**: WordPress, Webflow, Framer, Shopify, Wix plugins; React and Vue
  wrappers; Google Tag Manager template.
- **Custom component SDK**: tenants register their own safe renderers (for example a
  product configurator).
- **Actions marketplace**: Stripe checkout, booking, quote generation, trial provisioning,
  webhooks, Zapier and Make.
- **Integration marketplace listings**: HubSpot App Marketplace, Salesforce AppExchange,
  Webflow Apps. These are distribution channels as much as features.

### Bet 7: The visionary horizon
- **Every visitor gets their own website.** Graduate the Extreme tier into *Generative
  Landing Pages*: an ad click or email link produces a page composed for that account,
  persona and question, grounded in the brand design system, with the agent present.
- **Shareable recap pages.** After a conversation, the visitor gets a personalised
  "here's what we covered" page (their ROI model, the diagrams, next steps). It captures
  an email, gets forwarded internally to the buying committee, and **spreads the product
  inside target accounts**.
- **Memory for returning visitors**, with consent: "Welcome back. Last time we looked at
  SSO. Want to pick up there?"
- **Proactive presence** on intent signals: pricing-page dwell, exit intent, a return
  visit, or a reverse-IP match to a target account.
- **The website as an agent endpoint.** AI assistants will increasingly browse and buy on
  behalf of humans. Expose the same grounded knowledge and actions over an **MCP / agent
  API**, so FluidBuddha serves *both* human visitors and the AI agents researching for
  them. Being "agent-ready" is a story enterprise buyers will pay for.
- **Omnichannel brain**: the same tenant knowledge and persona on phone (Twilio),
  WhatsApp, and email follow-up.
- **Keep the Aura as the signature.** Resist photoreal avatars as the default, because
  they invite uncanny-valley comparisons with video-avatar vendors. The abstract light
  presence is ownable, fast, and brand-safe. An avatar can be an Enterprise add-on.

---

## 4. Phased roadmap

### Phase 0: "Shippable to customer #2" (weeks 0–4)
*Goal: a second, unrelated company can go live safely. No new features until this is done.*

**De-HireBuddha the brain (multi-tenant intelligence)**
- [ ] Per-site agent profile, editable in the console: agent name and voice, company name,
      brand voice, personas (label, focus, tone, landing route), and the closing use-case
      template. Replace hard-coded prompt text ([prompts.py:9](../backend/app/orchestrator/prompts.py)),
      `VALID_PERSONAS` ([personas.py:10](../backend/app/orchestrator/personas.py)), and the
      tour copy ([tour.py:93](../backend/app/orchestrator/tour.py)).
- [ ] Per-site sitemap auto-derived at ingestion, plus a console editor. Navigation
      currently fails for every non-HireBuddha site ([sitemap.py:52](../backend/app/orchestrator/sitemap.py)).
- [ ] Store a route for tenant sources (the URL path for crawled pages) so tour catalogues
      aren't collapsed to "/".

**Lock down the public surface**
- [ ] **Public widget key** per website. `/ws/voice` and `/chat` resolve the site from the
      key, check `Origin` against the website's `domain` allow-list, and **enforce the
      tenant's configured intelligence and design tiers server-side**.
- [ ] Rate limits per IP, session and site. A daily **spend cap** per site, with alerts.
- [ ] `tour_say` may speak only narration that exists in the stored plan, matched by index
      and hash.
- [ ] SSRF guard for URL sources: block private and link-local ranges, limit redirects,
      add size and time caps. URL-encode `call_site_api` path params.
- [ ] Require `JWT_SECRET` in non-local environments. Remove the real GCP project ID from
      `.env.example`. Use explicit CORS origins. Plan an httpOnly-cookie session for the
      console.

**Data lifecycle correctness**
- [ ] Deleting a source removes its CORTEX nodes. Deleting a website purges its tree,
      cache, tour, audio and usage data, or archives them on a retention schedule.
- [ ] Invalidate or re-validate cached answers when knowledge changes (version stamp per
      ingestion). Filter replay by `page` for page-specific questions.
- [ ] Re-ingestion must **not** overwrite a manually edited tour. Re-plan from the full
      corpus only on request.

**Activation basics in the console**
- [ ] **Install tab**: a copy-paste snippet pre-filled with the widget key and settings,
      plus a "test connection" check.
- [ ] Website settings: edit, delete, accent, design (**add Level 3**), and agent profile.
- [ ] Fix port and URL drift: console on 3001, backend on 8080, consistent SDK demos and
      env examples. Fix compose content mount paths.

**Production plumbing**
- [ ] Redis for session state, eviction, and horizontal scaling.
- [ ] Alembic migrations, replacing per-request `CREATE TABLE IF NOT EXISTS`.
- [ ] Observability: OpenTelemetry traces per turn (router, thinker, TTS spans), Sentry, a
      **time-to-first-audio** metric, and per-tenant cost alerts.
- [ ] CI: backend tests against an ephemeral pgvector, SDK typecheck and smoke tests,
      console lint and build.

**Marketing hygiene**
- [ ] Apply the claims policy (§2.4). Unify the product name. Commit or restore
      `docs/website-copies`.

**Exit criteria:** an outside company installs from the console snippet. Their agent uses
their name, personas, sitemap and tour. A red-team pass cannot read another tenant's
knowledge, raise its own tier, or run up spend.

---

### Phase 1: "Paid beta that proves ROI" (months 1–3)
*Goal: 5–10 design partners paying, with measured pipeline impact.*

**Revenue layer (Bet 1 MVP)**
- [ ] Conversational lead capture, plus a `Lead` object (contact, score, persona, summary,
      transcript link).
- [ ] Booking: Calendly and HubSpot Meetings, inline in the panel.
- [ ] HubSpot CRM sync (first), then Salesforce. Generic webhooks and Zapier.
- [ ] Slack hot-lead alerts, and text live-takeover from the console.
- [ ] Replace the simulated `enquiry_form` → LLM path with a direct, validated, PII-safe
      submission ([FluidBuddhaElement.ts:154](../fluid-buddha-sdk/src/ui/FluidBuddhaElement.ts)).

**Trust (Bet 3 MVP)**
- [ ] Show citations in every design level (data already present in `grounding`).
- [ ] Microphone and recording consent UX. PII redaction before storage. Retention
      settings.
- [ ] A "golden answers" approval toggle on cached responses.

**Self-serve onboarding (Bet 2 MVP)**
- [ ] Sitemap crawler, plus PDF and DOCX extraction.
- [ ] Auto-derived personas and anchors, with design-token extraction from site CSS.
- [ ] A hosted "preview on your site" link (bookmarklet).

**Insights v1 (Bet 4)**
- [ ] Conversation transcript viewer.
- [ ] Top questions, unanswered and low-confidence questions, and gap → "add source".
- [ ] Funnel: visitors → engaged → leads → meetings.

**Experience quality**
- [ ] **Text-first default with voice as a delight.** Most visitors won't speak in an
      office. Measure the engaged-voice rate and tune the defaults.
- [ ] Query rewriting with conversation history before retrieval (fixes follow-ups).
- [ ] AudioWorklet capture with a pre-roll buffer, so the first ~180 ms isn't lost
      ([Session.ts:243](../fluid-buddha-sdk/src/core/Session.ts)). Binary WebSocket audio
      frames. True streaming TTS.
- [ ] Wire the `DATA/patch` path end to end (currently a no-op). Make the ROI calculator
      configurable (rate, seats) and have it report state.
- [ ] Lazy-load Three.js only for Level 2. Ship the real ~35 kB L1/L3 bundle the docs
      promise.
- [ ] Multilingual v1: language auto-detect, multilingual TTS voices, and a per-site
      default.

**Business**
- [ ] Stripe billing with the new pricing (§5). Usage metering is already in
      `usage_events`, so add plan caps and overage.
- [ ] An A/B **holdout** (agent off for 10 % of traffic) for causal lift. It feeds the
      first honest case studies.

**Exit criteria:** at least 5 paying design partners, at least 1 with a statistically
supported lift in demo bookings or leads versus the holdout, and time-to-live under 15
minutes for a new site.

---

### Phase 2: "Repeatable growth" (months 3–6)
- **Insights v2**: objection and competitor mining, feature-request routing, and the
  weekly CMO digest.
- **Experimentation**: A/B test greetings, tours, personas, design levels and triggers.
  Optimise for conversion.
- **Proactive engagement**: triggers on pricing dwell, exit intent and return visits.
  Optional reverse-IP firmographics for account-based personalisation.
- **Shareable recap pages**: personalised summaries with captured email, built to be
  forwarded inside the buying committee.
- **Install everywhere**: WordPress, Webflow, Framer and Shopify plugins; a GTM template;
  React and Vue wrappers.
- **Custom component SDK** and an actions marketplace (Stripe, quotes, trial
  provisioning).
- **Team features**: multiple users per tenant, RBAC, SSO (Google and Okta), audit log.
- **Vertical templates**: SaaS, admissions, real estate. Pre-built personas, tours and
  components.
- **Voice handoff**: escalate a live voice conversation to a human (WebRTC).
- **Compliance**: SOC 2 Type I, EU data residency, DPA.

### Phase 3: "Platform and vision" (months 6–12)
- **Generative Landing Pages**: Extreme tier GA, with per-campaign and per-account pages
  composed at runtime.
- **Agent endpoint**: an MCP / agent API so AI assistants can query the grounded
  knowledge and perform actions on the site.
- **Returning-visitor memory** (opt-in), using the CORTEX episodic tree that is already
  being populated.
- **Omnichannel**: phone (Twilio), WhatsApp, and email follow-up from the same brain.
- **Enterprise**: VPC or on-prem deployment, bring-your-own-model and keys (OpenAI and
  Anthropic alongside Vertex; the engine interfaces in `app/ai/base.py` already make this
  clean), SOC 2 Type II, and a 99.9 % SLA.
- **Partner programme**: agencies resell and white-label FluidBuddha.

---

## 5. Pricing and unit economics

### 5.1 The current pricing loses money
Using the backend's own default rate card ([pricing.py](../backend/app/analytics/pricing.py))
and typical turn sizes:

| Per voice turn (estimate) | Lean path | Heavy path |
|---|---|---|
| TTS (~60-character ack + ~350-character answer) | $0.0066 | $0.0066 |
| Fast LLM (router plus lean answer) | ~$0.0004 | ~$0.0002 |
| Thinker LLM (2–3 calls × ~4k tokens in) | — | ~$0.003–0.005 |
| Tools | — | ~$0.0004 |
| ASR (server) | $0–0.002 | $0–0.002 |
| **Total** | **≈ $0.008** | **≈ $0.011–0.014** |

The estimate assumes a conversation of about 8 turns plus a welcome, which comes to
**≈ $0.07–0.12** before cache savings. **TTS is 50–80 % of the cost.** The audio cache is
therefore the biggest margin lever, and the cost of voice should be visible to buyers.

Measured against the published plans:

| Plan (website copy) | Price | Included | Est. model cost at full use | Gross margin |
|---|---|---|---|---|
| Starter | $49 | 5,000 chats | ≈ $350–600 | **deeply negative** |
| Studio | $199 | 25,000 chats | ≈ $1,750–3,000 | **deeply negative** |
| Enterprise | $999 | unlimited | unbounded | **unbounded loss** |

Even with a strong cache hit rate, these plans don't recover. They also price a premium
product below cheap text chatbots.

### 5.2 Recommended model: platform fee plus conversation allowance, with value-based upside
| Plan | Price | For | Includes |
|---|---|---|---|
| **Free** | $0 | Try it, viral loop | 50 conversations/month, text plus voice, L1, "Powered by FluidBuddha" badge |
| **Growth** | $399/month | Startups to Series A | 1,000 conversations, all design levels, advance tier, lead capture, booking, HubSpot, insights v1. Overage $0.35/conversation |
| **Scale** | $1,499/month | Series B–C SaaS | 5,000 conversations, A/B and holdout, Salesforce, Slack takeover, custom components, SSO. Overage $0.25 |
| **Enterprise** | from $40k/year | Regulated or large | Extreme tier and generative pages, VPC/BYO-model, residency, SOC 2 pack, SLA, success manager |

- Target **≥ 75 % gross margin** at plan allowances. Watch cost per conversation on the
  analytics page you already have.
- **Outcome-based pilot option:** "$X per booked meeting" for design partners. This
  removes adoption risk and is a powerful sales opener.
- Count **conversations, not turns or messages**. Buyers understand that unit.
- Price voice as included but metered, because TTS dominates cost.

---

## 6. Go-to-market plan

### 6.1 Motion
1. **Founder-led design partners (months 0–3).** 10 hand-picked SaaS companies. Offer free
   setup in exchange for a holdout test and a case study.
2. **"Hear your website talk" outbound.** For each target account, auto-build a preview
   of Pragya on *their* site from Bet 2's crawler, and send a 30-second screen recording or
   preview link. Showing a prospect their own site talking is the strongest outbound hook
   available to us.
3. **Product-led loop.** The free tier carries a "Talk to this website — powered by Fluid
   Buddha" badge, which links to the URL-preview funnel.
4. **Launch moments.** A Product Hunt and Hacker News "Show HN" launch with an L3
   Atmosphere demo, a short video of the agent navigating, spotlighting and building an
   ROI model live, and a *"The Agentic Website" manifesto*.
5. **Partners.** Webflow and Framer agencies (revenue share), and HubSpot solutions
   partners. Marketplace listings.
6. **Content engine.** Monthly "Voice of the Visitor" benchmark reports using aggregated,
   anonymised data on what B2B buyers actually ask before they buy. This builds authority
   and a stream of inbound leads.

### 6.2 Competitive framing (categories, not feature claims)
| Category (examples) | What they do | Our wedge |
|---|---|---|
| AI support and chat agents (Intercom Fin, Drift-style widgets) | Text answers in a corner box | Voice plus generative visuals, and **acts on the page** |
| AI SDR agents (e.g. Qualified-style) | Qualification and booking | Shows the product (diagrams, ROI, tours) while qualifying |
| Interactive demo tools (Navattic, Storylane, Arcade) | Pre-recorded click-through demos | Live, conversational, and personalised to the question asked |
| Voice-agent platforms (ElevenLabs, Vapi, Retell) | Voice infrastructure for builders | A finished product: one script tag, grounded, page-aware |
| Website personalisation (Mutiny-style) | Rules-based copy swaps | Persona inferred from conversation, plus runtime-generated pages |

**Message:** "Everyone else gives you a chatbot *about* your website. We make your website
the agent."

### 6.3 Launch sequencing
| When | Milestone | Marketing beat |
|---|---|---|
| Month 1 | Phase 0 done | Private beta; claims-clean website relaunch |
| Month 3 | Phase 1 done, first holdout result | First real case study; Product Hunt and Show HN |
| Month 6 | Insights, A/B, plugins | "Voice of the Visitor" report #1; marketplace listings; agency programme |
| Month 9–12 | Generative pages, agent endpoint | Category keynote: "The Agentic Website is here" |

---

## 7. Metrics that matter

**North Star:** *Qualified pipeline generated per active site per month (USD)*.

| Funnel stage | Metric | Phase-1 target |
|---|---|---|
| Activation | Sign-up → agent live on site | < 15 min median, > 60 % of sign-ups |
| Engagement | % of visitors who interact (text or voice) | 5–12 % |
| Voice adoption | % of engaged sessions using the mic | Track and learn. Don't assume |
| Conversion | Engaged session → lead | ≥ 15 % |
| Revenue | Lead → booked meeting | ≥ 25 % |
| Quality | Grounded-answer rate / unanswered rate | ≥ 90 % / ≤ 5 % |
| Speed | p95 time-to-first-audio (ack) / to answer | ≤ 1.2 s / ≤ 3.5 s |
| Economics | Cost per conversation / gross margin | ≤ $0.08 / ≥ 75 % |
| Retention | Logo retention at 90 days / NRR | ≥ 85 % / ≥ 110 % |

Most of the instrumentation exists already (`usage_events`, grounding confidence, cache
hit rate). Add a **conversation**-level table, the lead and meeting events, and
time-to-first-audio.

---

## 8. Prioritisation snapshot

| Initiative | Impact | Effort | Phase |
|---|:-:|:-:|:-:|
| Tenant-aware brain (profile, personas, sitemap) | 🔴 critical | M | 0 |
| Widget key, origin check, server-side tier, rate and spend limits | 🔴 critical | M | 0 |
| Data lifecycle fixes (delete, invalidation, tour overwrite) | 🔴 critical | S | 0 |
| Install snippet and website settings in console | 🔴 critical | S | 0 |
| Lead capture, booking, HubSpot | ⭐ very high | M | 1 |
| Citations, consent, PII redaction | ⭐ very high | S–M | 1 |
| Crawler, PDF, auto-onboarding, preview link | ⭐ very high | M–L | 1 |
| Insights v1 (gaps, top questions, funnel) | ⭐ very high | M | 1 |
| Pricing and billing rework | ⭐ very high | S–M | 1 |
| Holdout A/B (provable ROI) | ⭐ very high | S | 1 |
| Lazy Three.js, AudioWorklet, streaming TTS | high | M | 1 |
| Multilingual | high | M | 1–2 |
| CMS plugins, marketplace listings | high | M | 2 |
| Shareable recap pages | high | S–M | 2 |
| Generative landing pages | very high (vision) | L | 3 |
| Agent endpoint (MCP) | high (vision) | M | 3 |
| Omnichannel (phone, WhatsApp) | medium | L | 3 |

---

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Visitors won't talk to websites** (offices, shyness, permission prompts) | Text-first default with voice opt-in. Visual generative UI works without voice. Measure voice adoption before betting the brand on it |
| **LLM and TTS cost blow-ups** | Spend caps, the replay and audio caches, lean-path routing (already built), conversation-based pricing, and BYO-key for Enterprise |
| **Hallucination or brand-safety incident** | Citations, golden answers, blocked topics, guardrail transparency, and an honest claims policy |
| **Legal: recording consent and privacy** | Consent UX, regional notices, PII redaction, retention controls, DPA, data residency |
| **Single-vendor dependency (Google Vertex)** | Provider-neutral `app/ai/base.py` already exists. Add a second LLM and TTS provider in Phase 2–3 |
| **Incumbents add voice** | Win on "acts on the page" plus generative UI, plus the insights data network. Move fast on distribution (plugins, marketplaces) |
| **Premium design that is heavy on the page** | Lazy-load Level 2, ship the 35 kB core, Core Web Vitals budget in CI |
| **Brand name in global markets** | A deliberate naming review before major brand spend |

---

## 10. Next 10 actions (start Monday)

1. Freeze new features. Staff Phase 0 with a 4-week deadline.
2. Implement the **widget key with origin and tier enforcement**, plus rate and spend
   limits. This is the security gate for customer #2.
3. Ship the **per-site agent profile** and the **auto-derived sitemap**, which removes
   every HireBuddha hard-code.
4. Fix delete and invalidate and the tour-overwrite issues.
5. Add the **Install** and **Settings** tabs to the console.
6. Apply the **claims policy** to the website copy and unify the product name.
7. Recruit **10 design partners** with the "hear your website talk" pitch.
8. Draft the new **pricing** page and the outcome-based pilot terms.
9. Spec the **lead, booking and HubSpot** flow, plus the holdout experiment.
10. Instrument **time-to-first-audio** and **cost per conversation**, and put both on the
    analytics page.

> **The founder's line for the next pitch:** *"We don't put a chatbot on your website. We
> turn your website into your best solutions engineer: it talks, it shows, it never makes
> things up, and it books the meeting."*
