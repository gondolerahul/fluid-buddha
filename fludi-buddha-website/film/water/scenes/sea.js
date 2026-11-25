// 9 · Sea: the spray clears on open water. The camera glides low towards the horizon, over dark
//     water with a path of gold where the sun is.
// 10 · Underwater: without a cut, the camera slips below the surface: shafts of light, drifting
//     motes, slow currents.
import { KNIFE, DAB, BRUSH } from '../engine/impasto.js';
import { K, P, EL, lin, rad, lerp, clamp, sm, ss, seg, hash, tone, warm, mulberry, GOLD, GOLD_L, GOLD_XL, WHITE, TAU } from '../lib.js';
import { refOf, paint, drawPlate, flush, dyn, screenCam, E, RS, FW, FH } from '../stage.js';
import { terrain, fbm, vnoise } from '../terrain.js';

const HOME = [640, 512], HZ = 360;
const CAM = { eye: [0, 46, 0], f: 1150, cx: 640, horizon: HZ };
const SUN_X = 760;                       // where the sun stands over the horizon, in the frame
let L = null, U = null;

/** Waves: long swells from ahead, chop across them. */
function hf(x, z) {
  return 3.2 * Math.sin(z / 46 + 1.3 * Math.sin(x / 300)) + 1.6 * Math.sin((x * .6 + z) / 21) + 2.4 * (fbm(x / 70, z / 34, 3, 11) - .5) + 1 * Math.sin((z - x * .8) / 12);
}
/**
 * Water is a mirror: each facet shows the sky it faces. Facets that send the sun to the eye
 * glitter gold; the faces of swells towards us mirror the dark sky overhead and read as ink.
 */
function shade(s) {
  const dx = s.X - CAM.eye[0], dy = s.h - CAM.eye[1], dz = s.Z, dl = Math.hypot(dx, dy, dz);
  const vx = dx / dl, vy = dy / dl, vz = dz / dl;
  const dn = vx * s.nx + vy * s.ny + vz * s.nz, rx = vx - 2 * dn * s.nx, ry = vy - 2 * dn * s.ny, rz = vz - 2 * dn * s.nz;
  // the sun, low and ahead
  const sx = (SUN_X - CAM.cx) / CAM.f, sun = [sx, .12, 1], sl = Math.hypot(...sun);
  const toSun = (rx * sun[0] + ry * sun[1] + rz * sun[2]) / sl;
  const sky = clamp(1 - ry * 2.2);                                  // bright near the horizon, darker overhead
  if (toSun > .994) return { v: .98, g: .6, mat: 'g', flow: 'x' };
  if (toSun > .982) return { v: .74, g: .4, mat: 'h', flow: 'x' };
  return { v: lerp(.1, .56, Math.pow(sky, 2.2)), g: lerp(.02, .12, sky), mat: 'w', flow: 'x' };
}
const layer = (ref, near, far, o) => terrain(ref, {
  name: o.name, hf, ...CAM, near, far, light: [0, 1, 0], shade, gold: GOLD_L, levels: 14, glevels: 7, skirt: 1e5, step: .004, eps: 2, minStep: .4, shadowSteps: 0,
  fog: { v: .72, g: .22, from: 3000, to: 30000, amt: .6 },
  props: (mat) => ({ maxR: o.maxR * (mat === 'g' ? .5 : 1), hgt: mat === 'g' ? 1.4 : .9, jit: .04, detail: 1.1, aj: .1, len: 2.4, wid: .62 }),
});

function buildSea() {
  const sky = refOf(-500, -500, 1800, 420);
  sky.fill(P([[-500, -500], [1800, -500], [1800, 420], [-500, 420]]), lin(0, -500, 0, HZ, [[0, K(.3, .03)], [.5, K(.5, .1)], [.82, K(.8, .3, GOLD_L)], [1, K(.94, .44, GOLD_L)]]), { dir: -2, group: 'sky', maxR: 30, aj: .14, len: 2 });
  sky.fill(EL(SUN_X, HZ - 54, 70, 60), rad(SUN_X, HZ - 54, 4, 70, [[0, K(1, .1, GOLD_XL)], [.6, K(.98, .4, GOLD_L)], [1, K(.92, .44, GOLD_L)]]), { dir: { radial: [SUN_X, HZ - 54] }, group: 'sun', maxR: 10, aj: .2, hgt: 1.5 });
  const far = refOf(-700, 300, 2000, 620); layer(far, 1400, 60000, { name: 'f', maxR: 12 });
  const near = refOf(-1000, 330, 2300, 1500, .7); layer(near, 50, 1500, { name: 'n', maxR: 30 });
  L = [{ pl: paint(sky, { seed: 91, R: [30, 15, 7.5, 3.8], T: 9 }), p: .02 }, { pl: paint(far, { seed: 92, R: [12, 6, 3], T: 8 }), p: .2 }, { pl: paint(near, { seed: 93, R: [30, 15, 7.5, 3.8, 2.2], T: 8 }), p: 1 }];
}

function buildUnder() {
  // below the surface: light from above, falling off into ink
  const R = refOf(-400, -600, 1700, 1500);
  R.fill(P([[-400, -600], [1700, -600], [1700, 1500], [-400, 1500]]), lin(0, -200, 0, 1400, [[0, K(.7, .4, GOLD_L)], [.16, K(.42, .22)], [.4, K(.2, .08)], [.7, K(.09, .03)], [1, K(.04, .01)]]), { dir: { radial: [SUN_X, -900] }, group: 'deep', maxR: 40, aj: .5, len: 1.5, detail: 1.4 });
  // the underside of the surface: bright, broken into cells by the waves
  for (let i = 0; i < 90; i++) { const x = -400 + hash(i * 3.1) * 2100, y = -600 + hash(i * 5.3) * 380, w = 60 + hash(i) * 160; R.fill(EL(x, y, w, w * .3, (hash(i * 7) - .5) * .4), K(.9, .5, GOLD_L), { dir: 0, group: 'cell' + i, maxR: 10, aj: .2, hgt: 1.2 }); }
  U = paint(R, { seed: 95, R: [40, 20, 10, 5], T: 7 });
}

/** The glide towards the horizon: t0 .. t0 + dur. */
export function drawSea(t, { t0, dur, sink = 0, tr = {} } = {}) {
  if (!L) buildSea();
  const k = seg(t, t0, t0 + dur);
  // as the camera sinks to the surface, the horizon climbs the frame
  const view = { hx: HOME[0], hy: HOME[1], x: 640 + 30 * sm(k), y: 512, z: .5 * sm(k), zoom: 1, ty: -560 * Math.pow(sink, 1.6) };
  L.forEach((l, j) => {
    const cam = drawPlate(l.pl, view, { p: l.p, home: HOME }, { t, ...tr });
    if (j === 2) {
      // the glitter moves; the swells under it stay
      for (let i = 0; i < 360; i++) {
        const z = lerp(60, 1500, Math.pow(hash(i * 2.3), 1.6)), xs = SUN_X + (hash(i * 5.1) - .5) * (60 + 900 * 60 / z) * .5;
        const tw = Math.sin(t * (3 + hash(i) * 4) + i), y = HZ + CAM.f * CAM.eye[1] / z + Math.sin(t * 1.3 + i) * 2;
        if (tw < .2) continue;
        dyn.push({ x: xs, y, ang: (hash(i * 9) - .5) * .2, len: (10 + hash(i * 4) * 30) * 300 / z, wid: (2 + hash(i * 6) * 3) * 200 / z + 1.2, c: hash(i * 3) > .4 ? GOLD_XL : WHITE, type: KNIFE, seed: i, hgt: 1.3, alpha: tw });
      }
      flush(null, {}, { t, cam, run: .2, ...tr });
    }
  });
}

/** Under the surface: shafts of light that sway, motes and bubbles that drift. */
export function drawUnder(t, { t0, dur, tr = {} } = {}) {
  if (!U) buildUnder();
  const k = seg(t, t0, t0 + dur);
  const view = { hx: HOME[0], hy: HOME[1], x: 640, y: lerp(260, 620, sm(k)), z: 0, zoom: 1 };
  const cam = drawPlate(U, view, { p: 1, home: HOME }, { t, ...tr });
  // the shafts: long, thin, faint, fanning down from the surface
  for (let i = 0; i < 26; i++) {
    const x0 = SUN_X - 620 + hash(i * 1.9) * 1240 + Math.sin(t * .3 + i * 2) * 24, a = Math.atan2(2400, x0 - SUN_X) + Math.sin(t * .4 + i) * .015;   // all from the sun, high above
    const len = 900 + hash(i * 6.3) * 900, w = 18 + hash(i * 2.2) * 50;
    dyn.push({ x: x0 + Math.cos(a) * len * .5, y: -560 + Math.sin(a) * len * .5, ang: a, len, wid: w, c: warm(.95, .5, GOLD_L), c2: warm(.8, .3), type: BRUSH, seed: i, hgt: .35, alpha: .16 + .1 * hash(i * 8), taper: .5 });
  }
  flush(null, {}, { t, cam, run: 1, ...tr });
  // motes: tiny, slow, everywhere; droplets of air rising
  for (let i = 0; i < 260; i++) {
    const x = -300 + hash(i * 1.3) * 1900 + Math.sin(t * .5 + i) * 20 + t * 6 * (hash(i * 2) - .3), y = -500 + ((hash(i * 7.7) * 1900 - t * (6 + hash(i) * 10)) % 1900 + 1900) % 1900;
    const r = 2 + hash(i * 4.4) * 4, dk = clamp(1 - (y + 300) / 1600);
    dyn.push({ x, y, ang: 0, len: r * 1.4, wid: r, c: warm(lerp(.4, .95, dk), .3), type: DAB, seed: i, hgt: 1, alpha: .7 });
  }
  for (let i = 0; i < 40; i++) {
    const x = 300 + hash(i * 9.1) * 800 + Math.sin(t * 2 + i) * 10, y = 1300 - ((hash(i * 3.9) * 1900 + t * (90 + hash(i) * 80)) % 1900);
    const r = 5 + hash(i * 5.5) * 12;
    dyn.push({ x, y, ang: 0, len: r * 1.9, wid: r * 1.9, c: warm(.3, .1), type: DAB, seed: i + 500, hgt: .6, alpha: .8 });
    dyn.push({ x: x - r * .3, y: y - r * .35, ang: -.5, len: r * .8, wid: r * .5, c: GOLD_XL, type: DAB, seed: i + 700, hgt: 1.4 });
  }
  flush(null, {}, { t, cam, run: .2, ...tr });
}

/**
 * The slip below: the waterline climbs the frame (wl, in frame units, from the bottom to the top).
 * Under it the water; over it the sea and sky. A bright line of dabs is the surface seen edge on.
 */
export function slip(t, wl, drawAbove, drawBelow) {
  drawBelow();
  if (wl > 0) {
    E.clip([0, 0, FW * RS, Math.max(0, wl) * RS]);
    drawAbove();
    E.clip(null);
    for (let i = 0; i < 110; i++) {
      const x = -30 + i * 12.5 + Math.sin(t * 3 + i) * 4, y = wl + Math.sin(i * .7 + t * 4) * 5;
      dyn.push({ x, y, ang: (hash(i) - .5) * .3, len: 24 + hash(i * 3) * 30, wid: 5 + hash(i * 5) * 7, c: hash(i * 7) > .5 ? GOLD_XL : WHITE, c2: tone(.86), type: KNIFE, seed: i, hgt: 1.4 });
    }
    flush(null, {}, { t, cam: screenCam(), run: .2 });
  }
}
export const seaInfo = () => (L ? L.reduce((n, l) => n + l.pl.n, 0) : 0) + (U ? U.n : 0);
