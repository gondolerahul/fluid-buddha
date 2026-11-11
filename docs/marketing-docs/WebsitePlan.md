# FluidBuddha — Website Plan (default site + three persona sites)

> **Status.** Plan for review, 10 November 2026. Nothing here is built yet.
>
> **Sources.** Product: [Feature List](../product-docs/version_2.0/FeatureList.md) and
> [Functional Specification](../product-docs/version_2.0/FunctionalSpecification.md).
> Audience: [IdealCustomerProfiles.md](IdealCustomerProfiles.md),
> [ICPPersonas.md](ICPPersonas.md), [UseCases.md](UseCases.md). Design: the Buddha Cognitive
> Lab design system (`C:\Workspace\Development\buddha-cognitive-lab-design-system`). Existing
> code: `fludi-buddha-website/` (Next.js site, film pipeline, FluidBuddha logos).
>
> **Copy rule.** Every line of copy in this plan follows the claims guidance in
> [UseCases.md §10](UseCases.md#10-claims-guidance-for-marketing). All example numbers are
> marked as examples.
>
> **No version talk.** The product has not launched, so everything is new to the visitor.
> The site never mentions version numbers or says "new in". (This plan cites the version 2.0
> product documents as its source; that is internal.)

---

## Contents

1. [Decisions already made](#1-decisions-already-made)
2. [What exists and what we reuse](#2-what-exists-and-what-we-reuse)
3. [How the site works: four worlds and a morph](#3-how-the-site-works-four-worlds-and-a-morph)
4. [Design: one system, four settings](#4-design-one-system-four-settings)
5. [Film language and techniques](#5-film-language-and-techniques)
6. [World 0: the default site](#6-world-0-the-default-site)
7. [World 1: B2B SaaS](#7-world-1-b2b-saas)
8. [World 2: Education](#8-world-2-education)
9. [World 3: Regulated enterprise](#9-world-3-regulated-enterprise)
10. [Production pipeline](#10-production-pipeline)
11. [Technical build](#11-technical-build)
12. [Phases, deliverables and acceptance](#12-phases-deliverables-and-acceptance)
13. [Risks](#13-risks)
14. [What I need from you](#14-what-i-need-from-you)

---

## 1. Decisions already made

| # | Decision | Choice |
|---|---|---|
| 1 | How many sites | A default site plus three persona sites: B2B SaaS (ICP-1), Education (ICP-2), Regulated enterprise (ICP-7). Inside each, copy changes by role. |
| 2 | How different they look | Same design system, different settings per site (mode, density, material, type emphasis, motion pace, film subject). |
| 3 | How we identify the visitor | Layered: campaign link and referrer, then a visible selector, then what the visitor tells the agent. |
| 4 | Film concept | "The page that rearranges itself": a website shown as floating 3D panels that respond to a visitor. |
| 5 | Film production | A mix for variety: Gemini image and video models, animation written in code, and character (ASCII) animation. |

In this plan a persona site is called a **world**. World 0 is the default.

---

## 2. What exists and what we reuse

The repository already holds a working draft website. This plan builds on it instead of
starting again.

| Asset | Where | Reuse |
|---|---|---|
| Next.js site (Next 16, React 19), English and Hindi home, pricing, demo, content pages | `fludi-buddha-website/web/` | Keep as the platform. Add the world system on top. |
| Scroll film player: frames drawn to a canvas, chapters of HTML copy on top, day/night theme switch by frame | `web/src/components/FilmPlayer.tsx`, `web/src/content/home.ts` | Generalise it so each world supplies its own film and chapters. |
| Film pipeline: layout masks → Gemini keyframes → Gemini Omni interpolation → stitch → seam check, with a manifest of every request | `fludi-buddha-website/film/` | Reuse for all generated footage. It already solves shot-to-shot continuity. |
| Draft "liquid" film: 17 clips, 3,182 frames, 14 posters | Was in `film/out/` and `web/public/film/` | **Discarded on 10 November 2026** for a completely fresh take. Nothing from it is reused. The files were moved to `film/discarded-2026-11-10/` (191 MB, git-ignored), which can be deleted at any time. Until new frames exist, the old pages that used the posters show empty image areas. |
| FluidBuddha logos (gold, white, black, horizontal) | `fludi-buddha-website/brand/logo/` | Use as is. (I said earlier that no FluidBuddha logo existed. That was wrong: I had only looked in the design system folder.) |
| Paper and ink themes | `web/src/components/Theme.tsx`, design system `data-theme="light"` | Becomes one of the per-world settings. |
| A `GEMINI_API_KEY` file | `fludi-buddha-website/.env` (git-ignored) | Checked on 10 November 2026: the key works. It lists four image models and one video model, `gemini-omni-flash-preview`. **No Veo model appears in the list for this key**, so the plan uses Omni until Veo shows up (see §14). |

Known pipeline limits from its README: clips are 3–10 seconds each; generated video cannot
render text, so all words are HTML; 9:16 mobile versions are not made yet; the preview video
model ID is due for retirement.

---

## 3. How the site works: four worlds and a morph

### 3.1 URLs

| World | URL | Indexed by search engines |
|---|---|---|
| 0 Default | `/` | Yes |
| 1 B2B SaaS | `/for/saas` | Yes |
| 2 Education | `/for/education` | Yes |
| 3 Regulated enterprise | `/for/enterprise` | Yes |

Each world is a real page with its own URL. A morph is an animated move from `/` to a world
URL. This keeps links shareable, keeps the back button working and gives search engines one
clean page per world. Search engines and AI agents always get the page at the URL they asked
for, with no morph.

Hindi is a showcase, not a full translation: about one page in ten, in every world (§3.5).

### 3.2 How we identify the visitor

Checked in this order. The first confident match wins.

| Step | Signal | Example | Result |
|---|---|---|---|
| 1 | Link parameter | `?for=education`, `utm_campaign=saas-*`, `utm_content=enterprise` | Land directly in that world. No morph needed. |
| 2 | Remembered choice | The visitor chose a world before (stored in the browser) | Default hero paints, then the site morphs. A chip says "Showing the SaaS version · Change". |
| 3 | Referrer and landing path | Arrived on `/industries/education` | Offer the world with a one-line prompt. Do not morph without a click. |
| 4 | Selector | "What do you do?" with three choices, in the hero and again in the film | Morph on click. |
| 5 | Conversation | The visitor tells the agent "I run admissions at a university" | The agent sets the persona. The site listens for the `fluidbuddha:set_persona` event and morphs (FR-NAV-04, FR-NAV-05). |

Rules:

- Never morph while the visitor is reading or typing. Morph only on a click, on a persona
  event from the agent, or straight after first paint for a remembered choice.
- Always show which version is on screen and a one-click way back. This is the site's own
  version of the product's "Why this?" control.
- No sensitive inference. We only use what the link or the visitor tells us.

### 3.3 The role layer inside a world

A world sets theme, film and structure. A **role** changes words only: the hero sub-line, the
order of proof sections, the main button and the questions in the FAQ.

| World | Roles (from ICPPersonas.md) | Default role |
|---|---|---|
| SaaS | Growth, Revenue leader, Sales team, Engineering | Growth |
| Education | Admissions, Institution leader, Marketing, Counsellor | Admissions |
| Regulated | Digital, Security, Compliance and legal, Brand and design system, Architecture, Business sponsor | Digital |

The role is chosen with a small row of chips under the hero ("I work in: Growth · Sales ·
Engineering · Leadership") or with `?role=`. Role copy is in §7 to §9.

### 3.4 The morph

The morph is the one moment where the site shows what "fluid" means, so it deserves its own
short film.

1. The current world's panels break into a cloud of small gold dots (the dots of the brand
   mark). This is drawn in code, so it works from any world to any other.
2. The page colours cross-fade to the new world's settings while the dots are in the air.
3. The dots settle into the new world's opening layout.
4. New copy fades in. Total about 1.6 seconds. With reduced motion it is a plain 300 ms
   cross-fade.

Words on screen during the morph: "Changing this site for SaaS teams." Then the chip.

### 3.5 Hindi, changed in front of the visitor

Hindi exists to show that the product speaks it, so the change itself is the demonstration.

| Item | Decision |
|---|---|
| How much | About 10 % of pages. In each world: the world's home page (hero, film chapters, the "talk to it" section) and one more page (Pricing for default and SaaS, Privacy for Education, Controls for Regulated). |
| How it switches | A `हिंदी` button in the nav on those pages only. No reload. |
| The change | Text blocks change one after another from top to bottom. Each block fades its English out and its Hindi in, word by word, over about 0.6 seconds, with 0.25 seconds between blocks. A full screen takes 3 to 4 seconds. The film keeps playing underneath. |
| Layout | Each block reserves the taller of its two heights before it changes, so nothing jumps. Devanagari uses a matched font and slightly larger line height. |
| After the change | The URL becomes `/hi/…` so the page can be shared. The agent greets in Hindi. A small note says "Showing Hindi · English". |
| Other pages | The button is not shown. A page with no Hindi never pretends to have it. |
| Reduced motion | One 300 ms cross-fade of the whole page. |
| Quality | All Hindi copy is reviewed by a native reader before launch. |

---

## 4. Design: one system, four settings

All four worlds use the same tokens from `colors_and_type.css`: gold, warm black, warm white,
Space Grotesk, Hanken Grotesk, JetBrains Mono, Roblox for the logotype. No new colours. What
changes is which tokens are used and how.

| Setting | 0 Default | 1 SaaS | 2 Education | 3 Regulated |
|---|---|---|---|---|
| Mode | Ink: the brand's own warm black and gold | Ink, as a terminal: grid lines, no glow | Paper (light) throughout | Paper, near-white, document-like |
| Material | Glass plates and cards floating over a full-screen film | Flat dark cells, mono data, character texture | Soft solid cards, very little glass | Flat. No glass, no glow. Hairline borders. |
| Corner radius | `--r-lg` 16 | `--r-md` 11 | `--r-xl` 22 | `--r-xs` 4 |
| Density | Airy | Compact | Airy, large type | Structured grid, medium |
| Heading face | Space Grotesk | Space Grotesk, with JetBrains Mono for numbers and labels | Space Grotesk, larger, with Devanagari pairing | Space Grotesk, smaller, numbered sections |
| Gold use | Hero words, main button | Numbers, charts, active states | Warm glow, main button | Hairlines, approval marks only |
| Motion pace | Calm | Quick and precise | Slow and warm | Almost still. Things move once and stop. |
| Picture | Full screen, edge to edge, in every film chapter | Inside a framed stage | Full screen, edge to edge, in every film chapter; the page goes from night to morning | Inside framed figures |
| Film look | Thick amber glass slabs with etched gold detail over black water, streams of gold dots, shafts of light. Full screen, edge to edge. | Dark, code-drawn, character texture | Photoreal warm interior, night to morning | Flat technical drawing, isometric |
| Nav items | Product · Solutions · Pricing · Developers | Product · Proof · Pricing · Developers | How it works · Hindi · Pricing · Privacy | Deployment · Security · Governance · Pilot |
| Main button | Start free | Try it on your site | See it in Hindi | Plan a pilot |

Implementation: `data-world="saas|education|enterprise"` on `<html>` next to the existing
`data-theme`. Each world is a small block of token overrides. This is the same idea as the
product's own persona re-theming (`data-fb-persona`).

Design system rules that apply to every world: sentence case, no emoji, no invented numbers,
focus rings kept, reduced motion and reduced transparency respected.

---

## 5. Film language and techniques

### 5.1 The shared language

Every film uses the same four objects, so a visitor who sees two worlds recognises them.

| Object | Meaning | Always shown as |
|---|---|---|
| **Panels** | The customer's website | Seven floating rectangles in a page layout (nav, hero, side, three cards, button), using the existing layout masks |
| **Light** | The visitor | One small warm point of light that moves like a cursor |
| **Gold line** | An answer and its source | A line drawn from the answer back to the panel it came from |
| **Card** | Something handed over: a lead, a booking, a summary | A small panel that leaves the layout and travels |

The words on screen always say plainly what is happening. The picture may be stylised; the
sentence is never a metaphor.

### 5.2 Which technique for which world

| World | Main technique | Why it fits | Supporting techniques |
|---|---|---|---|
| 0 Default | Gemini image keyframes + Gemini Omni (or Veo) interpolation, scrubbed by scroll | The broadest audience gets the most polished, photoreal film. The pipeline exists. | SVG line drawing on top for charts and source lines |
| 1 SaaS | Real-time 3D in code (Three.js panels) with a character (ASCII) render pass | Technical buyers. Sharp at any screen size, tiny download, numbers can be live. The character texture reads as "engineering". | SVG for diagrams; a short rendered clip for the Slack and call scene |
| 2 Education | Gemini keyframes + Veo or Omni, warm interior scenes | The story is human and emotional: night, home, family. Photoreal warmth carries that. | SVG fee table; Devanagari set in HTML |
| 3 Regulated | Flat motion graphics written entirely in code (SVG + GSAP timelines) | Gatekeepers distrust spectacle. A precise diagram that moves once is more credible, and it is deterministic. | None. Stillness is the point. |
| Morph | Gold dots drawn in code | Works between any two worlds; it is the "fluid" moment | Colour cross-fade in CSS |

### 5.3 How the two skill packs fit

| Pack | What it is | Where we use it | Where we do not |
|---|---|---|---|
| `iart-ai/web-animation-skills` | Nine instruction packs for coding agents: GSAP and ScrollTrigger, 60 fps rules, page transitions in Next.js, accessible motion, micro-interactions, glass, SVG animation, Lottie, ASCII animation | The SaaS film (ASCII and GSAP), the Regulated film (SVG and GSAP), the morph (page transition), all hover and reveal details, the reduced-motion tiers | — |
| `Ar9av/framesmith` | Templates that turn a JSON brief into an MP4 with Python and ffmpeg (product promos, explainers, kinetic type) | Short loops inside sections, social and link-preview videos, a 20-second trailer per world | Not for the main scroll films: its templates are fixed promo layouts, and it outputs a finished MP4, not a scrubbable scene matched to our panel layout. Its image step uses an OpenAI key, which is optional. |

| `greensock/gsap-skills` | The official GSAP skills: core, timeline, ScrollTrigger, plugins, utilities, React, performance, frameworks | Every code-driven scroll scene, the Hindi text change (SplitText), the morph | — |

**Installed on 10 November 2026** into `.claude/skills/` after reading the code: all nine
web-animation skills (commit `b6dba3e`), all eight GSAP skills (commit `aed9cfd`) and four
framesmith skills (`framesmith`, `no-ai-slop`, `glass-saas-promo`, `keynote-product-film`,
commit `5ac1d90`). None has install hooks. Framesmith's scripts call ffmpeg, and reach
OpenAI only if an `OPENAI_API_KEY` is set, plus public icon hosts. The other thirteen
framesmith templates were left out to keep the repository small (the full pack is 182 MB);
any of them can be added later. An older copy of the GSAP skills already sits in
`skills/.agents/skills/` and was left untouched.

### 5.4 Film budgets (targets, to be checked in the prototype)

| Item | Target |
|---|---|
| Length per world | 8 to 9 scenes, 45 to 60 seconds of footage, about 9 to 11 screens of scrolling |
| Rendered films (worlds 0 and 2) | 1080p master, 720p delivery, about 1,100 to 1,400 frames at 24 fps |
| First load | Poster frame plus every 32nd frame, under 1.5 MB before the hero is usable |
| Total per rendered film | Under 25 MB on desktop, under 10 MB on mobile (9:16, every second frame) |
| Code films (worlds 1 and 3) | Under 400 kB of script each, loaded only in that world |
| Other worlds | Not downloaded until the visitor morphs |
| Reduced motion | One still per scene, copy fully readable, no scrubbing |

The existing draft is 51 MB at 360p for 3,182 frames. Four films at that length would be too
heavy, which is why each new film is under half as long.

---

## 6. World 0: the default site

**Who it is for.** Anyone we cannot identify yet, including all ICPs without their own world.

**One-line message.** Your website can talk to visitors, answer from your own content, and
change its pages to fit each visitor.

**Hero.** Eyebrow: `FLUIDBUDDHA`. Headline: "Your website can **answer every visitor.**"
Sub-line: "It answers by voice or text, using only what your site says. It shows charts and
prices, takes people to the right page and books the meeting." Buttons: **Start free** ·
Watch how it works. Under the buttons: "What do you do? SaaS · Education · Bank or insurer".

### Film storyboard

| # | What you see | Words on screen | Maps to |
|---|---|---|---|
| D1 | A website as seven glass panels, still, on a white studio floor. | "This is your website. Today it waits to be read." | — |
| D2 | A small warm light arrives and stops at the pricing panel. The panels turn slightly towards it. | "A visitor has a question." | Pillar 1 |
| D3 | One panel lifts forward and pulses with a voice wave. A gold line runs back to the two panels the answer came from. | "It answers out loud, from your own pages, and shows the source." | Pillars 1, 4 |
| D4 | The lifted panel unfolds into a bar chart, then a table, then a slider. | "It draws charts, tables and calculators while it talks." | Pillar 2 |
| D5 | The camera glides to a second group of panels. A ring lights one section. | "It takes the visitor to the right page." | Pillar 3 |
| D6 | A card slides out with a tick. A second card flies off-screen to the right. | "It books the meeting after the visitor says yes. Your team gets the lead." | Pillar 5 |
| D7 | The same seven panels rearrange three times into three different layouts, one for each of three lights. | "The page changes to fit each visitor, using only parts you approved." | Pillar 8 |
| D8 | The panels gather into three stacks. | "Tell us what you do. This site will change for you." (the selector) | Morph |
| D9 | Ten lights; one is dimmed. Two lines of a chart separate. | "One visitor in ten never sees it. The difference is your extra sales." Note: "Example chart." | Pillar 6 |

The whole film is in the ink theme. The gold light grows from one point in D2 to a warm glow by D9.

### Sections after the film

1. **Talk to it.** The live ask bar already built: "This site runs on FluidBuddha. Ask it anything."
2. **What it does**, six plain cards: Talks · Shows · Takes them there · Only your content · Books and sells · Proves it.
3. **It fits each visitor:** "Your pages change for each visitor" with a three-state before/after of one page.
4. **Who it is for:** three large doors (the worlds) and five small links (other industries).
5. **How to start:** "Add one line of code. It reads your site. It starts answering."
6. **Pricing strip:** Free 100 conversations · Growth ₹33,000 · Scale ₹1,25,000 · Enterprise.
7. **We use it ourselves:** see "Proof" below.
8. **Honest limits:** English and Hindi only; websites only; it says when it does not know.
9. **Start free.**

### Proof (all worlds)

FluidBuddha is launching, so there are no customers to quote and the sites show none. Proof
comes from three places, in this order:

1. **This site.** Every world page runs the agent. "Talk to it" is the first proof.
2. **Our own websites.** After launch the product goes onto buddhalab.in, hirebuddha.in and
   chantingbuddha.in. The section "We use it ourselves" lists a site only once the agent is
   live on it, with a link. Until then the section reads "Launching on our own sites first"
   with no claims.
3. **Our own measured results.** Once a holdout on one of those sites reaches a verdict, we
   publish the lift, its interval and the cost per conversation. Until then every number on
   the site is marked as an example.

No invented logos, quotes or customer counts, anywhere.

---

## 7. World 1: B2B SaaS

**Who it is for.** ICP-1. Lead reader: the Growth Owner (persona 1.1).

**One-line message.** Buyers read your pricing page at night and leave with questions.
FluidBuddha answers them and sends your team the lead.

**Hero.** Eyebrow: `FOR B2B SAAS`. Headline: "Your pricing page gets the traffic. **Now it
answers the questions.**" Sub-line by role:

| Role | Sub-line | Main button |
|---|---|---|
| Growth | "More qualified demos from the visitors you already have, with a built-in test that shows the lift." | Try it on your site |
| Revenue leader | "One more deal a quarter can pay for a year. The product measures whether you are on track." (example arithmetic shown below the fold) | See the business case |
| Sales team | "It handles the first six questions. Your first call starts at the seventh." | See a scored lead |
| Engineering | "One script tag, about 38.6 kB, isolated from your CSS and JavaScript." | Read the install guide |

### Film storyboard (dark, code-drawn, character texture)

| # | What you see | Words on screen | Maps to |
|---|---|---|---|
| S1 | The panels at night, drawn in fine gold characters. One light on the pricing panel. A clock reads 23:04. | "11 pm. A buyer is on your pricing page with three questions." | UC-01 |
| S2 | Three markers appear on three panels. | "Does it work with our ERP? What do 40 seats cost? Where is our data kept?" | UC-01 |
| S3 | Characters flow into a node-and-arrow diagram. | "It draws how the integration works." | FR-CMP-01 |
| S4 | A slider moves from 40 to 60. A rupee figure counts up. | "It works out the price for their team, from your price list." Note: "Example figures." | UC-05, FR-CMP-05 |
| S5 | The camera travels to the security panel. A ring lights one paragraph. | "It opens your security page at the right paragraph." | FR-NAV-01 |
| S6 | A card forms: a score, three reasons, a short summary. It drops into a Slack-shaped tray. | "Your team gets the lead, with a score and what was asked." | FR-SCORE-01, FR-DEL-02 |
| S7 | A second light joins the first. A call ring appears. | "A salesperson can join the conversation, or call the visitor in the browser." | UC-02 |
| S8 | The answer panel copies itself to four small lights. | "The buyer forwards a summary to their team. You see how far it travels." | UC-04 |
| S9 | Ten lights, one dimmed; two chart lines with a shaded band. | "One visitor in ten never sees it. The difference is your lift, safe to check every day." Note: "Example chart." | UC-09 |

### Sections after the film

1. **Try it on your own site:** enter a URL (the sandbox form already built).
2. **The six questions:** a list of real pre-sales questions with the kind of answer each gets.
3. **The lead your team receives:** one annotated lead card.
4. **Prove it:** how the holdout works, in four steps. No lift figure promised.
5. **What it costs per conversation:** ₹16.50 on Growth, compared with the visitor's own cost per click (calculator already built).
6. **Install:** script tag, WordPress, GTM, React, Vue, Next.js. Size and isolation facts.
7. **Honest limits:** English and Hindi only; no native CRM connectors (signed webhook, Zapier, Make, Slack); answers are grounded with sources, which is a guardrail and not a guarantee.
8. **FAQ**, ordered by role.

**Do not say:** "zero hallucinations", "guaranteed pipeline", any lift percentage, "replaces
your sales team".

---

## 8. World 2: Education

**Who it is for.** ICP-2. Lead reader: the Admissions Head (persona 2.1).

**One-line message.** Students ask at night, in Hindi or English. Your website answers them,
takes the application fee and gives them a summary to show their parents.

**Hero.** Eyebrow: `FOR UNIVERSITIES AND EDTECH`. Headline: "Your counsellors go home at six.
**Your website can keep answering.**" Language switch in the hero: English · हिंदी.

| Role | Sub-line | Main button |
|---|---|---|
| Admissions | "Every enquiry answered at once, in Hindi or English, from your own fee and programme pages." | See it in Hindi |
| Institution leader | "More of the students who already found you finish the application. Student details are masked before the AI sees them." | Read about privacy |
| Marketing | "See what prospects ask that your site does not answer. Works on WordPress." | See the weekly report |
| Counsellor | "You start each call knowing what the student asked." | See a lead summary |

### Film storyboard (light, warm, photoreal, with people)

This is the only film with people in it. Three characters: a **student** (about 19), a
**parent**, and a **counsellor**. To keep them natural and consistent:

- One approved reference image per character, used as a reference in every keyframe they appear in.
- People are framed from behind, in profile or at mid-distance. No close-up of a talking face, and no lip movement to match.
- Every shot with a person is 3 to 5 seconds, with small movements only (a hand, a head turn, leaning in).
- Each character shot has a version without the person as a fallback, so one bad shot never blocks the film.

| # | What you see | Words on screen | Maps to |
|---|---|---|---|
| E1 | A bedroom at night. The student sits at a desk, seen from behind, lit by a phone and a desk lamp. The phone shows the seven panels in miniature. | "11 pm. A student is on your website. Your counsellors are at home." | UC-14 |
| E2 | Over the student's shoulder: they lift the phone and speak to it. A voice wave. One panel answers. | "फ़ीस कितनी है?" then "They ask in Hindi. It answers in Hindi, from your English pages." | UC-11 |
| E3 | Three panels line up as columns of a comparison table. A slider moves and one column changes. | "It compares programmes and fees, and shows what a scholarship changes." Note: "Example figures." | FR-CMP-01 |
| E4 | The camera glides across three panel groups, pausing at each. | "It walks them through your programmes." | FR-TOUR-01 |
| E5 | A confirm card with a tick. | "They say 'haan'. It sends the application-fee link. The amount comes from your fee list, never from the AI." | UC-03, FR-ACT-06 |
| E6 | The answer panel folds into a card and leaves the phone. Cut to a living room: the parent, in profile, reads the same card on their own phone. The student stands beside them. | "The student sends a summary to their parents." | UC-04 |
| E7 | Morning light in an admissions office. The counsellor, at mid-distance, sits down with a cup of tea as a card arrives on the screen. | "9 am. Your counsellor has the lead and knows what was asked." | FR-SCORE-02 |
| E8 | A wall calendar with one month ringed in gold. | "Start before admission season." | Seasonality |

### Sections after the film

1. **Try it in Hindi:** the ask bar with Hindi starter questions.
2. **What a student can do in one visit:** ask · compare · pay the application fee · share with family.
3. **What parents see:** the recap page, shown as a phone screenshot. It works without scripts.
4. **What your counsellor receives:** one lead with score and summary.
5. **Wrong fee information:** how pinned answers and the fee list prevent it, stated as a control and not a guarantee.
6. **Student privacy:** masking, microphone consent, retention, deletion on request. Plainly: names and addresses are not masked; review your policy on minors with your own counsel.
7. **Example return:** one extra enrolment at ₹2,00,000 covers Growth for about six months. Marked as an example.
8. **Honest limits:** English and Hindi only (no Tamil, Telugu, Marathi yet); it is a website agent, not WhatsApp.

**Do not say:** "replaces counsellors", "guarantees admissions".

---

## 9. World 3: Regulated enterprise

**Who it is for.** ICP-7. Lead reader: the Digital Head (persona 7.1), with gatekeepers
reading over their shoulder.

**One-line message.** An AI website agent that runs on your servers, uses your model contract
and builds pages only from components you approved.

**Hero.** Eyebrow: `FOR BANKS, INSURERS AND FINTECHS`. Headline: "AI on your website, **inside
your rules.**" Sub-line by role:

| Role | Sub-line | Main button |
|---|---|---|
| Digital | "Your teams decide what AI may build with, what it may say and where it may not go." | Plan a pilot |
| Security | "Here is exactly where data goes, including the parts that still leave your network." | See the data flow |
| Compliance and legal | "You write the rules. The product enforces them and shows you what it did." | See the controls |
| Brand and design system | "Your components are the only building blocks the AI has. It never writes HTML or CSS." | See how components are approved |
| Architecture | "It starts on one Linux host, and falls back to your own page if it is slow or down." | Read the deployment guide |
| Business sponsor | "A 90-day pilot on one product area, with your compliance team reviewing from day one." | Plan a pilot |

### Film storyboard (flat, isometric, drawn in code; each scene moves once and stops)

| # | What you see | Words on screen | Maps to |
|---|---|---|---|
| R1 | A boundary line draws itself around the seven panels. | "It runs on your own infrastructure." | UC-17 |
| R2 | Two plugs connect at the boundary: one labelled model, one labelled sign-in. | "It uses your model contract and your sign-in system." | FR-BYO, FR-SSO |
| R3 | One thin line crosses the boundary and is labelled. | "One thing still leaves: speech and search indexing run on Google Vertex AI. We tell you first." | FR-BYO-06 |
| R4 | A shelf of blocks. A person-shaped marker stamps some of them. Only stamped blocks move to the workbench. | "An admin approves every component the AI may use." | UC-22 |
| R5 | Blocks pass through a gate one by one. One is turned away and fades. | "The AI chooses and fills components. Every page passes the same check before anyone sees it." | FR-PLAN-02 |
| R6 | A pipe from a box labelled "your systems" fills the price slot of a block. | "Prices and rates come from your systems, never from the AI." | FR-MAN-03 |
| R7 | Three routes are fenced off. One notice block locks to the top of every page. | "Checkout, legal and privacy pages are off limits. Your required notices appear on every page." | FR-G3-01, FR-G3-08 |
| R8 | A list builds line by line; a few lines are flagged. | "Every console change is logged. Generated pages go to a review queue." | FR-AUD-01, FR-G3-10 |
| R9 | One panel is highlighted; a 90-day bar fills. | "Start with one page and a measured pilot." | Persona 7.6 |

### Sections after the film

1. **Three limits, stated first:** speech and embeddings on Google Vertex AI; the generative page builders have been verified with test models, so we offer a pilot; pages cannot yet show a signed-in customer's own data.
2. **Data flow diagram:** what stays inside, what leaves.
3. **Controls:** approved components · source rules · site rules and blocked questions · blocked routes · pinned notices · budgets · review queue · audit log.
4. **Deployment:** one host, Docker Compose, backups, offline licence, upgrade path.
5. **Security documents:** control matrix, policies, sub-processor list, DPA template. Labelled as drafts. No certification claimed.
6. **What the visitor can see and change:** "Why this?" and the preferences panel. Prices are never personalised.
7. **The pilot:** scope, who reviews, how it is measured.
8. **FAQ**, ordered by role.

**Do not say:** "SOC 2 certified", "compliant", "regulator-approved", any named regulation,
any price.

---

## 10. Production pipeline

### 10.1 Rendered films (worlds 0 and 2, and the morph)

| Step | Tool | Output | Check before moving on |
|---|---|---|---|
| 1. Storyboard sign-off | This document | Approved scene tables | You approve words and pictures |
| 2. Style frames | Gemini image model | 3 keyframes per world | You approve the look. Cheap to redo. |
| 3. Layout masks | `film/pipeline.py masks` | One mask per panel layout, 16:9 and 9:16 | HTML copy fits the empty area |
| 4. Keyframes | `pipeline.py keyframes` | One image per join between scenes, each using the previous as reference | Continuity by eye |
| 5. Draft clips | `pipeline.py clips --res 360p` (Gemini Omni; Veo as second choice) | 3–10 s per shot | Motion reads; no flicker or zoom drift |
| 6. Preview | `film/preview.html` | Scroll-scrubbed draft with real copy | You approve the draft film |
| 7. Final clips | `--res 1080p`, both aspects | Master clips | Seam score under the threshold at every join |
| 8. Stitch and export | `pipeline.py stitch` | Frames or per-chapter MP4s within the budgets in §5.4 | File sizes |

Changes needed in the pipeline: one shot file per world (`shots_default.py`,
`shots_education.py`, `shots_morph.py`), a `--world` flag, Veo as an alternative model, and
the 9:16 run.

### 10.2 Code films (worlds 1 and 3)

| Step | Output |
|---|---|
| 1. Scene script | A timeline file per world: scene, start, end, what each object does |
| 2. Still pass | One static frame per scene, reviewed as a contact sheet |
| 3. Motion pass | A GSAP timeline driven by scroll position; Three.js with a character render pass for SaaS, SVG for Regulated |
| 4. Performance pass | 60 fps on a mid-range laptop; pauses when off-screen |
| 5. Fallback | The stills from step 2 are the reduced-motion and no-WebGL version |

### 10.3 Supporting clips

A 20-second trailer per world and the link-preview images, made with framesmith templates or
by rendering the code films to video. These come last.

---

## 11. Technical build

| Area | Change |
|---|---|
| World system | `data-world` on `<html>`; a token block per world in `globals.css`; a `World` component like today's `Theme`. |
| Content model | `src/content/worlds/{default,saas,education,enterprise}.ts`: hero, role variants, chapters, sections, nav, buttons. `home.ts` moves into `default.ts`. |
| Routes | `/for/[world]` plus Hindi equivalents. Existing `/industries/*` pages stay and link into the nearest world. |
| Film player | `FilmPlayer` takes a `film` source: `frames` (today's canvas scrubber) or `scene` (a code film with the same progress input). Chapters stay unchanged. |
| Identification | A small client module that reads link parameters, remembered choice and referrer, and listens for `fluidbuddha:set_persona`. One function: `resolveWorld()`. |
| Morph | Route transition with the morph clip and a token cross-fade. Plain cross-fade under reduced motion. |
| Selector and chip | "What do you do?" in the hero and at scene D8; the "Showing the … version · Change" chip in the nav. |
| Role layer | Chips under the hero; `?role=`; copy looked up from the world's content file. |
| Agent | The site's own agent profile gets three personas matching the worlds, so a conversation can trigger a morph. |
| Measurement | Events: world shown, how it was identified, morph completed, switch back, main button clicked. Later, a holdout of "no morph" against "morph". |
| Search | Each world page has its own title, description and canonical URL. Link parameters never create indexable duplicates. |
| Accessibility | All copy is HTML and readable without the film. Keyboard access to chapters, selector and chips. Contrast checked in every world. |

The site uses Next.js 16, which differs from older versions. Its own `AGENTS.md` says to read
the bundled docs before writing code, and I will.

---

## 12. Phases, deliverables and acceptance

| Phase | Work | Deliverable | Done when |
|---|---|---|---|
| 0. Set-up | Confirm the API key and which video models it can use. Review the two skill packs and install with your approval. Create a branch. | A short set-up note | A test keyframe and a test 3-second clip render |
| 1. Words | Final copy for all four worlds: hero, role variants, chapters, sections, FAQ. English first. | `docs/marketing-docs/website/copy-{world}.md` | You approve the copy |
| 2. Look | Three style frames per world, plus one HTML page per world showing the settings in §4 with real copy and no film. | Four static pages and twelve images | You approve each world's look |
| 3. Platform | World system, routes, content model, identification, selector, chip, role layer, generalised film player. Uses stills in place of films. | All four worlds navigable with stills | Morph works by link, selector, remembered choice and agent event |
| 4. Default film | Pipeline steps 3 to 8 for world 0. Sections after the film. | World 0 complete on desktop | Film within budget; all copy approved |
| 5. SaaS | Code film and sections. | World 1 complete | 60 fps; fallback stills work |
| 6. Education | Rendered film with people, sections. | World 2 complete | Every character shot approved or replaced by its fallback |
| 7. Regulated | Code film and sections. | World 3 complete | Every claim checked against §9 "do not say" |
| 8. Morph, Hindi and polish | Morph clip, the Hindi showcase pages and the runtime text change (§3.5), 9:16 films, reduced motion, performance, search tags, measurement events. | Release candidate | Budgets in §5.4 met on a mid-range phone; Hindi reviewed by a native reader |
| 9. Review | Claims check against UseCases.md §10, accessibility check, cross-browser check. | Checklist with results | No open blocker |

**Status on 10 November 2026.** Phases 0, 1 and 2 are done and waiting for review. Phase 2
lives in `fludi-buddha-website/look/`: `index.html` shows the four looks side by side, and
each world has its own page with final-draft copy and three film style frames. The frames for
the default and Education worlds were generated with `film/styleframes.py`
(`gemini-3-pro-image`, thirteen image requests in total, including a second, richer round for the default world after review); the SaaS and Enterprise frames are
drawn in code. To view: start the `website-assets` server and open
`http://localhost:5190/look/`.

**Phase 3 status (10 November 2026).** Built and verified in `fludi-buddha-website/web/`.

- Routes: `/` (default) and the fixed routes `/for/saas`, `/for/education`, `/for/enterprise`, each with its own canonical URL. They are fixed routes, not `/for/[world]`, so a morph is an instant navigation.
- The earlier pages (pricing, demo, industries, legal, Hindi) moved to the `(site)` route group and keep their old chrome. The worlds are in the `(worlds)` group.
- Content: `src/content/worlds/`. Components: `src/components/world/`. Logic: `src/lib/world.ts`. Styles: `src/app/(worlds)/worlds.css` (generated from the look pages) and `worlds-app.css`.
- Identification, checked in the browser: link (`?for=`, `utm_campaign`, `utm_content`), remembered choice, referrer offer, selector and doors, the nav chip, and the agent's `fluidbuddha:set_persona` event. Roles: chips and `?role=`.
- The film is stills and code-drawn scenes for now. Scroll-scrubbed footage arrives in phases 4 and 6; the `Film` type in `src/content/worlds/types.ts` already separates the picture from the chapters.
- Not in this phase: the full section list of each copy document (phases 4 to 7), Hindi switching (phase 8), 9:16 stills, and a real measurement destination (events are pushed to `window.dataLayer` when one exists).

**Phase 4 final render (11 November 2026).** The draft was approved and the film re-rendered at 1080p (nine clip requests: eight shots plus one re-render of S4, whose first frame had drifted from its keyframe). Both draft flaws are fixed in the prompts. All seven joins pass the seam check (1.4 to 2.7). The site plays 700 frames at 12 a second as WebP: 720p on desktop (23.6 MB) and 480p on screens under 768 px wide (11.1 MB, a little over the 10 MB target). The phone set is the same 16:9 film cropped to the screen, not a separate 9:16 render. The notes below describe the draft stage.

**Phase 4 status (11 November 2026) (draft stage).**

- The default film is storyboarded as 8 shots between 9 keyframes (`film/shots_default.py`), 58 seconds. Chapter D1 ("it waits to be read") is carried by the hero, so the film has eight chapters after it.
- Drafts were rendered at 360p with `gemini-omni-flash-preview` (the two newer Omni model IDs are not available on the key). All seven joins pass the seam check (1.6 to 3.2 against a limit of 4.0).
- The site plays it: `FilmScroll` scrubs 700 frames (12 a second, 14 MB) behind the hero and the chapters at `/`. With reduced motion it loads one frame per chapter.
- All sections of the default copy document are on the page. "Talk to it" links to the live demo page; the ask bar is not embedded in the new look yet.
- `film/pipeline.py` takes `--world <name>` (shots file and output folder per world), a `seed` step for approved style frames, and `--fps` for the stitch.
- Still to do for phase 4: your review of the draft; the 1080p render; 9:16 for phones; fixes for the two known flaws (a strip of dots at the left edge early in shot S2, and the slabs shifting position at the start of shot S1).

**Phase 5 status (11 November 2026) (built, waiting for review).**
- The SaaS film is drawn live in characters from the scroll position (`web/src/components/world/asciiFilm.ts`). It has nine scenes: 23:04, the three questions, the integration diagram, the price slider, the security page, the lead card, a salesperson joining, the summary, and the holdout chart. Nothing is downloaded for it, and it only moves when the visitor scrolls.
- The film player (`FilmScroll.tsx`) now plays both rendered films and code-drawn films. A link ending in `#<chapter id>` opens a film at that chapter.
- All sections of the SaaS copy document are on `/for/saas`: try it, the six questions, the lead card and install, prove it, cost, where data goes, limits, questions, close.
- Checked at 1440 px and at 390 px by capturing every scene. On desktop the picture sits to the right of the copy; on phones it sits above the copy. No sideways scrolling at either width.
- Not done: the FAQ is not ordered by role; reduced-motion handling for this film is left to phase 8; the film has not been watched in motion on a real phone.

**Phase 6, 1080p render (11 November 2026).** After approval of the draft, all eight shots were rendered at 1080p and stitched (561 frames, every seam passes). The page uses 1280 × 720 WebP frames (17 MB) and 854 × 480 on phones (9.8 MB). The last shot now only moves forward. The draft frames were removed. Still open from the list below: the phone model differs between the first two shots and the close-ups; no fallback shots without people were made.

**Phase 6 status (11 November 2026) (draft stage, since rendered at 1080p; see above).**
- The Education film is a rendered film with people: 8 shots, 44 seconds, 561 frames (`film/shots_education.py`). Scenes: the student's bedroom at night, a close-up of the phone (comparison, tour, fee confirmation), the living room with the parent, the admissions office with the counsellor, and a wall calendar. Four keyframes are the approved style frames; nine more were generated with them as references so the people stay the same.
- This is the 360p draft. It is on `/for/education` so the timing and copy can be judged. The full 1080p render comes after your review.
- `film/pipeline.py` gained three things: a per-world last line for clip prompts (this world allows people), scene cuts that the stitch turns into short cross-fades, and a "hold" that keeps a shot's last frame on screen for a set time.
- The film player keeps the subject in view when the picture is cropped at the sides, and on upright phones it can show the picture in the top part of the screen with the copy below it (used by this world). It also redraws when its size changes without a window resize event.
- All sections of the Education copy document are on the page: try it in Hindi, one visit, what parents see, what the counsellor receives, fees, privacy, example return, limits, questions, close.
- Known flaws in the draft: the last shot pushes in and then drifts back out; the phone in the close-ups is a different model from the one in the first two shots; the screen in the comparison shot shows a grid of blocks more than three clear columns.
- Not done: the versions of each people shot without a person (fallbacks) were not made because no people shot failed; the Hindi runtime switch is phase 8; "Talk to it" links to the live demo page.

**Phase 7 status (11 November 2026) (built, waiting for review).**
- The Enterprise film is drawn live as flat line drawings from the scroll position (`web/src/components/world/lineFilm.ts`): a still drawing behind the hero, then nine scenes (R1 to R9 of the storyboard). Each scene moves once, during the first part of its stretch, and then holds still. It uses the page's own colours and nothing is downloaded for it.
- The drawings are flat, not isometric, to match the approved Enterprise look.
- The hero is now part of the film (copy on the left, drawing on the right) instead of a separate split block.
- All sections of the Enterprise copy document are on `/for/enterprise`: limits, where data goes, controls, deployment, access and security, security documents, visitors, the pilot, questions, close. The nav links go to these sections.
- Checked at 1440 px and 390 px by capturing every scene. On phones the drawing sits above the copy and its labels are set larger.
- Not done: the FAQ is not ordered by role; "Get the security documents" links to the demo booking page because there is no documents page yet; reduced motion is phase 8.

**Phase 8 status (11 November 2026) (partly done, waiting for review).**
- **Hindi, changed in front of the visitor.** Each world page has a `हिंदी` button in the nav (Education also has the switch in its hero). Pressing it changes the blocks that have reviewed Hindi, one after another from the top of the screen, word by word, without a reload. The link becomes `?lang=hi` and can be shared; the button then reads "Showing Hindi · English". Code: `web/src/lib/lang.ts`, Hindi text in each world's content file under `hi`.
- Only the Hindi lines in the four copy documents are used. Everything else stays in English, so a Hindi page mixes Hindi headlines with English body text. To make the showcase fully Hindi, these still need reviewed Hindi: chapter body lines, eyebrows, role chips, the chapters without a Hindi line (default D8; SaaS S2, S5, S7, S8; Education E4, E8; Enterprise R2, R5, R7, R8), and the "talk to it" sections of the three persona worlds.
- Differences from §3.5: the shared link is `?lang=hi`, not `/hi/…` (the old `/hi` pages still exist at that address); the second Hindi page per world is only done for Education (two privacy lines), because the copy documents hold no Hindi for Pricing or Controls; the agent greeting is not changed.
- **Reduced motion.** Drawn films (SaaS, Enterprise) no longer move with the scroll: they step from one finished picture to the next. Rendered films already load one frame per chapter. The Hindi change becomes one short cross-fade. The morph was already a 300 ms cross-fade. Not tested with the system setting switched on.
- **Phones.** The default film now uses the same upright layout as Education: picture in the top part of the screen, copy below. True 9:16 renders of the two rendered films were not made (about 16 video requests and new keyframes).
- **Performance.** On a slow or data-saving connection a rendered film loads a quarter of its frames. Film sizes: default 25 MB (720p) and 13 MB (480p); Education 17 MB and 9.8 MB. Not measured on a mid-range phone, so the §5.4 budgets are not confirmed.
- **Search.** `sitemap.xml` lists the four world pages and `robots.txt` points to it. Each world already had its own title, description and canonical URL; link parameters do not create listed duplicates.
- **Measurement.** New events through `track()`: `lang_switched`, `film_chapter` (first time each chapter is reached) and `cta_clicked` for every main button, with the world and where on the page. They are pushed to `window.dataLayer` when one exists; no measurement destination is connected.
- **Morph.** Unchanged in this phase.
- Also fixed: the Hindi typeface was named in the styles but not actually applied; it is now.

**Phase 9 status (11 November 2026) (review done on Chromium only).** Results are in [website/review-checklist.md](website/review-checklist.md). Claims: all rules pass; six approved copy lines are listed for a decision and none was changed. Accessibility: contrast, keyboard focus in hidden film slides, one heading level and small click targets were fixed; the deeper gold for text on light pages slightly changes the Education look. Cross-browser: Firefox, Safari and real phones were not tested and remain open.

**Redesign (11 November 2026).** After review the site was audited and redesigned: one header and
footer for every page, the whole site taking the visitor's version, the older pages rebuilt on the
same system (their broken posters replaced by film frames), duplicate pages redirected, and a
signature moment per world. §4's "no new colours" is relaxed: each world now has its own ground,
with the brand gold as the common thread. Findings, decisions and what is still open:
[website/audit-2026-11-11.md](website/audit-2026-11-11.md).

Phases 5, 6 and 7 do not depend on each other and can run in parallel once phase 3 is done.
Phase 2 is the cheapest place to change direction, so it is where your review matters most.

---

## 13. Risks

| Risk | Effect | What we do |
|---|---|---|
| Generated video drifts, flickers or changes framing between shots | Seams show while scrubbing | Keyframe at every join, short clips, mid keyframes where needed, seam check. Already proven in the draft. |
| Generated video cannot show text or exact layouts | Panels do not line up with HTML | Layout masks as references; all words in HTML; code-drawn overlays for charts |
| Four films are too heavy | Slow first load, poor mobile experience | Shorter films, two worlds in code, other worlds loaded only on morph, budgets tested in phase 4 |
| The preview video model is retired | Pipeline stops | Add Veo and the newer Omni IDs as alternatives in phase 0 |
| Four worlds look like one site with different words | Directive 1 is not met | Phase 2 static pages are judged side by side before any film is made |
| A morph surprises or annoys the visitor | Bounce | Morph only on a click, an agent event or a remembered choice; always show the chip and a way back |
| Copy overclaims | Fails a security or legal review | Each world has a "do not say" list; phase 9 claims check |
| No customer proof exists yet | Proof sections look thin | The live agent on this site, then our own three websites, then our own measured results (§6 "Proof"). No invented logos, quotes or results. |
| People in the Education film look unnatural or change between shots | The film loses trust with the audience that most needs it | Reference image per character, framing from behind or in profile, short shots, a no-person fallback for every character shot (§8) |
| Veo is not available on the key | Fewer options for shots with people | Use Omni first; test one person shot in phase 2 before committing to the Education storyboard |
| Third-party skill packs contain code we have not read | Supply-chain risk | Read before install; install only with your approval |

---

## 14. Your answers and what is still open

Answered on 10 November 2026:

| Question | Your answer | Where it is in this plan |
|---|---|---|
| Gemini key | Valid, Veo enabled | §2. The key works, but see the open item below. |
| Skill packs | Install them, and the GSAP skill | §5.3. Installed. |
| Hindi | About 10 % of pages per world, changing from English to Hindi slowly at runtime | §3.5 |
| Proof | No customers yet. Our own sites after launch: buddhalab.in, hirebuddha.in, chantingbuddha.in | §6 "Proof" |
| People on screen | Yes, in the Education film only | §8 |

Still open:

1. **Veo.** The key's model list shows `gemini-omni-flash-preview` as its only video model.
   No Veo model is listed. Either Veo is enabled on a different Google Cloud project or key,
   or it is not switched on yet. Please check. Until then, generated footage uses Omni, which
   the existing pipeline already supports. I have not made any paid generation call.

Settled on 10 November 2026: ffmpeg is installed system-wide (winget, `Gyan.FFmpeg`); the
Hindi copy has been reviewed by the product owner; the old film outputs are discarded (§2).
