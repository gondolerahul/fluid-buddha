import Link from "next/link";
import { FOOTER } from "@/content/site";
import styles from "./Footer.module.css";

export default function Footer() {
  return (
    <footer className={styles.footer}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/brand/favicon.svg" alt="" aria-hidden className={styles.watermark} />
      <div className="wrap">
        <div className={styles.top}>
          <div className={styles.brand}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/logo-fluidbuddha-gold.svg" alt="FluidBuddha" className={styles.logo} />
            <p className={styles.tag}>Your website, answering every visitor.</p>
            <p className={styles.lab}>A Buddha Cognitive Lab product · Towards digital enlightenment</p>
          </div>
          <div className={styles.cols}>
            {FOOTER.map((col) => (
              <div key={col.title}>
                <h4>{col.title}</h4>
                <ul>
                  {col.links.map((l) => (
                    <li key={l.href}><Link href={l.href}>{l.label}</Link></li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <hr className="rule" />
        <div className={styles.bottom}>
          <span>© 2026 Buddha Cognitive Lab</span>
          <span><Link href="/">English</Link> · <Link href="/hi" lang="hi" className="deva">हिन्दी</Link></span>
          <span className="mono">Answers only from your website, with sources.</span>
        </div>
      </div>
    </footer>
  );
}
