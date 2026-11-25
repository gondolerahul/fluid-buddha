// 6 · Stream: a low tracking shot along clear water winding between stones.
// 7 · River: a drone pulls back to show its path through the land, then comes down to skim it,
//     towards the edge where it falls.
import { KNIFE, DAB } from '../engine/impasto.js';
import { K, P, lin, lerp, clamp, sm, ss, seg, hash, tone, warm, GOLD_L, GOLD_XL, WHITE } from '../lib.js';
import { refOf, paint, drawPlate, flush, dyn } from '../stage.js';
import { terrain, fbm, ridged, vnoise } from '../terrain.js';

const HOME = [640, 512];
const ih = (x, y, s) => { let h = Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(s, 1442695041) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
/** Round stones on a grid of cells: each cell may hold one, of its own size. Height at a point. */
function stones(x, z, size, s, fill = .8) {
  const gx = Math.floor(x / size), gz = Math.floor(z / size);
  let h = 0;
  for (let j = -1; j <= 1; j++) for (let i = -1; i <= 1; i++) {
    const cx = gx + i, cz = gz + j; if (ih(cx, cz, s) > fill) continue;
    const r = size * (.28 + .4 * ih(cx, cz, s + 1)), px = (cx + .2 + .6 * ih(cx, cz, s + 2)) * size, pz = (cz + .2 + .6 * ih(cx, cz, s + 3)) * size;
    const q = ((x - px) ** 2 + (z - pz) ** 2) / (r * r);
    if (q < 1) h = Math.max(h, r * .62 * Math.sqrt(1 - q));
  }
  return h;
}
/** The water mirrors what stands above it: follow the reflected ray until it meets the ground or the sky. */
function reflector(hf, cam, solid, sky) {
  return (s) => {
    const dx = s.X - cam.eye[0], dy = s.h - cam.eye[1], dz = s.Z - cam.eye[2], dl = Math.hypot(dx, dy, dz);
    const rx = dx / dl, ry = -dy / dl, rz = dz / dl;
    let d = 3;
    for (let i = 0; i < 70; i++) {
      const X = s.X + rx * d, Y = s.h + ry * d, Z = s.Z + rz * d, H = hf(X, Z);
      if (H > Y) return solid(X, Z, H);
      d *= 1.09; if (Y > cam.eye[1] * 4 + 400) break;
    }
    return typeof sky === 'function' ? sky(ry) : sky;
  };
}

// ================================================================== the stream
const S_CAM = { eye: [0, 95, 0], f: 1150, cx: 640, horizon: 300 };
const S_SUN = [-.8, .5, .22];               // ahead and to the left: the water carries its light towards us
const sX = (z) => (190 * Math.sin(z / 700) + 60 * Math.sin(z / 250)) * clamp((z - 60) / 500);
const sW = (z) => 46 + 12 * Math.sin(z / 400);
function sHf(x, z) {
  const d = Math.abs(x - sX(z)) - sW(z);
  const bank = d > 0 ? Math.min(d * .22, 60 + d * .05) : -26 + d * -.05;
  const st = stones(x, z, 64, 3, d > 0 ? .7 : .4) * .8 + stones(x, z, 26, 9, .7) * .7;
  const hills = z > 4000 ? Math.min(900, Math.pow((z - 4000) / 3000, 1.2) * 260) * (.6 + .8 * fbm(x / 2600, z / 2600, 3, 5)) : 0;
  return Math.max(bank + st * (d > 18 ? 1 : .8) + 8 * fbm(x / 60, z / 60, 2, 2), hills);
}
const sWater = (x, z) => Math.abs(x - sX(z)) < sW(z) + 6 && sHf(x, z) < 0;
function stoneShade(X, Z, H, s) {
  const lit = !s.shadow && s.ndl > .3, n = vnoise(X / 40, Z / 40, 7);
  if (Z > 4200 && H > 60) return { v: lit ? .74 : .56, g: lit ? .18 : .08, mat: 'h', flow: 'contour' };      // far hills
  if (lit && s.ndl > .6) return { v: .94 - n * .05, g: .22, mat: 'sl', flow: 'contour' };
  if (lit) return { v: .74 - n * .06, g: .12, mat: 'sm', flow: 'contour' };
  return { v: .5 + n * .08, g: .07, mat: 'sd', flow: 'contour' };
}
const sReflect = reflector(sHf, S_CAM, (X, Z, H) => ({ v: .4 + .1 * vnoise(X / 50, Z / 50, 2), g: .06 }), (ry) => { const k = Math.pow(clamp(1 - ry * 2.5), 1.4); return { v: lerp(.5, .96, k), g: lerp(.1, .38, k) }; });
function sShade(s) {
  if (sWater(s.X, s.Z)) {
    const r = sReflect({ ...s, h: 0 }), dz = 30, tx = sX(s.Z + dz) - sX(s.Z);
    return { v: Math.min(.98, r.v * .8 + .2 + (vnoise(s.X / 30, s.Z / 90, 5) - .5) * .12), g: r.g, mat: 'w', flow: [tx / dz, 1] };
  }
  return stoneShade(s.X, s.Z, s.h, s);
}
const sLayer = (ref, near, far, o) => terrain(ref, {
  name: o.name, hf: (x, z) => sWater(x, z) ? 0 : sHf(x, z), ...S_CAM, near, far, light: S_SUN, shade: sShade, gold: GOLD_L, levels: 13, glevels: 6, skirt: 1e5, step: .004, eps: 2, minStep: .5,
  fog: { v: .86, g: .2, from: 1500, to: 14000, amt: .7 },
  props: (mat) => ({ maxR: o.maxR * (mat === 'w' ? 1 : .8), hgt: mat === 'w' ? .8 : 1.25, jit: .05, detail: 1.15, aj: mat === 'w' ? .1 : .3, len: mat === 'w' ? 2.2 : 1.4, wid: mat === 'w' ? .7 : .9 }),
});
let SL = null;
function buildStream() {
  const sky = refOf(-500, -300, 1800, 420);
  sky.fill(P([[-500, -300], [1800, -300], [1800, 420], [-500, 420]]), lin(0, -300, 0, 300, [[0, K(.7, .06)], [1, K(.95, .34, GOLD_L)]]), { dir: -3, group: 'sky', maxR: 26, aj: .2, len: 1.8 });
  const far = refOf(-600, -100, 1900, 560); sLayer(far, 1800, 20000, { name: 'f', maxR: 14 });
  const mid = refOf(-800, 200, 2100, 900, .9); sLayer(mid, 520, 1900, { name: 'm', maxR: 26 });
  const near = refOf(-1100, 300, 2400, 1700, .6); sLayer(near, 90, 560, { name: 'n', maxR: 46 });
  SL = [
    { pl: paint(sky, { seed: 51, R: [26, 13, 6.5], T: 10 }), p: .03 },
    { pl: paint(far, { seed: 52, R: [14, 7, 3.5], T: 9 }), p: .15 },
    { pl: paint(mid, { seed: 53, R: [26, 13, 6.5, 3.2], T: 9 }), p: .45 },
    { pl: paint(near, { seed: 54, R: [46, 23, 11.5, 5.8, 2.9], T: 9 }), p: 1 },
  ];
}
const sProj = (X, h, Z) => [S_CAM.cx + S_CAM.f * X / Z, S_CAM.horizon + S_CAM.f * (S_CAM.eye[1] - h) / Z];
/** Light on the moving water: glints that run down the stream towards us. */
function streamGlints(t, z0, z1, n = 340) {
  for (let i = 0; i < n; i++) {
    const u = (hash(i * 3.3) + t * (.09 + hash(i) * .05)) % 1, Z = lerp(z1, z0, u), X = sX(Z) + (hash(i * 7.1) - .5) * 1.7 * sW(Z);
    if (sHf(X, Z) > 0) continue;
    const [x, y] = sProj(X, 1, Z), [x2, y2] = sProj(sX(Z - 30) + (X - sX(Z)), 1, Z - 30), sc = 260 / Z;
    const bright = hash(i * 9.3) > .55;
    dyn.push({ x, y, ang: Math.atan2(y2 - y, x2 - x), len: (9 + hash(i * 5) * 16) * sc, wid: (4 + hash(i * 6) * 5) * sc, c: bright ? GOLD_XL : WHITE, c2: tone(.92), type: hash(i * 2.7) > .5 ? DAB : KNIFE, seed: i, hgt: 1.3, alpha: .85 });
  }
}
export function drawStream(t, { t0, dur, tr = {} } = {}) {
  if (!SL) buildStream();
  const k = seg(t, t0, t0 + dur), c = sm(k);
  // the camera follows the water: forward, swaying gently with its bends
  const view = { hx: HOME[0], hy: HOME[1], x: 640 + 40 * Math.sin(k * 3), y: 512 - 30 * c, z: .42 * c, zoom: 1 };
  SL.forEach((l, j) => {
    const cam = drawPlate(l.pl, view, { p: l.p, home: HOME }, { t, ...tr });
    if (j === 2) { streamGlints(t, 520, 1900, 320); flush(null, {}, { t, cam, run: .2, ...tr }); }
    if (j === 3) { streamGlints(t, 100, 560, 360); flush(null, {}, { t, cam, run: .2, ...tr }); }
  });
}

// ================================================================== the river, from above, and skimming it to the edge
const R_CAM = { eye: [0, 3600, 0], f: 1150, cx: 640, horizon: 90 };
const R_SUN = [-.55, .62, .45];
const rX = (z) => 1300 * Math.sin(z / 5200 + .3) + 760 * Math.sin(z / 1500 + 2) - 200;
const rW = (z) => 190 + 50 * Math.sin(z / 3000);
/** The land the river has cut: rolling, with woods, and the river in its valley. */
function rHf(x, z) {
  const d = Math.abs(x - rX(z));
  const land = 520 * fbm(x / 3800, z / 3800, 4, 31) + 260 * ridged(x / 1500, z / 1500, 3, 33);
  const valley = Math.min(1, Math.max(0, (d - rW(z)) / 1600));
  return d < rW(z) ? -12 : 10 + land * Math.pow(valley, .8) + 30 * (1 - valley);
}
const wood = (x, z) => fbm(x / 700, z / 700, 3, 41) > .56;
function rShade(s) {
  if (s.h < 0) {
    // the river: the sky in it, and the sun's glitter where the slope of the water sends it to us
    const g = vnoise(s.X / 140, s.Z / 40, 6);
    return { v: .86 + g * .1, g: .2 + g * .3, mat: 'w', flow: [(rX(s.Z + 50) - rX(s.Z)) / 50, 1] };
  }
  const lit = !s.shadow && s.ndl > .32;
  if (s.h < 40 && Math.abs(s.X - rX(s.Z)) < rW(s.Z) + 70) return { v: .8, g: .12, mat: 'b', flow: 'contour' };   // the pale gravel of its banks
  if (wood(s.X, s.Z) && s.h > 30) return { v: lit ? .34 : .17, g: lit ? .08 : .02, mat: 'f', flow: 'contour' };
  return { v: lit ? (s.ndl > .7 ? .82 : .66) : .46, g: lit ? .12 : .04, mat: 'l', flow: 'fall' };
}
const rLayer = (ref, near, far, o) => terrain(ref, {
  name: o.name, hf: rHf, ...R_CAM, near, far, light: R_SUN, shade: rShade, gold: GOLD_L, levels: 12, glevels: 6, skirt: 1e5, step: .004, eps: 12, minStep: 3,
  fog: { v: .88, g: .24, from: 9000, to: 60000, amt: .8 },
  props: (mat) => ({ maxR: o.maxR * (mat === 'f' ? .7 : 1), hgt: mat === 'f' ? 1.4 : mat === 'w' ? .8 : 1.05, jit: .05, detail: 1.15, aj: mat === 'w' ? .1 : .3, len: mat === 'w' ? 2 : 1.3, wid: .85, type: mat === 'f' ? DAB : KNIFE }),
});
// the skim: low over the water, the river running straight away to an edge where the land drops
const K_CAM = { eye: [0, 70, 0], f: 1150, cx: 640, horizon: 400 };
export const EDGE_Z = 3000;
const kX = (z) => 60 * Math.sin(z / 900);
function kHf(x, z) {
  if (z > EDGE_Z + 20 * Math.sin(x / 300)) return z > 14000 ? -2600 + Math.pow((z - 14000) / 6000, 1.2) * 1400 * (.5 + fbm(x / 4000, z / 4000, 3, 7)) : -3000;   // beyond the edge, far below: the land the water falls to
  const d = Math.abs(x - kX(z)) - 420;
  return d < 0 ? 0 : Math.min(d * .35, 180) + stones(x, z, 140, 61, .6) + 40 * fbm(x / 300, z / 300, 2, 3);
}
const kReflect = reflector(kHf, K_CAM, (X, Z, H) => ({ v: .3, g: .05 }), (ry) => { const k = Math.pow(clamp(1 - ry * 6), 1.8); return { v: lerp(.3, .92, k), g: lerp(.06, .36, k) }; });
const K_SUN = (() => { const d = [.12, .07, 1], l = Math.hypot(...d); return d.map((v) => v / l); })();
function kShade(s) {
  if (s.h < -1000) return { v: .74 + .08 * fbm(s.X / 3000, s.Z / 3000, 2, 2), g: .22, mat: 'v', flow: 'contour', fog: 1 };
  if (s.h <= 0) {
    // the surface is never still: small ripples tilt it, and where a ripple sends the sun to the eye it glitters
    const e = 2, rp = (x, z) => 1.4 * Math.sin(z / 9 + 2 * Math.sin(x / 40)) + 2 * (vnoise(x / 16, z / 7, 9) - .5);
    const hx = (rp(s.X + e, s.Z) - rp(s.X - e, s.Z)) / (2 * e) * .3, hz = (rp(s.X, s.Z + e) - rp(s.X, s.Z - e)) / (2 * e) * .3;
    const nl = Math.hypot(hx, 1, hz), nx = -hx / nl, ny = 1 / nl, nz = -hz / nl;
    const dx = s.X, dy = -K_CAM.eye[1], dz = s.Z, dl = Math.hypot(dx, dy, dz), vx = dx / dl, vy = dy / dl, vz = dz / dl;
    const dn = vx * nx + vy * ny + vz * nz, rx = vx - 2 * dn * nx, ry = vy - 2 * dn * ny, rz = vz - 2 * dn * nz;
    const sun = rx * K_SUN[0] + ry * K_SUN[1] + rz * K_SUN[2];
    if (sun > .992) return { v: .98, g: .6, mat: 'g', flow: 'x' };
    if (sun > .975) return { v: .78, g: .42, mat: 'h', flow: 'x' };
    const r = kReflect(s);
    return { v: r.v * .85 - .04 + (vnoise(s.X / 50, s.Z / 160, 5) - .5) * .1, g: r.g, mat: 'w', flow: 'x' };
  }
  return stoneShade(s.X, s.Z, s.h, s);
}
const kLayer = (ref, near, far, o) => terrain(ref, {
  name: o.name, hf: kHf, ...K_CAM, near, far, light: R_SUN, shade: kShade, gold: GOLD_L, levels: 13, glevels: 6, skirt: 1e5, step: .004, eps: 3, minStep: .5,
  fog: { v: .88, g: .26, from: 2500, to: 40000, amt: .85 },
  props: (mat) => ({ maxR: o.maxR, hgt: mat === 'w' ? .8 : 1.2, jit: .05, detail: 1.15, aj: mat === 'w' ? .08 : .3, len: mat === 'w' ? 2.3 : 1.4, wid: mat === 'w' ? .7 : .9 }),
});
let RL = null, KL = null;
function buildRiver() {
  const sky = refOf(-600, -500, 1900, 300);
  sky.fill(P([[-600, -500], [1900, -500], [1900, 300], [-600, 300]]), lin(0, -500, 0, 90, [[0, K(.72, .08)], [1, K(.95, .3, GOLD_L)]]), { dir: -3, group: 'sky', maxR: 26, aj: .2, len: 1.8 });
  const far = refOf(-800, 0, 2100, 600); rLayer(far, 9000, 90000, { name: 'f', maxR: 12 });
  const near = refOf(-1400, 120, 2700, 1900, .8); rLayer(near, 3000, 9600, { name: 'n', maxR: 30 });
  RL = [{ pl: paint(sky, { seed: 61, R: [26, 13, 6.5], T: 10 }), p: .02 }, { pl: paint(far, { seed: 62, R: [12, 6, 3], T: 9 }), p: .2 }, { pl: paint(near, { seed: 63, R: [30, 15, 7.5, 3.8], T: 9 }), p: 1 }];
}
function buildSkim() {
  const sky = refOf(-600, -400, 1900, 520);
  sky.fill(P([[-600, -400], [1900, -400], [1900, 520], [-600, 520]]), lin(0, -400, 0, 420, [[0, K(.7, .06)], [.7, K(.88, .2)], [1, K(.96, .36, GOLD_L)]]), { dir: -3, group: 'sky', maxR: 26, aj: .2, len: 1.8 });
  const far = refOf(-700, 300, 2000, 700); kLayer(far, EDGE_Z - 300, 90000, { name: 'f', maxR: 14 });
  const near = refOf(-1100, 380, 2400, 1700, .6); kLayer(near, 60, EDGE_Z, { name: 'n', maxR: 40 });
  KL = [{ pl: paint(sky, { seed: 71, R: [26, 13, 6.5], T: 10 }), p: .03 }, { pl: paint(far, { seed: 72, R: [14, 7, 3.5], T: 9 }), p: .3 }, { pl: paint(near, { seed: 73, R: [40, 20, 10, 5, 2.6], T: 9 }), p: 1 }];
}
const rProj = (X, h, Z) => [R_CAM.cx + R_CAM.f * X / Z, R_CAM.horizon + R_CAM.f * (R_CAM.eye[1] - h) / Z];
const kProj = (X, h, Z) => [K_CAM.cx + K_CAM.f * X / Z, K_CAM.horizon + K_CAM.f * (K_CAM.eye[1] - h) / Z];

/** From above: the drone rises and pulls back while the river runs. */
export function drawRiver(t, { t0, dur, tr = {} } = {}) {
  if (!RL) buildRiver();
  const k = sm(seg(t, t0, t0 + dur));
  const view = { hx: HOME[0], hy: HOME[1], x: lerp(rProj(rX(4200), 0, 4200)[0], 700, k), y: lerp(760, 560, k), z: lerp(.55, 0, k), zoom: 1 };
  RL.forEach((l, j) => {
    const cam = drawPlate(l.pl, view, { p: l.p, home: HOME }, { t, ...tr });
    if (j === 2) {
      for (let i = 0; i < 420; i++) {
        const u = (hash(i * 3.3) + t * (.03 + hash(i) * .02)) % 1, Z = lerp(9000, 3200, u), X = rX(Z) + (hash(i * 7.1) - .5) * 1.6 * rW(Z);
        const [x, y] = rProj(X, 0, Z), [x2, y2] = rProj(rX(Z - 80) + (X - rX(Z)), 0, Z - 80), sc = 4500 / Z;
        dyn.push({ x, y, ang: Math.atan2(y2 - y, x2 - x), len: (10 + hash(i * 5) * 16) * sc, wid: (2 + hash(i * 6) * 2.5) * sc, c: hash(i * 9.3) > .5 ? GOLD_XL : WHITE, type: KNIFE, seed: i, hgt: 1.2, alpha: .9 });
      }
      flush(null, {}, { t, cam, run: .2, ...tr });
    }
  });
}
/** Low over the water, gliding towards the edge. */
export function drawSkim(t, { t0, dur, tr = {} } = {}) {
  if (!KL) buildSkim();
  const k = seg(t, t0, t0 + dur);
  const view = { hx: HOME[0], hy: HOME[1], x: 640, y: lerp(512, 470, sm(k)), z: .62 * Math.pow(k, 1.4), zoom: 1 };
  KL.forEach((l, j) => {
    const cam = drawPlate(l.pl, view, { p: l.p, home: HOME }, { t, ...tr });
    if (j === 2) {
      // the glitter on the path of the sun, sliding towards the edge with the water
      for (let i = 0; i < 300; i++) {
        const u = (hash(i * 3.3) + t * (.1 + hash(i) * .05)) % 1, Z = lerp(80, EDGE_Z, Math.pow(u, 1.6)), X = Z * K_SUN[0] / K_SUN[2] + (hash(i * 7.1) - .5) * (30 + Z * .08);
        const tw = Math.sin(t * (4 + hash(i) * 5) + i); if (tw < .3) continue;
        const [x, y] = kProj(X, 1, Z), sc = 160 / Z;
        dyn.push({ x, y, ang: (hash(i * 4) - .5) * .2, len: (14 + hash(i * 5) * 26) * sc * 3 + 2, wid: (3 + hash(i * 6) * 3) * sc * 1.6 + 1, c: hash(i * 9.3) > .4 ? GOLD_XL : WHITE, type: KNIFE, seed: i, hgt: 1.3, alpha: tw });
      }
      flush(null, {}, { t, cam, run: .2, ...tr });
    }
  });
}
export const riverInfo = () => [SL, RL, KL].reduce((n, L) => n + (L ? L.reduce((m, l) => m + l.pl.n, 0) : 0), 0);
