/**
 * The Enterprise world's film: flat technical line drawings, drawn live from the scroll position.
 *
 * `renderLineFilm(ctx, w, h, p, opt)` draws the frame for progress p (0 to 1). There is a still
 * drawing behind the hero and then nine scenes. Each scene moves once, during the first part of its
 * stretch of the film, and then holds still until the next scene replaces it.
 *
 * Everything is drawn in a 480 x 280 design space that is scaled to fit beside the copy (wide
 * screens) or above it (upright screens). Colours come from the page, so the drawing follows the theme.
 */

export type LineFilmOpt = { font: string; top: number; fg: string; accent: string };

const HERO_END = 0.07;
const N = 9;
const STEP = (1 - HERO_END) / N;
/** The stretch of the film each scene is on screen. Chapters in content/worlds/enterprise.ts sit inside these. */
export const LINE_SCENES: [number, number][] = Array.from({ length: N }, (_, i) => [HERO_END + i * STEP, HERO_END + (i + 1) * STEP]);

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = (t: number) => t * t * (3 - 2 * t);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
/** 0 before a, 1 after b, eased in between. */
const sub = (t: number, a: number, b: number) => ease(clamp((t - a) / (b - a)));

type Pt = [number, number];
// the seven panels of "your website", 200 x 130
const PAN: [number, number, number, number][] = [
  [0, 0, 200, 10], [0, 16, 124, 52], [130, 16, 70, 52], [0, 74, 62, 40], [69, 74, 62, 40], [138, 74, 62, 40], [0, 119, 46, 10],
];
const BOUND: [number, number, number, number] = [120, 46, 250, 186]; // "your network"

export function renderLineFilm(g: CanvasRenderingContext2D, w: number, h: number, p: number, opt: LineFilmOpt) {
  const upright = w < h * 0.8;
  // where the drawing sits: right of the copy on wide screens, above it on upright ones
  const ax = upright ? w * 0.03 : w * 0.42, aw = upright ? w * 0.94 : w * 0.56;
  const ay = opt.top + h * 0.03, ah = (upright ? h * 0.5 : h * 0.94) - ay;
  const k = Math.min(aw / 480, ah / 280);
  const ox = ax + (aw - 480 * k) / 2, oy = ay + (ah - 280 * k) / 2;

  g.setTransform(1, 0, 0, 1, 0, 0);
  g.clearRect(0, 0, w, h);
  g.setTransform(k, 0, 0, k, ox, oy);
  g.lineCap = "round"; g.lineJoin = "round";
  g.textBaseline = "alphabetic";

  let fade = 1; // visibility of the scene being drawn
  const pen = (color: string, width: number, alpha = 1, dash?: number[]) => {
    g.strokeStyle = color; g.fillStyle = color; g.lineWidth = width; g.globalAlpha = alpha * fade; g.setLineDash(dash ?? []);
  };
  const ink = (alpha = 1) => pen(opt.fg, 1.45, alpha);
  const soft = () => pen(opt.fg, 1.1, 0.36);
  const gold = (alpha = 1) => pen(opt.accent, 2.4, alpha);
  const dashed = (alpha = 1) => pen(opt.fg, 1.4, alpha, [5, 5]);

  // drafting paper under the drawing: the one place on the page where a grid belongs
  g.save();
  g.globalAlpha = 0.07; g.strokeStyle = opt.fg; g.lineWidth = 0.6; g.setLineDash([]);
  g.beginPath();
  for (let x = 0; x <= 480; x += 20) { g.moveTo(x, 0); g.lineTo(x, 280); }
  for (let y = 0; y <= 280; y += 20) { g.moveTo(0, y); g.lineTo(480, y); }
  g.stroke();
  g.globalAlpha = 0.12; g.lineWidth = 0.8;
  g.beginPath();
  for (let x = 0; x <= 480; x += 100) { g.moveTo(x, 0); g.lineTo(x, 280); }
  for (let y = 0; y <= 280; y += 100) { g.moveTo(0, y); g.lineTo(480, y); }
  g.stroke();
  g.restore();

  /** Strokes the first part `t` (0 to 1) of a line through the points. */
  const path = (pts: Pt[], t = 1, close = false) => {
    if (t <= 0) return;
    const P = close ? [...pts, pts[0]] : pts;
    const L = P.slice(1).map((q, i) => Math.hypot(q[0] - P[i][0], q[1] - P[i][1]));
    let rem = L.reduce((a, b) => a + b, 0) * Math.min(1, t);
    g.beginPath(); g.moveTo(P[0][0], P[0][1]);
    for (let i = 0; i < L.length && rem > 0; i++) {
      const f = Math.min(1, rem / (L[i] || 1));
      g.lineTo(lerp(P[i][0], P[i + 1][0], f), lerp(P[i][1], P[i + 1][1], f));
      rem -= L[i];
    }
    g.stroke();
  };
  const rect = (x: number, y: number, rw: number, rh: number, t = 1) => path([[x, y], [x + rw, y], [x + rw, y + rh], [x, y + rh]], t, true);
  const fill = (x: number, y: number, rw: number, rh: number) => g.fillRect(x, y, rw, rh);
  const tick = (x: number, y: number, t = 1) => { gold(); path([[x, y], [x + 5, y + 5], [x + 14, y - 5]], t); };
  const cross = (x: number, y: number, s: number, t = 1) => { path([[x, y], [x + s, y + s]], sub(t, 0, 0.5)); path([[x + s, y], [x, y + s]], sub(t, 0.5, 1)); };
  const arrow = (x: number, y: number) => path([[x - 8, y - 5], [x, y], [x - 8, y + 5]]);
  const label = (s: string, x: number, y: number, alpha = 1, color = opt.fg) => {
    if (alpha <= 0) return;
    g.setLineDash([]); g.globalAlpha = alpha * fade; g.fillStyle = color;
    // upright screens scale the drawing down, so the labels are set larger there to stay readable
    g.font = `500 ${upright ? 11.5 : 10}px ${opt.font}`;
    (g as CanvasRenderingContext2D & { letterSpacing?: string }).letterSpacing = upright ? "0.4px" : "1.1px";
    g.fillText(s.toUpperCase(), x, y);
  };
  const panels = (x: number, y: number, alpha = 1) => { ink(alpha); for (const [px, py, pw, ph] of PAN) rect(x + px, y + py, pw, ph); };
  /** The website inside the network boundary: the picture the first three scenes share. */
  const network = (boundary = 1) => {
    panels(145, 72);
    dashed(); rect(...BOUND, boundary);
    label("Your network", 120, 38, sub(boundary, 0.1, 0.4));
  };
  const plugs = (t: number) => {
    ([["Model", 82], ["Sign-in", 172]] as [string, number][]).forEach(([name, y], i) => {
      const u = sub(t, i * 0.3, i * 0.3 + 0.55);
      ink(); rect(14, y, 70, 26); label(name, 22, y + 16);
      ink(); path([[84, y + 13], [120, y + 13]], u);
      if (u >= 1) { gold(); g.beginPath(); g.arc(120, y + 13, 3.5, 0, Math.PI * 2); g.fill(); }
    });
  };

  const scenes: ((t: number) => void)[] = [
    // R1 where it runs: the boundary draws itself around the site
    (t) => { network(sub(t, 0, 0.85)); tick(352, 59, sub(t, 0.85, 1)); },
    // R2 your contracts: two plugs connect at the boundary
    (t) => { network(); tick(352, 59); plugs(t); label("Your contracts", 14, 70, sub(t, 0.1, 0.4)); },
    // R3 what still leaves: one thin line crosses the boundary, and is labelled
    (t) => {
      network(); plugs(1);
      gold(); path([[330, 180], [404, 180]], sub(t, 0, 0.6));
      ink(sub(t, 0.5, 0.8)); rect(404, 166, 70, 28);
      label("Vertex AI", 411, 183, sub(t, 0.6, 0.9));
      label("Speech and", 386, 148, sub(t, 0.7, 1)); label("indexing leave", 386, 159, sub(t, 0.7, 1));
    },
    // R4 approved parts: an admin stamps some blocks; only those move to the workbench
    (t) => {
      const ok = [0, 2, 3, 5, 6];
      label("Library", 36, 84); label("Approved for the AI", 290, 76, sub(t, 0.4, 0.6));
      dashed(sub(t, 0.4, 0.6)); rect(290, 84, 150, 100);
      // the admin
      ink(); g.beginPath(); g.arc(242, 118, 6, 0, Math.PI * 2); g.stroke(); path([[230, 142], [232, 131], [242, 127], [252, 131], [254, 142]]); label("Admin", 226, 158);
      for (let i = 0; i < 8; i++) {
        const x0 = 36 + (i % 4) * 40, y0 = 96 + Math.floor(i / 4) * 44, kI = ok.indexOf(i);
        if (kI < 0) { ink(lerp(1, 0.3, sub(t, 0.3, 0.6))); rect(x0, y0, 30, 30); continue; }
        const m = sub(t, 0.5 + kI * 0.06, 0.78 + kI * 0.06);
        const x = lerp(x0, 300 + (kI % 3) * 44, m), y = lerp(y0, 94 + Math.floor(kI / 3) * 44, m);
        ink(); rect(x, y, 30, 30);
        tick(x + 8, y + 16, sub(t, kI * 0.09, kI * 0.09 + 0.12));
      }
    },
    // R5 one check: blocks pass through a gate one by one; one is turned away
    (t) => {
      label("Check", 232, 70); ink(); path([[236, 80], [236, 190]]); path([[262, 80], [262, 190]]); path([[228, 80], [270, 80]]);
      soft(); path([[190, 129], [222, 129]]); ink(); arrow(222, 129);
      let passed = 0;
      for (let j = 0; j < 4; j++) {
        const u = sub(t, j * 0.2, j * 0.2 + 0.36), x0 = 20 + j * 40;
        if (j === 2) { // turned away at the gate
          const a = sub(u, 0, 0.55), b = sub(u, 0.55, 1);
          const x = lerp(x0, 232, a), y = lerp(112, 206, b);
          ink(lerp(1, 0.35, b)); rect(x, y, 34, 34);
          if (b > 0) { ink(0.35); cross(x + 9, y + 9, 16, b); }
          label("Left out", 276, 227, b * 0.5);
          continue;
        }
        const x = lerp(x0, 308 + passed * 44, u);
        ink(); rect(x, 112, 34, 34);
        tick(x + 10, 129, sub(u, 0.9, 1));
        passed++;
      }
    },
    // R6 your numbers: a line from your systems fills the price field; the AI is not connected
    (t) => {
      ink(); rect(36, 92, 120, 70); label("Your systems", 52, 131);
      ink(); rect(300, 56, 144, 150);
      soft(); path([[316, 78], [400, 78]]); path([[316, 92], [376, 92]]); path([[316, 162], [428, 162]]); path([[316, 176], [410, 176]]); path([[316, 190], [390, 190]]);
      gold(); path([[156, 127], [300, 127]], sub(t, 0, 0.5));
      gold(); rect(316, 112, 112, 30, sub(t, 0.45, 0.72)); label("₹ price", 326, 131, sub(t, 0.6, 0.8));
      ink(0.4); rect(76, 204, 40, 30); label("AI", 88, 223, 0.5);
      dashed(0.4); path([[116, 219], [250, 219]], sub(t, 0.6, 0.85));
      ink(); cross(246, 213, 12, sub(t, 0.85, 1));
    },
    // R7 off limits: three routes are fenced off; a notice locks to the top of every page
    (t) => {
      label("Never touched", 36, 50);
      ["Checkout", "Legal", "Privacy"].forEach((name, i) => {
        const y = 62 + i * 58, u = sub(t, i * 0.14, i * 0.14 + 0.3);
        ink(lerp(1, 0.45, u)); rect(42, y + 6, 104, 30); label(name, 52, y + 25, lerp(1, 0.5, u));
        dashed(); rect(34, y - 2, 120, 46, u);
        ink(); cross(160, y + 15, 12, sub(t, i * 0.14 + 0.25, i * 0.14 + 0.4));
      });
      ink(); rect(290, 50, 150, 186);
      soft(); for (let i = 0; i < 6; i++) path([[302, 100 + i * 20], [302 + [120, 96, 110, 80, 118, 70][i], 100 + i * 20]]);
      const m = sub(t, 0.5, 0.85);
      gold(m); g.globalAlpha = 0.16 * m * fade; fill(298, lerp(22, 58, m), 134, 20);
      gold(m); rect(298, lerp(22, 58, m), 134, 20);
      label("Required notice", 304, lerp(22, 58, m) + 13, m);
      tick(444, 68, sub(t, 0.85, 1));
    },
    // R8 the record: a list builds line by line; a few lines are flagged for review
    (t) => {
      label("Audit log", 40, 42); ink(); rect(40, 50, 250, 190);
      label("Review queue", 330, 88, sub(t, 0.2, 0.4)); ink(sub(t, 0.2, 0.4)); rect(330, 96, 120, 78);
      const flagged = [2, 6, 8];
      for (let i = 0; i < 10; i++) {
        const y = 67 + i * 17, u = sub(t, i * 0.07, i * 0.07 + 0.1);
        ink(0.5); path([[52, y], [78, y]], u);
        soft(); path([[90, y], [90 + [150, 120, 164, 100, 140, 156, 126, 148, 110, 160][i], y]], u);
        const f = flagged.indexOf(i);
        if (f >= 0) {
          const v = sub(t, i * 0.07 + 0.1, i * 0.07 + 0.3);
          gold(u); fill(270, y - 4, 8, 8);
          gold(); path([[278, y], [310, y], [310, 135], [330, 135]], v);
          if (v >= 1) { ink(); rect(342 + f * 34, 112, 24, 32); soft(); path([[347 + f * 34, 122], [361 + f * 34, 122]]); path([[347 + f * 34, 130], [357 + f * 34, 130]]); }
        }
      }
    },
    // R9 start small: one panel is highlighted; a 90-day bar fills
    (t) => {
      panels(140, 36);
      const u = sub(t, 0, 0.3);
      gold(u); g.globalAlpha = 0.16 * u * fade; fill(209, 110, 62, 40);
      gold(); rect(209, 110, 62, 40, u);
      label("One product area", 352, 133, sub(t, 0.2, 0.4)); soft(); path([[271, 130], [346, 130]], sub(t, 0.15, 0.35));
      const b = sub(t, 0.25, 1);
      ink(); rect(100, 214, 280, 10);
      gold(); g.globalAlpha = fade; fill(100, 214, 280 * b, 10);
      [0, 30, 60, 90].forEach((d, i) => { ink(0.5); path([[100 + (280 * i) / 3, 228], [100 + (280 * i) / 3, 234]]); label(i === 0 ? "Day 0" : i === 3 ? "Day 90" : String(d), 100 + (280 * i) / 3 - (i === 3 ? 34 : i === 0 ? 0 : 6), 247, 0.6); });
      label("Measured pilot", 100, 204, sub(t, 0.3, 0.5));
    },
  ];

  // the still drawing behind the hero: the site inside your network, a visitor arriving, speech leaving
  const heroV = 1 - sub(p, HERO_END - 0.012, HERO_END + 0.004);
  if (heroV > 0) {
    fade = heroV;
    network(); tick(352, 59);
    soft(); path([[20, 139], [112, 139]]); ink(); arrow(112, 139); label("Visitor", 20, 130, 0.5);
    soft(); path([[370, 180], [452, 180]]); label("Speech", 386, 172, 0.5); label("leaves", 386, 196, 0.5);
  }
  LINE_SCENES.forEach(([a, b], i) => {
    const v = Math.min(sub(p, a - 0.004, a + 0.012), i === N - 1 ? 1 : 1 - sub(p, b - 0.012, b + 0.004));
    if (v <= 0) return;
    fade = v;
    // the scene moves once, over the first 55 % of its stretch, then holds
    scenes[i](clamp((p - a - (b - a) * 0.06) / ((b - a) * 0.55)));
  });
  g.globalAlpha = 1; g.setLineDash([]);
  g.setTransform(1, 0, 0, 1, 0, 0);
}
