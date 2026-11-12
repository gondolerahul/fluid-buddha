"use client";

/**
 * The one header of the whole site. The same logo, version switch and five links on every page; the
 * colours and the main button follow the world on <html data-world>. Rendered once in the root
 * layout, so it stays put during navigation and during the morph between worlds.
 */
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { NAV, SOLUTIONS } from "@/content/site";
import { currentWorld, VERSIONS, WORLD_IDS, track, worldPath } from "@/lib/world";
import { getLang, hasHindi, resetLang, setLang } from "@/lib/lang";
import { GoWorld, LangSwitch, useLang } from "@/components/world/WorldClient";
import VersionSwitch, { Chev } from "./VersionSwitch";

/** The logo goes to the home page of the version on screen, so it never bounces a visitor out of it. */
function Logo() {
  const router = useRouter();
  return (
    <Link href="/" className="hdr-logo" aria-label="FluidBuddha home"
          onClick={(e) => { if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return; e.preventDefault(); router.push(worldPath(currentWorld())); }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="logo-dark" src="/brand/logo-fluidbuddha-horizontal-onblack.svg" alt="FluidBuddha" width={144} height={28} />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="logo-light" src="/brand/logo-fluidbuddha-horizontal-black.svg" alt="" aria-hidden width={144} height={28} />
    </Link>
  );
}

/** The world's own main button. All four are rendered; CSS shows the one for the world on screen. */
function HeaderCtas({ pathname, size = "" }: { pathname: string; size?: string }) {
  const lang = useLang();
  const onEducation = pathname === "/for/education";
  return (
    <>
      {WORLD_IDS.map((id) => {
        const v = VERSIONS[id];
        // On the Education page its main button is the Hindi switch itself.
        const toggles = id === "education" && onEducation;
        const label = toggles && lang === "hi" ? "Back to English" : v.cta.label;
        return (
          <a key={id} className={`btn btn-primary hdr-cta ${size}`} data-for={id} href={v.cta.href} data-tracked
             onClick={(e) => {
               track("cta_clicked", { world: id, where: "header", label });
               if (toggles) { e.preventDefault(); setLang(getLang() === "hi" ? "en" : "hi"); }
             }}>{label}</a>
        );
      })}
    </>
  );
}

function SolutionsPanel({ onPick }: { onPick: () => void }) {
  return (
    <div className="hdr-panel" role="menu">
      <div className="col">
        <h3>Versions of this site</h3>
        {SOLUTIONS.worlds.map((w) => (
          <GoWorld key={w.to} to={w.to} how="menu" className="hdr-item world">
            <b>{w.label}</b><small>{w.note}</small>
          </GoWorld>
        ))}
      </div>
      <div className="col">
        <h3>By team</h3>
        {SOLUTIONS.teams.map((t) => (
          <Link key={t.href} href={t.href} className="hdr-item" onClick={onPick}><b>{t.label}</b><small>{t.note}</small></Link>
        ))}
        <h3>More industries</h3>
        <div className="hdr-mini">{SOLUTIONS.industries.map((t) => <Link key={t.href} href={t.href} onClick={onPick}>{t.label}</Link>)}</div>
      </div>
    </div>
  );
}

export default function SiteHeader() {
  const pathname = usePathname();
  const [drop, setDrop] = useState(false);
  const [mobile, setMobile] = useState(false);
  const dropRef = useRef<HTMLDivElement>(null);
  const hindi = hasHindi(pathname) && pathname !== "/for/education";

  // every page starts in English (a page with Hindi applies a shared ?lang=hi itself, after it has
  // hydrated: <LangInit />); menus close on navigation
  useEffect(() => {
    resetLang();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- close menus when the route changes
    setDrop(false); setMobile(false);
  }, [pathname]);

  useEffect(() => {
    if (!drop) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent) { if (e.key === "Escape") setDrop(false); return; }
      if (!dropRef.current?.contains(e.target as Node)) setDrop(false);
    };
    document.addEventListener("pointerdown", close); document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, [drop]);

  useEffect(() => {
    document.documentElement.style.overflow = mobile ? "hidden" : "";
    if (!mobile) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setMobile(false); };
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("keydown", esc); document.documentElement.style.overflow = ""; };
  }, [mobile]);

  // the morph closes the menus too
  useEffect(() => {
    const on = () => { setDrop(false); setMobile(false); };
    window.addEventListener("fb:go-world", on);
    return () => window.removeEventListener("fb:go-world", on);
  }, []);

  return (
    <>
    <header className="hdr tone-ink">
      <div className="hdr-in wrap">
        <Logo />
        <VersionSwitch />
        <nav className="hdr-nav" aria-label="Main">
          {NAV.map((n) =>
            n.label === "Solutions" ? (
              <div key={n.label} className="hdr-drop" ref={dropRef}>
                <button type="button" className="hdr-link" aria-expanded={drop} aria-haspopup="menu" onClick={() => setDrop(!drop)}>
                  Solutions <Chev />
                </button>
                {drop && <SolutionsPanel onPick={() => setDrop(false)} />}
              </div>
            ) : (
              <Link key={n.label} href={n.href} className="hdr-link" aria-current={pathname === n.href ? "page" : undefined}>{n.label}</Link>
            ),
          )}
        </nav>
        <span className="hdr-sp" />
        <div className="hdr-act">
          {hindi && <LangSwitch where={pathname} />}
          <HeaderCtas pathname={pathname} />
          <button type="button" className="hdr-burger" aria-expanded={mobile} aria-controls="phone-menu" aria-label={mobile ? "Close the menu" : "Open the menu"} onClick={() => setMobile(!mobile)}>
            <span />
          </button>
        </div>
      </div>
    </header>

      {/* outside the header: its backdrop-filter would make it the containing block of a fixed menu */}
      {mobile && (
        <div className="mm tone-ink" id="phone-menu">
          <nav aria-label="Main">
            {NAV.filter((n) => n.label !== "Solutions").map((n) => <Link key={n.label} href={n.href}>{n.label}<span aria-hidden>&rarr;</span></Link>)}
            {SOLUTIONS.teams.map((t) => <Link key={t.href} href={t.href}>{t.label}<span aria-hidden>&rarr;</span></Link>)}
          </nav>
          <div>
            <h3>Version of this site</h3>
            <VersionSwitch variant="list" onDone={() => setMobile(false)} />
          </div>
          <div className="ctas">
            {hasHindi(pathname) && pathname !== "/for/education" && <LangSwitch where={pathname} />}
            <HeaderCtas pathname={pathname} size="btn-lg" />
          </div>
        </div>
      )}
    </>
  );
}
