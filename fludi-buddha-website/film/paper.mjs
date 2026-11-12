// Makes the sheet of paper the default world is painted on: web/public/film/paper/paper.webp.
// A 1024 px tile (shown at 512 CSS px) that repeats without a seam: a near-white ground, three octaves
// of soft noise, a fine grain and a few thousand short curved fibres. Seeded, so it is the same every run.
//   node film/paper.mjs            (run from fludi-buddha-website; uses web/node_modules/sharp)
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(here, "../web/") + "/");
const sharp = require("sharp");

const N = 1024;
const BASE = [246, 242, 234]; // the design system's paper, #f6f2ea
let seed = 20261112;
const rnd = () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };

// tileable value noise: a lattice of `cells` x `cells` random values, wrapped
function lattice(cells) { const a = new Float32Array(cells * cells); for (let i = 0; i < a.length; i++) a[i] = rnd() * 2 - 1; return { a, cells }; }
const smooth = (t) => t * t * (3 - 2 * t);
function sample(l, x, y) {
  const c = l.cells, fx = (x / N) * c, fy = (y / N) * c, x0 = Math.floor(fx), y0 = Math.floor(fy), tx = smooth(fx - x0), ty = smooth(fy - y0);
  const g = (i, j) => l.a[((j % c + c) % c) * c + ((i % c + c) % c)];
  return (g(x0, y0) * (1 - tx) + g(x0 + 1, y0) * tx) * (1 - ty) + (g(x0, y0 + 1) * (1 - tx) + g(x0 + 1, y0 + 1) * tx) * ty;
}
const octaves = [[lattice(5), 3.2], [lattice(13), 2.2], [lattice(41), 1.4]];

const lum = new Float32Array(N * N);
for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
  let v = 0;
  for (const [l, amp] of octaves) v += sample(l, x, y) * amp;
  lum[y * N + x] = v + (rnd() - 0.5) * 3.2; // the fine grain
}
// fibres: short curved hairs, most a little darker than the sheet, some lighter
function dab(x, y, v) {
  const x0 = Math.floor(x), y0 = Math.floor(y), fx = x - x0, fy = y - y0;
  for (const [dx, dy, w] of [[0, 0, (1 - fx) * (1 - fy)], [1, 0, fx * (1 - fy)], [0, 1, (1 - fx) * fy], [1, 1, fx * fy]])
    lum[(((y0 + dy) % N + N) % N) * N + (((x0 + dx) % N + N) % N)] += v * w;
}
for (let i = 0; i < 3400; i++) {
  let x = rnd() * N, y = rnd() * N, a = rnd() * Math.PI * 2;
  const len = 14 + rnd() * 46, bend = (rnd() - 0.5) * 0.09, v = (rnd() < 0.72 ? -1 : 0.8) * (2.2 + rnd() * 4.2);
  for (let s = 0; s < len; s += 0.7) { dab(x, y, v * Math.sin((s / len) * Math.PI)); a += bend; x += Math.cos(a) * 0.7; y += Math.sin(a) * 0.7; }
}

const px = Buffer.alloc(N * N * 3);
for (let i = 0; i < N * N; i++) {
  const v = lum[i];
  // fibres and hollows lean very slightly warm, like cotton rag
  px[i * 3] = Math.max(0, Math.min(255, Math.round(BASE[0] + v)));
  px[i * 3 + 1] = Math.max(0, Math.min(255, Math.round(BASE[1] + v * 1.02)));
  px[i * 3 + 2] = Math.max(0, Math.min(255, Math.round(BASE[2] + v * 1.12)));
}
const out = resolve(here, "../web/public/film/paper/paper.webp");
mkdirSync(dirname(out), { recursive: true });
await sharp(px, { raw: { width: N, height: N, channels: 3 } }).webp({ quality: 93, effort: 6 }).toFile(out);
const stats = await sharp(out).stats();
console.log(out, "mean", stats.channels.map((c) => c.mean.toFixed(1)).join(" "));
