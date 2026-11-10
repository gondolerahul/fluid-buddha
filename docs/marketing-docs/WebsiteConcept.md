# FluidBuddha.com — Website Concept

> **What this document is.** The complete concept for the FluidBuddha marketing website: the
> idea, the design direction, the sitemap, every page in detail, the scroll-driven liquid film
> that runs behind the site, and the pipeline for producing that film with Google's Gemini Omni
> video model. It is the brief for the next two phases: **(1) producing the film frames** and
> **(2) building the website**.
>
> **It merges three concepts** from earlier rounds:
> - **Option 1 — Before and After:** the same website and the same visitor, with a different
>   result. This is the story.
> - **Option 5 — Talk to It:** the website is the demo. This is how the visitor experiences the
>   product.
> - **Concept G — The Liquid Interface:** an interface that is liquid until you ask. This is the
>   visual world.
>
> **Sources.**
> - Product facts come from [`docs/product-docs/version_1.0/`](../product-docs/version_1.0/).
> - Use cases come from [UseCases.md](UseCases.md). All 18 are placed on pages; see
>   [§6](#6-use-case-to-page-map).
> - The visual system follows the **Buddha Cognitive Lab design system**
>   (`C:\Workspace\Development\buddha-cognitive-lab-design-system`).
>
> **Status.** Concept approved for production. The six open decisions were answered on
> 6 November 2026 and are recorded in [§13](#13-decisions-and-next-steps). This version
> includes them.

---

## Contents

1. [The concept on one page](#1-the-concept-on-one-page)
2. [Who the site is for](#2-who-the-site-is-for)
3. [Design direction](#3-design-direction)
4. [The liquid film](#4-the-liquid-film)
5. [Sitemap and global elements](#5-sitemap-and-global-elements)
6. [Use case to page map](#6-use-case-to-page-map)
7. [Page by page](#7-page-by-page)
8. [Home film: shot list](#8-home-film-shot-list)
9. [Film production pipeline (Gemini Omni)](#9-film-production-pipeline-gemini-omni)
10. [Website build architecture](#10-website-build-architecture)
11. [Copy and claims rules](#11-copy-and-claims-rules)
12. [Measuring the site with the product itself](#12-measuring-the-site-with-the-product-itself)
13. [Decisions and next steps](#13-decisions-and-next-steps)

---

## 1. The concept on one page

### Name

**Liquid until you ask.**

### The idea in three sentences

Most websites are frozen: when a buyer has a question at 9:40 PM, nothing answers, and they
leave. FluidBuddha makes your website liquid. It listens, then pours itself into the answer: it
speaks, draws a chart, takes the visitor to the right page and books the meeting, using only
what your website already says. We show this with the same website twice, then hand the visitor
the controls so they can try it on ours.

### The story spine (customer as hero)

| # | The visitor's question | What they see | What they read |
|---|---|---|---|
| 1 | *What is this?* | A drop of liquid gold-glass falls onto a white page and splashes into a website. | **Your website, answering every visitor.** |
| 2 | *Why do I need it?* | Night falls. Meera, a head of sales, is on a CRM company's pricing page with two questions. The website freezes over, cold and silent, and she leaves for a competitor. | **Most websites go quiet the moment someone has a question.** |
| 3 | *What changes?* | The same website melts back to liquid and pours itself into the answer: a spoken reply, the price for her team, an integration diagram, the security page, a booked demo. | **Same website. Same visitor. Different result.** |
| 4 | *What exactly did it do?* | The website separates into layers in mid-air, each one labelled. | **It listened. It answered from your website. It showed. It took her to the right page. It booked the demo. It told your team.** |
| 5 | *Can I trust it?* | The liquid only shines with light from the site's own pages. Ask it something off-site and it goes dull. | **It only answers from your website, and shows where each answer came from.** |
| 6 | *Does it really work?* | The film rests and the controls are handed over: "Ask this website anything." | **Don't read about it. Talk to it.** |
| 7 | *Is it hard?* | One drop (one line of code) falls in, the site's pages fall in like droplets, and a website rises. | **One line of code. Live this afternoon.** |
| 8 | *Will I know it's working?* | Two liquid columns rise: visitors who met it and visitors who didn't. | **Measure the extra sales yourself.** |
| 9 | *What does it cost?* | Everything gathers into a single gold drop in the corner: the real assistant, waiting. | **Start free. One drop, on your site.** |

### Why this works

- **It's plain.** Every chapter answers one question a buyer actually has, in ordinary words.
  The metaphor lives only in the visuals; the copy never asks anyone to decode it.
- **The customer is the hero.** "Your website", "your visitor", "your team". FluidBuddha is the
  helper.
- **It's provable.** The live agent runs on the site, so every claim in the film can be tried a
  scroll later.
- **It's luxurious.** A white gallery page, one precious material (liquid gold-glass), large
  quiet type and very few elements on screen at once.

---

## 2. Who the site is for

| Visitor | Arrives wanting to know | Their path through the site | Primary call to action |
|---|---|---|---|
| **Founder / owner of an SMB** (D2C, services, clinic, coaching, real estate) | "Will this get me more customers without hiring?" | Home → Live demo → Industry page → Pricing | Start free |
| **Head of sales / revenue leader** | "Will this turn traffic into qualified pipeline?" | Home → Solutions: Sales → Results & ROI → Book a demo | Book a demo |
| **Marketing head / growth** | "Will this lift conversion, and can I prove it to the CFO?" | Home → Solutions: Marketing → Results & ROI → Pricing | Start a trial |
| **CFO / finance** | "What does it cost, and how is the lift measured?" | Results & ROI → Pricing | Get a quote |
| **CTO / IT / security** | "Is it safe, private, and will it fit our stack?" | Product → Trust & security → Enterprise → Developers | Talk to an engineer |
| **Agency** | "Can I set this up for many clients quickly?" | Industries: Agencies → Pricing → Partner programme | Become a partner |
| **Hindi-first visitor** | "Does it work for my customers in Hindi?" | `/hi/` → `/hi/demo` → `/hi/pricing` (the three Hindi pages) | शुरू करें (Start free) |

**The one promise every page keeps:** *your website answers your visitors, out loud and on the
spot, using only what your website says, and turns them into customers.*

---

## 3. Design direction

The site follows the **Buddha Cognitive Lab design system**: calm, premium "zen-tech", a narrow
palette of gold with warm black and warm white, generous emptiness, and its liquid-glass
material. FluidBuddha is presented as **a Buddha Cognitive Lab product**, as Hire Buddha is.

### 3.1 Canvas: paper by day, ink by night

You asked for a lot of white space and a luxurious feel. The design system has both a warm-black
canvas (its default) and a **paper** theme. We use both, tied to the story:

| Theme | Token values (from `colors_and_type.css`) | Used for |
|---|---|---|
| **Paper** (primary) | `--bg #f6f2ea`, `--surface #fffdf9`, `--fg #1a1611`, `--fg-muted #5c554b`, `--accent #c98f2f` | Most of the site: the hero, explanations, use cases, pricing. A gallery-white page where the gold-glass is the only colour. |
| **Ink** (story moments) | `--bg #0a0908`, `--fg #f6f1e9`, `--accent #edab48` | The night-time "before and after" chapter, the live demo stage, Enterprise, and the night scenes on industry pages. |

On the home page, scrolling moves from **day to night and back to morning**: paper, then ink
for the visitor's 9:40 PM question, then paper again at dawn. Each switch is a slow lighting
change inside the film, never a hard cut. This adds Option 2's emotional idea ("you wake up to
customers") without a second story.

### 3.2 Colour

- **Gold is precious.** It appears only in the liquid, in hairline rules, in one key word per
  headline (`--gradient-gold-metallic` on text), and in the primary button. It is never used as
  a large fill.
- **No other hues.** Semantic colours (sage `#4f8d63`, terracotta `#bb4a34` on paper) appear
  only in small UI states inside product moments.
- **The liquid's colour.** Clear glass with a warm gold core and gold caustics. On paper it reads
  like jewellery photographed on a white sweep. On ink it glows.

### 3.3 Typography

| Role | Face | Usage on this site |
|---|---|---|
| Wordmark and hero words | **Roblox**: the real brand face, confirmed (§13) | The FluidBuddha lockup ([§3.9](#39-fluidbuddha-logo)), the logotype, and occasional single hero words. Never for paragraphs or UI. |
| Display | **Space Grotesk** | Headlines. For luxury, use **light and regular weights (300–400) at very large sizes** (72–148px desktop) with tight tracking (−0.035em), rather than the kit's 600. |
| Body | **Hanken Grotesk** 300–400 | Paragraphs at 18–21px on 1.7 line height, with a maximum measure of 34em. |
| Mono | **JetBrains Mono** | Eyebrows (uppercase, 0.16em tracking, gold), data, code and agent labels. |

**Rule:** at most **one headline, one sentence and one action** on screen at a time in the film
chapters.

**Font files.** The brand's Roblox files were supplied from
`C:\Workspace\Creatives-Logo-Card-Hire Buddha\Creatives-Logo-Card-Hire Buddha\roblox-font\`. They
are byte-for-byte identical to the files already in the design system's `fonts/` folder, so
Roblox is no longer a stand-in. It is the brand typeface (Light, Regular, Bold, Black, plus the
Outline, Round and Shadow cuts). No other brand faces were supplied, so Space Grotesk, Hanken
Grotesk and JetBrains Mono remain the display, body and mono faces. Ship the web build with
WOFF2 conversions of the Roblox TTFs, subset to the characters used.

### 3.4 Space and layout

- A 12-column grid, 1200px content width, and 1440px for full-bleed film frames.
- Section rhythm of **160–240px** vertical space on desktop. That is one step beyond the
  system's `--s-10` (128px), for luxury.
- Text sits in **one quiet column**, usually the left third, while the film owns the rest of the
  screen.
- The dotted-B mark appears as a large, very faint watermark at chapter breaks, never as
  decoration elsewhere.

### 3.5 Material

- **Liquid gold-glass** is the hero material, in the film.
- **Liquid glass UI** (`.glass`, `.glass-gold`, `.glass-bar` from `styles.css`, with paper
  variants) is used for everything interactive that sits over the film: the ask bar, answer
  cards, labels and the navigation bar. As the system requires, glass always sits over something
  with colour (the film), so its refraction reads.
- **Metallic gold** (`--gradient-gold-metallic` plus the `--gradient-gold-shine` sweep on hover)
  is for primary buttons and key figures only.

### 3.6 Motion

- **The film is the motion.** Everything else is calm: fades and 8–16px rises, `--ease-out`
  (`cubic-bezier(.16,1,.3,1)`), 320–640ms, with no bounce.
- Text never moves while you read it. It fades in once the film settles on a chapter.
- Gold may **breathe**, for example the resting drop and the assistant's launcher.
- `prefers-reduced-motion`: the film is replaced by its keyframe stills with cross-fades.

### 3.7 Voice

From the design system, applied:

- **Calm over hype.** No exclamation marks and no "revolutionary".
- **Concrete first, then one lift.** For example: "It answers in under a second, from your price
  list. *Your website, at last, attentive.*"
- **Sentence case.** Uppercase only for mono eyebrows.
- **No emoji.** Icons are Lucide outline icons at a 1.75px stroke.
- **Numbers stay honest.** Real prices are shown. Anything else is labelled *illustrative*.

### 3.8 Accessibility

- All copy is real HTML text (WCAG AA contrast on paper and ink). The film is decorative
  (`aria-hidden`).
- Keyboard users can reach the ask bar and every demo action.
- Captions accompany every spoken reply.
- Gold text on paper uses `--accent #c98f2f` or darker for contrast.

### 3.9 FluidBuddha logo

The FluidBuddha lockup follows the existing **Hire Buddha** lockup exactly. Only the word changes.

| Part | Specification |
|---|---|
| **Icon** | The existing dotted-B mark (`assets/logo-mark-*.svg` / `logo-icon-*.svg`), unchanged. Never redrawn. |
| **Wordmark** | The word **FluidBuddha**, set in **Roblox**, converted to outlines. One word, camel case, no space. Match the weight, letter-spacing and cap height of the Hire Buddha wordmark. |
| **Colour** | The same gold gradient as the Hire Buddha lockup: stops `#fdc871 → #edab48 → #ffefd8 → #fdc871` (icon gradient 0 / 0.26 / 0.54 / 1; wordmark gradient 0 / 0.34 / 0.74 / 1). |
| **Proportions** | Use the Hire Buddha lockup's icon-to-wordmark scale and gap (its viewBox is 728.69 × 396.08) as the template. |
| **Variants** | Gold (primary), white, black and on-black, mirroring `logo-hire-buddha-gold / -white / -black / -onblack.svg`. A horizontal lockup for the navigation bar, plus the icon alone for the favicon and the assistant launcher. |
| **Endorsement** | "A Buddha Cognitive Lab product" in JetBrains Mono, used in the footer and on About. It is not part of the lockup. |
| **On paper** | Use the gold lockup with the paper theme's deeper gold where small sizes need contrast. On ink, use gold or on-black. |

**Deliverable:** `logo-fluidbuddha-{gold,white,black,onblack}.svg`, saved next to the existing
lockups in the design system's `assets/` folder, plus PNG exports for social and app icons.

---

## 4. The liquid film

### 4.1 What it is

One continuous, cinematic 3D scene runs behind the site and is **driven by scroll**: scrolling
down plays it forward and scrolling up rewinds it. The scene is **generated with Gemini Omni**
from keyframes we design, then encoded for frame-accurate scrubbing. In it, liquid gold-glass
flows and morphs into beautiful interface forms, and real HTML (text, buttons, the live agent)
sits on top, aligned to those forms.

### 4.2 The visual vocabulary: seven states of the liquid

Each state is something the product actually does.

| Liquid state | What it looks like | What it means |
|---|---|---|
| **Drop** | One droplet of gold-glass falling in slow motion | One line of code. Also the assistant's launcher. |
| **Pool** | A calm, mirror-still surface | The site at rest, listening |
| **Pour / rise** | Liquid rising and gathering into a shape | Thinking: the answer being prepared |
| **Crystallise** | Liquid snapping into crisp glass panels: cards, bars, tables, buttons | Generative UI: the answer appears as an interface |
| **Ribbon** | A thin stream flowing down the page and pooling at one section | Taking the visitor to the right page |
| **Reflect / dull** | Panels shine with light from the site's pages; without that light, the metal turns flat grey and slumps | Answers only from the site's content; says when it doesn't know |
| **Freeze** | Glass frosting over, matte and cold | The "before": a static website that can't answer |

### 4.3 Film and real UI: how they line up

Generative video can't render readable text, so **the film never contains words.** It shows
blank glass forms, and the real HTML content fades into those forms once they settle.

To make the alignment exact:

1. **Layout first.** For every chapter where liquid becomes interface, we design the target
   layout in HTML (card positions, sizes, corner radii) and export it as a **layout mask image**.
2. **Keyframes from layouts.** A Gemini image model renders each mask as a photographic still in
   the film's material and lighting, so the "settled" frame of each chapter matches our layout
   pixel for pixel.
3. **Interpolate between keyframes.** Gemini Omni generates the motion between consecutive
   keyframes (first-frame / last-frame interpolation), so the clips join seamlessly and every
   clip ends exactly on our layout.
4. **Overlay.** At the settled scroll position, the HTML cards (text, buttons, live data) fade in
   over the blank glass forms. Their glass material matches the film's.

### 4.4 Interactive rests

The film pauses at two points so visitors can act: the **live demo** and the **final call to
action**. At each rest a short **seamless loop** plays (liquid breathing gently), made by giving
Omni the same frame as first and last keyframe, until the visitor scrolls on.

### 4.5 The live agent on top of the film

The site runs the real FluidBuddha agent:

- **The ask bar** ("Ask this website anything") is a glass bar fixed at the bottom of every page,
  styled with the site's tokens. Behind it is the real FluidBuddha widget, using its public
  `ask()` control surface.
- **Answers** appear as glass cards over the film, with generated components (tables, charts,
  flowcharts) rendered by the SDK.
- **The guided tour** can drive the film. "Give me a tour" makes the agent's scroll commands
  (`onScrollTo`) move the film from chapter to chapter, narrated, moving only after each line
  finishes.
- **Persona switching:** when the agent learns the visitor is a CFO, CTO or founder, pages
  re-order their use-case cards and shift emphasis behind the SDK's 300ms blurred cross-fade.
- **Languages:** English and Hindi. A Hindi question gets a Hindi answer. Hindi pages are
  covered in [§7.20](#720-hindi-site-hi).

*Product additions needed* (from the earlier technical review): public state, level and
component events from the SDK, a `setPersona` call for site-driven persona chips, and a
`start()` call that primes audio from the site's own gesture. All are small; see §10.

---

## 5. Sitemap and global elements

### 5.1 Sitemap

```
fluidbuddha.com
│
├── /                         Home — "Liquid until you ask" (the full film)
├── /product                  How it works — talks, shows, acts, only from your site, revenue, proof
│   └── /product/design       Three ways it appears on your site (Companion, Presence, Atmosphere)
├── /demo                     Live demo — talk to it, and try it on your own website
│
├── /solutions
│   ├── /solutions/sales      Turn traffic into qualified pipeline          (UC-01–06)
│   └── /solutions/marketing  Lift conversion and prove it                  (UC-07–10)
│
├── /industries
│   ├── /industries/saas            SaaS and B2B                            (UC-01, 02, 04, 05, 06)
│   ├── /industries/retail-services Retail, D2C and services · Bharat       (UC-03, 11)
│   ├── /industries/healthcare      Clinics and hospitals                   (UC-12)
│   ├── /industries/real-estate     Real estate                             (UC-13)
│   ├── /industries/education       Education and admissions                (UC-14)
│   └── /industries/agencies        Agencies and multi-brand groups         (UC-15)
│
├── /enterprise               Private, compliant, on your infrastructure   (UC-17)
├── /developers               For developers and AI assistants              (UC-16, 18)
├── /results                  Results and ROI — measure it yourself          (UC-09, §8 of UseCases)
├── /pricing                  Plans, calculator, FAQ
├── /integrations             WordPress, Shopify, Webflow, Framer, GTM, React, Vue, CRMs
├── /trust                    Trust and security centre
├── /customers                Customer stories (starting with Hire Buddha)
├── /about                    A Buddha Cognitive Lab product
├── /book-demo                Book a demo (and talk to sales live)
├── /contact
├── /hi/ · /hi/demo · /hi/pricing   Hindi versions of Home, Live demo and Pricing
│
├── /p/{slug}                 Campaign landing pages generated by FluidBuddha itself (UC-07)
├── /r/{id}                   Recap pages created from conversations (product feature)
├── /status                   Public status page (product feature)
└── /legal                    Privacy · Terms · DPA · Sub-processors · Cookie policy
```

### 5.2 Global elements

| Element | Behaviour |
|---|---|
| **Navigation** | A thin glass bar (`.glass-bar`, paper variant), wordmark on the left. Links: Product · Solutions · Industries · Pricing · Developers. Right side: "Book a demo" (ghost) and **"Start free"** (metallic gold). The bar becomes more opaque after the first chapter. Mega-menus for Solutions and Industries, each showing one short line per item. |
| **Ask bar** | Fixed, centred at the bottom, glass. "Ask this website anything", with a mic button and a text field. It expands into the conversation panel. On every page except checkout. |
| **Chapter index** | On film pages, a quiet vertical list of chapter names (mono, 11px) at the left edge, which highlights as you scroll. It doubles as accessible navigation. |
| **Footer** | Paper, with lots of space. A faint dotted-B watermark. Columns: Product, Solutions, Industries, Developers, Company, Legal. "A Buddha Cognitive Lab product." Language switch (English / हिन्दी). Status link. |
| **Cookie banner** | Minimal glass card. "Necessary only" is as prominent as "Accept". |

---

## 6. Use case to page map

Every use case from [UseCases.md](UseCases.md) has a home. Its **primary page** tells it in
full, as a short story section with a liquid film moment. **Secondary pages** reference it in one
line.

| Use case | Primary page | Also appears on |
|---|---|---|
| UC-01 The website that gives the demo | Solutions: Sales | Home (the before/after film), Industries: SaaS |
| UC-02 Anonymous visitor to live sales call | Solutions: Sales | Industries: SaaS, Book a demo |
| UC-03 Close the sale inside the conversation | Industries: Retail & services | Solutions: Sales, Home (the "haan" moment) |
| UC-04 The buying-committee multiplier | Solutions: Sales | Industries: SaaS |
| UC-05 Interactive ROI selling | Solutions: Sales | Industries: SaaS, Real estate |
| UC-06 Self-serve quote and trial desk | Solutions: Sales | Industries: SaaS, Pricing |
| UC-07 One campaign, a thousand landing pages | Solutions: Marketing | Agencies |
| UC-08 The agent that knows when to speak | Solutions: Marketing | Product |
| UC-09 Proving AI ROI to the CFO | Results & ROI | Solutions: Marketing, Pricing |
| UC-10 Voice of the visitor, every Monday | Solutions: Marketing | Results & ROI, Product |
| UC-11 Vernacular voice sales for Bharat | Industries: Retail & services | Hindi site, Home |
| UC-12 Safe AI front desk for clinics | Industries: Healthcare | Trust |
| UC-13 Long-cycle property buying with memory | Industries: Real estate | Product |
| UC-14 Admissions counsellor at midnight | Industries: Education | Home (night chapter) |
| UC-15 Agentic website in an afternoon (agencies) | Industries: Agencies | Integrations, Demo ("try it on your site") |
| UC-16 Your website as a service for AI assistants | Developers | Product, Enterprise |
| UC-17 The regulated enterprise's private agent | Enterprise | Trust |
| UC-18 The headless site that builds itself | Developers | Enterprise |

---

## 7. Page by page

Each page follows the same pattern: **a hero film moment** (short, scroll-driven or looping),
then **calm sections** of one idea each, then **one call to action**. Copy below is
draft-quality, in the brand voice, and meant to be refined.

### 7.1 Home `/`

**Purpose.** Explain the product in two minutes of scrolling, prove it live, and send each
visitor to the right next page.

**Audience.** Everyone. Persona switching re-orders the closing "For you" cards.

**Structure.** The full home film ([§8](#8-home-film-shot-list)) with HTML chapters on top:

| Chapter | On screen (HTML) | Film | Live product |
|---|---|---|---|
| **1. Hero** | Eyebrow `FLUIDBUDDHA · YOUR WEBSITE, ANSWERING`. Headline **"Your website, answering every visitor."** Sub: *"It listens, speaks, shows and books, using only what your website says."* Buttons: **Start free** · Watch what happens ↓. The ask bar is visible. | Drop falls and splashes into a glass website on white (shots S01–S02) | The ask bar works from the first second |
| **2. 9:40 PM** | **"Meera has two questions. Your website has no answers."** *She runs sales at a 40-person distribution company and is comparing CRMs tonight. Does it work with Tally? What would 25 users cost? She finds "Contact sales for pricing" and a calendar with the next call on Thursday.* | Dusk. The glass website frosts over, cold (S03–S04) | — |
| **3. Same website, different result** | **"Same website. Same visitor. Different result."** Four short lines appear one by one: *She asks out loud. It answers in a second, with the price for 25 users from your price list. It draws how the Tally sync works, and takes her to your security page. It books a demo for tomorrow morning, and tells your team.* | The website melts and pours into the answer: conversation, price card, integration flowchart, ribbon to the security section, booking card, gold drop to the team (S05–S08) | The HTML answer cards are real SDK components with example data |
| **4. What just happened** | Six labels around the separating layers: *It listened · It answered from your website · It drew the integration · It took her to the right page · It booked the demo · Your team got the lead* | The website comes apart into layers in depth (S09) | — |
| **5. Talk to it** *(interactive rest)* | **"Don't read about it. Talk to it."** A glass stage with suggestion chips: *How much does it cost? · Show me how it works · क्या ये हिंदी में बात करता है? · Who will win the IPL? · Book a demo*. Six capability cards light up as they're discovered: "You've discovered 3 of 6". | A seamless loop: the liquid breathing beneath the stage | **Fully live.** Real answers, real components, the real booking card (sent to the FluidBuddha sales team) |
| **6. It only answers from your website** | **"It can't shine with what isn't there."** *Every answer comes from your pages, with a link to the source. If something isn't on your site, it says so and offers your team.* | A studio of light panels (the site's pages) reflected in the liquid. One flares as a source. Then the panels go dark and the metal dulls and slumps (S10) | The demo's IPL answer is quoted here if the visitor tried it |
| **7. Morning** | **"You wake up to customers, not missed chances."** A glass notification stack: hot lead in Slack, last night's summary, the most-asked question. | Dawn. Ink returns to paper (S11) | — |
| **8. One line of code** | **"One line of code. Live this afternoon."** Three steps: *Add one line → It reads your website → It starts answering.* Platform names. | One drop falls, pages fall in like droplets, and a website rises from the pool (S12) | — |
| **9. Measure it yourself** | **"See the extra sales, measured properly."** *One in ten visitors never meets it. The difference is your lift, and it's safe to check every day.* Example dashboard, marked *illustrative*. | Two liquid columns rise: with and without (S13) | — |
| **10. For you** | Six cards that re-order by persona: Sales · Marketing · SaaS · Retail & services · Education · Healthcare (then Real estate, Agencies, Enterprise, Developers). | Liquid settles into a calm grid of glass tiles | Persona-driven order |
| **11. Start** | **"One drop, on your site."** Free plan: 100 conversations. Buttons: **Start free** · Book a demo. | Everything gathers into one gold drop, which rolls into the corner and becomes the real assistant's launcher (S14) | Hand-off to the real launcher |

**The sample business.** *Northwind CRM*, a fictional SaaS company selling a CRM to Indian SMBs.
Its example facts are: Starter ₹1,499 per user per month (so ₹37,475 a month for 25 users), syncs
with Tally and Zoho Books, data stored in India, 14-day free trial. All of these are illustrative
and labelled so on the page. The visitor, **Meera**, is a head of sales. Her two questions are the
ones technical buyers ask at night (UC-01).

**Use cases told here.** UC-01 (the film's story), UC-06 (the trial and demo booking), UC-11 and
UC-14 (Hindi, and night-time questions, via the live demo), UC-09 (measurement).

**Primary call to action:** Start free. **Secondary:** Book a demo.

---

### 7.2 Product: how it works `/product`

**Purpose.** A clear, complete explanation of what the product does, for people who want detail
before they try it.

**Hero.** **"Everything your best salesperson does, on every visit."** Film: the liquid website
cycles slowly through its states (pour, crystallise, ribbon, reflect), one per chapter below.

**Sections**, each a two-column chapter with a liquid film moment and a short live example via
the ask bar:

1. **It talks.** Spoken answers, with a first reply in under a second while the full answer is
   prepared. Visitors can interrupt. English and Hindi. *Try: "Can I ask in Hindi?"*
2. **It shows.** Thirteen kinds of visuals drawn while it talks: comparison tables, charts,
   flowcharts, calculators, timelines. They update when the visitor changes a number. *Try: "Compare your plans."*
3. **It takes them there.** Navigates, scrolls, highlights the right section, adapts the page for
   the visitor's role, and can give a narrated guided tour. *Try: "Give me a tour."*
4. **It only answers from your website.** It answers from your pages, files and price lists and
   shows its sources. When something isn't covered, it says so. Owners can pin approved answers
   and block topics. Safety mode for healthcare.
5. **It turns conversations into revenue.** Lead capture and scoring, quotes, trials, meetings
   and payment links (only after the visitor says yes), recap pages to forward, and live handoff
   to your team, including a browser voice call.
6. **It knows when to speak.** Proactive openers on time on page, scroll depth, exit intent and
   return visits, written for each page and capped so they never nag. *(UC-08)*
7. **It remembers, if invited.** Returning visitors who opt in pick up where they left off.
   *(UC-13)*
8. **It proves its value.** Holdout measurement, A/B tests, insights on what visitors ask,
   objections, competitors and missing content, and a Monday digest. *(UC-09, UC-10)*
9. **It gets cheaper as it learns.** Repeat questions replay from memory at almost no model cost.
   Spend caps and alerts per site.

**Sub-page `/product/design`: three ways it appears.** The Companion (a floating panel), the
Presence (an immersive full-screen field), the Atmosphere (no widget: the page itself glows and
captions). Each is shown as a looping film tile, with a live toggle to preview it on this page.

**Call to action:** Try the live demo.

---

### 7.3 Live demo `/demo`

**Purpose.** The full hands-on experience, combining Option 5 (talk to it) with Option 3 (see
it on your own website).

**Hero.** Ink stage. **"Talk to it."** A large glass conversation stage over a breathing liquid
loop. Six capability cards wait to be discovered, as on Home chapter 5 but larger, with voice
first.

**Section 2: "Now try it on your own website."** A glowing address field: *"Enter your website.
Hear it talk."* This is a **real sandbox preview from launch** (decided, §13).

1. The visitor enters their website address and a work email.
2. A one-time code is sent to that email. The email domain must match the website's domain, so
   nobody can preview a competitor's site. Free-mail addresses (gmail.com and similar) get a
   reduced preview of 3 pages.
3. The real onboarding pipeline runs and its real progress drives the animation: reading pages
   (up to 8, depth 1, respecting `robots.txt`), learning what they sell, finding their customers,
   picking up their brand.
4. Their homepage is recomposed in their own brand colours. Their own agent answers questions
   about their business with sources linking to their pages, in English or Hindi.
5. Suggested questions are generated from what was read, so they're about their business.
6. If reading takes longer than 45 seconds: *"We'll email you when your preview is ready."*
7. The preview, its knowledge and all its data are **deleted after 24 hours** through the
   product's true-deletion path. *"Keep it"* converts the preview into a Free-plan site.

Copy: *"A preview from a few of your pages in about a minute. A full setup takes an
afternoon."* Three example businesses (a software company, a clinic and a coaching institute)
stay available beside the address field for visitors who just want to watch.

The backend this needs is specified in [§10.1](#101-sandbox-preview-service).

**Section 3: "Take it home."** The install-preview bookmarklet ("drag this to your bookmarks bar,
open your site, click it") plus Start free.

**Use cases.** UC-15 (live from a URL), plus a little of every capability.

---

### 7.4 Solutions: Sales `/solutions/sales`

**For.** Heads of sales and revenue leaders, SaaS and B2B.

**Hero.** **"Turn tonight's visitors into tomorrow's pipeline."** Film: liquid gathers into a
calm pipeline of glass cards that fill up as you scroll.

**Story sections (one use case each)**, each with a liquid moment and a short HTML replay of the
conversation:

| Section | Headline | Use case |
|---|---|---|
| 1 | **"The demo, given by your website at 11 PM."** It answers the technical questions, draws the integration, prices 60 seats and hands over a qualified lead. | UC-01 |
| 2 | **"Spot the hot buyer. Call them in the browser."** Your team sees live visitors, takes over the conversation, and can start a voice call with no phone number needed. | UC-02 |
| 3 | **"Close the sale in the conversation."** The visitor says "yes" or "haan", and gets a correct payment link from your price list. | UC-03 |
| 4 | **"One champion, the whole committee."** A recap page the buyer forwards to colleagues, with live charts, and you see how far it spread. | UC-04 |
| 5 | **"A calculator built for their numbers."** It builds the ROI calculator on the spot and comments as they move the sliders. | UC-05 |
| 6 | **"Quotes and trials, without waiting for sales."** Quote PDFs and trial accounts, confirmed by the buyer and sent to your team. | UC-06 |

**Proof strip.** "How you'll measure it": holdout with the demo-booked page as the goal, lead
scores with reasons, cost per conversation. Worked examples are labelled *illustrative*.

**Call to action:** Book a demo. **Secondary:** Results & ROI.

---

### 7.5 Solutions: Marketing `/solutions/marketing`

**For.** Marketing and growth heads.

**Hero.** **"Every campaign, a page that talks back."** Film: one drop splits into many smaller
drops, each forming its own landing page.

| Section | Headline | Use case |
|---|---|---|
| 1 | **"One campaign. A thousand landing pages."** A page for every account, role and search term, written from your own content, with numbers checked against your sources. | UC-07 |
| 2 | **"It knows when to speak."** Openers written for each page, tested against each other, with the winner promoted in one click. | UC-08 |
| 3 | **"Show the CFO the lift."** A built-in control group and statistics that stay valid however often you check. | UC-09 (links to /results) |
| 4 | **"What your visitors asked, every Monday."** Top questions, objections, competitors and missing content, delivered by email. | UC-10 |

**Call to action:** Start a trial.

---

### 7.6 Industries: SaaS and B2B `/industries/saas`

**Hero.** **"The technical buyer, answered before they ask for a call."** Film: liquid crystallises
into an integration diagram, then a seat-price configurator.

**Sections:** the 11 PM technical demo (UC-01) · live takeover (UC-02) · the committee recap
(UC-04) · ROI calculator (UC-05) · quotes and trials (UC-06) · security questions answered from
your trust pages, with SSO, audit and self-hosting (link to Enterprise).

**Live example.** The ask bar uses an example knowledge base ("Northwind CRM").

**Call to action:** Book a demo.

### 7.7 Industries: Retail, D2C and services · Bharat `/industries/retail-services`

**Hero.** **"Your customers ask in Hinglish. Your website answers in Hindi."** Film (ink, night):
a phone glowing in a dark room, its screen made of liquid glass.

**Sections:**
- **Vernacular voice sales.** Hindi and Hinglish answers from your English content, with no
  translation project. *(UC-11)*
- **"Haan" closes the sale.** Payment links via your own Razorpay account, UPI Autopay handled.
  *(UC-03)*
- **Night-time demand.** Most enquiries arrive after hours.
- **Hindi live demo.** Chips in Hindi; the ask bar answers in Hindi.

**Call to action:** शुरू करें / Start free.

### 7.8 Industries: Healthcare `/industries/healthcare`

**Hero.** **"A front desk that books appointments and never gives medical advice."** Film (paper,
calm): liquid forms an appointment card that settles into a calendar.

**Sections:**
- Booking in English or Hindi.
- **Safety mode:** requests for diagnosis, treatment or dosage get a fixed, polite refusal and an
  offer to book. Emergencies get emergency numbers. This runs before any AI model is called.
  *(UC-12)*
- Privacy: masking of emails, phone numbers and card numbers, plus retention and erasure.
- Example clinic demo, including the refusal moment, shown honestly.

**Call to action:** Book a demo. **Compliance note:** link to /trust.

### 7.9 Industries: Real estate `/industries/real-estate`

**Hero.** **"Buyers take months. Your website remembers."** Film: liquid draws a floor plan, a
price chart, then a "welcome back" card.

**Sections:** returning-visitor memory, opt-in, with "Forget me" *(UC-13)* · EMI calculator with
live comments *(UC-05)* · site-visit booking · recap to share with family.

**Call to action:** Book a demo.

### 7.10 Industries: Education `/industries/education`

**Hero.** **"An admissions counsellor at midnight."** Film (ink): a student's laptop at night,
liquid forming a programme comparison, then a recap page passed to a parent's phone at dawn.

**Sections:** programme guidance from your prospectus · application-fee payment, confirmed by the
student · a recap the student forwards to parents · Hindi support. *(UC-14)*

**Call to action:** Start free.

### 7.11 Industries: Agencies `/industries/agencies`

**Hero.** **"Turn a client's website into a talking one in an afternoon."** Film: many small drops
land on many small websites, each blooming in its own brand colour.

**Sections:**
- From a URL to a working agent: reads the site, finds audiences, picks up the brand, plans a
  tour. *(UC-15)*
- Templates by industry.
- Generated campaign pages for clients. *(UC-07)*
- One account for many sites, with teams and roles.
- Partner programme (commercial terms to be decided).

**Call to action:** Become a partner. **Secondary:** Try it on a client's site (/demo).

### 7.12 Enterprise `/enterprise`

**Hero (ink).** **"Your agent, on your infrastructure, under your rules."** Film: liquid sealed
inside a clear glass cube, calm and contained.

**Sections:**
- **Self-hosted edition:** one-host install, backups, offline signed licence. Visitor-facing
  features keep working if the licence lapses. *(UC-17)*
- **Your identity and your model:** your own sign-in provider (OIDC SSO with domain proof), MFA,
  audit log, and bring your own model (Anthropic, OpenAI, Azure OpenAI). *Stated plainly: speech
  and embeddings run on Google Vertex AI.*
- **Governance:** roles, access reviews, SOC 2 control pack and policies, DPA and sub-processor
  list.
- **Reliability:** 99.9% SLA tooling, status page, graceful drain on deploys.

**Call to action:** Talk to an engineer.

### 7.13 Developers and AI assistants `/developers`

**Hero.** **"Your website, as a service other AI assistants can ask."** Film: liquid nodes
connecting into a calm network of glass.

**Sections:**
- **Agent endpoint:** an MCP server, `llms.txt`, an OpenAPI "ask" endpoint, and scoped tokens so
  assistants can capture leads or run actions. *(UC-16)*
- **Pages composed per question:** the top tier composes whole pages from typed sections and your
  site APIs. *(UC-18)*
- **SDK and installs:** script tag, `@fluidbuddha/react`, `@fluidbuddha/vue`, hooks
  (`onNavigate`, `onScrollTo`, `onSetPersona`), events, custom components.
- **Webhooks:** signed (HMAC-SHA256) to CRMs, Zapier and Make.

**Live example.** "Ask this site from your own AI assistant", with copyable MCP configuration.

**Call to action:** Read the docs.

### 7.14 Results and ROI `/results`

**Hero.** **"Measure the extra sales. Don't take our word for it."** Film: two liquid columns rise
side by side, one for visitors who met it and one for the 1 in 10 who didn't.

**Sections:**
1. **How the measurement works**, in plain words: a control group, your own goal (a thank-you
   page or a booking), and statistics that stay valid however often you look. *(UC-09)*
2. **The six-step ROI method** from UseCases §8, as six calm steps.
3. **Interactive ROI calculator** (a FluidBuddha component, live). Inputs: monthly traffic,
   conversion, deal size, plan. Stamped **Illustrative: replace with your numbers.**
4. **Unit economics:** about ₹16.50 per conversation on Growth and ₹12.50 on Scale, compared with
   one paid click or one hour of a sales engineer.
5. **What visitors ask you** (UC-10), shown as an example digest.

**Call to action:** Start a trial and measure it.

### 7.15 Pricing `/pricing`

**Hero.** **"Start free. Pay for conversations, not seats."** Film: liquid settles into four
glass columns.

| Plan | Price (INR / month) | Included | Extra |
|---|---|---|---|
| Free | ₹0 | 100 conversations | No overage (hard cap) |
| Growth | ₹33,000 | 2,000 conversations | ₹17 each |
| Scale | ₹1,25,000 | 10,000 conversations | ₹10 each |
| Enterprise | Custom | Unlimited | — |

**Sections:**
- What counts as a conversation: a visitor session with at least one answered turn. Calls from
  AI assistants are not counted.
- Feature comparison by plan and intelligence tier.
- A **cost calculator** (live component).
- FAQ, answered by the agent as well as written out.
- Quote request: the agent can produce a PDF quote. *(UC-06)*

**Call to action:** Start free · Get a quote.

### 7.16 Integrations `/integrations`

A gallery of glass tiles: WordPress, Shopify, Webflow, Framer, Google Tag Manager, React, Vue,
plain script tag, plus Slack, Zapier, Make, CRMs via webhook, Razorpay, Calendly and Cal.com.
Each tile opens a 3-step guide. Hero film: one drop landing on several platform shapes.

### 7.17 Trust and security `/trust`

Plain-language trust centre:

- Answers only from your content, with sources.
- PII masking (emails, phone numbers, card numbers), microphone consent, retention and erasure.
- Healthcare safety mode.
- Data processing details, including the Google Vertex AI note.
- SOC 2 control pack, policies, DPA, sub-processors.
- Status page and incident history.
- A "security questionnaire" request form.

Calm, mostly text, paper, very little film.

### 7.18 Customers `/customers`

Starts with **Hire Buddha** (the first customer and built-in demo profile). Only real,
consented results are published. Until holdout results exist, the page shows the story and the
measurement plan rather than numbers.

### 7.19 About, book a demo, contact

- **About:** *"A Buddha Cognitive Lab product. Towards digital enlightenment."* The lab, its
  mission and its team.
- **Book a demo:** the agent books the slot in the conversation (meeting-link action). A team
  member can join live during staffed hours.
- **Contact:** a form that posts straight to the server, plus email.

### 7.20 Hindi site `/hi/`

Three pages only, as decided: **Home (`/hi/`), Live demo (`/hi/demo`) and Pricing
(`/hi/pricing`)**. They are set in Devanagari with Noto Sans Devanagari, paired with Hanken
Grotesk. The ask bar defaults to Hindi. The film is shared with the English site; only the HTML
layer changes. Every other page is English-only, but the agent on those pages still answers in
Hindi when asked in Hindi, because that's the product's own behaviour.

### 7.21 Product-generated pages

- `/p/{slug}`: campaign landing pages composed by FluidBuddha from a brief (UC-07), styled with
  the site's design tokens.
- `/r/{id}`: recap pages created when a visitor says "send me this".
- `/status`: the product's public status page.

These are live proof that the product builds real pages.

---

## 8. Home film: shot list

The home film is about **2 minutes of footage across 14 shots**. Each shot is generated as one
Omni clip between two designed keyframes, so shot N's last frame is shot N+1's first frame.

**Formats:**
- **Desktop:** 16:9, finished at 1080p (with 4K masters).
- **Mobile:** 9:16. Re-framed keyframes are generated separately, not cropped.

| Shot | Scroll range | Length | Start keyframe → end keyframe | What happens | HTML on top |
|---|---|---|---|---|---|
| **S01 Drop** | 0–5% | 8s | Empty warm-white sweep, soft top light → a single drop of gold-glass mid-air | The drop falls in extreme slow motion, catching reflections | Hero copy (fades in at rest) |
| **S02 Splash to website** | 5–12% | 10s | Drop touching a mirror pool → **layout mask 1**: glass nav bar, hero card, three cards, button | The splash crowns, freezes, and crystallises into blank glass UI | Hero headline, ask bar, site text inside the glass forms |
| **S03 Dusk** | 12–17% | 8s | Layout 1 on paper → layout 1 at night (ink, a warm city glow far behind) | The light falls slowly from day to night; the glass glows faintly | "9:40 PM. Meera has two questions." |
| **S04 Freeze** | 17–25% | 10s | Layout 1 at night → **layout 1 frosted** (matte, opaque, cold) | Frost spreads across every surface; the gold fades to grey | Her two questions, "Contact sales for pricing", "Next available call: Thursday", "She leaves for a competitor." |
| **S05 Thaw** | 25–29% | 6s | Layout 1 frosted → layout 1 liquid, warm | Gold warmth spreads; the frost melts back to liquid | "Same website. Same visitor. Different result." |
| **S06 Pour into the answer** | 29–38% | 12s | Layout 1 liquid → **layout mask 2**: a conversation column, a price card, a three-node flowchart | Liquid rises from the page and crystallises into the answer forms | Her questions and the answers, the price for 25 users, the Tally sync flowchart, source chips |
| **S07 Ribbon** | 38–44% | 8s | Layout 2 → **layout mask 3**: the page scrolled, a gold ring around one section | A thin ribbon runs down the page and pools in a ring at the security section | "It takes her to your security page: data stored in India." |
| **S08 Booking and the drop** | 44–52% | 10s | Layout 3 → **layout mask 4**: a booking card, then a small gold drop falling out of frame | The card forms. On "yes" it condenses into a gold drop that falls away, followed by a soft ripple | "Demo booked for 10 AM. Your team has the lead in Slack." |
| **S09 Layers** | 52–60% | 10s | Layout 4 front-on → **layout mask 5**: the same layers separated in depth, seen at an angle | The website comes apart into floating layers; the camera orbits 25° | The six labels |
| **REST A — Talk to it** | 60–66% | 6s loop | Same frame first and last: liquid breathing beneath a glass stage | A seamless loop while the visitor uses the live demo | **The live demo** |
| **S10 Reflect, then dull** | 66–74% | 12s | A pool with a studio of blank light panels reflected → one panel bright → all panels dark, metal dull and slumped | The site's pages light the liquid; then a question with no source, and the metal dulls | "It can't shine with what isn't there." Panel titles as HTML |
| **S11 Dawn** | 74–78% | 6s | Dull dark scene → a bright warm-white morning sweep | The light returns; the liquid recovers its shine | "You wake up to customers." Notification stack |
| **S12 One line of code** | 78–86% | 10s | Empty sweep → **layout mask 6**: a pool rising into a small website | A drop falls (the script); small droplets (pages) rain into a pool; the pool rises into a website | The three steps, the code line, platforms |
| **S13 Two columns** | 86–92% | 8s | Calm pool → **layout mask 7**: two glass columns of different heights | Two columns of liquid rise; one taller | "Measure it yourself." Example numbers, *illustrative* |
| **S14 One drop** | 92–100% | 10s | Layout 7 → everything gathered into one gold drop resting at the bottom-right corner | All forms flow together into a single drop that rolls to the corner | "One drop, on your site." The real launcher takes over the drop's exact position |

**REST B:** a seamless loop of the resting drop holds the final call to action.

**Total:** about 128s of footage plus two 6s loops. Mobile adds its own 9:16 set of the same
shots.

### 8.1 Page hero films

Each page gets one 6–10s hero clip (and a 9:16 version). Most are scroll-driven; a few are loops.

| Page | Hero film |
|---|---|
| Product | The liquid cycles slowly through pour, crystallise, ribbon and reflect |
| Demo | A breathing liquid loop beneath a glass stage (ink) |
| Sales | Liquid gathering into a pipeline of glass cards |
| Marketing | One drop splitting into many drops, each forming a page |
| SaaS | Liquid crystallising into an integration diagram, then a configurator |
| Retail & services | A phone in a dark room, its screen made of liquid glass (ink) |
| Healthcare | Liquid forming an appointment card that settles into a calendar |
| Real estate | Liquid drawing a floor plan, then a price chart |
| Education | Liquid forming a comparison at night, then a recap on a phone at dawn |
| Agencies | Many small drops blooming into websites in different brand colours |
| Enterprise | Liquid sealed and calm inside a clear glass cube (ink) |
| Developers | Liquid nodes connecting into a network |
| Results | Two liquid columns rising side by side |
| Pricing | Liquid settling into four glass columns |
| Integrations | One drop landing on several platform shapes |

---

## 9. Film production pipeline (Gemini Omni)

### 9.1 What the model can do (verified November 2026)

According to Google's announcements:

- **Gemini Omni 1.2 Flash** is generally available on the Gemini API and Google Cloud.
- **Clip length:** native clips of **3 to 15 seconds**, set in one-second steps.
- **Resolution:** drafts at **360p or 720p**, upscaled to **1080p or 4K** for final output.
- **Inputs:** guidance from reference images and short motion clips (up to 3 seconds).
- **Joining and extending:** **interpolation between a first and a last keyframe**, and
  **extension** of a clip into a longer sequence.
- **Editing:** multi-turn conversational editing, without regenerating the whole clip.
- **Price:** **$0.07 per second at 720p**.
- **Watermark:** outputs carry an invisible SynthID watermark.
- **Known weak spot:** Google lists complex physics as still improving. That matters for liquid,
  so it drives our keyframe-first approach.

**Gemini Omni 1.1 Flash** (`gemini-omni-1.1-flash`) introduced:
- resolution control (`response_format`);
- extension via `previous_interaction_id`, in 10-second increments up to 40 seconds;
- 360p drafts, up to 60% faster than 720p at about a third of the cost.

Sources:
- [Google: Introducing Gemini Omni 1.2 Flash](https://blog.google/innovation-and-ai/technology/developers-tools/introducing-gemini-omni-1-2-flash/)
- [Google: Build with Gemini Omni 1.1 Flash](https://blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-omni-1-1-flash/)
- [Gemini API docs](https://ai.google.dev/gemini-api/docs/omni)

**Check parameter names and prices against the API docs before the production run.**

### 9.2 The pipeline

```
 1. Layout masks        HTML layouts → PNG masks (exact card positions, radii)       [in-house]
 2. Style frames        Gemini image model: mask + style references → photographic
                        keyframes in the film's material and light                    [Gemini]
 3. Keyframe approval   Art direction review of every keyframe (desktop 16:9 + mobile 9:16)
 4. Motion drafts       Omni 1.2 Flash, 360p: interpolate keyframe N → N+1, 6–12 s per shot
 5. Edit passes         Omni conversational edits on weak shots (lighting, speed, physics)
 6. Finals              Re-render approved shots at 720p, then upscale to 1080p / 4K
 7. Conform             Join shots, colour-match boundaries, remove any visible seams;
                        build the seamless loops (same first/last frame)               [in-house]
 8. Encode for scroll   Per-chapter MP4 (H.264 + AV1) with short keyframe intervals;
                        AVIF poster frames; 9:16 mobile set                            [ffmpeg]
 9. Register UI         Record the settled-frame position of every glass form for the HTML layer
10. QA                  Scrub test on target devices; seam check; brand check; text-free check
```

### 9.3 Generation guidelines for the liquid

- **Material:** "clear liquid glass with a warm gold core, polished, high-end jewellery product
  photography, soft studio light, warm white sweep background, gentle caustics". On ink: "warm
  near-black background, gold glow".
- **Camera:** slow, smooth and continuous: dolly, slow orbit at most 25°, no cuts and no shake.
  It must be predictable, because the film runs backwards on scroll-up.
- **Physics:** keep motion slow and viscous. Prefer short shots (6–10s) between close keyframes
  over long free-form shots, because Google lists complex physics as still improving.
- **No text, no logos, no faces, no hands** in any frame. Interfaces are blank glass forms only.
- **Palette lock:** use the same style references for every shot (approved keyframes plus a short
  motion reference), so the material never drifts.
- **Seam rule:** every shot starts on the exact approved end frame of the shot before it.

### 9.4 Budget estimate (generation only)

| Item | Seconds | Notes |
|---|---|---|
| Home film (desktop) | ~140 | 14 shots plus 2 loops |
| Home film (mobile 9:16) | ~140 | Re-framed keyframes |
| Page heroes (15 pages × 8s × 2 formats) | ~240 | |
| **Total per complete pass** | **~520 s** | |

- **Drafts at 360p:** about 3 passes × 520s at about $0.023/s (one third of the 720p price) ≈
  **$36**.
- **Finals at 720p:** 520s × $0.07 ≈ **$36** per pass. Allow 2–3 passes for retakes: **$75–110**.
- **Upscaling to 1080p/4K:** the price was not published in the announcement. Check the pricing
  page.
- **Keyframe image generation:** small by comparison.

**Working budget: about $150–300 in API costs**, plus upscaling, plus art-direction time. Costs
are from Google's announced 720p price; verify before the run.

### 9.5 API keys and safety

- Keep the Gemini API keys in a local `.env` or a secrets manager for the pipeline scripts. Never
  put them in the repository, the website build or any client-side code.
- Log every generation (prompt, references, seed if available, output ID) so any shot can be
  re-made.
- Confirm the commercial-use terms for generated video in your Google Cloud / Gemini API
  agreement before publishing.

---

## 10. Website build architecture

| Area | Choice |
|---|---|
| Framework | Next.js (App Router), static generation for all marketing pages, SSR for `/demo` and generated pages. |
| Styling | The design system's `colors_and_type.css` and `styles.css` as the token base. Paper theme via `data-theme="light"` on the film's day chapters; ink for night chapters. |
| Scroll engine | Lenis for smooth scrolling. A small chapter controller maps scroll position to film time. GSAP for the HTML layer's fades. |
| Film playback | Per-chapter MP4s decoded with **WebCodecs** into a `<canvas>` for frame-accurate scrubbing in both directions. Fallback: a pre-extracted image sequence at 12–15 fps for browsers without WebCodecs. Chapters stream ahead of the visitor. |
| Performance budgets | LCP under 2.0s, with the first frame served as an AVIF poster. Under 200KB of JS before the film starts. First chapter under 3MB. Desktop film under 60MB total, streamed lazily. Mobile under 25MB. |
| Reduced motion / low data | Keyframe stills with cross-fades, and no film streaming on Save-Data. |
| The agent | The real FluidBuddha SDK with the site's own glass ask bar on top (via `ask()`). The tour engine is mapped to film chapters through `onScrollTo`. Persona changes re-order cards. |
| SDK additions | Public `fluidbuddha:state`, `level` and `component` events; `setPersona(id, {explicit:true})`; `FluidBuddha.start()`. |
| SEO | All copy is real HTML. Per-page metadata. `llms.txt` and the MCP endpoint switched on for the site itself. `hreflang` pairs for the three Hindi pages. |
| Analytics | The product's own holdout and A/B tests (§12), plus privacy-friendly page analytics. |

### 10.1 Sandbox preview service

The real "try it on your own website" preview (§7.3) needs a small service next to the product
backend. It reuses the product's own onboarding, knowledge and agent. Only the gate, the limits
and the clean-up are new.

| Part | What it does |
|---|---|
| **Email gate** | Sends a one-time code. Checks that the email's domain matches the website's domain (allowing `www.` and subdomains). Free-mail domains get the reduced 3-page preview. Blocks disposable-email domains. |
| **Sandbox site** | Creates a temporary site in a dedicated sandbox account with an expiry time. Advance tier, Hindi enabled, demo-only actions (bookings and payments are simulated and never sent). |
| **Crawl** | The product's own crawler with sandbox limits: 8 pages, depth 1, robots.txt respected, the existing SSRF guard, a 60-second budget. |
| **Onboarding job** | The existing one-job pipeline (crawl → ingest → personas → brand design tokens), with its live progress streamed to the page to drive the animation. |
| **Preview rendering** | The visitor's homepage recomposed from typed sections in their extracted brand tokens. Their site is never framed or copied: if brand extraction fails, a neutral gold theme is used and the page says so. |
| **Agent** | The real agent pointed at the sandbox site's knowledge, with a per-session turn cap (for example 15 turns). |
| **Clean-up** | An hourly sweep hard-deletes expired sandbox sites after 24 hours using the product's true-deletion path. "Keep it" moves the site into a new Free-plan account instead. |
| **Abuse and cost limits** | Rate limits per IP, per email and per domain (for example one active preview per domain). A daily cap on sandbox crawls and model spend, with cost alerts. A queue during spikes, and the "we'll email you" path. |
| **Privacy copy** | Shown beside the address field: what is read (public pages only), what is stored, and that it's deleted after 24 hours. |
| **Leads** | A verified email plus a domain is a high-quality lead. It goes to the sales pipeline with the questions the visitor asked their own site. |

Build order: email gate → sandbox site and limits → progress streaming → preview rendering →
clean-up and conversion. It ships with the site, not after it.

---

## 11. Copy and claims rules

From [UseCases.md §9](UseCases.md#9-claims-guidance-for-marketing) and the design system's voice:

- Say **"answers only from your website, with sources"**. Never "never makes things up" or "zero
  hallucinations".
- Say **"English and Hindi"**. No other languages are supported.
- Say **"acts on your site through navigation, scrolling, highlighting and the actions you set
  up"**, not "does anything on your website".
- Say **"adapts to the visitor's role, language and page"**, not "personalised to each
  individual".
- Every ROI number is **illustrative** unless it is a real, consented customer result.
- State that **speech and embeddings run on Google Vertex AI** wherever data residency or bring
  your own model comes up.
- Time-to-first-reply claims: "under a second" for the spoken acknowledgement. Capacity planning
  is handled by us, not promised as unlimited.
- Calm voice: no exclamation marks, no emoji, sentence case.

---

## 12. Measuring the site with the product itself

- **Holdout from day one.** 10% of visitors get the site without the agent. Their film runs the
  same, but the ask bar and the live demo are replaced by a "see it in action" video. The goals
  are a booked demo, a trial start and a free sign-up.
- **A/B tests.** Hero headline variants, the opener for each page, and the design level.
- **Insights.** What visitors ask on each page feeds the copy roadmap (UC-10, applied to
  ourselves).
- **A public proof page.** Once the holdout leaves "collecting", publish our own lift on
  `/results`.

---

## 13. Decisions and next steps

### Decisions (recorded 6 November 2026)

| # | Question | Decision | What it changes in this document |
|---|---|---|---|
| 1 | Canvas | **Agreed:** paper is the primary canvas; ink only for night and stage moments. | §3.1 stands as written. |
| 2 | FluidBuddha wordmark | **Design it**, using the same dotted-B icon with the word "FluidBuddha" in the same font and colours as the existing lockups. | New logo specification in [§3.9](#39-fluidbuddha-logo). |
| 3 | Brand fonts | **Supplied:** the Roblox font folder. The files are identical to those in the design system, so Roblox is now confirmed as the brand typeface rather than a substitute. | §3.3 updated. Space Grotesk, Hanken Grotesk and JetBrains Mono remain for display, body and mono, because no other faces were supplied. |
| 4 | Sample business in the home film | **A SaaS business.** | The home story now follows Meera, a head of sales, on the pricing page of *Northwind CRM* (a fictional SaaS company): §1, §7.1 and the §8 shot list. |
| 5 | "Try it on your own website" | **Build the real sandbox preview** from launch. | §7.3 rewritten; new backend specification in [§10.1](#101-sandbox-preview-service); added to the build plan below. |
| 6 | Hindi at launch | **Two to three pages are enough.** | Hindi limited to Home, Live demo and Pricing (`/hi/`, `/hi/demo`, `/hi/pricing`): §2, §5.1, §7.20, §10. |

### Still open (smaller, can be settled during production)

- **The sample SaaS business's details.** The example facts for *Northwind CRM* (price per user,
  Tally integration, data in India) are illustrative. Replace them with a real customer's,
  with consent, if you prefer.
- **Partner programme terms** for the Agencies page.
- **Who answers live chats** during staffed hours (for live takeover and demo booking).

### Next steps

1. **Logo.** Design the FluidBuddha lockup and its variants (§3.9).
2. **Style test (1–2 days).** Generate 4–6 keyframes for S01, S02 and S04 in the paper and ink
   looks and a 360p Omni test of S01→S02, to lock the liquid's look before the full run.
3. **Layout masks.** Build the HTML layouts for the seven home-film masks at both aspect ratios,
   using the Northwind CRM story.
4. **Full film run.** Keyframes, drafts, edits, finals and encoding (§9.2).
5. **Website build.** Design system tokens with Roblox in WOFF2, scroll engine, film player, HTML
   chapters, ask bar, then pages in this order: Home, Demo, Pricing, Sales, Marketing,
   industries, the rest, then the three Hindi pages.
6. **Sandbox preview service** (§10.1), built alongside the site so `/demo` launches with it.
7. **SDK additions** in parallel with the site build.
