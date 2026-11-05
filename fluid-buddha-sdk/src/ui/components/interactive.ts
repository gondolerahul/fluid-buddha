// Shared interaction layer for the richer diagram / component renderers.
//
// The LLM still only ever emits typed JSON — all interaction logic (pan/zoom,
// tooltips, live recompute) lives here in the SDK, so nothing executable ever
// crosses the wire. `evalExpr` is a hand-rolled arithmetic evaluator (no eval /
// Function) so an LLM-authored formula like "hours * 45 - monthly_cost" is data,
// not code.

export interface RenderContext {
  syncId?: string;
  /** Report the component's current interactive state back to the host (which
   *  forwards it to the agent so it can narrate or patch). */
  reportState?: (patch: Record<string, unknown>) => void;
}

// ---- pan / zoom -------------------------------------------------------------

/** Wheel-zoom (toward the cursor) + drag-pan an <svg> by mutating its viewBox. */
export function enablePanZoom(svg: SVGSVGElement, w: number, h: number): void {
  const vb = { x: 0, y: 0, w, h };
  const minW = w * 0.4;
  const maxW = w * 1.8;
  const apply = () => svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`);
  svg.style.cursor = 'grab';
  (svg.style as unknown as { touchAction: string }).touchAction = 'none';

  svg.addEventListener(
    'wheel',
    (e: WheelEvent) => {
      e.preventDefault();
      const k = e.deltaY > 0 ? 1.1 : 0.9;
      const nw = Math.min(maxW, Math.max(minW, vb.w * k));
      const nh = nw * (h / w);
      const rect = svg.getBoundingClientRect();
      const fx = rect.width ? (e.clientX - rect.left) / rect.width : 0.5;
      const fy = rect.height ? (e.clientY - rect.top) / rect.height : 0.5;
      vb.x += (vb.w - nw) * fx;
      vb.y += (vb.h - nh) * fy;
      vb.w = nw;
      vb.h = nh;
      apply();
    },
    { passive: false },
  );

  let drag: { x: number; y: number } | null = null;
  svg.addEventListener('pointerdown', (e: PointerEvent) => {
    drag = { x: e.clientX, y: e.clientY };
    svg.style.cursor = 'grabbing';
    try {
      svg.setPointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  });
  svg.addEventListener('pointermove', (e: PointerEvent) => {
    if (!drag) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width) vb.x -= ((e.clientX - drag.x) / rect.width) * vb.w;
    if (rect.height) vb.y -= ((e.clientY - drag.y) / rect.height) * vb.h;
    drag = { x: e.clientX, y: e.clientY };
    apply();
  });
  const end = () => {
    drag = null;
    svg.style.cursor = 'grab';
  };
  svg.addEventListener('pointerup', end);
  svg.addEventListener('pointerleave', end);
}

// ---- tooltip ----------------------------------------------------------------

/** A single lazily-created tooltip pinned to a (relatively-positioned) root. */
export class Tooltip {
  private el: HTMLDivElement;

  constructor(private root: HTMLElement) {
    if (!root.style.position) root.style.position = 'relative';
    this.el = document.createElement('div');
    this.el.className = 'fb-tip';
    this.el.style.display = 'none';
    root.appendChild(this.el);
  }

  bind(target: Element, text: string): void {
    if (!text) return;
    const show = (e: Event) => {
      const pe = e as PointerEvent;
      this.el.textContent = text;
      this.el.style.display = 'block';
      const r = this.root.getBoundingClientRect();
      const x = Math.min(pe.clientX - r.left + 12, r.width - 8);
      this.el.style.left = `${Math.max(4, x)}px`;
      this.el.style.top = `${Math.max(4, pe.clientY - r.top + 12)}px`;
    };
    target.addEventListener('pointerenter', show);
    target.addEventListener('pointermove', show);
    target.addEventListener('pointerleave', () => {
      this.el.style.display = 'none';
    });
  }
}

// ---- safe arithmetic evaluator ---------------------------------------------

type Tok = { t: 'num' | 'op' | 'lp' | 'rp' | 'var'; v: string };

function tokenize(expr: string): Tok[] {
  const out: Tok[] = [];
  const re = /\s*([0-9]*\.?[0-9]+|[A-Za-z_][A-Za-z0-9_]*|[()+\-*/])/g;
  let m: RegExpExecArray | null;
  let prev: Tok | undefined;
  while ((m = re.exec(expr))) {
    const s = m[1];
    let tok: Tok;
    if (/^[0-9.]/.test(s)) tok = { t: 'num', v: s };
    else if (s === '(') tok = { t: 'lp', v: s };
    else if (s === ')') tok = { t: 'rp', v: s };
    else if (s === '+' || s === '-' || s === '*' || s === '/') {
      // Unary minus / plus: at the start or after an operator / '(' → inject a 0.
      if ((s === '-' || s === '+') && (!prev || prev.t === 'op' || prev.t === 'lp')) {
        out.push({ t: 'num', v: '0' });
      }
      tok = { t: 'op', v: s };
    } else tok = { t: 'var', v: s };
    out.push(tok);
    prev = tok;
  }
  return out;
}

const PREC: Record<string, number> = { '+': 1, '-': 1, '*': 2, '/': 2 };

function toRPN(toks: Tok[]): Tok[] {
  const out: Tok[] = [];
  const ops: Tok[] = [];
  for (const t of toks) {
    if (t.t === 'num' || t.t === 'var') out.push(t);
    else if (t.t === 'op') {
      while (ops.length && ops[ops.length - 1].t === 'op' &&
             PREC[ops[ops.length - 1].v] >= PREC[t.v]) {
        out.push(ops.pop()!);
      }
      ops.push(t);
    } else if (t.t === 'lp') ops.push(t);
    else if (t.t === 'rp') {
      while (ops.length && ops[ops.length - 1].t !== 'lp') out.push(ops.pop()!);
      ops.pop(); // discard '('
    }
  }
  while (ops.length) out.push(ops.pop()!);
  return out;
}

/** Evaluate a simple arithmetic expression over `vars` (unknown names → 0).
 *  Supports + - * / and parentheses only; never executes code. */
export function evalExpr(expr: string, vars: Record<string, number>): number {
  try {
    const rpn = toRPN(tokenize(String(expr || '')));
    const st: number[] = [];
    for (const t of rpn) {
      if (t.t === 'num') st.push(parseFloat(t.v));
      else if (t.t === 'var') st.push(Number(vars[t.v] ?? 0));
      else {
        const b = st.pop() ?? 0;
        const a = st.pop() ?? 0;
        st.push(t.v === '+' ? a + b : t.v === '-' ? a - b : t.v === '*' ? a * b : b ? a / b : 0);
      }
    }
    const r = st.pop() ?? 0;
    return Number.isFinite(r) ? r : 0;
  } catch {
    return 0;
  }
}

/** A whole amount of money in `currency` (ISO 4217; the server sets the
 *  site's, M2-8 follow-up). Rupees use Indian grouping: ₹1,49,999. */
export function money(v: number, currency?: string): string {
  const n = Math.round(v);
  const code = (currency || 'USD').toUpperCase();
  if (code === 'INR') return `${n < 0 ? '−' : ''}₹${Math.abs(n).toLocaleString('en-IN')}`;
  try {
    return new Intl.NumberFormat('en', { style: 'currency', currency: code, maximumFractionDigits: 0 }).format(n);
  } catch {
    return `${code} ${n.toLocaleString()}`;
  }
}

/** Format a number for display per a coarse format hint. A currency output
 *  may name its own `unit` (a currency code); else the component's currency. */
export function formatValue(v: number, format?: string, unit?: string, currency?: string): string {
  if (format === 'currency') return money(v, unit && /^[A-Za-z]{3}$/.test(unit) ? unit : currency);
  const s = format === 'percent' ? `${Math.round(v)}%` : Math.round(v).toLocaleString();
  return unit && format !== 'percent' ? `${s} ${unit}` : s;
}
