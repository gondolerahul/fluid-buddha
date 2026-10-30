// Timeline / roadmap — milestones along a horizontal axis. Each milestone
// reveals in sequence (synced to narration) and shows its detail on hover.

import { revealSequence } from './reveal';
import { Tooltip } from './interactive';
import { ensureGlassDefs, svgNode, svgRoot } from './svg';

interface TLEvent {
  date?: string;
  label?: string;
  detail?: string;
}

export function buildTimeline(state: Record<string, unknown>): HTMLElement {
  const events = (state.events as TLEvent[] | undefined) ?? [];
  const root = document.createElement('div');
  root.className = 'timeline';
  if (!events.length) {
    root.innerHTML = '<div class="empty">No timeline data.</div>';
    return root;
  }

  const W = 340;
  const H = 60 + events.length * 4;
  const axisY = H / 2;
  const pad = 26;
  const span = W - pad * 2;
  const step = events.length > 1 ? span / (events.length - 1) : 0;
  const svg = svgRoot(W, H);
  ensureGlassDefs(svg);
  const tip = new Tooltip(root);

  svg.appendChild(svgNode('line', {
    x1: pad, y1: axisY, x2: W - pad, y2: axisY, class: 'tl-axis',
  }));

  const items: SVGElement[] = [];
  events.forEach((e, i) => {
    const x = pad + i * step;
    const up = i % 2 === 0;
    const g = svgNode('g', { class: 'tl-stop' });
    g.appendChild(svgNode('circle', {
      cx: x, cy: axisY, r: 7, fill: 'url(#fbAccentFill)', filter: 'url(#fbGlow)',
      class: 'fb-glass-bead',
    }));
    g.appendChild(svgNode('circle', { cx: x - 2, cy: axisY - 2.5, r: 2, class: 'fb-glass-spec' }));
    const ly = up ? axisY - 16 : axisY + 24;
    if (e.date) g.appendChild(svgNode('text',
      { x, y: up ? axisY - 28 : axisY + 36, 'text-anchor': 'middle', class: 'tl-date' }, e.date));
    g.appendChild(svgNode('text',
      { x, y: ly, 'text-anchor': 'middle', class: 'tl-label' },
      (e.label ?? '').slice(0, 22)));
    tip.bind(g, e.detail || e.label || '');
    svg.appendChild(g);
    items.push(g);
  });

  root.appendChild(svg);
  revealSequence(items, { stepMs: 260 });
  return root;
}
