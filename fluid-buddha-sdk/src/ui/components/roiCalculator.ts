// Interactive ROI calculator. Seeded from state (barge-in patches are merged by
// the canvas, which rebuilds the card — Req 3.5.3/3.5.4).

import { money } from './interactive';

export function buildRoiCalculator(state: Record<string, unknown>): HTMLElement {
  const cur = typeof state.currency === 'string' ? state.currency : undefined;
  const num = (v: unknown, d: number) => (typeof v === 'number' ? v : d);
  let seats = num(state.seats, 10);
  let monthlyCost = num(state.monthly_cost, 10000);
  let hoursSaved = num(state.hours_saved, 320);
  // What an hour of the team's time is worth, in the component's currency.
  const hourly = num(state.hourly_value, cur === 'INR' ? 500 : 45);

  const root = document.createElement('div');
  root.className = 'roi';

  const netEl = document.createElement('span');
  const roiEl = document.createElement('span');

  const recompute = () => {
    const laborValue = Math.round(hoursSaved * hourly);
    const net = laborValue - monthlyCost;
    const roi = monthlyCost > 0 ? Math.round((net / monthlyCost) * 100) : 0;
    netEl.textContent = money(net, cur);
    netEl.className = net >= 0 ? 'roi-pos' : 'roi-neg';
    roiEl.textContent = `${roi}%`;
    roiEl.className = roi >= 0 ? 'roi-pos' : 'roi-neg';
  };

  const row = (
    label: string, min: number, max: number, step: number, value: number,
    fmt: (v: number) => string, set: (v: number) => void,
  ) => {
    const wrap = document.createElement('div');
    wrap.className = 'roi-row';
    const l = document.createElement('label');
    l.textContent = label;
    const input = document.createElement('input');
    input.type = 'range';
    input.min = String(min); input.max = String(max); input.step = String(step);
    input.value = String(value);
    const val = document.createElement('span');
    val.className = 'val';
    val.textContent = fmt(value);
    input.addEventListener('input', () => {
      const v = Number(input.value);
      set(v);
      val.textContent = fmt(v);
      recompute();
    });
    wrap.append(l, input, val);
    return wrap;
  };

  root.appendChild(row('Seats', 1, 200, 1, seats, (v) => String(v), (v) => (seats = v)));
  root.appendChild(row('Monthly cost', 0, 100000, 500, monthlyCost,
    (v) => money(v, cur), (v) => (monthlyCost = v)));
  root.appendChild(row('Hours saved/mo', 0, 2000, 10, hoursSaved,
    (v) => String(v), (v) => (hoursSaved = v)));

  const result = document.createElement('div');
  result.className = 'roi-result';
  const mk = (label: string, valueEl: HTMLElement) => {
    const d = document.createElement('div');
    const l = document.createElement('span');
    l.className = 'roi-label';
    l.textContent = label;
    d.append(l, valueEl);
    return d;
  };
  result.append(mk('Net value/mo', netEl), mk('ROI', roiEl));
  root.appendChild(result);

  recompute();
  return root;
}
