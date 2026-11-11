"use client";

// The small interactive parts of a world page: the link that changes world, the role chips,
// and the "Showing the … version" chip in the nav.

import { useEffect, useRef, useState } from "react";
import type { Role, WorldId } from "@/content/worlds/types";
import { goWorld, track, worldPath } from "@/lib/world";
import { getLang, initLang, LANG_EVENT, setLang, type Lang } from "@/lib/lang";

/** The language now on screen. Follows the switch, wherever it was pressed. */
function useLang(init = false) {
  const [lang, set] = useState<Lang>("en");
  useEffect(() => {
    const on = (e: Event) => set((e as CustomEvent<{ lang: Lang }>).detail.lang);
    window.addEventListener(LANG_EVENT, on);
    // a page always starts in English, unless its link says ?lang=hi
    if (init) initLang();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the language of a shared link is only known in the browser
    set(getLang());
    return () => window.removeEventListener(LANG_EVENT, on);
  }, [init]);
  return lang;
}

/**
 * The English / Hindi switch (WebsitePlan.md §3.5). Shown only on pages that have reviewed Hindi.
 * "nav" is the button in the nav bar; "pill" is the two-part switch in a hero.
 */
export function LangSwitch({ world, variant = "nav" }: { world: WorldId; variant?: "nav" | "pill" }) {
  const lang = useLang(variant === "nav");
  const go = (to: Lang) => { if (to === lang) return; setLang(to); track("lang_switched", { world, to }); };
  if (variant === "pill") {
    return (
      <div className="lang" role="group" aria-label="Language">
        <button type="button" className={lang === "en" ? "on" : undefined} aria-pressed={lang === "en"} onClick={() => go("en")}>English</button>
        <button type="button" lang="hi" className={`deva${lang === "hi" ? " on" : ""}`} aria-pressed={lang === "hi"} onClick={() => go("hi")}>हिंदी</button>
      </div>
    );
  }
  return (
    <button type="button" className="langbtn" onClick={() => go(lang === "en" ? "hi" : "en")}
            aria-label={lang === "en" ? "Show this page in Hindi" : "Showing Hindi. Change to English"}>
      {lang === "en" ? <span lang="hi" className="deva">हिंदी</span> : <>Showing Hindi · <u>English</u></>}
    </button>
  );
}

/** A link to another world. With JavaScript it morphs; without it, it is an ordinary link. */
export function GoWorld({ to, how = "selector", className, style, children }: {
  to: WorldId; how?: "selector" | "chip" | "offer"; className?: string; style?: React.CSSProperties; children: React.ReactNode;
}) {
  return (
    <a href={worldPath(to)} className={className} style={style}
       onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); goWorld(to, how); }}>
      {children}
    </a>
  );
}

/** Role chips under the hero. A role changes words only: the sub-line and the two buttons. */
export function RoleBlock({ world, roles, primaryHref, secondaryHref, hi }: {
  world: WorldId; roles: Role[]; primaryHref: string; secondaryHref: string;
  /** Reviewed Hindi for the first role's sub-line and main button. Other roles stay in English. */
  hi?: { sub?: string; primary?: string };
}) {
  const [id, setId] = useState(roles[0].id);
  const lang = useLang();
  useEffect(() => {
    const asked = new URLSearchParams(window.location.search).get("role");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the role comes from the link, known only in the browser
    if (asked && roles.some((r) => r.id === asked)) setId(asked);
  }, [roles]);
  const role = roles.find((r) => r.id === id) ?? roles[0];
  const inHindi = lang === "hi" && role.id === roles[0].id;
  const sub = inHindi && hi?.sub, primary = inHindi && hi?.primary;
  return (
    <>
      <div className="rolechips" role="group" aria-label="Your role">
        I work in:
        {roles.map((r) => (
          <button key={r.id} type="button" aria-pressed={r.id === id}
                  onClick={() => { setId(r.id); track("role_chosen", { world, role: r.id }); }}>
            {r.label}
          </button>
        ))}
      </div>
      <p key={sub ? "hi" : "en"} className={`lead langfade${sub ? " deva" : ""}`} lang={sub ? "hi" : undefined} aria-live="polite">{sub || role.sub}</p>
      <div className="ctas">
        <a className={`btn btn-primary${primary ? " deva" : ""}`} lang={primary ? "hi" : undefined} href={primaryHref} data-tracked
           onClick={() => track("cta_clicked", { world, role: role.id, where: "hero", label: role.primary })}>{primary || role.primary}</a>
        <a className="btn btn-secondary" href={secondaryHref}>{role.secondary}</a>
      </div>
    </>
  );
}

const CHOICES: { id: WorldId; label: string }[] = [
  { id: "default", label: "General" },
  { id: "saas", label: "SaaS" },
  { id: "education", label: "Education" },
  { id: "enterprise", label: "Bank or insurer" },
];

/** Says which version is on screen and gives a one-click way to change it (the site's own "Why this?"). */
export function WorldChip({ current, name }: { current: WorldId; name: string }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => { if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", close); document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, [open]);
  return (
    <div className="whichbox" ref={box}>
      <button type="button" className="which" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen(!open)}>
        Showing the {name} version · <u>Change</u>
      </button>
      {open && (
        <div className="whichmenu" role="menu">
          {CHOICES.filter((c) => c.id !== current).map((c) => (
            <button key={c.id} type="button" role="menuitem" onClick={() => { setOpen(false); goWorld(c.id, "chip"); }}>{c.label}</button>
          ))}
        </div>
      )}
    </div>
  );
}
