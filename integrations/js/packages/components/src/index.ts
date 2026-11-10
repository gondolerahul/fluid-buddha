/**
 * @fluidbuddha/components — author FluidBuddha page components in React
 * (P0-8, decision D2).
 *
 * Web Components are the runtime contract: a generated page draws a customer
 * component as a custom element (`renderer: "wc:<tag>"`), setting its props as
 * element properties. This package turns a React component into that custom
 * element and produces its manifest entry from the same declaration, so the
 * component and what the agent knows about it never drift apart.
 *
 *   export const PlanTable = defineFbComponent(PlanTableView, {
 *     id: 'acme.PlanTable', tag: 'acme-plan-table',
 *     purpose: 'Compare 2–4 subscription plans',
 *     useWhen: ['compare_plans'],
 *     props: {
 *       title: { type: 'string', source: 'model_text', maxLength: 120 },
 *       tiers: { type: 'array', source: 'binding_only', required: true, maxItems: 4 },
 *     },
 *   });
 *
 * `props` is typed against the component's own props, so a declared prop that
 * the component doesn't take is a type error.
 */
import { createElement, type ComponentType } from 'react';
import { createRoot, type Root } from 'react-dom/client';

export type PropType = 'string' | 'number' | 'boolean' | 'array' | 'object' | 'any';
export type PropSource = 'model_text' | 'binding_only' | 'either';

export interface PropDecl {
  type: PropType;
  /** Who may supply the value: the model's copy, only bound API data, or either. */
  source?: PropSource;
  required?: boolean;
  maxItems?: number;
  maxLength?: number;
  enum?: string[];
}

export interface FbComponentOptions<P> {
  /** Manifest id, a dotted name such as `acme.PlanTable`. */
  id: string;
  /** Custom-element tag, e.g. `acme-plan-table` (must contain a dash). */
  tag: string;
  purpose?: string;
  useWhen?: string[];
  avoidWhen?: string[];
  props: { [K in keyof P]?: PropDecl };
  /** Render into a shadow root (default true) for style isolation. */
  shadow?: boolean;
  /** CSS injected into the shadow root. */
  styles?: string;
  version?: number;
}

/** A manifest entry as the FluidBuddha server reads it. */
export interface ManifestEntry {
  id: string;
  renderer: string;
  purpose: string;
  use_when: string[];
  avoid_when: string[];
  version: number;
  props: Record<string, {
    type: PropType; source: PropSource; required?: boolean;
    max_items?: number; max_length?: number; enum?: string[];
  }>;
}

export interface FbComponentDefinition {
  id: string;
  tag: string;
  entry: ManifestEntry;
}

export interface ManifestBundle {
  url: string;
  integrity: string;
}

const ID_RE = /^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$/;
const TAG_RE = /^[a-z][a-z0-9]*(-[a-z0-9]+)+$/;
const RESERVED = ['fluid-buddha', 'fb-'];

function checkNames(id: string, tag: string): void {
  if (!ID_RE.test(id)) throw new Error(`FluidBuddha component id "${id}" must be dotted, e.g. acme.PlanTable`);
  if (!TAG_RE.test(tag) || RESERVED.some((r) => tag.startsWith(r))) {
    throw new Error(`FluidBuddha component tag "${tag}" must be a custom-element name with a dash, not starting with fluid-buddha or fb-`);
  }
}

export function manifestEntryFor<P>(opts: FbComponentOptions<P>): ManifestEntry {
  checkNames(opts.id, opts.tag);
  const props: ManifestEntry['props'] = {};
  for (const [name, d] of Object.entries(opts.props) as [string, PropDecl | undefined][]) {
    if (!d) continue;
    const spec: ManifestEntry['props'][string] = { type: d.type, source: d.source ?? 'either' };
    if (d.required) spec.required = true;
    if (d.maxItems) spec.max_items = d.maxItems;
    if (d.maxLength) spec.max_length = d.maxLength;
    if (d.enum?.length) spec.enum = [...d.enum];
    props[name] = spec;
  }
  return {
    id: opts.id,
    renderer: `wc:${opts.tag}`,
    purpose: opts.purpose ?? '',
    use_when: [...(opts.useWhen ?? [])],
    avoid_when: [...(opts.avoidWhen ?? [])],
    version: opts.version ?? 1,
    props,
  };
}

/**
 * Register `Component` as the custom element `opts.tag` (in a browser) and
 * return its manifest entry. Safe to import in Node (e.g. by the manifest
 * CLI): without `customElements`, nothing is registered.
 */
export function defineFbComponent<P extends object>(
  Component: ComponentType<P>,
  opts: FbComponentOptions<P>,
): FbComponentDefinition {
  const entry = manifestEntryFor(opts);
  const registry = typeof customElements !== 'undefined' ? customElements : undefined;
  if (registry && typeof HTMLElement !== 'undefined' && !registry.get(opts.tag)) {
    registry.define(opts.tag, makeElementClass(Component, Object.keys(entry.props), opts));
  }
  return { id: opts.id, tag: opts.tag, entry };
}

function makeElementClass<P extends object>(
  Component: ComponentType<P>,
  propNames: string[],
  opts: FbComponentOptions<P>,
): CustomElementConstructor {
  const useShadow = opts.shadow !== false;

  class FbReactElement extends HTMLElement {
    private _props: Record<string, unknown> = {};
    private _root: Root | null = null;
    private _unmountTimer: ReturnType<typeof setTimeout> | null = null;

    constructor() {
      super();
      // Props set before this element was upgraded live as own properties;
      // move them behind the accessors.
      for (const name of propNames) {
        if (Object.prototype.hasOwnProperty.call(this, name)) {
          const v = (this as unknown as Record<string, unknown>)[name];
          delete (this as unknown as Record<string, unknown>)[name];
          this._props[name] = v;
        } else if (this.hasAttribute(name)) {
          // Names shared with built-in HTMLElement properties (title, lang…)
          // were stored as attributes before the upgrade.
          this._props[name] = this.getAttribute(name);
        }
      }
    }

    connectedCallback(): void {
      if (this._unmountTimer) { clearTimeout(this._unmountTimer); this._unmountTimer = null; }
      if (!this._root) {
        let mount: Element | ShadowRoot = this;
        if (useShadow) {
          const shadow = this.shadowRoot ?? this.attachShadow({ mode: 'open' });
          // A server-rendered page (Phase 2) may have given this element a
          // declarative shadow root with a readable fallback: replace it.
          shadow.replaceChildren();
          if (opts.styles) {
            const style = document.createElement('style');
            style.textContent = opts.styles;
            shadow.appendChild(style);
          }
          const host = document.createElement('div');
          shadow.appendChild(host);
          mount = host;
        }
        this._root = createRoot(mount as Element);
      }
      this._render();
    }

    disconnectedCallback(): void {
      // Deferred, so moving the element in the DOM doesn't remount it.
      this._unmountTimer = setTimeout(() => { this._root?.unmount(); this._root = null; }, 0);
    }

    _set(name: string, value: unknown): void {
      this._props[name] = value;
      this._render();
    }

    private _render(): void {
      if (this._root) this._root.render(createElement(Component, { ...this._props } as P));
    }
  }

  for (const name of propNames) {
    Object.defineProperty(FbReactElement.prototype, name, {
      configurable: true,
      enumerable: true,
      get(this: FbReactElement) { return (this as unknown as { _props: Record<string, unknown> })._props[name]; },
      set(this: FbReactElement, v: unknown) { this._set(name, v); },
    });
  }
  return FbReactElement;
}

/** The manifest JSON for the console ("New draft" → paste) or a manifest file. */
export function buildManifest(
  definitions: FbComponentDefinition[],
  options: { bundle?: ManifestBundle; includeDefaults?: boolean } = {},
): { include_defaults: boolean; bundle?: ManifestBundle; components: ManifestEntry[] } {
  const seen = new Set<string>();
  const components: ManifestEntry[] = [];
  for (const d of definitions) {
    if (seen.has(d.id)) throw new Error(`Duplicate FluidBuddha component id ${d.id}`);
    seen.add(d.id);
    components.push(d.entry);
  }
  const out: { include_defaults: boolean; bundle?: ManifestBundle; components: ManifestEntry[] } = {
    include_defaults: options.includeDefaults ?? true,
    components,
  };
  if (options.bundle) out.bundle = options.bundle;
  return out;
}
