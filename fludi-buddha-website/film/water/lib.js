// Numbers, easing, repeatable chance and the film's palette.
import { hex, mixc } from './engine/impasto.js';

export const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const seg = (t, a, b) => clamp((t - a) / (b - a));
/** smoothstep on 0..1 */
export const ss = (t) => { t = clamp(t); return t * t * (3 - 2 * t); };
/** smoother step (zero speed and zero acceleration at both ends): camera moves */
export const sm = (t) => { t = clamp(t); return t * t * t * (t * (t * 6 - 15) + 10); };
export const eo = (t) => 1 - Math.pow(1 - clamp(t), 3);
export const ei = (t) => Math.pow(clamp(t), 3);
export const eio = (t) => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
export const back = (t, s = 1.7) => { t = clamp(t) - 1; return 1 + t * t * ((s + 1) * t + s); };
export const TAU = Math.PI * 2;

/** A repeatable number in 0..1 from one or two numbers. */
export const hash = (n) => { n = Math.sin(n * 127.1 + 311.7) * 43758.5453; return n - Math.floor(n); };
export const hash2 = (x, y) => { const n = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return n - Math.floor(n); };
/** A repeatable sequence: rng = mulberry(7); rng() -> 0..1 */
export const mulberry = (a) => () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };

/** Smooth noise, 0..1, in one and two dimensions, and layered. */
export const noise1 = (x, s = 0) => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash(i + s * 57.3), hash(i + 1 + s * 57.3), u); };
export const noise2 = (x, y, s = 0) => {
  const ix = Math.floor(x), iy = Math.floor(y), fx = x - ix, fy = y - iy, ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy);
  const h = (a, b) => hash2(a + s * 17.17, b - s * 9.31);
  return lerp(lerp(h(ix, iy), h(ix + 1, iy), ux), lerp(h(ix, iy + 1), h(ix + 1, iy + 1), ux), uy);
};
export const fbm1 = (x, oct = 4, s = 0) => { let v = 0, a = .5, n = 0; for (let i = 0; i < oct; i++) { v += noise1(x, s + i * 3.1) * a; n += a; x *= 2.03; a *= .5; } return v / n; };
export const fbm2 = (x, y, oct = 4, s = 0) => { let v = 0, a = .5, n = 0; for (let i = 0; i < oct; i++) { v += noise2(x, y, s + i * 3.1) * a; n += a; x *= 2.03; y *= 2.03; a *= .5; } return v / n; };

/** Keyframes: key(t, [[t0, v0, ease?], [t1, v1], ...]); v is a number or a list of numbers. */
export const key = (t, ks) => {
  if (t <= ks[0][0]) return ks[0][1];
  for (let i = 0; i < ks.length - 1; i++) {
    const [t0, v0, e] = ks[i], [t1, v1] = ks[i + 1];
    if (t < t1) { const k = (e || sm)((t - t0) / (t1 - t0)); return Array.isArray(v0) ? v0.map((v, j) => lerp(v, v1[j], k)) : lerp(v0, v1, k); }
  }
  return ks[ks.length - 1][1];
};
export const linear = (x) => x;

// ---------------------------------------------------------------- the palette
// Three tubes, from the Buddha Cognitive Lab design system: ink, paper white and gold. Every colour
// in the film is a mix of them, so the picture can never leave the brand.
export const INK = hex('#0a0908'), PAPER = hex('#f6f2ea'), WHITE = hex('#fffdf9');
export const GOLD = hex('#edab48'), GOLD_L = hex('#fdc871'), GOLD_XL = hex('#ffe6bd'), GOLD_D = hex('#a8722a'), GOLD_DD = hex('#7d551f'), GOLD_INK = hex('#4f3614');

/** A grey: 0 is ink, 1 is paper white. */
export const tone = (k) => mixc(INK, WHITE, clamp(k));
/** A grey warmed with gold: g is how much gold is mixed in (0..1). */
export const warm = (k, g = 0, gold = GOLD) => mixc(tone(k), gold, clamp(g));
export const mix3 = mixc;
/** For the reference drawings: a colour as a CSS string. */
export const css = (c, a = 1) => `rgba(${Math.round(clamp(c[0]) * 255)},${Math.round(clamp(c[1]) * 255)},${Math.round(clamp(c[2]) * 255)},${a})`;
export const K = (k, g = 0, gold = GOLD) => css(warm(k, g, gold));

// ---------------------------------------------------------------- drawing helpers for the reference pictures
export const P = (pts) => (c) => { c.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); c.closePath(); };
export const PL = (pts) => (c) => { c.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); };
export const EL = (x, y, rx, ry, rot = 0) => (c) => c.ellipse(x, y, rx, ry, rot, 0, TAU);
export const RECT = (x, y, w, h) => (c) => c.rect(x, y, w, h);
export const lin = (x0, y0, x1, y1, stops) => (c) => { const g = c.createLinearGradient(x0, y0, x1, y1); stops.forEach(([o, col]) => g.addColorStop(o, col)); return g; };
export const rad = (x, y, r0, r1, stops) => (c) => { const g = c.createRadialGradient(x, y, r0, x, y, r1); stops.forEach(([o, col]) => g.addColorStop(o, col)); return g; };

// affine [a,b,c,d,e,f]: x' = a x + c y + e, y' = b x + d y + f
export const mul = (A, B) => [A[0] * B[0] + A[2] * B[1], A[1] * B[0] + A[3] * B[1], A[0] * B[2] + A[2] * B[3], A[1] * B[2] + A[3] * B[3], A[0] * B[4] + A[2] * B[5] + A[4], A[1] * B[4] + A[3] * B[5] + A[5]];
export const TR = (x, y) => [1, 0, 0, 1, x, y];
export const SC = (s, sy = s) => [s, 0, 0, sy, 0, 0];
export const RO = (a) => [Math.cos(a), Math.sin(a), -Math.sin(a), Math.cos(a), 0, 0];
export const about = (px, py, a) => mul(TR(px, py), mul(RO(a), TR(-px, -py)));
export const bez = (a, b, c, d, u) => { const v = 1 - u; return [v * v * v * a[0] + 3 * v * v * u * b[0] + 3 * v * u * u * c[0] + u * u * u * d[0], v * v * v * a[1] + 3 * v * v * u * b[1] + 3 * v * u * u * c[1] + u * u * u * d[1]]; };
