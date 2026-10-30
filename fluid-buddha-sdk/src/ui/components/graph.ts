// Node-link graph — a circular layout of nodes with connecting edges, drawn in
// SVG. Good for relationship/dependency graphs. Nodes then edges reveal in
// sequence (Req 3.5.2).

import { revealSequence } from './reveal';
import { ensureGlassDefs, svgNode, svgRoot } from './svg';

interface GraphNode { id?: string; label?: string }
interface GraphEdge { from?: string; to?: string; label?: string }

export interface GraphState {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  directed?: boolean;
}

export function buildGraph(state: Record<string, unknown>): HTMLElement {
  const nodes = (state.nodes as GraphNode[] | undefined) ?? [];
  const edges = (state.edges as GraphEdge[] | undefined) ?? [];
  const directed = state.directed !== false;

  const root = document.createElement('div');
  root.className = 'graph';
  if (nodes.length === 0) {
    root.innerHTML = '<div class="empty">No graph data.</div>';
    return root;
  }

  const W = 320;
  const H = 240;
  const cx = W / 2;
  const cy = H / 2;
  const r = Math.min(W, H) / 2 - 40;
  const svg = svgRoot(W, H);
  ensureGlassDefs(svg);

  if (directed) {
    const defs = svgNode('defs');
    const marker = svgNode('marker', {
      id: 'fb-arrow', viewBox: '0 0 10 10', refX: 9, refY: 5,
      markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse',
    });
    marker.appendChild(svgNode('path', { d: 'M0,0 L10,5 L0,10 z', class: 'fb-arrow-head' }));
    defs.appendChild(marker);
    svg.appendChild(defs);
  }

  // Circular layout.
  const pos = new Map<string, { x: number; y: number }>();
  nodes.forEach((n, i) => {
    const a = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
    const id = n.id ?? String(i);
    pos.set(id, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
  });

  const edgeEls: SVGElement[] = [];
  edges.forEach((e) => {
    const a = pos.get(e.from ?? '');
    const b = pos.get(e.to ?? '');
    if (!a || !b) return;
    const line = svgNode('line', {
      x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: 'graph-edge',
    });
    if (directed) line.setAttribute('marker-end', 'url(#fb-arrow)');
    svg.appendChild(line);
    edgeEls.push(line);
  });

  const nodeEls: SVGElement[] = [];
  nodes.forEach((n, i) => {
    const id = n.id ?? String(i);
    const p = pos.get(id)!;
    const g = svgNode('g', { class: 'graph-node' });
    // Glassy bead: accent-tinted glass body + glow + a small specular highlight.
    g.appendChild(svgNode('circle', {
      cx: p.x, cy: p.y, r: 16, fill: 'url(#fbAccentFill)', filter: 'url(#fbGlow)',
      class: 'fb-glass-bead',
    }));
    g.appendChild(svgNode('circle', {
      cx: p.x - 5, cy: p.y - 6, r: 4.5, class: 'fb-glass-spec',
    }));
    g.appendChild(svgNode('text', { x: p.x, y: p.y + 28, 'text-anchor': 'middle' },
      n.label ?? id));
    svg.appendChild(g);
    nodeEls.push(g);
  });

  root.appendChild(svg);
  // Reveal nodes first, then the edges between them.
  revealSequence([...nodeEls, ...edgeEls], { stepMs: 200 });
  return root;
}
