// 8 · Waterfall: the river spills over the edge; the camera tilts down beside the falling water,
// and the spray rises until it fills the frame.
import { KNIFE, DAB, BRUSH } from '../engine/impasto.js';
import { K, P, lin, rad, lerp, clamp, sm, ss, seg, hash, tone, warm, mulberry, GOLD_L, GOLD_XL, WHITE } from '../lib.js';
import { refOf, paint, drawPlate, flush, dyn, screenCam, FW, FH } from '../stage.js';
import { fbm, ridged } from '../terrain.js';

const HOME = [640, 512];
export const LIP = 250, POOL = 2560, BOTTOM = 3000;
/** The curtain's edges at height y: it widens as it falls. */
const left = (y) => 470 - (y - LIP) * .07 - 14 * Math.sin(y / 170);
const right = (y) => 860 + (y - LIP) * .06 + 12 * Math.sin(y / 210 + 1);
let L = null;

function build() {
  const rng = mulberry(81);
  const R = refOf(-300, -500, 1580, BOTTOM + 200, .7);
  // the far land, seen over the edge, in morning haze
  R.fill(P([[-300, -500], [1580, -500], [1580, LIP + 40], [-300, LIP + 40]]), lin(0, -500, 0, LIP, [[0, K(.72, .08)], [.7, K(.9, .26, GOLD_L)], [1, K(.95, .34, GOLD_L)]]), { dir: -3, group: 'sky', maxR: 30, aj: .2, len: 1.8 });
  const hills = [[-300, LIP + 40]]; for (let x = -300; x <= 1580; x += 30) hills.push([x, LIP - 30 - 60 * fbm(x / 400, 2, 3, 5)]); hills.push([1580, LIP + 40]);
  R.fill(P(hills), K(.78, .18), { dir: 0, group: 'hills', maxR: 12, aj: .2 });
  // the cliff, both sides of the curtain: dark rock in vertical blocks, lit on the faces that turn to the left
  const cliffL = [[-300, LIP + 10]], cliffR = [[1580, LIP + 10]];
  for (let y = LIP + 10; y <= POOL + 80; y += 40) { cliffL.push([left(y) - 6, y]); cliffR.push([right(y) + 6, y]); }
  cliffL.push([-300, POOL + 80]); cliffR.push([1580, POOL + 80]);
  R.fill(P(cliffL), lin(0, LIP, 0, POOL, [[0, K(.3, .04)], [1, K(.14, .02)]]), { dir: 90, group: 'cl', maxR: 30, aj: .25, len: 1.5, follow: 5 });
  R.fill(P(cliffR), lin(0, LIP, 0, POOL, [[0, K(.24, .03)], [1, K(.1, .01)]]), { dir: 90, group: 'cr', maxR: 30, aj: .25, len: 1.5, follow: 5 });
  // blocks and ledges in the rock: lit faces on the left of each, and the green-less dark of wet stone
  // tall slabs of rock, each lit down its left edge
  for (let i = 0; i < 34; i++) {
    const side = i % 2, y = LIP + rng() * (POOL - LIP - 500), h = 400 + rng() * 900, w = 30 + rng() * 70;
    const edge = side ? right(y + h / 2) + 40 : left(y + h / 2) - 40, x = side ? edge + rng() * 520 : edge - w - rng() * 520, sl = (rng() - .5) * 40;
    R.clip(P(side ? cliffR : cliffL), () => R.fill(P([[x, y], [x + w, y + 20], [x + w + sl, y + h], [x + sl, y + h - 30]]), K(side ? .3 : .4, .08, GOLD_L), { dir: 90, group: 'bl' + i, maxR: 12, aj: .15, len: 1.8 }));
  }
  // the river at the lip, coming towards the edge
  R.fill(P([[left(LIP) - 60, LIP - 6], [right(LIP) + 60, LIP - 6], [right(LIP) + 10, LIP + 12], [left(LIP) - 10, LIP + 12]]), K(.9, .3, GOLD_L), { dir: 0, group: 'lip', maxR: 6, aj: .1, hgt: 1.3 });
  // the curtain: white water, lit gold on the left, greyer to the right; darker streaks where it is thin
  const cur = [[left(LIP), LIP]]; for (let y = LIP; y <= POOL + 40; y += 40) cur.push([left(y), y]); for (let y = POOL + 40; y >= LIP; y -= 40) cur.push([right(y), y]);
  R.fill(P(cur), lin(left(800), 0, right(800), 0, [[0, K(.97, .34, GOLD_L)], [.35, K(.94, .12)], [.75, K(.82, .04)], [1, K(.66, .02)]]), { dir: 90, group: 'cur', maxR: 16, aj: .06, len: 2.6, wid: .6, hgt: 1.3 });
  R.clip(P(cur), () => { for (let i = 0; i < 26; i++) { const x = lerp(left(LIP), right(LIP), rng()), w = 4 + rng() * 12, y0 = LIP + rng() * 600; R.fill(P([[x, y0], [x + w, y0], [x + w * 1.6 + 30, POOL], [x + 20, POOL]]), K(.58 + rng() * .14, .04), { dir: 90, group: 'st' + i, maxR: 5, aj: .05, len: 3 }); } });
  // the pool: churning white, and the dark water beyond it
  R.fill(P([[-300, POOL + 60], [1580, POOL + 60], [1580, BOTTOM + 200], [-300, BOTTOM + 200]]), lin(0, POOL, 0, BOTTOM, [[0, K(.3, .06)], [1, K(.18, .04)]]), { dir: 0, group: 'pool', maxR: 26, aj: .1, len: 2 });
  R.fill((c) => c.ellipse(660, POOL + 110, 560, 150, 0, 0, 7), rad(660, POOL + 110, 40, 560, [[0, K(.98, .22, GOLD_L)], [.6, K(.88, .08)], [1, K(.7, .04)]]), { dir: { radial: [660, POOL + 110] }, group: 'foam', maxR: 18, aj: .5 });
  L = paint(R, { seed: 82, R: [30, 15, 7.5, 3.8], T: 9 });
}

/** The falling water: long strokes that drop down the curtain, faster as they fall. */
function falling(t) {
  for (let i = 0; i < 520; i++) {
    const u = hash(i * 1.37), lane = lerp(.02, .98, u), ph = (hash(i * 3.1) + t * (.32 + hash(i * 5.7) * .12)) % 1;
    const y = LIP + Math.pow(ph, 1.4) * (POOL - LIP + 80), x = lerp(left(y), right(y), lane) + Math.sin(y / 90 + i) * 6;
    const k = lerp(1, .78, Math.pow(lane, 1.5)), gold = lane < .3 && hash(i * 8.1) > .5;
    dyn.push({ x, y, ang: Math.PI / 2 + (lane - .5) * .12, len: 50 + ph * 160, wid: 6 + hash(i * 2.2) * 10, c: gold ? GOLD_XL : tone(k), c2: tone(k - .08), type: KNIFE, seed: i, hgt: 1.3, alpha: .9, skew: .2 });
  }
  // drops that break away from the edges
  for (let i = 0; i < 120; i++) {
    const ph = (hash(i * 2.9) + t * .4) % 1, side = i % 2, y = LIP + 200 + ph * (POOL - LIP - 200);
    const x = (side ? right(y) + 10 + ph * 40 * hash(i) : left(y) - 10 - ph * 40 * hash(i));
    dyn.push({ x, y, ang: Math.PI / 2, len: 14 + hash(i) * 20, wid: 6 + hash(i * 3) * 6, c: tone(.92), type: DAB, seed: i + 900, hgt: 1.2, alpha: .8 });
  }
}
/** Spray from the pool: dabs that billow up and out. `fill` 0..1: how much of the frame they cover. */
export function spray(t, fill, { cam, tr = {}, n = 700, origin = [660, POOL + 80] } = {}) {
  for (let i = 0; i < n; i++) {
    const life = 2.2 + hash(i * 4.4) * 1.6, ph = ((hash(i * 1.9) * life + t) % life) / life;
    const a = -Math.PI / 2 + (hash(i * 7.3) - .5) * 2.6, sp = 200 + hash(i * 3.3) * 420 * (1 + fill * 1.6);
    const x = origin[0] + Math.cos(a) * sp * ph * 1.4, y = origin[1] + Math.sin(a) * sp * ph * (1 + fill * 2.2);
    const r = (34 + hash(i * 6.1) * 70) * (1 + ph * 1.3) * (1 + fill * 1.3);
    const k = lerp(.86, 1, hash(i * 8.8));
    // mist is scumbled: broad, dry, half-covering strokes of white dragged over what is behind
    dyn.push({ x, y, ang: a + Math.PI / 2 + (hash(i * 5.2) - .5) * 1.2, len: r * 2.6, wid: r, c: tone(k), c2: warm(k - .05, .06), type: BRUSH, seed: i * 3, hgt: .15, alpha: clamp((1 - ph) * 1.4) * lerp(.22, .5, fill) });
  }
  flush(null, {}, { t, cam, run: .6, wet: 0, ...tr });
}
/** t0: the shot starts at the lip; the tilt down runs `dur`; `fill` is when the spray covers everything. */
export function drawFalls(t, { t0, dur, tr = {} } = {}) {
  if (!L) build();
  const k = seg(t, t0, t0 + dur), c = sm(k);
  const view = { hx: HOME[0], hy: HOME[1], x: 640 + 70 * c, y: lerp(LIP + 160, POOL - 120, c), z: .18 * ss(seg(k, .6, 1)), zoom: 1 };
  const cam = drawPlate(L, view, { p: 1, home: HOME }, { t, ...tr });
  falling(t); flush(null, {}, { t, cam, run: .3, ...tr });
  spray(t, ss(seg(k, .7, 1)), { cam, tr });
  return view;
}
export const fallsInfo = () => (L ? L.n : 0);
