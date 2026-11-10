// Plan patches (P2-4): apply an edit of a composed page in place.
//
//   {plan_id, ops: [{op: 'add'|'replace'|'remove'|'move', region, section?, before?, animation?}]}
//
// Applied to every element carrying that `data-fb-plan` under the given roots
// (the widget's own page surface, or a server-rendered page), so only the
// regions that changed move; what the visitor is reading stays put. Animations
// use the Web Animations API (no stylesheet needed).

import type { PageSection } from '../../protocol';
import { PageRenderer } from '../../ui/page/PageRenderer';

// The same chunk carries the page renderer: the widget's Extreme page surface
// creates it on the first page, so the core script doesn't ship it.
export { PageRenderer };

export interface PlanPatch {
  plan_id: string;
  ops: Array<{ op: string; region: string; section?: PageSection; before?: string | null; animation?: string }>;
}

type Root = Document | ShadowRoot | Element;
const ID_RE = /^pl_[0-9a-f]{10}$/;

function animate(el: Element, kind?: string): void {
  const a = (el as HTMLElement).animate;
  if (typeof a !== 'function') return;
  const frames = kind === 'highlight'
    ? [{ boxShadow: '0 0 0 3px rgba(201,162,74,.8)' }, { boxShadow: '0 0 0 0 rgba(201,162,74,0)' }]
    : [{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }];
  try { (el as HTMLElement).animate(frames, { duration: 700, easing: 'ease-out' }); } catch { /* no-op */ }
}

function region(container: Element, id: string): Element | null {
  for (const el of Array.from(container.querySelectorAll('[data-fb-region]'))) {
    if (el.getAttribute('data-fb-region') === id) return el;
  }
  return null;
}

/** Apply a patch; returns how many page containers it changed. */
export function applyPatch(
  patch: PlanPatch, roots: Root[],
  enquiry: (values: Record<string, string>) => Promise<boolean> = async () => false,
): number {
  if (!patch || !ID_RE.test(patch.plan_id) || !Array.isArray(patch.ops)) return 0;
  let changed = 0;
  for (const root of roots) {
    const containers = Array.from(root.querySelectorAll(`[data-fb-plan="${patch.plan_id}"]`));
    for (const host of containers) {
      // A server-rendered page wraps its sections in .fbpage-inner.
      // Direct child, without `:scope` (jsdom 30 misses `:scope` inside shadow roots).
      const container = Array.from(host.children).find((el) => el.classList.contains('fbpage-inner')) || host;
      const renderer = new PageRenderer(container as HTMLElement, (p) => enquiry(p.values));
      for (const op of patch.ops) {
        const cur = region(container, op.region);
        const before = op.before ? region(container, op.before) : null;
        if (op.op === 'remove') {
          cur?.remove();
        } else if (op.op === 'move' && cur) {
          container.insertBefore(cur, before);
        } else if ((op.op === 'add' || op.op === 'replace') && op.section) {
          const el = renderer.renderSection(op.section);
          if (!el) continue;
          if (op.op === 'replace' && cur) cur.replaceWith(el);
          else if (!cur) container.insertBefore(el, before);
          else continue;
          animate(el, op.animation);
        }
      }
      changed++;
    }
  }
  return changed;
}
