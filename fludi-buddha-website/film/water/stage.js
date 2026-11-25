// The stage: the renderer, painted plates in layers, the camera, and the strokes that move.
import { Impasto, Strokes, F, S, KNIFE } from './engine/impasto.js';
import { paintRef } from './engine/plate.js';
import { Ref } from './engine/plate.js';
import { INK, PAPER, mul, TR } from './lib.js';

/** The frame, in scene units: a 5 : 4 canvas. One unit is one pixel of the full-size render at zoom 1. */
export const FW = 1280, FH = 1024;
export const NEVER = 1e6;

export let E = null;
/** Pixels per scene unit at zoom 1 (1 for the full-size render, .5 for a half-size look). */
export let RS = 1;
/** The strokes that move: filled by a shot, drawn with flush(), then emptied. */
export const dyn = new Strokes(32768);

export function init(canvas, { W, H, ss }) {
  E = new Impasto(canvas, { W, H, ss });
  RS = W / FW;
  return E;
}

/**
 * A painted plate: the strokes of one reference picture, on the graphics card, with its thin
 * underpainting. `o` goes to paintRef (R: stroke sizes coarse to fine, T: how exact, seed).
 */
export function paint(ref, o = {}) {
  const strokes = paintRef(ref, { R: [44, 22, 11, 5.5, 3], T: 13, ...o });
  if (o.extra) o.extra(strokes, ref);
  return upload(ref, strokes);
}
export function upload(ref, strokes) {
  return { b: E.batch(strokes.data().slice()), tex: E.texture(ref.ctx.canvas), w: ref.w, h: ref.h, ox: ref.ox, oy: ref.oy, strokes: strokes.data().slice(), n: strokes.n };
}
/** A reference picture covering the scene from (x0, y0) to (x1, y1), drawn in scene coordinates. */
export function refOf(x0, y0, x1, y1, scale = 1) { return new Ref(x1 - x0, y1 - y0, scale).at(x0, y0); }
/** Strokes alone (no reference picture under them). */
export function batchOf(strokes) { return { b: E.batch(strokes.data().slice()), strokes: strokes.data().slice(), n: strokes.n }; }

/**
 * Where a layer is seen from. The view is the camera: {x, y} the point it looks at on the focal
 * layer, `zoom` the lens, `z` how far it has travelled forward (0 to just under 1), `tx, ty` a
 * tilt that slides every layer alike, `rot` a roll. A layer has `p`, its nearness: 1 is the focal
 * layer, 0 is infinitely far (it never slides or grows), more than 1 is in front. `home` is the
 * camera position the layers were drawn for.
 */
export function camOf(view, layer = {}) {
  const p = layer.p ?? 1, s = 1 / Math.max(.02, 1 - (view.z || 0) * p);
  const hx = layer.home?.[0] ?? view.hx ?? FW / 2, hy = layer.home?.[1] ?? view.hy ?? FH / 2;
  return {
    x: hx + (view.x - hx) * p + (view.tx || 0) / s + (layer.dx || 0),
    y: hy + (view.y - hy) * p + (view.ty || 0) / s + (layer.dy || 0),
    zoom: (view.zoom ?? 1) * s * RS, rot: view.rot || 0,
  };
}
/** The frame itself, for strokes placed in frame units (weather in front of the lens, the title). */
export const screenCam = () => ({ x: FW / 2, y: FH / 2, zoom: RS, rot: 0 });

/** Draw a plate: the underpainting, then its strokes. `o` may carry a sweep (appear or vanish). */
export function drawPlate(pl, view, layer = {}, o = {}) {
  const cam = o.cam || camOf(view, layer);
  const sweeping = (o.appear !== undefined && o.appear > -NEVER / 2) || (o.vanish !== undefined && o.vanish < NEVER / 2);
  if (pl.tex && !o.noUnder) E.under(pl.tex, pl.w, pl.h, { ...o, cam, M: mul(o.M || [1, 0, 0, 1, 0, 0], TR(pl.ox, pl.oy)), late: sweeping ? (o.late ?? .5) : 0 });
  E.draw(pl.b, { ...o, cam });
  return cam;
}
/** Draw the moving strokes gathered so far, seen through a layer (or in frame units with cam: screenCam()). */
export function flush(view, layer = {}, o = {}) {
  if (dyn.n) E.drawNow(dyn.data(), { ...o, cam: o.cam || camOf(view, layer) });
  dyn.clear();
}

/**
 * Re-lay some of a plate's strokes in another colour, as moving strokes: light that passes over
 * static paint. fn(x, y, i) returns null (leave it) or {k: 0..1 how strongly, c: [r,g,b]}.
 */
export function relight(pl, fn, o = {}) {
  const a = pl.strokes, n = pl.n, lift = o.hgt ?? 1.04;
  for (let i = 0; i < n; i++) {
    const j = i * F, r = fn(a[j + S.x], a[j + S.y], i);
    if (!r || r.k <= .01) continue;
    const c = r.c, k = r.k;
    dyn.push({ x: a[j + S.x], y: a[j + S.y], ang: a[j + S.ang], len: a[j + S.len], wid: a[j + S.wid],
      c: [a[j + S.r] + (c[0] - a[j + S.r]) * k, a[j + S.g] + (c[1] - a[j + S.g]) * k, a[j + S.b] + (c[2] - a[j + S.b]) * k],
      c2: [a[j + S.r2] + (c[0] - a[j + S.r2]) * k, a[j + S.g2] + (c[1] - a[j + S.g2]) * k, a[j + S.b2] + (c[2] - a[j + S.b2]) * k],
      seed: a[j + S.seed], type: a[j + S.type], alpha: a[j + S.alpha], hgt: a[j + S.hgt] * lift, bend: a[j + S.bend], skew: a[j + S.skew], taper: a[j + S.taper] });
  }
}

/** The light and the grade of a frame. Each shot starts from this and changes what it needs. */
export const LOOK = {
  light: [-.55, -.6, .7], norm: 3.4, amb: .8, dif: .29, spec: .18, shin: 28, ao: 1.25,
  ground: PAPER.map((v) => v * .93), lift: [0, 0, 0], gain: [1, 1, 1], sat: 1, expo: 1, contrast: 1.02, vig: .1, weave: .1, lightCol: [1, .95, .86],
};
export const BLACK = INK;
export { KNIFE };
