// Component/architecture diagram — labelled boxes laid out on a grid with
// arrowed connectors between them, drawn in SVG. Good for system architecture
// ("frontend → API → DB"). Boxes then connectors reveal in sequence (Req 3.5.2).

import { revealSequence } from './reveal';
import { ensureGlassDefs, svgNode, svgRoot } from './svg';

interface DiagramComponent { id?: string; label?: string; group?: string }
interface DiagramConnection { from?: string; to?: string; label?: string }

export interface ComponentDiagramState {
  components?: DiagramComponent[];
  connections?: DiagramConnection[];
}

export function buildComponentDiagram(state: Record<string, unknown>): HTMLElement {
  const components = (state.components as DiagramComponent[] | undefined) ?? [];
  const connections = (state.connections as DiagramConnection[] | undefined) ?? [];

  const root = document.createElement('div');
  root.className = 'cdiag';
  if (components.length === 0) {
    root.innerHTML = '<div class="empty">No diagram data.</div>';
    return root;
  }

  const cols = Math.min(components.length, Math.ceil(Math.sqrt(components.length)) + 1);
  const rows = Math.ceil(components.length / cols);
  const boxW = 92;
  const boxH = 46;
  const gapX = 36;
  const gapY = 44;
  const padX = 16;
  const padY = 16;
  const W = padX * 2 + cols * boxW + (cols - 1) * gapX;
  const H = padY * 2 + rows * boxH + (rows - 1) * gapY;
  const svg = svgRoot(W, H);
  ensureGlassDefs(svg);

  const defs = svgNode('defs');
  const marker = svgNode('marker', {
    id: 'fb-arrow-c', viewBox: '0 0 10 10', refX: 9, refY: 5,
    markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse',
  });
  marker.appendChild(svgNode('path', { d: 'M0,0 L10,5 L0,10 z', class: 'fb-arrow-head' }));
  defs.appendChild(marker);
  svg.appendChild(defs);

  const center = new Map<string, { x: number; y: number }>();
  components.forEach((c, i) => {
    const col = i % cols;
    const r = Math.floor(i / cols);
    const x = padX + col * (boxW + gapX);
    const y = padY + r * (boxH + gapY);
    center.set(c.id ?? String(i), { x: x + boxW / 2, y: y + boxH / 2 });
  });

  // Connectors first (so boxes paint over the line ends), revealed after boxes.
  const connEls: SVGElement[] = [];
  connections.forEach((cn) => {
    const a = center.get(cn.from ?? '');
    const b = center.get(cn.to ?? '');
    if (!a || !b) return;
    const line = svgNode('line', {
      x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: 'cdiag-edge',
      'marker-end': 'url(#fb-arrow-c)',
    });
    svg.appendChild(line);
    connEls.push(line);
  });

  const boxEls: SVGElement[] = [];
  components.forEach((c, i) => {
    const col = i % cols;
    const r = Math.floor(i / cols);
    const x = padX + col * (boxW + gapX);
    const y = padY + r * (boxH + gapY);
    const g = svgNode('g', { class: 'cdiag-box' });
    // Liquid-glass node: frosted body + glow, a bright top sheen, a crisp rim.
    g.appendChild(svgNode('rect', {
      x, y, width: boxW, height: boxH, rx: 12,
      fill: 'url(#fbGlassFill)', filter: 'url(#fbGlow)', class: 'fb-glass-rect',
    }));
    g.appendChild(svgNode('rect', {
      x: x + 1, y: y + 1, width: boxW - 2, height: boxH * 0.46, rx: 11,
      class: 'fb-glass-sheen',
    }));
    g.appendChild(svgNode('text', {
      x: x + boxW / 2, y: y + boxH / 2 + 4, 'text-anchor': 'middle',
    }, c.label ?? c.id ?? `C${i + 1}`));
    svg.appendChild(g);
    boxEls.push(g);
  });

  root.appendChild(svg);
  revealSequence([...boxEls, ...connEls], { stepMs: 220 });
  return root;
}
