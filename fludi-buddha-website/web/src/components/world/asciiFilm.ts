/**
 * The SaaS world's film: a website of seven panels in 3D, drawn in plain characters.
 *
 * It is rendered live from the scroll position: `renderAsciiFilm(ctx, w, h, p)` draws the frame for
 * progress p (0 to 1). Nothing is pre-rendered, so it is sharp at any size and weighs a few kB.
 *
 * How it works:
 *  1. The seven panels are rectangles in 3D space (x right, y up, z towards the viewer).
 *  2. A camera (yaw, pitch, distance, target) is interpolated between the nine scenes.
 *  3. Each rectangle is projected onto a grid of character cells and rasterised: fill characters
 *     inside, line characters along the edges (- | / \) chosen by the direction of each edge.
 *  4. Each scene adds its own elements (a diagram, a slider, a lead card, a chart) and a few labels.
 *  5. The grid is painted with one fillText per row per brightness layer.
 *
 * Only basic ASCII is used so that every cell has the same width.
 */

type V3 = [number, number, number];
type Cam = { yaw: number; pitch: number; dist: number; t: V3 };
type Rect = [number, number, number, number]; // x (left), y (top), width, height, in world units

const DIM = 0, MID = 1, LIT = 2;
// The night-console palette: cool slate characters, gold for what is lit (the visitor, the answer).
const COLORS = ["#3a4250", "#9ba6b6", "#f6c064"];
const GLOW = "rgba(246, 192, 100, .55)";

export type AsciiOpt = {
  font: string;
  /** Height in canvas pixels covered by the site header: labels stay below it. */
  top?: number;
  /** A point of light (canvas pixels) that brightens the characters near it: the visitor's pointer. */
  light?: { x: number; y: number } | null;
};

// The page: 10 wide, about 6.3 tall, centred on the origin, in the plane z = 0.
const P: Record<string, Rect> = {
  nav: [-5, 3.15, 10, 0.5], hero: [-5, 2.4, 6.1, 2.7], side: [1.3, 2.4, 3.7, 2.7],
  c1: [-5, -0.55, 3.1, 2], c2: [-1.55, -0.55, 3.1, 2], c3: [1.9, -0.55, 3.1, 2], pill: [-5, -2.8, 2.2, 0.45],
};
const mid = (r: Rect, z = 0): V3 => [r[0] + r[2] / 2, r[1] - r[3] / 2, z];

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = (t: number) => t * t * (3 - 2 * t);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
/** 0 before a, 1 after b, eased in between. */
const ramp = (p: number, a: number, b: number) => ease(clamp((p - a) / (b - a)));
/** A stable pseudo-random number in [0, 1) for a cell: used to dissolve things in and out. */
const hash = (x: number, y: number) => { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); };

// ------------------------------------------------------------------ the nine scenes
// `at` is the stretch of the film the scene's own elements are on screen. Chapters in
// content/worlds/saas.ts sit inside these stretches.
const WIDE: Cam = { yaw: -0.3, pitch: 0.08, dist: 14, t: [0, 0.1, 0] };
const SCENES: { at: [number, number]; cam: Cam }[] = [
  { at: [0, 0.17], cam: WIDE },                                                              // S1 23:04, a buyer on the pricing card
  { at: [0.17, 0.285], cam: { yaw: -0.2, pitch: 0.06, dist: 13.6, t: [0, 0.2, 0] } },       // S2 three questions
  { at: [0.285, 0.405], cam: { yaw: -0.14, pitch: 0.04, dist: 9, t: mid(P.hero) } },       // S3 the integration, drawn
  { at: [0.405, 0.525], cam: { yaw: 0.12, pitch: 0.05, dist: 6.4, t: mid(P.c2) } },          // S4 the price for their team
  { at: [0.525, 0.635], cam: { yaw: 0.3, pitch: 0.04, dist: 7.8, t: mid(P.side) } },         // S5 the security page
  { at: [0.635, 0.745], cam: { yaw: -0.2, pitch: 0.1, dist: 14, t: [0, 0, 0] } },           // S6 the lead
  { at: [0.745, 0.835], cam: { yaw: -0.1, pitch: 0.08, dist: 10.5, t: [0, -0.8, 0] } },      // S7 a salesperson joins
  { at: [0.835, 0.925], cam: { yaw: 0.15, pitch: 0.1, dist: 15, t: [0, 0.1, 0] } },         // S8 the summary travels
  { at: [0.925, 1.001], cam: { yaw: 0, pitch: 0.02, dist: 17, t: [0, 0.2, 0] } },            // S9 the holdout chart
];

function camAt(p: number): Cam {
  let i = SCENES.findIndex((s) => p < s.at[1]);
  if (i < 0) i = SCENES.length - 1;
  const a = SCENES[i].cam, b = SCENES[Math.min(i + 1, SCENES.length - 1)].cam;
  // hold each scene's framing, then move to the next over the last 30 % of its stretch
  const [s0, s1] = SCENES[i].at;
  const k = ramp(p, lerp(s0, s1, 0.7), s1);
  return { yaw: lerp(a.yaw, b.yaw, k), pitch: lerp(a.pitch, b.pitch, k), dist: lerp(a.dist, b.dist, k),
           t: [lerp(a.t[0], b.t[0], k), lerp(a.t[1], b.t[1], k), lerp(a.t[2], b.t[2], k)] };
}
/** How far through scene i we are (0 to 1), and how visible its elements are (0 to 1). */
function scene(p: number, i: number) {
  const [a, b] = SCENES[i].at;
  const t = clamp((p - a) / (b - a));
  const v = Math.min(ramp(p, a - 0.012, a + 0.012), 1 - ramp(p, b - 0.012, b + 0.012));
  return { t, v };
}

// ------------------------------------------------------------------ the renderer
export function renderAsciiFilm(ctx: CanvasRenderingContext2D, w: number, h: number, p: number, opt: AsciiOpt) {
  const { font, top = 0, light = null } = opt;
  const narrow = w < h * 1.1;
  const cols = narrow ? 64 : 140;
  const cw = w / cols, fs = cw / 0.6, ch = fs * 1.22;
  const rows = Math.ceil(h / ch);
  const hud = Math.ceil(top / ch) + 1; // first row for labels at the top of the screen
  const chars = new Array<string>(cols * rows).fill(" ");
  const layer = new Uint8Array(cols * rows);
  // where the page sits on screen: right of the copy on wide screens, upper half on phones
  const cx = cols * (narrow ? 0.5 : 0.72), cy = rows * (narrow ? 0.25 : 0.5);
  const scale = cols * (narrow ? 0.82 : 0.6), cellAspect = cw / ch;

  let gate = 1; // cells with hash > gate are skipped: a dissolve
  const set = (x: number, y: number, c: string, l: number) => {
    x = Math.round(x); y = Math.round(y);
    if (x < 0 || y < 0 || x >= cols || y >= rows || (gate < 1 && hash(x, y) > gate)) return;
    const i = y * cols + x; chars[i] = c; layer[i] = l;
  };
  const text = (x: number, y: number, s: string, l: number) => { for (let i = 0; i < s.length; i++) set(Math.round(x) + i, y, s[i], l); };

  const cam = camAt(p);
  const cyaw = Math.cos(cam.yaw), syaw = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
  const project = (v: V3): [number, number, number] => {
    const x = v[0] - cam.t[0], y = v[1] - cam.t[1], z = v[2] - cam.t[2];
    const x1 = x * cyaw - z * syaw, z1 = x * syaw + z * cyaw;
    const y1 = y * cp - z1 * sp, z2 = y * sp + z1 * cp;
    const d = Math.max(0.4, cam.dist - z2), f = 1.25 / d;
    return [cx + x1 * f * scale, cy - y1 * f * scale * cellAspect, d];
  };
  const line = (a: number[], b: number[], l: number) => {
    const dx = b[0] - a[0], dy = b[1] - a[1], n = Math.max(1, Math.ceil(Math.max(Math.abs(dx), Math.abs(dy))));
    // the slope is judged in screen pixels, not cells, because a cell is taller than it is wide
    const sx = Math.abs(dx) * cw, sy = Math.abs(dy) * ch;
    const c = sx > sy * 2.4 ? "-" : sy > sx * 2.4 ? "|" : dx * dy > 0 ? "\\" : "/";
    for (let i = 0; i <= n; i++) set(a[0] + (dx * i) / n, a[1] + (dy * i) / n, c, l);
  };
  /** A rectangle in the page plane, pushed forward by z. `fill` is the interior character ("" = see-through). */
  const quad = (r: Rect, z: number, fill: string, l: number, fl = DIM) => {
    const c = [[r[0], r[1]], [r[0] + r[2], r[1]], [r[0] + r[2], r[1] - r[3]], [r[0], r[1] - r[3]]].map((q) => project([q[0], q[1], z]));
    if (fill) {
      const x0 = Math.max(0, Math.floor(Math.min(...c.map((q) => q[0])))), x1 = Math.min(cols - 1, Math.ceil(Math.max(...c.map((q) => q[0]))));
      const y0 = Math.max(0, Math.floor(Math.min(...c.map((q) => q[1])))), y1 = Math.min(rows - 1, Math.ceil(Math.max(...c.map((q) => q[1]))));
      for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
        let inside = true, sign = 0;
        for (let k = 0; k < 4 && inside; k++) {
          const a = c[k], b = c[(k + 1) % 4];
          const cr = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]);
          if (cr !== 0) { if (sign === 0) sign = Math.sign(cr); else if (Math.sign(cr) !== sign) inside = false; }
        }
        if (inside) set(x, y, fill === "." ? ((x + y * 2) % 3 === 0 ? "." : " ") : fill, fl);
      }
    }
    for (let k = 0; k < 4; k++) line(c[k], c[(k + 1) % 4], l);
    for (const q of c) set(q[0], q[1], "+", l);
    return c;
  };
  /** Text anchored at a point of the page plane. */
  const label = (v: V3, s: string, l: number, dx = 0, dy = 0) => { const q = project(v); text(q[0] + dx, Math.round(q[1]) + dy, s, l); };

  // ---- the page itself, always there, dim
  const fade9 = scene(p, 8).v;                     // the chart scene dims the page
  gate = 1 - fade9 * 0.75;
  for (const [k, r] of Object.entries(P)) quad(r, 0, k === "hero" ? ":" : ".", DIM);
  gate = 1;

  // ---- S1: 23:04, one visitor on the pricing card
  let s = scene(p, 0);
  const cursor = (v: V3, l = LIT) => { const q = project(v); set(q[0], q[1], "@", l); };
  if (s.v > 0) {
    gate = s.v;
    quad(P.c2, 0.02, "", LIT);
    label([P.c2[0] + 0.25, P.c2[1] - 0.45, 0.02], "PRICING", LIT);
    const k = ramp(s.t, 0, 0.45);
    cursor([lerp(-9, 0.6, k), lerp(1.4, -1.1, k), 0.6]);
    text(cols - 22, hud, "23:04", LIT); text(cols - 22, hud + 1, "sales: offline", DIM);
    text(cols - 22, rows - 3, "visitors online  1", MID);
  }
  // ---- S2: three questions, one after another
  s = scene(p, 1);
  if (s.v > 0) {
    gate = s.v;
    const marks: [Rect, string][] = [[P.hero, "[1] ERP?"], [P.c2, "[2] 40 seats?"], [P.side, "[3] our data?"]];
    marks.forEach(([r, m], i) => {
      if (s.t < i * 0.28) return;
      quad(r, 0.02, "", LIT);
      label([r[0] + 0.25, r[1] - 0.45, 0.02], m, LIT);
    });
    cursor([0.6, -1.1, 0.6]);
    text(cols - 22, hud, "23:04", LIT); text(cols - 22, hud + 1, "questions  " + Math.min(3, 1 + Math.floor(s.t / 0.28)) + " of 3", MID);
  }
  // ---- S3: the integration, drawn on the hero panel
  s = scene(p, 2);
  if (s.v > 0) {
    gate = s.v;
    const h0 = P.hero;
    quad(h0, 0.02, " ", LIT, DIM);
    const bx = (i: number): Rect => [h0[0] + 0.55 + i * 1.85, h0[1] - 0.85, 1.25, 0.95];
    ["ERP", "SYNC", "YOU"].forEach((n, i) => {
      if (s.t < 0.1 + i * 0.22) return;
      quad(bx(i), 0.25, " ", LIT, DIM);
      label([bx(i)[0] + 0.3, bx(i)[1] - 0.5, 0.25], n, LIT);
      if (i > 0) { const a = project([bx(i - 1)[0] + 1.25, bx(i)[1] - 0.48, 0.25]), b = project([bx(i)[0], bx(i)[1] - 0.48, 0.25]); line(a, b, LIT); set(b[0] - 1, b[1], ">", LIT); }
    });
    if (s.t > 0.75) label([h0[0] + 0.55, h0[1] - 2.2, 0.02], "orders . stock . invoices", MID);
    text(cols - 28, hud, "source  /docs/integrations", DIM);
  }
  // ---- S4: the price for their team, from the price list
  s = scene(p, 3);
  if (s.v > 0) {
    gate = s.v;
    const r = P.c2;
    quad(r, 0.02, " ", LIT, DIM);
    const k = ramp(s.t, 0.2, 0.8), seats = Math.round(lerp(40, 60, k));
    label([r[0] + 0.25, r[1] - 0.35, 0.02], "PRICING", LIT);
    label([r[0] + 0.25, r[1] - 0.8, 0.02], "seats  " + seats, MID);
    const a = project([r[0] + 0.25, r[1] - 1.1, 0.02]), b = project([r[0] + r[2] - 0.25, r[1] - 1.1, 0.02]);
    line(a, b, MID); set(lerp(a[0], b[0], 0.35 + k * 0.4), a[1], "O", LIT);
    const c0 = project([r[0] + 0.25, r[1] - 1.55, 0.02]), n = Math.round((b[0] - a[0]) * (0.5 + k * 0.4));
    text(c0[0], Math.round(c0[1]), "#".repeat(Math.max(1, n)), LIT);
    label([r[0] + 0.25, r[1] - 1.85, 0.02], "from your price list", DIM);
    text(cols - 18, rows - 3, "example figures", DIM);
  }
  // ---- S5: the security page, opened at the right paragraph
  s = scene(p, 4);
  if (s.v > 0) {
    gate = s.v;
    const r = P.side;
    quad(r, 0.02, " ", LIT, DIM);
    label([r[0] + 0.25, r[1] - 0.35, 0.02], "/security", LIT);
    for (let i = 0; i < 6; i++) {
      const hot = i === 3 || i === 4, on = hot && s.t > 0.35;
      const q = project([r[0] + 0.25, r[1] - 0.8 - i * 0.3, 0.02]), q2 = project([r[0] + r[2] - 0.3, r[1] - 0.8 - i * 0.3, 0.02]);
      const len = Math.max(3, Math.round((q2[0] - q[0]) * (i % 2 ? 0.8 : 1)));
      text(q[0], Math.round(q[1]), (on ? "=" : "~").repeat(len), on ? LIT : DIM);
      if (on) { set(q[0] - 2, q[1], ">", LIT); set(q[0] + len + 1, q[1], "<", LIT); }
    }
    if (s.t > 0.35) text(cols - 22, hud, "your own words", MID);
  }
  // ---- S6: the lead, with a score and what was asked
  s = scene(p, 5);
  if (s.v > 0) {
    gate = s.v;
    const k = ramp(s.t, 0, 0.5), z = lerp(0.05, 1.6, k);
    const r: Rect = [lerp(P.c3[0], 0.9, k), lerp(P.c3[1], 0.6, k), 3.4, 2.1];
    quad(r, z, " ", LIT, DIM);
    label([r[0] + 0.25, r[1] - 0.4, z], "LEAD   78 / 100", LIT);
    if (s.t > 0.3) label([r[0] + 0.25, r[1] - 0.85, z], "asked: ERP sync,", MID);
    if (s.t > 0.4) label([r[0] + 0.25, r[1] - 1.2, z], "60 seats, data", MID);
    if (s.t > 0.6) label([r[0] + 0.25, r[1] - 1.65, z], "-> slack  -> crm", LIT);
    text(cols - 16, rows - 3, "example lead", DIM);
  }
  // ---- S7: a salesperson joins the conversation
  s = scene(p, 6);
  if (s.v > 0) {
    gate = s.v;
    quad(P.c2, 0.02, "", LIT);
    cursor([0.3, -1.4, 0.6]);
    const k = ramp(s.t, 0, 0.5);
    cursor([lerp(8, 1.5, k), lerp(-3.5, -1.4, k), 0.6]);
    if (s.t > 0.5) {
      const c = project([0.9, -1.4, 0.6]), rad = 7 + ((s.t * 6) % 1) * 6;
      for (let a = 0; a < 56; a++) set(c[0] + Math.cos((a / 56) * Math.PI * 2) * rad, c[1] + Math.sin((a / 56) * Math.PI * 2) * rad * cellAspect, "o", MID);
      text(cols - 20, hud, "sales joined", LIT);
    }
  }
  // ---- S8: the summary travels to the rest of the buying team
  s = scene(p, 7);
  if (s.v > 0) {
    gate = s.v;
    quad(P.hero, 0.02, "", LIT);
    const ends: V3[] = [[-4, 3.9, 1.5], [3.8, 3.7, 1.8], [-3.8, -3.6, 1.6], [4, -3.2, 1.5]];
    let opened = 0;
    ends.forEach((e, i) => {
      const k = ramp(s.t, i * 0.16, i * 0.16 + 0.4);
      if (k <= 0) return;
      const m = mid(P.hero), c: V3 = [lerp(m[0], e[0], k), lerp(m[1], e[1], k), lerp(0.05, e[2], k)];
      quad([c[0] - 0.7, c[1] + 0.45, 1.4, 0.9], c[2], " ", LIT, DIM);
      if (k >= 1) { cursor([c[0], c[1] - 0.75, c[2]]); opened++; }
    });
    text(cols - 22, hud, "summary opened  " + opened, opened ? LIT : DIM);
  }
  // ---- S9: one visitor in ten is held back; the gap is the lift
  s = scene(p, 8);
  if (s.v > 0) {
    gate = s.v;
    const x0 = Math.round(cols * (narrow ? 0.08 : 0.46)), x1 = cols - 6, y0 = Math.round(rows * 0.2), y1 = Math.round(rows * (narrow ? 0.5 : 0.78));
    for (let y = y0; y <= y1; y++) set(x0, y, "|", MID);
    text(x0, y1 + 1, "+" + "-".repeat(x1 - x0), MID);
    text(x0 + 2, y0 - 2, "@ @ @ @ @ @ @ @ @ o", LIT); set(x0 + 20, y0 - 2, "o", DIM);
    const n = Math.round((x1 - x0 - 3) * ramp(s.t, 0.05, 0.85)), span = y1 - y0;
    for (let i = 0; i < n; i++) {
      const u = i / (x1 - x0 - 3), x = x0 + 2 + i;
      const base = y1 - 3 - Math.round(span * (0.08 * u + 0.02 * Math.sin(i / 9)));
      const up = y1 - 4 - Math.round(span * (0.62 * u + 0.03 * Math.sin(i / 11)));
      if (i % 2 === 0) set(x, base, ".", MID);
      set(x, up, i % 4 === 0 ? "@" : "-", LIT);
      if (u > 0.3) for (let y = up + 1; y < base; y++) if ((x + y) % 2 === 0) set(x, y, "#", DIM);
    }
    if (s.t > 0.6) { text(x1 - 17, y0 + 1, "with FluidBuddha", LIT); text(x1 - 8, y1 - 1, "without", MID); }
    text(x0 + 2, y1 + 2, "day 1", DIM); text(x1 - 6, y1 + 2, "day 30", DIM); text(x0 + 12, y1 + 2, "example chart", DIM);
  }
  gate = 1;

  // ---- the visitor's light: characters near the pointer brighten, and empty cells catch a little of it
  if (light) {
    const lx = light.x / cw, ly = light.y / ch, rad = narrow ? 7 : 11;
    const x0 = Math.max(0, Math.floor(lx - rad * 1.6)), x1 = Math.min(cols - 1, Math.ceil(lx + rad * 1.6));
    const y0 = Math.max(hud, Math.floor(ly - rad)), y1 = Math.min(rows - 1, Math.ceil(ly + rad));
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
      const d = Math.hypot((x - lx) / 1.6, y - ly) / rad;
      if (d > 1) continue;
      const i = y * cols + x;
      if (chars[i] === " ") { if (d < 0.72 && (x + y * 2) % 3 === 0) { chars[i] = d < 0.3 ? "+" : "."; layer[i] = d < 0.45 ? MID : DIM; } }
      else if (layer[i] < LIT && d < 0.55) layer[i] = layer[i] + 1;
    }
    const cx0 = Math.round(lx), cy0 = Math.round(ly);
    if (cx0 >= 0 && cx0 < cols && cy0 >= hud && cy0 < rows) { chars[cy0 * cols + cx0] = "@"; layer[cy0 * cols + cx0] = LIT; }
  }

  // ---- paint: one fillText per row for each brightness layer; the lit layer glows
  ctx.clearRect(0, 0, w, h);
  ctx.font = `${fs}px ${font}`;
  ctx.textBaseline = "top";
  for (let l = 0; l < 3; l++) {
    ctx.fillStyle = COLORS[l];
    ctx.shadowColor = l === LIT ? GLOW : "transparent";
    ctx.shadowBlur = l === LIT ? fs * 0.7 : 0;
    for (let y = 0; y < rows; y++) {
      let row = "", any = false;
      for (let x = 0; x < cols; x++) { const i = y * cols + x; if (layer[i] === l && chars[i] !== " ") { row += chars[i]; any = true; } else row += " "; }
      if (any) ctx.fillText(row, 0, y * ch);
    }
  }
  ctx.shadowBlur = 0; ctx.shadowColor = "transparent";
}
