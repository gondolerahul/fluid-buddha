# fluid-buddha

A **framework-agnostic, voice-first agentic UI overlay** delivered as a single
Web Component, `<fluid-buddha>`. Drop it onto *any* website with one `<script>`
tag — it lives entirely inside a Shadow DOM (no CSS/JS collisions with the host)
and talks to the A2UI backend orchestrator over the multiplexed voice WebSocket.

It is the "Frontend SDK (Eyes, Ears & Hands)" from the A2UI architecture: mic
capture + VAD, a jitter buffer that keeps TTS audio in sync with generated UI, a
Shadow-DOM component registry (flowchart / ROI calculator / table), and a host
bridge that performs navigation, scroll, and silent persona switching on the
host page.

## Install on any site (one line)

```html
<script src="https://cdn.example.com/fluid-buddha.global.js"
        data-backend="wss://voice.hirebuddha.com"
        data-site="hirebuddha"
        data-accent="#c9a24a"></script>
```

That auto-injects the floating launcher. `data-*` options: `backend` (required,
the backend WS base), `site`, `api` (HTTP base for the text fallback; derived
from `backend` if omitted), `accent`, `position` (`bottom-right`|`bottom-left`),
`greeting`, `auto` (`false` to disable auto-inject), and the two capability axes
below.

### Intelligence & design levels

Two orthogonal axes, both selectable per site (`data-intelligence` /
`data-design`, or `intelligence` / `design` in `init()`):

| `intelligence` | What the agent can do |
|---|---|
| `basic` | text chat + redirect/scroll (no voice, no diagrams) |
| `high` | + bidirectional voice with spoken feedback |
| `advance` | + generated diagrams/charts/typed components **(default)** |
| `extreme` | + runtime whole-page generation grounded in an ingested design system & APIs (host is a blank container app) |

**The design levels are three scales of one living Aura.** Pragya is rendered as
the same "liquid light on molten obsidian" presence everywhere; her state —
*dormant · listening · thinking · speaking* — is read through how the light
behaves (warm gold at rest, cool silver while she listens, a bright shimmer
while she thinks), never through extra chrome.

| `design` | Look & feel |
|---|---|
| `level1` | **The Companion** — an Aura you hold. A breathing light-form launcher (a 2D canvas, *no WebGL*) and a molten-obsidian glass panel with a gold light-seam, a living avatar, and a reactive voice ring **(default)** |
| `level2` | **The Presence** — an Aura you step inside. A panel-less, full-viewport volumetric curl-noise smoke field (Three.js) with an "Awaken" invitation, a reactive halo, a fading message column, and a centred drawing surface |
| `level3` | **The Atmosphere** — an Aura dissolved into the page. No widget: a breathing edge-aura that pulses with her state, a spotlight that dims the page and illuminates whatever she references as she scrolls/navigates, ephemeral glass captions, and a `⌘K` / light-mote summon |

```html
<script src="…/fluid-buddha.global.js"
        data-backend="wss://voice.example.com" data-site="hirebuddha"
        data-intelligence="advance" data-design="level2"></script>
```

## Programmatic use (bundlers / SPAs)

```ts
import { init } from 'fluid-buddha';

init({
  backend: 'wss://voice.hirebuddha.com',
  site: 'hirebuddha',
  // Take over DOM commands to integrate with your app's own mechanisms:
  hooks: {
    onNavigate: (path) => router.push(path),      // your router, explicitly
    onSetPersona: (p) => store.setICP(p),         // your existing persona switch
    onScrollTo: (id) => scrollToSection(id),
  },
});
```

You can also place `<fluid-buddha backend="…" site="…">` in markup yourself.

## Holdout experiments

When the site runs a holdout experiment (console → Experiment), the widget
asks the backend which group this visitor is in before it draws anything. A
held-out visitor gets no widget at all (the element stays empty and carries
`data-holdout`), and calls like `openPanel()` do nothing. The group is cached
in `localStorage` for a few hours, so later page views render at once.

Both groups are measured the same way. Set a goal page in the console, or
report a goal yourself:

```js
window.FluidBuddha.conversion('demo_booked');      // script tag
import { conversion } from 'fluid-buddha';          // bundlers
conversion('demo_booked', 499);                     // optional value
```

Outside an experiment it does nothing. The visitor id is an anonymous random
string; without `localStorage` the visitor isn't part of the experiment and
gets the agent. If enrolment fails (network, CORS), so does everyone else.

## Generated regions on your own pages

Wrap a part of a page in `<fb-region>` and FluidBuddha fills it for each visitor's
likely goal (worked out from where they landed and how they arrived, before they say
anything). Your own content stays until a region is ready, and stays if one can't be
made; search engines always see your own content.

```html
<fb-region name="hero">
  <h1>Your own hero</h1>   <!-- shown until (and unless) a generated one replaces it -->
</fb-region>
```

Declare the region (`hero`) in the console's **Regions** tab. All regions on a page are
fetched in one request; the first visitor for a new goal triggers a background build
and later visitors get it instantly. A region already in view never changes after the
visitor starts scrolling or clicking. With the widget's script on the page nothing else
is needed; standalone, give the element `data-api` and `data-key`. React and Vue users
can write `<FbRegion name="hero">…</FbRegion>` (`@fluidbuddha/react`, `@fluidbuddha/vue`).
Each fill fires a `fluidbuddha:region` event.

## Personal experience

The widget learns how each visitor likes things presented — layout density, format
(tables, charts, prose), level of detail, tone — from their own settings
(`prefers-reduced-motion`, dark mode), how they use the agent, what they open and what
they say ("keep it short", "show me a table"). Anonymous visitors' preferences stay in
their browser for the visit (`sessionStorage`, plus a compact `fbtaste` session cookie
your server-rendered pages can read); a visitor who chose "Remember me" has them saved.

Generated regions and pages adapt within the limits your design system allows, each with
a small **Why this?** that explains what shaped it and links to the visitor's
**preferences panel** (also in the widget header). Clicks, form submits and
`FluidBuddha.conversion()` reward the version that was shown, so the console's
"Learn what works" setting can favour the better one.

## Navigation on single-page apps

When the agent takes the visitor to another page, the widget doesn't reload a
single-page app. By default (`navigation: 'auto'`, or `data-navigation="auto"`)
it pushes the route onto the browser history and fires `popstate`, which React
Router, Vue Router, Next.js and most other routers answer by rendering the
page. If nothing on the page changes within 600 ms, the site is multi-page and
the widget loads the page normally. Other origins always load normally.

| `navigation` | Behaviour |
|---|---|
| `auto` | History API + `popstate`; a normal page load if nothing re-renders **(default)** |
| `spa` | History API + `popstate` only, never a page load |
| `reload` | Always a normal page load |

To route it yourself, pass `hooks.onNavigate`, or cancel the event:

```js
window.addEventListener('fluidbuddha:navigate', (e) => {
  e.preventDefault();          // the widget does nothing further
  router.push(e.detail.path);
});
```

After an in-app route change the widget emits `fluidbuddha:navigated` and tells
the agent the visitor's new page.

## React to the agent from any framework

Even without hooks, every DOM command is dispatched as a `CustomEvent` on
`window`, so any host can listen:

```js
window.addEventListener('fluidbuddha:set_persona', (e) => setICP(e.detail.persona));
window.addEventListener('fluidbuddha:navigate', (e) => router.push(e.detail.path));
window.addEventListener('fluidbuddha:scroll_to', (e) => { /* … */ });
```

## How it works

| Piece | File |
|---|---|
| `<fluid-buddha>` custom element (Shadow DOM UI) | `src/ui/FluidBuddhaElement.ts` |
| Multiplexed WS client (`AUDIO/DATA/EVENTS/STATE`) | `src/transport/VoiceClient.ts` |
| Mic capture (AudioWorklet, ScriptProcessor fallback) | `src/audio/AudioCapture.ts` |
| Energy VAD + pre-roll (the first word isn't clipped) → PCM16 @ 16 kHz | `src/audio/SpeechGate.ts` |
| Jitter buffer (audio held until UI renders; filler on >1.5 s) | `src/audio/JitterBuffer.ts` |
| TTS PCM player | `src/audio/AudioPlayer.ts` |
| Generative UI canvas + component registry (flowchart, workflow, component diagram, graph, chart, ROI, table) | `src/ui/components/` |
| The Aura — Pragya's living "liquid light" being (2D canvas, no WebGL); shared by L1 + L3 | `src/ui/aura/AuraCanvas.ts` |
| Design Level 2 particle engine (Three.js) + immersive shell | `src/ui/particles/` · `src/ui/level2/` |
| Design Level 3 ambient atmosphere (edge-aura + spotlight + captions + ⌘K summon) | `src/ui/level3/Level3Shell.ts` |
| Extreme: runtime page renderer + design-token loader | `src/ui/page/PageRenderer.ts` · `src/core/designSystem.ts` |
| Host bridge (navigate / scroll / persona, overridable) | `src/core/HostBridge.ts` |
| Orchestrator (transcribe → ack → grounded answer + UI) | `src/core/Session.ts` |

Transcription uses the browser Web Speech API when available (works without
server ASR); raw PCM is still streamed so the backend can run Cloud ASR. Audio
travels as binary WebSocket frames in both directions (the socket asks with
`?audio=binary`; an older server keeps base64 JSON and the widget follows). The
LLM never emits raw HTML — it calls `render_component` with a JSON schema that
maps to a pre-built, safe renderer.

## Develop

```bash
npm install
npm run typecheck          # tsc --noEmit
npm run build              # dist/fluid-buddha.{global.js,mjs,cjs} + .d.ts
npm test                   # jsdom: element, session routing, canvas, auto-inject
node test/inject.mjs       # proves single-<script> auto-injection

# Try it against a locally running backend (../backend, uvicorn :8080):
npm run serve:demo         # builds, serves demo/ at http://localhost:4000
```

> Cross-origin note: when the host page's origin differs from the backend, add
> it to the backend's `CORS_ORIGINS`. The WebSocket itself is not CORS-gated;
> the HTTP `/chat` text fallback is.

## Build outputs
- `dist/fluid-buddha.global.js` — IIFE for a `<script>` tag, exposes `window.FluidBuddha`.
- `dist/fluid-buddha-particles.global.js` — the Design Level 2 particle field
  (Three.js). **Host it next to `fluid-buddha.global.js`**: the core fetches it
  from the same folder, only when Level 2 starts.
- `dist/fluid-buddha-regions.global.js` — the generated-regions controller, fetched
  from the same folder only on pages that use `<fb-region>`. **Host it next to
  `fluid-buddha.global.js`** too.
- `dist/fluid-buddha-patcher.global.js` — the Extreme page renderer and plan patcher,
  fetched the first time the agent draws or edits a page. **Host it next to
  `fluid-buddha.global.js`.**
- `dist/fluid-buddha-prefs.global.js` — the visitor's preferences panel, fetched when
  opened. **Host it next to `fluid-buddha.global.js`.**
- `dist/fluid-buddha-composed.global.js` — the script of a server-rendered composed page
  (Phase 2): hydrates its interactive sections, sends its forms, applies the agent's
  edits. Loaded by the page itself (`/g/…` or `@fluidbuddha/next`).
- `dist/fluid-buddha.mjs` (+ `dist/chunks/`) — ESM for bundlers; Three.js, the regions
  controller and the page renderer are split chunks loaded by dynamic import.
- `dist/fluid-buddha.cjs` — CommonJS (Three.js inline).
- `dist/index.d.ts` — TypeScript types.

> Bundle size: the script-tag core (all design levels' UI, no Three.js) is
> ~38 kB gzipped (the page renderer, regions, patches and the preferences panel load on demand); about a third of that is the stylesheet.
> Level 2 adds the ~465 kB (~120 kB gzipped) particles file. `npm test`
> fails if the gzipped core grows past 42 kB. If the particles file can't be
> loaded, Level 2 still works, with the halo instead of the smoke field.
