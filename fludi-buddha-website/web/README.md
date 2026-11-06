# FluidBuddha website

The marketing site described in `docs/marketing-docs/WebsiteConcept.md`. It runs on Next.js 16 with Cache Components.

## Run

```bash
npm install
npm run dev -- -p 3100
```

From the repo root, the `website` entry in `.claude/launch.json` starts the same server.

## Film frames

The home page scrubs a JPEG frame sequence on a canvas. The frames are git-ignored, so copy them in after rendering the film (see `../film/README.md`):

```bash
mkdir -p public/film/home/16x9
cp ../film/out/16x9/clips-360p/frames/f*.jpg public/film/home/16x9/
```

The frame count, fps and night range are set in `src/content/home.ts` (`FILM`). Chapter frame ranges live there as well. The posters in `public/film/posters/` are committed and used on every other page.

## Environment

| Variable | Used by | Without it |
| --- | --- | --- |
| `NEXT_PUBLIC_FB_LOADER_URL` | `AgentLoader`: the URL of the FluidBuddha widget loader | The ask bar runs its scripted preview |
| `NEXT_PUBLIC_FB_KEY` | `AgentLoader`: this site's agent key | Same as above |
| `NEXT_PUBLIC_CONSOLE_URL` | The "Create your free account" link on `/demo` and `/hi/demo` | `http://localhost:3001` |
| `SANDBOX_API_URL` | `/api/sandbox`, which forwards to `${SANDBOX_API_URL}/sandbox/start` | The form answers 503 with "being connected" |

When the widget loads, the ask bar hands every question to `document.querySelector("fluid-buddha").ask()`. The `fb:ask` and `fb:answered` window events drive the demo chips and capability cards in both modes.

## Layout

- `src/content/`: all copy. `site.ts` holds nav, footer and plans; `pages.ts` holds the template pages and legal pages; `home.ts` holds the film chapters and demo content (English and Hindi).
- `src/app/[...slug]`: renders every template page from `pages.ts`. Unknown paths return 404.
- `src/app/hi/`: the three Hindi pages: home, demo and pricing.
- `src/components/`: `FilmPlayer`, `AskBar`, `DemoStage`, `SandboxForm`, `CostCalculator`, `ContentPage`, `Nav`, `Footer`.

## Copy rules

- Say "answers only from your website, with sources". Never claim it "never makes things up".
- Languages are English and Hindi only.
- Label every ROI or example figure as illustrative.
