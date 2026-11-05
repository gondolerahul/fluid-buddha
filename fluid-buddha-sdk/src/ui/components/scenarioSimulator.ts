// Scenario simulator — drag the sliders and watch the series recompute live as
// proportional bars. Series values are safe formulas over the slider keys
// (evaluated by interactive.ts). Lets the visitor explore "what if" directly.

import { evalExpr, formatValue, RenderContext } from './interactive';

interface SimSlider {
  key?: string; label?: string; min?: number; max?: number; step?: number; value?: number; unit?: string;
}
interface SimSeries { label?: string; expr?: string; format?: string; unit?: string }

const num = (v: unknown, d: number) => (typeof v === 'number' && isFinite(v) ? v : d);

export function buildScenarioSimulator(state: Record<string, unknown>, ctx?: RenderContext): HTMLElement {
  const sliders = (state.sliders as SimSlider[] | undefined) ?? [];
  const series = (state.series as SimSeries[] | undefined) ?? [];
  const root = document.createElement('div');
  root.className = 'sim';
  if (!sliders.length || !series.length) {
    root.innerHTML = '<div class="empty">No simulator data.</div>';
    return root;
  }

  const vals: Record<string, number> = {};
  sliders.forEach((s, i) => (vals[s.key ?? `s${i}`] = num(s.value, num(s.min, 0))));

  // Bars (one per series).
  const chart = document.createElement('div');
  chart.className = 'sim-chart';
  const bars = series.map((s) => {
    const row = document.createElement('div');
    row.className = 'sim-bar-row';
    const name = document.createElement('span');
    name.className = 'sim-bar-name';
    name.textContent = s.label ?? '';
    const track = document.createElement('div');
    track.className = 'sim-bar-track';
    const fill = document.createElement('div');
    fill.className = 'sim-bar-fill';
    track.appendChild(fill);
    const val = document.createElement('span');
    val.className = 'sim-bar-val';
    row.append(name, track, val);
    chart.appendChild(row);
    return { s, fill, val };
  });

  const recompute = () => {
    const computed = bars.map((b) => evalExpr(b.s.expr ?? '0', vals));
    const max = Math.max(1, ...computed.map((v) => Math.abs(v)));
    bars.forEach((b, i) => {
      b.fill.style.width = `${Math.max(0, Math.min(100, (computed[i] / max) * 100))}%`;
      b.val.textContent = formatValue(computed[i], b.s.format, b.s.unit, state.currency as string | undefined);
    });
  };

  root.appendChild(chart);

  sliders.forEach((s, i) => {
    const key = s.key ?? `s${i}`;
    const row = document.createElement('div');
    row.className = 'sim-row';
    const label = document.createElement('label');
    label.textContent = s.label ?? key;
    const input = document.createElement('input');
    input.type = 'range';
    input.min = String(num(s.min, 0));
    input.max = String(num(s.max, 100));
    input.step = String(num(s.step, 1));
    input.value = String(vals[key]);
    const val = document.createElement('span');
    val.className = 'sim-slider-val';
    const fmt = () => `${Number(input.value).toLocaleString()}${s.unit ? ' ' + s.unit : ''}`;
    val.textContent = fmt();
    input.addEventListener('input', () => {
      vals[key] = Number(input.value);
      val.textContent = fmt();
      recompute();
    });
    input.addEventListener('change', () => ctx?.reportState?.({ values: { ...vals } }));
    row.append(label, input, val);
    root.appendChild(row);
  });

  recompute();
  return root;
}
