// The avalanche: snow pours off the ridge and becomes the glacier.
// 5 · Glacier: a slow sideways dolly along the ice. Light travels through it like a quiet pulse,
// and at the end the camera finds meltwater in a fissure.
import { KNIFE, DAB, BRUSH } from '../engine/impasto.js';
import { K, P, lin, lerp, clamp, sm, ss, seg, hash, tone, warm, GOLD, GOLD_L, GOLD_XL, WHITE, TAU, mix3 } from '../lib.js';
import { refOf, paint, drawPlate, relight, flush, dyn, screenCam } from '../stage.js';
import { mulberry } from '../lib.js';
import { terrain, fbm, ridged, vnoise } from '../terrain.js';

const HOME = [640, 512], HZ = 250;
const CAM = { eye: [0, 2500, 0], f: 1150, cx: 640, horizon: HZ };
const SUN = [-.66, .5, .35];               // morning, from the left and ahead
let L = null;

/** The glacier: a river of ice in a valley. Its centre line wanders as it comes towards us. */
const centre = (z) => 900 * Math.sin(z / 6200 + .5) + 380 * Math.sin(z / 2300 + 1.3);
const half = (z) => 1150 + 260 * Math.sin(z / 5200);
/** Arcs across the ice, bowed downstream (towards us): the glacier's banding. */
const arcs = (x, z) => { const u = x - centre(z); return (z + .00042 * u * u) / 520; };
/** Cracks where the ice is stretched: across the flow in the icefall, slanting at the margins. */
function crevasse(x, z) {
  const u = Math.abs(x - centre(z)) / half(z), a = arcs(x, z) * 2.6 + .4 * fbm(x / 900, z / 900, 2, 4);
  const f = a - Math.floor(a), d = Math.abs(f - .5);
  const zone = clamp((u - .62) * 4) + clamp(1 - Math.abs(z - 10500) / 1800);
  return clamp(zone) * Math.pow(clamp(1 - d / (.05 + .04 * vnoise(x / 300, z / 300, 3))), .7) * (u < 1 ? 1 : 0);
}
/** The two dark stripes of rock carried on the ice. */
const moraine = (x, z) => { const u = (x - centre(z)) / half(z), brk = clamp((fbm(x / 500, z / 500, 2, 9) - .36) * 4); return brk * Math.max(clamp(1 - Math.abs(u + .3 + .04 * Math.sin(z / 900)) / .03), .7 * clamp(1 - Math.abs(u - .4 - .05 * Math.sin(z / 700)) / .022)); };
export const FISSURE_Z = 4300;
function hf(x, z) {
  const c = centre(z), w = half(z), d = Math.abs(x - c);
  let h = 60 * fbm(x / 800, z / 800, 3, 2) - 70 * crevasse(x, z) + 22 * moraine(x, z) - z * .02 - .00004 * d * d;
  if (d > w) h += Math.min(d - w, 5200) * .5 * (.6 + .75 * ridged(x / 1900, z / 1900, 5, 13)) + 380 * ridged(x / 700, z / 700, 3, 17) * clamp((d - w) / 500);
  // the crack the meltwater runs in, across the near ice
  const fz = FISSURE_Z + 140 * Math.sin(x / 400);
  h -= 120 * Math.pow(clamp(1 - Math.abs(z - fz) / 28), .5) * clamp((w - d) / 200);
  return h;
}
function shade(s) {
  const c = centre(s.Z), w = half(s.Z), d = Math.abs(s.X - c), lit = !s.shadow && s.ndl > .28;
  if (d > w + 30) {                                         // the valley's walls: snow where it can lie, rock where it cannot
    if (s.ny > .7 - .12 * fbm(s.X / 900, s.Z / 900, 2, 5)) return { v: lit ? (s.ndl > .6 ? .97 : .86) : .62, g: lit ? .16 : .03, mat: 's', flow: 'fall' };
    return { v: lit ? .48 : .24, g: lit ? .08 : .02, mat: 'r', flow: 'fall' };
  }
  const cv = crevasse(s.X, s.Z), fz = FISSURE_Z + 140 * Math.sin(s.X / 400);
  if ((cv > .35 || Math.abs(s.Z - fz) < 22) && s.h < 40 - s.Z * .02) return lit ? { v: .72, g: .62, mat: 'c', flow: 'fall' } : { v: .34, g: .52, mat: 'c', flow: 'fall' };   // the light inside the ice
  if (moraine(s.X, s.Z) > .35) return { v: lit ? .56 : .4, g: .06, mat: 'm', flow: 'z' };
  const a = arcs(s.X, s.Z), band = a - Math.floor(a) < .42;
  if (lit && s.ndl > .55) return { v: band ? .9 : .98, g: .1, mat: 'i', flow: 'z' };
  if (lit) return { v: band ? .8 : .88, g: .06, mat: 'i', flow: 'z' };
  return { v: band ? .58 : .66, g: .04, mat: 'i', flow: 'z' };
}
const layer = (ref, near, far, o) => terrain(ref, {
  name: o.name, hf, ...CAM, near, far, light: SUN, shade, gold: GOLD_L, levels: 12, glevels: 6, skirt: 1e5, step: .004, eps: 8, minStep: 2,
  fog: { v: .86, g: .18, from: 6000, to: 50000, amt: .75 },
  props: (mat) => ({ maxR: o.maxR * (mat === 'c' ? .45 : mat === 'r' ? .8 : 1), hgt: mat === 'c' ? .8 : mat === 'r' ? 1.3 : 1.12, jit: .04, detail: 1.15, aj: .16, len: mat === 'i' ? 1.9 : 1.4, wid: .82 }),
});
/** A point of the ground seen from the camera, in scene units. */
const proj = (X, h, Z) => [CAM.cx + CAM.f * X / Z, HZ + CAM.f * (CAM.eye[1] - h) / Z];

function build() {
  const sky = refOf(-600, -400, 2000, 520);
  sky.fill(P([[-600, -400], [2000, -400], [2000, 520], [-600, 520]]), lin(0, -400, 0, HZ, [[0, K(.62, .03)], [.6, K(.8, .1)], [1, K(.94, .28, GOLD_L)]]), { dir: -3, group: 'sky', maxR: 30, aj: .2, len: 1.8 });
  const far = refOf(-700, -100, 2100, 640); layer(far, 12000, 120000, { name: 'f', maxR: 14 });
  const mid = refOf(-900, 120, 2300, 1000, .9); layer(mid, 5600, 12500, { name: 'm', maxR: 24 });
  const near = refOf(-1200, 300, 2600, 1800, .6); layer(near, 2000, 6000, { name: 'n', maxR: 44 });
  L = [
    { pl: paint(sky, { seed: 41, R: [30, 15, 8], T: 10 }), p: .03 },
    { pl: paint(far, { seed: 42, R: [14, 7, 3.5], T: 9 }), p: .12 },
    { pl: paint(mid, { seed: 43, R: [24, 12, 6, 3], T: 9 }), p: .4 },
    { pl: paint(near, { seed: 44, R: [44, 22, 11, 5.5, 2.8], T: 9 }), p: 1 },
  ];
}

// ------------------------------------------------------------------ the avalanche
/** Snow pours off the ridge (from `src`, on screen) and spreads until it fills the frame. */
export function avalanche(t, t0, { src = [930, 300], tr = {} } = {}) {
  const a = t - t0; if (a < 0) return;
  for (let i = 0; i < 2600; i++) {
    const e = hash(i * 1.7) * 1.6, age = a - e; if (age <= 0 || age > 3.2) continue;
    const ang = 1.95 + (hash(i * 3.1) - .5) * .9, sp = 380 + hash(i * 5.3) * 520;
    const turb = Math.sin(age * 3 + i) * 40 * age;
    const x = src[0] + Math.cos(ang) * sp * age - age * age * 60 + turb, y = src[1] + Math.sin(ang) * sp * age * .8 + age * age * 120;
    const r = (6 + hash(i * 7.7) * 12) * (1 + age * 1.1);
    const k = lerp(.86, 1, hash(i * 2.3));
    const vx = Math.cos(ang) * sp - age * 120, vy = Math.sin(ang) * sp * .8 + age * 240;
    dyn.push({ x, y, ang: Math.atan2(vy, vx) + (hash(i) - .5) * .5, len: r * (2.2 + hash(i * 9.1) * 1.6), wid: r * .8, c: tone(k), c2: tone(k - .1), type: i % 5 ? KNIFE : BRUSH, seed: i * 7, hgt: 1.15, skew: .5, alpha: clamp(1 - (age - 2.4) / .8) });
  }
  flush(null, {}, { t, cam: screenCam(), run: .4, ...tr });
}

/** The pulse of light, at `phase` 0..1 across the ice: brightens and warms the ice strokes it passes. */
function pulse(pl, phase, strength = 1) {
  // it runs down the glacier, towards us: a band across the ice that moves down the frame
  const py = lerp(150, 1900, phase);
  relight(pl, (x, y, i) => {
    const d = (y - py + (x - 640) * .12) / 170, k = Math.exp(-d * d) * strength;
    if (k < .03) return null;
    return { k: k * .85, c: hash(i * .37) > .45 ? GOLD_XL : warm(1, .26, GOLD_L) };
  });
}

/** Meltwater runs along the bottom of the crack in the near ice, catching the light. */
function meltwater(t, amount) {
  for (let i = 0; i < 260; i++) {
    const u = (hash(i * 4.1) + t * (.05 + hash(i) * .03)) % 1; if (u > amount) continue;
    const c = centre(FISSURE_Z), w = half(FISSURE_Z), X = c - w * .9 + u * w * 1.8, Z = FISSURE_Z + 140 * Math.sin(X / 400);
    const [x, y] = proj(X, -40 - Z * .02, Z), [x2, y2] = proj(X + 30, -40 - Z * .02, FISSURE_Z + 140 * Math.sin((X + 30) / 400));
    dyn.push({ x: x + (hash(i * 2) - .5) * 4, y: y + (hash(i * 3) - .5) * 3, ang: Math.atan2(y2 - y, x2 - x), len: 14 + hash(i * 5) * 20, wid: 2.5 + hash(i * 6) * 3, c: hash(i * 8) > .55 ? GOLD_XL : WHITE, c2: tone(.86), type: KNIFE, seed: i, hgt: 1.35 });
  }
}
export const FISSURE_AT = proj(centre(FISSURE_Z) + 200, -100, FISSURE_Z + 140 * Math.sin((centre(FISSURE_Z) + 200) / 400));

/** t from the shot's start: the dolly runs `dur` seconds; the pulse crosses at `pulseAt`; the meltwater shows from `melt`. */
export function drawGlacier(t, { t0, dur, pulseAt = [.1, .62], melt = .55, tr = {} } = {}) {
  if (!L) build();
  const k = seg(t, t0, t0 + dur), c = sm(k), push = sm(seg(k, melt + .08, 1));
  const view = { hx: HOME[0], hy: HOME[1], x: lerp(420, 840, c) + (FISSURE_AT[0] - 840) * .7 * push, y: 512 + (FISSURE_AT[1] - 512) * .75 * push, z: .04 * c + .62 * Math.pow(push, 1.5), zoom: 1 };
  L.forEach((l, j) => {
    const cam = drawPlate(l.pl, view, { p: l.p, home: HOME }, { t, ...tr });
    if (j >= 2) {
      const ph = seg(k, pulseAt[0], pulseAt[1]);
      if (ph > 0 && ph < 1) { pulse(l.pl, ph, Math.sin(ph * Math.PI)); flush(null, {}, { t, cam, run: .3, ...tr }); }
    }
    if (j === 3) { meltwater(t, ss(seg(k, melt - .08, melt + .2))); flush(null, {}, { t, cam, run: .2, ...tr }); }
  });
  return view;
}
export const glacierInfo = () => (L ? L.reduce((n, l) => n + l.pl.n, 0) : 0);
