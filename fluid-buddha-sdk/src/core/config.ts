// Configuration: defaults, programmatic options, and parsing from the
// injecting <script data-*> tag or the <fluid-buddha> element's attributes.

export interface FluidBuddhaHooks {
  /** Handle navigation yourself (e.g. SPA router). Return nothing — providing
   *  the hook suppresses the default full-page navigation. */
  onNavigate?: (path: string) => void;
  /** Handle scrolling yourself (section jump and/or relative direction). */
  onScrollTo?: (target: { sectionId?: string; direction?: string }) => void;
  /** Trigger your site's persona/theme switch (e.g. Redux dispatch, setICP). */
  onSetPersona?: (persona: string) => void;
}

/** How capable the agent is — gates which backend tools are offered and which
 *  frontend affordances are enabled (see the A2UI "intelligence levels"):
 *  - `basic`   : text chat + redirect/scroll only (no voice, no diagrams).
 *  - `high`    : + bidirectional voice with spoken feedback.
 *  - `advance` : + generated diagrams/charts/typed components (the default,
 *                today's behaviour).
 *  - `extreme` : + runtime whole-page generation grounded in an ingested design
 *                system & APIs (the host is a container app with no authored
 *                pages). */
export type IntelligenceLevel = 'basic' | 'high' | 'advance' | 'extreme';

/** How the overlay looks/feels — three scales of the same living Aura:
 *  - `level1` : "The Companion" — a held Aura. A breathing light-form launcher
 *               and a molten-obsidian chat panel (the default).
 *  - `level2` : "The Presence" — an Aura you step inside. A panel-less, immersive
 *               volumetric smoke field (Three.js) with a whisper of HUD.
 *  - `level3` : "The Atmosphere" — an Aura dissolved into the page itself: a
 *               breathing edge-aura, a spotlight that illuminates whatever Pragya
 *               references, floating glass captions, and a ⌘K / long-press summon.
 *               No persistent widget. */
export type DesignLevel = 'level1' | 'level2' | 'level3';

export const INTELLIGENCE_LEVELS: IntelligenceLevel[] = ['basic', 'high', 'advance', 'extreme'];
export const DESIGN_LEVELS: DesignLevel[] = ['level1', 'level2', 'level3'];

/** Ordinal rank so callers can ask "is at least `advance`?" without a switch. */
export function intelligenceRank(level: IntelligenceLevel): number {
  return INTELLIGENCE_LEVELS.indexOf(level);
}

export interface FluidBuddhaConfig {
  /** WebSocket base of the A2UI backend, e.g. wss://voice.hirebuddha.com */
  backend: string;
  /** HTTP base for the text fallback; derived from `backend` if omitted. */
  api: string;
  /** Knowledge scope on the backend (one per site). */
  site: string;
  position: 'bottom-right' | 'bottom-left';
  accent: string;
  greeting: string;
  /** Auto-inject the element into <body> on load (script-tag usage). */
  autoInject: boolean;
  /** Open the panel and speak the page-aware welcome as soon as the component
   *  loads (voice-first). Audio still obeys browser autoplay policy — if the
   *  page hasn't been interacted with yet, the welcome plays on the first
   *  click/tap/keypress anywhere. */
  autoStart: boolean;
  /** Agent capability tier (gates tools + UI affordances). Default `advance`. */
  intelligence: IntelligenceLevel;
  /** Visual/interaction style. Default `level1` (classic panel). */
  design: DesignLevel;
  /** Play the agent-led guided tour when the site has one (authored at
   *  ingestion). Default `true`; set `data-tour="false"` to opt out. */
  tour: boolean;
  hooks: FluidBuddhaHooks;
}

export type FluidBuddhaOptions = Partial<Omit<FluidBuddhaConfig, 'hooks'>> & {
  hooks?: FluidBuddhaHooks;
};

const DEFAULTS: FluidBuddhaConfig = {
  backend: '',
  api: '',
  site: 'hirebuddha',
  position: 'bottom-right',
  accent: '#c9a24a',
  greeting:
    "Hi, I'm Pragya. Tap the mic and ask me anything — I can show you around, run the numbers, and answer with grounded facts.",
  autoInject: false,
  autoStart: false,
  intelligence: 'advance',
  design: 'level1',
  tour: true,
  hooks: {},
};

/** wss://host -> https://host ; ws://host -> http://host */
export function deriveApi(backend: string): string {
  if (!backend) return '';
  return backend.replace(/^wss:/, 'https:').replace(/^ws:/, 'http:');
}

export function resolveConfig(options: FluidBuddhaOptions = {}): FluidBuddhaConfig {
  const backend = options.backend ?? DEFAULTS.backend;
  return {
    ...DEFAULTS,
    ...options,
    backend,
    api: options.api || deriveApi(backend),
    hooks: { ...DEFAULTS.hooks, ...(options.hooks || {}) },
  };
}

/** Read `data-*` attributes from an element/script into options. */
export function optionsFromAttributes(el: Element | null): FluidBuddhaOptions {
  if (!el) return {};
  const get = (name: string) =>
    el.getAttribute(`data-${name}`) ?? el.getAttribute(name) ?? undefined;
  const opts: FluidBuddhaOptions = {};
  const backend = get('backend');
  if (backend) opts.backend = backend;
  const api = get('api');
  if (api) opts.api = api;
  const site = get('site');
  if (site) opts.site = site;
  const accent = get('accent');
  if (accent) opts.accent = accent;
  const greeting = get('greeting');
  if (greeting) opts.greeting = greeting;
  const position = get('position');
  if (position === 'bottom-left' || position === 'bottom-right') opts.position = position;
  const auto = get('auto');
  if (auto != null) opts.autoInject = auto !== 'false';
  const autoStart = get('auto-start');
  if (autoStart != null) opts.autoStart = autoStart !== 'false';
  const intelligence = get('intelligence');
  if (intelligence && (INTELLIGENCE_LEVELS as string[]).includes(intelligence))
    opts.intelligence = intelligence as IntelligenceLevel;
  const design = get('design');
  if (design && (DESIGN_LEVELS as string[]).includes(design))
    opts.design = design as DesignLevel;
  const tour = get('tour');
  if (tour != null) opts.tour = tour !== 'false';
  return opts;
}
