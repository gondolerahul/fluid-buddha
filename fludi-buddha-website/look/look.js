// Phase 2 look pages: role chips and the character-drawn stills for the SaaS world.

// ---- role chips: swap the hero sub-line and the two buttons
document.querySelectorAll("[data-roles]").forEach((box) => {
  const roles = JSON.parse(box.dataset.roles);
  const sub = document.querySelector("[data-sub]");
  const b1 = document.querySelector("[data-b1]");
  const b2 = document.querySelector("[data-b2]");
  box.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const r = roles[btn.dataset.role];
      box.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
      sub.textContent = r[0]; b1.textContent = r[1]; b2.textContent = r[2];
    });
  });
});

// ---- character stills: a 128 x 36 grid with a dim layer and a lit (gold) layer
const W = 128, H = 36;
function grid() { return Array.from({ length: H }, () => Array(W).fill(" ")); }
function put(g, x, y, s) { [...s].forEach((ch, i) => { if (g[y] && x + i >= 0 && x + i < W) g[y][x + i] = ch; }); }
function box(g, x, y, w, h, fill) {
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const t = j === 0, b = j === h - 1, l = i === 0, r = i === w - 1;
    let ch = fill || " ";
    if (t && l) ch = "+"; else if (t && r) ch = "+"; else if (b && l) ch = "+"; else if (b && r) ch = "+";
    else if (t || b) ch = "-"; else if (l || r) ch = "|";
    if (g[y + j]) g[y + j][x + i] = ch;
  }
}
// the seven panels of "your website": nav, hero, side, three cards, pill
const PANELS = { nav: [46, 2, 78, 3], hero: [46, 6, 48, 13], side: [96, 6, 28, 13], c1: [46, 20, 24, 10], c2: [73, 20, 24, 10], c3: [100, 20, 24, 10], pill: [46, 31, 18, 3] };
function site(g, fills = {}) { for (const [k, p] of Object.entries(PANELS)) box(g, ...p, fills[k] ?? "."); }
const QUESTIONS = ["> does it work with our ERP?", "> what do 40 seats cost?", "> where is our data kept?"];

const SCENES = {
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
    box(lit, 50, 10, 11, 5, " "); put(lit, 54, 12, "ERP");
    box(lit, 66, 10, 11, 5, " "); put(lit, 69, 12, "SYNC");
    box(lit, 82, 10, 9, 5, " "); put(lit, 85, 12, "YOU");
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
document.querySelectorAll("[data-ascii]").forEach((el) => {
  const dim = grid(), lit = grid();
  SCENES[el.dataset.ascii](dim, lit);
  const text = (g) => g.map((r) => r.join("")).join("\n");
  el.innerHTML = `<pre class="dim" aria-hidden="true"></pre><pre class="lit" aria-hidden="true"></pre>`;
  el.children[0].textContent = text(dim); el.children[1].textContent = text(lit);
});
