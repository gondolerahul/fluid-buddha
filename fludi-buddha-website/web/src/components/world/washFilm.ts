/**
 * The default world's film, "The painted page": a website painted in watercolour on one sheet of
 * paper, drawn live from the scroll position. `renderWashFilm(ctx, w, h, p, opt)` draws the frame
 * for progress p (0 to 1). Nothing is pre-rendered: it is sharp at any size and weighs a few kB.
 *
 * The look follows the "Watercolor Brush" style of lemo-opuscar (styles/watercolor/STYLE.md):
 *  - one sheet of fibrous paper under everything; the paper is the white and nothing paints over it;
 *  - every shape is built from single translucent brush strokes: a ribbon of uneven width with a
 *    thin body, a few bristle tracks and a dry tail ("flying white"); overlaps darken like pigment;
 *  - the result at the end is painted in negative: a deep ink wash with the gold laid on it;
 *  - things paint themselves in, structure first: pencil, then wash, then detail, then the note;
 *  - a quiet annotation layer of handwritten notes;
 *  - the camera glides along the sheet; a finished passage lifts back to blank paper.
 * It keeps to the design system's three colours: paper, a warm ink diluted from its near-black, and
 * the gold of the logo. The sheet hangs on the ink page; its notes are set in the system's mono.
 *
 * How it works: every object (a panel, a line of content, a ring) is a list of strokes with a
 * moment on the timeline. An object is painted into its own small canvas (re-painted only while it
 * is changing), given the paper's grain, and laid on the sheet with multiply. Gold is laid opaque,
 * like gouache. Everything is a pure function of p, so the film scrubs backwards exactly.
 */

export type WashOpt = {
  /** Canvas pixels per CSS pixel. */
  dpr: number;
  /** Height in canvas pixels covered by the site header. */
  top: number;
  /** The paper tile (film/paper.mjs): 1024 px, shown at 512 CSS px. */
  paper: CanvasImageSource | null;
  /** Font family of the notes (the design system's mono). */
  hand: string;
  /** The opening: 0 to 1 as the page paints itself in when the visitor arrives. */
  intro: number;
  /** "stage": beside the copy (or above it on upright screens). "fill": the whole canvas, for a still. */
  layout?: "stage" | "fill";
  /** A still may look at any part of the sheet: [x, y, zoom]. */
  cam?: [number, number, number];
  /** Paint on the page's own paper (leave the canvas clear) instead of drawing a sheet. */
  clear?: boolean;
};

type Pt = [number, number];
type Win = [number, number];

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const ease = (t: number) => t * t * (3 - 2 * t);
/** 0 before a, 1 after b, eased in between. */
const ramp = (p: number, a: number, b: number) => ease(clamp((p - a) / (b - a)));

function rng(seed: number) {
  let s = seed | 0;
  return () => { s = (s + 0x6d2b79f5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const h1 = (i: number, seed: number) => { const s = Math.sin(i * 127.1 + seed * 311.7) * 43758.5453; return (s - Math.floor(s)) * 2 - 1; };
/** Smooth 1D noise in -1..1. */
const vnoise = (x: number, seed: number) => { const i = Math.floor(x), f = x - i; return lerp(h1(i, seed), h1(i + 1, seed), ease(f)); };

// ------------------------------------------------------------------ the three colours
// the design system's paper, a warm ink diluted from its near-black, and the gold of the logo
const PAPER = "#f6f2ea";
const INK_MID = "56,48,41", INK_DEEP = "26,21,17", INK_TINT = "112,100,88";
const GOLD = "237,171,72", GOLD_HI = "253,200,113", GOLD_LO = "168,114,42";
const PENCIL = "74,68,62", NOTE_INK = "26,22,17";
/** Paper-coloured paint, for lines and notes laid over the deep wash. */
const LIGHT = "246,241,233";

// ------------------------------------------------------------------ strokes
type Profile = "wash" | "brush" | "even" | "tip";
const PROFILE: Record<Profile, (u: number) => number> = {
  // a loaded flat brush: full at once, lifting a little at the end
  wash: (u) => ramp(u, 0, 0.035) * (1 - 0.45 * ramp(u, 0.95, 1)),
  // a round brush: pressed in, then drawn out to a thin dry tail
  brush: (u) => (u < 0.14 ? lerp(0.4, 1, ease(u / 0.14)) : u < 0.62 ? 1 : lerp(1, 0.16, ease((u - 0.62) / 0.38))),
  even: (u) => 0.82 + 0.18 * Math.sin(Math.PI * clamp(u * 1.1)),
  tip: (u) => 0.25 + 0.75 * Math.pow(Math.sin(Math.PI * u), 0.7),
};

type Track = { o: number; a: number; dash: number[]; off: number; end: number; lw: number };
type Stroke = {
  t0: number; t1: number; rgb: string; a: number;
  // a ribbon
  n: number; x: Float32Array; y: Float32Array; nx: Float32Array; ny: Float32Array; hw: Float32Array;
  bodyEnd: number; tracks: Track[]; trackRgb: string;
  // or a plain line (pencil), a blob (gold leaf), a flat wash (a polygon laid three times)
  line?: { lw: number; dash?: number[] };
  blob?: { cx: number; cy: number; r: number; hi: boolean };
  poly?: boolean;
  /** A soft patch where the wash was still wet: `clip` is the panel it stays inside. */
  cloud?: { cx: number; cy: number; r: number; clip: [number, number, number, number] };
  /** A deep wash laid around reserved shapes: its outline is the stroke's own points. */
  ground?: { holes: Pt[][]; rows: Stroke[]; clouds: Stroke[]; base: number };
  seed: number;
};
type StrokeOpt = { profile?: Profile; rgb?: string; a?: number; seed: number; t0?: number; t1?: number; tracks?: number; trackRgb?: string; dry?: number; wob?: number; rough?: number };

/** Resamples a polyline to n points at even spacing. */
function resample(pts: Pt[], n: number): Pt[] {
  const d = [0];
  for (let i = 1; i < pts.length; i++) d.push(d[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const len = d[d.length - 1] || 1, out: Pt[] = [];
  let k = 1;
  for (let i = 0; i < n; i++) {
    const t = (i / (n - 1)) * len;
    while (k < pts.length - 1 && d[k] < t) k++;
    const f = (t - d[k - 1]) / Math.max(1e-6, d[k] - d[k - 1]);
    out.push([lerp(pts[k - 1][0], pts[k][0], f), lerp(pts[k - 1][1], pts[k][1], f)]);
  }
  return out;
}
const length = (pts: Pt[]) => { let l = 0; for (let i = 1; i < pts.length; i++) l += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); return l; };

/** One brush stroke: a ribbon along the points, `width` at its fullest. */
function mk(pts: Pt[], width: number, o: StrokeOpt): Stroke {
  const r = rng(o.seed), len = length(pts);
  const n = Math.round(clamp(len / 5, 6, 96));
  const q = resample(pts, n), prof = PROFILE[o.profile ?? "wash"], wob = o.wob ?? Math.min(1.5, width * 0.1), rough = o.rough ?? 0.22;
  const x = new Float32Array(n), y = new Float32Array(n), nx = new Float32Array(n), ny = new Float32Array(n), hw = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const a = q[Math.max(0, i - 1)], b = q[Math.min(n - 1, i + 1)];
    const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
    nx[i] = -dy / l; ny[i] = dx / l;
    const u = i / (n - 1), w = vnoise(u * (len / 46) + 3, o.seed) * wob;
    x[i] = q[i][0] + nx[i] * w; y[i] = q[i][1] + ny[i] * w;
    // unevenness along the edge: about a fifth for a single stroke, much less inside a flat wash
    hw[i] = (width / 2) * prof(u) * (1 + rough * vnoise(u * (len / (rough > 0.15 ? 15 : 34)), o.seed + 7));
  }
  const tracks: Track[] = [];
  const count = o.tracks ?? (width < 3 ? 0 : Math.round(clamp(width / (rough > 0.15 ? 3.2 : 5), 3, 9)));
  const a = o.a ?? 0.3;
  for (let i = 0; i < count; i++) {
    tracks.push({
      o: (r() * 2 - 1) * 0.86, a: a * (rough > 0.15 ? 0.3 + r() * 0.55 : 0.1 + r() * 0.24), end: r() < 0.3 ? 0.8 + r() * 0.14 : 1, off: r() * 60,
      dash: [10 + r() * 52, 2 + r() * 10, 6 + r() * 36, 1 + r() * 7], lw: Math.min(1.7, 0.55 + r() * (0.5 + width * 0.03)),
    });
  }
  return { t0: o.t0 ?? 0, t1: o.t1 ?? 1, rgb: o.rgb ?? INK_MID, a, n, x, y, nx, ny, hw, bodyEnd: 1 - (o.dry ?? 0.5) * (0.03 + r() * 0.1), tracks, trackRgb: o.trackRgb ?? o.rgb ?? INK_MID, seed: o.seed };
}
/** A plain line: pencil, or a thin thread. */
function ln(pts: Pt[], o: { lw?: number; dash?: number[]; rgb?: string; a?: number; seed: number; t0?: number; t1?: number; wob?: number }): Stroke {
  const s = mk(pts, 1, { seed: o.seed, rgb: o.rgb ?? PENCIL, a: o.a ?? 0.5, t0: o.t0, t1: o.t1, tracks: 0, wob: o.wob ?? 0.7 });
  s.line = { lw: o.lw ?? 0.9, dash: o.dash };
  return s;
}
/** A disc of gold leaf (or of pigment). */
function blob(cx: number, cy: number, r: number, o: { rgb?: string; a?: number; seed: number; t0?: number; t1?: number; hi?: boolean }): Stroke {
  const n = 22, pts: Pt[] = [];
  for (let i = 0; i <= n; i++) { const t = (i / n) * Math.PI * 2, k = 1 + 0.07 * vnoise((i % n) * 0.9, o.seed); pts.push([cx + Math.cos(t) * r * k, cy + Math.sin(t) * r * k]); }
  const s = mk(pts, 1, { seed: o.seed, rgb: o.rgb ?? GOLD, a: o.a ?? 0.96, t0: o.t0, t1: o.t1, tracks: 0, wob: 0 });
  // keep the outline exactly as built
  for (let i = 0; i < s.n; i++) { const t = (i / (s.n - 1)) * Math.PI * 2, k = 1 + 0.07 * vnoise(((i * n) / (s.n - 1)) * 0.9, o.seed); s.x[i] = cx + Math.cos(t) * r * k; s.y[i] = cy + Math.sin(t) * r * k; }
  s.blob = { cx, cy, r, hi: o.hi ?? true };
  return s;
}
/** A darker patch inside a wash, soft at the edge: paint that met paint while both were wet. */
function cloud(cx: number, cy: number, r: number, clip: [number, number, number, number], o: { rgb?: string; a?: number; seed: number; t0?: number; t1?: number }): Stroke {
  const s = mk([[cx - r, cy], [cx + r, cy]], 1, { seed: o.seed, rgb: o.rgb ?? INK_MID, a: o.a ?? 0.12, t0: o.t0, t1: o.t1, tracks: 0, wob: 0 });
  s.cloud = { cx, cy, r, clip };
  return s;
}
/** A flat wash: one polygon laid three times with its corners nudged, so the edges darken where the passes disagree. */
function wash(pts: Pt[], o: { rgb?: string; a?: number; seed: number; t0?: number; t1?: number }): Stroke {
  const closed = [...pts, pts[0]];
  const s = mk(closed, 1, { seed: o.seed, rgb: o.rgb ?? INK_MID, a: o.a ?? 0.2, t0: o.t0, t1: o.t1, tracks: 0, wob: 0 });
  s.poly = true;
  return s;
}

function drawStroke(g: CanvasRenderingContext2D, s: Stroke, f: number) {
  if (f <= 0) return;
  if (s.ground) {
    const G = s.ground, outline = () => { g.beginPath(); for (let i = 0; i < s.n; i++) { if (i) g.lineTo(s.x[i], s.y[i]); else g.moveTo(s.x[i], s.y[i]); } g.closePath(); };
    const holes = () => { for (const h of G.holes) { h.forEach(([px, py], i) => (i ? g.lineTo(px, py) : g.moveTo(px, py))); g.closePath(); } };
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < s.n; i++) { x0 = Math.min(x0, s.x[i]); y0 = Math.min(y0, s.y[i]); x1 = Math.max(x1, s.x[i]); y1 = Math.max(y1, s.y[i]); }
    g.save();
    outline(); holes(); g.clip("evenodd");
    // a thin first wash over the whole field, then rows of the flat brush, then the wet patches
    g.fillStyle = `rgba(${INK_DEEP},${G.base * ease(clamp(f / 0.45))})`; g.fillRect(x0, y0, x1 - x0, y1 - y0);
    for (const st of G.rows) drawStroke(g, st, clamp((f - st.t0) / (st.t1 - st.t0)));
    for (const st of G.clouds) drawStroke(g, st, clamp((f - st.t0) / (st.t1 - st.t0)));
    // the pigment pools where it meets a reserved panel
    if (f > 0.6) { g.beginPath(); holes(); g.lineWidth = 1.6; g.strokeStyle = `rgba(${INK_DEEP},${0.55 * ease((f - 0.6) / 0.4)})`; g.stroke(); }
    g.restore();
    // and dries darker along its own edge
    if (f > 0.5) { outline(); g.lineWidth = 1.8; g.strokeStyle = `rgba(${INK_DEEP},${0.42 * ease((f - 0.5) / 0.5)})`; g.stroke(); }
    return;
  }
  if (s.blob) {
    // gold leaf: the disc grows from its centre, with a lighter crescent and a darker rim
    const k = ease(f), b = s.blob;
    g.beginPath();
    for (let i = 0; i < s.n; i++) { const px = b.cx + (s.x[i] - b.cx) * k, py = b.cy + (s.y[i] - b.cy) * k; if (i) g.lineTo(px, py); else g.moveTo(px, py); }
    g.closePath(); g.fillStyle = `rgba(${s.rgb},${s.a})`; g.fill();
    if (b.hi) {
      g.lineWidth = Math.max(0.5, b.r * 0.07); g.strokeStyle = `rgba(${GOLD_LO},.45)`; g.stroke();
      g.beginPath(); g.ellipse(b.cx - b.r * 0.2 * k, b.cy - b.r * 0.24 * k, b.r * 0.5 * k, b.r * 0.34 * k, -0.6, 0, Math.PI * 2);
      g.fillStyle = `rgba(${GOLD_HI},.5)`; g.fill();
    }
    return;
  }
  if (s.cloud) {
    const c = s.cloud, gr = g.createRadialGradient(c.cx, c.cy, c.r * 0.15, c.cx, c.cy, c.r);
    gr.addColorStop(0, `rgba(${s.rgb},${s.a * ease(f)})`); gr.addColorStop(1, `rgba(${s.rgb},0)`);
    g.save(); g.beginPath(); g.rect(c.clip[0], c.clip[1], c.clip[2], c.clip[3]); g.clip();
    g.fillStyle = gr; g.fillRect(c.cx - c.r, c.cy - c.r, c.r * 2, c.r * 2); g.restore();
    return;
  }
  if (s.poly) {
    for (let pass = 0; pass < 3; pass++) {
      g.beginPath();
      for (let i = 0; i < s.n - 1; i++) {
        const j = 2.6, px = s.x[i] + h1(i * 3 + pass, s.seed) * j, py = s.y[i] + h1(i * 3 + pass + 40, s.seed) * j;
        if (i) g.lineTo(px, py); else g.moveTo(px, py);
      }
      g.closePath(); g.fillStyle = `rgba(${s.rgb},${(s.a / 3) * 1.25 * ease(f)})`; g.fill();
    }
    return;
  }
  if (s.line) {
    const last = f * (s.n - 1), m = Math.floor(last), fr = last - m;
    g.beginPath(); g.moveTo(s.x[0], s.y[0]);
    for (let i = 1; i <= m; i++) g.lineTo(s.x[i], s.y[i]);
    if (fr > 0 && m < s.n - 1) g.lineTo(lerp(s.x[m], s.x[m + 1], fr), lerp(s.y[m], s.y[m + 1], fr));
    g.lineWidth = s.line.lw; g.lineCap = "round"; g.lineJoin = "round"; g.setLineDash(s.line.dash ?? []); g.strokeStyle = `rgba(${s.rgb},${s.a})`; g.stroke(); g.setLineDash([]);
    return;
  }
  // the body: a thin wash, stopping a little short so the bristles run on alone
  const last = Math.min(f, s.bodyEnd) * (s.n - 1), m = Math.floor(last), fr = last - m, more = fr > 0 && m < s.n - 1;
  g.beginPath();
  for (let i = 0; i <= m; i++) { const px = s.x[i] + s.nx[i] * s.hw[i], py = s.y[i] + s.ny[i] * s.hw[i]; if (i) g.lineTo(px, py); else g.moveTo(px, py); }
  if (more) {
    const cx = lerp(s.x[m], s.x[m + 1], fr), cy = lerp(s.y[m], s.y[m + 1], fr), w = lerp(s.hw[m], s.hw[m + 1], fr);
    g.lineTo(cx + s.nx[m] * w, cy + s.ny[m] * w); g.lineTo(cx - s.nx[m] * w, cy - s.ny[m] * w);
  }
  for (let i = m; i >= 0; i--) g.lineTo(s.x[i] - s.nx[i] * s.hw[i], s.y[i] - s.ny[i] * s.hw[i]);
  g.closePath(); g.fillStyle = `rgba(${s.rgb},${s.a})`; g.fill();
  // the bristles: darker tracks inside the stroke, broken, some giving out early
  g.lineCap = "butt"; g.lineJoin = "round";
  for (const t of s.tracks) {
    const e = Math.min(f, t.end) * (s.n - 1), tm = Math.floor(e);
    if (tm < 1) continue;
    g.beginPath();
    for (let i = 0; i <= tm; i++) { const px = s.x[i] + s.nx[i] * s.hw[i] * t.o, py = s.y[i] + s.ny[i] * s.hw[i] * t.o; if (i) g.lineTo(px, py); else g.moveTo(px, py); }
    g.setLineDash(t.dash); g.lineDashOffset = t.off; g.lineWidth = t.lw; g.strokeStyle = `rgba(${s.trackRgb},${t.a})`; g.stroke();
  }
  g.setLineDash([]);
}

// ------------------------------------------------------------------ objects
type Obj = {
  x: number; y: number; w: number; h: number; strokes: Stroke[];
  /** When it paints in: a stretch of the film, or of the opening when `intro` is set. */
  at: Win; intro?: boolean;
  /** When it lifts back to paper. */
  out?: Win;
  layer: number; grain: number; gold: boolean;
  cv?: HTMLCanvasElement; q?: number; ss?: number;
};
type ObjOpt = { at: Win; out?: Win; intro?: boolean; layer?: number; grain?: number; gold?: boolean };

const OBJS: Obj[] = [];
/** Moves a stroke, and everything it carries, by (dx, dy). */
function shift(s: Stroke, dx: number, dy: number) {
  for (let i = 0; i < s.n; i++) { s.x[i] += dx; s.y[i] += dy; }
  if (s.blob) { s.blob.cx += dx; s.blob.cy += dy; }
  if (s.cloud) { s.cloud.cx += dx; s.cloud.cy += dy; s.cloud.clip[0] += dx; s.cloud.clip[1] += dy; }
  if (s.ground) {
    for (const h of s.ground.holes) for (const q of h) { q[0] += dx; q[1] += dy; }
    for (const r of s.ground.rows) shift(r, dx, dy);
    for (const c of s.ground.clouds) shift(c, dx, dy);
  }
}
function add(strokes: Stroke[], o: ObjOpt): Obj {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const s of strokes) for (let i = 0; i < s.n; i++) {
    const r = (s.ground ? 8 : s.line ? s.line.lw : s.blob || s.poly || s.cloud ? 3 : s.hw[i]) + 4;
    x0 = Math.min(x0, s.x[i] - r); y0 = Math.min(y0, s.y[i] - r); x1 = Math.max(x1, s.x[i] + r); y1 = Math.max(y1, s.y[i] + r);
  }
  for (const s of strokes) shift(s, -x0, -y0);
  const ob: Obj = { x: x0, y: y0, w: x1 - x0, h: y1 - y0, strokes, at: o.at, out: o.out, intro: o.intro, layer: o.layer ?? 2, grain: o.grain ?? 0.5, gold: o.gold ?? false };
  OBJS.push(ob);
  return ob;
}

type Tone = "pale" | "mid" | "deep" | "gold";
const TONE: Record<Tone, { rgb: string; a: number }> = {
  pale: { rgb: INK_TINT, a: 0.24 }, mid: { rgb: INK_MID, a: 0.4 }, deep: { rgb: INK_DEEP, a: 0.74 }, gold: { rgb: GOLD, a: 0.95 },
};
let SEED = 11;

/**
 * A panel of the website. In pigment: a thin flat wash, rows of a flat brush back and forth over it,
 * a patch or two where the wash was still wet, then the darker edge where it pooled.
 * In gold: leaf laid over whatever is there, in squares whose seams just show.
 */
function panel(x: number, y: number, w: number, h: number, tone: Tone, o: ObjOpt & { rows?: number }) {
  const seed = (SEED += 17), r = rng(seed), t = TONE[tone], gold = tone === "gold";
  const rows = o.rows ?? Math.round(clamp(h / 32, 1, 6)), rh = h / rows, strokes: Stroke[] = [];
  const one = rows === 1;
  if (!one) strokes.push(wash([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], { rgb: t.rgb, a: t.a * (gold ? 0.8 : 0.42), seed: seed + 50, t0: 0, t1: 0.6 }));
  for (let i = 0; i < rows; i++) {
    const yy = y + rh * (i + 0.5), a: Pt = [x - 1 - r() * 4, yy + (r() - 0.5) * 1.6], b: Pt = [x + w + 1 + r() * 5, yy + (r() - 0.5) * 1.6];
    const mid: Pt = [(a[0] + b[0]) / 2, yy + (r() - 0.5) * 2];
    const t0 = one ? 0 : (i / rows) * 0.66;
    strokes.push(mk(i % 2 ? [b, mid, a] : [a, mid, b], rh * (one ? 1 : 1.07), {
      profile: "wash", rgb: t.rgb, a: one ? t.a : t.a * (gold ? 0.62 : 0.62 + r() * 0.1), seed: seed + i, t0, t1: one ? 0.92 : t0 + Math.max(0.3, 1.1 / rows),
      trackRgb: gold ? GOLD_HI : t.rgb, dry: one ? 1 : 0.4, rough: one ? 0.2 : 0.07, wob: one ? undefined : 0.6,
    }));
  }
  if (gold && !one) {
    // the seams between the squares of leaf
    for (let sx = x + 38 + r() * 14; sx < x + w - 20; sx += 40 + r() * 16)
      strokes.push(ln([[sx, y + 2], [sx + (r() - 0.5) * 3, y + h - 2]], { lw: 0.7, rgb: GOLD_LO, a: 0.3, seed: seed + Math.round(sx), t0: 0.7, t1: 1, wob: 0.5 }));
  }
  if (!gold && !one) {
    const n = w * h > 30000 ? 2 : 1;
    for (let k = 0; k < n; k++) strokes.push(cloud(x + w * (0.2 + r() * 0.6), y + h * (0.25 + r() * 0.5), Math.min(w, h) * (0.5 + r() * 0.3), [x, y, w, h], { rgb: t.rgb, a: t.a * 0.4, seed: seed + 60 + k, t0: 0.3, t1: 0.9 }));
    // the pooled edge: the only line a watercolour has
    const c = 5, e: Pt[] = [[x + c, y], [x + w - c, y], [x + w, y + c], [x + w, y + h - c], [x + w - c, y + h], [x + c, y + h], [x, y + h - c], [x, y + c], [x + c, y]];
    strokes.push(ln(e, { lw: 1.1, rgb: INK_DEEP, a: tone === "deep" ? 0.55 : 0.34, seed: seed + 90, t0: 0.72, t1: 1, wob: 0.8 }));
  }
  return add(strokes, { ...o, gold, grain: o.grain ?? (gold ? 0.2 : 0.5) });
}
/**
 * A deep wash of ink: a field with a brush edge all round, painted in
 * rows of a wide flat brush, with the panels left as paper. The panels are painted into the paper
 * afterwards, so the website appears where the paint did not go.
 */
function ground(rect: [number, number, number, number], holes: [number, number, number, number][], o: ObjOpt) {
  const seed = (SEED += 29), r = rng(seed), [x, y, w, h] = rect, edge: Pt[] = [];
  const side = (ax: number, ay: number, bx: number, by: number, nx: number, ny: number, k: number) => {
    const len = Math.hypot(bx - ax, by - ay), n = Math.max(10, Math.round(len / 6));
    for (let i = 0; i < n; i++) {
      const t = i / n, d = t * len, a = 6 * vnoise(d / 70, seed + k) + 2.4 * vnoise(d / 16, seed + k + 9) + 0.8 * vnoise(d / 4, seed + k + 17);
      edge.push([lerp(ax, bx, t) + nx * a, lerp(ay, by, t) + ny * a]);
    }
  };
  side(x, y, x + w, y, 0, -1, 1); side(x + w, y, x + w, y + h, 1, 0, 2); side(x + w, y + h, x, y + h, 0, 1, 3); side(x, y + h, x, y, -1, 0, 4);
  const reserved = holes.map(([hx, hy, hw, hh]) => [[hx - 0.5, hy - 0.5], [hx + hw + 0.5, hy - 0.5], [hx + hw + 0.5, hy + hh + 0.5], [hx - 0.5, hy + hh + 0.5]] as Pt[]);
  const n = Math.max(4, Math.round(h / 46)), rh = h / n, rows: Stroke[] = [];
  for (let i = 0; i < n; i++) {
    const yy = y + rh * (i + 0.5), t0 = (i / n) * 0.74;
    const a: Pt = [x - 16 - r() * 10, yy + (r() - 0.5) * 3], b: Pt = [x + w + 16 + r() * 10, yy + (r() - 0.5) * 3], m: Pt = [(a[0] + b[0]) / 2, yy + (r() - 0.5) * 4];
    rows.push(mk(i % 2 ? [b, m, a] : [a, m, b], rh * 1.5, { profile: "wash", rgb: INK_DEEP, a: 0.26 + r() * 0.06, seed: seed + i, t0, t1: t0 + 0.26, rough: 0.07, wob: 0.8, dry: 0.4 }));
  }
  const clouds: Stroke[] = [];
  for (let k = 0; k < 3; k++) clouds.push(cloud(x + w * (0.12 + r() * 0.76), y + h * (0.12 + r() * 0.76), Math.min(w, h) * (0.32 + r() * 0.26), [x - 20, y - 20, w + 40, h + 40], { rgb: INK_DEEP, a: 0.24, seed: seed + 70 + k, t0: 0.35, t1: 0.95 }));
  const st = mk([edge[0], edge[1]], 1, { seed, tracks: 0, wob: 0 });
  st.n = edge.length; st.x = Float32Array.from(edge, (q) => q[0]); st.y = Float32Array.from(edge, (q) => q[1]);
  st.nx = new Float32Array(st.n); st.ny = new Float32Array(st.n); st.hw = new Float32Array(st.n);
  st.ground = { holes: reserved, rows, clouds, base: 0.62 };
  return add([st], { layer: 0, grain: 0.42, ...o });
}
/** Lines of content inside a panel: [x, y, length, thickness]. */
function lines(specs: [number, number, number, number][], o: ObjOpt & { rgb?: string; a?: number }) {
  const seed = (SEED += 13);
  return add(specs.map(([x, y, l, th], i) => mk([[x, y], [x + l, y + (h1(i, seed)) * 0.8]], th, {
    profile: "even", rgb: o.rgb ?? INK_DEEP, a: o.a ?? 0.6, seed: seed + i, t0: (i / specs.length) * 0.7, t1: (i / specs.length) * 0.7 + 0.3, dry: 1,
  })), { layer: 3, ...o });
}
/** The pencil underdrawing of a rectangle: four lines that run a little past their corners. */
function sketch(rects: [number, number, number, number][], o: ObjOpt) {
  const seed = (SEED += 7), r = rng(seed), strokes: Stroke[] = [];
  rects.forEach(([x, y, w, h], k) => {
    const e = () => 3 + r() * 7, t0 = (k / rects.length) * 0.75, dt = 0.25 / 4;
    const sides: Pt[][] = [[[x - e(), y], [x + w + e(), y]], [[x + w, y - e()], [x + w, y + h + e()]], [[x + w + e(), y + h], [x - e(), y + h]], [[x, y + h + e()], [x, y - e()]]];
    sides.forEach((pts, i) => strokes.push(ln(pts, { seed: seed + k * 4 + i, a: 0.34, lw: 0.75, t0: t0 + i * dt, t1: t0 + (i + 1) * dt + 0.05 })));
  });
  return add(strokes, { layer: 1, grain: 0, ...o });
}
/** A curve from a to b that bows to one side. */
function bow(a: Pt, b: Pt, bulge: number, n = 16): Pt[] {
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1;
  const c: Pt = [mx - (dy / l) * bulge, my + (dx / l) * bulge], out: Pt[] = [];
  for (let i = 0; i <= n; i++) { const t = i / n, u = 1 - t; out.push([u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1]]); }
  return out;
}
/** Part of an ellipse, as points. Angles in turns. */
function arc(cx: number, cy: number, rx: number, ry: number, a0: number, a1: number, seed = 1, rough = 0.03): Pt[] {
  const n = Math.max(12, Math.round(Math.abs(a1 - a0) * 64)), out: Pt[] = [];
  for (let i = 0; i <= n; i++) { const t = lerp(a0, a1, i / n) * Math.PI * 2, k = 1 + rough * vnoise(i * 0.35, seed); out.push([cx + Math.cos(t) * rx * k, cy + Math.sin(t) * ry * k]); }
  return out;
}

// ------------------------------------------------------------------ notes (the painter's hand)
type Note = { text: string; x: number; y: number; at: Win; out?: Win; intro?: boolean; size?: number; rot?: number; align?: CanvasTextAlign; leader?: Pt[];
  /** Written over the deep wash: in light instead of ink. */
  light?: boolean; bare?: boolean };
const NOTES: Note[] = [];

// ------------------------------------------------------------------ the sheet
// Five passages along one long sheet, 900 apart. Each lifts back to paper as the camera leaves it.
// The website is painted in warm ink washes. Gold is laid only where the product acts: the visitor, the sources of an answer, the sentence
// that answers, the yes, the panel fitted to a visitor, the result.
const X2 = 900, X3 = 1800, X4 = 2700, X5 = 3600;

// ---- 1. your website, today: seven panels (painted by the opening, not by the scroll)
const S1_OUT: Win = [0.39, 0.425];
{
  const o = { intro: true, out: S1_OUT };
  sketch([[-300, -226, 600, 28], [-300, -184, 366, 176], [80, -184, 220, 176], [-300, 8, 188, 134], [-94, 8, 188, 134], [112, 8, 188, 134], [-300, 160, 136, 32]], { at: [0, 0.42], ...o });
  panel(-300, -226, 600, 28, "deep", { at: [0.14, 0.36], ...o });
  panel(-300, -184, 366, 176, "pale", { at: [0.24, 0.56], ...o });
  panel(80, -184, 220, 176, "mid", { at: [0.36, 0.64], ...o });
  panel(-300, 8, 188, 134, "pale", { at: [0.48, 0.72], ...o });
  panel(-94, 8, 188, 134, "mid", { at: [0.55, 0.79], ...o });
  panel(112, 8, 188, 134, "pale", { at: [0.62, 0.86], ...o });
  panel(-300, 160, 136, 32, "gold", { at: [0.82, 0.96], ...o, layer: 4 });
  // what the panels say (the upper two lift when their panels are gilded)
  lines([[-278, -154, 208, 13], [-278, -130, 150, 13], [-278, -98, 250, 4], [-278, -84, 228, 4], [-278, -70, 170, 4]], { at: [0.5, 0.82], intro: true, out: [0.172, 0.196] });
  lines([[98, -160, 150, 4], [98, -146, 176, 4], [98, -132, 120, 4], [98, -104, 164, 4], [98, -90, 140, 4]], { at: [0.58, 0.86], intro: true, out: [0.18, 0.204] });
  lines([[-284, 30, 96, 9], [-284, 52, 150, 4], [-284, 66, 118, 4], [-78, 30, 80, 9], [-78, 52, 146, 4], [-78, 66, 100, 4], [128, 30, 104, 9], [128, 52, 140, 4], [128, 66, 126, 4]], { at: [0.7, 0.98], ...o });
  NOTES.push({ text: "your website, today", x: 300, y: -243, at: [0.86, 1], out: [0.052, 0.07], intro: true, align: "right" });
}
// ---- a visitor arrives with a question (chapter "question")
add([ln(bow([-420, -330], [0, 75], -110, 30), { seed: 301, dash: [2, 7], lw: 1.8, a: 0.95, rgb: GOLD })], { at: [0.056, 0.088], out: [0.118, 0.145], gold: true, layer: 5, grain: 0 });
NOTES.push({ text: "a visitor, with a question", x: 40, y: 200, at: [0.09, 0.108], out: [0.118, 0.142], leader: bow([34, 182], [14, 98], 16) });
// ---- it answers out loud, from your own pages: the two pages it used are gilded (chapter "talks")
const TALK_OUT: Win = [0.25, 0.278];
add([
  mk(arc(0, 75, 30, 28, 0.58, 0.92, 5), 4.5, { profile: "tip", rgb: GOLD, a: 0.95, seed: 311, t0: 0, t1: 0.4, trackRgb: GOLD_HI }),
  mk(arc(0, 75, 30, 28, 1.08, 1.42, 5), 4.5, { profile: "tip", rgb: GOLD, a: 0.95, seed: 314, t0: 0.05, t1: 0.45, trackRgb: GOLD_HI }),
  mk(arc(0, 75, 50, 46, 0.6, 0.9, 6), 3.8, { profile: "tip", rgb: GOLD, a: 0.9, seed: 312, t0: 0.25, t1: 0.7, trackRgb: GOLD_HI }),
  mk(arc(0, 75, 50, 46, 1.1, 1.4, 6), 3.8, { profile: "tip", rgb: GOLD, a: 0.9, seed: 315, t0: 0.3, t1: 0.75, trackRgb: GOLD_HI }),
  mk(arc(0, 75, 72, 66, 0.62, 0.88, 7), 3, { profile: "tip", rgb: GOLD, a: 0.85, seed: 313, t0: 0.5, t1: 0.95, trackRgb: GOLD_HI }),
  mk(arc(0, 75, 72, 66, 1.12, 1.38, 7), 3, { profile: "tip", rgb: GOLD, a: 0.85, seed: 316, t0: 0.55, t1: 1, trackRgb: GOLD_HI }),
], { at: [0.118, 0.164], out: TALK_OUT, gold: true, layer: 7, grain: 0.14 });
add([
  mk(bow([-10, 50], [-120, -6], 22, 20), 3.2, { profile: "even", rgb: GOLD, a: 0.95, seed: 321, t0: 0, t1: 0.9, tracks: 0 }),
  mk(bow([10, 50], [190, -6], -26, 20), 3.2, { profile: "even", rgb: GOLD, a: 0.95, seed: 323, t0: 0.1, t1: 1, tracks: 0 }),
], { at: [0.158, 0.182], out: TALK_OUT, gold: true, layer: 7, grain: 0.1 });
panel(-300, -184, 366, 176, "gold", { at: [0.176, 0.212], out: S1_OUT, layer: 4 });
panel(80, -184, 220, 176, "gold", { at: [0.184, 0.218], out: S1_OUT, layer: 4 });
NOTES.push({ text: "source: /pricing", x: -280, y: -150, at: [0.208, 0.222], out: TALK_OUT, bare: true });
NOTES.push({ text: "source: /plans", x: 98, y: -150, at: [0.213, 0.227], out: TALK_OUT, bare: true });
// ---- it draws while it talks: a chart, a table, a slider, in ink on the gilded panels (chapter "shows")
const BARS = [34, 52, 44, 68, 0, 62];
add([
  ln([[-280, -52], [-44, -52]], { seed: 331, rgb: INK_DEEP, a: 0.8, lw: 1.1, t0: 0, t1: 0.25 }),
  ...BARS.map((bh, i) => (bh ? mk([[-262 + i * 38, -53], [-262 + i * 38, -53 - bh]], 23, { profile: "wash", rgb: INK_MID, a: 0.78, seed: 332 + i, t0: 0.12 + i * 0.12, t1: 0.42 + i * 0.12, dry: 1.2, rough: 0.06, wob: 0.3 }) : null)).filter((s): s is Stroke => !!s),
], { at: [0.262, 0.306], out: S1_OUT, layer: 5 });
const TALL_BAR = mk([[-110, -53], [-110, -53 - 116]], 23, { profile: "wash", rgb: INK_DEEP, a: 0.92, seed: 339, dry: 1.2, rough: 0.06, wob: 0.3 });
add([ln([[-274, -26], [-52, -26]], { seed: 341, lw: 1.3, rgb: INK_DEEP, a: 0.8 })], { at: [0.3, 0.314], out: S1_OUT, layer: 5, grain: 0 });
{
  const grid: Stroke[] = [];
  [-166, -132, -98, -64, -30].forEach((y, i) => grid.push(ln([[96, y], [284, y]], { seed: 350 + i, rgb: INK_DEEP, a: 0.7, t0: i * 0.08, t1: 0.3 + i * 0.08 })));
  [98, 160, 221, 282].forEach((x, i) => grid.push(ln([[x, -168], [x, -28]], { seed: 360 + i, rgb: INK_DEEP, a: 0.7, t0: 0.3 + i * 0.07, t1: 0.6 + i * 0.07 })));
  add(grid, { at: [0.284, 0.318], out: S1_OUT, layer: 5, grain: 0 });
  const cells: [number, number, number, number][] = [];
  for (let r = 0; r < 4; r++) for (let c = 0; c < 3; c++) cells.push([106 + c * 61.5, -149 + r * 34, 22 + ((r * 7 + c * 11) % 5) * 5, r === 0 ? 7 : 4]);
  lines(cells, { at: [0.3, 0.332], out: S1_OUT, layer: 5, a: 0.85 });
}
NOTES.push({ text: "example figures", x: 300, y: -243, at: [0.33, 0.345], out: [0.385, 0.405], align: "right", size: 20 });

// ---- 2. it opens the right page, at the sentence that answers (chapter "there")
const S2_OUT: Win = [0.632, 0.665];
{
  const o = { out: S2_OUT };
  sketch([[X2 - 300, -226, 600, 28], [X2 - 300, -184, 600, 58], [X2 - 300, -112, 600, 84], [X2 - 300, -14, 600, 84], [X2 - 300, 84, 600, 84]], { at: [0.4, 0.432], ...o });
  panel(X2 - 300, -226, 600, 28, "deep", { at: [0.408, 0.43], ...o });
  panel(X2 - 300, -184, 600, 58, "mid", { at: [0.414, 0.44], ...o });
  panel(X2 - 300, -112, 600, 84, "pale", { at: [0.42, 0.448], ...o });
  panel(X2 - 300, -14, 600, 84, "pale", { at: [0.426, 0.454], ...o });
  panel(X2 - 300, 84, 600, 84, "pale", { at: [0.432, 0.46], ...o });
  // the sentence that answers is gilded, then ringed with one loaded brush, round once and a little more
  add([mk([[X2 - 284, 37], [X2 + 232, 37]], 26, { profile: "wash", rgb: GOLD, a: 0.94, seed: 402, trackRgb: GOLD_HI, dry: 1.3, rough: 0.12 })], { at: [0.452, 0.474], ...o, gold: true, layer: 4, grain: 0.2 });
  lines([[X2 - 280, -156, 230, 13], [X2 - 280, -88, 120, 8], [X2 - 280, -68, 470, 4], [X2 - 280, -54, 430, 4], [X2 - 280, 10, 150, 8], [X2 - 280, 30, 500, 4], [X2 - 280, 44, 360, 4], [X2 - 280, 108, 110, 8], [X2 - 280, 128, 450, 4], [X2 - 280, 142, 300, 4]], { at: [0.436, 0.47], ...o, layer: 5 });
  add([mk(arc(X2, 28, 326, 64, 0.62, 1.7, 9, 0.022), 10, { profile: "brush", rgb: GOLD, a: 0.95, seed: 401, trackRgb: GOLD_HI, dry: 1.6 })], { at: [0.464, 0.5], ...o, gold: true, layer: 7, grain: 0.2 });
  NOTES.push({ text: "this sentence answers it", x: X2 + 296, y: 198, at: [0.49, 0.506], out: [0.532, 0.552], align: "right", leader: bow([X2 + 200, 180], [X2 + 226, 98], -14) });
}
// ---- it books the meeting, after a yes; your team gets the lead (chapter "books")
{
  const o = { out: S2_OUT };
  sketch([[X2 - 40, 200, 196, 118]], { at: [0.546, 0.56], ...o });
  panel(X2 - 40, 200, 196, 118, "pale", { at: [0.55, 0.574], ...o });
  const cal: Stroke[] = [];
  [232, 258, 284].forEach((y, i) => cal.push(ln([[X2 - 26, y], [X2 + 142, y]], { seed: 420 + i, t0: i * 0.1, t1: 0.4 + i * 0.1 })));
  [X2 + 16, X2 + 58, X2 + 100].forEach((x, i) => cal.push(ln([[x, 214], [x, 304]], { seed: 430 + i, t0: 0.3 + i * 0.1, t1: 0.7 + i * 0.1 })));
  add(cal, { at: [0.562, 0.582], ...o, layer: 4, grain: 0 });
  // the yes: a tick in gold
  add([mk([[X2 + 58, 262], [X2 + 76, 286], [X2 + 84, 292], [X2 + 96, 272], [X2 + 130, 226]], 11, { profile: "brush", rgb: GOLD, a: 0.96, seed: 441, trackRgb: GOLD_HI, dry: 1.5 })], { at: [0.578, 0.594], ...o, gold: true, layer: 7, grain: 0.14 });
  add([ln(bow([X2 + 164, 250], [X2 + 262, 214], -26, 20), { seed: 451, dash: [2, 7], lw: 1.8, a: 0.95, rgb: GOLD })], { at: [0.588, 0.602], ...o, gold: true, layer: 5, grain: 0 });
  // the lead: a card of gold, sent to the team
  panel(X2 + 268, 170, 116, 80, "gold", { at: [0.596, 0.612], ...o, layer: 4, rows: 3 });
  lines([[X2 + 280, 190, 54, 7], [X2 + 280, 208, 84, 3.4], [X2 + 280, 221, 66, 3.4], [X2 + 280, 234, 76, 3.4]], { at: [0.604, 0.616], ...o, layer: 5, a: 0.85 });
  NOTES.push({ text: "Thursday, 11:00", x: X2 - 40, y: 190, at: [0.566, 0.58], out: S2_OUT, size: 22 });
  NOTES.push({ text: "the lead, to your team", x: X2 + 384, y: 282, at: [0.606, 0.618], out: S2_OUT, align: "right", size: 22 });
}

// ---- 3. the page changes to fit the visitor (chapter "fits"): painted twice, differently
{
  const A: Win = [0.692, 0.716], C_OUT: Win = [0.778, 0.805], L = X3 - 300;
  panel(L, -226, 600, 28, "deep", { at: [0.636, 0.656], out: C_OUT });
  // first visitor: pricing first, and gilded
  sketch([[L, -184, 366, 176], [L + 380, -184, 220, 176], [L, 8, 188, 134], [L + 206, 8, 188, 134], [L + 412, 8, 188, 134]], { at: [0.636, 0.662], out: A });
  panel(L, -184, 366, 176, "gold", { at: [0.644, 0.668], out: A, layer: 4 });
  panel(L + 380, -184, 220, 176, "pale", { at: [0.648, 0.67], out: A });
  panel(L, 8, 188, 134, "pale", { at: [0.654, 0.674], out: [0.688, 0.71] });
  panel(L + 206, 8, 188, 134, "mid", { at: [0.658, 0.678], out: [0.688, 0.71] });
  panel(L + 412, 8, 188, 134, "pale", { at: [0.662, 0.68], out: [0.688, 0.71] });
  panel(L, 160, 136, 32, "deep", { at: [0.674, 0.684], out: [0.686, 0.706] });
  lines([[L + 22, -154, 150, 13], [L + 22, -124, 250, 4], [L + 22, -110, 210, 4], [L + 22, -70, 86, 15], [L + 124, -70, 86, 15], [L + 226, -70, 86, 15]], { at: [0.662, 0.682], out: A, layer: 5, a: 0.8 });
  NOTES.push({ text: "came for pricing: pricing first", x: L + 24, y: -243, at: [0.668, 0.684], out: [0.692, 0.708] });
  // second visitor: security first, and a different shape of page
  sketch([[L, -184, 220, 176], [L + 234, -184, 366, 176], [L, 8, 292, 134], [L + 308, 8, 292, 134]], { at: [0.706, 0.728], out: C_OUT });
  panel(L, -184, 220, 176, "pale", { at: [0.71, 0.732], out: C_OUT });
  panel(L + 234, -184, 366, 176, "gold", { at: [0.714, 0.74], out: C_OUT, layer: 4 });
  panel(L, 8, 292, 134, "mid", { at: [0.722, 0.742], out: C_OUT });
  panel(L + 308, 8, 292, 134, "pale", { at: [0.726, 0.746], out: C_OUT });
  panel(L + 464, 160, 136, 32, "deep", { at: [0.74, 0.75], out: C_OUT });
  lines([[L + 18, -154, 110, 9], [L + 18, -128, 170, 4], [L + 18, -114, 140, 4], [L + 18, 34, 130, 9], [L + 18, 58, 230, 4], [L + 18, 72, 190, 4], [L + 326, 34, 110, 9], [L + 326, 58, 220, 4]], { at: [0.73, 0.75], out: C_OUT });
  lines([[L + 256, -154, 170, 13], [L + 256, -122, 280, 4], [L + 256, -108, 240, 4], [L + 256, -94, 200, 4]], { at: [0.734, 0.752], out: C_OUT, layer: 5, a: 0.85 });
  NOTES.push({ text: "came for security: security first", x: L + 24, y: -243, at: [0.734, 0.75], out: C_OUT });
}

// ---- 4. three versions of one site (chapter "you")
{
  const o = { out: [0.872, 0.904] as Win };
  const mini = (cx: number, k: number, at: number) => {
    const l = cx - 100, w: Win = [at, at + 0.03];
    sketch([[l, -150, 200, 290]], { at: [at - 0.008, at + 0.012], ...o });
    panel(l, -150, 200, 20, "deep", { at: w, ...o });
    if (k === 0) { // many small cells, one of them live: the console
      [[0, 0], [1, 0], [0, 1], [1, 1], [0, 2], [1, 2]].forEach(([c, r], i) => panel(l + c * 104, -118 + r * 74, 96, 66, i === 3 ? "gold" : i % 3 === 1 ? "deep" : "mid", { at: [at + 0.006 + i * 0.003, at + 0.03 + i * 0.003], ...o, layer: i === 3 ? 4 : 2 }));
    } else if (k === 1) { // a lamp and a few soft words: admissions
      panel(l, -118, 200, 130, "pale", { at: [at + 0.006, at + 0.03], ...o });
      add([blob(cx, -56, 36, { seed: 601 })], { at: [at + 0.018, at + 0.034], ...o, gold: true, layer: 4, grain: 0.16 });
      lines([[l + 8, 34, 150, 10], [l + 8, 56, 184, 4], [l + 8, 70, 150, 4], [l + 8, 84, 170, 4]], { at: [at + 0.02, at + 0.04], ...o });
    } else { // ruled rows, one approved: the specification
      [0, 1, 2, 3].forEach((r) => panel(l, -118 + r * 60, 200, 50, r === 1 ? "gold" : "pale", { at: [at + 0.006 + r * 0.004, at + 0.03 + r * 0.004], ...o, rows: 2, layer: r === 1 ? 4 : 2 }));
      lines([[l + 10, -100, 90, 6], [l + 10, -40, 120, 5], [l + 10, 20, 100, 4], [l + 10, 80, 130, 4]], { at: [at + 0.022, at + 0.04], ...o, layer: 5 });
    }
    panel(l, 152, 84, 22, "deep", { at: [at + 0.03, at + 0.04], ...o });
  };
  mini(X4 - 270, 0, 0.776); mini(X4, 1, 0.787); mini(X4 + 270, 2, 0.798);
}

// ---- 5. one visitor in ten never sees it; the gap is the result (chapter "measure")
{
  const L = X5 - 270;
  ground([X5 - 338, -282, 676, 540], [], { at: [0.884, 0.912] });
  const dots: Stroke[] = [];
  for (let i = 0; i < 9; i++) dots.push(blob(L + i * 60, -160, 15, { seed: 700 + i, t0: i * 0.08, t1: 0.3 + i * 0.08 }));
  add(dots, { at: [0.892, 0.922], gold: true, layer: 6, grain: 0.1 });
  add([ln(arc(L + 540, -160, 15, 15, 0, 1.04, 3, 0.05), { seed: 711, lw: 1.5, a: 0.85, rgb: LIGHT })], { at: [0.916, 0.928], gold: true, layer: 5, grain: 0 });
  add([ln([[L, -84], [L, 172]], { seed: 721, rgb: LIGHT, a: 0.6, t0: 0, t1: 0.5 }), ln([[L - 6, 170], [L + 556, 170]], { seed: 722, rgb: LIGHT, a: 0.6, t0: 0.4, t1: 1 })], { at: [0.898, 0.92], gold: true, layer: 5, grain: 0 });
  const base = bow([L + 4, 148], [L + 548, 116], 8, 30), up = bow([L + 4, 146], [L + 548, -56], 66, 30);
  // the gap between the two lines, laid in gold: the extra sales
  add([wash([...up, ...[...base].reverse()], { rgb: GOLD, a: 0.86, seed: 731 })], { at: [0.944, 0.975], gold: true, layer: 2, grain: 0.24 });
  add([ln(base, { seed: 741, dash: [7, 6], lw: 1.6, a: 0.85, rgb: LIGHT })], { at: [0.918, 0.938], gold: true, layer: 5, grain: 0 });
  add([mk(up, 6, { profile: "even", rgb: LIGHT, a: 0.96, seed: 751, dry: 1.2 })], { at: [0.924, 0.956], gold: true, layer: 6, grain: 0.12 });
  NOTES.push({ text: "one in ten never sees it", x: L + 548, y: -200, at: [0.922, 0.936], align: "right", light: true, leader: bow([L + 524, -190], [L + 538, -178], -4) });
  NOTES.push({ text: "the difference", x: L + 330, y: 84, at: [0.962, 0.976], rot: -0.16, bare: true });
  NOTES.push({ text: "example", x: L + 552, y: 198, at: [0.966, 0.98], align: "right", size: 20, light: true });
}
OBJS.sort((a, b) => a.layer - b.layer);

// ------------------------------------------------------------------ the camera and the visitor
// [p, x, y, zoom]: it holds on a passage, then glides along the sheet to the next
const CAM: [number, number, number, number][] = [
  [0, 0, -17, 1], [0.06, 0, -17, 1], [0.088, -8, 22, 1.1], [0.118, -8, 22, 1.1], [0.146, 0, -17, 1], [0.25, 0, -17, 1], [0.29, 0, -68, 1.16], [0.386, 0, -68, 1.16],
  [0.43, X2, -12, 1], [0.528, X2, -12, 1], [0.56, X2 + 86, 118, 1.08], [0.628, X2 + 86, 118, 1.08], [0.668, X3, -17, 1], [0.776, X3, -17, 1],
  [0.806, X4, 8, 0.88], [0.872, X4, 8, 0.88], [0.91, X5, 2, 1], [1, X5, 2, 1],
];
// [p, x, y, radius]: the visitor, a disc of gold leaf
const DOT: [number, number, number, number][] = [
  [0.054, -420, -330, 0], [0.058, -404, -318, 14], [0.088, 0, 75, 14], [0.386, 0, 75, 14], [0.4, 120, 60, 0],
  [0.438, X2 - 420, 40, 0], [0.444, X2 - 380, 34, 13], [0.462, X2 - 312, 36, 13], [0.54, X2 - 312, 36, 13], [0.566, X2 - 62, 222, 13], [0.63, X2 - 62, 222, 13], [0.642, X2 + 20, 230, 0],
  [0.668, X3 - 290, -251, 0], [0.674, X3 - 290, -251, 9], [0.77, X3 - 290, -251, 9], [0.782, X3 - 290, -251, 0],
];
function track4(keys: [number, number, number, number][], p: number): [number, number, number] {
  if (p <= keys[0][0]) return [keys[0][1], keys[0][2], keys[0][3]];
  for (let i = 1; i < keys.length; i++) {
    if (p <= keys[i][0]) { const a = keys[i - 1], b = keys[i], t = ease(clamp((p - a[0]) / (b[0] - a[0]))); return [lerp(a[1], b[1], t), lerp(a[2], b[2], t), lerp(a[3], b[3], t)]; }
  }
  const l = keys[keys.length - 1];
  return [l[1], l[2], l[3]];
}

// ------------------------------------------------------------------ grain
let GRAIN: HTMLCanvasElement | null = null;
/** The tooth of the paper: specks and soft patches where the pigment did not settle. */
function grain(): HTMLCanvasElement {
  if (GRAIN) return GRAIN;
  const n = 384, cv = document.createElement("canvas");
  cv.width = cv.height = n;
  const g = cv.getContext("2d")!, im = g.createImageData(n, n), r = rng(77), cells = 9;
  const lat = new Float32Array(cells * cells).map(() => r());
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const fx = (x / n) * cells, fy = (y / n) * cells, x0 = Math.floor(fx), y0 = Math.floor(fy), tx = ease(fx - x0), ty = ease(fy - y0);
    const v = (i: number, j: number) => lat[(j % cells) * cells + (i % cells)];
    const soft = lerp(lerp(v(x0, y0), v(x0 + 1, y0), tx), lerp(v(x0, y0 + 1), v(x0 + 1, y0 + 1), tx), ty);
    const k = r(), speck = k > 0.8 ? (k - 0.8) / 0.2 : 0;
    im.data[(y * n + x) * 4 + 3] = Math.round(255 * clamp(speck * 0.62 + Math.max(0, soft - 0.42) * 0.9));
  }
  g.putImageData(im, 0, 0);
  return (GRAIN = cv);
}

/** Paints an object, as far as q (0 to 1), into its own canvas. Re-paints only when q or the size changed. */
function sprite(o: Obj, q: number, ss: number): HTMLCanvasElement {
  const cw = Math.max(1, Math.ceil(o.w * ss)), ch = Math.max(1, Math.ceil(o.h * ss));
  if (!o.cv) o.cv = document.createElement("canvas");
  if (o.q === q && o.ss === ss) return o.cv;
  if (o.cv.width !== cw || o.cv.height !== ch) { o.cv.width = cw; o.cv.height = ch; }
  const g = o.cv.getContext("2d")!;
  g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, cw, ch);
  g.setTransform(ss, 0, 0, ss, 0, 0);
  for (const s of o.strokes) drawStroke(g, s, clamp((q - s.t0) / (s.t1 - s.t0)));
  if (o.grain > 0) {
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = "destination-out"; g.globalAlpha = o.grain;
    const pat = g.createPattern(grain(), "repeat");
    if (pat) { g.fillStyle = pat; g.fillRect(0, 0, cw, ch); }
    g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;
  }
  o.q = q; o.ss = ss;
  return o.cv;
}

const VIEW_W = 700, VIEW_H = 566;
/** Sprites are painted a little larger than the camera ever shows them, so a push-in stays sharp. */
const ZMAX = 1.27;

export function renderWashFilm(g: CanvasRenderingContext2D, w: number, h: number, p: number, opt: WashOpt) {
  const fill = opt.layout === "fill", upright = !fill && w < h * 0.8;
  // where the painting sits: beside the copy on wide screens (from 45 % of the page's own grid, as in
  // app/globals.css: --gutter and --max), above it on upright ones
  const cw = w / opt.dpr, gut = Math.min(64, Math.max(20, cw * 0.044)), wrap = Math.min(1320, cw - 2 * gut), wl = (cw - wrap) / 2;
  const ax = fill || upright ? 0 : (wl + wrap * 0.45) * opt.dpr, ay = fill ? 0 : opt.top;
  const aw = w - ax - (fill || upright ? 0 : w * 0.03), ah = (fill ? h : upright ? h * 0.56 : h) - ay;
  const S = Math.min(aw / VIEW_W, ah / VIEW_H);
  const [cx, cy, cz] = opt.cam ?? track4(CAM, p);
  const Z = S * cz, ox = ax + aw / 2 - cx * Z, oy = ay + ah / 2 - cy * Z;
  const ss = Math.round(S * ZMAX * 100) / 100;

  // the sheet: it moves with the camera, so the fibres pass by as the picture glides
  g.setTransform(1, 0, 0, 1, 0, 0);
  g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;
  const pat = opt.paper && !opt.clear ? g.createPattern(opt.paper, "repeat") : null;
  if (opt.clear) g.clearRect(0, 0, w, h);
  else if (pat) {
    const k = opt.dpr / 2, tile = 1024 * k;
    pat.setTransform(new DOMMatrix([k, 0, 0, k, ((ox % tile) + tile) % tile, ((oy % tile) + tile) % tile]));
    g.fillStyle = pat;
    g.fillRect(0, 0, w, h);
  } else { g.fillStyle = PAPER; g.fillRect(0, 0, w, h); }

  for (const o of OBJS) {
    const q = o.intro ? ramp(opt.intro, o.at[0], o.at[1]) : clamp((p - o.at[0]) / (o.at[1] - o.at[0]));
    if (q <= 0) continue;
    const gone = o.out ? ramp(p, o.out[0], o.out[1]) : 0;
    if (gone >= 1) continue;
    const sx = ox + o.x * Z, sy = oy + o.y * Z, sw = o.w * Z, sh = o.h * Z;
    if (sx > w || sy > h || sx + sw < 0 || sy + sh < 0) continue;
    const cv = sprite(o, q, ss);
    // pigment darkens what is under it; gold is laid on top, opaque
    g.globalCompositeOperation = o.gold ? "source-over" : "multiply";
    g.globalAlpha = 1 - gone;
    g.drawImage(cv, sx, sy, sw, sh);
  }
  g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;

  // the tall bar of the chart grows as the slider is moved
  {
    const q = clamp((p - 0.294) / 0.02), gone = ramp(p, S1_OUT[0], S1_OUT[1]);
    if (q > 0 && gone < 1) {
      const k = ramp(p, 0.324, 0.362);
      g.setTransform(Z, 0, 0, Z, ox, oy);
      g.globalAlpha = 1 - gone;
      drawStroke(g, TALL_BAR, q * lerp(0.7, 1, k));
      const kq = clamp((p - 0.312) / 0.01);
      if (kq > 0) {
        g.beginPath(); g.arc(lerp(-214, -96, k), -26, 7.5 * ease(kq), 0, Math.PI * 2);
        g.fillStyle = `rgba(${INK_DEEP},.95)`; g.fill();
      }
      g.globalAlpha = 1;
    }
  }
  // the visitor
  {
    const [dx, dy, dr] = track4(DOT, p);
    if (dr > 0.3 && p > DOT[0][0] && p < DOT[DOT.length - 1][0]) {
      g.setTransform(Z, 0, 0, Z, ox, oy);
      const halo = g.createRadialGradient(dx, dy, dr * 0.6, dx, dy, dr * 3.4);
      halo.addColorStop(0, `rgba(${GOLD},.3)`); halo.addColorStop(1, `rgba(${GOLD},0)`);
      g.fillStyle = halo; g.beginPath(); g.arc(dx, dy, dr * 3.4, 0, Math.PI * 2); g.fill();
      disc(g, dx, dy, dr);
    }
  }
  // the notes: the design system's mono, small, uppercase and tracked, written left to right
  g.setTransform(Z, 0, 0, Z, ox, oy);
  g.textBaseline = "alphabetic"; g.lineJoin = "round";
  for (const n of NOTES) {
    const q = n.intro ? (p < 0.03 ? ramp(opt.intro, n.at[0], n.at[1]) : 1) : ramp(p, n.at[0], n.at[1]);
    const gone = n.out ? ramp(p, n.out[0], n.out[1]) : 0;
    if (q <= 0 || gone >= 1) continue;
    const size = (n.size ?? 25) * 0.5, text = n.text.toUpperCase();
    g.save();
    g.globalAlpha = 1 - gone;
    if (n.leader) {
      const lq = clamp(q * 2 - 1);
      if (lq > 0) {
        g.beginPath(); g.moveTo(n.leader[0][0], n.leader[0][1]);
        const m = Math.floor(lq * (n.leader.length - 1));
        for (let i = 1; i <= m; i++) g.lineTo(n.leader[i][0], n.leader[i][1]);
        g.lineWidth = 0.9; g.strokeStyle = n.light ? `rgba(${LIGHT},.7)` : `rgba(${PENCIL},.6)`; g.stroke();
      }
    }
    g.translate(n.x, n.y); if (n.rot) g.rotate(n.rot);
    g.font = `500 ${size}px ${opt.hand}`; g.textAlign = n.align ?? "left";
    (g as CanvasRenderingContext2D & { letterSpacing?: string }).letterSpacing = `${(size * 0.16).toFixed(2)}px`;
    const tw = g.measureText(text).width, left = n.align === "right" ? -tw : n.align === "center" ? -tw / 2 : 0;
    g.beginPath(); g.rect(left - 6, -size * 1.1, (tw + 12) * clamp(q * 2), size * 1.6); g.clip();
    g.fillStyle = n.light ? `rgba(${LIGHT},.94)` : `rgba(${NOTE_INK},.86)`; g.fillText(text, 0, 0);
    g.restore();
  }
  g.setTransform(1, 0, 0, 1, 0, 0);
}

/** A small disc of gold leaf, drawn live (the visitor, the slider's knob). */
function disc(g: CanvasRenderingContext2D, x: number, y: number, r: number) {
  if (r <= 0) return;
  g.beginPath();
  for (let i = 0; i <= 20; i++) { const t = (i / 20) * Math.PI * 2, k = 1 + 0.06 * vnoise((i % 20) * 0.9, 5); if (i) g.lineTo(x + Math.cos(t) * r * k, y + Math.sin(t) * r * k); else g.moveTo(x + Math.cos(t) * r * k, y + Math.sin(t) * r * k); }
  g.closePath(); g.fillStyle = `rgba(${GOLD},.97)`; g.fill();
  g.lineWidth = Math.max(0.5, r * 0.08); g.strokeStyle = `rgba(${GOLD_LO},.5)`; g.stroke();
  g.beginPath(); g.ellipse(x - r * 0.2, y - r * 0.24, r * 0.5, r * 0.34, -0.6, 0, Math.PI * 2); g.fillStyle = `rgba(${GOLD_HI},.5)`; g.fill();
}

