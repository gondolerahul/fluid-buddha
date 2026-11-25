// 1 · Clouds at dawn. A sea of cloud seen from above, still in shadow; the first light, low on the
// left, catches only the crowns and the two towers. Five layers, far to near; the camera glides
// forward, then flies down into the cloud.
import { K, P, EL, lin, lerp, mulberry, css, warm, GOLD_L, GOLD_XL, sm, seg, clamp } from '../lib.js';
import { refOf, paint, drawPlate } from '../stage.js';
import { terrain, vnoise, fbm } from '../terrain.js';

const HOME = [640, 512], HZ = 452;
const CAM = { eye: [0, 330, 0], f: 1100, cx: 640, horizon: HZ };
const SUN = [-.74, .5, .2];                       // towards the light: from the left, above the cloud
export const CLOUD_END = { x: 560, y: 930 };     // the point in the near cloud the camera flies into
let L = null;

// two towers of cumulus stand out of the deck: the first things the light finds. Each is a few
// domes grown together, [dx, dz, radius, height].
const TOWERS = [
  { x: 900, z: 4300, seed: 31, lobes: [[0, 0, 300, 900], [-250, 60, 230, 600], [230, -20, 220, 650], [30, -200, 200, 470], [-90, 190, 190, 390], [-430, 120, 190, 300], [410, 60, 180, 330], [140, 230, 170, 250]] },
  { x: -1560, z: 7900, seed: 47, lobes: [[0, 0, 360, 700], [330, 60, 280, 450], [-300, -40, 250, 380], [80, 260, 220, 300]] },
];
/** Rounded tops with creases between them, in three sizes: the surface of a cloud. 0..1. */
function puffs(x, z, s) {
  const b1 = Math.pow(Math.abs(2 * vnoise(x, z, s) - 1), .6);
  const b2 = Math.pow(Math.abs(2 * vnoise(x * 2.3 + 5.2, z * 2.3 + 1.3, s + 9) - 1), .7);
  const b3 = Math.abs(2 * vnoise(x * 5.1 + 2.2, z * 5.1 + 8.1, s + 17) - 1);
  return b1 * .62 + b2 * .27 * (.4 + .6 * b1) + b3 * .11 * b1;
}
/** How much of a tower stands at a point: 0 outside, towards 1 at its heart. Sets `towerTop`. */
let towerTop = 0;
function towerAt(x, z) {
  let body = 0; towerTop = 0;
  for (const T of TOWERS) {
    const dx = x - T.x, dz = z - T.z;
    if (dx * dx + dz * dz > 640000) continue;
    for (const [lx, lz, r, hh] of T.lobes) { const q = ((dx - lx) * (dx - lx) + (dz - lz) * (dz - lz)) / (r * r); if (q < 1) { const e = Math.pow(1 - q, .5); towerTop = Math.max(towerTop, hh * e + 64 * puffs(x / 230, z / 230, T.seed) * Math.min(1, e * 2.2) + 14 * puffs(x / 90, z / 90, T.seed + 3) * Math.min(1, e * 2)); body = Math.max(body, e); } }
  }
  return body;
}
/** The top of the cloud: a carpet of pillows on a slow swell, and the towers. */
function deck(x, z) {
  const h = 96 * puffs(x / 340, z / 340, 11) + 70 * puffs(x / 960, z / 960, 23) + 90 * fbm(x / 2600, z / 2600, 2, 5);
  return towerAt(x, z) > 0 ? Math.max(h, 40 + towerTop) : h;
}
/**
 * Light on cloud, as five close values. Cloud scatters light, so the light wraps round each form
 * and no shadow is dark: the lit crown (warm), two half-lights, shade, and the creases. A tower
 * is denser, so its far side is deeper. The cloud nearest the eye is still in the night.
 */
function cloudShade(s) {
  const side = clamp(.62 - (s.sx - 300) / 1500);          // the side of the sun is warmer
  const tw = towerAt(s.X, s.Z) > .02 && s.h > 300;
  const nearer = lerp(.72, 1, clamp((s.zc - 300) / 1700)), away = clamp((s.zc - 600) / 5000);   // the cloud nearest the eye is still in the night
  let m = (s.nl + .3) / 1.3;
  if (s.shadow) m *= tw ? .6 : .72;
  if (m > .8) return { v: .97 * nearer, g: (.07 + .12 * away) + (.08 + .2 * away) * side, mat: 'l', flow: 'contour' };
  if (m > .6) return { v: (tw ? .86 : .9) * nearer, g: .03 + .09 * side * away, mat: 'h', flow: 'contour' };
  if (m > .44) return { v: (tw ? .66 : .78) * nearer, g: .03, mat: 'g', flow: 'contour' };
  if (m > .28) return { v: (tw ? .48 : .64) * nearer, g: .01, mat: 's', flow: 'contour' };
  return { v: (tw ? .36 : .5) * nearer, g: .01, mat: 'd', flow: 'contour' };
}
const layer = (ref, near, far, o) => terrain(ref, {
  name: o.name, hf: deck, ...CAM, near, far, light: SUN, shade: cloudShade, gold: GOLD_L, levels: 17, glevels: 6, shadowFrom: -1,
  fog: { v: .84, g: .3, from: 3000, to: 34000, amt: .86 }, skirt: o.skirt ?? 90, step: o.step ?? .009,
  props: (mat) => ({ maxR: o.maxR * (mat === 'l' ? .7 : 1), hgt: mat === 'l' ? 1.25 : 1, jit: .04, detail: 1.15, aj: .26, len: 1.25 }),
});

function build() {
  const rng = mulberry(11);
  // ---- the sky: deep at the top, a band of first light on the horizon
  const sky = refOf(-100, -100, 1380, 720);
  sky.fill(P([[-100, -100], [1380, -100], [1380, 720], [-100, 720]]),
    lin(0, -100, 0, HZ, [[0, K(.13)], [.24, K(.2)], [.5, K(.34, .03)], [.72, K(.52, .1)], [.88, K(.78, .26)], [1, K(.92, .36, GOLD_L)]]),
    { dir: -3, group: 'sky', maxR: 44, aj: .12, detail: 2, jit: .05, len: 2.1, wid: .74 });
  // the sun is still under the cloud: its glow sits low on the left
  sky.fill(EL(300, HZ - 4, 560, 96), lin(0, HZ - 100, 0, HZ, [[0, K(.6, .16)], [.55, K(.86, .36, GOLD_L)], [1, K(.96, .5, GOLD_L)]]), { dir: -2, group: 'sky', maxR: 26, aj: .14, detail: 1.5, len: 1.7, wid: .8 });
  sky.fill(EL(296, HZ - 6, 300, 14), css(warm(.99, .34, GOLD_XL)), { dir: 0, group: 'sun', maxR: 9, aj: .08, hgt: 1.3, len: 2.2 });
  // long bars of cloud above the horizon: dark on top, lit from beneath
  const bar = (x, y, len, th, lit, i) => {
    const s = -.02 - rng() * .02;
    sky.fill(P([[x, y], [x + len * .3, y - th * .8 + len * .3 * s], [x + len * .7, y - th + len * .7 * s], [x + len, y + len * s], [x + len * .6, y + th * .5 + len * .6 * s]]), K(lerp(.3, .42, lit), .05), { dir: s * 57, group: 'bar' + i, maxR: 12, aj: .1, len: 1.8 });
    sky.fill(P([[x + len * .04, y + 1], [x + len * .6, y + th * .5 + len * .6 * s], [x + len, y + len * s], [x + len * .62, y + th * 1.05 + len * .6 * s]]), K(lerp(.7, .95, lit), lerp(.2, .52, lit), GOLD_L), { dir: s * 57, group: 'barl' + i, maxR: 6, aj: .08, hgt: 1.3, len: 1.8 });
  };
  bar(-60, 404, 520, 20, 1, 0); bar(360, 372, 640, 24, .75, 1); bar(820, 414, 520, 16, .45, 2); bar(120, 318, 420, 14, .5, 3); bar(700, 300, 560, 15, .25, 4);
  // ---- the deck of cloud, in four ranges of depth so the nearer cloud can pass the farther
  const far = refOf(-140, 250, 1420, 660, 1); layer(far, 5200, 90000, { name: 'f', maxR: 9, step: .006 });
  const mid = refOf(-240, 140, 1520, 800, 1); layer(mid, 1900, 6400, { name: 'm', maxR: 20 });
  const near = refOf(-380, 430, 1660, 1120, .8); layer(near, 800, 2400, { name: 'n', maxR: 38 });
  const front = refOf(-760, 430, 2040, 1900, .6); layer(front, 240, 980, { name: 'x', maxR: 62, skirt: 1e5 });
  L = [
    { pl: paint(sky, { seed: 3, R: [44, 22, 11, 5.5, 3], T: 11 }), p: 0, drift: 0 },
    { pl: paint(far, { seed: 4, R: [9, 4.5, 2.4], T: 10 }), p: .05, drift: .8 },
    { pl: paint(mid, { seed: 5, R: [20, 10, 5, 2.6], T: 10 }), p: .16, drift: 2 },
    { pl: paint(near, { seed: 6, R: [30, 15, 7.5, 3.8, 2.2], T: 10 }), p: .42, drift: 4.5 },
    { pl: paint(front, { seed: 7, R: [38, 19, 9.5, 4.8, 2.6], T: 10 }), p: 1, drift: 8 },
  ];
}

/** t runs from 0: the glide (0 to `dolly`), then the flight into the cloud (to `end`). */
export function drawClouds(t, { dolly = 7, end = 10.4, tr = {} } = {}) {
  if (!L) build();
  const g = seg(t, 0, dolly), d = seg(t, dolly - .6, end);
  const z = Math.min(.945, lerp(.2 * sm(g), .945, Math.pow(d, 2.2)));
  const k = Math.pow(d, 1.6);
  const view = { hx: HOME[0], hy: HOME[1], x: lerp(640 + 26 * sm(g), CLOUD_END.x, sm(k)), y: lerp(512 + 10 * sm(g), CLOUD_END.y, sm(k)), z, zoom: 1 };
  for (const l of L) drawPlate(l.pl, view, { p: l.p, home: HOME, dx: -t * l.drift }, { t, ...tr });
  return view;
}
export const cloudsInfo = () => (L ? L.reduce((n, l) => n + l.pl.n, 0) : 0);
