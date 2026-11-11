// The code-drawn stills for the SaaS world (plain characters) and the Enterprise world (flat line
// drawings). Server components: they render to static markup. Phases 5 and 7 animate these same scenes.

import type { SceneId } from "@/content/worlds/types";

// ------------------------------------------------------------------ SaaS: a 128 x 36 character grid
// Only basic ASCII is used: other characters fall back to a different font width and break the grid.
const W = 128, H = 36;
type Grid = string[][];
const grid = (): Grid => Array.from({ length: H }, () => Array<string>(W).fill(" "));
function put(g: Grid, x: number, y: number, s: string) {
  [...s].forEach((ch, i) => { if (g[y] && x + i >= 0 && x + i < W) g[y][x + i] = ch; });
}
function box(g: Grid, x: number, y: number, w: number, h: number, fill = " ") {
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const t = j === 0, b = j === h - 1, l = i === 0, r = i === w - 1;
    const ch = (t || b) && (l || r) ? "+" : t || b ? "-" : l || r ? "|" : fill;
    if (g[y + j]) g[y + j][x + i] = ch;
  }
}
// the seven panels of "your website": nav, hero, side, three cards, pill
const PANELS: Record<string, [number, number, number, number]> = {
  nav: [46, 2, 78, 3], hero: [46, 6, 48, 13], side: [96, 6, 28, 13],
  c1: [46, 20, 24, 10], c2: [73, 20, 24, 10], c3: [100, 20, 24, 10], pill: [46, 31, 18, 3],
};
function site(g: Grid, fills: Record<string, string> = {}) {
  for (const [k, p] of Object.entries(PANELS)) box(g, ...p, fills[k] ?? ".");
}
const QUESTIONS = ["> does it work with our ERP?", "> what do 40 seats cost?", "> where is our data kept?"];

const ASCII: Record<"s1" | "s3" | "s9", (dim: Grid, lit: Grid) => void> = {
  s1(dim, lit) {              // 23:04, a buyer on the pricing card with three questions
    site(dim, { hero: ":" });
    box(lit, ...PANELS.c2, "#");
    put(lit, 76, 22, " PRICING "); put(lit, 76, 24, " INR -------------- "); put(lit, 76, 26, " INR ---------- ");
    put(lit, 91, 18, "@");
    put(lit, 3, 2, "23:04"); put(dim, 3, 4, "sales: offline");
    QUESTIONS.forEach((q, i) => put(lit, 3, 12 + i * 2, q));
    put(dim, 3, 33, "visitors online"); put(lit, 20, 33, "1");
  },
  s3(dim, lit) {              // the integration, drawn while it explains
    site(dim, { hero: " " });
    box(lit, ...PANELS.hero, " ");
    put(dim, 50, 8, "how the integration works");
    box(lit, 50, 10, 11, 5); put(lit, 54, 12, "ERP");
    box(lit, 66, 10, 11, 5); put(lit, 69, 12, "SYNC");
    box(lit, 82, 10, 9, 5); put(lit, 85, 12, "YOU");
    put(lit, 61, 12, "---->"); put(lit, 77, 12, "---->");
    put(lit, 50, 16, "orders . stock . invoices");
    put(lit, 3, 2, "23:05"); put(dim, 3, 4, "answer 1 of 3");
    put(lit, 3, 12, QUESTIONS[0]); put(dim, 3, 14, QUESTIONS[1]); put(dim, 3, 16, QUESTIONS[2]);
    put(dim, 3, 33, "source  /docs/integrations");
  },
  s9(dim, lit) {              // one visitor in ten is held back; the gap is the lift
    put(dim, 3, 2, "visitors"); put(lit, 13, 2, "@ @ @ @ @ @ @ @ @"); put(dim, 31, 2, "o  held back");
    for (let y = 6; y < 31; y++) put(dim, 12, y, "|");
    put(dim, 12, 31, "+" + "-".repeat(110));
    for (let i = 0; i < 108; i++) {
      const x = 14 + i;
      const base = 26 - Math.round(i * 0.03 + Math.sin(i / 9) * 0.6);
      const up = 25 - Math.round(i * 0.12 + Math.sin(i / 11) * 0.8);
      if (i % 2 === 0) put(dim, x, base, ".");
      put(lit, x, up, i % 4 === 0 ? "@" : "-");
      if (i > 30) for (let y = up + 1; y < base; y++) if ((x + y) % 2 === 0) put(dim, x, y, "#");
    }
    put(lit, 100, 9, "with FluidBuddha"); put(dim, 110, 28, "without");
    put(dim, 14, 32, "day 1"); put(dim, 116, 32, "day 30"); put(dim, 3, 34, "example chart");
  },
};
const ASCII_ALT: Record<string, string> = {
  s1: "A website drawn in characters at 23:04, with one visitor on the pricing card and three questions",
  s3: "An integration diagram drawn in characters: ERP to sync to you",
  s9: "A chart drawn in characters: the line with FluidBuddha rises above the line without",
};

function Ascii({ id }: { id: "s1" | "s3" | "s9" }) {
  const dim = grid(), lit = grid();
  ASCII[id](dim, lit);
  const text = (g: Grid) => g.map((r) => r.join("")).join("\n");
  return (
    <div className="ascii" role="img" aria-label={ASCII_ALT[id]}>
      <pre className="dim" aria-hidden>{text(dim)}</pre>
      <pre className="lit" aria-hidden>{text(lit)}</pre>
    </div>
  );
}

// ------------------------------------------------------------------ Enterprise: flat line drawings
/** The seven panels as outlines, 200 x 130, placed at (x, y). */
function Panels({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect className="ln" x="0.6" y="0.6" width="198.8" height="10" /><rect className="ln" x="0.6" y="16" width="124" height="52" /><rect className="ln" x="130" y="16" width="69.4" height="52" />
      <rect className="ln" x="0.6" y="74" width="62" height="40" /><rect className="ln" x="69" y="74" width="62" height="40" /><rect className="ln" x="137.4" y="74" width="62" height="40" /><rect className="ln" x="0.6" y="119.4" width="46" height="10" />
    </g>
  );
}
const DIAGRAM: Record<"r0" | "r1" | "r5" | "r6", { alt: string; body: React.ReactNode }> = {
  r0: {
    alt: "A website drawn inside a dashed boundary labelled your network. A visitor arrives from outside. Speech leaves the boundary.",
    body: (<>
      <rect className="dash" x="120" y="46" width="250" height="186" /><text x="120" y="38">Your network</text>
      <Panels x={145} y={72} />
      <path className="soft" d="M20 139 H112" /><path className="ln" d="M104 134 l8 5 l-8 5" /><text className="mut" x="20" y="130">Visitor</text>
      <path className="ok" d="M352 54 l5 5 l9 -10" />
      <path className="soft" d="M370 180 H452" /><text className="mut" x="386" y="172">Speech</text><text className="mut" x="386" y="196">leaves</text>
    </>),
  },
  r1: {
    alt: "The website inside your network boundary",
    body: (<>
      <rect className="dash" x="120" y="46" width="250" height="186" /><text x="120" y="38">Your network</text>
      <Panels x={145} y={72} /><path className="ok" d="M352 54 l5 5 l9 -10" />
    </>),
  },
  r5: {
    alt: "Blocks pass through a check and are ticked; one is turned away and left out",
    body: (<>
      <g className="ln"><rect x="40" y="112" width="34" height="34" /><rect x="84" y="112" width="34" height="34" /><rect x="128" y="112" width="34" height="34" /></g>
      <path className="soft" d="M170 129 H222" /><path className="ln" d="M214 124 l8 5 l-8 5" />
      <path className="ln" d="M236 80 V190 M262 80 V190 M228 80 H270" /><text x="232" y="70">Check</text>
      <path className="soft" d="M270 129 H300" />
      <g className="ln"><rect x="308" y="112" width="34" height="34" /><rect x="352" y="112" width="34" height="34" /><rect x="396" y="112" width="34" height="34" /></g>
      <g className="ok"><path d="M318 129 l5 5 l9 -10" /><path d="M362 129 l5 5 l9 -10" /><path d="M406 129 l5 5 l9 -10" /></g>
      <g opacity=".35"><rect className="ln" x="232" y="206" width="34" height="34" /><path className="ln" d="M241 215 l16 16 M257 215 l-16 16" /></g><text className="mut" x="276" y="227">Left out</text>
    </>),
  },
  r6: {
    alt: "A price field filled by a line from your systems; the AI is not connected to it",
    body: (<>
      <rect className="ln" x="36" y="92" width="120" height="70" /><text x="52" y="131">Your systems</text>
      <path className="ok" d="M156 127 H300" /><circle className="okfill" cx="300" cy="127" r="3.5" />
      <rect className="ln" x="300" y="56" width="144" height="150" />
      <path className="soft" d="M316 78 H400 M316 92 H376" /><rect className="ok" x="316" y="112" width="112" height="30" /><text x="326" y="131">₹ price</text>
      <path className="soft" d="M316 162 H428 M316 176 H410 M316 190 H390" />
      <rect className="ln" x="76" y="204" width="40" height="30" opacity=".4" /><text className="mut" x="88" y="223">AI</text>
      <path className="dash" d="M116 219 H250" opacity=".4" /><path className="ln" d="M246 213 l12 12 M258 213 l-12 12" />
    </>),
  },
};

export default function Scene({ id }: { id: SceneId }) {
  if (id === "s1" || id === "s3" || id === "s9") return <Ascii id={id} />;
  const d = DIAGRAM[id];
  return <svg className="dia" viewBox="0 0 480 270" role="img" aria-label={d.alt}>{d.body}</svg>;
}
