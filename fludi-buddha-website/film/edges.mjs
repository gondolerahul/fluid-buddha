// Makes the two painted edges of the default world (web/public/film/paper/):
//   edge.svg    the edge of a brush, where a block of colour meets the page (used as a mask)
//   deckle.svg  the deckled edge of a sheet of handmade paper (used as a mask on the film's sheet)
// Seeded, so they are the same every run.   node film/edges.mjs
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const here = dirname(fileURLToPath(import.meta.url)), out = resolve(here, "../web/public/film/paper");
mkdirSync(out, { recursive: true });
let s = 4242;
const r = () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const lat = Array.from({ length: 900 }, () => r() * 2 - 1);
const sm = (t) => t * t * (3 - 2 * t);
const n1 = (x, o) => { const i = Math.floor(x), f = x - i; return lat[(i + o) % 900] * (1 - sm(f)) + lat[(i + 1 + o) % 900] * sm(f); };
const f = (v) => v.toFixed(1);
// brush edge: a long swell, a shorter wobble, a little bristle chatter
{
  const W = 1200, H = 26, pts = [];
  for (let x = 0; x <= W; x += 6) pts.push([x, Math.max(1.5, Math.min(H - 4, 12 + n1(x / 170, 0) * 6.5 + n1(x / 46, 100) * 3.2 + n1(x / 9, 200) * 1.1))]);
  const d = `M0 ${H}V${f(pts[0][1])}` + pts.slice(1).map(([x, y]) => `L${x} ${f(y)}`).join("") + `V${H}Z`;
  writeFileSync(resolve(out, "edge.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><path d="${d}"/></svg>`);
}
// deckle: four torn sides of a 1000 x 800 sheet, about half a percent deep
{
  const W = 1000, H = 800, a = 5, pts = [];
  const side = (x0, y0, x1, y1, nx, ny, o) => {
    const len = Math.hypot(x1 - x0, y1 - y0), n = Math.round(len / 4);
    for (let i = 0; i < n; i++) {
      const t = i / n, d = t * len, k = (n1(d / 60, o) * 0.6 + n1(d / 13, o + 300) * 0.3 + n1(d / 3.5, o + 600) * 0.1) * a + a;
      pts.push([x0 + (x1 - x0) * t + nx * k, y0 + (y1 - y0) * t + ny * k]);
    }
  };
  side(0, 0, W, 0, 0, 1, 10); side(W, 0, W, H, -1, 0, 120); side(W, H, 0, H, 0, -1, 240); side(0, H, 0, 0, 1, 0, 360);
  const d = "M" + pts.map(([x, y]) => `${f(x)} ${f(y)}`).join("L") + "Z";
  writeFileSync(resolve(out, "deckle.svg"), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><path d="${d}"/></svg>`);
}
console.log("edge.svg, deckle.svg");
