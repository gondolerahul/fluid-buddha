// Charts — bar / line / pie, drawn in raw SVG (no chart lib). Series are
// revealed one datum at a time (Req 3.5.2). Themed via --fb-accent.

import { revealSequence } from './reveal';
import { ensureGlassDefs, svgNode, svgRoot } from './svg';

interface Datum { label?: string; value?: number }

export interface ChartState {
  chart_type?: 'bar' | 'line' | 'pie';
  title?: string;
  unit?: string;
  data?: Datum[];
}

const num = (v: unknown): number => (typeof v === 'number' && isFinite(v) ? v : 0);

export function buildChart(state: Record<string, unknown>): HTMLElement {
  const type = (state.chart_type as string) || 'bar';
  const data = ((state.data as Datum[] | undefined) ?? []).map((d) => ({
    label: d.label ?? '',
    value: num(d.value),
  }));
  const unit = (state.unit as string) || '';

  const root = document.createElement('div');
  root.className = 'chart';
  if (data.length === 0) {
    root.innerHTML = '<div class="empty">No chart data.</div>';
    return root;
  }
  if (state.title) {
    const t = document.createElement('div');
    t.className = 'chart-title';
    t.textContent = String(state.title);
    root.appendChild(t);
  }

  if (type === 'pie') root.appendChild(pie(data, unit));
  else if (type === 'line') root.appendChild(line(data, unit));
  else root.appendChild(bar(data, unit));
  return root;
}

function fmt(v: number, unit: string): string {
  return unit ? `${v.toLocaleString()}${unit}` : v.toLocaleString();
}

function bar(data: Datum[], unit: string): SVGSVGElement {
  const W = 320, H = 200, padL = 8, padB = 28, padT = 8;
  const max = Math.max(1, ...data.map((d) => num(d.value)));
  const bw = (W - padL * 2) / data.length;
  const svg = svgRoot(W, H);
  ensureGlassDefs(svg);
  const bars: SVGElement[] = [];
  data.forEach((d, i) => {
    const h = (num(d.value) / max) * (H - padB - padT);
    const x = padL + i * bw + bw * 0.15;
    const w = bw * 0.7;
    const y = H - padB - h;
    const g = svgNode('g', { class: 'chart-bar' });
    // Glass column: accent-tinted body + glow, with a bright top cap as the rim.
    g.appendChild(svgNode('rect', {
      x, y, width: w, height: h, rx: 5,
      fill: 'url(#fbAccentFill)', filter: 'url(#fbGlow)',
    }));
    g.appendChild(svgNode('rect', {
      x, y, width: w, height: Math.min(h, 6), rx: 5, class: 'fb-glass-sheen',
    }));
    g.appendChild(svgNode('text',
      { x: x + w / 2, y: y - 4, 'text-anchor': 'middle', class: 'chart-val' },
      fmt(num(d.value), unit)));
    g.appendChild(svgNode('text',
      { x: x + w / 2, y: H - padB + 14, 'text-anchor': 'middle', class: 'chart-axis' },
      d.label ?? ''));
    svg.appendChild(g);
    bars.push(g);
  });
  revealSequence(bars, { stepMs: 200 });
  return svg;
}

function line(data: Datum[], unit: string): SVGSVGElement {
  const W = 320, H = 200, padL = 8, padB = 28, padT = 10, padR = 8;
  const max = Math.max(1, ...data.map((d) => num(d.value)));
  const span = data.length > 1 ? data.length - 1 : 1;
  const px = (i: number) => padL + (i / span) * (W - padL - padR);
  const py = (v: number) => H - padB - (v / max) * (H - padB - padT);
  const svg = svgRoot(W, H);
  ensureGlassDefs(svg);

  // Translucent glass area under the curve grounds the line in a lit volume.
  const baseY = H - padB;
  const areaPts = `${px(0)},${baseY} ` +
    data.map((d, i) => `${px(i)},${py(num(d.value))}`).join(' ') +
    ` ${px(data.length - 1)},${baseY}`;
  svg.appendChild(svgNode('polygon', { points: areaPts, fill: 'url(#fbAccentFill)', class: 'chart-area' }));

  const pts = data.map((d, i) => `${px(i)},${py(num(d.value))}`).join(' ');
  const poly = svgNode('polyline', { points: pts, class: 'chart-line', filter: 'url(#fbGlow)' });
  svg.appendChild(poly);

  const dots: SVGElement[] = [];
  data.forEach((d, i) => {
    const g = svgNode('g', { class: 'chart-dot' });
    g.appendChild(svgNode('circle', { cx: px(i), cy: py(num(d.value)), r: 3.5 }));
    g.appendChild(svgNode('text',
      { x: px(i), y: H - padB + 14, 'text-anchor': 'middle', class: 'chart-axis' },
      d.label ?? ''));
    svg.appendChild(g);
    dots.push(g);
  });
  revealSequence([poly, ...dots], { stepMs: 160 });
  void unit;
  return svg;
}

function pie(data: Datum[], unit: string): SVGSVGElement {
  const W = 320, H = 210, cx = 96, cy = 100, r = 80;
  const total = data.reduce((s, d) => s + Math.max(0, num(d.value)), 0) || 1;
  const svg = svgRoot(W, H);
  ensureGlassDefs(svg);
  let a0 = -Math.PI / 2;
  const slices: SVGElement[] = [];
  data.forEach((d, i) => {
    const frac = Math.max(0, num(d.value)) / total;
    const a1 = a0 + frac * Math.PI * 2;
    const large = a1 - a0 > Math.PI ? 1 : 0;
    const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const path = svgNode('path', {
      d: `M${cx},${cy} L${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1} Z`,
      class: 'chart-slice',
      style: `--i:${i}`,
      filter: 'url(#fbGlow)',
    });
    svg.appendChild(path);
    slices.push(path);

    // Legend.
    const ly = 24 + i * 20;
    const sw = svgNode('rect',
      { x: 200, y: ly - 9, width: 11, height: 11, rx: 2, class: 'chart-slice', style: `--i:${i}` });
    const lt = svgNode('text',
      { x: 217, y: ly, class: 'chart-axis' },
      `${d.label ?? ''} ${fmt(num(d.value), unit)}`);
    svg.appendChild(sw);
    svg.appendChild(lt);
    slices.push(sw, lt);
    a0 = a1;
  });
  revealSequence(slices, { stepMs: 160 });
  return svg;
}
