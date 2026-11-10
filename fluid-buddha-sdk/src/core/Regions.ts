// <fb-region>: generated regions on the host's own page (Phase 1, G1).
//
//   <fb-region name="hero"> …the page's own hero, shown until replaced… </fb-region>
//
// This is the small part that ships in the core script: the element (which
// shows the host's children through a <slot> until filled), the backend
// config, and whether the visitor has interacted yet. The controller that
// fetches and renders regions (./regions/controller.ts) loads only on pages
// that use <fb-region>, so pages without regions pay nothing for it.

import type { RegionsConfig, RegionsController } from './regions/controller';
import { loadRegions } from './regions/load';

let config: Partial<RegionsConfig> | null = null;
let controller: RegionsController | null = null;
let loading = false;
const waiting: FbRegionElement[] = [];

let interacted = false;
if (typeof window !== 'undefined') {
  const mark = () => { interacted = true; };
  for (const ev of ['scroll', 'pointerdown', 'keydown', 'touchstart']) {
    window.addEventListener(ev, mark, { once: true, passive: true });
  }
}

function ensureController(): void {
  if (controller || loading || !waiting.length) return;
  loading = true;
  loadRegions().then((m) => {
    controller = m.createController(() => interacted);
    controller.configure(config);
    for (const el of waiting.splice(0)) controller.register(el);
  }).catch(() => {
    loading = false; // the host's own content stays; try again on the next region
  });
}

/** Point generated regions at a backend (the widget calls this on start). */
export function configureRegions(cfg: Partial<RegionsConfig>): void {
  if (!cfg.api || !(cfg.key || cfg.site)) return;
  config = cfg;
  controller?.configure(cfg);
}

const BaseElement: typeof HTMLElement =
  typeof HTMLElement !== 'undefined' ? HTMLElement : (class {} as unknown as typeof HTMLElement);

export class FbRegionElement extends BaseElement {
  static readonly tagName = 'fb-region';
  filled = false;

  get regionName(): string {
    return (this.getAttribute('name') || '').trim().toLowerCase();
  }

  connectedCallback(): void {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' }).appendChild(document.createElement('slot'));
    }
    this.setAttribute('data-fb-region', this.regionName);
    if (!this.filled) this.setAttribute('data-fb-state', 'fallback');
    // Standalone use: <fb-region data-api="…" data-key="…">.
    const api = this.getAttribute('data-api');
    const key = this.getAttribute('data-key');
    if (api && key) configureRegions({ api, key });
    if (controller) controller.register(this);
    else { waiting.push(this); ensureController(); }
  }

  belowFold(): boolean {
    return this.getBoundingClientRect().top >= (window.innerHeight || 0);
  }
}

export function defineRegionElement(): void {
  if (typeof customElements !== 'undefined' && !customElements.get(FbRegionElement.tagName)) {
    customElements.define(FbRegionElement.tagName, FbRegionElement);
  }
}
