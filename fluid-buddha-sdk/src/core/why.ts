// "Why am I seeing this?" (Phase 3, P3-5) for generated regions and served
// pages, plus the engagement rewards those regions send for the bandit.

import { openPreferences, planFeedback, TasteConfig } from './taste';

export const WHY_STYLES = `.fb-why{font-size:.8rem;opacity:.75;margin:0 0 6px}
.fb-why button{font:inherit;background:none;border:0;color:inherit;text-decoration:underline;cursor:pointer;padding:0}
.fb-why span{margin-left:6px}`;

/** A small "Why this?" control that reveals the reasons and a way to change them. */
export function whyControl(doc: Document, reasons: string[] | undefined): HTMLElement | null {
  if (!reasons || !reasons.length) return null;
  const p = doc.createElement('p');
  p.className = 'fb-why';
  const toggle = doc.createElement('button');
  toggle.type = 'button';
  toggle.textContent = 'Why this?';
  toggle.setAttribute('aria-expanded', 'false');
  const detail = doc.createElement('span');
  detail.hidden = true;
  detail.textContent = reasons.join(' · ') + ' · ';
  const change = doc.createElement('button');
  change.type = 'button';
  change.textContent = 'Change your preferences';
  change.addEventListener('click', () => openPreferences());
  detail.appendChild(change);
  toggle.addEventListener('click', () => {
    detail.hidden = !detail.hidden;
    toggle.setAttribute('aria-expanded', String(!detail.hidden));
  });
  p.append(toggle, detail);
  return p;
}

/** CTA clicks and form submits inside `root` reward the plan (once per visit). */
export function trackEngagement(root: Element | ShadowRoot, cfg: TasteConfig, planId: string | undefined): void {
  if (!planId) return;
  const reward = () => planFeedback(cfg, 'engage', [planId]);
  root.addEventListener('click', (e) => {
    const t = e.target as Element | null;
    if (t?.closest?.('.fbpage-btn, [data-fb-action]')) reward();
  });
  root.addEventListener('submit', reward, true);
}
