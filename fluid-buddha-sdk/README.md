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
- `dist/fluid-buddha.mjs` (+ `dist/chunks/`) — ESM for bundlers; Three.js is a
  split chunk loaded by dynamic import.
- `dist/fluid-buddha.cjs` — CommonJS (Three.js inline).
- `dist/index.d.ts` — TypeScript types.

> Bundle size: the script-tag core (all design levels' UI, no Three.js) is
> ~141 kB minified, ~39 kB gzipped; about a third of that is the stylesheet.
> Level 2 adds the ~465 kB (~120 kB gzipped) particles file. `npm test`
> fails if the gzipped core grows past 42 kB. If the particles file can't be
> loaded, Level 2 still works, with the halo instead of the smoke field.
