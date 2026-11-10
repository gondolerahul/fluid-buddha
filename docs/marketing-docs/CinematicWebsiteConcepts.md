# FluidBuddha — Cinematic Website: Creative Concepts

> **What this document is.** A creative brainstorm for the FluidBuddha marketing website. The
> goal is an award-level site (Awwwards Site of the Day / Year, FWA, Cannes Lions Digital Craft)
> built on real-time 3D, with the feel of a film, and partly **run by the product itself**. It
> offers **seven concepts** to choose from: six from the brainstorm below, and
> the client's own concept, *The Liquid Interface*, refined (Concept G). Once one is chosen, it will be developed into a full
> treatment, storyboard, styleframes and a technical plan.
>
> **How it was made.** Four creative teams each read the product documents in
> [`docs/product-docs/version_1.0/`](../product-docs/version_1.0/) and
> [UseCases.md](UseCases.md), then pitched three concepts through one lens each: *myth and
> heritage*, *film genre and story*, *interactive meta-experience* and *matter and physics*.
> That gave 12 concepts. An executive creative director then scored all 12, merged near-duplicates,
> carried the best ideas over from the rejected ones, and checked every concept against the
> product's real features and the claims rules in [UseCases.md §9](UseCases.md#9-claims-guidance-for-marketing).
> These six are the result. Concept G was added afterwards, from the client's own idea. It was
> refined, reviewed by the same creative director, and revised to address that review.
>
> **Mockups.** Interactive high-fidelity mockups of Concepts A (KOLAM), C (PLACES, PLEASE) and
> G (THE LIQUID INTERFACE) are in [`mockups/`](mockups/index.html). Each shows the hero and two key sections. Run
> them with a static server, for example `python -m http.server 5180 --directory docs/marketing-docs/mockups`,
> then open http://localhost:5180. C and G need WebGL; G needs WebGL2.
>
> **Status.** For selection. Every product behaviour named here exists in version 1.0 unless it
> is marked **[new]**. Items marked **[new]** are small additions the site would need (listed
> in [§11](#11-shared-engineering-prerequisites)).

---

## Contents

1. [The brief, as we read it](#1-the-brief-as-we-read-it)
2. [Rules every concept follows](#2-rules-every-concept-follows)
3. [The slate at a glance](#3-the-slate-at-a-glance)
4. [Concept A — KOLAM: First Light at the Threshold](#4-concept-a--kolam-first-light-at-the-threshold)
5. [Concept B — 11:58: The Night the Website Learned](#5-concept-b--1158-the-night-the-website-learned)
6. [Concept C — PLACES, PLEASE: The Site That Isn't There Yet](#6-concept-c--places-please-the-site-that-isnt-there-yet)
7. [Concept D — CAST: Wake Your Website](#7-concept-d--cast-wake-your-website)
8. [Concept E — ANECHOIC: The Room That Listens](#8-concept-e--anechoic-the-room-that-listens)
9. [Concept F — MOLTEN: Solid. Liquid. Gas. Light.](#9-concept-f--molten-solid-liquid-gas-light)
10. [Concept G — THE LIQUID INTERFACE: It Only Reflects What's Real](#10-concept-g--the-liquid-interface-it-only-reflects-whats-real)
11. [Shared engineering prerequisites](#11-shared-engineering-prerequisites)
12. [Scorecard and comparison](#12-scorecard-and-comparison)
13. [Ideas from the concepts that were not shortlisted](#13-ideas-from-the-concepts-that-were-not-shortlisted)
14. [Recommendation and next steps](#14-recommendation-and-next-steps)

---

## 1. The brief, as we read it

**The product, in one breath.** One `<script>` tag turns a business website into a live,
voice-first sales agent, Pragya (Sanskrit for *wisdom*). She **talks**: streamed speech, a
spoken acknowledgement in under a second, barge-in, English and Hindi. She **shows**: 13
typed generative components, drawn in sync with her speech. She **acts on the page**: she
navigates, scrolls, spotlights sections, re-themes the page for the visitor's segment and gives
narrated tours. She **never makes things up**: answers are grounded in the site's own content,
with sources, and she says "I don't know" below a confidence of 0.45. And she **turns traffic
into revenue**: leads, visitor-confirmed actions such as a spoken "haan", recap pages and live
human handoff. The product also **proves its own value** (holdout experiments with always-valid
statistics) and **gets cheaper as it learns** (answer and byte-exact audio replay).

**The five product truths that are hardest to show, and that a film can show best.**

| # | Truth | Why it is hard to sell with copy |
|---|---|---|
| 1 | *It talks, shows and acts at the same time.* | Everyone claims "AI chat". Doing all three at once only lands when people see it. |
| 2 | *It says when it doesn't know.* | "No hallucinations" claims are everywhere and nobody believes them. A shown refusal is believed. |
| 3 | *It hides latency.* An acknowledgement in under a second while the answer is composed. | It is invisible when it works. |
| 4 | *It gets cheaper as it learns.* Cache replay with identical audio. | Economics are abstract. |
| 5 | *It proves its own lift.* A holdout with an always-valid verdict. | Statistics are boring, unless they are drama. |

**What "out of the box" means here.** No glowing brains, no particle robots, no chat
bubbles, no neon "AI" aesthetic. Each concept is built on **one physical or cultural
metaphor** that maps onto the product feature by feature. The visitor does not watch a film
*about* the product. **The film is directed by the product.**

---

## 2. Rules every concept follows

These apply whichever concept is chosen. They are what makes the site a demonstration rather
than a showreel.

1. **Pragya directs the film.** The real widget runs on the site with the production key,
   usually at Design Level 3, *The Atmosphere*, so Three.js loads only once. The site registers
   `FluidBuddha.init({ onNavigate, onScrollTo, onSetPersona })`. Every `navigate`, `scroll_to` and
   persona switch the agent sends then becomes an **authored camera move** instead of a plain
   scroll.
2. **The guided tour is the film's director.** The film's scenes are authored as tour stops in
   the console's tour editor (6–9 stops). The SDK plays each stop's narration and moves only
   after the audio has finished, plus 450 ms. So **every camera cut lands on the end of a spoken
   line**, which is real product behaviour. Barge-in or a typed question pauses the film exactly
   where the visitor interrupted. **Note:** in version 1.0 the tour plays when the session opens,
   in place of the spoken welcome (FR-WEL-05). A visitor asking "give me the tour" halfway through
   gets the agent's own navigate-and-scroll answer, not the stored tour. Concepts that start a tour
   on request (A, C, D) need the "start tour on request" addition in [§11](#11-shared-engineering-prerequisites).
3. **Persona switching re-grades the whole film.** The widget sets `data-fb-persona` on
   `<html>` behind its 300 ms blurred cross-fade. The site maps that attribute to a 3D colour
   grade (LUT), materials, copy and which components Pragya prefers. A CFO, a CTO and a founder
   see three cuts of the same film.
4. **Story props are real components.** Diagrams, calculators and sankeys in the film are the
   SDK's own typed components (flowchart, roi_calculator, sankey, workflow and so on). Where the
   3D world shows a component, it is drawn from the same JSON, so the spectacle and the
   interactive panel cannot disagree.
5. **The Honest Dare.** Every concept includes one suggestion chip that invites an off-site
   question, so the confidence guardrail is *shown*, not claimed. (If that question is pinned
   as a curated answer, the site says so.)
6. **The Credits [new].** Every experience ends with a session receipt that lists only what
   actually happened in this visit: the acknowledgement time, each grounded answer with its
   match percentage, the components drawn, the page moves, any cache replays, the persona
   switch and any confirmed action. It is built from `fluidbuddha:*` events and grounding
   payloads, and it becomes the visitor's recap page. It proves nothing was faked, and it is
   something the visitor can forward.
7. **The Silent Film.** The site runs a real holdout (default 10 %). Visitors in the holdout get
   no widget (FR-WID-07), so they receive a complete, beautiful, agent-free cut of the same
   film. That cut is the control group. The site publishes its own live verdict and shows
   **"collecting"** until the result is real. Holdout visitors are never told mid-visit that
   they are the control.
8. **Visitors without a microphone get the same experience.** "Type instead" drives the same
   pipeline. Keystrokes animate the scene. Pragya's spoken output still drives the visuals,
   because output audio needs no microphone. Captions are on by default. With sound off, the
   film still works.
9. **Real numbers or none.** Every live figure (cache hit rate, "asked N times", holdout
   verdict) comes from real counters or a nightly export from the site's own console. ROI
   figures are always stamped **Illustrative**.
10. **Claims rules.** Say "grounded in our content, with sources", never "zero hallucinations".
    Say English and Hindi only. The agent acts through navigation, scrolling, spotlight and
    configured actions, never "clicks anything". Personalisation is by segment, language and
    page, never by "each individual".
11. **SEO and impatience.** Every scene is a real, server-rendered `<section id>` or route. That
    gives the crawler, the agent's `scroll_to` and the tour planner something real to land on.
    A discreet "Read instead" index is always available.
12. **Reduced motion, no WebGL and mobile** each get a designed version (still plates with
    cross-fades, an SVG or CSS version, and portrait-composed scenes with fewer particles and
    baked video) rather than a broken one.

---

## 3. The slate at a glance

| | Concept | One-line pitch | Core metaphor | Tone | Signature shot | Build effort | Best for |
|---|---|---|---|---|---|---|---|
| **A** | **KOLAM** | Pragya draws every answer as one unbroken line that can only loop around the dots of your own content. | The kolam drawn at an Indian doorstep every dawn: dots, then one line *around* them. | Serene, lyrical, warm | The line refuses to cross empty ground for an off-site question, then closes into the logo on "haan". | High | An ownable, India-first brand idea built to win on craft. |
| **B** | **11:58** | A time-loop thriller: the same buyer, the same pricing page, the same minute before midnight, until the website learns. | The time loop is the learning loop. | Tense, human, clever | Two replays of Pragya's answer lock together sample for sample: the byte-exact audio cache. | High | A story people retell, aimed at CFOs and CMOs (learning, cost, proof). |
| **C** | **PLACES, PLEASE** | There is no website here. Ask, and it is built: sections fly in from a theatre's fly tower on cue. | A black-box theatre: the stage manager, the prompt book and lighting cues. | Witty, theatrical | The camera cranes into the rigging to show every possible page hanging dark, then three light up and fly down. | Medium–high | The purest "the site *is* the product". |
| **D** | **CAST** | A cast court of silent plaster websites. Bring your own URL; watch it cast and woken, talking with your own sources. | A museum of plaster casts, and the waking. | Personal, surprising | The visitor's own site cracks out of plaster in full colour and speaks about their business. | Highest (backend) | Conversion and virality over awards. |
| **E** | **ANECHOIC** | The quietest page on the internet: 20,000 foam wedges that bow to your voice. | An anechoic chamber, a room that adds nothing. | Austere, minimal | The visitor interrupts and Pragya's gold wave is swallowed by the room mid-word. | Lowest | A bold, minimal piece that runs superbly on mobile, for a small team. |
| **F** | **MOLTEN** | Your website is a conversation that cooled too fast. The visitor's voice is heat. | Phase change: solid → liquid → gas → light = static site → the three design levels. | Epic, elemental | Saying "I'm the CTO" recrystallises the whole world from amber basalt to blue bismuth without a cut. | High | Maximum spectacle, the closest fit to the existing brand materials. |
| **G** | **THE LIQUID INTERFACE** *(client concept)* | One drop of liquid metal splashes and becomes the website. Answers pour into shape, and the metal can only shine with what it reflects: the site's own pages. | A liquid-metal product shoot whose light boxes are the site's pages. | Sleek, precise, cool | Asked something off-site, the metal finds nothing to reflect, turns dull grey and slumps. | Medium–high | The most direct visual for generative UI; a droplet icon that is also the install story. |

---

## 4. Concept A — KOLAM: First Light at the Threshold

> **Tagline:** *Every threshold deserves a welcome. Yours is drawn live, in voice.*
>
> **Logline:** Every dawn, across India, a hand draws a kolam on the doorstep to welcome
> whoever comes. Here the hand is a voice. Pragya draws each answer as one unbroken line that
> can only loop around the dots of your own content. Grounding, generative UI and the close of
> a sale become one continuous act of welcome.

### 4.1 The idea

A **kolam** is drawn every morning at the threshold of a home to greet guests. Its pan-Indian
cousin is rangoli. It is a household, mathematical and secular craft. First a grid of dots
(*pulli*) is laid. Then a single line weaves *around* the dots, never across empty ground. The
finest kind, the *sikku kolam*, is one closed, unbroken loop.

| In the kolam | In FluidBuddha |
|---|---|
| The threshold, where strangers arrive | The website |
| The dots (pulli) | The site's own knowledge chunks in the CORTEX tree |
| The line bends only around dots that exist | Grounded answers, only from site content, with sources |
| **No dots, no line** | The honest "I don't know" below 0.45 confidence |
| A fresh kolam every dawn | A page-aware welcome for every visitor |
| A pattern the hand remembers | Answer and byte-exact audio cache |
| **Closing the loop** | The visitor-confirmed action ("haan") |
| "Buddha", the awakened, at dawn | The widget's existing Level 2 "Awaken" ring |
| Pragya (wisdom), the knowing hand | The agent |

### 4.2 Storyline (six acts and a coda)

| Act | What the visitor sees and hears | What the live product is doing |
|---|---|---|
| **Prelude — Wet Stone** | A black screen, then water poured from a brass lota. A 100 mm macro lens finds dark granite at blue hour, raked by dawn light at 4°. The loader is rice flour sifting through unseen fingers. "Every threshold deserves a welcome." *Tap to sprinkle water*: droplets wet the stone. | Level 3's gold edge rim-light breathes with the dawn. The tap is the gesture that primes audio (FR-WEL-07). Pragya speaks a page-aware welcome, with glass captions for silent viewers. |
| **I. Pulli — The Dots** | The camera cranes from macro to straight overhead. Dots press into the flour like first raindrops, clustered by source page. Scrolling changes their density. Hovering lifts a dot on a thread of light and shows its source title. "These dots are everything I know. Only what this website says." | The dot field is generated at build time from the site's real crawl: one dot per chunk in the knowledge tree. The section has a real id so `scroll_to` and the tour can land on it. |
| **II. The First Stroke** | The visitor speaks, and their voice scatters **silver** grains across the stone. After the 850 ms end-of-speech window, a short **gold** flourish is drawn: the acknowledgement. Then the main line unspools around the five retrieved dots, one segment per spoken sentence. A "grounded · 87 % match" seal is pressed into the flour, and its source dots glow and can be clicked. Interrupt her and the line freezes mid-curve, the flour lifts like a held breath, and it turns towards the new question. | Fast Router acknowledgement (12 words or fewer) while the answer is computed in parallel. Sentence-streamed speech. The grounding badge and Sources. Barge-in ("Re-calibrating…"). Input level drives the silver, output level drives the gold **[new: energy event]**. |
| **III. The Honest Line** | Pragya dares the visitor: "Ask me something this website doesn't cover." A chip offers *"Who will win the IPL this year?"* A low tracking shot at flour height: the line heads for bare stone, slows, hesitates and curls back into a small closed loop beside the last dot. No seal. The score drops to **1.2 s of true silence**. "I don't know that from this site. I can connect you with the team." | The real confidence guardrail produces this moment by itself. The scene only reads that the reply carried no grounding. |
| **IV. The Pattern Learns to Speak** | "Let me draw it." The line lifts off the stone. Flour streams into the air and settles behind molten-obsidian glass into the outline of a real flowchart ("one script tag → crawl → live agent"). The live HTML component sharpens in exact registration, and the flour becomes the ghost that drew it. The ROI calculator, stamped *Illustrative*, pours flour between two pans as the slider moves. "Actually, make it 40 people" makes the figure count up in place. | The 13 generative components. Audio/UI sync (speech waits until the component has rendered). A live reaction after 0.7 s. An in-place patch rather than a redraw. Rupee amounts with Indian digit grouping. |
| **V. Closing the Loop** | "Want a free trial set up? Check the card and say yes." The visitor says **"haan"**. The line, open since the first stroke, travels home and joins its own beginning. The camera pulls up: one closed sikku kolam spans the whole threshold, and **it was the FluidBuddha mark all along**. "Send me this" lifts the kolam onto handmade paper: the recap. During staffed hours a **vermilion** line enters: "Ananya from the team joined", with an optional browser call. | Visitor-confirmed trial and meeting actions with voice confirmation ("haan", "yes", "ठीक है"). Lead capture and scoring. Recap page. Live takeover and WebRTC voice handoff, run by the real FluidBuddha team. |
| **Coda — Thirty Dawns** | A 12-second time-lapse of thirty dawns over the same doorstep. Familiar patterns redraw faster, in the identical voice. **One doorstep in ten is left bare**: "1 in 10 of our visitors never meets Pragya. That is how we measure her." Beside it, the live holdout verdict. The Credits are drawn as a kolam legend. Final frame: a wet, empty threshold and *"Draw your threshold: paste your URL"*. | Cache replay with identical audio. Holdout (10 %) with an always-valid verdict. An exit-intent opener. Self-serve onboarding. The site's MCP / `llms.txt` endpoint, linked in the footer. |

**The guided tour** does not cut away to new locations. Each tour stop expands the kolam
outward into a new quadrant of the same threshold, and the camera cranes only between overhead
and macro. This keeps the film's grammar pure.

### 4.3 Look and sound

- **Look:** an Apple product film shot at dawn in a Chennai lane, finished like Ghibli. Wet black
  granite with puddle reflections. Rice flour as millions of matte, slightly translucent grains
  with real height and tiny long shadows. Turmeric and kumkum as persona pigments.
  Molten-obsidian glass for every UI surface. One low warm key light (3200 K) and a cool sky
  fill (7500 K).
- **Palette:** Threshold Granite `#15171A` · Laterite `#3A2A22` · Rice Flour `#F4EFE6` ·
  Turmeric Gold `#D8A93A` (Pragya) · Accent `#C9A24A` · Moonstone Silver `#C2C8D2` (visitor) ·
  Kumkum `#B5462F` (the human line) · Dawn Haze `#E9C7A8 → #6E7FA3`.
- **Type:** a high-contrast display serif (Ogg or Fraunces) with Söhne or Inter for UI, and Tiro
  Devanagari Hindi or Mukta for Hindi. In Hindi, the **flour line draws the shirorekha** (the
  headline bar) that each Devanagari headline hangs from.
- **Motion:** one continuous line; never cut where a stroke can carry the eye. It eases like a
  hand: fast mid-stroke, slow at each turn. Everything pauses when Pragya pauses.
- **Sound:** dawn field recordings (a koel, a coir broom, a distant pressure cooker) mixed very
  low. Granular flour foley panned to screen position, so the line can be *heard* travelling.
  A commissioned score of ghatam and hand percussion with a soft analogue pad, and no sacred
  chant. The acknowledgement is close and dry; the answer has a longer tail. The score ducks
  9 dB under Pragya. Every closed loop resolves to the tonic.

### 4.4 Signature moments

1. **The Honest Line.** The line refuses to cross empty ground. It is the first time "it
   doesn't make things up" is *shown* rather than claimed.
2. **Two voices, two colours, one drawing.** The visitor's silver grains and Pragya's gold line,
   drawn live.
3. **The loop closes on "haan"**, and the finished kolam is revealed as the logo.
4. **Flour becomes interface.** Grains settle into the exact outline of a real flowchart, which
   then sharpens into live, clickable HTML.
5. **Thirty Dawns.** Cached answers redraw faster in the identical voice. One doorstep in ten
   stays bare, next to the live holdout verdict.

### 4.5 Persona and language cuts

- **CTO:** a cool moonstone key light. The dots are labelled with chunk IDs and similarity
  scores. Pragya prefers component diagrams (one multiplexed WebSocket, lean versus heavy
  routing). The close leads with the install snippet and the MCP endpoint.
- **CFO:** turmeric-gold flour, warm stone, numerals inside the dots. The roi_calculator and a
  sankey of cost per conversation (Growth is about ₹16.50 per conversation). The coda expands
  the holdout and the always-valid statistics.
- **Founder:** kumkum and gold, the fastest pace (the tour is trimmed to 6 stops). "One script
  tag, live in an afternoon". A payment link closed by "haan".
- **Campaign links** (`/p/{site_key}/{slug}?persona=cfo&account=Acme`) open on a doorstep already
  drawn with "Prepared for Acme".
- **Hindi:** Pragya narrates in Hindi and the captions switch to Devanagari. "Haan" is the hero
  beat of the Hindi cut.

### 4.6 Build notes

- Next.js (SSR) + React Three Fiber. WebGPU renderer with a WebGL2 fallback. Theatre.js camera
  sheets, triggered by GSAP ScrollTrigger + Lenis in free-scroll mode and by widget hooks in tour
  mode.
- **Flour:** a GPGPU particle system (262k grains on desktop, 65k on mobile) deposited into a
  height field and lit with screen-space normals for real grain shadows.
- **The line:** a constrained mirror-curve (Gerdes) graph is **precomputed per section**, so the
  rule "only around the retrieved dots, as one closed loop" is reliable at runtime. It is
  rendered as an instanced ribbon whose drawing progress follows the sentence segments.
- **Stone:** photogrammetry of a real threshold, Draco- or meshopt-compressed, with KTX2
  textures. The hero is under 1.8 MB. LCP stays under 2.5 s because the first frame is a static
  AVIF that hands off to WebGL.
- Targets: 60 fps on M1 or RTX 3060-class machines, 30 fps on mid-range Android. A frame-time
  governor halves particles and drops depth of field when needed. Reduced motion uses still
  photographic plates with an SVG kolam that fades in stroke by stroke. Without WebGL, the SVG
  kolam sits over static plates.
- Optional: a tenant **custom iframe component** (`kolam_trace`) so the agent itself can call
  the kolam renderer with typed props.

### 4.7 Risks and guardrails

- **Cultural:** kolam is a living daily practice with household-ritual associations. Commission
  and credit 2–3 practising kolam artists, paid and featured in an "about the craft" section.
  Keep out all temple and deity imagery. Run a sensitivity review with Tamil and pan-Indian
  reviewers. These are **non-negotiable line items**.
- **The logo:** the reveal only works if a sikku-kolam version of the FluidBuddha mark is
  commissioned before production.
- **Heaviest real-time graphics of the slate**, after MOLTEN.
- The IPL dare depends on the guardrail. If it is pinned as a curated answer, be open about it.

### 4.8 Why it wins

One image does everything. The single line is **the brand mark, the grounded answer, the honest
"I don't know", the navigation path and the closed sale**. Juries reward that kind of total
coherence. It is Indian without being touristy, mathematical without being cold, and it turns
the hardest truth to sell into the most memorable shot on the site.

---

## 5. Concept B — 11:58: The Night the Website Learned

> **Tagline:** *Same question. Better answer. Every time.*
>
> **Logline:** A time-loop thriller. Ananya, the operations head of a 40-truck logistics firm,
> reaches the same vendor pricing page at 11:58 p.m., again and again. First the site is silent
> and she leaves. Then it speaks, and honestly admits it doesn't know. Then the owner, the only
> person who remembers every loop, fills the gap. Finally it answers instantly from memory, she
> says "haan", and midnight is allowed to pass. Then the film reveals that the visitor is a loop
> on this very website.

*(This concept merges two pitches. LOOP provides the structure. NIGHT SHIFT provides the
local-time clock, the turn to camera, the exit-intent mirror and the credits.)*

### 5.1 The idea

**The time loop is the learning loop.** FluidBuddha's most valuable truths are about
repetition. Answers and audio are replayed. Knowledge gaps are found and filled. Test winners
are promoted. A holdout measures the site *without* the agent, and the statistics stay valid
however often you check. The buyer lives the moment; the owner remembers it, through Insights
and the Monday digest; and the control timeline that never changes is the holdout.

| In the film | In FluidBuddha |
|---|---|
| The loop that never changes | The holdout control group |
| The gold index card that survives the rewind | A knowledge gap logged in Insights |
| The man who remembers every loop | The weekly digest and Insights |
| The loop going better each time | Uploading the knowledge and pinning a golden answer |
| Déjà vu | Byte-exact audio replay |
| Midnight finally passes | The visitor-confirmed action |

### 5.2 Storyline

| Loop | What the visitor sees | What the live product is doing |
|---|---|---|
| **The clock** | The clock on Ananya's screen starts at the **visitor's own local time** and runs towards 11:58. One apartment, one laptop, chai. The frame is 2.39:1. | The scene is seeded from the browser clock. |
| **Loop 0 — Silent** | A cold, desaturated grade. Ananya hovers over "Integrations". Subtitle: *"Does it sync with Tally?"* Nothing answers. At 11:59 she closes the tab. Time runs backwards: the tab reopens, the chai un-spills, the clock snaps to 11:58. | This is the visual language of the holdout. Visitors in the real holdout get the full silent cut, and are told why only *at exit*, never on arrival. |
| **Loop 1 — Honest** | A warmer grade. A nudge appears after 15 s. Ananya asks about Tally. Pragya acknowledges at once, then: *"That isn't in our documentation, and I'd rather not guess. Shall I have the team confirm by morning?"* Ananya leaves her email. The clock rewinds, but a **gold index card drops out of the loop** and falls through the floor. | A time-on-page trigger with an agent-written opener. The instant acknowledgement. The 0.45 guardrail. Lead capture. A knowledge gap logged in Insights. |
| **Interlude — The Man Who Remembers** | IMAX 1.43:1. Monday, 09:00. Vikram, the vendor's sales head, is the only one who remembers, because **his weekly digest does**. The index cards pile up as Insights: top question "Tally?", objection "integration effort", a knowledge gap. He uploads the Tally guide and pins a golden answer. Old cached answers visibly dissolve. | Weekly digest. Insights v1 and v2. Knowledge upload. Changed knowledge clears cached answers, while pinned answers stay. |
| **Loop 2 — Shows** | 11:58 again. The answer arrives with "grounded · 91 % match" and the source *Tally integration guide*. A workflow diagram draws itself, and Pragya speaks only once it has landed. "Actually, 60 trucks" makes the configurator count up. The page re-grades for her operations role. Then **the film turns to camera**: *"Ask it your way."* The visitor's own question enters the loop. | Grounded answers with citations. Generative workflow and configurator components. Audio waits for the render. An in-place patch. Silent persona re-theming. A live voice or text turn from the visitor. |
| **Loops 3–300 — Two Timelines** | Split screen: the control timeline on the left, the agent timeline on the right. A montage of loops 12, 47, 120 and 300. A confidence corridor narrows as the camera flies down it, and the verdict word moves *collecting → trending → significant* only when the maths allows. Two greetings compete, and one is stamped "Make default". Card: *"Simulated loops. Your real numbers come from your own holdout."* | The always-valid mSPRT verdict ("safe to read daily"). Wilson and Newcombe intervals. Variant A/B tests with one-click promotion. The simulation is clearly labelled. |
| **Loop 301 — Déjà vu** | The same question replays instantly. Two waveforms, from loop 47 and loop 301, **lock together sample for sample** and fuse into one gold line. A cost meter drains towards near-zero model cost. Ananya: *"Huh. That was fast."* | Exact and semantic replay (at least 0.92 match) with byte-exact audio. "Model cost falls on replay; the plan price is per conversation." |
| **The Loop Breaks** | Pragya offers a 14-day trial. Ananya reaches for the laptop lid, **mirrored by the visitor's own cursor heading for the close button**, then says **"haan"**. For the first time the second hand passes 11:59:59. The camera moves on into an unrehearsed morning: she forwards the recap to her CEO, and at 09:00 Vikram's phone lights up with a Slack hot-lead alert. | Exit-intent trigger. Voice-confirmed trial. Recap forwards that raise the lead score. Slack hot-lead alert. |
| **Your Loop** | The film pulls back to a wall of loop counters on the real fluidbuddha.com: *"N % of answers on this site were replayed from memory this week."* The visitor's questions join an anonymised wall of top questions. *"In another timeline, an AI assistant asked our site the same thing."* The Credits roll, listing only the events this session fired. CTA: *"Start your first loop: 100 conversations free."* | The site's own analytics, exported nightly and dated "as of". Agent traffic from the MCP endpoint. The Free plan from the real price list. |

### 5.3 Look and sound

- **Look:** practical, analogue cinema with grain, real materials and restrained colour. **Time
  is the special effect.** The aspect ratio carries meaning: 2.39:1 for Ananya's loops, 1.43:1
  for Vikram's remembering timeline, full-bleed split screen for the two timelines. Characters
  are **stylised and partly seen**, never photoreal faces. The agent timeline is graded towards
  Pragya gold `#C9A24A` and visitor silver `#C2C8D2`. Night slate `#0B0E12`, control grey
  `#8A9099`, loop-counter red `#E5484D`.
- **Type:** a monumental condensed grotesk for clocks and loop counts (Druk or Neue Haas
  Display), tabular mono for statistics, and a book serif for subtitles.
- **Interaction signature:** **scrolling down moves time forward and scrolling up rewinds the
  room**, with the audio reversed. Pragya's live voice is never reversed.
- **Sound:** a ticking clock that slowly becomes the score's pulse, under a tension figure that
  climbs every loop and resolves only when midnight passes. Rewinds use reversed audio with
  tape-stop bends. Because Pragya's cached answer is *literally the same audio* every time, her
  identical delivery becomes the recurring musical motif of déjà vu. The control timeline is
  mixed thin and mono; the agent timeline is wide and warm.

### 5.4 Signature moments

1. **Scroll up and time runs backwards**: the chai un-spills and the tab reopens.
2. **The waveform lock**: visual proof of the byte-exact audio cache.
3. **The confidence corridor** the camera flies through, where "significant" may land only when
   the statistics allow.
4. **The turn to camera**: the visitor's own question enters the loop.
5. **Midnight passes** on one "haan".

### 5.5 Persona and language cuts

- **CFO (the natural hero):** the two-timeline and déjà-vu loops are extended. A scenario
  simulator of traffic × conversion × deal size is stamped *Illustrative, replace with your
  numbers*. Real plan economics.
- **CTO:** Loop 2 opens up the machinery: acknowledgement and answer running as two parallel
  tracks, lean versus heavy routing, sentence-ahead speech synthesis, audio waiting for the
  diagram. Then BYO model and self-hosting, framed as "running the loop on your own clock".
- **Founder:** Vikram *is* the founder. The interlude leads with Monday insights and a setup in
  one afternoon from a crawl.
- **Hindi:** Ananya speaks Hinglish and Pragya answers in Hindi from English content. A faint
  subtitle shows the English search query the router wrote (FR-LANG-03). The close is "haan".

### 5.6 Build notes

- React Three Fiber, with all character and prop animation **baked to vertex-animation
  textures** and Theatre.js sequences, so time is fully deterministic and can be scrubbed in both
  directions. Scroll position is the clock, and scroll velocity drives the speed ramps and motion
  blur.
- Split screen uses two scissor-tested cameras over one scene with two LUT passes, so no geometry
  is duplicated. Rewinds play the animation textures backwards with a chromatic time-smear
  shader.
- **One set (one apartment) in five lighting states.** That is far cheaper than a city-wide
  one-take shot.
- The confidence corridor is generated from the real interval series. The waveform lock uses two
  real TTS clips captured from the production cache.
- Mobile: each loop is a vertical swipeable story card. Reduced motion: a side-by-side storyboard
  table of Loops 0, 1, 2 and 301. No JS: a long-read titled *"Four versions of the same minute"*.

### 5.7 Risks and guardrails

- **Demo tenant separation.** Ananya's vendor and its Tally gap live in a **separate demo
  tenant** with its own key and knowledge base. They never enter fluidbuddha.com's own knowledge,
  or the real agent would start answering questions about a fictional vendor. The visitor's live
  turns go to the real fluidbuddha.com agent.
- It is the most complex narrative of the slate, so each loop needs a crisp title card.
- Remove obvious film homages from the brief so juries cannot name the references. The rewind
  grammar is the film's own.
- Keep the holdout at the 10 % default so the verdict can mature.

### 5.8 Why it wins

It turns the hardest truths to show (it learns, it gets cheaper, it proves its own lift, it
admits what it doesn't know) into the most cinematic device there is: time. Scroll-to-rewind,
the waveform lock and the holdout as a real control timeline are interactions juries have not
seen, and they are *true*. It speaks straight to the people who sign the budget.

---

## 6. Concept C — PLACES, PLEASE: The Site That Isn't There Yet

> **Tagline:** *There's no website here. Ask, and it will be built.*
>
> **Logline:** The visitor arrives in an empty black-box theatre lit by a single ghost light.
> There is no navigation, no hero and no menu. Every section of the FluidBuddha site hangs dark
> in the fly tower above. A section is flown in, lit and spoken only when the visitor asks for it,
> and Pragya calls the cues as the stage manager.

*(This concept merges three pitches. CUE provides the empty stage and the fly tower. PLACES,
PLEASE provides the stage devices. SUTRADHARA provides the visible event threads.)*

### 6.1 The idea

Most websites are a set left standing after the show has closed. FluidBuddha is a live
performance.

| In the theatre | In FluidBuddha |
|---|---|
| The **ghost light**, the single bulb left burning on an empty stage | Pragya's dormant state (the breathing Aura) |
| The flats hanging in the fly tower | The Extreme tier's typed page sections (14 types, up to 12 per page): a safe, fixed repertoire assembled on cue, not free-form UI |
| The prompt book; actors don't ad-lib | The knowledge base and grounding. When a line isn't in the book, she says so. |
| **"The line waits for the set"** | Audio/UI sync: speech is held until the component renders |
| The set moves only after the line ends | The guided tour moves only after its narration finishes |
| "Vamp till ready" | The 1.5 s filler tone |
| The gauze transformation | The 300 ms persona veil |
| A lighting cue | Persona re-theming |
| "Hold, please" | Barge-in |
| Repertory: a scene performed many times costs little to perform again | The answer cache |
| The fly ropes and lighting lines | The real `fluidbuddha:*` events. Every rope is labelled and visibly tugs on each command. |
| The playbill | The recap page |
| The curtain call | The conversion |

### 6.2 Storyline

| Act | What the visitor sees | What the live product is doing |
|---|---|---|
| **I. House Lights Down** | The murmur of an empty house and a timber creak. A bare ghost light breathes on a 5.5 s cycle. A locked-off wide shot from row M with silhouetted seat backs, then a 12-second push-in so slow it is barely noticeable. On the stage floor: *"There's no website here."* A beat later: *"Ask for one."* | A time-on-page trigger with a composed opener. Level 3 captions on the proscenium arch. The ghost light follows the Aura's state language **[new: state event]**. |
| **II. The House Rules** | A "house rules" card slides down on two wires. It carries the real consent copy (listens only while voice is on; emails, phone and card numbers masked; transcripts kept for a stated retention period) and two choices: *Allow microphone* or *Type instead*. Typing lights a slim prompt line in the footlights. | Microphone consent (the server drops audio until consent). The privacy story becomes part of the drama instead of a pop-up to dismiss. |
| **III. Places, Please** | *"So what is FluidBuddha?"* Within a second Pragya says *"Standby…"*. The camera **cranes up into the fly loft** and reveals every possible page hanging dark in rows, like a library. Three light from within (hero, feature grid, flowchart) and fly down on counterweighted ropes with a soft overshoot. **Pragya's explanation begins exactly as the flowchart flat lands.** | Extreme-tier runtime page generation, themed with brand tokens. The instant acknowledgement masks composition time. Audio/UI sync gating. The sections stay real, accessible DOM. |
| **IV. The Prompt Book** | Stage left, a prompt book under a blue cue light riffles to the source. A brass tag reads "grounded · 88 % match", and clicking it navigates to the source page. Then the Honest Dare: *"Can you integrate with my coffee machine?"* The cue light stays dark and the book stays shut. Pragya says it isn't in her material and offers the team. In the wings: **"We don't ad-lib."** | CORTEX grounding, the badge, clickable Sources, and the 0.45 guardrail, staged rather than claimed. |
| **V. Lighting Cue 7: Who's in the House?** | *"Are you looking at this from the tech side or the business side?"* *"I'm the CFO."* A lamp **thunk**. Haze rolls across. The whole gel plot crossfades to steel and ledger green, the flowchart flies out, and a pricing table and ROI calculator fly in. The camera holds dead still so the light does all the work. | Adaptive persona: one qualifying question at most every 3 turns, a switch at 0.6 confidence, a lock on self-identification. `onSetPersona` turns the 300 ms veil into a 3D lighting crossfade and changes which sections fly in. |
| **VI. Props** | The ROI calculator comes down to waist height like a prop table, stencilled ILLUSTRATIVE. The visitor drags a slider, and after 0.7 s Pragya adds one insight. *"Actually, make it 40."* The same prop updates in place with a brass highlight. | Interactive components, live reactions, in-place patching, ₹ formatting with Indian grouping. |
| **VII. The Running Order** | *"Give me the tour."* The stage floor is a **revolve**. Each stop is a scene on one segment: Talks, Shows, Acts, Proves, Revenue. The revolve turns 60° only after Pragya's last word. Interrupt (*"Wait, go back to pricing"*) and the revolve, the flying flats and the haze all **freeze mid-air**: *"Hold, please."* | The tour engine (move after narration plus 450 ms), driven by `onNavigate` and `onScrollTo`. Barge-in cancels queued audio. |
| **VIII. Repertory, Playbill, Curtain Call** | A common question: the flats arrive already lit, and an enamel plaque reads *"Performed 1,204 times · replayed from memory"* (a real count). A ticket stub slides out: *Book a 20-min walkthrough*. **"Haan"**, and it is torn and stamped. "Send me this" prints a **playbill**: the recap. During team hours a side door opens and a person from the team steps on stage. The house lights come up. | Cache replay with a real hit count **[new: counter endpoint]**. Voice-confirmed meeting action. Recap page. Live takeover and voice handoff. |
| **Epilogue — The Ghost Light** | The stage is empty again. A *Director's notes* board shows anonymised aggregate Insights: what the audience asked about this week. | Insights v1 and v2, exported nightly. |

**The CTO cut** adds **"raise the scrim"**. The backdrop lifts to reveal the live event log of the
visitor's own session: every rope and the event that pulled it.

### 6.3 Look and sound

- **Look:** a black-box theatre, not red velvet. A matte black floor with chalk tape marks, an
  exposed steel fly grid, hemp ropes, worn brass, and glossy obsidian glass on the faces of the
  flats, echoing the widget panel. **The only colour comes from light.** Volumetric followspot
  cones in thin haze. Baked lighting for the set, dynamic light only for cues.
- **Palette:** Stage Black `#0B0A09` · Ghost-light Amber `#F2B35E` · Pragya Gold `#C9A24A` ·
  Cue Blue `#3F6BFF` · Moonstone Silver `#C7CCD3` (the visitor). Persona gels: CFO Ledger
  `#6E8F7A` + Steel `#A9B4BD`; CTO Work-light Cyan `#7FE3F0`; Founder Amber `#E8873A`.
- **Type:** a theatrical high-contrast serif (Canela or Fraunces) and a stencil monospace for cue
  numbers and the ILLUSTRATIVE marks.
- **Motion:** everything moves on cue and nothing drifts. Flats fall on damped springs and settle
  in under 900 ms. Long locked-off wide shots, slow push-ins, one big crane move per act, and no
  handheld. Light changes are timed like real lighting desk cues.
- **Sound:** the recorded room tone of an empty theatre. Foley *is* the UI: hemp rope through
  pulleys, the clunk of counterweights, the lamp thunk, chalk on a slate, a ticket punch. A
  single bowed cello and a tanpura tuned to Pragya's voice enter only in Acts V and VIII.
  Stage-manager language (*"Standby… Go"*) appears as captions and light, **never as extra
  synthetic speech**, because only the real agent speaks.

### 6.4 Signature moments

1. **The fly-loft reveal**: every possible page hangs dark, until the visitor asks.
2. **"The line waits for the set"**: Pragya's sentence begins exactly as the flat lands.
3. **The persona lighting cue**: a 300 ms product behaviour, performed at the scale of a stage.
4. **"Hold, please"**: the whole theatre freezes mid-air when the visitor interrupts.
5. **The repertory plaque**: cache economics turned into theatre lore.

### 6.5 Persona and language cuts

- **CTO:** white work lights and cyan. Component diagrams and the transport story (one
  multiplexed WebSocket, binary audio, Shadow DOM, self-hosting). A *Backstage* tour stop that
  walks the rigging. Raise the scrim.
- **CFO:** the ledger plot. Pricing, an illustrative ROI calculator and holdout flats come first.
  The curtain call offers a quote request with PDF.
- **Founder:** footlight amber, the shortest show (four cues): one script tag, live in an
  afternoon, a scenario simulator, a trial.
- **Hindi:** flat titles and captions switch to Devanagari. The cue cards read *"तैयार… चलो"*,
  and "haan" confirms the ticket.

### 6.6 Build notes

- Astro or Next.js for server-rendered content routes, which also serve as the knowledge source
  and the agent's navigation targets. React Three Fiber + drei, with a small **cue engine**: a
  state machine that turns `fluidbuddha:*` events into GSAP timelines.
- Each runtime page section maps one-to-one to a 3D flat. The flat's face is the real
  Shadow-DOM section, placed with CSS3DRenderer. During flight it shows a texture snapshot; once
  it lands it switches to live DOM, so it stays accessible and clickable.
- A cheap analytic volumetric cone shader (no full raymarch), gobo projection for persona gels,
  and spring motion on the CPU. The stage GLB is under 2.5 MB with baked lightmaps.
- LCP under 2.0 s: the ghost light is a 2D canvas first, and the 3D stage streams in after the
  first interaction. Mobile: one front-of-house camera, flats as sliding cards, no volumetrics.
- **Pin the top 30 questions** so the opening acts are cache replays, not slow first-time page
  composition.

### 6.7 Risks and guardrails

- Extreme-tier page composition is the slowest path (up to 4 thinker rounds). Pinned answers,
  the acknowledgement and flats that animate in anticipation all hide the wait.
- **A site with no navigation** is a risk for SEO and for impatient visitors, so a persistent
  *Programme* index of plain, server-rendered pages sits in a corner at all times.
- Keep it black-box and brutalist so the theatre never feels old-world.
- The CSS3D/WebGL hybrid needs careful depth sorting and focus management for accessibility.

### 6.8 Why it wins

It is the purest form of "the site is the demo": **a jury literally cannot read it without
using the product**, and every theatrical device maps to a verifiable product behaviour. Each
visitor's show is assembled differently, which drives replays and shares. It also gives the
brand a quotable line, *"We don't ad-lib"*, and an icon, the ghost light, to replace the
glowing AI orb.

---

## 7. Concept D — CAST: Wake Your Website

> **Tagline:** *Every website you've ever built is a statue. Let's wake yours.*
>
> **Logline:** A sunlit 19th-century cast court where the web's static websites stand as plaster
> casts, frozen mid-gesture: a carousel stuck on slide two, a contact form still waiting, a chat
> bubble that never answered. Pragya is the curator. The visitor walks the galleries, then brings
> their own URL to the casting room. They watch it crawled and cast live, then woken, with a voice
> made from their own content.

### 7.1 The idea

The great **cast courts** (the V&A's, and the plaster galleries of Indian museums) hold copies
of monuments: beautiful and silent. Static websites are the same: monuments that cannot hear a
single visitor. The *waking* is the value moment: plaster cracks away to reveal living colour and
a voice.

| In the museum | In FluidBuddha |
|---|---|
| The curator and the audio guide | The grounded agent and the guided tour |
| Plinth spotlights | The Level 3 spotlight |
| **The casting room** | The real onboarding pipeline: crawl → ingest → personas → brand design |
| Pigment swirled into the plaster | Brand-token extraction (colours, fonts, logo) |
| Plaster visitors standing before a cast | Derived personas |
| The Control Wing | The holdout experiment |
| The exhibition catalogue | The recap page |

### 7.2 Storyline

| Gallery | What the visitor sees | What the live product is doing |
|---|---|---|
| **I. The Hall of Silence** | A Steadicam glide down a top-lit nave of travertine and plaster, with dust in the light shafts. On plinths, generic (never real-brand) casts with bilingual placards: *"Homepage with Carousel, Stuck on Slide Two. c. 2012."* · *"Contact Form, Unanswered. c. 2003–present."* · *"Chat Bubble: 'Hi! How can I help?' Never Followed Up."* A gold rim light traces the screen and the curator welcomes the visitor. | Level 3: rim light, captions, Ctrl-K summon. A page-aware welcome. Consent arrives as an *Audio guide* card. |
| **II. The Exhibits Speak** | At each of three plinths the camera dollies in and the page dims around a ring of light. *"How does it actually work?"* A cast **cracks along a seam** and a live gold flowchart draws itself inside the fracture, with Sources on the placard. | The guided tour (each move after narration ends) and the spotlight. Generative components with audio held until render. Clickable citations. |
| **III. The Casting Room** | A dark workshop of plaster dust and a giant empty mould on a turntable. *"Bring us your website."* The visitor says or types their URL, and **the real pipeline phases drive the ritual**. *Crawling*: pages found arrive as relief panels pressed into the mould, with a live count. *Ingesting*: liquid plaster pours. *Personas*: 2–4 plaster figures of the derived audiences rise (*"Clinic owner"*, *"Enterprise IT"*). *Design*: pigment in **the visitor's own brand colours** swirls in. A slow 360° orbit. Elapsed time is shown honestly. | One-job onboarding with live progress phases. Robots.txt respected, sitemap seeding, capped low for the demo (about 8 pages, depth 1). |
| **IV. The Waking** | The mould lifts. *"Let's wake it."* A gold rim light traces the white cast, and hairline cracks spread across it. The plaster **falls away in a cascade**, revealing the visitor's content re-composed as a living page in their own colours, fonts and logo. Then a voice speaks **for their business**, grounded only in their pages. The visitor asks it a question about their own business, and it answers with Sources that link to their own URLs. | A sandbox site created from the crawl. Grounded answers citing the visitor's own pages. Extreme-tier page composition themed with their extracted brand tokens. |
| **V. Your Visitors, Tonight** | The plaster persona figures turn to face the living page. *"Show me how a CFO would see it."* The skylight shifts colour temperature and the page re-themes. *"Ab Hindi mein bataiye."* **Every placard in the museum flips like a split-flap board to Devanagari**, and the agent answers in Hindi from the visitor's English content. | Persona discovery and silent re-theming. "Reply in Hindi", Hindi speech, and English search queries written by the router (FR-LANG-03). |
| **VI. The Control Wing** | A quiet gallery with one large split-flap board: *"This museum is an experiment. A share of today's visitors walked these halls without a curator."* The live verdict (COLLECTING / TRENDING / SIGNIFICANT), plus the result of **a real test of design levels run on the museum itself**. A cabinet of *"This week's questions"*: anonymised objections, gaps and competitors. | Holdout with always-valid statistics. A variant A/B test of the design level. Insights v1 and v2. |
| **VII. Take It Home** | A museum shop counter with three objects. **The Lantern**: the install-preview bookmarklet; drag it to the bookmarks bar, open your real site, click, and the agent appears there. **The Catalogue**: the recap page, laid out as an object worth forwarding. **The Ticket**: a trial or meeting card, stamped on "haan". *"Your preview and its data are deleted after 24 hours."* During team hours a docent (a real person) can start a browser call. | The bookmarklet. Recap pages. Voice-confirmed actions. True deletion. Live takeover and voice handoff. |

### 7.3 Look and sound

- **Look:** neoclassical meets brutalist. Travertine, raw plaster, board-marked concrete and
  soft north light. The exhibits are white plaster with porosity, chisel marks and dust in the
  recesses. **The only saturated colour on the whole site is the visitor's own brand**, which is
  what makes their waking unforgettable. The curator's light is liquid gold `#C9A24A` and the
  visitor's voice is silver `#C7CCD3`. Plaster `#EDE8DF`, Travertine `#D9CFC0`, Umber Shadow
  `#2B2622`.
- **Type:** a museum placard serif (GT Sectra or Newsreader), an accession-number monospace (IBM
  Plex Mono), and split-flap boards for live data.
- **Motion:** museum pace, with long continuous glides and no cuts in the galleries. The waking
  is the one fast moment: cracks spread in 600 ms, the plaster falls in 1.2 s, the colour blooms
  in 400 ms.
- **Sound:** a stone-hall reverb with a 4–5 s tail. Footsteps follow scroll speed. Each static
  exhibit emits a faint, flat **50 Hz hum (India's mains frequency)**, the sound of a lifeless
  machine. When a cast wakes, **harmonics bloom out of that same 50 Hz** into a warm chord, then
  a swell of tanpura and strings. Pragya's voice is the only dry, close sound in the hall, like
  an audio guide in one ear.

### 7.4 Signature moments

1. **Casting your own website**: the real crawl, performed as plaster pouring and brand pigment
   swirling in.
2. **The waking**: your site cracks out of plaster and *talks about your business*. Nobody
   forgets hearing their own website speak.
3. **The split-flap flip to Devanagari** across the whole museum.
4. **The Control Wing**: an award site that publishes its own live experiment.

### 7.5 Persona and language cuts

- **CTO:** an *Engine Room* wing (one multiplexed WebSocket, Shadow DOM isolation, the
  SSRF-safe crawler, SSO, audit, BYO model, self-hosting). Their woken site appears with a
  component diagram of how the widget sits on it.
- **CFO:** the *Treasury* wing first: the Control Wing, cost per conversation, replay economics
  and an illustrative ROI calculator. The shop counter leads with a quote request (PDF).
- **Founder or agency:** straight to the casting room. The waking *is* the pitch. The counter
  leads with the bookmarklet and the Free plan.
- **Hindi:** every placard carries Devanagari as a first-class line, not as a translation added
  later.

### 7.6 Build notes

- Next.js + React Three Fiber. A camera spline between plinths, built in Blender with baked GI.
  The hall is under 4 MB, streamed gallery by gallery.
- **The waking shader:** a Voronoi crack mask spreading from the click point, a noise-threshold
  dissolve, and emissive brand pigment underneath. 300–600 pre-fractured shards on a vertex
  animation texture (no runtime physics).
- **The sandbox service:** a thin marketing service provisions a short-lived sandbox site through
  the product's own onboarding API and maps its real job progress to the casting animation.
  The visitor's site is **never iframed** (it is composed from crawled content). A server-side
  screenshot is used only as the relief texture on the mould.
- **Sequential sessions:** the curator "hands the mic" to the visitor's site through a session
  switch, not two widget instances at once (unless the SDK is shown to support that).
- Mobile: a vertical corridor with one plinth per screen and a 2D crack-and-dissolve shader.

### 7.7 Risks and guardrails

- **Heaviest on the backend:** anonymous sandbox sites, crawls of arbitrary URLs and runtime
  page composition all cost money and attract abuse. **Gate the full waking behind a work email
  whose domain matches the URL**, which stops anyone waking a competitor's site. Everyone else
  gets a 3-page silent preview of the cast. Add per-IP rate limits, low caps and a spend cap.
- A crawl plus ingestion can take 30–90 s, so the ritual must be genuinely watchable, with a
  *"We'll email you when it's awake"* path for anything over 45 s.
- Brand extraction can fail on heavily scripted sites. Fall back to a neutral gold pigment and
  say so. Thin sites produce thin knowledge, and the curator says so honestly.
- **Claims:** *"A preview from 8 of your pages in about a minute; a full install takes an
  afternoon."* Never *"live in a minute"*.
- The tone must be witty, never contemptuous of the visitor's current site.

### 7.8 Why it wins

It makes the visitor the protagonist in the most personal way possible: **their own website,
woken, talking about their business with their own sources**. That is the moment people
screen-record and post. It compresses the whole sales cycle (problem, demo, proof, install) into
one walk, using the real onboarding pipeline, so the wow cannot be faked. It has the highest
business impact of the slate.

---

## 8. Concept E — ANECHOIC: The Room That Listens

> **Tagline:** *Websites have never heard a word you said. This one is listening.*
>
> **Logline:** The whole site is a single anechoic chamber: a field of twenty thousand matte foam
> wedges in darkness, with no menu, no scroll and no pages. The visitor's voice sends a silver
> wave across the field. Pragya's answer comes back as a gold one. The wedges part to raise
> diagrams out of the floor. The physics of sound becomes the explanation of the product.

### 8.1 The idea

An anechoic chamber is the quietest room on earth. It is built to add no echo and no colour to
sound, and to reflect only what is truly there.

| In acoustics | In FluidBuddha |
|---|---|
| A room engineered for listening | Websites have been mute rooms; this one listens |
| **Early reflection**, arriving first | The spoken acknowledgement in under a second |
| The full response that follows | The grounded answer |
| **Absorption** | Barge-in: the moment the visitor speaks, Pragya's sound is soaked up |
| **Echo** | The cache: a repeated question returns identical (byte-exact audio) and almost free |
| A room that adds nothing | Grounding: nothing that isn't in the content |
| **Field coherence** | Confidence: an ungrounded question leaves the field visibly unsettled |
| **The ultrasonic band**, frequencies you can't hear | AI assistants querying the site through MCP |
| The room's tuning | Persona and language |

### 8.2 Storyline (three movements)

To read as cinema rather than a tech demo, the piece is scored in **three movements**, each
allowed **one authored camera move**.

**Movement I — Silence**

| Beat | What the visitor sees | What the live product is doing |
|---|---|---|
| **Arrival** | Two seconds of true black. A grazing key light rakes across a field of charcoal foam wedges that stretches to the horizon. *"This is the quietest page on the internet."* The wedges begin to breathe on a 5.5 s swell. *"It's been waiting for you to say something."* The camera drifts down to a low angle near the horizon. | The dormant state (the Aura's breath). Level 3, so the page itself is the agent. |
| **The light is on** | A thin silver line along the bottom edge: *"The room listens only while this light is on."* The visitor speaks, and **a silver wavefront rolls across twenty thousand wedges**. The ripple begins a fraction *before* the first word appears visually, because the room keeps the 400 ms before the visitor spoke. Their words rest on the crests as captions. | Consent. Voice detection with a 400 ms pre-roll. Mic level fed into a GPU wave simulation **[new: level event]**. |

**Movement II — Conversation**

| Beat | What the visitor sees | What the live product is doing |
|---|---|---|
| **Early reflection** | Within a second a thin **gold ring** travels back from the far horizon: the acknowledgement. Deep in the field a soft glow pulses: the answer being composed. A tiny "room meter" shows *real* times: *"first reflection 0.7 s · response composing…"* | The concurrent acknowledgement. Thinking and speaking states. Time to first audio measured on the client and shown honestly. |
| **The room draws** | *"How does this work on my site?"* The central wedges fold down in a widening radial clearing, like grass bowing. A matte stone surface rises and gold lines draw a flowchart on it. **Pragya's sentence begins exactly as the first node appears.** At the field's edge, glowing "sound sources" mark where the answer came from: *"How it works · grounded · 91 % match"*. | Generative components with audio/UI sync. Citations shown as sound sources, each linking to its source route. |
| **The unsettled field** | The Honest Dare: an off-site question. The wedges **never settle**: they stay noisy and unresolved before Pragya says she doesn't know and offers the team. | Field noise = 1 − confidence. The 0.45 guardrail. |
| **Absorption** | A tiny caption: *"Interrupt her."* The visitor does. Pragya's gold wave is **swallowed** in a radial dark ripple, *"Re-calibrating…"* appears, and the field turns silver. The clearing reshapes into a pricing comparison and an ILLUSTRATIVE ROI configurator. The wedges around it lift in step with the computed output. | Barge-in. The heavy path for pricing. Component state reported to the agent. A live reaction after 0.7 s. In-place patching. |
| **Two tunings** | *"Hindi mein samjhaiye."* The whole field re-tunes: the wedges align into **one long horizontal ridge of light, like a Devanagari shirorekha**, and the Hindi captions hang from it. *"I run finance."* The foam turns to **copper-and-steel vault wedges** behind a soft blur (carbon and cyan for a CTO, terracotta for a founder). | English and Hindi. Persona re-theming via `onSetPersona`. |
| **Echo** | A common question returns almost at once, trailed by faint **ghost copies of the identical waveform** stacking into the distance: *"asked 3,412 times · this answer replayed"* (a real count). *"Some questions echo. Echoes cost almost nothing."* | Cache replay with byte-exact audio **[new: replay flag, counter endpoint]**. |
| **The ultrasonic band** | A faint strip along the horizon flickers whenever an AI assistant somewhere queries this site: *"Frequencies you can't hear."* | Agent traffic through MCP and `llms.txt`. |

**Movement III — The Door**

| Beat | What the visitor sees | What the live product is doing |
|---|---|---|
| **The door** | Far off, a tall rectangle of warm light opens in the field. *"I can set up a 20-minute walkthrough with the team. Shall I?"* **"Haan."** The door brightens and the card seals. Or a second, silver-white source appears beside the door as a team member joins. A **tanpura drone in Sa** fades in, the first music in the whole experience, a resolution earned by the silence before it. The Credits appear as *the score*. | Visitor-confirmed actions. Live takeover and voice handoff. Recap page. PII masking ("your email", never read out). |

### 8.3 Look and sound

- **Look:** minimal, sculptural, an acoustics lab. **One material** (matte open-cell foam), **one
  key light**, **one hero shape** (the wedge) repeated twenty thousand times, so scale is the
  spectacle. **Colour exists only as sound**: silver for the visitor, gold for Pragya, with a gold
  sheen on the wedge tips during speech. Chamber Black `#070708` · Foam Charcoal `#1C1C1F` ·
  Pragya Gold `#C9A24A` · Moonstone Silver `#C7CCD3` · Ember `#E9B872` (thinking). Persona
  materials: CFO Vault Copper `#B87333` and Ledger Green `#5F8A6E`; CTO Carbon `#15181C` and
  Edge Cyan `#6FE1EE`; Founder Terracotta `#C46A45`.
- **Type:** an engineering grotesk and mono (Söhne Mono, or Space Grotesk and Space Mono).
  Devanagari hangs from a literal shirorekha of light.
- **Motion:** all motion is wave motion, travelling from a source at a finite speed (about 0.8
  screen-widths a second). There are no tweened UI slides. Absorption is the only abrupt motion.
  The camera stays low and nearly still, **because the field is the camera move**.
- **Sound:** **near-silence is the score.** The visitor's own voice is dry, and Pragya's voice is
  dry, close and intimate, because an anechoic room adds no reverb. Thinking is a single sine at
  Pragya's fundamental. A cached answer is preceded by a faint pre-echo flutter, the only reverb
  on the whole site, as a deliberate wink. Absorption is a 120 ms low-pass sweep. The tanpura
  arrives only at the door.

### 8.4 Signature moments

1. **Twenty thousand wedges bowing to the visitor's first word.** They literally see that the
   website heard them.
2. **The early reflection**: latency masking turned into physics anyone understands.
3. **Absorption**: the site invites the visitor to interrupt, then shows that it works.
4. **The echo**: cache economics made beautiful and literal.
5. **The shirorekha re-tuning** into Hindi.

### 8.5 Persona and language cuts

- **CTO:** a carbon-and-cyan room. Component diagrams first. The room meter shows more
  instrumentation (time to first audio, cache hit rate). The door offers self-hosting and SSO.
- **CFO:** a copper vault. The holdout method and cost per conversation come first. The echo
  scene stresses near-zero replay cost. The door offers a quote with PDF.
- **Founder:** terracotta, the fastest path: one script tag, a scenario simulator, the Free plan
  or a trial.
- **Growth marketer:** the room draws a sankey of campaign pages (one brief to many persona and
  UTM pages) and A/B verdicts.
- **Hindi:** the shirorekha tuning, Hindi suggestion "tones", and "haan" at the door.

### 8.6 Build notes

- Astro + React Three Fiber islands. The field is **one InstancedMesh** of a 10-triangle wedge
  (20k instances on desktop, 4–6k on mobile), displaced in the vertex shader from a **GPU 2D
  damped wave equation** (ping-pong render targets). About **2 ms of GPU time**, so it holds
  60 fps even on integrated graphics.
- Sources are injected at the edges as Gaussian splats. The clearing is a signed-distance mask.
  Components sit on a CSS3D plane registered to the rising surface, so they stay live and
  accessible.
- Gold and silver are emissive tints in the shader, not post-processing bloom.
- LCP under 1.8 s from a pre-rendered still of the field. Under 150 KB of JS before WebGL.
- Reduced motion: the field holds still and states show only as light intensity and colour.
  Without WebGL: a CSS "room" with concentric rings and the Level 1 Companion.
- **Tap-to-talk is a first-class toggle** for open offices. The typed line is equally beautiful:
  every keystroke is a ripple.

### 8.7 Risks and guardrails

- **Silence can read as broken.** The breath must start within 1 s and the first caption must
  appear by 1.5 s.
- Many B2B visitors browse muted at work, so the typed-and-captions path must be first-class.
- Without strict art direction the field can read as a **music visualiser**. Keep the motion
  physical (finite wave speed, absorption) and tie every wave to a real event.
- The live "first reflection" meter will honestly show slow turns under launch load, so plan
  capacity first.
- Pair the consent copy ("audio isn't stored") with the transcript retention line, so it does
  not read as "nothing is kept".

### 8.8 Why it wins

It is radically reductive in a category full of noise: one material, one light, one shape, and
**the visitor's own voice as the camera move**. Juries reward that confidence. Every wow moment
is also an explanation, through physics anyone already understands. It is the cheapest concept
to build and the best on mobile, and *"the website heard me"* is an emotion no static site can
produce.

---

## 9. Concept F — MOLTEN: Solid. Liquid. Gas. Light.

> **Tagline:** *Your website is a conversation that cooled too fast.*
>
> **Logline:** Obsidian is lava that cooled too fast to crystallise, and a static website is
> knowledge that cooled too fast to hold a conversation. Set in a glass furnace, the visitor's
> voice is heat. It melts the site's obsidian slab into flowing molten glass (talks), casts the
> glass into diagrams (shows), lifts it as gold smoke (The Presence) and ends as pure
> incandescent light around the page (The Atmosphere).

### 9.1 The idea

**Phase change and blackbody radiation**, framed as **glassblowing and casting craft** rather
than a volcanic disaster. A caldera appears only in the cold open.

| In the furnace | In FluidBuddha |
|---|---|
| **Solid** obsidian | The static site, and the holdout baseline |
| **Liquid** glass | Level 1 *The Companion*, whose launcher and panel already *are* liquid light and molten-obsidian glass |
| **Gas**, gold smoke | Level 2 *The Presence*, the curl-noise smoke field |
| **Light**, incandescence | Level 3 *The Atmosphere*, where the page itself glows |
| Temperature on the blackbody ramp | Agent state: dormant (black) → listening (deep red, brief) → thinking (orange shimmer) → speaking (**gold**) |
| **Heat before flow**: radiant heat arrives at light speed, glass flows slowly | The acknowledgement in under a second, then the grounded answer |
| Molten glass flows only over real terrain | Grounding: the knowledge tree is the landscape |
| It crusts at a cliff edge | The 0.45 guardrail |
| Lava tubes: insulated channels, fast and almost free | The answer and audio cache |
| Crystal habit: the same melt cools into different crystals | Persona |
| Casting from typed moulds, with no cuts and no glue | Components built from safe typed blocks, never free-form UI |

### 9.2 Storyline

| Act | What the visitor sees | What the live product is doing |
|---|---|---|
| **I. Cold Open — The Slab** | A 35 Hz rumble. An 85 mm macro dolly crosses a polished obsidian monolith. Frozen inside it, like fossils in strata, are the parts of a typical website: a nav bar, a hero headline cut off mid-sentence, a "Book a demo" button. Engraved copy cools from gold to black: *"This is your website. It stopped talking the day you published it."* A crane back shows the slab alone. **One ember breathes in the stone.** It is Pragya's real launcher Aura. | Experiment enrolment runs first. **The holdout gets this act as a complete silent film**, the "solid" baseline. The Level 1 Aura (5.5 s breath) is the ember. A time-on-page nudge: *"Touch the ember, or just say hello."* |
| **II. Ignition — Heat Before Flow** | Tap the ember and the consent arrives as a heat-proof glass card. The visitor speaks, and silver heat spreads along conchoidal fractures, driven by their voice. **In under a second the stone glows before anything moves**: *"ack 0.6 s"*. *"Heat travels at the speed of light. Glass doesn't."* Then the grounded answer lands and molten gold runs. Interrupt, and the flow **quenches** with a hiss of water on hot glass. | Consent. Voice detection with pre-roll. The concurrent acknowledgement. Sentence-streamed speech. Barge-in. The product's own silver-and-gold language. |
| **III. Flow — The Terrain of Truth** | A long-lens tracking shot follows a molten river across a landscape that is **this site's real knowledge tree**: documents as mountains, sections as ridges, chunks as pebbles. *"Do you work with Shopify?"* The glass runs down the Integrations valley and pools at the matching chunk. The strata light up as Sources, and the badge reads like a pyrometer: "grounded · 87 % match". The Honest Dare (a truly off-site question): the glass reaches a cliff edge and **crusts over**. | Grounded retrieval (top 5). The 0.45 guardrail. Clickable citations. Navigation snaps to valid routes, so there are no 404s. |
| **IV. Casting — Every Answer Takes a Shape** | *"Show me how a voice turn works."* Molten glass is cast into a flowchart: glass ingots for nodes, glowing channels for edges. A kiln hum covers the wait: the product's own 1.5 s filler tone, re-sampled. Then the ROI calculator rises as a **Giant's Causeway of hexagonal basalt columns**, carved *illustrative* at the base. The sliders raise the columns. *"Actually, 25 seats"* re-melts only the affected columns. Copy: *"No cuts. No glue. Every cast from a typed mould."* | Typed generative components (JSON, never HTML). Audio waits for the render. The filler tone. A live reaction after 0.7 s. In-place patching. INR formatting. The 3D cast and the real component read the same JSON. |
| **V. Crystal Habit** | *"I'm the CFO."* A 300 ms blurred veil runs across the frame and the whole world **recrystallises** into amber basalt columns telling the payback story. *"Actually, I run engineering."* The melt turns into **blue-black bismuth hopper crystals** whose geometry *is* the real component diagram. The camera holds still: a regrade, not a cut. | Adaptive persona (0.6 to switch, a lock on self-identification). `data-fb-persona` → `onSetPersona` → LUT, materials and copy. |
| **VI. Lava Tubes — It Gets Cheaper as It Learns** | A cutaway lava tube. Left: a new question carves a fresh channel, bright and slow, with a ₹ cost ticker climbing. Right: a much-asked question shoots through an insulated tube and arrives **instantly, with the same audio, waveform for waveform**, while the cost needle barely moves. A plaque shows this site's real cache hit rate. | Exact and semantic replay (at least 0.92), byte-exact audio, pinned answers shown as reinforced tubes, analytics. |
| **VII. Evaporation — Solid, Liquid, Gas, Light** | The pooled gold boils off as smoke and the film **hands over to the product's real Level 2 Presence field**: 8k–16k particles, gold and silver, reacting to the live voice. The smoke thins. Then **the browser viewport's own edges begin to breathe**: Level 3. A rim light, a spotlight ringing the pricing section for 4.2 s, glass captions. *"Solid. Liquid. Gas. Light. One script tag."* | The three design levels from one script, switched live. The Level 2 field is the product's own shader, not an imitation. |
| **VIII. Set in Stone** | *"Book me a demo."* A glowing glass tablet forms with the meeting details. **"Haan"** cools it to obsidian with the link engraved. "Send me this" cuts a **core sample**: the recap, with strata of answers. Finale: Pragya composes a whole page for this visitor's segment, and it cools into a *new* obsidian slab, **this time with a breathing ember**, a callback to Act I. The site's own A/B test of design levels reports its verdict. | Visitor-confirmed actions. Recap pages. Exit-intent and return-visit triggers. Extreme-tier page composition. Live takeover. A variant A/B test of the design level, run on the site itself. |

### 9.3 Look and sound

- **Look:** macro geology photography crossed with furnace craft. Obsidian with
  conchoidal-fracture normals, a clearcoat and a thin-film sheen. Molten glass with a viscous
  meniscus and a crust that forms as it cools. Basalt and bismuth. **The glass's own emission is
  the only key light.** Heat haze through screen-space refraction. Gold dominates the ramp, and
  red is reserved for the brief listening state.
- **Palette:** Obsidian `#07070A` / `#121015` · Ash `#2A2A2E` · blackbody ramp `#3A0A05 →
  #B3261E → #E8641E → #F2A93B → #FFD98A → #FFF4D6` · Pragya Gold `#C9A24A` / `#D8A93A` ·
  Visitor Silver `#C9CED6` · CTO lattice `#0E1C2B` / `#5FA8D3`.
- **Type:** a high-contrast serif (Canela or PP Editorial New) whose headlines *cool* from gold
  to black, and a mono for readouts (match %, kelvin, ₹). In Hindi, **the shirorekha becomes a
  glowing channel of molten glass** that the letters hang from.
- **Motion:** viscous and heavily damped, with nothing snapping. Long lenses (85–135 mm), slow
  dollies, and cuts only when narration ends.
- **Sound:** a 30–50 Hz caldera sub. Granular crackle from real recordings of cooling glass and
  obsidian knapping. A flow drone whose pitch tracks temperature. A quench hiss on barge-in and
  a Doppler whoosh for a cache replay. Pragya's voice is warm, dry and close-miked, with the
  score ducked 12 dB beneath it. The Hindi cut adds a tanpura drone.

### 9.4 Signature moments

1. **Your voice melts the website**: the fossilised site inside the obsidian cracks with silver
   heat, and gold answers within a second.
2. **The basalt-column ROI calculator**: data visualisation as geology.
3. **The crust of honesty**: grounding as spectacle.
4. **The lava-tube dive**: the same question twice, the second instant and almost free.
5. **Recrystallisation**: one sentence turns the whole world from amber basalt to blue bismuth
   without a cut.

### 9.5 Persona and language cuts

- **CFO:** amber basalt and money-first copy. Illustrative payback, cost per conversation
  (about ₹16.50 on Growth, ₹12.50 on Scale), the holdout, and the weekly digest arriving as a
  stone tablet.
- **CTO:** blue-black bismuth and quartz. Act IV casts the component diagram (one WebSocket,
  lean versus heavy routing, sentence-ahead speech synthesis, the cache). Act VI shows p50/p95
  latency. Trust is spelled out honestly: SSO, MFA, audit, self-hosting with an offline licence,
  and BYO model *with the note that speech and embeddings stay on Google Vertex*.
- **Founder:** a polished obsidian mirror. Live in an afternoon, one script tag, a demo booking.
- **Marketer:** Insights shown as mineral veins in the rock, and campaign landing pages as a
  quarry of slabs, each cut for a segment.
- **Hindi:** engraved glyphs re-melt into Devanagari. *"नमस्ते, मैं प्रज्ञा हूँ"*. "Haan" confirms
  the booking.

### 9.6 Build notes

- Next.js + React Three Fiber + Theatre.js + GSAP ScrollTrigger + Lenis. MeshPhysicalMaterial
  obsidian. A **heat field** in a 512² ping-pong FBO (diffusion plus advection, with splats
  from voice and pointer) drives blackbody emission and displacement.
- **The flow** uses baked flow maps over a knowledge-terrain heightmap generated at build time,
  plus a cheap runtime flow front, rather than a full shallow-water simulation.
- The basalt is an InstancedMesh of up to 2k hex prisms whose heights come from the
  roi_calculator JSON.
- **Only one Three.js.** The Level 2 smoke beat is rendered inside the site's own scene with
  the SDK's shader, or the SDK particles bundle is shipped as a build that shares Three.js.
  Never load two copies.
- 60 fps on M1 or RTX-class machines, a 30 fps floor on mid-range Android, at most about 150
  draw calls. On mid-tier phones, baked AV1/HEVC video loops replace the simulations. Reduced
  motion uses key stills with cross-fades. Photosensitive flicker stays under 3 Hz.

### 9.7 Risks and guardrails

- **Senior WebGL team and a real budget.** It is the most simulation-heavy concept.
- Heat must read as craft, not destruction. Red and orange read as warnings, so gold must win.
- Fluid simulations are common in generative art, so the knowledge-terrain and design-level
  mappings must carry the originality.
- The Honest Dare must be a *truly* off-site question. "Do you speak Tamil?" is **not** one,
  because the site's own content can answer it ("English and Hindi").

### 9.8 Why it wins

It is one physically true metaphor: obsidian really *is* lava that cooled too fast. That single
idea explains the whole product, **including the three design levels**, which no other concept
turns into the story. It has the tightest fit with the brand's existing materials (molten
obsidian, liquid light, gold and silver). Buyers leave with a sentence they will repeat: *"my
website is cooled lava."*

---

## 10. Concept G — THE LIQUID INTERFACE: It Only Reflects What's Real

> **Tagline:** *One drop. Liquid until you ask.*
>
> **Logline:** A dark void. One droplet of liquid metal falls in slow motion and splashes, and
> the splash *becomes* the website: nav bar, cards and buttons crystallise out of the fluid.
> Nothing Pragya shows you is pre-drawn. When an answer needs a picture, it pours itself into
> shape. And like all liquid metal, the interface has no light of its own. **It can only shine
> with what it reflects, and the only thing in the room to reflect is the site's own content.**
> Ask it something the site doesn't cover, and the metal goes dull. At the end, the whole
> interface draws back into a single gold droplet that waits in the corner of the screen: one
> drop, on your site.

*(This is the client's own concept, refined. The original idea is kept intact: the droplet
birth, UI crystallising from fluid, a raymarched / metaball technique, a generated-video option
and a "taste" toggle. The same creative director who scored the slate reviewed it twice. The
first refinement scored **42/60** and the second **43/60**. The review's view is that the
page-lit studio, where grounding becomes optics, is a real and ownable idea. It also judged
that the liquid-chrome look is a well-worn trope, and that the act structure still followed
MOLTEN (F) beat for beat. This version answers that review. It rebuilds the structure around
the two things only this concept has, **the ribbon tour through the page-lit studio** and **the
dull-metal grounding**. Taste now changes the light rather than the metal, and the close uses
the droplet bookend instead of a freeze. It also corrects the product details the review found.
This version has not been re-scored.)*

### 10.1 The idea

The brand is literally called **Fluid**Buddha, and the widget's own language is "liquid light".
This concept takes that word at face value: **an interface that is liquid until someone asks
for something, and set only while it is useful.** That is what generative UI is.

What lifts it above generic liquid chrome is a physical fact. **Liquid metal is only as
beautiful as what it reflects.** In a product shoot, the metal's shape comes from the light
boxes around it. Here, **the light boxes are the website's own pages**: every page of the site
hangs in the darkness as a soft rectangular light panel with its title, and the metal reflects
them. So the interface literally *cannot shine* with anything that isn't on the site. That is
grounding, turned into optics. **Everything in the film is told through light and reflection,
not through changes to the material.**

| In the liquid-metal studio | In FluidBuddha |
|---|---|
| **One droplet** falling into the void | One `<script>` tag. The droplet's surface reflects the real install line. |
| The splash freezes and crystallises into a website | The agent composes UI at runtime (components, and whole pages on the Extreme tier) |
| **Liquid until you ask** | Nothing Pragya shows is pre-drawn. A component exists only when the conversation calls for it. |
| **The light boxes are the site's pages** | The per-site knowledge, built from the crawl |
| **A ribbon of metal that flows from panel to panel** | The guided tour: it moves only after each narration ends |
| The answer's surface **reflects the panels it came from** | Sources: you can see which pages lit the answer, and click them |
| **Nothing to reflect: the metal goes dull grey and slumps** | The 0.45 confidence guardrail and the honest "I don't know" |
| Surface tension holds only clean, known shapes | Typed components (13 built-in, plus the tenant's own typed custom components), never free-form HTML: *liquid, not lawless* |
| **Taste: the same metal under different light** | Persona: the segment changes which pages light the room and what Pragya emphasises |
| **Your "yes" is a drop too**: the card condenses into a droplet that falls to the team | A visitor-confirmed action, delivered as a lead to the business |
| **The droplet that stays** | The Level 3 summon mote, the agent waiting in the corner of the page |

### 10.2 Storyline

The film opens **as the site's guided tour**. In the product, the tour plays when the session
opens, in place of the spoken welcome (FR-WEL-05). So Act I is the tour's first stop, and the
ribbon tour of Act II is the spine of the film. Free conversation takes over from the moment the
visitor speaks.

| Act | What the visitor sees and hears | What the live product is doing |
|---|---|---|
| **0. The Drop** (cold open) | A true black void. A single droplet of liquid metal falls in extreme slow motion, turning gently. As it turns, its surface reflects one line of text, `<script src="…/loader.js" data-key="…">`. Title in the darkness: *"One drop."* A small prompt beneath it: *"Tap the drop to begin, sound on."* The visitor taps, and the drop lands. **The splash crowns.** | Experiment enrolment runs **first**, so holdout visitors get the Silent Film from frame one. The first frame is a static still for a fast LCP. The tap primes audio and connects the agent without opening its summon prompt: a small `FluidBuddha.start()` call **[new]**. The splash is a pre-baked fluid simulation played in the live 3D scene (see 10.6). |
| **I. The Splash Becomes a Website** (tour stop 1) | The crown of the splash **freezes mid-air**. A single specular flash runs around its rim, and it crystallises: the rim stretches into a nav bar, the tallest spikes flatten into three cards, and a bead at the centre hardens into a button. They are this site's real hero section, rendered as DOM, with the metal as their frame. The camera pulls back, and for the first time we see what the metal is reflecting: **dozens of soft light panels hanging in the dark, each one a page of this website**, its title just readable. Pragya speaks the first stop: one sentence of welcome. Copy: *"It only reflects what's real."* | The hero is a server-rendered `<section>`, so it is crawlable. The light panels are generated at build time from the site's own pages. The tour's stored narration plays, and Pragya's voice level drives a gold ripple across the surface **[new: level event]**. Captions use the Level 3 glass captions. |
| **II. The Ribbon** (tour stops 2–7) | The metal becomes a **liquid ribbon** that flows out of the hero and runs through the hanging panels, and the camera rides it. At each stop the ribbon flows into one panel. That page's section of the site comes forward and crystallises (*Talks*, *Shows*, *Acts*, *Grounded*, *Revenue*, *Proof*), and its panel burns brighter while Pragya narrates. The ribbon moves on **only after her last word**, holds for a breath, then flows. The panels already visited stay faintly lit, so the studio fills with light as the tour goes on. | The guided tour: 6–9 stored stops, each move made after its narration has finished, plus 450 ms. Each stop's `scroll_to` or `navigate` is caught by `onScrollTo` / `onNavigate` and drives the camera spline instead of a plain scroll. The Level 3 spotlight rings each section for about 4.2 s. |
| **III. Interrupt the River** (talks) | At any moment the visitor can speak. The ribbon **freezes mid-pour, trembling**, and silver capillary ripples spread from the bottom of the frame in time with their voice. Within a second a single **gold ripple** runs back: the acknowledgement. Under the surface, metal gathers into a soft, shapeless swell while the answer is being composed. | Consent card (*Allow microphone* / *Type instead*). Barge-in stops the tour. Voice detection with a 400 ms pre-roll. The concurrent acknowledgement. Thinking and speaking states **[new: state event]**. The swell fills the thinking time, so the visual has somewhere to go while the answer is prepared. |
| **IV. Liquid Until You Ask** (shows) | *"How does this work on my site?"* The swell holds, pulsing, until the answer's component arrives. Then, in **one cold snap of under 120 ms**, it crystallises into the exact shape: mercury beads joined by thin liquid bridges, *one script tag → crawl → live agent*. The real flowchart component sharpens in registration over it, and **Pragya's sentence follows the snap**. A question the site has answered many times snaps straight into its shape, with no swell at all. | Generative components from typed JSON. The snap is triggered by the component event **[new]**, and speech waits for the render (audio/UI sync; a soft filler tone after 1.5 s). A cache replay (match of at least 0.92) skips the swell **[new: replay flag]**. |
| **V. It Only Reflects What's Real** (grounding, the heart of the film) | As Pragya answers, **the panels her sources came from flare**, and their reflections visibly slide across the surface of the answer: you can read *Pricing* or *Security* in the metal. The badge "grounded · 89 % match" is etched beside them. Tapping a reflection opens that page. Then the Honest Dare: a chip offers an off-site question. The swell begins to rise, but **no panel lights. The studio stays dark. With nothing to reflect, the metal turns a dull, flat grey, cannot hold a shape, and slumps back into the pool.** Pragya: *"I don't have that on this site. I can connect you with the team."* Copy: *"It can't shine with what isn't there."* | The 0.45 guardrail, produced by the live agent itself. The panels that flare are the real citations from the grounding payload **[new: grounding event]**. Clickable Sources. |
| **VI. Taste** (personalisation: the light changes, not the metal) | A row of small liquid **taste drops** floats at the edge: *Engineering*, *Finance*, *Founder*. The visitor taps one, or simply says *"I'm the CFO"*. **The metal stays the same. The light changes.** The studio rearranges itself: the panels that matter to that visitor drift forward and brighten (for Finance: *Pricing*, *Proof*, *ROI*; for Engineering: *Architecture*, *Security*, *Self-host*; for Founder: *Install*, *Trial*), the others recede into the dark, and the colour temperature of the room shifts. The metal now reflects a different website, the same site seen from that visitor's side. The site's own cards and the 3D frames also change their corner geometry. Pragya's next answers change emphasis with it. | Saying the role out loud is the product's native behaviour: the agent locks the persona on self-identification. Tapping a drop calls a small new SDK method, `setPersona(id, { explicit: true })` **[new]**, which locks the persona without putting words in the visitor's mouth and without the SDK's echo veil, so there is no double blur. The site re-lights on the tap and reconciles when the `set_persona` event arrives. Inside `onSetPersona` it sets `data-fb-persona` itself and maps it to the panel layout, light temperature and corner-radius tokens. Personalisation is by segment, as the visitor chose. |
| **VII. Your "Yes" Is a Drop Too** (conversion) | *"Want me to set up a walkthrough? Check the card and say yes."* A liquid card forms with the details the visitor gave. The visitor says **"haan"**. The card **condenses into a single gold droplet**, the same drop that opened the film, and it falls out of the bottom of the frame. A beat later a soft ripple rises back from below: *"Sent to the team."* "Send me this" turns the conversation into the recap page. If a teammate is watching live visitors, a second, warmer stream enters the pool: *"Ananya from the team joined"*, with an optional browser call. | Visitor-confirmed actions with voice confirmation ("haan", "yes", "ठीक है"). On confirmation, the meeting action opens the team's booking page pre-filled, and the lead reaches the team (scoring, signed webhook, Slack alert for hot leads). Masking: Pragya says "your email". Recap page. Live takeover and WebRTC voice handoff, which start when an operator takes over. |
| **Coda — The Droplet That Stays** | The panels dim one by one. The whole interface draws back into the pool, the pool contracts, and everything gathers into **a single droplet that cools to Pragya gold** as it rolls to the bottom-right corner. It comes to rest **exactly where the real summon mote lives** and hands over to it. It breathes. *"One drop. On your site."* The install snippet appears, with *"Or ask this site from your own AI assistant"* (MCP / `llms.txt`). The Credits are etched in the droplet's reflection. If the pointer heads for the close button, the mote brightens and Pragya offers to send the recap. | The real Level 3 summon mote (a small breathing gold dot in the corner; tapping it opens the summon prompt). The exit-intent trigger with a composed opener. The site's own MCP endpoint and `llms.txt`. |

**The Silent Film.** Visitors in the holdout get no widget, so from the first frame they get a
fully pre-rendered cut of the same story, played as a scroll-driven image sequence: the drop, the
splash becoming the website, the page-lit studio, the ribbon tour with printed narration, and the
gold droplet at the end. The same cut serves reduced-data and no-WebGL visitors. Mobile visitors
get the live 2.5D version (10.6), so they keep the real agent. The client's generated or
pre-rendered video route therefore has a real job.

**Linking to a taste.** For ads and outbound emails, the cinematic site can open already lit for
a segment by mapping a link parameter to a variant whose starting persona is that segment (the
variant route works today), or through a direct `startPersona` option **[new]**. FluidBuddha's
own generated campaign pages (`/p/…`) remain a separate product feature, shown in the Finance
cut.

### 10.3 Look and sound

- **Look:** high-end product photography in a black studio, where **the studio lighting is the
  site's own content**. The light panels are soft, slightly warm rectangles at different depths,
  each showing its page title in faint type, so their reflections stretch and curve across the
  metal. The metal itself never changes colour (except to go dull). Thin-film **iridescence** stays
  in a narrow band between Pragya gold and visitor silver, never a rainbow. Restrained
  post-processing: bloom on specular highlights only, depth of field during the slow-motion drop,
  a fine film grain, and chromatic aberration only at the very edge of the frame during fast
  moves. Post-processing is applied to the WebGL layer only, so **DOM text always stays sharp**.
- **Palette:** Void `#050506` · Studio Grey `#16171A` · Panel Light `#F3EFE7` · Mercury
  `#C9CED6` / `#E9EDF2` (the visitor) · Pragya Gold `#C9A24A` · Dull (ungrounded) `#5B5E63` ·
  thin-film sheen `#D8A93A → #9FB8C9`. Taste is expressed as light temperature (Finance 3600 K,
  Founder 4500 K, Engineering 6500 K) rather than metal colour.
- **Type:** a precise neo-grotesk (PP Neue Montreal or Söhne). Headlines are rendered as
  signed-distance text in the same shader as the fluid, so a headline can melt into the pool and
  set again. Mono for readouts. In Hindi, Devanagari captions appear on the light panels
  themselves, so the metal reflects the Hindi too.
- **Motion:** two speeds only. Liquid moves are slow, heavy and viscous. Crystallising is
  instant, a cold snap of under 120 ms. Nothing bounces like rubber. The camera dollies along the
  ribbon; it never cuts while metal is moving.
- **Sound:** a near-silent studio. Viscous liquid-metal foley recorded from safe substitutes
  (gallium, heavy oils, glass beads): low, glassy, with weight. Each crystallising snap is a tiny
  crystalline *tick*, and each panel that lights gives a soft, warm hum. The dull, ungrounded
  slump is the only dead, unresonant sound in the piece. The score is sparse electronic texture
  with a **santoor**, the Indian hammered dulcimer whose struck notes sound like falling water.
  It gives the piece an India-first sonic identity without any sacred association. The santoor
  plays the droplet motif at the start, again when the visitor's "yes" falls, and resolves on the
  final droplet. Pragya's voice is dry and close, and the score ducks under it.

### 10.4 Signature moments

1. **The drop**: the install line reflected in a single falling droplet, and the splash that
   freezes into a website.
2. **The studio is the website**: the camera pulls back to reveal that every reflection in the
   metal is a page of the site, and the tour ribbon flows from page to page.
3. **It goes dull**: asked something off-site, no panel lights, and the metal turns flat grey and
   slumps. Grounding as optics.
4. **Taste changes the light, not the metal**: one tap and the studio rearranges itself, so the
   same metal reflects the site as that visitor would see it.
5. **Your "yes" is a drop too**: the confirmed card condenses into the same droplet that opened
   the film and falls to the team.

### 10.5 Persona and language cuts

- **Engineering (CTO):** cool 6500 K light. *Architecture*, *Security* and *Self-host* panels
  lead. Component diagrams first (one multiplexed WebSocket, lean versus heavy routing, audio
  waiting for the render). The coda leads with the install snippet and the MCP endpoint.
- **Finance (CFO):** warm 3600 K light. *Pricing*, *Proof* and *ROI* panels lead. An
  illustrative ROI calculator, cost per conversation (about ₹16.50 on Growth), replay economics
  and the holdout. The confirmed action is a quote request with PDF. A short beat shows
  FluidBuddha's generated campaign pages: one brief, many landing pages.
- **Founder:** *Install* and *Trial* panels lead. The fastest path: one drop, live in an
  afternoon, a scenario simulator, a trial.
- **Hindi:** Pragya narrates in Hindi, and the panel titles and captions switch to Devanagari,
  so the metal reflects Hindi. "Haan" sends the drop.

### 10.6 Build notes: real-time, generated video, or both

The client proposed two routes. They are not alternatives. **Use both, each where it is strong.**

| | **Route 1: real-time fluid** (raymarched SDF + metaballs) | **Route 2: generated or pre-rendered video**, played as a scroll-driven frame sequence |
|---|---|---|
| **Strengths** | Reacts to the live agent: voice, tour, components, persona, cache, guardrail. That is the whole point of dogfooding. Infinite variation. Light payload. | Unlimited visual quality. Cheap to iterate. Predictable on every device. |
| **Weaknesses** | Raymarching costs GPU time. Needs a strong shader developer. | **Cannot react** to Pragya, the visitor or the persona. Heavy payload (8 s at 30 fps is 240 frames; at about 80 KB per AVIF frame that is about 19 MB). Current generative video models struggle to keep fluid physics consistent from frame to frame and garble text and UI. Clear rights to any generated output are needed. |
| **Use it for** | **The whole live site**, desktop and mobile (2.5D on mobile). | **The Silent Film** (holdout, reduced-data and no-WebGL visitors) and **styleframes** during concept development. |

**The cold open, in one renderer.** Simulate the drop and splash offline in a fluid tool (for
example Houdini FLIP), **bake it to a vertex animation texture** and play it inside the same
React Three Fiber scene, with the same material and the same light panels as everything after it.
The one hard moment is the switch from the baked splash mesh to the raymarched SDF cards. It
happens at the crown freeze and is **masked by the specular flash** that runs around the rim, as
the mesh is swapped for SDF primitives fitted to the crown's frozen shape. Budget dedicated
look-development time for this one transition, because it is the hero's most-watched frame.
Generative image models remain useful for styleframes and for look-development of the panel
lighting.

**Real-time technique:**

- **The key idea: one "liquidity" parameter.** Each UI element is a rounded-box signed distance
  field (its corner radius is a uniform). The fluid is a set of metaballs. Everything is blended
  with a smooth minimum whose blend factor `k` *is* the liquidity. A high `k` melts everything into
  one pool. Dropping `k` towards zero separates the shapes and **crystallises them into crisp
  cards**. At that moment the real DOM component fades in on top in exact registration, and the
  metal becomes its frame. One number tells the whole story, from liquid to interface. (The
  widget's own built-in components keep their fixed styling inside their shadow DOM, so the taste
  geometry applies to the site's own cards and the 3D frames.)
- **Reflections are the grounding.** The light panels are textured quads arranged in the scene and
  captured into a dynamic environment probe, re-rendered only when a panel brightens, dims or
  moves. A cited panel's emission is raised from the grounding event. When nothing is cited, the
  environment is dimmed and the metal's roughness is raised, which is the "dull" state. Taste
  re-arranges the panels and re-renders the probe once.
- **Timing follows the product.** The shapeless swell plays during the thinking state. The snap to
  a specific form happens on the component event, and speech follows the SDK's render. The tour
  ribbon moves on the SDK's own "narration finished plus 450 ms" move.
- Raymarched in a bounded region, not full screen, at half resolution with temporal upscaling.
  At most about 32 primitives live at once. Thin-film interference for the iridescence.
- **Mobile:** a live 2.5D version, a height-field fluid with screen-space normals and a
  simplified panel environment.
- **Reduced motion:** no dolly and no pouring. Forms appear with a short cross-fade, and taste
  re-lights instantly. **No WebGL:** the Silent Film frames plus the real widget.
- Stack: Next.js (SSR content routes for SEO, citations and the agent's navigation targets) +
  React Three Fiber + Theatre.js + GSAP ScrollTrigger + Lenis. The widget runs at Level 3, so
  Three.js loads only once.
- Budgets: LCP under 2.0 s from the static first frame, under 200 KB of JS before WebGL, 60 fps
  on M1 or RTX-class laptops, 30 fps on mid-range Android, adaptive resolution through drei's
  PerformanceMonitor.

### 10.7 Risks and guardrails

- **Liquid chrome and metaballs are a well-worn look** in award-site culture and perfume ads. The
  review scored originality 6/10 for this reason. The concept stands out only through its own
  ideas: the studio made of the site's pages, the ribbon tour through it, the metal going dull
  when nothing is grounded, taste as light, and the splash that becomes a website. These must
  survive every round of cuts. Without them it is a showreel.
- **Overlap with MOLTEN (F).** Both are liquid. MOLTEN is hot, elemental and about the product's
  states (the design levels), told through changes to the material. The Liquid Interface is cool,
  precise and about **the interface itself**, told through light and reflection. **Choose one;
  they should not both go forward.** The review's alternative: graft this concept's drop cold open
  and page-lit studio into MOLTEN or KOLAM.
- **Product additions:** `FluidBuddha.start()`, `setPersona(…, { explicit: true })` and the
  director-bridge events (§11) are small but required.
- **Legibility:** grain, chromatic aberration and depth of field must never touch DOM text or
  live components.
- **Iridescence and flashing:** keep thin-film shifts slow, and any brightness change under 3 Hz.
- **Generated-video rights:** if any generative model output ships, it needs clear commercial
  rights, and it must never show fabricated customers, logos or results.
- **Raymarching cost:** keep strict bounds on primitives and the raymarched area, and fall back to
  2.5D early.

### 10.8 Why it wins

It is the most direct visual for the product's central promise. **Generative UI becomes a
material**: an interface that is liquid until you ask, and set only while it is useful. Its
studio is lit by nothing but the site's own pages, so **"grounded, with sources" stops being a
claim and becomes optics**: the interface visibly cannot shine with what isn't there. It grows
out of the brand's name and its "liquid light" language. And the droplet gives FluidBuddha an
icon that is also the install story and the close: *one drop* to install, *one drop* for every
"yes".

---

## 11. Shared engineering prerequisites

Every concept depends on a few small additions. Schedule them first, whichever concept is
chosen. Most of them are features customers would want anyway.

| # | Item | Why | Size |
|---|---|---|---|
| 1 | **The director bridge (SDK) [new].** Public window events: `fluidbuddha:state` (dormant / listening / thinking / speaking), a throttled `fluidbuddha:energy` or `level` event `{in, out}`, `fluidbuddha:component` (the typed JSON and bounding box of each rendered component), `fluidbuddha:render`, `fluidbuddha:grounding` and a **cache-replay flag**. | The SDK computes most of these internally (the Aura already uses the levels), but today it only emits navigation, scroll and a few housekeeping events. Without these, no 3D scene can react to Pragya. | Small (SDK) plus a small server change for the replay flag |
| 2 | **Read-only public counters [new]**: cache hit count for pinned questions, the site's holdout verdict and interval, anonymised Insights categories, agent-traffic counts. | "Real numbers or none". The public site cannot call the console API. | Small (an endpoint or a nightly static JSON export) |
| 3 | **The Credits [new]**: a session receipt built from the events above, which becomes the recap. | The cross-concept proof device. | Small to medium |
| 4 | **Launch capacity.** More replicas, top questions pre-warmed and pinned, a daily spend cap and cost alerts. | The recorded load test met time-to-first-audio at about 50 concurrent voice sessions per replica. An award feature or Product Hunt spike will exceed that. | Operations |
| 5 | **Demo tenants** (for B, and for D's sandbox). | Scripted story content must never enter fluidbuddha.com's own knowledge base. | Configuration |
| 6 | **Persona set and tour outline** for fluidbuddha.com in the console (cto, cfo, founder, marketer, agency), and the tour stops that sequence the film. | This is the "script" the product performs. | Content |
| 7 | **The holdout and one variant test** running on fluidbuddha.com from day one. | The Silent Film and the published verdict. | Configuration |
| 8 | **Host control calls [new]**: `setPersona(id, { explicit: true })` locks a persona chosen through the site's own UI, without sending a visitor turn and without a second veil. `FluidBuddha.start()` primes audio and connects inside the host's own gesture at Level 3, without opening the summon prompt. A `startPersona` option sets the opening persona from a link. | Lets a site's own controls (G's taste drops and tap-the-drop, any concept's persona chips or "begin" gesture) drive the agent honestly. Today a Level 3 host can only call `ask(text)`, which would put words in the visitor's mouth, and the starting persona comes only from a variant or the site default. | Small (SDK plus one server message) |
| 9 | **Optional "hold render" hook [new]**: lets the host delay the render acknowledgement (with a cap) until its own 3D transition has landed. | Speech waits for the SDK's DOM render, which happens moments after the component arrives. Any concept that wants a long flight or pour to finish *before* Pragya speaks (C's flats, A's flour) needs this. Otherwise, choreograph a fast snap on the component event, as G does. | Small (SDK) |
| 10 | **Start the tour on request [new]**: let the visitor (or a chip) start the stored guided tour mid-conversation. | Today the tour plan is sent only when the session opens, in place of the welcome. Concepts A, C and D stage a tour on request; G and F open with it instead. | Small (server plus SDK) |

---

## 12. Scorecard and comparison

Scores are the creative director's, out of 10 per criterion and 60 in total. For A–F they are for
the pitched base concept, before the improvements described above, and merged concepts show their
base. G was scored after refinement, which flatters it slightly against the others.

| Concept | Originality | Cinematic power | Product truth | Dogfooding | Buildability | Brand fit | **Total** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| **A — KOLAM** | 9 | 8 | 9 | 9 | 6 | 9 | **50** |
| **E — ANECHOIC** | 9 | 7 | 9 | 9 | 8 | 7 | **49** |
| **F — MOLTEN** | 7 | 9 | 9 | 8 | 5 | 9 | **47** |
| **C — PLACES, PLEASE** (CUE base; SUTRADHARA's threads scored 48) | 8 | 7 | 9 | 9 | 6 | 7 | **46** |
| **B — 11:58** (LOOP base) | 8 | 8 | 9 | 8 | 5 | 6 | **44** |
| **D — CAST** (PLASTER base, before the Pompeii reframe) | 8 | 7 | 9 | 10 | 4 | 5 | **43** |
| **G — THE LIQUID INTERFACE** (client concept; second refinement. The first scored 42. The current version answers the second review but has not been re-scored.) | 6 | 8 | 8 | 8 | 5 | 8 | **43** |

**How they differ:**

| | A KOLAM | B 11:58 | C PLACES | D CAST | E ANECHOIC | F MOLTEN | G LIQUID |
|---|---|---|---|---|---|---|---|
| **Tone** | Serene | Tense | Playful | Personal | Austere | Epic | Sleek, cool |
| **Core mechanic** | A drawn line | Time and rewind | Rigging cues | The onboarding pipeline | Wave physics | Phase change | Liquidity and reflection |
| **Hero truth** | Grounding | Learns and proves | Site = product | Your own site, live | Hears you | Three design levels | Generative UI, grounding |
| **Primary audience** | All, brand-led | CFO / CMO | All, jury-led | Founders, agencies | All, tech-curious | All, spectacle-led | All, product-led |
| **India-first signal** | Strongest | Medium | Medium | Medium | Medium (tanpura, shirorekha) | Medium | Light (santoor, liquid shirorekha) |
| **Mobile** | Medium | Good (story cards) | Good | Medium | **Best** | Weakest (video fallback) | Medium (live 2.5D) |
| **Backend work** | Low | Medium (demo tenant) | Medium (Extreme tier) | **Highest** | Low | Low | Low |
| **Real-time 3D effort** | High | High | Medium | Medium | **Lowest** | **Highest** | Medium–high (bounded raymarch) |
| **Biggest risk** | Cultural care, logo | Narrative complexity | Composition latency | Abuse and cost | Reads as a visualiser | Budget, mobile | Liquid-chrome trope; overlap with F |

---

## 13. Ideas from the concepts that were not shortlisted

These concepts were not shortlisted, but each one has an idea worth keeping. Several are
already folded into the concepts above.

| Concept | Lens | The idea worth keeping | Where it went |
|---|---|---|---|
| **BAOLI: The Descent** (a 13-storey crane down an Indian stepwell) | Myth | The **echo before water**: the acknowledgement close and dry, the answer with a deep tail. Also **running a design-level A/B test on the site itself**. | The reverb went to KOLAM; the design-level test went to CAST and MOLTEN |
| **SUTRADHARA: Holder of the Threads** (shadow puppetry) | Myth | **Visible gold threads tied to the real `navigate` / `scroll_to` / `set_persona` events**, and "Reveal the Threads" as a backstage event log for CTOs. | PLACES, PLEASE (labelled fly ropes; raise the scrim) |
| **NIGHT SHIFT** (a one-take thriller of a 2 a.m. buyer) | Film | A clock seeded from local time, the turn to camera, the exit-intent mirror, and **credits listing only the events that fired**. | 11:58, and The Credits in every concept |
| **NADA: Every Answer Has a Shape** (cymatics, sand on a plate) | Matter | **Field noise = 1 − confidence**, and the **ultrasonic band** for AI-assistant traffic. | ANECHOIC |
| **FOLD: One Sheet, No Cuts, No Glue** (origami) | Matter | **"No cuts, no glue"** as the visual law of typed components, and the recap unfolding into a crease pattern. It is also the **runner-up swap for MOLTEN** if mobile and budget come first. | MOLTEN's casting copy; CAST's catalogue |

---

## 14. Recommendation and next steps

**The creative director's pick: A — KOLAM.** It is the only concept where one image does
everything. The single line is the brand mark, the grounded answer, the honest "I don't know",
the navigation path and the closed sale on "haan". It is distinctly Indian without being
touristy, and it makes the truth that is hardest to sell (*it admits when it doesn't know*)
into the most memorable shot. It is the strongest bet for awards and the most durable brand
asset.

**If the constraints are different:**

- **Small team or fast timeline:** choose **E — ANECHOIC**. It is the cheapest to build, the best
  on mobile, and the boldest.
- **Pipeline matters more than trophies:** choose **D — CAST**. The visitor's own site, woken, is
  the highest-converting moment on the slate.
- **A CFO/CMO audience and a story to retell:** choose **B — 11:58**.
- **Maximum spectacle and the closest fit to the existing brand materials:** choose **F — MOLTEN**.
- **The purest "the site is the product" piece for a jury:** choose **C — PLACES, PLEASE**.
- **The most direct visual for generative UI, and a product-film look:** choose **G — THE LIQUID
  INTERFACE**. Choose either G or F, not both. If another concept wins, G's drop cold open and its
  page-lit studio (grounding as reflection) can be grafted into it, most naturally into F or A.

**Once a concept is chosen, the next deliverables are:**

1. **Creative treatment.** The final storyline, the script for every line Pragya speaks in
   the tour, the copy deck, and the persona and Hindi cuts.
2. **Storyboard and animatic.** Shot by shot, with camera, timing, the product event that
   triggers each beat, and the fallback for each beat.
3. **Styleframes.** 6–8 key frames, a look-development test of the hero material (flour, foam,
   obsidian, plaster, stage or liquid metal), and the type and colour system.
4. **Sound brief.** The composer and foley direction, the WebAudio graph, and the ducking rules.
5. **Technical spike (2–3 weeks).** The director-bridge SDK events, one hero scene at target
   frame rate on a mid-range Android, the tour-driven camera, the persona regrade, and a load
   test of the launch capacity plan.
6. **Production plan.** Team, timeline, budget, asset pipeline, accessibility and performance
   budgets, and the award-submission calendar.
