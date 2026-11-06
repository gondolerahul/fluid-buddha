// Customer Web Components in generated pages (Experience Plan, P0-8).
//
// A manifest entry can be drawn by the customer's own custom element
// (`renderer: "wc:<tag>"`). The page payload then carries `bundle` — the https
// script that defines those elements plus its subresource-integrity hash —
// which is loaded once per page view. Props are set as element *properties*
// (not attributes), after the element is defined, so components receive rich
// values (arrays, objects) exactly as bound from the site's APIs.

export interface ComponentBundle {
  url: string;
  integrity: string;
}

const TAG_RE = /^[a-z][a-z0-9]*(-[a-z0-9]+)+$/;
const SRI_RE = /^sha(256|384|512)-[A-Za-z0-9+/]+={0,2}$/;
const RESERVED = ['fluid-buddha', 'fb-'];
const UNSAFE_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

const loads = new Map<string, Promise<void>>();

/** The custom-element tag of a `wc:<tag>` section type, or null if invalid. */
export function wcTag(type: string): string | null {
  if (!type.startsWith('wc:')) return null;
  const tag = type.slice(3);
  if (!TAG_RE.test(tag) || RESERVED.some((r) => tag.startsWith(r))) return null;
  return tag;
}

export function validBundle(b: unknown): b is ComponentBundle {
  const x = b as ComponentBundle | null;
  return !!x && typeof x.url === 'string' && x.url.startsWith('https://') && !/["'<>\s\\]/.test(x.url)
    && typeof x.integrity === 'string' && SRI_RE.test(x.integrity);
}

/** Load the bundle script once (module, integrity-checked, anonymous CORS). */
export function loadBundle(bundle: ComponentBundle): Promise<void> {
  if (!validBundle(bundle)) return Promise.reject(new Error('invalid component bundle'));
  const key = `${bundle.url}#${bundle.integrity}`;
  const existing = loads.get(key);
  if (existing) return existing;
  const p = new Promise<void>((resolve, reject) => {
    const s = document.createElement('script');
    s.type = 'module';
    s.src = bundle.url;
    s.integrity = bundle.integrity;
    s.crossOrigin = 'anonymous';
    s.setAttribute('data-fb-bundle', '');
    s.addEventListener('load', () => resolve());
    s.addEventListener('error', () => { loads.delete(key); reject(new Error('component bundle failed to load')); });
    document.head.appendChild(s);
  });
  loads.set(key, p);
  return p;
}

function assignProps(el: HTMLElement, props: Record<string, unknown>): void {
  for (const [k, v] of Object.entries(props)) {
    if (UNSAFE_KEYS.has(k)) continue;
    try { (el as unknown as Record<string, unknown>)[k] = v; } catch { /* read-only prop */ }
  }
}

/** Create the customer's element; props land once the element is defined. */
export function buildCustomElement(tag: string, props: Record<string, unknown>): HTMLElement {
  const el = document.createElement(tag);
  el.className = 'fbpage-custom';
  const registry = typeof customElements !== 'undefined' ? customElements : null;
  if (!registry || registry.get(tag)) {
    assignProps(el, props);
  } else {
    // Setting properties before upgrade would shadow the class's accessors.
    registry.whenDefined(tag).then(() => assignProps(el, props)).catch(() => {});
  }
  return el;
}
