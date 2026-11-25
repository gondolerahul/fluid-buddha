// 3 · The sky the snow falls through, and the tilt down to the range.
// 4 · Frozen mountains: a high crane over the peaks, descending towards one sharp ridge.
import { K, P, EL, lin, lerp, clamp, mulberry, css, warm, GOLD_L, GOLD_XL, sm, seg } from '../lib.js';
import { refOf, paint, drawPlate } from '../stage.js';
import { terrain, ridged, fbm, vnoise } from '../terrain.js';

const HOME = [640, 512], HZ = 420;
const CAM = { eye: [0, 4300, 0], f: 1150, cx: 640, horizon: HZ };
const SUN = [-.7, .52, .36];
/** How far up the sky reaches above the frame of the range (for the tilt down). */
export const SKY_TOP = -2300;
let L = null;

// the great peaks, [x, z, height, radius]: a tall pair on the right, a long wall far behind
const PEAKS = [[2300, 11000, 6900, 5200], [6800, 15500, 5600, 4200], [-4600, 17000, 6100, 5200], [-900, 26000, 6000, 6400], [-9200, 11500, 5000, 4200]];
/** The near ridge the crane descends towards: a crest running away from the eye, right of centre. */
const RIDGE = (x, z) => { if (z < 900) return 0; const cx = 1100 + (z - 2000) * .5, d = Math.abs(x - cx); return 3900 * Math.exp(-((z - 4600) ** 2) / (2 * 2900 ** 2)) * Math.max(0, 1 - d / (1700 + (z - 2000) * .3)) ** 1.25; };

function hf(x, z) {
  // a highland of ridges everywhere, so there is no valley floor in sight
  let h = 1700 + 600 * fbm(x / 9000, z / 9000, 3, 2) + 1500 * Math.pow(ridged(x / 4600, z / 4600, 4, 3), 1.5) + 260 * ridged(x / 1500, z / 1500, 3, 9);
  for (const [px, pz, ph, pr] of PEAKS) { const d = Math.hypot(x - px, z - pz) / pr; if (d < 1.3) h = Math.max(h, ph * Math.max(0, 1 - d * .8) ** 1.45 * (.8 + .3 * ridged(x / 3200, z / 3200, 4, 7))); }
  return Math.max(h, RIDGE(x, z) * (.82 + .3 * ridged(x / 1300, z / 1300, 4, 19)));
}
/** Snow where it can lie, rock where it is too steep; a low sun from the left. Few values, big shapes. */
function shade(s) {
  const steep = 1 - s.ny, n = fbm(s.X / 1800, s.Z / 1800, 2, 5);
  const snow = steep < .38 + n * .2;
  const lit = !s.shadow && s.ndl > .22;
  if (snow) {
    if (lit && s.ndl > .55) return { v: .98, g: .2, mat: 'sl', flow: 'fall' };
    if (lit) return { v: .84, g: .08, mat: 'sh', flow: 'fall' };
    return { v: .58, g: .02, mat: 'ss', flow: 'fall' };
  }
  if (lit) return { v: .5, g: .14, mat: 'rl', flow: 'fall' };
  return { v: .27, g: .03, mat: 'rs', flow: 'fall' };
}
const layer = (ref, near, far, o) => terrain(ref, {
  name: o.name, hf, ...CAM, near, far, light: SUN, shade, gold: GOLD_L, levels: 11, glevels: 5,
  fog: { v: .86, g: .14, from: 5000, to: 50000, amt: .86 }, skirt: 1e5, step: o.step ?? .005, eps: 10, minStep: 2,
  props: (mat) => ({ maxR: o.maxR * (mat[0] === 'r' ? .8 : 1), hgt: mat[0] === 'r' ? 1.3 : 1.05, jit: .05, detail: 1.2, aj: .22, len: 1.5, wid: .85 }),
});

function build() {
  const rng = mulberry(5);
  // ---- the morning sky, tall enough to tilt down from: pale at the top, warm low down
  const sky = refOf(-200, SKY_TOP - 300, 1480, 760);
  sky.fill(P([[-200, SKY_TOP - 300], [1480, SKY_TOP - 300], [1480, 760], [-200, 760]]),
    lin(0, SKY_TOP - 300, 0, HZ, [[0, K(.6, .02)], [.4, K(.72, .04)], [.75, K(.84, .1)], [.92, K(.92, .22, GOLD_L)], [1, K(.95, .3, GOLD_L)]]),
    { dir: -4, group: 'sky', maxR: 34, aj: .2, detail: 1.8, jit: .04, len: 1.8, wid: .8 });
  // wisps of high cloud, lit from below
  for (let i = 0; i < 9; i++) {
    const x = -200 + rng() * 1500, y = SKY_TOP + rng() * (HZ - SKY_TOP - 300), len = 300 + rng() * 600, th = 10 + rng() * 22, sl = -.03 - rng() * .04, k = (y - SKY_TOP) / (HZ - SKY_TOP);
    sky.fill(P([[x, y], [x + len * .4, y - th + len * .4 * sl], [x + len, y + len * sl], [x + len * .55, y + th * .7 + len * .55 * sl]]), K(lerp(.8, .97, k), lerp(.04, .3, k), GOLD_L), { dir: sl * 57, group: 'w' + i, maxR: 12, aj: .1, len: 1.9 });
  }
  const far = refOf(-300, 120, 1580, 700); layer(far, 11000, 160000, { name: 'f', maxR: 10, step: .004 });
  const mid = refOf(-420, 0, 1700, 1000, .9); layer(mid, 5200, 11600, { name: 'm', maxR: 22 });
  const near = refOf(-700, 0, 1980, 1400, .7); layer(near, 2300, 5600, { name: 'n', maxR: 36 });
  const front = refOf(-900, 100, 2180, 2000, .55); layer(front, 800, 2500, { name: 'x', maxR: 56 });
  L = [
    { pl: paint(sky, { seed: 13, R: [34, 17, 8.5, 4.5], T: 10 }), p: 0 },
    { pl: paint(far, { seed: 14, R: [10, 5, 2.6], T: 9 }), p: .08 },
    { pl: paint(mid, { seed: 15, R: [22, 11, 5.5, 2.8], T: 9 }), p: .24 },
    { pl: paint(near, { seed: 16, R: [36, 18, 9, 4.5, 2.4], T: 9 }), p: .55 },
    { pl: paint(front, { seed: 17, R: [52, 26, 13, 6.5, 3.2], T: 9 }), p: 1 },
  ];
}

/**
 * tilt: 1 looks up into the sky, 0 at the range. crane: 0..1, the move forward over the peaks and
 * down towards the ridge. `only` draws just the sky (while the snow is still falling high up).
 */
export function drawMountains(t, { tilt = 0, crane = 0, tr = {}, skyOnly = false } = {}) {
  if (!L) build();
  const c = sm(crane);
  const view = { hx: HOME[0], hy: HOME[1], x: 640 + 170 * c, y: 512 + 230 * c, z: .62 * Math.pow(c, 1.3), zoom: 1, ty: (SKY_TOP + 400 - 512) * tilt };
  for (const l of skyOnly ? L.slice(0, 1) : L) drawPlate(l.pl, view, { p: l.p, home: HOME }, { t, ...tr });
  return view;
}
export const mountainsInfo = () => (L ? L.reduce((n, l) => n + l.pl.n, 0) : 0);
