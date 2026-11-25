// A height field seen in perspective, drawn into a reference picture as flat values.
//
// The knife needs a clean, value-planned picture to paint from. For land, cloud and ice that
// picture is made here: a surface h(x, z) is seen by a camera, lit by a low sun with real cast
// shadows, hazed by distance and reduced to a few flat values. Each value becomes a shape the
// strokes may not leave, so the planes stay sharp.
//
// It is a column march ("voxel space"): for every column of the picture, walk away from the eye,
// and whenever the surface rises above everything nearer, fill that run of the column.
import { warm, clamp } from './lib.js';

// ---------------------------------------------------------------- repeatable noise
const ih = (x, y, s) => { let h = Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(s | 0, 1442695041) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
/** Smooth noise, 0..1. */
export function vnoise(x, y, s = 0) {
  const ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy;
  const ux = fx * fx * fx * (fx * (fx * 6 - 15) + 10), uy = fy * fy * fy * (fy * (fy * 6 - 15) + 10);
  const a = ih(ix, iy, s), b = ih(ix + 1, iy, s), c = ih(ix, iy + 1, s), d = ih(ix + 1, iy + 1, s);
  return a + (b - a) * ux + (c - a) * uy + (a - b - c + d) * ux * uy;
}
/** Layered noise, 0..1. */
export function fbm(x, y, oct = 5, s = 0, lac = 2.03, gain = .5) { let v = 0, a = .5, n = 0; for (let i = 0; i < oct; i++) { v += vnoise(x, y, s + i * 7) * a; n += a; x = x * lac + 13.1; y = y * lac + 7.7; a *= gain; } return v / n; }
/** Pillows: rounded tops, sharp creases between them. 0 in a crease, towards 1 on a top. */
export function billow(x, y, oct = 4, s = 0, lac = 2.1, gain = .5) { let v = 0, a = .5, n = 0; for (let i = 0; i < oct; i++) { v += Math.abs(2 * vnoise(x, y, s + i * 7) - 1) * a; n += a; x = x * lac + 13.1; y = y * lac + 7.7; a *= gain; } return v / n; }
/** Ridges: sharp crests, rounded hollows (mountains). 0..1. */
export function ridged(x, y, oct = 5, s = 0, lac = 2.07, gain = .5) {
  let v = 0, a = .5, n = 0, w = 1;
  for (let i = 0; i < oct; i++) { let r = 1 - Math.abs(2 * vnoise(x, y, s + i * 7) - 1); r *= r; v += r * a * w; n += a; w = clamp(r * 1.6); x = x * lac + 13.1; y = y * lac + 7.7; a *= gain; }
  return v / n;
}

// ---------------------------------------------------------------- the painter
/**
 * terrain(R, o) draws into the reference picture R (made with refOf, so it knows where it sits).
 *   hf(x, z)        the surface: height at a point of the ground
 *   eye [x, y, z]   the camera; it looks along +z, turned by `yaw`
 *   f, cx, horizon  the lens: focal length, and where the view's centre line and horizon fall in the scene
 *   near, far       the depths drawn (one layer of a set draws one range of depths)
 *   skirt           how far below its nearest edge a layer is filled, so layers overlap (scene units)
 *   light [x,y,z]   towards the sun
 *   shade(s)        s = {ndl, shadow, h, X, Z, zc, ny, ...} -> {v: value 0..1, g: gold 0..1, mat, flow: 'fall' | 'contour' | radians}
 *   fog             {v, g, from, to, amt}: distance pulls every value towards this one
 *   props(mat, band, v, g)  stroke settings for a value in a depth band (0 near .. 3 far)
 *   levels, glevels how many steps of value and of gold are kept
 * Returns {classes: how many flat values were used}.
 */
export function terrain(R, o) {
  const { hf, eye, f, cx, horizon, near, far, light, shade } = o;
  const levels = o.levels ?? 12, glevels = o.glevels ?? 5, yaw = o.yaw ?? 0, step = o.step ?? .011;
  const W = R.pw, H = R.ph, sc = R.scale, ox = R.ox, oy = R.oy;
  const col = R.ctx.getImageData(0, 0, W, H), idm = R.idc.getImageData(0, 0, W, H), cd = col.data, idd = idm.data;
  const ang = new Float32Array(W * H);
  const cyaw = Math.cos(yaw), syaw = Math.sin(yaw);
  const ll = Math.hypot(light[0], light[1], light[2]), Lx = light[0] / ll, Ly = light[1] / ll, Lz = light[2] / ll;
  const bands = o.bands || [near * 2.2, near * 5, near * 12];
  const classes = new Map();
  const dirFn = { fn: (x, y) => { const px = Math.min(W - 1, Math.max(0, Math.round((x - ox) * sc))), py = Math.min(H - 1, Math.max(0, Math.round((y - oy) * sc))); return ang[py * W + px]; } };
  const classOf = (mat, vq, gq, band) => {
    const key = `${mat}|${vq}|${gq}|${band}`;
    let c = classes.get(key);
    if (!c) {
      const rgb = (o.colour ? o.colour(mat, vq, gq) : warm(vq, gq, o.gold)).map((v) => Math.round(clamp(v) * 255));
      const p = o.props ? o.props(mat, band, vq, gq) : {};
      const id = R._id({ dir: dirFn, group: `${o.name || 't'}:${key}`, aj: .3, follow: 9, ...p });
      c = { rgb, id }; classes.set(key, c);
    }
    return c;
  };
  const S = {}, skirt = (o.skirt ?? 60) * sc, shadowSteps = o.shadowSteps ?? 14, shadow0 = o.shadow0 ?? 5;
  for (let px = 0; px < W; px++) {
    const sx = ox + (px + .5) / sc, k = (sx - cx) / f;
    let ybuf = H, zc = near, first = true;
    while (zc < far && ybuf > 0) {
      const xc = k * zc, X = eye[0] + xc * cyaw + zc * syaw, Z = eye[2] - xc * syaw + zc * cyaw;
      const h = hf(X, Z);
      const py = Math.ceil((horizon + f * (eye[1] - h) / zc - oy) * sc);
      if (py < ybuf) {
        // slope, from the surface a little to each side (wider far away, so distance stays calm)
        const e = Math.max(o.eps ?? 1.5, zc * .0035);
        const hx = (hf(X + e, Z) - hf(X - e, Z)) / (2 * e), hz = (hf(X, Z + e) - hf(X, Z - e)) / (2 * e);
        const nl = Math.hypot(hx, 1, hz), nx = -hx / nl, ny = 1 / nl, nz = -hz / nl;
        const nl0 = nx * Lx + ny * Ly + nz * Lz, ndl = Math.max(0, nl0);
        // is the sun hidden from here?
        let shadow = 0;
        if (ndl > (o.shadowFrom ?? 0) && Ly < .98) { let d = shadow0 + zc * .002; for (let i = 0; i < shadowSteps; i++) { if (hf(X + Lx * d, Z + Lz * d) > h + Ly * d + d * .02 + .5) { shadow = 1; break; } d *= 1.5; } } else if (ndl <= 0) shadow = 1;
        S.ndl = ndl; S.nl = nl0; S.shadow = shadow; S.h = h; S.X = X; S.Z = Z; S.zc = zc; S.nx = nx; S.ny = ny; S.nz = nz; S.hx = hx; S.hz = hz; S.sx = sx;
        const r = shade(S);
        let v = r.v, g = r.g || 0;
        if (o.fog) { const a = clamp((zc - o.fog.from) / (o.fog.to - o.fog.from)); const m = a * a * (3 - 2 * a) * (o.fog.amt ?? 1) * (r.fog ?? 1); v += (o.fog.v - v) * m; g += ((o.fog.g || 0) - g) * m; }
        const vq = Math.round(clamp(v) * (levels - 1)) / (levels - 1), gq = Math.round(clamp(g) * (glevels - 1)) / (glevels - 1);
        const band = zc < bands[0] ? 0 : zc < bands[1] ? 1 : zc < bands[2] ? 2 : 3;
        const c = classOf(r.mat ?? 0, vq, gq, band);
        // which way the knife goes: down the slope, along it, or a set angle
        let a = 0;
        if (typeof r.flow === 'number') a = r.flow;
        else {
          const gl = Math.hypot(hx, hz) || 1e-6;
          let dx = -hx / gl, dz = -hz / gl;                       // downhill
          if (r.flow === 'x' || r.flow === 'z') { dx = r.flow === 'x' ? 1 : 0; dz = r.flow === 'x' ? 0 : 1; }   // along the ground
          else if (Array.isArray(r.flow)) { dx = r.flow[0]; dz = r.flow[1]; }
          else if (r.flow !== 'fall') { const t = dx; dx = -dz; dz = t; }   // along the slope
          const st = Math.max(3, zc * .01), X2 = X + dx * st, Z2 = Z + dz * st, h2 = r.flow === 'fall' ? hf(X2, Z2) : h;
          const rx = X2 - eye[0], rz = Z2 - eye[2], xc2 = rx * cyaw - rz * syaw, zc2 = rx * syaw + rz * cyaw;
          a = Math.atan2((eye[1] - h2) / zc2 - (eye[1] - h) / zc, xc2 / zc2 - xc / zc);
        }
        const y0 = Math.max(py, 0), y1 = first ? Math.min(H, Math.max(py, 0) + Math.ceil(skirt)) : ybuf;
        const id = c.id, rr = c.rgb[0], gg = c.rgb[1], bb = c.rgb[2];
        for (let y = y0; y < y1; y++) { const i = y * W + px, j = i * 4; cd[j] = rr; cd[j + 1] = gg; cd[j + 2] = bb; cd[j + 3] = 255; idd[j] = id & 255; idd[j + 1] = (id >> 8) & 255; idd[j + 2] = (id >> 16) & 255; idd[j + 3] = 255; ang[i] = a; }
        ybuf = y0; first = false;
      }
      zc += Math.max(o.minStep ?? .5, zc * step);
    }
  }
  // smooth the shapes: each pixel takes the value most of its neighbours have, so the edges of light
  // and shadow are clean curves, not the steps of the march
  const rad = o.smooth ?? 2;
  if (rad > 0) {
    const src = new Uint32Array(W * H), dst = new Uint32Array(W * H);
    for (let i = 0; i < W * H; i++) src[i] = idd[i * 4 + 3] ? (idd[i * 4] | idd[i * 4 + 1] << 8 | idd[i * 4 + 2] << 16) + 1 : 0;
    const cnt = new Map();
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const c0 = src[y * W + x]; if (!c0) { dst[y * W + x] = 0; continue; }
      cnt.clear(); let best = c0, bn = 0;
      for (let dy = -rad; dy <= rad; dy++) { const yy = y + dy; if (yy < 0 || yy >= H) continue; for (let dx = -rad; dx <= rad; dx++) { const xx = x + dx; if (xx < 0 || xx >= W) continue; const c = src[yy * W + xx]; if (!c) continue; const n = (cnt.get(c) || 0) + 1; cnt.set(c, n); if (n > bn) { bn = n; best = c; } } }
      dst[y * W + x] = best;
    }
    const rgbOf = new Map(); for (const c of classes.values()) rgbOf.set(c.id + 1, c.rgb);
    for (let i = 0; i < W * H; i++) {
      const c = dst[i]; if (!c || c === src[i]) continue;
      const rgb = rgbOf.get(c); if (!rgb) continue;
      const j = i * 4, id = c - 1; cd[j] = rgb[0]; cd[j + 1] = rgb[1]; cd[j + 2] = rgb[2]; idd[j] = id & 255; idd[j + 1] = (id >> 8) & 255; idd[j + 2] = (id >> 16) & 255;
    }
  }
  R.ctx.putImageData(col, 0, 0); R.idc.putImageData(idm, 0, 0);
  return { classes: classes.size, dir: dirFn };
}
