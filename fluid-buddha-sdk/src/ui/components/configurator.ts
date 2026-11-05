// Configurator — a generalised interactive widget the visitor plays with:
// sliders / toggles / selects drive live computed outputs. Output values are
// safe declarative formulas over the control keys (evaluated by interactive.ts,
// never eval'd). Generalises the ROI calculator.

import { evalExpr, formatValue, RenderContext } from './interactive';

interface CfgControl {
  key?: string;
  label?: string;
  type?: 'slider' | 'toggle' | 'select';
  min?: number;
  max?: number;
  step?: number;
  value?: number;
  unit?: string;
  options?: Array<{ label?: string; value?: number }>;
}
interface CfgOutput { label?: string; expr?: string; unit?: string; format?: string }

const num = (v: unknown, d: number) => (typeof v === 'number' && isFinite(v) ? v : d);

export function buildConfigurator(state: Record<string, unknown>, ctx?: RenderContext): HTMLElement {
  const controls = (state.controls as CfgControl[] | undefined) ?? [];
  const outputs = (state.outputs as CfgOutput[] | undefined) ?? [];
  const root = document.createElement('div');
  root.className = 'cfg';
  if (!controls.length) {
    root.innerHTML = '<div class="empty">No configurator controls.</div>';
    return root;
  }

  const vals: Record<string, number> = {};
  controls.forEach((c, i) => {
    vals[c.key ?? `c${i}`] = num(c.value, c.type === 'toggle' ? 0 : num(c.min, 0));
  });

  const outRow = document.createElement('div');
  outRow.className = 'cfg-out';
  const outEls = outputs.map((o) => {
    const cell = document.createElement('div');
    const v = document.createElement('span');
    v.className = 'cfg-out-val';
    const l = document.createElement('span');
    l.className = 'cfg-out-label';
    l.textContent = o.label ?? '';
    cell.append(v, l);
    outRow.appendChild(cell);
    return { o, v };
  });

  const recompute = () => {
    for (const { o, v } of outEls) {
      v.textContent = formatValue(evalExpr(o.expr ?? '0', vals), o.format, o.unit, state.currency as string | undefined);
    }
  };

  controls.forEach((c, i) => {
    const key = c.key ?? `c${i}`;
    const row = document.createElement('div');
    row.className = 'cfg-row';
    const label = document.createElement('label');
    label.textContent = c.label ?? key;
    row.appendChild(label);

    const commit = () => ctx?.reportState?.({ values: { ...vals } });

    if (c.type === 'toggle') {
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.className = 'cfg-toggle';
      input.checked = num(c.value, 0) >= 1;
      input.addEventListener('change', () => {
        vals[key] = input.checked ? 1 : 0;
        recompute();
        commit();
      });
      row.appendChild(input);
    } else if (c.type === 'select') {
      const sel = document.createElement('select');
      sel.className = 'cfg-select';
      (c.options ?? []).forEach((opt, j) => {
        const o = document.createElement('option');
        o.value = String(num(opt.value, j));
        o.textContent = opt.label ?? String(opt.value ?? j);
        sel.appendChild(o);
      });
      sel.value = String(num(c.value, num(c.options?.[0]?.value, 0)));
      vals[key] = Number(sel.value);
      sel.addEventListener('change', () => {
        vals[key] = Number(sel.value);
        recompute();
        commit();
      });
      row.appendChild(sel);
    } else {
      const input = document.createElement('input');
      input.type = 'range';
      input.min = String(num(c.min, 0));
      input.max = String(num(c.max, 100));
      input.step = String(num(c.step, 1));
      input.value = String(vals[key]);
      const val = document.createElement('span');
      val.className = 'cfg-val';
      const fmt = () => `${Number(input.value).toLocaleString()}${c.unit ? ' ' + c.unit : ''}`;
      val.textContent = fmt();
      input.addEventListener('input', () => {
        vals[key] = Number(input.value);
        val.textContent = fmt();
        recompute();
      });
      input.addEventListener('change', commit);
      row.append(input, val);
    }
    root.appendChild(row);
  });

  if (outputs.length) root.appendChild(outRow);
  recompute();
  return root;
}
