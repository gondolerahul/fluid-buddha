// Holdout A/B (WS11). When the site runs an experiment, a share of visitors
// (the holdout) never sees the agent: the widget doesn't render for them. Both
// arms are measured the same way, on the site's own goal — a goal page, or the
// host calling `FluidBuddha.conversion()` — so the dashboard can show the lift
// the agent causes.
//
// The visitor id is a random string kept in localStorage: anonymous, and the
// same across this site's pages. Without storage (private mode, blocked), the
// visitor simply isn't part of the experiment and gets the agent.
//
// The arm is cached for a few hours, so repeat page views render at once; the
// server is asked again in the background to pick up a new run or a stop.
//
// Variant tests (M2-4) use the same enrolment: the arm is then a variant key
// ('a'..'d') or 'holdout', and comes with the variant's `overrides`. The answer
// also carries the site's `defaults` (its greeting and design level).

import { DesignLevel, FluidBuddhaConfig } from './config';

/** 'agent' | 'holdout' for a holdout run; 'a'..'d' | 'holdout' for a test. */
export type Arm = string;

export interface Overrides {
  greeting?: string;
  triggers?: string[];
  tour?: boolean;
  persona?: string;
  design?: DesignLevel;
}

interface Defaults {
  greeting?: string | null;
  design?: DesignLevel | null;
}

interface Enrolment {
  experiment_id: string;
  arm: Arm;
  goal_path: string | null;
  overrides?: Overrides;
  defaults?: Defaults;
  at: number;
}

const VISITOR_KEY = 'fluidbuddha:vid';
const CACHE_MS = 6 * 60 * 60 * 1000;
const ENROL_TIMEOUT_MS = 1500;
const GOAL_POLL_MS = 1000;

function storage(): Storage | null {
  try {
    const s = window.localStorage;
    const probe = '__fb_probe__';
    s.setItem(probe, '1');
    s.removeItem(probe);
    return s;
  } catch {
    return null;
  }
}

function randomId(): string {
  const bytes = new Uint8Array(16);
  const c = (globalThis as { crypto?: Crypto }).crypto;
  if (c?.getRandomValues) c.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  let s = '';
  bytes.forEach((b) => (s += String.fromCharCode(b)));
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** True when `path` is the goal page (or below it). */
export function matchesGoal(path: string, goal: string | null): boolean {
  if (!goal) return false;
  const p = path.replace(/\/+$/, '') || '/';
  const g = goal.replace(/\/+$/, '') || '/';
  return g === '/' ? p === '/' : p === g || p.startsWith(g + '/');
}

let active: Experiment | null = null;

/** Record a site goal for the current visitor (no-op outside an experiment). */
export function conversion(name = 'goal', value?: number): void {
  active?.convert(name, value);
}

export class Experiment {
  private readonly store = storage();
  readonly visitorId: string | null;
  private enrolment: Enrolment | null = null;
  /** The site's defaults when no experiment runs. */
  private siteDefaults: Defaults = {};
  private goalTimer = 0;
  private lastPath = '';
  private readonly onNav = () => this.checkGoal();

  constructor(private readonly config: FluidBuddhaConfig) {
    let vid = this.store?.getItem(VISITOR_KEY) ?? null;
    if (this.store && !vid) {
      vid = randomId();
      this.store.setItem(VISITOR_KEY, vid);
    }
    this.visitorId = vid;
  }

  get id(): string | null {
    return this.enrolment?.experiment_id ?? null;
  }

  get overrides(): Overrides {
    return this.enrolment?.overrides || {};
  }

  get defaults(): Defaults {
    return this.enrolment?.defaults || this.siteDefaults;
  }

  /** Experiments run only for keyed (tenant) sites and visitors with storage. */
  get eligible(): boolean {
    return !!(this.config.key && this.config.api && this.visitorId);
  }

  private get cacheKey(): string {
    return `fluidbuddha:exp:${this.config.key}`;
  }

  /** The arm decided on an earlier page view, when still fresh. */
  cached(): Arm | null {
    if (!this.eligible) return null;
    try {
      const e = JSON.parse(this.store?.getItem(this.cacheKey) || 'null') as Enrolment | null;
      if (e && Date.now() - e.at < CACHE_MS) {
        this.enrolment = e;
        return e.arm;
      }
    } catch {
      /* corrupt cache: ask the server */
    }
    return null;
  }

  /** Ask the server for this visitor's arm. Null when there's no experiment
   *  (or it can't be reached in time: the visitor then just gets the agent). */
  async enroll(): Promise<Arm | null> {
    if (!this.eligible) return null;
    const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    const timer = setTimeout(() => ctrl?.abort(), ENROL_TIMEOUT_MS);
    try {
      const res = await fetch(`${this.config.api.replace(/\/$/, '')}/experiment/enroll`, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        // `automated`: a browser driven by Selenium/Puppeteer/Playwright says so;
        // the server then keeps it out of the experiment (bots dilute both arms).
        body: JSON.stringify({
          key: this.config.key, site: this.config.site, visitor: this.visitorId,
          automated: typeof navigator !== 'undefined' && navigator.webdriver === true,
        }),
        signal: ctrl?.signal,
      });
      if (!res.ok) return null;
      const data = (await res.json()) as Partial<Enrolment>;
      this.siteDefaults = data.defaults || {};
      if (!data.experiment_id || typeof data.arm !== 'string' || !data.arm) {
        this.enrolment = null;
        this.store?.removeItem(this.cacheKey);
        return null;
      }
      this.enrolment = {
        experiment_id: data.experiment_id, arm: data.arm,
        goal_path: data.goal_path ?? null, overrides: data.overrides || {},
        defaults: this.siteDefaults, at: Date.now(),
      };
      this.store?.setItem(this.cacheKey, JSON.stringify(this.enrolment));
      return data.arm;
    } catch {
      return null;
    } finally {
      clearTimeout(timer);
    }
  }

  /** Start measuring: the goal page is watched in BOTH arms, and
   *  `FluidBuddha.conversion()` reports through this visitor. */
  start(): void {
    active = this;
    if (typeof window === 'undefined') return;
    this.checkGoal();
    window.addEventListener('popstate', this.onNav);
    window.addEventListener('fluidbuddha:navigated', this.onNav);
    // SPA routers change the path without an event we can hear: poll lightly.
    this.goalTimer = window.setInterval(this.onNav, GOAL_POLL_MS);
  }

  stop(): void {
    if (active === this) active = null;
    if (typeof window === 'undefined') return;
    window.removeEventListener('popstate', this.onNav);
    window.removeEventListener('fluidbuddha:navigated', this.onNav);
    window.clearInterval(this.goalTimer);
  }

  private checkGoal(): void {
    const path = typeof window !== 'undefined' ? window.location.pathname : '';
    if (path === this.lastPath) return;
    this.lastPath = path;
    if (matchesGoal(path, this.enrolment?.goal_path ?? null)) this.convert('goal_page');
  }

  convert(name = 'goal', value?: number): void {
    const e = this.enrolment;
    if (!e || !this.eligible) return;
    const url = `${this.config.api.replace(/\/$/, '')}/experiment/convert`;
    const body = JSON.stringify({
      key: this.config.key, site: this.config.site, visitor: this.visitorId,
      experiment_id: e.experiment_id, name, value,
    });
    // A beacon survives the page unloading (a form that submits and navigates).
    // text/plain keeps it a simple request: no CORS preflight.
    try {
      if (navigator.sendBeacon?.(url, new Blob([body], { type: 'text/plain' }))) return;
    } catch {
      /* fall through to fetch */
    }
    void fetch(url, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body, keepalive: true })
      .catch(() => {});
  }
}
