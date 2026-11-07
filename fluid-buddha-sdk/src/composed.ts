// Script of a server-rendered composed page (Phase 2):
// dist/fluid-buddha-composed.global.js (window.FluidBuddhaComposed).
//
// The page arrives as HTML that already reads well (P2-1). This script:
//   * hydrates the interactive sections (charts, ROI calculators) from the
//     page data in <script id="fb-page-data">;
//   * sends enquiry forms with fetch to /leads (without JavaScript they post
//     to the server's form endpoint);
//   * shows multi-step pages (Phase 4) one step at a time, with Back / Next;
//   * declares the page's tools to an in-browser agent (Phase 5);
//   * applies plan patches from the conversation (P2-4) to the page, when the
//     widget on the page relays them as `fluidbuddha:plan_patch` events.

import type { PageSection } from './protocol';
import { PageRenderer } from './ui/page/PageRenderer';
import { applyPatch, PlanPatch } from './core/patch/patcher';
import { rememberPlan } from './core/taste';
import { trackEngagement, whyControl } from './core/why';
import { setupSteps } from './ui/page/steps';
import { declareTools } from './core/agentTools';

interface PageData {
  why?: string[];
  plan_id?: string;
  api?: string;
  key?: string;
  sections?: PageSection[];
}

function readData(doc: Document): PageData {
  try {
    return JSON.parse(doc.getElementById('fb-page-data')?.textContent || '{}') as PageData;
  } catch {
    return {};
  }
}

function sender(data: PageData) {
  return async (values: Record<string, string>): Promise<boolean> => {
    if (!data.api || !data.key) return false;
    try {
      const res = await fetch(`${data.api.replace(/\/$/, '')}/leads`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: data.key, values }),
      });
      return res.ok;
    } catch {
      return false;
    }
  };
}

/** Hydrate the page; returns how many sections were taken over. */
export function hydrate(doc: Document = document): number {
  const data = readData(doc);
  const send = sender(data);
  let n = 0;
  for (const section of data.sections || []) {
    if (!section.id || section.type.startsWith('wc:')) continue;
    const host = Array.from(doc.querySelectorAll('[data-fb-hydrate]'))
      .find((el) => el.getAttribute('data-fb-region') === section.id);
    if (!host || !host.parentElement) continue;
    if (section.type === 'enquiry_form') {
      // Keep the server's form (it works without JS); send it with fetch.
      const form = host.querySelector('form');
      form?.addEventListener('submit', (e) => {
        e.preventDefault();
        const values: Record<string, string> = {};
        new FormData(form).forEach((v, k) => { if (!k.startsWith('_')) values[k] = String(v); });
        void send(values).then((ok) => {
          const msg = doc.createElement('p');
          msg.className = 'fbpage-body';
          msg.textContent = ok ? 'Thank you — we will be in touch.' : 'Sorry, that did not send. Please try again.';
          form.replaceWith(msg);
        });
      });
      host.removeAttribute('data-fb-hydrate');
      n++;
      continue;
    }
    const el = new PageRenderer(host.parentElement, (p) => send(p.values)).renderSection(section);
    if (el) {
      host.replaceWith(el);
      n++;
    }
  }
  // Customer Web Components replace their declarative fallback when they upgrade;
  // hand them their props from the server (kept as JSON on the element).
  for (const el of Array.from(doc.querySelectorAll('[data-fb-props]'))) {
    const tag = el.tagName.toLowerCase();
    const set = () => {
      try {
        const props = JSON.parse(el.getAttribute('data-fb-props') || '{}') as Record<string, unknown>;
        for (const [k, v] of Object.entries(props)) {
          if (k !== '__proto__' && k !== 'constructor' && k !== 'prototype') (el as unknown as Record<string, unknown>)[k] = v;
        }
      } catch { /* bad props: keep the fallback */ }
    };
    if (customElements.get(tag)) set();
    else customElements.whenDefined(tag).then(set).catch(() => {});
  }
  // "Why this?" and engagement rewards (Phase 3).
  const main = doc.querySelector('main[data-fb-plan]');
  const inner = main?.querySelector('.fbpage-inner');
  const why = whyControl(doc, data.why);
  if (why && inner) inner.prepend(why);
  if (main && data.api) {
    trackEngagement(main, { api: data.api, key: data.key || '' }, data.plan_id);
    rememberPlan(data.plan_id);
  }
  // A multi-step page (Phase 4): the server rendered every step; show one at a time.
  if (inner) setupSteps(inner, { history: true });
  // Page-declared tools for an in-browser agent, when the browser offers one (Phase 5).
  if (main) declareTools(main);
  window.addEventListener('fluidbuddha:plan_patch', (e) => {
    applyPatch((e as CustomEvent<PlanPatch>).detail, [doc], send);
  });
  return n;
}

if (typeof document !== 'undefined' && document.getElementById('fb-page-data')) {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => hydrate(), { once: true });
  else hydrate();
}

export { applyPatch };
