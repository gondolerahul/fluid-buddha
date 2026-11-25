// 2 · The snowflake. Inside the cloud the camera finds one crystal forming; it is laid in by the
// knife, arm by arm, and catches the first trace of gold.
// 3 · Then the camera pulls back and it is one flake among countless others.
import { KNIFE, DAB } from '../engine/impasto.js';
import { K, P, rad, lerp, clamp, sm, seg, back, hash, tone, WHITE, GOLD_L, GOLD_XL, TAU } from '../lib.js';
import { refOf, paint, drawPlate, flush, dyn, screenCam, FW, FH } from '../stage.js';

export const FLAKE_AT = [700, 520];           // where the crystal sits in the frame
const R = 330;                                // its arm, at full size and zoom 1
let ground = null;

function build() {
  // the inside of the cloud: pale vapour, darker where the crystal will be, so white reads on it
  const g = refOf(-160, -160, 1440, 1184);
  const [cx, cy] = FLAKE_AT;
  g.fill(P([[-160, -160], [1440, -160], [1440, 1184], [-160, 1184]]),
    rad(cx + 30, cy + 20, 40, 900, [[0, K(.4)], [.18, K(.46)], [.38, K(.58)], [.62, K(.72)], [.85, K(.8, .02)], [1, K(.84, .04)]]),
    { dir: { radial: [cx, cy], off: 78 }, group: 'vap', aj: .7, jit: .03, detail: 1.4, len: 1.1, maxR: 46 });
  ground = paint(g, { seed: 21, R: [46, 23, 12, 6], T: 6 });
}

/**
 * The crystal as knife strokes, in its own space (centre 0,0, arm length 1). Each stroke knows
 * when it is born (0..1 of the growth), so the crystal grows outwards from its heart.
 * Built once: [x, y, angle, length, width, born, kind] with kind 0 body, 1 fine, 2 glint.
 */
const CRYSTAL = (() => {
  const out = [], add = (x, y, a, len, wid, born, kind = 0, taper = 0) => out.push({ x, y, a, len, wid, born, kind, taper });
  // along a line from (r0 at angle a) outward: a stroke centred on it
  for (let k = 0; k < 6; k++) {
    const a = k * TAU / 6, ca = Math.cos(a), sa = Math.sin(a);
    const at = (r, off = 0, oa = a + Math.PI / 2) => [ca * r + Math.cos(oa) * off, sa * r + Math.sin(oa) * off];
    // the heart: a small six-sided plate
    { const [x, y] = at(.1); add(x, y, a + Math.PI / 2, .125, .05, 0); }
    { const [x, y] = at(.2); add(x, y, a + Math.PI / 2, .22, .034, .1 + k * .008, 1); }
    // the spine, thick at the heart, thin at the tip
    for (let i = 0; i < 6; i++) { const r = (i + .5) / 6; const [x, y] = at(r * .96); add(x, y, a, .185, lerp(.092, .04, i / 5), .05 + r * .5); }
    // side branches in pairs, shorter towards the tip
    [[.3, .33], [.46, .27], [.62, .19], [.78, .115]].forEach(([f, b], j) => {
      for (const sgn of [-1, 1]) {
        const ba = a + sgn * TAU / 6, cb = Math.cos(ba), sb = Math.sin(ba), [x0, y0] = at(f);
        add(x0 + cb * b * .3, y0 + sb * b * .3, ba, b * .62, .05 - j * .006, .2 + f * .5);
        add(x0 + cb * b * .76, y0 + sb * b * .76, ba, b * .5, .034 - j * .004, .27 + f * .5, 0, .5);
        // the two largest carry small branches of their own
        if (j < 2) for (const s2 of [-1, 1]) { const sa2 = ba + s2 * TAU / 6, x1 = x0 + cb * b * .52, y1 = y0 + sb * b * .52, l2 = b * .34; add(x1 + Math.cos(sa2) * l2 * .5, y1 + Math.sin(sa2) * l2 * .5, sa2, l2, .026, .36 + f * .5, 1, .4); }
      }
    });
    // the tip: a small diamond
    for (const sgn of [-1, 1]) { const ta = a + sgn * .5, [x0, y0] = at(.9); add(x0 + Math.cos(ta) * .05, y0 + Math.sin(ta) * .05, ta, .12, .03, .74, 1, .6); }
    { const [x, y] = at(1.0); add(x, y, a, .1, .026, .8, 1, .7); }
    // a glint of the first light on the arms that face it
    if (k === 3 || k === 4) { const [x, y] = at(.97); add(x, y, a, .075, .06, .9 + (k - 3) * .04, 2); const [x2, y2] = at(.46, .03); add(x2, y2, a, .12, .022, .93, 2); }
  }
  return out;
})();

/** Draw the crystal at (cx, cy) with arm length r, grown to `grow` (0..1), turned by rot. */
export function crystal(cx, cy, r, grow, rot, o = {}) {
  const cr = Math.cos(rot), sr = Math.sin(rot), light = o.c || WHITE, dark = o.dark || tone(.26);
  const put = (s, dx, dy, c, c2, wm, hgt) => {
    const g = clamp((grow - s.born) / .13); if (g <= 0) return;
    const e = back(g, 1.5), len = s.len * r * e, x = s.x * r, y = s.y * r;
    // it grows from its inner end
    const ix = x - Math.cos(s.a) * s.len * r * .5 * (1 - e), iy = y - Math.sin(s.a) * s.len * r * .5 * (1 - e);
    dyn.push({ x: cx + ix * cr - iy * sr + dx, y: cy + ix * sr + iy * cr + dy, ang: s.a + rot, len, wid: s.wid * r * wm * (.7 + .3 * g), c, c2, type: s.kind === 2 ? DAB : KNIFE, taper: s.taper, seed: s.born * 913 + s.x * 71 + s.y * 37, hgt, skew: s.kind === 0 ? .3 : 0 });
  };
  // its own shadow first, a little down and to the right, so it stands off the cloud
  if (!o.flat) for (const s of CRYSTAL) if (s.kind < 2) put(s, r * .026, r * .034, dark, dark, 1.12, .5);
  for (const s of CRYSTAL) if (s.kind === 0) put(s, 0, 0, light, tone(.86), 1, 1.5);
  for (const s of CRYSTAL) if (s.kind === 1) put(s, 0, 0, light, tone(.9), 1, 1.3);
  if (!o.noGold) for (const s of CRYSTAL) if (s.kind === 2) put(s, 0, 0, GOLD_XL, GOLD_L, 1, 1.7);
}

/** A far flake is a few marks; a near one is the whole crystal, simplified. */
function smallFlake(x, y, r, rot, a, seed, tint) {
  if (r < 5) { dyn.push({ x, y, ang: rot, len: r * 2.2, wid: r * 1.7, c: tint, c2: tone(.82), type: DAB, seed, alpha: a, hgt: 1.3 }); return; }
  for (let k = 0; k < 3; k++) dyn.push({ x, y, ang: rot + k * TAU / 6, len: r * 2, wid: Math.max(2.2, r * .26), c: tint, c2: tone(.86), type: KNIFE, seed: seed + k, alpha: a, hgt: 1.4, skew: 0 });
  if (r > 12) for (let k = 0; k < 6; k++) { const an = rot + k * TAU / 6, bx = x + Math.cos(an) * r * .56, by = y + Math.sin(an) * r * .56; for (const s of [-1, 1]) dyn.push({ x: bx + Math.cos(an + s * 1.05) * r * .17, y: by + Math.sin(an + s * 1.05) * r * .17, ang: an + s * 1.05, len: r * .36, wid: Math.max(2, r * .15), c: tint, type: KNIFE, seed: seed + 10 + k * 2 + s, alpha: a, hgt: 1.3 }); }
}

/**
 * The snowfall, in front of the lens. `back` is how far the camera has pulled away from the
 * first crystal (0 = at it); `fall` how far the snow has fallen past the camera (frame units);
 * `amount` 0..1 how many of the flakes have formed. The first crystal is flake 0.
 */
export function snowfall(t, { back: B = 0, fall = 0, amount = 1, fade = 1, n = 420, ty = 0, tr = {} } = {}) {
  const F = 1, [cx, cy] = FLAKE_AT;   // the first crystal is at depth 1
  for (let i = 1; i < n; i++) {
    const born = hash(i * 3.7) * .92; if (amount <= born) continue;
    const grow = clamp((amount - born) / .1);
    const D = lerp(.55, 6.5, Math.pow(hash(i * 1.3), 1.5));          // depth, in units of the first crystal's distance
    const s = F / (D + B);                                            // scale on screen
    if (s < .012) continue;
    const X = (hash(i * 7.1) - .5) * 9000, wob = Math.sin(t * (.5 + hash(i) * .7) + i) * 26;
    const span = 9000, Y = ((hash(i * 5.3) * span + fall * (1 + .25 * hash(i * 2.2)) / 1) % span + span) % span - span / 2;
    const x = cx + (X + wob) * s, y = cy + Y * s;
    if (x < -60 || x > FW + 60 || y < -60 || y > FH + 60) continue;
    const r = (44 + hash(i * 9.1) * 40) * s * (.5 + .5 * back(grow, 1.4));
    const dim = clamp(1.25 - D * .13);
    smallFlake(x, y + ty * lerp(.25, 1, clamp(1 / D)), r, hash(i * 4.4) * TAU + t * (.12 + hash(i * 6.2) * .3) * (i % 2 ? 1 : -1), fade * (.55 + .45 * dim), i * 13, tone(lerp(.8, 1, dim)));
  }
  flush(null, {}, { t, cam: screenCam(), run: .2, ...tr });
}

/** How far the camera has pulled back from the crystal, from `pull` to `end`. */
export const pullBack = (t, pull, end) => lerp(0, 5, Math.pow(sm(seg(t, pull, end)), 1.15));

/**
 * t0 is when the crystal starts to form. The camera pushes in while it grows (to `grown`), holds
 * (to `pull`), then pulls back while the cloud opens around it (to `end`).
 */
export function drawFlake(t, { t0, grown, pull, end, dy = 0, tr = {} } = {}) {
  if (!ground) build();
  const view = { hx: 640, hy: 512, x: 640 + Math.sin(t * .21) * 14, y: 512 + Math.cos(t * .17) * 10, zoom: 1, z: 0 };
  // the cloud opens: the vapour is scraped away from the crystal outwards
  const open = t > pull + .3 ? { vanish: pull + .5, vanDur: .4, sweep: { c: [FLAKE_AT[0] / FH, FLAKE_AT[1] / FH, 2.4], baked: 1.6 } } : {};
  if (t < pull + 3.6) {
    drawPlate(ground, view, { p: 0 }, { t, ...tr, ...open });
    // drifting vapour: long, thin planes that slide across, close in tone to the cloud
    for (let i = 0; i < 26; i++) {
      const sp = 12 + hash(i * 3.1) * 26, span = FW + 900, x = ((hash(i * 5.7) * span + (t - t0 + 20) * sp) % span) - 450, y = hash(i * 8.3) * FH;
      const d = Math.hypot(x - FLAKE_AT[0], y - FLAKE_AT[1]), k = lerp(.46, .84, clamp(d / 700)) + (hash(i * 2.9) - .5) * .05;
      dyn.push({ x, y, ang: -.06 + (hash(i) - .5) * .2, len: 380 + hash(i * 4.1) * 380, wid: 40 + hash(i * 6.6) * 60, c: tone(k), c2: tone(k + .05), type: 1, seed: i * 31, hgt: .5, alpha: .55 });
    }
    flush(view, { p: 0 }, { t, run: 1, ...tr, ...open });
  }
  const grow = seg(t, t0 + .3, grown), g = Math.pow(grow, .8);
  const B = t < pull ? lerp(3.4, 0, sm(seg(t, t0, grown + .2))) : pullBack(t, pull, end);
  const s = 1 / (1 + B), rot = -.5 + (t - t0) * .035;
  if (grow > 0 && s > .05) { crystal(FLAKE_AT[0], FLAKE_AT[1] + Math.sin(t * .6) * 5 + dy, R * s, g, rot, { flat: s < .4 }); flush(null, {}, { t, cam: screenCam(), run: .15, wet: .5, ...tr }); }
  return B;
}
export { R as FLAKE_R };
