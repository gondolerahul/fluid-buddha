// The one footer of the whole site: the same ink block in every world (the design system's dark).
import Link from "next/link";
import { FOOTER } from "@/content/site";
import VersionSwitch from "./VersionSwitch";

export default function SiteFooter() {
  return (
    <footer className="ftr tone-ink">
      <div className="wrap">
        <div className="ftr-top">
          <div className="ftr-brand">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="logo-dark" src="/brand/logo-fluidbuddha-horizontal-onblack.svg" alt="FluidBuddha" width={154} height={30} />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img className="logo-light" src="/brand/logo-fluidbuddha-horizontal-black.svg" alt="" aria-hidden width={154} height={30} />
            <p>Your website answers visitors by voice or text, from your own pages, and books the next step. A Buddha Cognitive Lab product.</p>
            <Link href="/book-demo" className="link">Book a demo <span className="arrow" aria-hidden>&rarr;</span></Link>
          </div>
          <nav className="ftr-cols" aria-label="Footer">
            {FOOTER.map((col) => (
              <div className="ftr-col" key={col.title}>
                <h3>{col.title}</h3>
                <ul>{col.links.map((l) => <li key={l.href}><Link href={l.href}>{l.label}</Link></li>)}</ul>
              </div>
            ))}
          </nav>
        </div>
        <div className="ftr-bot">
          <div className="grp">
            <span>&copy; 2026 Buddha Cognitive Lab</span>
            <span>Answers only from your website, with sources.</span>
          </div>
          <div className="grp">
            <span>You are viewing</span>
            <VersionSwitch placement="up" />
          </div>
        </div>
        <div className="ftr-word" aria-hidden>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="logo-dark" src="/brand/logo-fluidbuddha-horizontal-onblack.svg" alt="" />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="logo-light" src="/brand/logo-fluidbuddha-horizontal-black.svg" alt="" />
        </div>
      </div>
    </footer>
  );
}
