// Proactive triggers (M2-3): the agent speaks up first, at the right moment.
//
// The site's rules come from /widget/triggers (cached for the visit). Each page
// view arms the rules whose pages match; nothing runs until one could fire,
// and at most one fires per page view (highest priority first in a tie).
// Caps: `max_per_day` per visitor and rule, nothing more this visit after the
// visitor dismisses one or starts talking, never while the agent is open.
// What happened is reported (shown / clicked / dismissed / engaged) so the
// console can show each rule's performance.

import { FluidBuddhaConfig } from './config';

export interface TriggerRule {
  id: string;
  kind: 'time_on_page' | 'scroll_depth' | 'exit_intent' | 'return_visit';
  pages: string[];
  message: string;
  action: 'nudge' | 'open';
  max_per_day: number;
  priority: number;
  seconds?: number;
  percent?: number;
  visits?: number;
  within_days?: number;
}

type TriggerEvent = 'shown' | 'clicked' | 'dismissed' | 'engaged';

const CACHE_MS = 10 * 60 * 1000;
const MUTED = 'fluidbuddha:trg:muted';
const VISITS = 'fluidbuddha:visits';
const VISIT_FLAG = 'fluidbuddha:visit';

/** `/pricing*` matches /pricing and /pricing/teams; no globs = every page. */
export function pageMatches(path: string, globs: string[]): boolean {
  if (!globs.length) return true;
  const p = path.replace(/\/+$/, '') || '/';
  return globs.some((g) => {
    const rx = new RegExp('^' + g.replace(/\/+$/, '').replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '/?$');
    return rx.test(p) || rx.test(p + '/');
  });
}

function store(kind: 'local' | 'session'): Storage | null {
  try {
    return kind === 'local' ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export class Triggers {
  private rules: TriggerRule[] = [];
  private cleanups: (() => void)[] = [];
  private firedThisPage = false;
  private clicked: TriggerRule | null = null;
  private engagedSent = false;
  private readonly local = store('local');
  private readonly session = store('session');
  private readonly onNav = () => this.arm();

  constructor(
    private readonly config: FluidBuddhaConfig,
    private readonly visitorId: string | null,
    private readonly fire: (rule: TriggerRule) => void,
    private readonly busy: () => boolean,
  ) {}

  private get base(): string {
    return (this.config.api || '').replace(/\/$/, '');
  }

  async start(): Promise<void> {
    if (!this.config.key || !this.visitorId) return;
    this.countVisit();
    this.rules = await this.load();
    if (!this.rules.length) return;
    window.addEventListener('fluidbuddha:navigated', this.onNav);
    window.addEventListener('popstate', this.onNav);
    this.arm();
  }

  stop(): void {
    this.disarm();
    window.removeEventListener('fluidbuddha:navigated', this.onNav);
    window.removeEventListener('popstate', this.onNav);
  }

  private async load(): Promise<TriggerRule[]> {
    const ck = `fluidbuddha:trg:${this.config.key}`;
    try {
      const hit = JSON.parse(this.session?.getItem(ck) || 'null') as { at: number; rules: TriggerRule[] } | null;
      if (hit && Date.now() - hit.at < CACHE_MS) return hit.rules;
    } catch {
      /* stale cache: refetch */
    }
    try {
      const res = await fetch(`${this.base}/widget/triggers?key=${encodeURIComponent(this.config.key || '')}`);
      if (!res.ok) return [];
      const rules = ((await res.json()).rules || []) as TriggerRule[];
      this.session?.setItem(ck, JSON.stringify({ at: Date.now(), rules }));
      return rules;
    } catch {
      return [];
    }
  }

  /** A visit is a browser session; remembered for return-visit rules. */
  private countVisit(): void {
    if (!this.local || !this.session || this.session.getItem(VISIT_FLAG)) return;
    this.session.setItem(VISIT_FLAG, '1');
    let times: number[] = [];
    try {
      times = JSON.parse(this.local.getItem(VISITS) || '[]');
    } catch {
      /* reset */
    }
    times = [...times.filter((t) => typeof t === 'number'), Date.now()].slice(-50);
    this.local.setItem(VISITS, JSON.stringify(times));
  }

  private visitsWithin(days: number): number {
    try {
      const since = Date.now() - days * 86_400_000;
      return (JSON.parse(this.local?.getItem(VISITS) || '[]') as number[]).filter((t) => t >= since).length;
    } catch {
      return 0;
    }
  }

  private muted(): boolean {
    return this.session?.getItem(MUTED) === '1';
  }

  /** Nothing more this visit (dismissed, or the visitor started talking). */
  mute(): void {
    this.session?.setItem(MUTED, '1');
    this.disarm();
  }

  private shownToday(rule: TriggerRule): number {
    try {
      const v = JSON.parse(this.local?.getItem(`fluidbuddha:trg:${rule.id}`) || 'null') as { d: string; n: number } | null;
      return v && v.d === today() ? v.n : 0;
    } catch {
      return 0;
    }
  }

  private disarm(): void {
    this.cleanups.splice(0).forEach((f) => f());
  }

  /** Arm this page view's rules (also after an SPA navigation). */
  arm(): void {
    this.disarm();
    this.firedThisPage = false;
    if (this.muted()) return;
    const path = typeof location !== 'undefined' ? location.pathname : '/';
    const rules = this.rules
      .filter((r) => pageMatches(path, r.pages) && this.shownToday(r) < r.max_per_day)
      .sort((a, b) => b.priority - a.priority);
    for (const r of rules) this.watch(r);
  }

  private go(rule: TriggerRule): void {
    if (this.firedThisPage || this.muted() || this.busy()) return;
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
    this.firedThisPage = true;
    this.disarm();
    this.local?.setItem(`fluidbuddha:trg:${rule.id}`, JSON.stringify({ d: today(), n: this.shownToday(rule) + 1 }));
    this.report(rule, 'shown');
    this.fire(rule);
  }

  private watch(rule: TriggerRule): void {
    const later = (ms: number, fn: () => void) => {
      const t = setTimeout(fn, ms);
      this.cleanups.push(() => clearTimeout(t));
    };
    if (rule.kind === 'time_on_page') {
      later((rule.seconds ?? 20) * 1000, () => this.go(rule));
    } else if (rule.kind === 'return_visit') {
      if (this.visitsWithin(rule.within_days ?? 30) >= (rule.visits ?? 2)) later(3000, () => this.go(rule));
    } else if (rule.kind === 'scroll_depth') {
      const onScroll = () => {
        const doc = document.documentElement;
        const depth = ((window.scrollY + window.innerHeight) / Math.max(1, doc.scrollHeight)) * 100;
        if (depth >= (rule.percent ?? 60)) this.go(rule);
      };
      window.addEventListener('scroll', onScroll, { passive: true });
      this.cleanups.push(() => window.removeEventListener('scroll', onScroll));
    } else if (rule.kind === 'exit_intent') {
      // Desktop: the pointer leaves through the top of the window (towards the
      // tabs or the address bar). Only after a few seconds on the page.
      let ready = false;
      later(5000, () => (ready = true));
      const onOut = (e: MouseEvent) => {
        if (ready && !e.relatedTarget && e.clientY <= 0) this.go(rule);
      };
      document.addEventListener('mouseout', onOut);
      this.cleanups.push(() => document.removeEventListener('mouseout', onOut));
    }
  }

  /** The visitor acted on a trigger. */
  clickedRule(rule: TriggerRule): void {
    this.clicked = rule;
    this.report(rule, 'clicked');
  }

  dismissed(rule: TriggerRule): void {
    this.report(rule, 'dismissed');
    this.mute();
  }

  /** The visitor asked something: credit the trigger they clicked, once. */
  engaged(): void {
    this.mute();
    if (this.clicked && !this.engagedSent) {
      this.engagedSent = true;
      this.report(this.clicked, 'engaged');
    }
  }

  private report(rule: TriggerRule, event: TriggerEvent): void {
    const body = JSON.stringify({
      key: this.config.key, visitor: this.visitorId, rule_id: rule.id, event,
      page: typeof location !== 'undefined' ? location.pathname : undefined,
      automated: typeof navigator !== 'undefined' && navigator.webdriver === true,
    });
    const url = `${this.base}/widget/triggers/event`;
    try {
      if (typeof navigator !== 'undefined' && navigator.sendBeacon?.(url, body)) return;
    } catch {
      /* fall back to fetch */
    }
    void fetch(url, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body, keepalive: true })
      .catch(() => undefined);
  }
}
