"use client";

/**
 * The scroll-driven liquid film behind the home page.
 * Scrolling plays the film forward and rewinds it backwards; HTML chapters sit on top.
 * Draft implementation: a progressive JPEG frame sequence. The production build swaps this for
 * per-chapter MP4s decoded with WebCodecs (WebsiteConcept.md §10) without changing the chapters.
 */
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { CAPABILITIES, CAPABILITIES_HI, CHAPTERS, CHAPTERS_HI, DEMO_QUESTIONS, DEMO_QUESTIONS_HI, FILM } from "@/content/home";
import styles from "./FilmPlayer.module.css";

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));

export default function FilmPlayer({ locale = "en" }: { locale?: "en" | "hi" }) {
  const hi = locale === "hi";
  const CH = hi ? CHAPTERS_HI : CHAPTERS;
  const QUESTIONS = hi ? DEMO_QUESTIONS_HI : DEMO_QUESTIONS;
  const CAPS = hi ? CAPABILITIES_HI : CAPABILITIES;
  const T = hi
    ? { start: "मुफ़्त शुरू करें", watch: "देखिए क्या होता है", demo: "डेमो बुक करें", found: (n: number, t: number) => `${t} में से ${n} खोजे गए`, film: "फ़िल्म" }
    : { start: "Start free", watch: "Watch what happens", demo: "Book a demo", found: (n: number, t: number) => `${n} of ${t} discovered`, film: "Film" };
  const track = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const frames = useRef<(HTMLImageElement | undefined)[]>(new Array(FILM.frames));
  const copies = useRef<(HTMLDivElement | null)[]>([]);
  const [active, setActive] = useState(0);
  const [loaded, setLoaded] = useState(0);
  const [found, setFound] = useState<Set<string>>(new Set());
  const reduced = useRef(false);
  const activeRef = useRef(0);

  const frameAt = useCallback(() => {
    const el = track.current;
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    return Math.round(clamp(-r.top / (r.height - window.innerHeight)) * (FILM.frames - 1));
  }, []);

  const draw = useCallback(() => {
    const cv = canvas.current;
    if (!cv) return;
    const g = cv.getContext("2d");
    const f = frameAt();
    let im: HTMLImageElement | undefined;
    for (let d = 0; d < 80 && !im; d++) im = frames.current[f - d] || frames.current[f + d];
    if (g && im) {
      const s = Math.max(cv.width / im.naturalWidth, cv.height / im.naturalHeight);
      const w = im.naturalWidth * s, h = im.naturalHeight * s;
      g.drawImage(im, (cv.width - w) / 2, (cv.height - h) / 2, w, h);
    }
    // day / night
    const night = f >= FILM.night[0] && f <= FILM.night[1];
    document.documentElement.dataset.theme = night ? "ink" : "paper";
    // chapters
    let current = 0;
    CH.forEach((c, i) => {
      const el = copies.current[i];
      if (!el) return;
      const fade = 18;
      const o = c.kind === "hero" && f <= c.from ? 1 : Math.min(clamp((f - c.from) / fade), clamp((c.to - f) / fade));
      el.style.opacity = String(o);
      el.style.transform = `translateY(${(1 - o) * 14}px)`;
      el.style.pointerEvents = o > 0.6 ? "auto" : "none";
      if (o > 0.5) current = i;
    });
    if (current !== activeRef.current) { activeRef.current = current; setActive(current); }
  }, [frameAt, CH]);

  // size the canvas to the screen
  useEffect(() => {
    reduced.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const size = () => {
      const cv = canvas.current;
      if (!cv) return;
      const d = Math.min(window.devicePixelRatio || 1, 2);
      cv.width = window.innerWidth * d; cv.height = window.innerHeight * d;
      draw();
    };
    size();
    window.addEventListener("resize", size);
    window.addEventListener("scroll", draw, { passive: true });
    return () => {
      window.removeEventListener("resize", size);
      window.removeEventListener("scroll", draw);
      document.documentElement.dataset.theme = "paper";
    };
  }, [draw]);

  // load frames in passes (every 32nd, then 8th, 2nd, all) so scrubbing works immediately;
  // with reduced motion only the chapter key frames are loaded
  useEffect(() => {
    const order: number[] = [];
    const seen = new Set<number>();
    const steps = reduced.current ? [16] : [32, 8, 2, 1];
    for (const step of steps) for (let i = 0; i < FILM.frames; i += step) if (!seen.has(i)) { seen.add(i); order.push(i); }
    let q = 0, n = 0, cancelled = false;
    const next = () => {
      if (cancelled || q >= order.length) return;
      const i = order[q++];
      const im = new Image();
      im.decoding = "async";
      im.onload = () => {
        frames.current[i] = im; n++;
        if (n % 40 === 0 || n === order.length) setLoaded(Math.round((n / order.length) * 100));
        if (Math.abs(i - frameAt()) < 60) draw();
        next();
      };
      im.onerror = next;
      im.src = FILM.src(i);
    };
    for (let k = 0; k < 6; k++) next();
    return () => { cancelled = true; };
  }, [draw, frameAt]);

  // the live demo chapter lights a capability each time the agent answers a topic
  useEffect(() => {
    const on = (e: Event) => {
      const t = (e as CustomEvent<{ topic: string }>).detail.topic;
      setFound((s) => new Set(s).add(t));
    };
    window.addEventListener("fb:answered", on);
    return () => window.removeEventListener("fb:answered", on);
  }, []);

  const jump = (c: (typeof CH)[number]) => {
    const el = track.current;
    if (!el) return;
    const f = (c.from + c.to) / 2;
    window.scrollTo({ top: el.offsetTop + (f / (FILM.frames - 1)) * (el.offsetHeight - window.innerHeight), behavior: "smooth" });
  };
  const ask = (text: string) => window.dispatchEvent(new CustomEvent("fb:ask", { detail: text }));

  return (
    <div ref={track} className={styles.track} style={{ height: FILM.frames * FILM.pxPerFrame }}>
      <div className={styles.stage}>
        <canvas ref={canvas} className={styles.canvas} aria-hidden />
        <div className={styles.veil} aria-hidden />

        {CH.map((c, i) => (
          <section key={c.id} ref={(el) => { copies.current[i] = el as HTMLDivElement | null; }}
                   className={`${styles.copy} ${c.kind === "demo" ? styles.demo : ""} ${hi ? "deva" : ""}`} aria-label={c.label} lang={hi ? "hi" : undefined}>
            <div className="eyebrow">{c.eyebrow}</div>
            {c.kind === "hero"
              ? <h1 className="display">{c.title[0]} <span className="gold">{c.title[1]}</span></h1>
              : <h2 className="h2">{c.title[0]} <span className="gold">{c.title[1]}</span></h2>}
            {c.body && <p className="lead">{c.body}</p>}
            {c.lines && <ul className={styles.lines}>{c.lines.map((l) => <li key={l}>{l}</li>)}</ul>}
            {c.note && <p className="illustrative">{c.note}</p>}
            {c.kind === "hero" && (
              <div className={styles.ctas}>
                <Link href={hi ? "/hi/demo#start" : "/demo#start"} className="btn btn-metal btn-lg">{T.start}</Link>
                <button className="btn btn-ghost btn-lg" onClick={() => jump(CH[2])}>{T.watch}</button>
              </div>
            )}
            {c.kind === "demo" && (
              <>
                <div className={styles.chips}>
                  {QUESTIONS.map((q) => (
                    <button key={q.label} className={`glass ${styles.chip} ${q.hi ? "deva" : ""}`} onClick={() => ask(q.ask)}>{q.label}</button>
                  ))}
                </div>
                <div className={styles.caps}>
                  {CAPS.map((cap) => (
                    <div key={cap.topic} className={`${styles.cap} ${found.has(cap.topic) ? styles.on : ""}`}>
                      <i>{found.has(cap.topic) ? "✓" : ""}</i>
                      <div><b>{cap.title}</b><small>{cap.body}</small></div>
                    </div>
                  ))}
                </div>
                <p className={styles.count}>{T.found(found.size, CAPS.length)}</p>
              </>
            )}
            {c.kind === "start" && (
              <div className={styles.ctas}>
                <Link href={hi ? "/hi/demo#start" : "/demo#start"} className="btn btn-metal btn-lg">{T.start}</Link>
                <Link href="/book-demo" className="btn btn-ghost btn-lg">{T.demo}</Link>
              </div>
            )}
          </section>
        ))}

        <nav className={styles.index} aria-label="Chapters">
          {CH.map((c, i) => (
            <button key={c.id} className={i === active ? styles.current : ""} onClick={() => jump(c)}>{c.label}</button>
          ))}
        </nav>
        {loaded < 100 && <div className={styles.loading}>{T.film} {loaded}%</div>}
      </div>
    </div>
  );
}
