// Multi-step pages (Phase 4). A free-form plan may split its regions into steps
// (compare → choose → book). Every step is rendered — the page reads in full
// without JavaScript — and this shows one step at a time: the step list becomes
// tabs (aria-current="step"), Back / Next move between steps, and on served
// pages the step is kept in the URL hash (#step-<name>) so a reload or a shared
// link opens the same step.

import type { FlowStep } from '../../protocol';

/** The ordered list of steps (the server renders the same markup). */
export function stepNav(doc: Document, flow: FlowStep[]): HTMLOListElement {
  const ol = doc.createElement('ol');
  ol.className = 'fb-steps';
  for (const st of flow) {
    const li = doc.createElement('li');
    li.setAttribute('data-fb-step-nav', st.step);
    li.textContent = st.title || st.step;
    ol.appendChild(li);
  }
  return ol;
}

/** Show one step at a time inside `root`; returns a function that moves to a
 *  step by name, or null when the page has no steps. */
export function setupSteps(root: Element, opts: { history: boolean }): ((step: string) => void) | null {
  const doc = root.ownerDocument;
  const regions = Array.from(root.querySelectorAll<HTMLElement>(':scope > [data-fb-step]'));
  const items = Array.from(root.querySelectorAll<HTMLElement>('.fb-steps [data-fb-step-nav]'));
  const steps = items.map((li) => li.getAttribute('data-fb-step-nav') || '').filter(Boolean);
  if (steps.length < 2 || !regions.length) return null;
  // Agent and plain modes (Phase 5) show every step: nothing is hidden from them.
  if (root.closest('[data-fb-mode]')) return null;

  const nav = doc.createElement('div');
  nav.className = 'fb-step-nav';
  const back = doc.createElement('button');
  back.type = 'button';
  back.className = 'fbpage-btn fbpage-btn-secondary';
  back.textContent = 'Back';
  const next = doc.createElement('button');
  next.type = 'button';
  next.className = 'fbpage-btn';
  nav.append(back, next);
  root.appendChild(nav);

  let current = '';
  const show = (step: string, push: boolean) => {
    if (!steps.includes(step)) step = steps[0];
    current = step;
    const i = steps.indexOf(step);
    for (const el of regions) el.hidden = el.getAttribute('data-fb-step') !== step;
    for (const li of items) {
      if (li.getAttribute('data-fb-step-nav') === step) li.setAttribute('aria-current', 'step');
      else li.removeAttribute('aria-current');
    }
    back.hidden = i === 0;
    next.hidden = i === steps.length - 1;
    const following = items[i + 1];
    next.textContent = following ? `Next: ${following.textContent || steps[i + 1]}` : 'Next';
    if (push && opts.history) {
      try { history.replaceState(history.state, '', `#step-${step}`); } catch { /* sandboxed */ }
    }
  };
  for (const li of items) {
    li.tabIndex = 0;
    li.setAttribute('role', 'button');
    const go = () => show(li.getAttribute('data-fb-step-nav') || '', true);
    li.addEventListener('click', go);
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); }
    });
  }
  const move = (d: number) => {
    show(steps[Math.max(0, Math.min(steps.length - 1, steps.indexOf(current) + d))], true);
    (root.querySelector('.fb-steps') as HTMLElement | null)?.scrollIntoView?.({ block: 'nearest' });
  };
  back.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));

  const fromHash = () => (opts.history ? /^#step-(.+)$/.exec(window.location.hash)?.[1] || '' : '');
  show(fromHash(), false);
  if (opts.history) window.addEventListener('hashchange', () => { const s = fromHash(); if (s) show(s, false); });
  return (step: string) => show(step, true);
}
