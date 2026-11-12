# Design audit and rebuild (12 November 2026)

> Scope: every page of `fludi-buddha-website/web`, the four worlds (`/`, `/for/saas`,
> `/for/education`, `/for/enterprise`) and the content pages (product, solutions, industries,
> developers, trust, pricing, demo, legal, 404).
> Brief: the look was not award level; the header, footer and structure were inconsistent; the
> default film was not good enough; every world must use its colours 60 / 30 / 10 (main, secondary,
> gold); each world must feel unique with its own wow moment; and the site must stay on the
> Buddha Cognitive Lab design system (`C:\Workspace\Development\buddha-cognitive-lab-design-system`).
> Method: the code was read in full and every page rendered in headless Chrome at 1440 x 900 and
> 390 x 844, at many points of each film. Checked against the design system, against **taste-skill**
> and **impeccable**, and the default film was rebuilt in the **Watercolor Brush** style of
> **lemo-opuscar** (`styles/watercolor/STYLE.md`), in code.
> Follows on from [audit-2026-11-11.md](audit-2026-11-11.md).

**In one line.** The site now uses only the design system: its ink, paper and gold, its four
typefaces, its buttons, radii and motion. Each world is a different proportion and material of
those, measured at close to 60 / 30 / 10. The chrome is identical everywhere, and the default film
is a watercolour painted live in the browser.

---

## 1. What was wrong

| # | Finding | Where | Why it matters |
|---|---|---|---|
| 1 | Two header looks and two footer looks: the header and footer took each world's colours, so the logo, the bar and the buttons changed from page to page | All pages | The chrome is the one thing that should never change |
| 2 | The default film was an upscaled AI render: soft, low in detail, the same amber haze in every chapter | `/` | The first thing every visitor sees |
| 3 | Gold everywhere: the second half of most headings, the buttons, the glow, the film | Default and SaaS | The design system says gold is "precious, never flood fill" |
| 4 | No colour hierarchy: each world used one ground and gold, with no secondary colour, so sections were told apart only by thin lines | All worlds | Every section looked the same |
| 5 | The content pages showed frames of the default film in every world (an amber render on the bank's white page) | 17 content pages, pricing, demo | One world's pictures in another world's colours |
| 6 | Header 64 px and buttons, radii and easing that did not match the design system (72 px bar, pill buttons with a gold shadow, `cubic-bezier(.16,1,.3,1)`) | All pages | Drift from the system |
| 7 | Hero copy overlapped the picture on phones in the SaaS and Education worlds (headline, sub-line, two buttons and role chips under a 40 % picture) | 390 px | Unreadable first screen |
| 8 | Cool tints in places (a graphite with a blue cast in SaaS) | SaaS | The design system asks for warm imagery, "never cool/blue" |

An intermediate pass on 12 November gave each world new colours (indigo, pine, teal, oxblood) and
new typefaces (Cormorant, Outfit, Caveat). That broke the design system and was reverted in favour
of section 2.

---

## 2. The design system as the only source

From `project/colors_and_type.css` and the README of the design system:

| Token | Value | Used for |
|---|---|---|
| Ink | `#0a0908` (`--ink-950`), raised `#1c1916` (`--surface-2`) | The dark ground; the raised panes of the console |
| Paper | `#f6f2ea` (light canvas), `#fffdf9` (warm white) | The light ground, paper blocks, the film's sheet |
| Gold | `#edab48` (`--gold-500`), with `#fdc871` / `#a8722a` / `#7d551f` for text on dark and light | Actions, the answer, the closing band |
| Type | Roblox (logotype and hero words), Space Grotesk (headings), Hanken Grotesk (reading), JetBrains Mono (data, notes) | As the system's marketing kit |
| Radii | 4, 7, 11, 16, 22, 30, pill | Each world picks from this scale |
| Motion | `cubic-bezier(.16,1,.3,1)`, rises of 8 to 16 px, 160 to 640 ms | Entrances and hovers |

Noto Sans Devanagari is the one addition, for the Hindi showcase.

---

## 3. 60 / 30 / 10, per world

Each world is three colours from the system in a fixed proportion. A section picks its ground with a
tone class (`tone-main`, `tone-second`, `tone-gold`, `tone-ink`) and every other colour is derived
from that ground (`app/globals.css`).

| World | Main 60 | Secondary 30 | Gold 10 | Material |
|---|---|---|---|---|
| General | Ink | Paper | Gold | A watercolour on paper sheets hung on the ink; Roblox hero |
| SaaS | Ink | Raised ink | Gold | A console window drawn in characters; mono data; 7 px corners |
| Education | Paper | Ink | Gold | Photographs in ink frames; soft 30 px corners; large type |
| Enterprise | White | Ink | Gold | Line drawings on ink sheets; 4 px corners; numbered sections |

**Measured.** Every screen a visitor scrolls through was captured at 1440 x 900 (23 to 25 screens per
world, films included). Each pixel was placed on the nearest blend of two of the three colours, so a
wash of ink on paper counts partly as each. Text and photographs are left out.

| World | Main | Secondary | Gold |
|---|---|---|---|
| General | 63.4 % | 30.3 % | 6.3 % |
| SaaS | 64.9 % | 29.7 % | 5.4 % |
| Education | 59.9 % | 31.0 % | 9.1 % |
| Enterprise | 61.3 % | 33.5 % | 5.2 % |

Gold is held at or under 10 %, as the design system asks ("never flood fill"). It can be raised
towards 10 % in General, SaaS and Enterprise with one more gold block each, if wanted.

---

## 4. One chrome

| Part | Now |
|---|---|
| Header | One ink bar, 72 px, frosted, the same in every world and on every page: logo, version switch, five links, the Hindi switch where Hindi exists, one gold button. Only the button's words follow the version |
| Footer | One ink block in every world: brand, four columns with mono labels, the version switch, the wordmark cut off by the bottom edge |
| Phone menu, Ask Pragya | Ink and the system's liquid glass, the same everywhere |
| Version switch | Each version shows its own three colours as a 60 / 30 / 10 swatch |
| The morph | Gold dots over the target world's main colour, with its own ink for the line |

---

## 5. The default film, rebuilt in code

`components/world/washFilm.ts`, about 700 lines, no downloads but a 32 kB paper tile.

| Watercolour rule (lemo-opuscar) | How it is done here |
|---|---|
| One sheet of fibrous paper under everything | `film/paper.mjs` makes a seamless tile in the system's paper colour: three octaves of noise, grain and 3,400 fibres. The sheet has a deckled edge (`film/edges.mjs`) and hangs on the ink with the system's gold glow behind it |
| Every shape is translucent strokes, with bristle tracks and a dry tail; overlaps darken like pigment | A stroke engine: ribbons of uneven width, 3 to 9 broken bristle tracks, multiply compositing, a darker pooled edge, wet patches, paper grain |
| Structure first: pencil, then wash, then detail, then the note | Every object has its moment: underdrawing, washes in rows of a flat brush, content lines, gold, then a mono note |
| A quiet annotation layer | Notes in the system's mono, uppercase and tracked ("SOURCE: /PRICING", "THIS SENTENCE ANSWERS IT", "EXAMPLE FIGURES") |
| One long sheet, a gliding camera, passages that return to paper | Five passages along one sheet; the camera holds, pushes in and glides; each passage lifts as the next is painted |
| The palette carries the meaning | The website is painted in warm ink diluted from the system's near-black. Gold is laid only where the product acts: the visitor, the two pages an answer came from, the sentence that answers, the yes, the page fitted to a visitor, the result |

The opening is the wow moment of the General site: the website paints itself on the sheet as the page
loads. The chapters then paint the visitor arriving, the voice rings, the gilded sources, a chart and
table drawn in ink on the gold, the right page with its answering sentence ringed, the booking and the
lead, the page re-painted for two visitors, three versions of one site, and the result in gold on a
deep ink wash. Reduced motion shows one finished picture per chapter. The same engine draws the
pictures on the content pages, the doors and the bento, from the same sheet.

---

## 6. Four worlds, four wow moments

| World | First impression | Wow moment |
|---|---|---|
| General | The page paints itself: a sumi-ink website on a paper print, gold where it acts | Talk to it: pick a question; the page answers, draws, shows its source and rings the section it came from |
| SaaS | A console window drawn in characters, a pointer light over the hero, a gold status line | Be the buyer: three questions build a scored lead, shown as the lead, the Slack message and the webhook JSON |
| Education | A student at night, photographed, in an ink frame on morning paper | Your English page, answered in Hindi: a gold line runs from the Hindi answer to the English sentence it came from |
| Enterprise | A drafting sheet on ink that moves once and stops; an ink contents rail like a binder's spine | The rule console: switch the rules, run the check, watch each block pass or be left out; the result turns gold when every rule held |

---

## 7. Other fixes

| Area | Change |
|---|---|
| Pictures on content pages | `components/world/WorldArt.tsx`: one picture, four materials (painted, characters, line drawing, photograph); the page shows the one for the world on screen |
| Section rhythm | Each world alternates main and secondary blocks and ends on one gold band; the General site's paper blocks have brush edges |
| Headings | Space Grotesk 600 with a quieter second half (`--fg-2`), not gold; gold is kept for the hero's words, as the design system does |
| Buttons | The system's: Hanken 600, gold with a gold shadow, a quiet outline second, the metallic gold on the General site's one key action |
| Phones | A shorter picture, one row of buttons and the role chips in one scrolling row, so every hero fits under its picture at 390 px |
| Enterprise rail | On ink, with the pilot button at its foot; the pilot plan sits on gold (gold means approved in this world) |
| Link preview | `public/film/stills/painted-page.jpg` (1200 x 630) from the new hero |

---

## 8. Verified

- `tsc` and `eslint`: clean. `next build`: passes, 34 pages.
- No console errors on `/`, the three persona worlds, `/product`, `/pricing`, `/demo`, `/legal/privacy` or an unknown path.
- The version switch morphs General into SaaS (`/for/saas`); the Hindi switch rewrites Pricing (`?lang=hi`).
- Every world checked at 1440 x 900 and 390 x 844: films at several points, every section, the content pages in all four worlds.

## 9. Still open

| # | Item |
|---|---|
| 1 | The old rendered default film (`public/film/default/`, about 38 MB) and the stills `public/film/stills/D*.jpg` are no longer used. They can be removed from the repository; they were left in place for you to decide |
| 2 | The Roblox face is the design system's stand-in for the custom wordmark ("swap in the real faces when available"). When the real face arrives, it replaces `--font-logo` in one place |
| 3 | Gold is 5 to 9 % rather than 10 %. Raising it is one more gold block per world if you prefer the exact figure |
| 4 | Firefox, Safari and real phones are still untested; the checks above are in Chromium |
| 5 | The copy documents (`copy-*.md`) do not record the copy moves of 11 November (unchanged here) |
