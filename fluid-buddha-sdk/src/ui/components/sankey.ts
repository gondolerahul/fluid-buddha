// Sankey flow diagram — weighted bands between nodes, widths proportional to
// flow value. Node columns are taken from `column` when given, else inferred
// (sources on the left, each node one step right of its deepest predecessor).
// Hovering a band shows its value. Good for "where does the time/cost/traffic go".

import { Tooltip } from './interactive';
import { ensureGlassDefs, svgNode, svgRoot } from './svg';

interface SkNode { id?: string; label?: string; column?: number }
interface SkLink { source?: string; target?: string; value?: number }

export function buildSankey(state: Record<string, unknown>): HTMLElement {
  const nodesIn = (state.nodes as SkNode[] | undefined) ?? [];
  const links = ((state.links as SkLink[] | undefined) ?? [])
    .filter((l) => l.source && l.target && (l.value ?? 0) > 0);
  const root = document.createElement('div');
  root.className = 'sankey';
  if (!links.length) {
    root.innerHTML = '<div class="empty">No flow data.</div>';
    return root;
  }

  // Node registry (explicit + endpoints).
  const labels = new Map<string, string>();
  const explicitCol = new Map<string, number>();
  const reg = (id?: string, label?: string, col?: number) => {
    if (!id) return;
    if (!labels.has(id)) labels.set(id, label ?? id);
    else if (label) labels.set(id, label);
    if (typeof col === 'number') explicitCol.set(id, col);
  };
  nodesIn.forEach((n) => reg(n.id, n.label, n.column));
  links.forEach((l) => { reg(l.source); reg(l.target); });

  const preds = new Map<string, string[]>();
  links.forEach((l) => {
    const arr = preds.get(l.target!) ?? [];
    arr.push(l.source!);
    preds.set(l.target!, arr);
  });
  const colMemo = new Map<string, number>();
  const colOf = (id: string, seen: Set<string> = new Set()): number => {
    if (explicitCol.has(id)) return explicitCol.get(id)!;
    if (colMemo.has(id)) return colMemo.get(id)!;
    if (seen.has(id)) return 0; // cycle guard
    seen.add(id);
    const ps = preds.get(id) ?? [];
    const c = ps.length ? 1 + Math.max(...ps.map((p) => colOf(p, seen))) : 0;
    colMemo.set(id, c);
    return c;
  };

  const ids = [...labels.keys()];
  const colByNode = new Map(ids.map((id) => [id, colOf(id)]));
  const maxCol = Math.max(0, ...colByNode.values());

  // Flow per node = max(inflow, outflow); column total drives vertical scale.
  const inflow = new Map<string, number>();
  const outflow = new Map<string, number>();
  links.forEach((l) => {
    outflow.set(l.source!, (outflow.get(l.source!) ?? 0) + (l.value ?? 0));
    inflow.set(l.target!, (inflow.get(l.target!) ?? 0) + (l.value ?? 0));
  });
  const flow = (id: string) => Math.max(inflow.get(id) ?? 0, outflow.get(id) ?? 0, 1);

  const W = 340;
  const H = 240;
  const gap = 10;
  const colNodes: string[][] = Array.from({ length: maxCol + 1 }, () => []);
  ids.forEach((id) => colNodes[colByNode.get(id)!].push(id));
  const colTotal = colNodes.map((c) => c.reduce((s, id) => s + flow(id), 0) + gap * Math.max(0, c.length - 1));
  const scale = (H - 20) / Math.max(1, ...colTotal);

  // Lay out node rectangles.
  const box = new Map<string, { x: number; y: number; w: number; h: number }>();
  const nodeW = 12;
  const colX = (c: number) => (maxCol === 0 ? W / 2 : 12 + (c / maxCol) * (W - 24 - nodeW));
  colNodes.forEach((c, ci) => {
    let y = (H - (colTotal[ci] * scale)) / 2 + 4;
    c.forEach((id) => {
      const h = Math.max(6, flow(id) * scale);
      box.set(id, { x: colX(ci), y, w: nodeW, h });
      y += h + gap;
    });
  });

  const svg = svgRoot(W, H);
  ensureGlassDefs(svg);
  const tip = new Tooltip(root);

  // Bands (draw first, under the node rects). Stack at each node by order.
  const outCursor = new Map<string, number>();
  const inCursor = new Map<string, number>();
  links.forEach((l) => {
    const a = box.get(l.source!);
    const b = box.get(l.target!);
    if (!a || !b) return;
    const t = (l.value ?? 0) * scale;
    const sy = a.y + (outCursor.get(l.source!) ?? 0);
    const ty = b.y + (inCursor.get(l.target!) ?? 0);
    outCursor.set(l.source!, (outCursor.get(l.source!) ?? 0) + t);
    inCursor.set(l.target!, (inCursor.get(l.target!) ?? 0) + t);
    const x1 = a.x + a.w;
    const x2 = b.x;
    const mx = (x1 + x2) / 2;
    const path = svgNode('path', {
      d: `M${x1},${sy} C${mx},${sy} ${mx},${ty} ${x2},${ty} `
        + `L${x2},${ty + t} C${mx},${ty + t} ${mx},${sy + t} ${x1},${sy + t} Z`,
      class: 'sk-link',
    });
    tip.bind(path, `${labels.get(l.source!)} → ${labels.get(l.target!)}: ${l.value}`);
    svg.appendChild(path);
  });

  // Node rects + labels on top.
  ids.forEach((id) => {
    const r = box.get(id)!;
    svg.appendChild(svgNode('rect', {
      x: r.x, y: r.y, width: r.w, height: r.h, rx: 3,
      fill: 'url(#fbAccentFill)', filter: 'url(#fbGlow)', class: 'fb-glass-rect',
    }));
    const atEnd = colByNode.get(id) === maxCol;
    svg.appendChild(svgNode('text', {
      x: atEnd ? r.x - 5 : r.x + r.w + 5, y: r.y + r.h / 2 + 3,
      'text-anchor': atEnd ? 'end' : 'start', class: 'sk-label',
    }, (labels.get(id) ?? '').slice(0, 16)));
  });

  root.appendChild(svg);
  return root;
}
