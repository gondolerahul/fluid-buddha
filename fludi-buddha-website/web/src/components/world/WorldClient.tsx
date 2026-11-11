"use client";

// The small interactive parts shared by the pages: the language switch, the link that changes
// world, and the role chips under a persona world's headline.

import { useEffect, useState } from "react";
import type { Role, WorldId } from "@/content/worlds/types";
import { goWorld, track, worldPath } from "@/lib/world";
import { getLang, initLang, LANG_EVENT, setLang, type Lang } from "@/lib/lang";

/**
 * Put inside a page that carries reviewed Hindi. Its effect runs after that page has hydrated, so a
 * shared ?lang=hi link changes the page without disturbing React's hydration.
 */
export function LangInit() {
  useEffect(() => { initLang(); }, []);
  return null;
}

/** The language now on screen. Follows the switch, wherever it was pressed. */
export function useLang() {
  const [lang, set] = useState<Lang>("en");
  useEffect(() => {
    const on = (e: Event) => set((e as CustomEvent<{ lang: Lang }>).detail.lang);
    window.addEventListener(LANG_EVENT, on);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the language of a shared link is only known in the browser
    set(getLang());
    return () => window.removeEventListener(LANG_EVENT, on);
  }, []);
  return lang;
}

/**
 * The English / Hindi switch (WebsitePlan.md §3.5), shown only on pages with reviewed Hindi.
 * "button" is the compact switch in the header; "pill" is the two-part switch in a hero.
 */
export function LangSwitch({ where, variant = "button" }: { where: string; variant?: "button" | "pill" }) {
  const lang = useLang();
  const go = (to: Lang) => { if (to === lang) return; setLang(to); track("lang_switched", { where, to }); };
  if (variant === "pill") {
    return (
      <div className="lang-pill" role="group" aria-label="Language">
        <button type="button" aria-pressed={lang === "en"} onClick={() => go("en")}>English</button>
        <button type="button" lang="hi" className="deva" aria-pressed={lang === "hi"} onClick={() => go("hi")}>हिंदी</button>
      </div>
    );
  }
  return (
    <button type="button" className="lang-btn" onClick={() => go(lang === "en" ? "hi" : "en")}
            aria-label={lang === "en" ? "Show this page in Hindi" : "Showing Hindi. Change to English"}>
      {lang === "en" ? <span lang="hi" className="deva">हिंदी</span> : <>हिंदी on · <u>English</u></>}
    </button>
  );
}

/** A link to another world. With JavaScript it morphs; without it, it is an ordinary link. */
export function GoWorld({ to, how = "selector", className, style, children, label }: {
  to: WorldId; how?: "selector" | "chip" | "offer" | "menu"; className?: string; style?: React.CSSProperties; children: React.ReactNode; label?: string;
}) {
  return (
    <a href={worldPath(to)} className={className} style={style} aria-label={label}
       onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); goWorld(to, how); }}>
      {children}
    </a>
  );
}

/** Role chips under the hero. A role changes words only: the sub-line and the two buttons. */
export function RoleBlock({ world, roles, hi }: {
  world: WorldId; roles: Role[];
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
      <p key={sub ? "hi" : role.id} className={`t-lead role-sub${sub ? " deva" : ""}`} lang={sub ? "hi" : undefined} aria-live="polite">{sub || role.sub}</p>
      <div className="ctas">
        <a className={`btn btn-primary btn-lg${primary ? " deva" : ""}`} lang={primary ? "hi" : undefined} href={role.primaryHref} data-tracked
           onClick={() => track("cta_clicked", { world, role: role.id, where: "hero", label: role.primary })}>{primary || role.primary}</a>
        <a className="btn btn-quiet btn-lg" href={role.secondaryHref}>{role.secondary}</a>
      </div>
      <div className="roles" role="group" aria-label="Your role">
        <span>I work in</span>
        {roles.map((r) => (
          <button key={r.id} type="button" aria-pressed={r.id === id}
                  onClick={() => { setId(r.id); track("role_chosen", { world, role: r.id }); }}>
            {r.label}
          </button>
        ))}
      </div>
    </>
  );
}
