"use client";

/**
 * One finished picture from a drawn film, as a still: the painted film (default world), the
 * character film (SaaS) or the line film (Enterprise), drawn into a canvas that fills its box.
 * It is drawn when it first comes near the screen, and again when its box or the world changes.
 */
import { useEffect, useRef } from "react";
import { renderAsciiFilm } from "./asciiFilm";
import { renderLineFilm } from "./lineFilm";
import { renderWashFilm } from "./washFilm";

let PAPER: Promise<HTMLImageElement | null> | null = null;
/** The paper tile, loaded once for every painted still on the page. */
function paper(): Promise<HTMLImageElement | null> {
  return (PAPER ??= new Promise((done) => {
    const im = new Image();
    im.decoding = "async";
    im.onload = () => done(im);
    im.onerror = () => done(null);
    im.src = "/film/paper/paper.webp";
  }));
}

export default function FilmStill({ kind, at, cam, className = "", label }: {
  kind: "wash" | "ascii" | "line";
  /** The moment of the film, 0 to 1. */
  at: number;
  /** Painted film only: look at this part of the sheet instead ([x, y, zoom]). */
  cam?: [number, number, number];
  className?: string;
  /** Says what the picture shows. Without it the picture is treated as decoration. */
  label?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    let sheet: HTMLImageElement | null = null, seen = false, live = true;
    const draw = () => {
      // not on screen yet, or belonging to a world that is not showing
      if (!seen || !cv.clientWidth || !cv.clientHeight) return;
      const d = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.round(cv.clientWidth * d), h = Math.round(cv.clientHeight * d);
      if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
      const g = cv.getContext("2d");
      if (!g) return;
      const cs = getComputedStyle(cv);
      if (kind === "wash") renderWashFilm(g, w, h, at, { dpr: d, top: 0, paper: sheet, hand: cs.fontFamily || "monospace", intro: 1, layout: "fill", cam });
      else if (kind === "line") renderLineFilm(g, w, h, at, { font: cs.fontFamily || "sans-serif", fg: cs.color, accent: cs.getPropertyValue("--gold").trim() || "#edab48" });
      else renderAsciiFilm(g, w, h, at, { font: cs.fontFamily || "monospace", dpr: d });
    };
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { seen = true; draw(); } }, { rootMargin: "300px" });
    io.observe(cv);
    const ro = new ResizeObserver(draw);
    ro.observe(cv);
    const mo = new MutationObserver(draw);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-world"] });
    if (kind === "wash") paper().then((im) => { if (live) { sheet = im; draw(); } });
    // a canvas does not ask for a web font by itself: load the one this film writes in, then draw again
    const cs = getComputedStyle(cv);
    const face = `${kind === "ascii" ? 400 : 500} 13px ${cs.fontFamily}`;
    document.fonts?.load(face).then(() => live && draw()).catch(() => {});
    return () => { live = false; io.disconnect(); ro.disconnect(); mo.disconnect(); };
  }, [kind, at, cam]);
  return <canvas ref={ref} className={`still still-${kind} ${className}`} role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true} />;
}
