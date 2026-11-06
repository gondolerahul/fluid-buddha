"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { NAV } from "@/content/site";
import styles from "./Nav.module.css";

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const [mobile, setMobile] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 40);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- close menus on navigation
  useEffect(() => { setOpen(null); setMobile(false); }, [pathname]);

  const hi = pathname.startsWith("/hi");

  return (
    <header className={`${styles.bar} ${scrolled ? styles.scrolled : ""}`} onMouseLeave={() => setOpen(null)}>
      <div className={`wrap-wide ${styles.inner}`}>
        <Link href={hi ? "/hi" : "/"} className={styles.logo} aria-label="FluidBuddha home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/logo-fluidbuddha-horizontal-gold.svg" alt="FluidBuddha" className="logo-paper" width={180} height={34} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/logo-fluidbuddha-horizontal-onblack.svg" alt="" aria-hidden className="logo-ink" width={180} height={34} />
        </Link>

        <nav className={`${styles.links} ${mobile ? styles.mobileOpen : ""}`} aria-label="Main">
          {NAV.map((item) =>
            item.menu ? (
              <div key={item.label} className={styles.group} onMouseEnter={() => setOpen(item.label)}>
                <button className={styles.link} aria-expanded={open === item.label} onClick={() => setOpen(open === item.label ? null : item.label)}>
                  {item.label}
                </button>
                {open === item.label && (
                  <div className={`glass glass-strong ${styles.menu}`}>
                    {item.menu.map((m) => (
                      <Link key={m.href} href={m.href} className={styles.menuItem}>
                        <span>{m.label}</span>
                        {m.note && <small>{m.note}</small>}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <Link key={item.label} href={item.href!} className={`${styles.link} ${pathname === item.href ? styles.active : ""}`}>
                {item.label}
              </Link>
            ),
          )}
        </nav>

        <div className={styles.actions}>
          <Link href={hi ? "/" : "/hi"} className={styles.lang} lang={hi ? "en" : "hi"}>{hi ? "English" : "हिन्दी"}</Link>
          <Link href="/book-demo" className={`btn btn-ghost ${styles.demo}`}>Book a demo</Link>
          <Link href="/demo#start" className="btn btn-metal">{hi ? "शुरू करें" : "Start free"}</Link>
          <button className={styles.burger} aria-label="Menu" aria-expanded={mobile} onClick={() => setMobile(!mobile)}>
            <span /><span />
          </button>
        </div>
      </div>
    </header>
  );
}
