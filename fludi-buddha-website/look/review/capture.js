// Test aid, not part of the site. Paste into the browser console on a world page (or run from a test
// tool) to capture a scroll film at several points, with the slide copy drawn on top, and POST each
// picture as a data URL to a local receiver.  await window.__cap('name', [0.02, 0.5], 'http://127.0.0.1:5199')
window.__cap = async (pre, ps, to) => {
  await document.fonts.ready;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  const t = document.querySelector(".filmtrack");
  const top = t.getBoundingClientRect().top + scrollY, L = t.offsetHeight - innerHeight;
  const out = [];
  for (let i = 0; i < ps.length; i++) {
    scrollTo(0, top + ps[i] * L);
    window.dispatchEvent(new Event("scroll"));
    await wait(350);
    const cv = document.querySelector(".filmstage canvas"), d = cv.width / innerWidth;
    const o = document.createElement("canvas"); o.width = cv.width; o.height = cv.height;
    const g = o.getContext("2d");
    g.fillStyle = getComputedStyle(document.querySelector(".filmstage")).backgroundColor; g.fillRect(0, 0, o.width, o.height);
    g.drawImage(cv, 0, 0);
    const s = [...document.querySelectorAll(".filmslide")].find((e) => +e.style.opacity > 0.5);
    let box = null;
    if (s) {
      if (s.classList.contains("first") && getComputedStyle(s).backgroundImage !== "none") {
        const narrow = innerWidth <= 900;
        const gr = narrow ? g.createLinearGradient(0, o.height, 0, 0) : g.createLinearGradient(0, 0, o.width, 0);
        if (narrow) { gr.addColorStop(0, "rgba(14,11,8,.9)"); gr.addColorStop(0.3, "rgba(14,11,8,.9)"); gr.addColorStop(0.7, "rgba(14,11,8,.35)"); gr.addColorStop(1, "rgba(14,11,8,.2)"); }
        else { gr.addColorStop(0, "rgba(14,11,8,.78)"); gr.addColorStop(0.36, "rgba(14,11,8,.5)"); gr.addColorStop(0.62, "rgba(14,11,8,0)"); }
        g.fillStyle = gr; g.fillRect(0, 0, o.width, o.height);
      }
      for (const el of s.querySelectorAll(".plate, .btn, .lang span, .chips button, .chips a")) {
        const cs = getComputedStyle(el), b = el.getBoundingClientRect();
        if (cs.backgroundColor === "rgba(0, 0, 0, 0)" || !b.width) continue;
        g.fillStyle = cs.backgroundColor; g.beginPath();
        g.roundRect(b.left * d, b.top * d, b.width * d, b.height * d, Math.min(parseFloat(cs.borderTopLeftRadius) || 0, b.height / 2) * d); g.fill();
        if (el.classList.contains("plate")) box = [b.left | 0, b.top | 0, b.right | 0, b.bottom | 0];
      }
      g.textBaseline = "alphabetic";
      const w = document.createTreeWalker(s, NodeFilter.SHOW_TEXT); let n;
      while ((n = w.nextNode())) {
        const cs = getComputedStyle(n.parentElement); const re = /\S+/g; let m;
        while ((m = re.exec(n.data))) {
          const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
          const b = r.getBoundingClientRect(); if (!b.width) continue;
          g.font = `${cs.fontStyle} ${cs.fontWeight} ${parseFloat(cs.fontSize) * d}px ${cs.fontFamily}`;
          g.fillStyle = cs.color === "rgba(0, 0, 0, 0)" ? "#edab48" : cs.color;
          g.fillText(cs.textTransform === "uppercase" ? m[0].toUpperCase() : m[0], b.left * d, (b.bottom - b.height * 0.22) * d);
        }
      }
    }
    const st = await fetch(to + "/" + pre + i, { method: "POST", body: o.toDataURL("image/jpeg", 0.85) }).then((r) => r.status).catch((e) => String(e));
    out.push([st, box]);
  }
  return JSON.stringify({ w: innerWidth, h: innerHeight, sw: document.documentElement.scrollWidth, loading: document.querySelector(".filmloading")?.textContent ?? "done", out });
};
