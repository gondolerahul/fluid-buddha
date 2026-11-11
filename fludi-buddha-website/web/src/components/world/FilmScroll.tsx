"use client";

/**
 * A scroll-driven film that fills the screen. Scrolling plays it forward and rewinds it backwards.
 * The slides (hero copy and chapter copy) are ordinary HTML laid over the picture, each shown for
 * a stretch of the film given as a fraction from 0 to 1.
 *
 * Two kinds of picture:
 *  - `frames`: a rendered film, as an image sequence drawn to the canvas. Frames load in passes
 *    (every 32nd frame, then 8th, 2nd, all) so scrubbing works at once. With reduced motion only
 *    one frame per slide is loaded.
 *  - `code`: a film drawn live from the scroll position (SaaS in characters, Enterprise as line
 *    drawings). Nothing to download. Over the SaaS hero a small light follows the pointer: the
 *    film's own sign for "a visitor".
 *
 * The film is drawn from the scroll event, not from animation frames: browsers pause
 * requestAnimationFrame in background tabs, and one draw per scroll event is cheap. It is the one
 * scroll-linked part of a world page, and it never touches React state while scrolling.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { renderAsciiFilm } from "./asciiFilm";
import { renderLineFilm } from "./lineFilm";
import { track as measure } from "@/lib/world";

/** `mobileDir` holds a lighter set of the same frames, used on narrow screens. */
export type FilmFrames = { dir: string; mobileDir?: string; ext?: "jpg" | "webp"; count: number; pxPerFrame: number; poster: string; portraitTop?: number };
/** `length` is the scroll distance of the whole film, in pixels. */
export type FilmCode = { id: "saas" | "enterprise"; length: number };

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const FADE = 0.012; // fraction of the film over which a slide fades in or out

export default function FilmScroll({ frames, code, ranges, labels, ids, focus, children }: {
  frames?: FilmFrames; code?: FilmCode; ranges: [number, number][]; labels: string[];
  /** One id per slide. A link ending in #<id> opens the film at that chapter. */
  ids: string[];
  /** One value per slide, 0 (left) to 1 (right): where the subject is. Used when the picture is cropped at the sides. */
  focus?: number[];
  children: React.ReactNode[];
}) {
  const count = frames?.count ?? 0;
  const track = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const bar = useRef<HTMLSpanElement>(null);
  const imgs = useRef<(HTMLImageElement | undefined)[]>(new Array(count));
  const slides = useRef<(HTMLDivElement | null)[]>([]);
  const raf = useRef(0);
  const font = useRef("monospace");
  const navH = useRef(0);
  const reduced = useRef(false);
  const seen = useRef(new Set<number>());
  const light = useRef<{ x: number; y: number } | null>(null);
  const colors = useRef({ fg: "#14110f", accent: "#b9791a" });
  const [loading, setLoading] = useState(!!frames);
  const [active, setActive] = useState(0);
  const activeRef = useRef(0);
  const dir = useRef(frames?.dir ?? "");
  const ext = frames?.ext ?? "jpg";
  const src = useCallback((i: number) => `${dir.current}/f${String(i + 1).padStart(5, "0")}.${ext}`, [ext]);

  const progress = useCallback(() => {
    const el = track.current;
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    return clamp(-r.top / Math.max(1, r.height - window.innerHeight));
  }, []);

  const draw = useCallback(() => {
    raf.current = 0;
    const p = progress();
    const cv = canvas.current;
    const g = cv?.getContext("2d");
    if (cv && g) {
      // Reduced motion: a drawn film does not move with the scroll. It steps from one finished
      // picture to the next, one per slide.
      let pd = p;
      if (code && reduced.current) {
        let k = ranges.findIndex(([, b]) => p <= b);
        if (k < 0) k = ranges.length - 1;
        pd = k === 0 ? 0 : ranges[k][0] + (ranges[k][1] - ranges[k][0]) * 0.75;
      }
      if (code?.id === "enterprise") renderLineFilm(g, cv.width, cv.height, pd, { font: font.current, top: navH.current, ...colors.current });
      else if (code) renderAsciiFilm(g, cv.width, cv.height, pd, { font: font.current, top: navH.current, light: p < ranges[0][1] + 0.01 ? light.current : null });
      else {
        const f = Math.round(p * (count - 1));
        let im: HTMLImageElement | undefined;
        for (let d = 0; d < 96 && !im; d++) im = imgs.current[f - d] || imgs.current[f + d];
        if (im) {
          // upright screens can show the picture in the top part only, with the copy below it
          const upright = !!frames?.portraitTop && cv.width < cv.height * 0.8;
          const area = upright ? cv.height * frames!.portraitTop! : cv.height;
          const s = Math.max(cv.width / im.naturalWidth, area / im.naturalHeight);
          const w = im.naturalWidth * s, h = im.naturalHeight * s;
          // Where the subject is at this point of the film: between the two nearest slides' values.
          let fx = 0.5;
          if (focus && w > cv.width) {
            const mids = ranges.map(([a, b]) => (a + b) / 2);
            let k = mids.findIndex((m) => p < m);
            if (k < 0) k = mids.length;
            const i0 = Math.max(0, k - 1), i1 = Math.min(mids.length - 1, k);
            const t = i0 === i1 ? 0 : clamp((p - mids[i0]) / (mids[i1] - mids[i0]));
            fx = (focus[i0] ?? 0.5) + ((focus[i1] ?? 0.5) - (focus[i0] ?? 0.5)) * t;
          }
          const x = clamp(fx * w - cv.width / 2, 0, w - cv.width);
          if (upright) g.clearRect(0, 0, cv.width, cv.height);
          g.drawImage(im, -x, (area - h) / 2, w, h);
        }
      }
    }
    let current = 0;
    ranges.forEach(([from, to], i) => {
      const el = slides.current[i];
      if (!el) return;
      const o = i === 0 && p <= from ? 1 : Math.min(clamp((p - from) / FADE), clamp((to - p) / FADE));
      el.style.opacity = String(o);
      el.style.transform = `translateY(${(1 - o) * 16}px)`;
      el.style.filter = o < 1 ? `blur(${(1 - o) * 6}px)` : "";
      el.style.pointerEvents = o > 0.6 ? "auto" : "none";
      el.setAttribute("aria-hidden", o > 0.5 ? "false" : "true");
      // a slide that is not showing must not take keyboard focus either
      el.inert = o <= 0.5;
      if (o > 0.5) current = i;
    });
    if (current !== activeRef.current) {
      activeRef.current = current; setActive(current);
      // measurement: the first time each chapter is reached
      if (current > 0 && !seen.current.has(current)) { seen.current.add(current); measure("film_chapter", { chapter: ids[current], index: current }); }
    }
  }, [code, count, focus, frames, ids, progress, ranges]);

  const schedule = useCallback(() => { if (!raf.current) raf.current = requestAnimationFrame(draw); }, [draw]);

  useEffect(() => {
    reduced.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const size = () => {
      const cv = canvas.current;
      if (!cv) return;
      const d = Math.min(window.devicePixelRatio || 1, 2);
      cv.width = window.innerWidth * d; cv.height = window.innerHeight * d;
      const cs = getComputedStyle(cv);
      font.current = cs.fontFamily || "monospace";
      // the line film is drawn in the page's own colours
      colors.current = { fg: cs.color || "#14110f", accent: cs.getPropertyValue("--accent").trim() || "#b9791a" };
      navH.current = (document.querySelector<HTMLElement>(".hdr")?.offsetHeight ?? 0) * d;
      draw();
    };
    size();
    // the character film needs its font before the first frame is right
    document.fonts?.ready.then(size).catch(() => {});
    window.addEventListener("resize", size);
    // also when the stage itself changes size without a window resize event (mobile address bar, device emulation)
    const ro = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(size);
    if (ro && canvas.current) ro.observe(canvas.current);
    window.addEventListener("scroll", draw, { passive: true });
    // the colours change when the visitor switches version in place
    const mo = new MutationObserver(size);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-world"] });
    return () => { ro?.disconnect(); mo.disconnect(); window.removeEventListener("resize", size); window.removeEventListener("scroll", draw); cancelAnimationFrame(raf.current); };
  }, [draw]);

  // the SaaS hero: a small light follows a fine pointer across the characters
  useEffect(() => {
    if (code?.id !== "saas" || reduced.current || !window.matchMedia("(pointer: fine)").matches) return;
    const stage = canvas.current?.parentElement;
    if (!stage) return;
    const d = Math.min(window.devicePixelRatio || 1, 2);
    const move = (e: PointerEvent) => { light.current = { x: e.clientX * d, y: e.clientY * d }; schedule(); };
    const leave = () => { light.current = null; schedule(); };
    stage.addEventListener("pointermove", move);
    stage.addEventListener("pointerleave", leave);
    return () => { stage.removeEventListener("pointermove", move); stage.removeEventListener("pointerleave", leave); };
  }, [code, schedule]);

  useEffect(() => {
    if (!frames) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    dir.current = frames.mobileDir && window.innerWidth < 768 ? frames.mobileDir : frames.dir;
    const order: number[] = [];
    const added = new Set<number>();
    const add = (i: number) => { const k = Math.round(clamp(i, 0, frames.count - 1)); if (!added.has(k)) { added.add(k); order.push(k); } };
    if (reduced) ranges.forEach(([a, b]) => add(((a + b) / 2) * (frames.count - 1)));
    else {
      // on a slow or data-saving connection, a quarter of the frames is enough to scrub with
      const c = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
      const light = !!c && (c.saveData || /(^|-)(2g|3g)$/.test(c.effectiveType ?? ""));
      for (const step of light ? [32, 8, 4] : [32, 8, 2, 1]) for (let i = 0; i < frames.count; i += step) add(i);
    }
    let q = 0, n = 0, cancelled = false;
    const next = () => {
      if (cancelled || q >= order.length) return;
      const i = order[q++];
      const im = new Image();
      im.decoding = "async";
      im.onload = () => {
        imgs.current[i] = im; n++;
        if (bar.current) bar.current.style.transform = `scaleX(${n / order.length})`;
        if (n === order.length) setLoading(false);
        schedule();
        next();
      };
      im.onerror = next;
      im.src = src(i);
    };
    for (let k = 0; k < 6; k++) next();
    return () => { cancelled = true; };
  }, [frames, ranges, schedule, src]);

  const jump = useCallback((i: number, behavior: ScrollBehavior = "smooth") => {
    const el = track.current;
    if (!el) return;
    const [a, b] = ranges[i];
    const p = i === 0 ? 0 : (a + b) / 2;
    window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY + p * (el.offsetHeight - window.innerHeight), behavior });
  }, [ranges]);

  // a link to #<chapter id> opens the film at that chapter
  useEffect(() => {
    const go = () => { const i = ids.indexOf(window.location.hash.slice(1)); if (i > 0) { jump(i, "auto"); draw(); } };
    go();
    const click = (e: MouseEvent) => {
      const a = (e.target as Element | null)?.closest?.("a[href^='#']");
      const i = a ? ids.indexOf(a.getAttribute("href")!.slice(1)) : -1;
      if (i > 0) { e.preventDefault(); jump(i); history.replaceState(history.state, "", `#${ids[i]}`); }
    };
    window.addEventListener("hashchange", go);
    document.addEventListener("click", click);
    return () => { window.removeEventListener("hashchange", go); document.removeEventListener("click", click); };
  }, [ids, jump, draw]);

  const length = frames ? frames.count * frames.pxPerFrame : code?.length ?? 0;
  return (
    <div ref={track} className="film-track" style={{ height: `calc(${length}px + 100vh)` }}>
      <div className={`film-stage${code ? ` drawn drawn-${code.id}` : ""}`} style={frames ? { backgroundImage: `url('${frames.poster}')` } : undefined} data-upright={frames?.portraitTop ? "" : undefined}>
        <canvas ref={canvas} aria-hidden />
        <div className="film-veil" aria-hidden />
        {children.map((c, i) => (
          <div key={i} ref={(el) => { slides.current[i] = el; }} className={`film-slide${i === 0 ? " first" : ""}`}>{c}</div>
        ))}
        <nav className="film-rail" aria-label="Film chapters">
          {labels.map((l, i) => (
            <button key={ids[i]} type="button" aria-current={i === active ? "step" : undefined} onClick={() => jump(i)}>
              <i aria-hidden /><span>{l}</span>
            </button>
          ))}
        </nav>
        {loading && <span className="film-load" aria-hidden><span ref={bar} /></span>}
      </div>
    </div>
  );
}
