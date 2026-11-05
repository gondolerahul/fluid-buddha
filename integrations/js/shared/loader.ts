// Shared by @fluidbuddha/react and @fluidbuddha/vue (bundled into each).
//
// The wrappers don't bundle the widget: they load it from the FluidBuddha
// server through /widget/loader.js, the same script every install surface uses
// (M2-10). Visitors always get the server's current widget, and the app's own
// bundle grows by about 1.5 kB gzipped.
//
// An *install code* carries both things a page needs, the server and the
// widget key, the way a DSN does:   https://fbk_abc123@agent.example.com
// The console's Install tab shows it for each website.

/** Server base URL (no trailing slash) and the website's widget key. */
export interface InstallTarget {
  server: string;
  key: string;
}

export type Position = 'bottom-right' | 'bottom-left';
export type Lang = 'auto' | 'en' | 'hi';
export type DesignLevel = 'level1' | 'level2' | 'level3';
export type NavigationMode = 'auto' | 'spa' | 'reload';

export interface FluidBuddhaHooks {
  /** Route inside your app; replaces the widget's own navigation. */
  onNavigate?: (path: string) => void;
  onScrollTo?: (target: { sectionId?: string; direction?: string }) => void;
  onSetPersona?: (persona: string) => void;
}

/** Display options; anything left out comes from the website's settings. */
export interface WidgetOptions {
  position?: Position;
  lang?: Lang;
  design?: DesignLevel;
  accent?: string;
  greeting?: string;
  autoStart?: boolean;
  tour?: boolean;
  navigation?: NavigationMode;
}

/** What /widget/loader.js puts on window (the widget's script-tag build). */
export interface FluidBuddhaGlobal {
  init(options: Record<string, unknown>): HTMLElement;
  conversion(name?: string): void;
  VERSION?: string;
}

const KEY = /^fbk_[A-Za-z0-9_-]{8,200}$/;

function trimServer(url: string): string | null {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return null;
  }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') return null;
  if (u.username || u.password || u.search || u.hash) return null;
  return (u.origin + u.pathname).replace(/\/+$/, '');
}

/**
 * Read an install code (`https://fbk_…@host`), or a plain widget key plus the
 * server it belongs to. Returns null when it isn't usable.
 */
export function parseInstallCode(code: string, server?: string): InstallTarget | null {
  const text = (code || '').trim();
  if (KEY.test(text)) {
    const s = server ? trimServer(server.trim()) : null;
    return s ? { server: s, key: text } : null;
  }
  const m = /^(https?):\/\/([^@/\s?#]+)@([^\s]+)$/.exec(text);
  if (!m) return null;
  let key: string;
  try {
    key = decodeURIComponent(m[2]);
  } catch {
    return null;
  }
  const s = trimServer(`${m[1]}://${m[3]}`);
  return KEY.test(key) && s ? { server: s, key } : null;
}

/** ws(s):// address of a server, for the widget's voice connection. */
export function socketBase(server: string): string {
  return server.replace(/^http/, 'ws');
}

type Win = Window & { FluidBuddha?: FluidBuddhaGlobal };

const loading = new Map<string, Promise<FluidBuddhaGlobal>>();

/** Load the widget code from `server` once per page (it doesn't show it). */
export function loadFluidBuddha(server: string, timeoutMs = 20000): Promise<FluidBuddhaGlobal> {
  const w = window as Win;
  if (w.FluidBuddha) return Promise.resolve(w.FluidBuddha);
  const pending = loading.get(server);
  if (pending) return pending;
  const p = new Promise<FluidBuddhaGlobal>((resolve, reject) => {
    let timer = 0;
    const done = (err?: Error) => {
      window.clearTimeout(timer);
      window.removeEventListener('fluidbuddha:ready', onReady);
      if (!err && w.FluidBuddha) resolve(w.FluidBuddha);
      else reject(err || new Error('FluidBuddha: the widget did not load'));
    };
    const onReady = () => done();
    window.addEventListener('fluidbuddha:ready', onReady);
    timer = window.setTimeout(() => done(new Error('FluidBuddha: timed out loading the widget')), timeoutMs);
    const s = document.createElement('script');
    s.src = `${server}/widget/loader.js`;
    s.async = true;
    // Load only: the wrapper creates the widget itself, with your hooks.
    s.setAttribute('data-auto', 'false');
    s.onerror = () => done(new Error(`FluidBuddha: could not load ${s.src}`));
    document.head.appendChild(s);
  }).catch((err) => {
    loading.delete(server); // a later mount may retry
    throw err;
  });
  loading.set(server, p);
  return p;
}

export interface MountOptions extends WidgetOptions {
  installCode: string;
  /** Only when `installCode` is a bare widget key. */
  server?: string;
  hooks?: FluidBuddhaHooks;
  onReady?: (el: HTMLElement) => void;
  onError?: (err: Error) => void;
}

function widgetOptions(o: WidgetOptions): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const k of ['position', 'lang', 'design', 'accent', 'greeting', 'autoStart', 'tour', 'navigation'] as const) {
    if (o[k] !== undefined && o[k] !== '') out[k] = o[k];
  }
  return out;
}

/**
 * Show the widget on this page; returns a function that removes it. Safe to
 * call and undo before the widget code has arrived (React StrictMode, fast
 * route changes): nothing is left behind.
 */
export function mountWidget(opts: MountOptions): () => void {
  let el: HTMLElement | null = null;
  let cancelled = false;
  const fail = (err: Error) => {
    if (opts.onError) opts.onError(err);
    else console.warn(err.message);
  };
  const target = parseInstallCode(opts.installCode, opts.server);
  if (!target) {
    fail(new Error('FluidBuddha: invalid install code — copy it from the console (Install tab)'));
    return () => {};
  }
  if (typeof window === 'undefined') return () => {}; // server rendering
  loadFluidBuddha(target.server).then(
    (fb) => {
      if (cancelled) return;
      if (document.querySelector('fluid-buddha')) {
        fail(new Error('FluidBuddha: the widget is already on this page (installed twice?)'));
        return;
      }
      el = fb.init({
        ...widgetOptions(opts),
        backend: socketBase(target.server),
        api: target.server,
        key: target.key,
        hooks: opts.hooks || {},
      });
      opts.onReady?.(el);
    },
    (err: Error) => {
      if (!cancelled) fail(err);
    },
  );
  return () => {
    cancelled = true;
    el?.remove();
    el = null;
  };
}

/** Report a goal for A/B tests, e.g. after a demo is booked. */
export function conversion(name = 'goal'): void {
  if (typeof window === 'undefined') return;
  (window as Win).FluidBuddha?.conversion(name);
}
