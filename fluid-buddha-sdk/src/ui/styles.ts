// Self-contained stylesheet injected into the Shadow DOM. Nothing here leaks to
// the host page and host CSS cannot reach in (Req 3.1.2 / 4.1).
//
// ════════════════════════════════════════════════════════════════════════════
//  THE LIQUID-LIGHT SYSTEM
//  Pragya is one living light-form rendered on molten obsidian. The whole
//  surface language is built from three ideas:
//   • Material  — molten obsidian glass: deep translucent black, a true 1px
//                 gradient rim-light (brighter where light "hits" the top edge),
//                 a diffuse depth shadow, and a faint specular sheen.
//   • Light     — a champagne→gold→amber spectrum derived from --fb-accent, so a
//                 host can re-tint the entire presence with one colour and it
//                 stays coherent and luxurious.
//   • State     — dormant · listening · thinking · speaking are read through how
//                 the LIGHT behaves (colour + cadence on the Aura/orb/edge), never
//                 through extra chrome. Surfaces stay calm and readable; motion
//                 lives in the presence.
//  The three design levels are three scales of the same Aura: a companion you
//  hold (L1), a presence you step inside (L2), an atmosphere woven into the page
//  (L3).
// ════════════════════════════════════════════════════════════════════════════

export const CORE_STYLES = `
:host {
  /* — configurable anchor — */
  --fb-accent: #c9a24a;

  /* — molten-obsidian surface ramp — */
  --fb-void: #0a0b0e;
  --fb-bg: #0e0f13;
  --fb-surface: #15171e;
  --fb-surface-2: #1c1f28;
  --fb-fg: #f4f1e9;          /* warm ivory ink, never pure white */
  --fb-muted: #a7a294;       /* warm muted */
  --fb-faint: #6e6a60;
  --fb-border: rgba(255,255,255,0.10);
  --fb-pos: #5fd0a6;
  --fb-neg: #e8806f;

  /* — the liquid-light spectrum (the Aura), derived from the accent — */
  --fb-gold: var(--fb-accent);
  --fb-gold-bright: color-mix(in srgb, var(--fb-accent) 58%, #fff6df);
  --fb-platinum: color-mix(in srgb, var(--fb-accent) 22%, #fff8e9);
  --fb-amber: color-mix(in srgb, var(--fb-accent) 72%, #140d02);
  --fb-silver: #c2c8d2;      /* cool counter-light — "listening"/user */
  --fb-silver-bright: #e9edf3;

  /* — motion + rhythm — */
  --fb-ease: cubic-bezier(.16,1,.3,1);
  --fb-ease-spring: cubic-bezier(.34,1.4,.5,1);
  --fb-breath: 5.5s;
  --fb-dur: .5s;
  /* live 0..1 amplitude (mic / TTS), written per-frame by JS for reactive light */
  --fb-energy: 0;

  /* — semantic elevation — */
  --fb-z-base: 2147483000;
  --fb-z-page: 2147483400;

  all: initial;
  font-family: "Geist", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
*, *::before, *::after { box-sizing: border-box; }
.hidden { display: none !important; }

/* ───────────────────────── film grain ─────────────────────────
   A single fixed, pointer-transparent grain film over the overlay — the
   "shot on film" texture that reads as luxury. Painted once; never on a
   scrolling container (perf). */
.fb-grain {
  position: fixed; inset: 0; z-index: calc(var(--fb-z-base) + 60);
  pointer-events: none; opacity: .035; mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

/* ═══════════════════ molten-obsidian glass material ═══════════════════
   Shared by every elevated surface: L1 panel, generative cards, L2 draw
   surface, L3 captions + summon. */
.fb-glass, .card {
  position: relative; isolation: isolate;
  border-radius: 20px;
  color: var(--fb-fg);
  background:
    radial-gradient(135% 95% at 50% -14%, color-mix(in srgb, var(--fb-accent) 12%, transparent), transparent 60%),
    linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.012) 40%, rgba(255,255,255,0.02)),
    rgba(12,13,17,0.66);
  -webkit-backdrop-filter: blur(26px) saturate(155%);
  backdrop-filter: blur(26px) saturate(155%);
  box-shadow:
    0 34px 90px -34px rgba(0,0,0,0.86),
    0 8px 24px -18px rgba(0,0,0,0.7),
    inset 0 1px 0 rgba(255,255,255,0.16),
    inset 0 -34px 70px -48px rgba(0,0,0,0.65);
}
.card { padding: 16px; }
/* faint diagonal specular sheen (static — surfaces stay calm) */
.fb-glass::before, .card::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; z-index: -1;
  pointer-events: none;
  background: linear-gradient(135deg, transparent 0%, color-mix(in srgb, var(--fb-platinum) 16%, transparent) 16%, transparent 34%);
}
/* true 1px gradient rim-light — brighter at the top-left "lit" edge */
.fb-glass::after, .card::after {
  content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1px;
  pointer-events: none;
  background: linear-gradient(155deg,
    var(--fb-gold-bright) 0%, color-mix(in srgb, var(--fb-platinum) 60%, transparent) 14%,
    transparent 38%, transparent 64%,
    color-mix(in srgb, var(--fb-accent) 46%, transparent) 100%);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  mask-composite: exclude;
  opacity: .9;
}

/* ════════════════════════════════════════════════════════════════════
   DESIGN LEVEL 1 — "The Companion": an Aura you hold.
   ════════════════════════════════════════════════════════════════════ */

/* — Launcher: a living light-form, not a button with an icon — */
.trigger {
  position: fixed; bottom: 24px; right: 24px; z-index: var(--fb-z-base);
  width: 64px; height: 64px; padding: 0; border: none; border-radius: 50%;
  background: transparent; cursor: pointer; isolation: isolate;
  display: grid; place-items: center;
  -webkit-tap-highlight-color: transparent;
  transition: transform .35s var(--fb-ease-spring);
  will-change: transform;
}
:host([data-position="bottom-left"]) .trigger { left: 24px; right: auto; }
.trigger-aura { width: 100%; height: 100%; display: block; border-radius: 50%; }
/* the obsidian well the light sits in + its cast glow on the page */
.trigger::before {
  content: ""; position: absolute; inset: 0; border-radius: 50%; z-index: -1;
  background: radial-gradient(circle at 38% 34%, #1b1d25, var(--fb-void) 72%);
  box-shadow:
    0 14px 40px -10px rgba(0,0,0,0.6),
    0 0 38px -6px color-mix(in srgb, var(--fb-accent) 55%, transparent),
    inset 0 1px 0 rgba(255,255,255,0.10);
  border: 1px solid color-mix(in srgb, var(--fb-accent) 45%, transparent);
}
/* a slow breathing halo ring — the presence "inhaling" */
.trigger::after {
  content: ""; position: absolute; inset: -5px; border-radius: 50%; z-index: -1;
  border: 1px solid color-mix(in srgb, var(--fb-accent) 36%, transparent);
  animation: fb-breathe var(--fb-breath) var(--fb-ease) infinite;
}
.trigger:hover { transform: translateY(-3px) scale(1.05); }
.trigger:active { transform: translateY(-1px) scale(.99); }
@keyframes fb-breathe {
  0%, 100% { transform: scale(1); opacity: .55; }
  50% { transform: scale(1.18); opacity: 0; }
}

/* — Panel: a slab of molten obsidian with a gold light-seam at the brow — */
.panel {
  position: fixed; bottom: 24px; right: 24px; z-index: var(--fb-z-base);
  width: 392px; max-width: calc(100vw - 28px);
  height: 580px; max-height: calc(100vh - 48px);
  display: flex; flex-direction: column; overflow: hidden;
  border-radius: 26px; color: var(--fb-fg);
  background:
    radial-gradient(150% 80% at 50% -8%, color-mix(in srgb, var(--fb-accent) 9%, transparent), transparent 56%),
    linear-gradient(180deg, var(--fb-surface) 0%, var(--fb-bg) 26%, var(--fb-void) 100%);
  border: 1px solid rgba(255,255,255,0.08);
  box-shadow:
    0 50px 120px -40px rgba(0,0,0,0.9),
    0 10px 30px -20px rgba(0,0,0,0.7),
    inset 0 1px 0 rgba(255,255,255,0.07);
  isolation: isolate;
}
:host([data-position="bottom-left"]) .panel { left: 24px; right: auto; }
/* the light-seam — a bright gold thread along the top edge */
.panel::before {
  content: ""; position: absolute; left: 0; right: 0; top: 0; height: 1px; z-index: 3;
  background: linear-gradient(90deg, transparent, var(--fb-gold-bright), color-mix(in srgb, var(--fb-accent) 70%, transparent), transparent);
  opacity: .9;
}
/* a soft aura bloom behind the header, gently breathing */
.panel::after {
  content: ""; position: absolute; left: 50%; top: -40px; width: 240px; height: 160px; z-index: -1;
  transform: translateX(-50%);
  background: radial-gradient(closest-side, color-mix(in srgb, var(--fb-accent) 26%, transparent), transparent 72%);
  filter: blur(6px); opacity: .6;
  animation: fb-bloom calc(var(--fb-breath) * 1.3) var(--fb-ease) infinite;
}
@keyframes fb-bloom { 0%,100% { opacity: .38; transform: translateX(-50%) scale(1); } 50% { opacity: .7; transform: translateX(-50%) scale(1.08); } }

.header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 18px 14px; position: relative; z-index: 2;
}
.profile { display: flex; align-items: center; gap: 12px; }
/* living avatar — a miniature Aura, not a letter */
.avatar {
  width: 40px; height: 40px; border-radius: 50%; flex: none; position: relative;
  background: radial-gradient(circle at 38% 34%, #1c1e26, var(--fb-void) 75%);
  border: 1px solid color-mix(in srgb, var(--fb-accent) 40%, transparent);
  box-shadow: 0 0 22px -8px color-mix(in srgb, var(--fb-accent) 70%, transparent), inset 0 1px 0 rgba(255,255,255,0.08);
  overflow: hidden;
}
.avatar canvas { width: 100%; height: 100%; display: block; }
.name { font-weight: 600; font-size: 15px; letter-spacing: -.01em; color: var(--fb-fg); }
.status {
  font-size: 11.5px; color: var(--fb-muted); display: flex; align-items: center; gap: 6px;
  letter-spacing: .02em; margin-top: 1px; text-transform: lowercase;
}
.dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--fb-pos); flex: none;
  box-shadow: 0 0 0 0 color-mix(in srgb, var(--fb-pos) 60%, transparent);
  animation: fb-livedot 2.6s var(--fb-ease) infinite;
}
/* state-of-light: the status dot + word recolour with the agent's state */
.panel[data-state="listening"] .dot { background: var(--fb-silver); animation-duration: 1.1s; }
.panel[data-state="thinking"]  .dot { background: var(--fb-gold-bright); animation-duration: 1.8s; }
.panel[data-state="speaking"]  .dot { background: var(--fb-gold); animation-duration: .9s; }
.panel[data-state="listening"] .status { color: var(--fb-silver); }
.panel[data-state="speaking"]  .status,
.panel[data-state="thinking"]  .status { color: color-mix(in srgb, var(--fb-gold-bright) 80%, var(--fb-fg)); }
@keyframes fb-livedot { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 55%, transparent); } 70%,100% { box-shadow: 0 0 0 7px transparent; } }

.icon-btn {
  background: none; border: none; color: var(--fb-faint); cursor: pointer;
  padding: 7px; border-radius: 10px; display: grid; place-items: center;
  transition: color .2s var(--fb-ease), background .2s var(--fb-ease);
}
.icon-btn:hover { color: var(--fb-fg); background: rgba(255,255,255,0.06); }
.icon-btn svg { width: 18px; height: 18px; }

/* — Conversation: editorial, breathing, not a stack of chat bubbles — */
.messages {
  flex: 1; overflow-y: auto; padding: 8px 18px 16px;
  display: flex; flex-direction: column; gap: 16px; position: relative; z-index: 1;
  scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.16) transparent;
}
.messages::-webkit-scrollbar { width: 8px; }
.messages::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.14); border-radius: 8px; }
.messages::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.26); }

.bubble {
  max-width: 90%; font-size: 14.5px; line-height: 1.55; white-space: pre-wrap;
  word-wrap: break-word; text-wrap: pretty;
  animation: fb-rise-in .42s var(--fb-ease) both;
}
/* Pragya speaks as warm ivory prose with a gold margin-thread — editorial,
   weightless, unboxed. */
.bubble.pragya {
  align-self: flex-start; color: var(--fb-fg); padding-left: 14px;
  border-left: 1px solid color-mix(in srgb, var(--fb-accent) 50%, transparent);
}
/* The visitor's words: a cool, solid moonstone chip — the counter-light. */
.bubble.user {
  align-self: flex-end; padding: 9px 14px; border-radius: 16px 16px 5px 16px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--fb-silver) 22%, var(--fb-surface-2)), var(--fb-surface-2));
  border: 1px solid rgba(255,255,255,0.08); color: var(--fb-silver-bright);
}
.bubble.system {
  align-self: center; background: transparent; color: var(--fb-neg);
  font-size: 12px; text-align: center; border: none; padding: 0;
}
/* answer citations (trust layer) */
.sources {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px;
  font-size: 11px; color: var(--fb-fg); opacity: .9;
}
.sources-lead {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 10px; letter-spacing: .08em; text-transform: uppercase; color: var(--fb-pos);
}
.sources-lead::before { content: ""; width: 5px; height: 5px; border-radius: 50%; background: currentColor; box-shadow: 0 0 8px currentColor; }
.source {
  font: inherit; color: inherit; padding: 2px 8px; border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--fb-fg) 18%, transparent);
  background: color-mix(in srgb, var(--fb-fg) 5%, transparent);
}
button.source { cursor: pointer; }
button.source:hover, button.source:focus-visible { border-color: var(--fb-pos); outline: none; }
@keyframes fb-rise-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

/* "thinking" — three motes of light drifting upward */
.bubble.typing { display: inline-flex; gap: 6px; align-items: center; padding-left: 14px; border-left-color: color-mix(in srgb, var(--fb-gold-bright) 60%, transparent); }
.bubble.typing .dot {
  width: 7px; height: 7px; border-radius: 50%; background: var(--fb-gold-bright);
  box-shadow: 0 0 8px color-mix(in srgb, var(--fb-gold-bright) 70%, transparent);
  animation: fb-mote 1.3s var(--fb-ease) infinite;
}
.bubble.typing .dot:nth-child(2) { animation-delay: .17s; }
.bubble.typing .dot:nth-child(3) { animation-delay: .34s; }
@keyframes fb-mote { 0%,80%,100% { opacity: .35; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-4px); } }

.canvas { display: flex; flex-direction: column; gap: 12px; align-self: stretch; }

/* — Suggestion seeds — */
.chips { display: flex; gap: 8px; flex-wrap: wrap; padding: 0 18px 10px; position: relative; z-index: 1; }
.chip {
  font-size: 12px; padding: 7px 13px; border-radius: 999px; cursor: pointer; font: inherit;
  color: color-mix(in srgb, var(--fb-gold-bright) 75%, var(--fb-fg));
  background: color-mix(in srgb, var(--fb-accent) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--fb-accent) 30%, transparent);
  transition: transform .2s var(--fb-ease-spring), background .2s var(--fb-ease), border-color .2s var(--fb-ease);
}
.chip:hover { background: color-mix(in srgb, var(--fb-accent) 18%, transparent); border-color: color-mix(in srgb, var(--fb-accent) 55%, transparent); transform: translateY(-1px); }
.chip:active { transform: translateY(0) scale(.98); }

/* — Input: voice-first. The mic is the hero; type as the quiet alternative — */
.input {
  display: flex; align-items: center; gap: 10px; padding: 14px 16px;
  position: relative; z-index: 2;
  background: linear-gradient(180deg, transparent, color-mix(in srgb, var(--fb-void) 55%, transparent));
}
.input::before {
  content: ""; position: absolute; left: 16px; right: 16px; top: 0; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.10), transparent);
}
.input textarea {
  flex: 1; resize: none; height: 42px; max-height: 110px; padding: 11px 14px;
  border-radius: 14px; border: 1px solid var(--fb-border);
  background: rgba(255,255,255,0.035); color: var(--fb-fg);
  font: inherit; font-size: 14px; outline: none;
  transition: border-color .2s var(--fb-ease), box-shadow .2s var(--fb-ease), background .2s var(--fb-ease);
}
.input textarea::placeholder { color: var(--fb-faint); }
.input textarea:focus {
  border-color: color-mix(in srgb, var(--fb-accent) 55%, transparent);
  background: rgba(255,255,255,0.055);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--fb-accent) 16%, transparent);
}
.in-btn {
  width: 42px; height: 42px; flex: none; border-radius: 14px; cursor: pointer;
  border: 1px solid var(--fb-border); color: var(--fb-fg);
  background: linear-gradient(180deg, color-mix(in srgb, var(--fb-accent) 16%, var(--fb-surface-2)), var(--fb-surface-2));
  display: grid; place-items: center;
  transition: transform .18s var(--fb-ease), background .18s var(--fb-ease), border-color .18s var(--fb-ease), box-shadow .25s var(--fb-ease);
}
.in-btn:hover { border-color: color-mix(in srgb, var(--fb-accent) 55%, transparent); background: color-mix(in srgb, var(--fb-accent) 24%, var(--fb-surface-2)); }
.in-btn:active { transform: scale(.93); }
.in-btn svg { width: 18px; height: 18px; }
/* mic LIVE — the button becomes a pulsing well of light synced to the voice */
.in-btn.live {
  color: #16130a; border-color: var(--fb-gold-bright);
  background: radial-gradient(circle at 40% 34%, var(--fb-gold-bright), var(--fb-accent) 78%);
  box-shadow:
    0 0 0 calc(2px + var(--fb-energy) * 10px) color-mix(in srgb, var(--fb-accent) 40%, transparent),
    0 0 22px color-mix(in srgb, var(--fb-accent) 60%, transparent);
}

@media (max-width: 480px) {
  .panel { width: 100vw; height: 100dvh; max-width: 100vw; max-height: 100dvh; bottom: 0; right: 0; border-radius: 0; }
  :host([data-position="bottom-left"]) .panel { left: 0; }
  .trigger { bottom: calc(24px + env(safe-area-inset-bottom, 0px)); }
  .input { padding-bottom: calc(14px + env(safe-area-inset-bottom, 0px)); }
  .icon-btn { min-width: 44px; min-height: 44px; }
}

/* ════════════════════════════════════════════════════════════════════
   GENERATIVE CANVAS — diagrams, charts, widgets. Surfaces stay calm and
   legible; they inherit the molten-glass material from .card above.
   (Selectors preserved verbatim so the SVG/DOM renderers keep working.)
   ════════════════════════════════════════════════════════════════════ */
.caption { font-size: 12px; color: var(--fb-muted); margin-bottom: 10px; letter-spacing: .2px; line-height: 1.45; }
.empty { font-size: 12px; color: var(--fb-faint); font-style: italic; }

.fb-glass-rect { stroke: rgba(255,255,255,0.4); stroke-width: 1; }
.fb-glass-sheen { fill: url(#fbEdge); opacity: .55; pointer-events: none; }
.fb-glass-bead { stroke: rgba(255,255,255,0.45); stroke-width: 1.1; }
.fb-glass-spec { fill: rgba(255,255,255,0.7); pointer-events: none; }
.chart-area { opacity: .5; }

.fb-reveal-item { opacity: 0; animation: fb-rise .45s var(--fb-ease) forwards; }
@keyframes fb-rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@keyframes fb-fade { to { opacity: 1; } }

.flow { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.flow-node {
  position: relative; width: 100%; text-align: center; padding: 11px 14px;
  border-radius: 14px; font-size: 13px; color: var(--fb-fg);
  border: 1px solid rgba(255,255,255,0.20);
  background:
    linear-gradient(160deg, rgba(255,255,255,0.15), rgba(255,255,255,0.03)),
    color-mix(in srgb, var(--fb-accent) 15%, rgba(18,20,26,0.5));
  -webkit-backdrop-filter: blur(12px) saturate(150%); backdrop-filter: blur(12px) saturate(150%);
  box-shadow: 0 8px 22px -10px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.30);
}
.flow-edge { color: var(--fb-accent); font-size: 16px; line-height: 1; filter: drop-shadow(0 0 6px color-mix(in srgb, var(--fb-accent) 60%, transparent)); }

.wf { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.wf-node {
  padding: 10px 14px; border-radius: 14px; font-size: 12.5px; text-align: center;
  color: var(--fb-fg); border: 1px solid rgba(255,255,255,0.20);
  background:
    linear-gradient(160deg, rgba(255,255,255,0.15), rgba(255,255,255,0.03)),
    color-mix(in srgb, var(--fb-accent) 15%, rgba(18,20,26,0.5));
  -webkit-backdrop-filter: blur(12px) saturate(150%); backdrop-filter: blur(12px) saturate(150%);
  box-shadow: 0 8px 22px -10px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.30);
}
.wf-start, .wf-end { border-radius: 999px; }
.wf-decision {
  font-style: italic;
  background: linear-gradient(160deg, rgba(255,255,255,0.12), rgba(255,255,255,0.02)), color-mix(in srgb, var(--fb-accent) 8%, rgba(18,20,26,0.5));
}
.wf-arrow { color: var(--fb-accent); font-size: 13px; white-space: nowrap; filter: drop-shadow(0 0 6px color-mix(in srgb, var(--fb-accent) 55%, transparent)); }

.graph svg, .cdiag svg, .chart svg { display: block; width: 100%; height: auto; overflow: visible; }
.fb-arrow-head { fill: var(--fb-accent); }
.graph-edge, .cdiag-edge { stroke: color-mix(in srgb, var(--fb-accent) 55%, rgba(255,255,255,0.25)); stroke-width: 1.6; stroke-linecap: round; }
.graph-node text, .cdiag-box text { fill: var(--fb-fg); font-size: 10px; font-weight: 500; }

.chart-title { font-size: 12px; color: var(--fb-muted); margin-bottom: 6px; }
.chart-val { fill: var(--fb-fg); font-size: 9px; }
.chart-axis { fill: var(--fb-muted); font-size: 9px; }
.chart-line { fill: none; stroke: var(--fb-accent); stroke-width: 2.4; stroke-linejoin: round; stroke-linecap: round; }
.chart-dot circle { fill: #fff; stroke: var(--fb-accent); stroke-width: 1.6; }
.chart-slice { fill: url(#fbAccentFill); opacity: calc(0.95 - var(--i, 0) * 0.12); stroke: rgba(255,255,255,0.35); stroke-width: 1; }

.roi { display: flex; flex-direction: column; gap: 10px; }
.roi-row { display: grid; grid-template-columns: 92px 1fr 62px; align-items: center; gap: 8px; font-size: 12px; color: var(--fb-muted); }
.roi-row input[type=range] { width: 100%; accent-color: var(--fb-accent); }
.roi-row .val { text-align: right; color: var(--fb-fg); }
.roi-result { display: flex; justify-content: space-around; gap: 12px; margin-top: 6px; padding-top: 10px; border-top: 1px solid var(--fb-border); }
.roi-result > div { display: flex; flex-direction: column; align-items: center; }
.roi-label { font-size: 11px; color: var(--fb-faint); }
.roi-pos { color: var(--fb-pos); font-weight: 600; font-size: 16px; }
.roi-neg { color: var(--fb-neg); font-weight: 600; font-size: 16px; }

table.cmp { width: 100%; border-collapse: collapse; font-size: 12px; }
table.cmp th, table.cmp td { border: 1px solid var(--fb-border); padding: 6px 8px; text-align: left; }
table.cmp th { color: var(--fb-accent); font-weight: 600; }

.mindmap svg, .timeline svg, .sankey svg { display: block; width: 100%; height: auto; overflow: visible; }
.fb-tip {
  position: absolute; z-index: 6; pointer-events: none; max-width: 210px;
  padding: 6px 9px; border-radius: 10px; font-size: 11.5px; line-height: 1.35;
  color: var(--fb-fg); background: rgba(14,15,19,0.94);
  border: 1px solid var(--fb-border); box-shadow: 0 10px 26px rgba(0,0,0,0.55);
}
.mm-edge { stroke: color-mix(in srgb, var(--fb-accent) 45%, rgba(255,255,255,0.2)); stroke-width: 1.4; }
.mm-edge-sub { stroke-dasharray: 3 3; opacity: .7; }
.mm-node text { fill: var(--fb-fg); font-size: 10px; font-weight: 500; }
.mm-node-sub text { font-size: 9px; }
.mm-root rect { stroke: var(--fb-accent); stroke-width: 1.4; }
.mm-badge { fill: var(--fb-accent); }
.mm-badge-t { fill: #15130c; font-size: 11px; font-weight: 700; pointer-events: none; }

.tl-axis { stroke: color-mix(in srgb, var(--fb-accent) 50%, rgba(255,255,255,0.2)); stroke-width: 2; stroke-linecap: round; }
.tl-date { fill: var(--fb-accent); font-size: 9px; font-weight: 600; }
.tl-label { fill: var(--fb-fg); font-size: 9.5px; }

.sk-link { fill: url(#fbAccentFill); opacity: .48; transition: opacity .15s ease; }
.sk-link:hover { opacity: .85; }
.sk-label { fill: var(--fb-fg); font-size: 9px; }

.cfg, .sim { display: flex; flex-direction: column; gap: 9px; }
.cfg-row, .sim-row { display: grid; grid-template-columns: 96px 1fr 58px; align-items: center; gap: 8px; font-size: 12px; color: var(--fb-muted); }
.cfg-row input[type=range], .sim-row input[type=range] { width: 100%; accent-color: var(--fb-accent); }
.cfg-val, .sim-slider-val { text-align: right; color: var(--fb-fg); }
.cfg-row label, .sim-row label { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cfg-toggle { width: 18px; height: 18px; accent-color: var(--fb-accent); justify-self: start; }
.cfg-select { grid-column: 2 / 4; background: var(--fb-bg); color: var(--fb-fg); border: 1px solid var(--fb-border); border-radius: 8px; padding: 5px 8px; font: inherit; font-size: 12px; }
.cfg-out { display: flex; justify-content: space-around; gap: 12px; margin-top: 4px; padding-top: 10px; border-top: 1px solid var(--fb-border); }
.cfg-out > div { display: flex; flex-direction: column; align-items: center; }
.cfg-out-val { font-weight: 700; font-size: 17px; color: var(--fb-accent); }
.cfg-out-label { font-size: 11px; color: var(--fb-faint); }
.sim-chart { display: flex; flex-direction: column; gap: 7px; margin-bottom: 4px; }
.sim-bar-row { display: grid; grid-template-columns: 84px 1fr 56px; align-items: center; gap: 8px; font-size: 11.5px; }
.sim-bar-name { color: var(--fb-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sim-bar-track { height: 14px; border-radius: 7px; background: rgba(255,255,255,0.06); overflow: hidden; }
.sim-bar-fill { height: 100%; border-radius: 7px; background: linear-gradient(90deg, color-mix(in srgb, var(--fb-accent) 55%, transparent), var(--fb-accent)); transition: width .18s ease; }
.sim-bar-val { text-align: right; color: var(--fb-fg); }

.tabs-bar { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
.tabs-tab { font-size: 12px; padding: 6px 11px; border-radius: 10px; cursor: pointer; font: inherit; color: var(--fb-muted); background: transparent; border: 1px solid var(--fb-border); transition: color .18s var(--fb-ease), background .18s var(--fb-ease); }
.tabs-tab:hover { color: var(--fb-fg); }
.tabs-tab.active { color: #15130c; background: var(--fb-accent); border-color: var(--fb-accent); font-weight: 600; }
.tabs-tab:active { transform: scale(.96); }
.tabs-panel { font-size: 13px; line-height: 1.5; color: var(--fb-fg); white-space: pre-wrap; }

`;

export const L2_STYLES = `
/* ════════════════════════════════════════════════════════════════════
   DESIGN LEVEL 2 — "The Presence": an Aura you step inside.
   The volumetric smoke field (ParticleField) is the star; the HUD is a
   whisper of chrome around it.
   ════════════════════════════════════════════════════════════════════ */
.l2 { position: fixed; inset: 0; z-index: var(--fb-z-base); pointer-events: none; }
.l2-hidden { display: none !important; }
.l2-scrim {
  position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(120% 90% at 50% 60%, transparent 40%, color-mix(in srgb, var(--fb-void) 55%, transparent) 100%);
}
.l2-canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }

/* state-of-light readout — quiet, letterspaced, centred at the brow */
.l2-status {
  position: absolute; left: 50%; top: 24px; transform: translateX(-50%);
  font-size: 10.5px; letter-spacing: 3px; text-transform: uppercase;
  color: color-mix(in srgb, var(--fb-accent) 55%, rgba(214,216,224,0.55));
  pointer-events: none; transition: color .4s var(--fb-ease);
}
.l2[data-state="listening"] .l2-status { color: color-mix(in srgb, var(--fb-silver) 80%, transparent); }

.l2-close {
  position: absolute; right: 22px; top: 18px; pointer-events: auto;
  background: none; border: none; color: rgba(220,222,232,0.5); cursor: pointer;
  padding: 8px; border-radius: 10px; transition: color .2s var(--fb-ease), background .2s var(--fb-ease);
}
.l2-close:hover { color: var(--fb-fg); background: rgba(255,255,255,0.06); }
/* after close: a small orb of the same light, to reopen the presence */
.l2-reopen {
  position: fixed; right: 24px; bottom: 24px; z-index: var(--fb-z-base);
  width: 52px; height: 52px; border-radius: 50%; cursor: pointer; padding: 0;
  border: 1px solid color-mix(in srgb, var(--fb-accent) 55%, transparent);
  background: radial-gradient(circle at 40% 34%, color-mix(in srgb, var(--fb-accent) 45%, #16130e), var(--fb-void) 78%);
  box-shadow: 0 0 24px color-mix(in srgb, var(--fb-accent) 35%, transparent), 0 10px 30px rgba(0,0,0,0.45);
  animation: fb-l2-reopen-breathe 3.6s var(--fb-ease) infinite;
}
:host([data-position="bottom-left"]) .l2-reopen { left: 24px; right: auto; }
.l2-reopen:focus-visible { outline: 2px solid var(--fb-gold-bright); outline-offset: 3px; }
@keyframes fb-l2-reopen-breathe { 50% { transform: scale(1.06); } }
@media (prefers-reduced-motion: reduce) { .l2-reopen { animation: none; } }
.l2-close svg { width: 20px; height: 20px; }

/* a reactive halo ring centred on the presence — scales with live amplitude */
.l2-halo {
  position: absolute; left: 50%; top: 45%; transform: translate(-50%,-50%) scale(calc(1 + var(--fb-energy) * .5));
  width: 240px; height: 240px; border-radius: 50%; pointer-events: none; z-index: 1;
  border: 1px solid color-mix(in srgb, var(--fb-accent) 22%, transparent);
  box-shadow: 0 0 calc(40px + var(--fb-energy) * 120px) -10px color-mix(in srgb, var(--fb-accent) 45%, transparent);
  opacity: 0; transition: opacity .8s var(--fb-ease);
}
.l2.awake .l2-halo { opacity: .7; }
.l2[data-state="listening"] .l2-halo { border-color: color-mix(in srgb, var(--fb-silver) 30%, transparent); box-shadow: 0 0 calc(40px + var(--fb-energy) * 120px) -10px color-mix(in srgb, var(--fb-silver) 45%, transparent); }

/* "Awaken" — the invitation. A breathing ring of light, not a play button. */
.l2-play {
  position: absolute; left: 50%; top: 45%; transform: translate(-50%,-50%);
  width: 104px; height: 104px; border-radius: 50%; pointer-events: auto; cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--fb-accent) 60%, transparent);
  background: radial-gradient(circle at 40% 34%, color-mix(in srgb, var(--fb-accent) 26%, rgba(16,14,9,0.5)), rgba(14,12,8,0.45));
  color: var(--fb-gold-bright);
  display: grid; place-items: center;
  box-shadow: 0 0 70px -10px color-mix(in srgb, var(--fb-accent) 55%, transparent), inset 0 1px 0 rgba(255,255,255,0.2);
  transition: opacity .6s var(--fb-ease), transform .3s var(--fb-ease-spring);
  isolation: isolate;
}
.l2-play::after {
  content: ""; position: absolute; inset: -8px; border-radius: 50%; z-index: -1;
  border: 1px solid color-mix(in srgb, var(--fb-accent) 45%, transparent);
  animation: fb-breathe calc(var(--fb-breath) * .8) var(--fb-ease) infinite;
}
.l2-play:hover { transform: translate(-50%,-50%) scale(1.06); }
.l2-play svg { width: 38px; height: 38px; margin-left: 5px; }
.l2-hint {
  position: absolute; left: 50%; top: calc(45% + 78px); transform: translateX(-50%);
  font-size: 11px; letter-spacing: 2.5px; text-transform: uppercase;
  color: color-mix(in srgb, var(--fb-accent) 45%, rgba(214,216,224,0.5)); pointer-events: none;
  animation: fb-fade-loop 3.4s var(--fb-ease) infinite;
}
@keyframes fb-fade-loop { 0%,100% { opacity: .35; } 50% { opacity: .85; } }

/* fading message column — luxurious, legible over moving smoke */
.l2-stack {
  position: absolute; right: 3vw; bottom: 104px; left: auto; pointer-events: none;
  width: min(360px, 42vw);
  display: flex; flex-direction: column; gap: 10px; align-items: flex-end; text-align: right;
}
.l2-msg {
  font-size: 16px; line-height: 1.5; letter-spacing: .2px; color: #d6dae3;
  max-width: 100%; text-shadow: 0 1px 3px rgba(0,0,0,0.9), 0 2px 22px rgba(0,0,0,0.6);
  transition: opacity .6s var(--fb-ease), transform .6s var(--fb-ease);
}
.l2-msg.agent { color: #f6f1e3; font-weight: 450; }

/* centred drawing surface — molten glass over the smoke */
.l2-draw {
  position: absolute; left: 50%; top: 43%;
  width: min(640px, 88vw); max-height: 64vh; overflow: auto; pointer-events: auto;
  display: flex; flex-direction: column; gap: 14px;
  opacity: 0; transform: translate(-50%, calc(-50% + 16px)); transition: opacity .55s var(--fb-ease), transform .55s var(--fb-ease);
}
.l2-draw.show { opacity: 1; transform: translate(-50%,-50%); }
.l2-draw .card {
  -webkit-backdrop-filter: blur(30px) saturate(180%); backdrop-filter: blur(30px) saturate(180%);
  box-shadow: 0 30px 80px -18px rgba(0,0,0,0.78), inset 0 1px 0 rgba(255,255,255,0.30), inset 0 -26px 56px -34px rgba(0,0,0,0.8);
}

.l2-input {
  position: absolute; left: 50%; bottom: 26px; transform: translateX(-50%);
  width: min(720px, 92vw); display: flex; gap: 10px; align-items: center; pointer-events: auto;
}
.l2-input textarea {
  flex: 1; resize: none; height: 52px; max-height: 130px; padding: 15px 20px;
  border-radius: 999px; border: 1px solid rgba(255,255,255,0.14);
  background: rgba(16,17,22,0.5); color: #eef1f5; font: inherit; font-size: 15px; outline: none;
  -webkit-backdrop-filter: blur(16px); backdrop-filter: blur(16px);
  transition: border-color .2s var(--fb-ease), box-shadow .2s var(--fb-ease), background .2s var(--fb-ease);
}
.l2-input textarea::placeholder { color: rgba(220,225,235,0.4); }
.l2-input textarea:focus { border-color: color-mix(in srgb, var(--fb-accent) 60%, transparent); background: rgba(20,21,28,0.62); box-shadow: 0 0 0 3px color-mix(in srgb, var(--fb-accent) 18%, transparent); }
.l2-send {
  width: 52px; height: 52px; flex: none; border-radius: 50%; cursor: pointer; pointer-events: auto;
  border: 1px solid color-mix(in srgb, var(--fb-accent) 60%, transparent); color: var(--fb-gold-bright);
  background: linear-gradient(180deg, color-mix(in srgb, var(--fb-accent) 30%, rgba(16,14,9,0.5)), rgba(16,14,9,0.5));
  display: grid; place-items: center;
  box-shadow: 0 8px 26px -10px color-mix(in srgb, var(--fb-accent) 60%, transparent);
  transition: transform .18s var(--fb-ease), background .18s var(--fb-ease);
}
.l2-send:hover { background: color-mix(in srgb, var(--fb-accent) 40%, rgba(16,14,9,0.5)); }
.l2-send:active { transform: scale(.93); }
.l2-send svg { width: 20px; height: 20px; }

`;

export const L3_STYLES = `
/* ════════════════════════════════════════════════════════════════════
   DESIGN LEVEL 3 — "The Atmosphere": an Aura dissolved into the page.
   No widget. The agent is the light in the room: a breathing edge-aura, a
   spotlight that illuminates whatever Pragya references, glass captions
   anchored to content, and a ⌘K / long-press summon.
   ════════════════════════════════════════════════════════════════════ */
.l3 { position: fixed; inset: 0; z-index: var(--fb-z-base); pointer-events: none; }
.l3-hidden { display: none !important; }

/* breathing rim-light — the agent's presence at the edge of vision */
.l3-aura {
  position: fixed; inset: 0; pointer-events: none; z-index: 1; opacity: 0;
  transition: opacity 1s var(--fb-ease);
  box-shadow:
    inset 0 0 calc(70px + var(--fb-energy) * 150px) calc(-22px) color-mix(in srgb, var(--fb-accent) 42%, transparent),
    inset 0 0 2px 0 color-mix(in srgb, var(--fb-gold-bright) 30%, transparent);
}
.l3.awake .l3-aura { opacity: 1; animation: fb-aura-breath calc(var(--fb-breath) * 1.4) var(--fb-ease) infinite; }
.l3[data-state="listening"] .l3-aura { box-shadow: inset 0 0 calc(70px + var(--fb-energy) * 150px) -22px color-mix(in srgb, var(--fb-silver) 45%, transparent); }
.l3[data-state="thinking"] .l3-aura { animation-duration: calc(var(--fb-breath) * .8); }
@keyframes fb-aura-breath { 0%,100% { opacity: .65; } 50% { opacity: 1; } }

/* spotlight — dims the page and opens a soft window over the referenced spot */
.l3-veil {
  position: fixed; inset: 0; pointer-events: none; z-index: 2; opacity: 0;
  transition: opacity .7s var(--fb-ease);
  background: radial-gradient(circle var(--l3-r, 220px) at var(--l3-x, 50%) var(--l3-y, 40%),
    transparent 0%, transparent 55%, color-mix(in srgb, var(--fb-void) 78%, transparent) 100%);
}
.l3.spotlight .l3-veil { opacity: 1; }
.l3-ring {
  position: fixed; pointer-events: none; z-index: 3; border-radius: 18px; opacity: 0;
  left: var(--l3-rx, 0px); top: var(--l3-ry, 0px); width: var(--l3-rw, 0px); height: var(--l3-rh, 0px);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--fb-accent) 60%, transparent), 0 0 40px -4px color-mix(in srgb, var(--fb-accent) 55%, transparent);
  transition: opacity .6s var(--fb-ease), left .6s var(--fb-ease), top .6s var(--fb-ease), width .6s var(--fb-ease), height .6s var(--fb-ease);
}
.l3.spotlight .l3-ring { opacity: 1; }

/* floating glass captions — Pragya's words, anchored to the page */
.l3-caps {
  position: fixed; left: 50%; bottom: 4vh; transform: translateX(-50%); z-index: 5;
  width: min(560px, 92vw); display: flex; flex-direction: column; gap: 10px;
  align-items: center; pointer-events: none;
}
.l3-cap {
  pointer-events: auto; max-width: 100%; padding: 14px 18px; border-radius: 18px;
  font-size: 15px; line-height: 1.5; color: var(--fb-fg); text-wrap: pretty;
  animation: fb-rise-in .5s var(--fb-ease) both;
  transition: opacity .6s var(--fb-ease), transform .6s var(--fb-ease);
}
.l3-cap.user { color: var(--fb-silver-bright); font-size: 14px; }
.l3-cap .sources { margin-top: 8px; }

/* the summon — a centred Aura with a prompt; appears on ⌘K / long-press */
.l3-seed {
  position: fixed; bottom: 26px; right: 26px; z-index: 6; width: 16px; height: 16px;
  border-radius: 50%; pointer-events: auto; cursor: pointer; border: none; padding: 0;
  background: radial-gradient(circle at 40% 36%, var(--fb-gold-bright), var(--fb-accent) 75%);
  box-shadow: 0 0 18px -2px color-mix(in srgb, var(--fb-accent) 70%, transparent);
  animation: fb-breathe var(--fb-breath) var(--fb-ease) infinite;
  transition: transform .3s var(--fb-ease-spring);
}
:host([data-position="bottom-left"]) .l3-seed { left: 26px; right: auto; }
.l3-seed:hover { transform: scale(1.5); }

.l3-summon {
  position: fixed; left: 50%; top: 38%; transform: translate(-50%,-50%) scale(.96); z-index: 7;
  width: min(560px, 92vw); pointer-events: auto; padding: 26px 24px 18px;
  display: flex; flex-direction: column; align-items: center; gap: 16px;
  opacity: 0; transition: opacity .4s var(--fb-ease), transform .4s var(--fb-ease-spring);
}
.l3.summoning .l3-summon { opacity: 1; transform: translate(-50%,-50%) scale(1); }
.l3-summon-backdrop {
  position: fixed; inset: 0; z-index: 6; pointer-events: none; opacity: 0;
  background: radial-gradient(120% 90% at 50% 38%, color-mix(in srgb, var(--fb-void) 40%, transparent), color-mix(in srgb, var(--fb-void) 82%, transparent));
  -webkit-backdrop-filter: blur(3px); backdrop-filter: blur(3px);
  transition: opacity .4s var(--fb-ease);
}
.l3.summoning .l3-summon-backdrop { opacity: 1; pointer-events: auto; }
.l3-orb { width: 96px; height: 96px; display: block; }
.l3-summon-input {
  width: 100%; display: flex; gap: 10px; align-items: center;
}
.l3-summon-input textarea {
  flex: 1; resize: none; height: 52px; max-height: 120px; padding: 15px 20px;
  border-radius: 999px; border: 1px solid rgba(255,255,255,0.16);
  background: rgba(16,17,22,0.55); color: #eef1f5; font: inherit; font-size: 15px; outline: none;
  -webkit-backdrop-filter: blur(16px); backdrop-filter: blur(16px);
  transition: border-color .2s var(--fb-ease), box-shadow .2s var(--fb-ease);
}
.l3-summon-input textarea::placeholder { color: rgba(220,225,235,0.4); }
.l3-summon-input textarea:focus { border-color: color-mix(in srgb, var(--fb-accent) 60%, transparent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--fb-accent) 18%, transparent); }
.l3-summon-send {
  width: 52px; height: 52px; flex: none; border-radius: 50%; cursor: pointer;
  border: 1px solid color-mix(in srgb, var(--fb-accent) 60%, transparent); color: var(--fb-gold-bright);
  background: linear-gradient(180deg, color-mix(in srgb, var(--fb-accent) 30%, rgba(16,14,9,0.5)), rgba(16,14,9,0.5));
  display: grid; place-items: center; transition: transform .18s var(--fb-ease), background .18s var(--fb-ease);
}
.l3-summon-send:hover { background: color-mix(in srgb, var(--fb-accent) 40%, rgba(16,14,9,0.5)); }
.l3-summon-send:active { transform: scale(.93); }
.l3-summon-send svg { width: 20px; height: 20px; }
.l3-summon-hint {
  font-size: 10.5px; letter-spacing: 2.5px; text-transform: uppercase;
  color: color-mix(in srgb, var(--fb-accent) 45%, rgba(214,216,224,0.5));
}
.l3-summon-hint kbd {
  font: inherit; font-size: 10px; padding: 2px 6px; border-radius: 6px;
  background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.12); color: var(--fb-fg);
}

@media (max-width: 480px) {
  .l2-input, .l3-caps { bottom: calc(26px + env(safe-area-inset-bottom, 0px)); }
}

`;

export const EXTREME_STYLES = `
/* ════════════════════════════════════════════════════════════════════
   EXTREME — runtime-generated full-page surface. Themed by the site's
   design tokens (--ds-*), with molten-obsidian fallbacks.
   ════════════════════════════════════════════════════════════════════ */
.fbpage {
  position: fixed; inset: 0; z-index: var(--fb-z-page); overflow-y: auto; pointer-events: auto;
  background: var(--ds-color-background, var(--fb-void)); color: var(--ds-color-text, var(--fb-fg));
  font-family: var(--ds-font, "Geist", ui-sans-serif, system-ui, sans-serif);
  font-size: var(--ds-base-size, 16px);
}
.fbpage-bar {
  position: sticky; top: 0; z-index: 1; display: flex; align-items: center; gap: 10px;
  justify-content: space-between; padding: 14px 5vw;
  background: color-mix(in srgb, var(--ds-color-surface, var(--fb-surface)) 80%, transparent);
  -webkit-backdrop-filter: blur(18px); backdrop-filter: blur(18px);
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.fbpage-brand { font-weight: 700; color: var(--ds-color-primary, var(--fb-accent)); letter-spacing: -.01em; }
.fbpage-back {
  background: none; border: 1px solid var(--ds-color-primary, var(--fb-accent));
  color: var(--ds-color-primary, var(--fb-accent)); border-radius: 999px;
  padding: 7px 16px; font: inherit; font-size: 13px; cursor: pointer;
  transition: background .18s var(--fb-ease), color .18s var(--fb-ease);
}
.fbpage-back:hover { background: color-mix(in srgb, var(--ds-color-primary, var(--fb-accent)) 16%, transparent); }
.fbpage-inner { max-width: 1000px; margin: 0 auto; padding: 8px 5vw 96px; display: flex; flex-direction: column; gap: 34px; }
.fbpage-h2 { font-size: 1.6rem; font-family: var(--ds-font-heading, inherit); margin: 0 0 12px; letter-spacing: -.01em; }
.fbpage-body { line-height: 1.65; color: var(--ds-color-text, var(--fb-fg)); opacity: .92; max-width: 70ch; }
.fbpage-hero { text-align: center; padding: 56px 0 28px; }
.fbpage-hero-title { font-size: clamp(2rem, 5vw, 3.4rem); margin: 0 0 16px; font-family: var(--ds-font-heading, inherit); color: var(--ds-color-primary, var(--fb-accent)); letter-spacing: -.02em; text-wrap: balance; }
.fbpage-hero-sub { font-size: 1.15rem; opacity: .85; max-width: 60ch; margin: 0 auto 24px; line-height: 1.55; }
.fbpage-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; }
.fbpage-card {
  background: color-mix(in srgb, var(--ds-color-surface, var(--fb-surface)) 70%, transparent);
  -webkit-backdrop-filter: blur(20px); backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.1); border-radius: var(--ds-radius, 18px); padding: 20px;
}
.fbpage-card-title { margin: 0 0 8px; font-size: 1.1rem; }
.fbpage-card p { margin: 0; opacity: .85; line-height: 1.55; }
.fbpage-price { font-size: 1.7rem; font-weight: 700; color: var(--ds-color-primary, var(--fb-accent)); margin: 6px 0 10px; }
.fbpage-features { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 7px; opacity: .9; font-size: .95rem; }
.fbpage-features li::before { content: "✓ "; color: var(--ds-color-primary, var(--fb-accent)); }
.fbpage-btn {
  display: inline-block; border: none; cursor: pointer; font: inherit; font-weight: 600;
  padding: 13px 26px; border-radius: var(--ds-radius, 14px);
  background: var(--ds-color-primary, var(--fb-accent)); color: var(--ds-color-background, #15130c);
  transition: filter .18s var(--fb-ease), transform .18s var(--fb-ease);
}
.fbpage-btn:hover { filter: brightness(1.08); }
.fbpage-btn:active { transform: translateY(1px) scale(.99); }
.fbpage-btn:disabled { opacity: .6; cursor: default; }
.fbpage-form { display: flex; flex-direction: column; gap: 12px; max-width: 480px; }
.fbpage-field { display: flex; flex-direction: column; gap: 5px; font-size: .9rem; opacity: .9; }
.fbpage-field input, .fbpage-field textarea {
  font: inherit; padding: 11px 13px; border-radius: 12px; color: var(--ds-color-text, var(--fb-fg));
  border: 1px solid rgba(255,255,255,0.16); background: rgba(255,255,255,0.05); outline: none;
}
.fbpage-field textarea { min-height: 90px; resize: vertical; }
.fbpage-field input:focus, .fbpage-field textarea:focus { border-color: var(--ds-color-primary, var(--fb-accent)); }
.fbpage-media { max-width: 100%; border-radius: var(--ds-radius, 16px); }
.fbpage-caption { font-size: .85rem; opacity: .6; margin-top: 6px; }
.fbpage-quote { margin: 0; } .fbpage-quote blockquote { margin: 0 0 10px; font-size: 1.02rem; line-height: 1.55; }
.fbpage-quote figcaption { opacity: .7; font-size: .88rem; }
.fbpage-logos { display: flex; flex-wrap: wrap; gap: 28px; align-items: center; opacity: .85; }
.fbpage-logos img { height: 34px; max-width: 160px; object-fit: contain; }
.fbpage-qa { margin-bottom: 10px; } .fbpage-qa summary { cursor: pointer; font-weight: 600; } .fbpage-qa p { margin: 10px 0 0; opacity: .85; }
.fbpage-scroll { overflow-x: auto; } .fbpage-table { border-collapse: collapse; width: 100%; }
.fbpage-table th, .fbpage-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.12); }

`;

export const COMMON_STYLES = `
/* ════════════════════════════════════════════════════════════════════
   ACCESSIBILITY — focus rings, contrast, reduced motion (non-negotiable).
   ════════════════════════════════════════════════════════════════════ */
:host *:focus-visible {
  outline: 2px solid color-mix(in srgb, var(--fb-accent) 82%, white 8%);
  outline-offset: 2px; border-radius: 10px;
}
@media (prefers-contrast: more) {
  :host { --fb-border: rgba(255,255,255,0.30); --fb-muted: #cbd2dd; }
  .card { border-color: rgba(255,255,255,0.34); }
  .bubble.pragya { border-left-color: var(--fb-gold-bright); }
}
@media (prefers-reduced-motion: reduce) {
  :host *, :host *::before, :host *::after {
    animation-duration: .001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .001ms !important;
    scroll-behavior: auto !important;
  }
  .fb-reveal-item, .bubble, .l3-cap { opacity: 1 !important; transform: none !important; }
  .trigger::after, .l2-play::after, .l3-seed, .panel::after, .l2-hint { animation: none !important; }
  .trigger::after { opacity: 0 !important; }
}

/* ---- Microphone consent (WS8): above every design level ---- */
.fb-consent {
  position: fixed; inset: 0; z-index: calc(var(--fb-z-base) + 100);
  display: flex; align-items: center; justify-content: center; padding: 16px;
  background: rgba(5,6,8,0.55); backdrop-filter: blur(6px);
  font-family: inherit;
}
.fb-consent-card {
  width: min(380px, 100%); padding: 20px 20px 16px; border-radius: 16px;
  background: var(--fb-surface); color: var(--fb-fg);
  border: 1px solid var(--fb-border); box-shadow: 0 24px 60px rgba(0,0,0,0.45);
  display: flex; flex-direction: column; gap: 10px;
}
.fb-consent-card h2 { margin: 0; font-size: 1.05rem; font-weight: 600; }
.fb-consent-card p { margin: 0; font-size: 0.88rem; line-height: 1.5; color: var(--fb-muted); }
.fb-consent-card a { font-size: 0.84rem; color: var(--fb-gold-bright); }
.fb-consent-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 6px; }
.fb-consent-actions button, .fb-consent-actions a {
  text-decoration: none;
  font: inherit; font-size: 0.86rem; padding: 8px 14px; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--fb-border); background: transparent; color: var(--fb-fg);
}
.fb-consent-actions .fb-consent-allow {
  background: var(--fb-accent); border-color: var(--fb-accent); color: var(--fb-void); font-weight: 600;
}
.fb-consent-actions button:focus-visible, .fb-consent-card a:focus-visible {
  outline: 2px solid var(--fb-gold-bright); outline-offset: 2px;
}
/* ---- Action confirmation (M2-8): the consent dialog's look ---- */
.fb-action-rows { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 4px 14px; font-size: 0.88rem; }
.fb-action-rows dt { color: var(--fb-muted); }
.fb-action-rows dd { margin: 0; }
/* ---- Proactive nudge (M2-3): a message bubble by the launcher ---- */
.fb-nudge {
  position: fixed; right: 24px; bottom: 96px; z-index: calc(var(--fb-z-base) + 5);
  display: flex; align-items: flex-start; gap: 4px; max-width: min(300px, calc(100vw - 48px));
  padding: 4px; border-radius: 14px; background: var(--fb-surface); color: var(--fb-fg);
  border: 1px solid var(--fb-border); box-shadow: 0 14px 34px rgba(0,0,0,0.4);
  animation: fb-nudge-in .35s ease-out;
}
:host([data-position="bottom-left"]) .fb-nudge { right: auto; left: 24px; }
.fb-nudge button { font: inherit; color: inherit; background: none; border: 0; cursor: pointer; }
.fb-nudge-msg { padding: 8px 6px 8px 10px; text-align: left; font-size: 0.88rem; line-height: 1.45; }
.fb-nudge-x { padding: 4px 8px; font-size: 1.1rem; line-height: 1; color: var(--fb-muted); }
.fb-nudge button:focus-visible { outline: 2px solid var(--fb-gold-bright); outline-offset: 2px; border-radius: 8px; }
@keyframes fb-nudge-in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .fb-nudge { animation: none; } }
/* ---- A voice call with a person (M2-2) ---- */
.fb-callbar {
  position: fixed; left: 50%; bottom: 20px; transform: translateX(-50%);
  z-index: calc(var(--fb-z-base) + 90); display: flex; gap: 12px; align-items: center;
  padding: 8px 8px 8px 16px; border-radius: 999px; font-size: 0.88rem;
  background: var(--fb-surface); color: var(--fb-fg); border: 1px solid var(--fb-border);
  box-shadow: 0 12px 30px rgba(0,0,0,0.4);
}
.fb-callbar button {
  font: inherit; font-size: 0.84rem; padding: 6px 14px; border-radius: 999px; cursor: pointer;
  border: 0; background: #d64545; color: #fff; font-weight: 600;
}
.fb-callbar button:focus-visible { outline: 2px solid var(--fb-gold-bright); outline-offset: 2px; }
`;

/** The stylesheet for one widget: the shared material and Level 1 surfaces
 *  (other levels reuse some of them) plus only the parts this design level
 *  and intelligence tier use. Level 3 builds on Level 2's input styles. */
export function stylesFor(design: string, extreme: boolean): string {
  return CORE_STYLES
    + (design === 'level2' || design === 'level3' ? L2_STYLES : '')
    + (design === 'level3' ? L3_STYLES : '')
    + (extreme ? EXTREME_STYLES : '')
    + COMMON_STYLES;
}
