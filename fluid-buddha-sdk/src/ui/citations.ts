// Answer citations (trust layer, WS8): every design level shows where a grounded
// answer came from. An ungrounded answer shows none — the agent already says out
// loud that it doesn't know (the guardrail), and a tag under small talk is noise.
import { Grounding } from '../protocol';

/** A "Sources" row for an agent message, or null when there's nothing to show.
 *  Sources with a known page route become links that `open` (host navigation). */
export function sourcesEl(grounding?: Grounding, open?: (route: string) => void): HTMLElement | null {
  if (!grounding?.found) return null;
  const row = document.createElement('div');
  const items = (grounding.sources || []).filter((s) => s.label || s.document).slice(0, 3);
  row.className = 'sources';
  row.title = `grounded · ${(grounding.confidence * 100).toFixed(0)}% match`;
  const lead = document.createElement('span');
  lead.className = 'sources-lead';
  lead.textContent = items.length ? 'Sources' : 'Grounded';
  row.appendChild(lead);
  for (const s of items) {
    const label = s.label || String(s.document || '').replace(/^\W+/, '');
    const route = s.route;
    const chip = document.createElement(route && open ? 'button' : 'span');
    chip.className = 'source';
    chip.textContent = label;
    if (s.section) chip.title = s.section;
    if (route && open) {
      (chip as HTMLButtonElement).type = 'button';
      chip.addEventListener('click', () => open(route));
    }
    row.appendChild(chip);
  }
  return row;
}
