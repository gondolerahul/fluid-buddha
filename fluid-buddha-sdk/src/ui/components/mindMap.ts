// Mind map — a radial topic tree. Branches fan out from a central topic; any
// branch with children is clickable to expand/collapse. Pannable + zoomable.
// Complex + interactive (Features 3 & 4).

import { enablePanZoom, RenderContext } from './interactive';
import { ensureGlassDefs, svgNode, svgRoot } from './svg';

interface MindNode {
  label?: string;
  children?: MindNode[];
}

function chip(x: number, y: number, text: string, cls: string): SVGGElement {
  const label = text || '';
  const w = Math.min(132, Math.max(44, label.length * 6.4 + 18));
  const h = 26;
  const g = svgNode('g', { class: cls });
  g.appendChild(svgNode('rect', {
    x: x - w / 2, y: y - h / 2, width: w, height: h, rx: 13,
    fill: 'url(#fbAccentFill)', filter: 'url(#fbGlow)', class: 'fb-glass-rect',
  }));
  g.appendChild(svgNode('text', { x, y: y + 4, 'text-anchor': 'middle' },
    label.length > 18 ? label.slice(0, 17) + '…' : label));
  return g;
}

export function buildMindMap(state: Record<string, unknown>, ctx?: RenderContext): HTMLElement {
  const topic = String(state.topic ?? state.label ?? 'Topic');
  const branches = (state.branches as MindNode[] | undefined) ?? [];
  const root = document.createElement('div');
  root.className = 'mindmap';
  if (!branches.length) {
    root.innerHTML = '<div class="empty">No mind-map data.</div>';
    return root;
  }

  const W = 360;
  const H = 300;
  const cx = W / 2;
  const cy = H / 2;
  const svg = svgRoot(W, H);
  ensureGlassDefs(svg);
  const layer = svgNode('g');
  svg.appendChild(layer);

  const expanded = new Set<number>();

  const draw = () => {
    layer.replaceChildren();
    const R = 98;
    branches.forEach((b, i) => {
      const a = (i / branches.length) * Math.PI * 2 - Math.PI / 2;
      const bx = cx + R * Math.cos(a);
      const by = cy + R * Math.sin(a);
      layer.appendChild(svgNode('line', { x1: cx, y1: cy, x2: bx, y2: by, class: 'mm-edge' }));

      if (expanded.has(i) && b.children?.length) {
        const cR = 66;
        b.children.forEach((c, j) => {
          const ca = a + (j - (b.children!.length - 1) / 2) * 0.42;
          const ccx = bx + cR * Math.cos(ca);
          const ccy = by + cR * Math.sin(ca);
          layer.appendChild(svgNode('line',
            { x1: bx, y1: by, x2: ccx, y2: ccy, class: 'mm-edge mm-edge-sub' }));
          layer.appendChild(chip(ccx, ccy, c.label ?? '', 'mm-node mm-node-sub'));
        });
      }

      const g = chip(bx, by, b.label ?? '', 'mm-node');
      if (b.children?.length) {
        g.style.cursor = 'pointer';
        g.appendChild(svgNode('circle', { cx: bx + 36, cy: by - 13, r: 8, class: 'mm-badge' }));
        g.appendChild(svgNode('text',
          { x: bx + 36, y: by - 9.5, 'text-anchor': 'middle', class: 'mm-badge-t' },
          expanded.has(i) ? '–' : '+'));
        g.addEventListener('click', () => {
          expanded.has(i) ? expanded.delete(i) : expanded.add(i);
          ctx?.reportState?.({ expanded: [...expanded] });
          draw();
        });
      }
      layer.appendChild(g);
    });
    layer.appendChild(chip(cx, cy, topic, 'mm-node mm-root'));
  };

  draw();
  root.appendChild(svg);
  enablePanZoom(svg, W, H);
  return root;
}
