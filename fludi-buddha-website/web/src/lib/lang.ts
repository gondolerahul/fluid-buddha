// The English to Hindi change on a world page (docs/marketing-docs/WebsitePlan.md §3.5).
//
// The server renders English. Every text block that has reviewed Hindi carries it in a `data-hi`
// attribute ("plain|gold|plain" for a headline, plain text otherwise). Changing language rewrites
// those blocks in the browser, one after another from the top of the screen, without a reload.
// A block with no Hindi stays in English: the page never pretends to have a translation.

export type Lang = "en" | "hi";
export const LANG_EVENT = "fb:lang";

const BLOCK_MS = 600;  // one block: English out, Hindi in word by word
const GAP_MS = 250;    // between blocks
const english = new WeakMap<Element, string>();
let current: Lang = "en";
let run = 0;

export const getLang = () => current;

/** "plain|gold|plain" becomes text and a gold span; each word is wrapped so it can fade in on its own. */
function fill(el: HTMLElement, text: string, stagger: boolean) {
  el.textContent = "";
  // one wrapper, so a button laid out with flexbox still sees a single line of text
  const root = document.createElement("span");
  el.append(root);
  const parts = text.split("|");
  const words: HTMLElement[] = [];
  parts.forEach((part, i) => {
    if (!part) return;
    const host = i === 1 && parts.length > 1 ? Object.assign(document.createElement("span"), { className: "em" }) : root;
    part.trim().split(/\s+/).forEach((w, k) => {
      if (k > 0) host.append(" ");
      const s = document.createElement("span");
      s.className = "hw"; s.textContent = w;
      host.append(s); words.push(s);
    });
    if (host !== root) root.append(host);
    if (i < parts.length - 1) root.append(" ");
  });
  if (!stagger) return;
  const each = Math.min(70, (BLOCK_MS * 0.6) / Math.max(1, words.length));
  words.forEach((s, k) => { s.style.opacity = "0"; s.style.transition = `opacity 260ms ease ${Math.round(k * each)}ms`; });
  // read the layout once so the starting opacity is applied, then let the words fade in.
  // (Not requestAnimationFrame: browsers pause it in background tabs and the words would stay hidden.)
  void el.offsetWidth;
  words.forEach((s) => { s.style.opacity = "1"; });
}

function swap(el: HTMLElement, to: Lang, animate: boolean) {
  if (!english.has(el)) english.set(el, el.innerHTML);
  let stagger = false;
  const apply = () => {
    if (to === "hi") { fill(el, el.dataset.hi ?? "", stagger); el.lang = "hi"; el.classList.add("deva"); }
    else { el.innerHTML = english.get(el) ?? ""; el.removeAttribute("lang"); el.classList.remove("deva"); }
  };
  if (!animate) { apply(); return; }
  // reserve the taller of the two heights before the words change, so nothing jumps while they do
  const before = el.offsetHeight, was = el.innerHTML, wasLang = el.lang, wasDeva = el.classList.contains("deva");
  apply();
  const after = el.offsetHeight;
  el.innerHTML = was; el.lang = wasLang; el.classList.toggle("deva", wasDeva);
  if (!wasLang) el.removeAttribute("lang");
  el.style.minHeight = `${Math.max(before, after)}px`;
  el.style.transition = "opacity 180ms ease"; el.style.opacity = "0";
  window.setTimeout(() => {
    stagger = true;
    apply();
    el.style.opacity = "1";
    window.setTimeout(() => { el.style.minHeight = ""; el.style.transition = ""; }, BLOCK_MS);
  }, 190);
}

const onScreen = (el: Element) => {
  const r = el.getBoundingClientRect();
  if (r.bottom < 0 || r.top > window.innerHeight || r.width === 0) return false;
  // a film slide that is not showing counts as off screen
  const slide = el.closest<HTMLElement>(".film-slide");
  return !slide || Number(slide.style.opacity || (slide.classList.contains("first") ? 1 : 0)) > 0.5;
};

/** Changes every block that has Hindi. `instant` skips the animation (first load of a Hindi link). */
export function setLang(to: Lang, instant = false) {
  if (to === current && !instant) return;
  current = to;
  const mine = ++run;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const blocks = [...document.querySelectorAll<HTMLElement>("main [data-hi]")];
  const url = new URL(window.location.href);
  if (to === "hi") url.searchParams.set("lang", "hi"); else url.searchParams.delete("lang");
  window.history.replaceState(window.history.state, "", url);
  window.dispatchEvent(new CustomEvent(LANG_EVENT, { detail: { lang: to } }));

  if (instant || reduced) {
    // reduced motion: one short cross-fade of the whole page
    const world = document.querySelector<HTMLElement>("main");
    if (reduced && !instant && world) { world.style.transition = "opacity 150ms ease"; world.style.opacity = "0"; }
    window.setTimeout(() => {
      blocks.forEach((el) => swap(el, to, false));
      if (world) { world.style.opacity = ""; window.setTimeout(() => { world.style.transition = ""; }, 160); }
    }, reduced && !instant ? 150 : 0);
    return;
  }
  // blocks in view change one after another from the top; the rest change at once, unseen
  const seen = blocks.filter(onScreen).sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
  blocks.filter((el) => !seen.includes(el)).forEach((el) => swap(el, to, false));
  seen.forEach((el, i) => window.setTimeout(() => { if (mine === run) swap(el, to, true); else swap(el, current, false); }, i * (BLOCK_MS * 0.5 + GAP_MS)));
}

/** On every route change: back to English, without touching the page (the new page may still be hydrating). */
export function resetLang() {
  current = "en";
  run++;
  window.dispatchEvent(new CustomEvent(LANG_EVENT, { detail: { lang: "en" } }));
}

/** Called by a page with Hindi once it has hydrated (<LangInit />): English unless its link says ?lang=hi. */
export function initLang() {
  current = "en";
  run++;
  window.dispatchEvent(new CustomEvent(LANG_EVENT, { detail: { lang: "en" } }));
  if (new URLSearchParams(window.location.search).get("lang") === "hi") setLang("hi", true);
}

/** The pages that carry reviewed Hindi (WebsitePlan.md §3.5): each world's page and the pricing page. */
export const HINDI_PAGES = ["/", "/for/saas", "/for/education", "/for/enterprise", "/pricing"];
export const hasHindi = (pathname: string) => HINDI_PAGES.includes(pathname.replace(/\/$/, "") || "/");
