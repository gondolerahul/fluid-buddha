"use client";

/**
 * Decides which world the visitor sees, keeps <html data-world> in step with the route, and performs
 * the morph between worlds (docs/marketing-docs/WebsitePlan.md §3.2 and §3.4).
 *
 * On a world's own page a change of version is a move to another route:
 *   1. the page breaks into a cloud of gold dots (drawn on a canvas),
 *   2. the route changes while the dots cover the screen,
 *   3. the dots clear over the new world.
 * On any other page (pricing, product, …) the same morph re-themes the page in place: the visitor
 * stays where they are and the page takes the chosen version's look and buttons.
 * With reduced motion it is a plain 300 ms cross-fade.
 *
 * It never switches while the visitor is reading: only on a click, on a persona event from the
 * agent, or straight after first paint for a remembered choice.
 */
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { WORLDS } from "@/content/worlds";
import type { WorldId } from "@/content/worlds/types";
import {
  applyWorld, currentWorld, GO_EVENT, isWorld, isWorldPage, remember, remembered, resolveWorld, track,
  worldFromPath, worldFromPersonaEvent, worldPath,
} from "@/lib/world";
import styles from "./WorldSwitch.module.css";

const MORPH_MS = 1600;
const SWAP_AT = 0.45; // fraction of the morph at which the route (or the theme) changes
// each world's main colour and its ink (app/globals.css); the dots are always the brand's gold
const BG: Record<WorldId, string> = { default: "#0a0908", saas: "#0a0908", education: "#f6f2ea", enterprise: "#fffdf9" };
const INK: Record<WorldId, string> = { default: "#f6f1e9", saas: "#f6f1e9", education: "#1a1611", enterprise: "#1a1611" };
const DOT = "237,171,72";

type Morph = { to: WorldId; reduced: boolean };

export default function WorldSwitch() {
  const pathname = usePathname();
  const router = useRouter();
  const [morph, setMorph] = useState<Morph | null>(null);
  const [offer, setOffer] = useState<WorldId | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const busy = useRef(false);
  const path = useRef(pathname);
  useEffect(() => { path.current = pathname; }, [pathname]);

  // <html data-world> follows the route: a world page takes its own world, any other page the
  // visitor's remembered one. (The first paint is already right: app/layout.tsx sets it inline.)
  useEffect(() => {
    if (busy.current) return;
    const own = isWorldPage(pathname) ? worldFromPath(pathname) : null;
    // landing on a persona world's page is a choice too: the rest of the site keeps that version
    if (own && own !== "default") remember(own);
    const r = remembered();
    applyWorld(own ?? (isWorld(r) ? r : "default"));
  }, [pathname]);

  const go = useCallback((to: WorldId, how: string) => {
    const onWorldPage = isWorldPage(path.current);
    const from = currentWorld();
    if (busy.current || to === from) return;
    busy.current = true;
    remember(to);
    setOffer(null);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const total = reduced ? 300 : MORPH_MS;
    track("morph_started", { from, to, how, inPlace: !onWorldPage });
    setMorph({ to, reduced });
    if (onWorldPage) router.prefetch(worldPath(to));
    window.setTimeout(() => {
      if (onWorldPage) { router.push(worldPath(to)); window.scrollTo(0, 0); }
      applyWorld(to);
    }, total * SWAP_AT);
    window.setTimeout(() => { setMorph(null); busy.current = false; track("morph_completed", { to, how }); }, total);
  }, [router]);

  // the selector, the doors, the version switch, the ask stage and the offer all ask through this event
  useEffect(() => {
    const on = (e: Event) => { const d = (e as CustomEvent<{ id: WorldId; how: string }>).detail; go(d.id, d.how); };
    window.addEventListener(GO_EVENT, on);
    return () => window.removeEventListener(GO_EVENT, on);
  }, [go]);

  // the agent identified the visitor in conversation (FR-NAV-04, FR-NAV-05)
  useEffect(() => {
    const on = (e: Event) => { const w = worldFromPersonaEvent((e as CustomEvent).detail); if (w) go(w, "agent"); };
    window.addEventListener("fluidbuddha:set_persona", on);
    return () => window.removeEventListener("fluidbuddha:set_persona", on);
  }, [go]);

  // arriving on the default site: link parameter, remembered choice, referrer
  useEffect(() => {
    if (pathname !== "/") { if (isWorldPage(pathname)) track("world_shown", { world: worldFromPath(pathname) }); return; }
    const r = resolveWorld({ search: window.location.search, referrer: document.referrer, origin: window.location.origin, remembered: remembered() });
    if (!r) { track("world_shown", { world: "default" }); return; }
    if (r.how === "link") {
      remember(r.world);
      track("world_identified", { world: r.world, how: "link" });
      router.replace(worldPath(r.world));
      return;
    }
    if (r.how === "remembered") {
      const t = window.setTimeout(() => go(r.world, "remembered"), 700);
      return () => window.clearTimeout(t);
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the referrer is only known in the browser
    setOffer(r.world);
  }, [pathname, router, go]);

  // measurement: a click on any main button
  useEffect(() => {
    const on = (e: MouseEvent) => {
      const b = (e.target as Element | null)?.closest?.("main .btn-primary");
      if (!b || b.hasAttribute("data-tracked")) return;
      track("cta_clicked", { world: currentWorld(), where: b.closest("section[id]")?.id ?? "page", label: b.textContent?.trim() });
    };
    document.addEventListener("click", on);
    return () => document.removeEventListener("click", on);
  }, []);

  // the cloud of gold dots
  useEffect(() => {
    const cv = canvas.current;
    if (!morph || morph.reduced || !cv) return;
    const g = cv.getContext("2d");
    if (!g) return;
    const d = Math.min(window.devicePixelRatio || 1, 2);
    const w = (cv.width = window.innerWidth * d), h = (cv.height = window.innerHeight * d);
    const step = 24 * d;
    const rgb = DOT;
    const dots: { x: number; y: number; a: number; s: number; p: number }[] = [];
    for (let y = step / 2; y < h; y += step) for (let x = step / 2; x < w; x += step)
      dots.push({ x, y, a: Math.random() * Math.PI * 2, s: 20 + Math.random() * 60, p: Math.random() * 0.25 });
    const t0 = performance.now();
    let raf = 0;
    const draw = (now: number) => {
      const t = Math.min((now - t0) / MORPH_MS, 1);
      g.clearRect(0, 0, w, h);
      for (const o of dots) {
        // each dot swells as the old page dissolves, drifts, then shrinks away over the new page
        const k = Math.max(0, Math.min(1, (t - o.p) / 0.5));
        const out = Math.max(0, (t - 0.55 - o.p * 0.6) / 0.4);
        const size = Math.max(0, Math.sin(Math.min(k, 1) * Math.PI / 2) - out) * 3.2 * d;
        if (size <= 0.05) continue;
        const drift = Math.sin(t * Math.PI) * o.s * d * 0.25;
        g.beginPath();
        g.arc(o.x + Math.cos(o.a) * drift, o.y + Math.sin(o.a) * drift, size, 0, Math.PI * 2);
        g.fillStyle = `rgba(${rgb},${0.35 + 0.65 * (1 - out)})`;
        g.fill();
      }
      if (t < 1) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [morph]);

  return (
    <>
      {morph && (
        <div className={`${styles.morph} ${morph.reduced ? styles.reduced : ""}`} style={{ ["--to" as string]: BG[morph.to], ["--to-ink" as string]: INK[morph.to] }} role="status" aria-live="polite">
          <div className={styles.veil} />
          <canvas ref={canvas} className={styles.dots} aria-hidden />
          <p className={styles.line}>
            {morph.to === "default" ? "Changing back to the general site." : `Changing this site for ${WORLDS[morph.to].audience}.`}
          </p>
        </div>
      )}
      {offer && !morph && (
        <div className={styles.offer} role="dialog" aria-label="A version of this site for you">
          <p>There is a version of this site for <b>{WORLDS[offer].audience}</b>.</p>
          <div>
            <button type="button" className={styles.yes} onClick={() => go(offer, "offer")}>Show it</button>
            <button type="button" className={styles.no} onClick={() => { setOffer(null); track("offer_dismissed", { world: offer }); }}>No thanks</button>
          </div>
        </div>
      )}
    </>
  );
}
