// The visitor's taste (Phase 3): how they like things presented.
//
// Anonymous visitors: the profile lives in sessionStorage for this visit and
// travels with each request; nothing is stored on the server. A visitor who
// chose "Remember me" also gets it saved server-side (the server decides).
// A compact copy of the confident values goes in a session cookie, `fbtaste`,
// so a server-rendered page (the Next.js adapter) can be composed for it.
//
// Functions take the backend config explicitly so the core, the regions
// controller and served pages can share them (state is in sessionStorage).

import { visitorId } from './Experiment';

export interface TasteConfig { api: string; key: string; site?: string }
export interface TasteRaw { dims: Record<string, { value: string; confidence: number; source: string; at: number }>;
  interests: Record<string, number> }
export interface TasteEvent { type: string; dim?: string; value?: string; topic?: string }

const KEY = 'fluidbuddha:taste';
const PLANS = 'fluidbuddha:plans';
const SENT = 'fluidbuddha:fb-sent';
const pending: TasteEvent[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;

function store(): Storage | null {
  try { return window.sessionStorage; } catch { return null; }
}

function read<T>(k: string, fallback: T): T {
  try { return JSON.parse(store()?.getItem(k) || 'null') ?? fallback; } catch { return fallback; }
}

function write(k: string, v: unknown): void {
  try { store()?.setItem(k, JSON.stringify(v)); } catch { /* storage full or blocked */ }
}

export function getTaste(): TasteRaw | null {
  return read<TasteRaw | null>(KEY, null);
}

/** Keep the server's merged profile (and its compact cookie form). */
export function setTaste(raw: TasteRaw | null, compact?: string): void {
  if (raw) write(KEY, raw);
  if (compact !== undefined && typeof document !== 'undefined') {
    // A session cookie: functional, no identity, readable by the site's own server.
    document.cookie = `fbtaste=${encodeURIComponent(compact)}; path=/; SameSite=Lax`;
  }
}

async function flush(cfg: TasteConfig): Promise<void> {
  timer = null;
  if (!pending.length || !cfg.api) return;
  const events = pending.splice(0, pending.length);
  try {
    const res = await fetch(`${cfg.api.replace(/\/$/, '')}/experience/taste`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: cfg.key || undefined, site: cfg.key ? undefined : cfg.site,
        visitor: visitorId() || undefined, taste: getTaste(), events }),
    });
    if (!res.ok) return;
    const out = await res.json() as { raw?: TasteRaw; compact?: string };
    setTaste(out.raw || null, out.compact);
  } catch { /* offline: try with the next event */ }
}

/** Record a taste event; sent in a small batch. */
export function tasteEvent(cfg: TasteConfig, ev: TasteEvent, now = false): void {
  pending.push(ev);
  if (pending.length > 30) pending.splice(0, pending.length - 30);
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => void flush(cfg), now ? 0 : 1500);
}

/** The visitor's own settings are the first signals (once per visit). */
export function initTaste(cfg: TasteConfig): void {
  if (typeof window === 'undefined' || !window.matchMedia || read(KEY + ':init', false)) return;
  write(KEY + ':init', true);
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) tasteEvent(cfg, { type: 'reduced_motion' });
  if (window.matchMedia('(prefers-color-scheme: dark)').matches) tasteEvent(cfg, { type: 'dark_scheme' });
}

/** Plans served to this visitor this visit (for rewards). */
export function rememberPlan(planId: string | undefined): void {
  if (!planId) return;
  const list = read<string[]>(PLANS, []).filter((p) => p !== planId);
  list.unshift(planId);
  write(PLANS, list.slice(0, 10));
}

/** A reward for the plans that served this visitor (engage | convert), once each. */
export function planFeedback(cfg: TasteConfig, event: 'engage' | 'convert', planIds?: string[]): void {
  const ids = planIds || read<string[]>(PLANS, []);
  const sent = read<string[]>(SENT, []);
  const fresh = ids.filter((id) => !sent.includes(`${event}:${id}`));
  const vid = visitorId();
  if (!fresh.length || !vid || !cfg.api) return;
  write(SENT, [...sent, ...fresh.map((id) => `${event}:${id}`)].slice(-60));
  void fetch(`${cfg.api.replace(/\/$/, '')}/experience/feedback`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, keepalive: true,
    body: JSON.stringify({ key: cfg.key || undefined, site: cfg.key ? undefined : cfg.site, visitor: vid,
      plan_ids: fresh, event }),
  }).catch(() => {});
}

/** Ask the widget to open the preferences panel. */
export function openPreferences(): void {
  window.dispatchEvent(new CustomEvent('fluidbuddha:preferences'));
}
