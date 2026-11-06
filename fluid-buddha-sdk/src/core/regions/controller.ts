// Generated regions: the part loaded on demand (Phase 1, adaptive slots / G1).
//
// The core script only defines <fb-region> (src/core/Regions.ts). The first
// time a region appears on a page, this controller loads, and every region on
// the page is fetched in ONE request to POST /experience/regions with the page
// and the visitor's signals (path, UTM tags, referrer, search query). A region
// the server fills renders in its own shadow root with the generated-page
// styles and the site's design tokens; one it doesn't fill keeps the host's
// children (shown through a <slot>), so the page never loses content and
// nothing waits on a model.
//
// Morph rule: when the first answer is `pending` (the plan is being built),
// the controller asks once more after `retry_after_ms` and then only fills a
// region if the visitor hasn't interacted yet or the region is below the fold,
// so visible content never jumps under someone who is reading.

import type { PageSection } from '../../protocol';
import { PageRenderer } from '../../ui/page/PageRenderer';
import { EXTREME_STYLES } from '../../ui/styles';
import { applyTokens } from '../designSystem';
import { optionsFromAttributes, resolveConfig } from '../config';
import { visitorId } from '../Experiment';
import { getTaste, rememberPlan } from '../taste';
import { trackEngagement, whyControl, WHY_STYLES } from '../why';

export interface RegionsConfig {
  api: string;
  key: string;
  site: string;
}

/** What the controller needs from a <fb-region> element (core side). */
export interface RegionHost extends HTMLElement {
  readonly regionName: string;
  filled: boolean;
  belowFold(): boolean;
}

interface RegionsAnswer {
  regions?: Record<string, PageSection>;
  plan_id?: string;
  tokens?: Record<string, string>;
  bundle?: { url: string; integrity: string };
  pending?: boolean;
  retry_after_ms?: number;
  why?: string[];
}

const NAME_RE = /^[a-z][a-z0-9-]{0,39}$/;
const MAX_RETRY_MS = 10000;

const REGION_STYLES = `
:host { display: block; }
.fbpage-region {
  --fb-accent: #c9a24a; --fb-fg: currentColor; --fb-surface: rgba(127,127,127,.08); --fb-void: transparent;
  color: var(--ds-color-text, inherit); font-family: var(--ds-font, inherit);
  display: flex; flex-direction: column; gap: 24px;
}
.fbpage-region .fbpage-hero { padding: 32px 0 16px; }
`;

function signals(): Record<string, string> {
  const out: Record<string, string> = {};
  try {
    const q = new URLSearchParams(window.location.search);
    for (const k of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term']) {
      const v = q.get(k);
      if (v) out[k] = v.slice(0, 200);
    }
    const query = q.get('q') || q.get('query');
    if (query) out.q = query.slice(0, 300);
    if (document.referrer) out.referrer = document.referrer.slice(0, 500);
  } catch { /* no location in some embeds */ }
  return out;
}

function fill(el: RegionHost, section: PageSection, answer: RegionsAnswer,
              enquiry: (values: Record<string, string>) => Promise<boolean>, cfg: RegionsConfig): void {
  const root = el.shadowRoot;
  if (!root) return;
  const style = document.createElement('style');
  style.textContent = EXTREME_STYLES + REGION_STYLES + WHY_STYLES;
  const wrap = document.createElement('div');
  wrap.className = 'fbpage-region';
  applyTokens(wrap, answer.tokens);
  new PageRenderer(wrap, (p) => enquiry(p.values)).render({
    sync_id: answer.plan_id || '', title: '', sections: [section],
    plan_id: answer.plan_id, bundle: answer.bundle,
  });
  if (!wrap.childElementCount) return; // nothing drawable: keep the fallback
  // "Why this?" (Phase 3) and engagement rewards for the plan that drew it.
  const why = whyControl(document, answer.why);
  if (why) wrap.prepend(why);
  trackEngagement(wrap, cfg, answer.plan_id);
  rememberPlan(answer.plan_id);
  root.replaceChildren(style, wrap);
  el.filled = true;
  el.setAttribute('data-fb-state', 'ready');
  if (answer.plan_id) el.setAttribute('data-fb-plan', answer.plan_id);
  el.dispatchEvent(new CustomEvent('fluidbuddha:region', {
    bubbles: true, detail: { name: el.regionName, plan_id: answer.plan_id, component: section.component },
  }));
}

export class RegionsController {
  private config: RegionsConfig | null = null;
  private queue = new Set<RegionHost>();
  private scheduled = false;

  constructor(private readonly interacted: () => boolean) {}

  configure(cfg: Partial<RegionsConfig> | null): void {
    if (!cfg || !cfg.api || !(cfg.key || cfg.site)) return;
    this.config = { api: cfg.api.replace(/\/$/, ''), key: cfg.key || '', site: cfg.site || '' };
    this.schedule();
  }

  /** Config from the widget's script tag, when the widget isn't on the page. */
  private discover(): void {
    if (this.config || typeof document === 'undefined') return;
    const script = document.querySelector('script[data-backend], script[data-key]');
    if (!script) return;
    const c = resolveConfig(optionsFromAttributes(script));
    this.configure({ api: c.api, key: c.key, site: c.key ? '' : c.site });
  }

  register(el: RegionHost): void {
    this.queue.add(el);
    this.schedule();
  }

  private schedule(): void {
    if (this.scheduled || !this.queue.size) return;
    this.scheduled = true;
    setTimeout(() => {
      this.scheduled = false;
      this.discover();
      const els = [...this.queue].filter((e) => e.isConnected && !e.filled && NAME_RE.test(e.regionName));
      if (!this.config || !els.length) return;
      this.queue.clear();
      void this.fetch(els, false);
    }, 0);
  }

  private async fetch(els: RegionHost[], retry: boolean): Promise<void> {
    const cfg = this.config!;
    let answer: RegionsAnswer = {};
    try {
      const res = await fetch(`${cfg.api}/experience/regions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key: cfg.key || undefined, site: cfg.key ? undefined : cfg.site,
          visitor: visitorId() || undefined, page: window.location.pathname,
          regions: [...new Set(els.map((e) => e.regionName))], signals: signals(), taste: getTaste(),
          lang: (document.documentElement.lang || '').toLowerCase().startsWith('hi') ? 'hi' : 'en',
          automated: !!(navigator as { webdriver?: boolean }).webdriver,
        }),
      });
      if (!res.ok) return;
      answer = (await res.json()) as RegionsAnswer;
    } catch {
      return; // the host's own content stays
    }
    const regions = answer.regions || {};
    for (const el of els) {
      const section = regions[el.regionName];
      if (!section) continue;
      if (retry && this.interacted() && !el.belowFold()) continue; // never jump visible content
      fill(el, section, answer, (values) => this.enquiry(values), cfg);
    }
    if (answer.pending && !retry) {
      const wait = Math.min(Math.max(answer.retry_after_ms || 2500, 500), MAX_RETRY_MS);
      setTimeout(() => {
        const left = els.filter((e) => e.isConnected && !e.filled);
        if (left.length) void this.fetch(left, true);
      }, wait);
    }
  }

  /** A generated enquiry form posts straight to /leads, like the widget's. */
  private async enquiry(values: Record<string, string>): Promise<boolean> {
    const cfg = this.config;
    if (!cfg) return false;
    try {
      const res = await fetch(`${cfg.api}/leads`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: cfg.key || undefined, site: cfg.key ? undefined : cfg.site, values }),
      });
      return res.ok;
    } catch {
      return false;
    }
  }
}

export function createController(interacted: () => boolean): RegionsController {
  return new RegionsController(interacted);
}
