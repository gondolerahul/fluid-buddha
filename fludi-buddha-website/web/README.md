# FluidBuddha website

The marketing site described in `docs/marketing-docs/WebsitePlan.md`, redesigned on 11 November 2026
(`docs/marketing-docs/website/audit-2026-11-11.md`). It runs on Next.js 16 with Cache Components.

## Run

```bash
npm install
npm run dev -- -p 3100
```

From the repo root, the `website` entry in `.claude/launch.json` starts the same server.

## One site, four worlds

The site has four versions ("worlds"): the general site at `/` and three persona sites at
`/for/saas`, `/for/education` and `/for/enterprise`. A world sets the colours, type, corners, film
and main button of the whole site, not only of its own page:

- An inline script in `src/app/layout.tsx` (`WORLD_BOOT` in `src/lib/world.ts`) sets
  `<html data-world>` before the first paint: a world's page takes its own world, any other page the
  visitor's remembered choice (`localStorage` key `fb:world`).
- `src/app/globals.css` holds one token block per world. Everything else (the shared header and
  footer, the content pages, the forms) is drawn from those tokens.
- The version switch (`src/components/site/VersionSwitch.tsx`) changes world. On a world's page it
  morphs to the other world's route; on any other page it re-themes the page in place
  (`src/components/world/WorldSwitch.tsx`).

## Layout

- `src/app/layout.tsx`: the one header, footer, Ask Pragya light and morph, for every page.
- `src/app/(worlds)/`: the four world pages and their styles (`film.css`, `world-*.css`).
- `src/app/(site)/`: pricing, demo, legal, and `[...slug]` for every template page in `content/pages.ts`.
- `src/content/`: all copy. `worlds/*.ts` (each world's hero, film chapters, sections and reviewed
  Hindi), `pages.ts` (template and legal pages), `site.ts` (nav, footer, plans), `media.ts` (the film
  frames used as pictures), `demo.ts`.
- `src/components/world/`: `WorldPage` (renders a world), `FilmScroll` with `asciiFilm` and
  `lineFilm` (the scroll films), and `signature/` (the four signature moments).
- `src/components/site/`: header, footer, version switch, Ask Pragya, small shared parts.
- `src/lib/`: `world.ts` (which world, the morph events, measurement), `lang.ts` (the runtime Hindi
  switch), `answers.ts` (the scripted preview answers).

## Film frames

The default and Education films are WebP frame sequences in `public/film/<world>/720` (desktop) and
`480` (phones), committed so a deploy has them. They are exported from `../film` after a render (see
`../film/README.md`). The frame count, pace and chapters are set in each world's content file.
Single frames from the same films are the pictures of the other pages (`src/content/media.ts`).

## Environment

| Variable | Used by | Without it |
| --- | --- | --- |
| `NEXT_PUBLIC_FB_LOADER_URL` | `AgentLoader`: the URL of the FluidBuddha widget loader | Ask Pragya runs its scripted preview |
| `NEXT_PUBLIC_FB_KEY` | `AgentLoader`: this site's agent key | Same as above |
| `NEXT_PUBLIC_CONSOLE_URL` | The "Create your free account" link on `/demo` | `http://localhost:3001` |
| `SANDBOX_API_URL` | `/api/sandbox`, which forwards to `${SANDBOX_API_URL}/sandbox/start` | The form answers 503 with "being connected" |

When the widget loads, Ask Pragya hands every question to `document.querySelector("fluid-buddha").ask()`.
The `fb:ask` and `fb:answered` window events drive the demo chips and the "Ask it" buttons.

## Copy rules

- Say "answers only from your website, with sources". Never claim it "never makes things up".
- Languages are English and Hindi only. Hindi is shown only where a native reader has reviewed it.
- Label every ROI or example figure as an example.
- No dashes as punctuation, no small labels above headings, no gradient text, no claims of customers
  or certifications (audit §4).
