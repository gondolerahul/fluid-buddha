// Test aid, not part of the site. A quick accessibility audit of a world page, run in the browser:
//   JSON.stringify(window.__audit())
// It reports structure, names, hidden-but-focusable controls, and text contrast outside the film.
window.__audit = () => {
  const vis = (el) => { const r = el.getBoundingClientRect(), cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none"; };
  const name = (el) => (el.getAttribute("aria-label") || el.innerText || el.getAttribute("title") || el.querySelector("img")?.alt || "").trim();
  const heads = [...document.querySelectorAll("h1,h2,h3,h4")].map((h) => +h.tagName[1]);
  const skips = []; heads.forEach((l, i) => { if (i && l > heads[i - 1] + 1) skips.push(`h${heads[i - 1]}->h${l}`); });
  const focusable = "a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex='-1'])";
  const hiddenFocus = [...document.querySelectorAll("[aria-hidden='true']")].flatMap((h) => [...h.querySelectorAll(focusable)].filter((f) => !f.closest("[inert]")).map((f) => name(f).slice(0, 30) || f.tagName));

  const parse = (c) => { const m = c.match(/[\d.]+/g)?.map(Number); return m ? { r: m[0], g: m[1], b: m[2], a: m[3] ?? 1 } : null; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (el) => { // nearest solid background colour, blending translucent layers on the way up
    const layers = [];
    for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; } }
    let out = { r: 255, g: 255, b: 255 };
    if (layers.length && layers[layers.length - 1].a >= 1) out = layers.pop();
    layers.reverse().forEach((c) => { out = { r: c.r * c.a + out.r * (1 - c.a), g: c.g * c.a + out.g * (1 - c.a), b: c.b * c.a + out.b * (1 - c.a) }; });
    return out;
  };
  const low = new Map();
  const walker = document.createTreeWalker(document.querySelector(".world"), NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const el = n.parentElement;
    if (!n.data.trim() || !vis(el) || el.closest(".filmtrack") || el.closest("[aria-hidden='true']")) continue;
    const cs = getComputedStyle(el), fg = parse(cs.color);
    if (!fg || cs.webkitTextFillColor === "rgba(0, 0, 0, 0)" || cs.backgroundClip === "text") continue; // gradient text: checked by eye
    const bg = bgOf(el), a = fg.a * parseFloat(cs.opacity || "1");
    const mix = { r: fg.r * a + bg.r * (1 - a), g: fg.g * a + bg.g * (1 - a), b: fg.b * a + bg.b * (1 - a) };
    const l1 = lum(mix), l2 = lum(bg), ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    const size = parseFloat(cs.fontSize), big = size >= 24 || (size >= 18.66 && +cs.fontWeight >= 700);
    if (ratio < (big ? 3 : 4.5)) {
      const key = `${el.tagName.toLowerCase()}.${(el.className || "").toString().split(" ")[0]} ${Math.round(size)}px ${cs.color} on rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`;
      const cur = low.get(key) || { ratio: +ratio.toFixed(2), n: 0, eg: n.data.trim().slice(0, 28) };
      cur.n++; low.set(key, cur);
    }
  }
  const small = [...document.querySelectorAll(".world a[href], .world button")].filter((e) => vis(e) && !e.closest("[aria-hidden='true']")).filter((e) => { const r = e.getBoundingClientRect(); return r.width < 24 || r.height < 24; }).map((e) => `${name(e).slice(0, 24)} ${Math.round(e.getBoundingClientRect().width)}x${Math.round(e.getBoundingClientRect().height)}`);
  return {
    lang: document.documentElement.lang, title: document.title.slice(0, 50),
    h1: document.querySelectorAll("h1").length, headingSkips: [...new Set(skips)],
    landmarks: { main: document.querySelectorAll("main").length, nav: document.querySelectorAll("nav, [role=navigation]").length, header: document.querySelectorAll("header").length, footer: document.querySelectorAll("footer").length },
    skipLink: !!document.querySelector("a[href='#main'], a.skip, a[href='#content']"),
    imgNoAlt: [...document.querySelectorAll("img")].filter((i) => !i.hasAttribute("alt")).length,
    unnamed: [...document.querySelectorAll(".world a[href], .world button")].filter((e) => !name(e)).map((e) => e.outerHTML.slice(0, 60)),
    hiddenFocus: [...new Set(hiddenFocus)].slice(0, 12), hiddenFocusCount: hiddenFocus.length,
    lowContrast: [...low.entries()].map(([k, v]) => `${v.ratio} (${v.n}x) ${k} "${v.eg}"`).sort().slice(0, 25),
    smallTargets: [...new Set(small)].slice(0, 15),
    canvasHidden: [...document.querySelectorAll("canvas")].every((c) => c.getAttribute("aria-hidden") !== null),
  };
};
