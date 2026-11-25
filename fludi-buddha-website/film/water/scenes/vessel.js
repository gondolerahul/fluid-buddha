// 11 · Water takes shape: a clear stream pours into a simple bowl; the camera arcs up and round as
//      the water settles into the bowl's form.
// 12 · The finish: close on the still water; one ripple crosses it, the light it bends paints a
//      clean pattern on the bowl beneath; the camera eases back to the whole, and the name.
//
// The bowl is not a picture: its strokes are fixed to its surface (seeded, in its own coordinates)
// and seen through the camera each frame, so the arc turns the paint with the form, never boils it.
import { KNIFE, DAB, BRUSH } from '../engine/impasto.js';
import { Ref } from '../engine/plate.js';
import { K, P, EL, lin, rad, lerp, clamp, sm, ss, seg, hash, tone, warm, mix3, css, GOLD, GOLD_L, GOLD_XL, GOLD_D, GOLD_DD, WHITE, INK, TAU } from '../lib.js';
import { refOf, paint, upload, drawPlate, flush, dyn, screenCam, FW, FH } from '../stage.js';
import { paintRef } from '../engine/plate.js';

// ---------------------------------------------------------------- the bowl, in its own units (rim radius 1)
const H = .46, RF = .36, TH = .035, FOOT = .05;
/** The outer profile, from the foot (u = 0) to the rim (u = 1): radius and height. */
const prof = (u) => [RF + (1 - RF) * Math.sqrt(1 - (1 - u) * (1 - u)), FOOT + (H - FOOT) * u];
const dprof = (u) => { const e = 1e-3, a = prof(Math.max(0, u - e)), b = prof(Math.min(1, u + e)); return [b[0] - a[0], b[1] - a[1]]; };
/** The inside: a smooth hollow from the centre of its floor (u = 0) up to the rim (u = 1). */
const INNER_Y = FOOT + .06;
const iprof = (u) => [(1 - TH) * Math.sin(u * Math.PI / 2) ** .8, INNER_Y + (H - INNER_Y) * (1 - Math.cos(u * Math.PI / 2)) ** 1.1];
const diprof = (u) => { const e = 1e-3, a = iprof(Math.max(0, u - e)), b = iprof(Math.min(1, u + e)); return [b[0] - a[0], b[1] - a[1]]; };
/** The inside's radius at a height (for the water's edge). */
const innerR = (y) => { let a = 0, b = 1; for (let i = 0; i < 24; i++) { const m = (a + b) / 2; if (iprof(m)[1] < y) a = m; else b = m; } return iprof(a)[0]; };

// strokes on the surface, fixed once: [u, phi, along, across, seed]
const OUT = [], INN = [], FLOOR = [];
(() => {
  let s = 1;
  for (let i = 0; i < 26; i++) for (let j = 0; j < 72; j++) {
    const u = (i + .5 + (hash(s * 1.3) - .5) * .7) / 26, ph = (j + (hash(s * 2.7) - .5) * .8 + (i % 2) * .5) / 72 * TAU;
    OUT.push([u, ph, 1.6 + hash(s * 3.1) * 1.2, 1.25 + hash(s * 5.3) * .5, s]); s++;
    INN.push([Math.min(.995, .12 + .88 * u + (hash(s * 7.1) - .5) * .02), ph + .04, 1.5 + hash(s * 3.9) * 1.1, 1.3 + hash(s * 4.3) * .4, s + 5000]); s++;
  }
  // the floor: the bottom of the hollow, laid in short strokes
  for (let i = 0; i < 700; i++) { const a = hash(i * 1.7) * TAU, r = Math.sqrt(hash(i * 2.9)) * iprof(.16)[0]; FLOOR.push([r * Math.cos(a), r * Math.sin(a), hash(i * 3.3) * Math.PI, i + 9000]); }
  INN.sort((a, b) => Math.sin(a[1]) - Math.sin(b[1]));    // the far side of the inside first
})();

/**
 * The camera: elevation e (radians above the horizontal), azimuth of the light relative to it,
 * the bowl's centre on screen (cx, cy: the centre of its rim), and its scale (px per unit).
 */
const view = (o) => {
  const se = Math.sin(o.e), ce = Math.cos(o.e);
  return {
    ...o, se, ce,
    // a point of the bowl (x right, y up, z towards the viewer) on screen
    P: (x, y, z) => [o.cx + x * o.s, o.cy - (y - H) * ce * o.s + z * se * o.s],
    // towards the camera
    V: [0, se, ce],
  };
};
const LIGHT = (az) => { const l = [-Math.cos(az) * .62, .66, Math.sin(az) * .42 + .2], n = Math.hypot(...l); return l.map((v) => v / n); };
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/** A tone for paper-white glaze under a light: four values, so the form reads as planes. */
function glaze(ndl, sd) {
  const k = ndl > .62 ? .97 : ndl > .32 ? .87 : ndl > .05 ? .72 : .54;
  return warm(k + (hash(sd * 1.9) - .5) * .03, ndl > .62 ? .1 : .04, GOLD_L);
}

function bowlOuter(v, L, front) {
  for (const [u, ph, al, ac, sd] of OUT) {
    const [r, y] = prof(u), [dr, dy] = dprof(u), nl = Math.hypot(dr, dy);
    const cp = Math.cos(ph), sp = Math.sin(ph), N = [dy / nl * cp, -dr / nl, dy / nl * sp];
    const facing = dot(N, v.V);
    if (facing < -.02) continue;
    if (front !== (sp > 0)) continue;
    const [x, yy] = v.P(r * cp, y, r * sp), [x2, y2] = v.P(r * Math.cos(ph + .02), y, r * Math.sin(ph + .02));
    const len = r * TAU / 72 * al * v.s * Math.max(.3, Math.abs(sp) * .4 + .6), wid = .06 * ac * v.s * Math.max(.35, facing);
    const c = glaze(dot(N, L), sd);
    dyn.push({ x, y: yy, ang: Math.atan2(y2 - yy, x2 - x), len, wid, c, c2: mix3(c, tone(.8), .2), type: KNIFE, seed: sd, hgt: 1.2, skew: .3 });
  }
}
function bowlInner(v, L, waterY) {
  floor(v, waterY);
  for (const [u, ph, al, ac, sd] of INN) {
    const [r, y] = iprof(u);
    const [dr, dy] = diprof(u), nl = Math.hypot(dr, dy), cp = Math.cos(ph), sp = Math.sin(ph);
    const N = [-dy / nl * cp, dr / nl, -dy / nl * sp];          // the inner wall faces in
    if (dot(N, v.V) < -.02) continue;
    const [x, yy] = v.P(r * cp, y, r * sp), [x2, y2] = v.P(r * Math.cos(ph + .02), y, r * Math.sin(ph + .02));
    let c = glaze(dot(N, L) * .9, sd);
    if (y < waterY) c = mix3(c, warm(.44, .3, GOLD_L), .66);  // seen through the water: deeper and warmer
    dyn.push({ x, y: yy, ang: Math.atan2(y2 - yy, x2 - x), len: r * TAU / 72 * al * v.s, wid: .055 * ac * v.s * Math.max(.4, v.se + .3), c, c2: mix3(c, tone(.8), .2), type: KNIFE, seed: sd, hgt: 1.1, skew: .3 });
  }
}
/** The floor of the hollow, seen through the water. */
function floor(v, waterY) {
  for (const [fx, fz, a, sd] of FLOOR) {
    const [x, y] = v.P(fx, INNER_Y, fz);
    const c = mix3(glaze(.55, sd), warm(.44, .3, GOLD_L), waterY > INNER_Y + .01 ? .66 : 0);
    dyn.push({ x, y, ang: a, len: .07 * v.s, wid: .045 * v.s * Math.max(.3, v.se), c, type: KNIFE, seed: sd, hgt: 1 });
  }
}
/** The rim: a thin band of gold, lit where it turns to the light. */
function rim(v, L, front) {
  const n = 360;
  for (let i = 0; i < n; i++) {
    const ph = (i + .5) / n * TAU, cp = Math.cos(ph), sp = Math.sin(ph); if (front !== (sp > 0)) continue;
    const [x, y] = v.P(cp * (1 - TH * .5), H + .004, sp * (1 - TH * .5)), [x2, y2] = v.P(Math.cos(ph + .03), H, Math.sin(ph + .03));
    const lit = dot([cp, .3, sp], L);
    dyn.push({ x, y, ang: Math.atan2(y2 - y, x2 - x), len: TAU / n * v.s * 2.6, wid: Math.max(3, .024 * v.s), c: lit > .45 ? GOLD_XL : lit > 0 ? GOLD_L : GOLD_D, c2: GOLD, type: KNIFE, seed: 7000 + i, hgt: 1.5 });
  }
}
/** The water: clear, so it shows as light on it, the line where it meets the wall, and its rings. */
function water(v, L, level, t, ripple, stir = 1, glint = 1) {
  if (level <= .003) return;
  const y = INNER_Y + level, rr = innerR(y) * .99;
  // the meniscus: a bright line where the water meets the wall
  for (let i = 0; i < 140; i++) {
    const ph = (i + .5) / 140 * TAU, [x, yy] = v.P(rr * Math.cos(ph), y, rr * Math.sin(ph)), [x2, y2] = v.P(rr * Math.cos(ph + .03), y, rr * Math.sin(ph + .03));
    dyn.push({ x, y: yy, ang: Math.atan2(y2 - yy, x2 - x), len: rr * TAU / 140 * v.s * 1.8, wid: Math.max(2, .012 * v.s), c: Math.sin(ph) < 0 ? GOLD_XL : WHITE, type: KNIFE, seed: i + 400, hgt: 1.3, alpha: .9 });
  }
  // the reflection of the light: a soft bright patch on the far side
  const [hx, hy] = v.P(-rr * .32, y, -rr * .3);
  if (glint > .02) for (let i = 0; i < 16; i++) { const a = hash(i * 5.1) * TAU, d = Math.sqrt(hash(i * 6.3)); dyn.push({ x: hx + Math.cos(a) * d * rr * .07 * v.s, y: hy + Math.sin(a) * d * rr * .07 * v.s * v.se, ang: (hash(i) - .5) * .3, len: rr * (.03 + hash(i) * .03) * v.s + 3, wid: rr * .02 * v.s + 2, c: hash(i * 4) > .4 ? GOLD_XL : WHITE, type: DAB, seed: i + 500, hgt: 1.4, alpha: glint }); }
  // rings: from where the stream strikes, and the one ripple of the finish
  const rings = [];
  if (stir > 0) for (let k = 0; k < 4; k++) rings.push([((t * .55 + k / 4) % 1) * rr * .9, .5 * stir * (1 - ((t * .55 + k / 4) % 1))]);
  if (ripple) rings.push(ripple);
  for (const [rho, a] of rings) {
    if (rho <= .01 || a <= .02) continue;
    const m = Math.max(24, Math.round(rho * 120));
    for (let i = 0; i < m; i++) {
      const ph = (i + .5) / m * TAU, [x, yy] = v.P(rho * Math.cos(ph), y + .002, rho * Math.sin(ph)), [x2, y2] = v.P(rho * Math.cos(ph + .05), y, rho * Math.sin(ph + .05));
      const lit = Math.sin(ph) < 0;
      dyn.push({ x, y: yy, ang: Math.atan2(y2 - yy, x2 - x), len: rho * TAU / m * v.s * 1.6, wid: Math.max(1.6, .011 * v.s), c: lit ? GOLD_XL : warm(.3, .1), type: KNIFE, seed: i + m * 7, hgt: 1.2, alpha: a });
    }
  }
}
/** The stream that pours in: a narrow column, bright at its edges, glinting. */
function stream(v, level, t, amount) {
  if (amount <= 0) return;
  const y = INNER_Y + level, [, bot] = v.P(0, y, 0), top = -60, w = Math.max(5, .026 * v.s);
  const end = lerp(top, bot, amount);
  for (let i = 0; i < 110; i++) {
    const ph = (hash(i * 1.9) + t * 1.7) % 1, yy = lerp(top, bot, ph); if (yy > end) continue;
    const side = (hash(i * 3.7) - .5) * w, x = v.cx + side + Math.sin(yy / 60 + t * 3) * 1.5;
    dyn.push({ x, y: yy, ang: Math.PI / 2, len: 30 + hash(i * 5.1) * 50, wid: w * (.3 + hash(i * 6.2) * .4), c: Math.abs(side) > w * .25 ? (hash(i) > .5 ? GOLD_XL : WHITE) : tone(.82), c2: tone(.92), type: KNIFE, seed: i + 1200, hgt: 1.3 });
  }
  // the crown where it strikes
  if (amount >= 1) for (let i = 0; i < 18; i++) { const a = -Math.PI * (.1 + .8 * hash(i * 2.3)), ph = (hash(i * 4.1) + t * 2.2) % 1, d = ph * .1 * v.s; dyn.push({ x: v.cx + Math.cos(a) * d * 1.6, y: bot + Math.sin(a) * d - 4, ang: a, len: 8 + hash(i) * 8, wid: 5, c: WHITE, type: DAB, seed: i + 1300, hgt: 1.3, alpha: 1 - ph }); }
}
/**
 * The light the water bends, on the floor of the bowl: a net of bright, wavering lines, the
 * outlines of cells that drift slowly. The ripple, as it passes, gathers the light and sharpens it.
 */
const CELLS = (() => { const c = [], n = 15; for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) { const x = (i + .5 + (hash(i * 7.1 + j * 3.3) - .5) * .7) / n * 2 - 1, z = (j + .5 + (hash(i * 2.9 + j * 5.7) - .5) * .7) / n * 2 - 1; if (x * x + z * z < 1.1) c.push([x, z, i * 31 + j]); } return c; })();
function caustics(v, level, t, ripple, strength) {
  if (strength <= .01) return;
  const R0 = innerR(INNER_Y + level) * .95, cs = R0 / 7.5, y = INNER_Y + .004;
  for (const [cx0, cz0, sd] of CELLS) {
    const cx = cx0 * R0 + Math.sin(t * .35 + sd) * cs * .18, cz = cz0 * R0 + Math.cos(t * .3 + sd * 1.7) * cs * .18;
    if (Math.hypot(cx, cz) > R0 * .97) continue;
    let gain = 1;
    if (ripple) { const d = Math.hypot(cx, cz) - ripple[0] * R0 * 1.1; gain += 1.4 * Math.exp(-d * d / (cs * cs * .8)) * ripple[1]; }
    const m = 20;
    for (let i = 0; i < m; i++) {
      const a0 = (i / m) * TAU, a1 = ((i + 1) / m) * TAU;
      const rr = (k) => cs * (.5 + .12 * Math.sin(k * 3 + sd + t * .6) + .07 * Math.sin(k * 5 - sd * 2 + t * .4));
      const p0 = [cx + Math.cos(a0) * rr(a0), cz + Math.sin(a0) * rr(a0)], p1 = [cx + Math.cos(a1) * rr(a1), cz + Math.sin(a1) * rr(a1)];
      if (Math.hypot(p0[0], p0[1]) > R0) continue;
      const [x0, y0] = v.P(p0[0], y, p0[1]), [x1, y1] = v.P(p1[0], y, p1[1]);
      const w = hash(sd * 7 + i) * .6 + .7;
      dyn.push({ x: (x0 + x1) / 2, y: (y0 + y1) / 2, ang: Math.atan2(y1 - y0, x1 - x0), len: Math.hypot(x1 - x0, y1 - y0) * 1.3, wid: Math.max(1.2, cs * v.s * .04 * w * gain), c: gain > 1.5 ? GOLD_XL : hash(sd + i) > .5 ? GOLD_XL : warm(1, .32, GOLD_L), type: KNIFE, seed: sd * 13 + i, hgt: 1.3, alpha: clamp(strength * (.55 + .35 * gain)) });
    }
  }
}

// ---------------------------------------------------------------- the room, and the name
let room = null, name = null;
function buildRoom() {
  const R = refOf(-300, -300, 1580, 1324);
  R.fill(P([[-300, -300], [1580, -300], [1580, 1324], [-300, 1324]]), rad(640, 560, 60, 900, [[0, K(.15, .32, GOLD_D)], [.35, K(.09, .16)], [.7, K(.05, .05)], [1, K(.03, .01)]]), { dir: { radial: [640, 560], off: 90 }, group: 'room', maxR: 40, aj: .5, detail: 1.3 });
  room = paint(R, { seed: 101, R: [40, 20, 10], T: 5 });
  // the name, laid in with the knife: the brand's face, in its gold
  const N = refOf(240, 860, 1040, 990);
  N.text('FluidBuddha', 640, 960, '400 96px "Roblox"', lin(340, 0, 940, 0, [[0, css(GOLD_L)], [.34, css(GOLD)], [.74, css(warm(1, .4, GOLD_XL))], [1, css(GOLD_L)]]), { group: 'name', maxR: 4, aj: .25, dir: 'edge', hgt: 1.5, track: '1px' });
  name = paint(N, { seed: 102, R: [6, 3.2, 1.8], T: 6 });
}

/**
 * t0: the stream starts; fill: the water has reached its level; arc: the camera's rise and turn;
 * close: the push onto the water; rip: the ripple; back: the ease back; nameAt: the name is laid in.
 */
export function drawVessel(t, T, tr = {}) {
  if (!room) buildRoom();
  const camAt = (tt) => {
    const a = sm(seg(tt, T.vessel, T.close)), c = sm(seg(tt, T.close, T.close + 2.2)), b = sm(seg(tt, T.back, T.back + 3));
    const e = lerp(lerp(.2, .6, a), 1.12, c) * (1 - b) + .74 * b;
    const s = lerp(lerp(300, 330, a), 1450, Math.pow(c, 1.3)) * (1 - b) + 300 * b;
    const cy = lerp(lerp(590, 560, a), 520 + 260, c) * (1 - b) + 600 * b;
    return view({ e, s, cx: 640 + lerp(0, -40, c) * (1 - b), cy, az: lerp(.3, -.25, a) + .3 * c });
  };
  const v = camAt(t), L = LIGHT(v.az);
  drawPlate(room, { hx: 640, hy: 512, x: 640 + (v.cx - 640) * .1, y: 512 + (v.cy - 590) * .1, z: 0, zoom: 1 }, { p: 1 }, { t, ...tr });
  // the bowl's soft shadow on the dark ground
  const [sx, sy] = v.P(0, 0, 0);
  for (let i = 0; i < 14; i++) dyn.push({ x: sx + 40 + (hash(i) - .5) * 60, y: sy + 8 + (hash(i * 2) - .5) * 10, ang: 0, len: v.s * 1.3, wid: v.s * .22 * Math.max(.3, v.se), c: tone(.02), type: BRUSH, seed: i + 50, hgt: .3, alpha: .25 });
  const level = .3 * ss(seg(t, T.vessel + .8, T.full));
  const ripple = t > T.rip ? [seg(t, T.rip, T.rip + 3.4) * .7, 1 - ss(seg(t, T.rip + 2.4, T.rip + 3.6))] : null;
  const pour = t < T.full + .6 ? sm(seg(t, T.vessel, T.vessel + .9)) : 1 - sm(seg(t, T.full + .6, T.full + 1.2));
  bowlOuter(v, L, false);                        // the back of the outside never shows over the inside, but its edge does
  bowlInner(v, L, INNER_Y + level);
  caustics(v, level, t, ripple, ss(seg(t, T.close - .4, T.close + 1.6)) * (1 - ss(seg(t, T.back + 1, T.back + 2.6))) * (level > .05 ? 1 : 0));
  water(v, L, level, t, ripple, 1 - ss(seg(t, T.full + .6, T.full + 2.6)), 1 - ss(seg(t, T.close, T.close + 1)) + ss(seg(t, T.back + .5, T.back + 2)));
  rim(v, L, false);
  bowlOuter(v, L, true);
  rim(v, L, true);
  stream(v, level, t, pour > 0 && t < T.full + 1.2 ? (t < T.full ? pour : 1) : 0);
  flush(null, {}, { t, cam: screenCam(), run: .15, ...tr });
  if (t > T.nameAt) drawPlate(name, null, {}, { t, cam: screenCam(), appear: T.nameAt, appDur: .25, sweep: { dir: [1.1, 0], off: -.2, baked: .3 }, noUnder: true });
}
export const vesselInfo = () => (room ? room.n + name.n : 0);
