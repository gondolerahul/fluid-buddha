"use client";

// Small interactive parts of the world pages.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { track } from "@/lib/world";

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" className="copy" onClick={async () => {
      try { await navigator.clipboard.writeText(text); setDone(true); window.setTimeout(() => setDone(false), 1800); } catch { /* clipboard refused */ }
    }} aria-live="polite">{done ? "Copied" : label}</button>
  );
}

/** Install code in tabs (SaaS world). */
export function InstallTabs({ tabs }: { tabs: { label: string; code: string }[] }) {
  const [i, setI] = useState(0);
  return (
    <div className="tabs">
      <div className="tabs-bar" role="tablist" aria-label="Install with">
        {tabs.map((t, k) => <button key={t.label} type="button" role="tab" aria-selected={k === i} onClick={() => setI(k)}>{t.label}</button>)}
        <CopyButton text={tabs[i].code} />
      </div>
      <pre className="ui-code tabs-code" role="tabpanel" aria-label={tabs[i].label}>{tabs[i].code}</pre>
    </div>
  );
}

/** "Compare that with what you pay for one click." (SaaS world). */
export function CostCompare() {
  const [cpc, setCpc] = useState(60);
  const per = 16.5;
  const conv = cpc > 0 ? cpc / per : 0;
  return (
    <div className="cc">
      <label className="field">
        <span>Your cost for one click on your main keyword</span>
        <span className="cc-in"><b aria-hidden>₹</b><input className="input num" type="number" min={1} max={5000} value={cpc || ""} onChange={(e) => setCpc(Math.max(0, +e.target.value))} inputMode="numeric" /></span>
      </label>
      <p className="cc-out" aria-live="polite">
        {cpc > 0 ? <>One click costs the same as <b className="num">{conv.toLocaleString("en-IN", { maximumFractionDigits: 1 })}</b> conversations on Growth.</> : "Enter what one click costs you."}
      </p>
    </div>
  );
}

/** "Enter your website" (SaaS world): opens the sandbox preview with the address filled in. */
export function TrySite() {
  const router = useRouter();
  const [site, setSite] = useState("");
  return (
    <form className="try" onSubmit={(e) => { e.preventDefault(); track("try_site", { from: "saas" }); router.push(`/demo?site=${encodeURIComponent(site.trim())}#your-site`); }}>
      <label className="sr-only" htmlFor="try-site">Your website</label>
      <input id="try-site" className="input" value={site} onChange={(e) => setSite(e.target.value)} placeholder="yourcompany.com" inputMode="url" autoComplete="url" />
      <button className="btn btn-primary btn-lg">Read my site</button>
    </form>
  );
}

/** The Enterprise world's index: the sections as a specification's contents, with the current one marked. */
export function SpecIndex({ items }: { items: { id: string; num: string; title: string }[] }) {
  const [cur, setCur] = useState(items[0]?.id);
  useEffect(() => {
    const els = items.map((i) => document.getElementById(i.id)).filter(Boolean) as HTMLElement[];
    const io = new IntersectionObserver((es) => {
      const vis = es.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (vis[0]) setCur(vis[0].target.id);
    }, { rootMargin: "-30% 0px -60% 0px" });
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [items]);
  return (
    <nav className="spec-index tone-second" aria-label="Contents">
      <p>Contents</p>
      <ol>
        {items.map((i) => (
          <li key={i.id}><a href={`#${i.id}`} aria-current={cur === i.id ? "true" : undefined}><span className="num">{i.num}</span>{i.title}</a></li>
        ))}
      </ol>
      <a href="#pilot" className="btn btn-primary btn-sm spec-go">Plan a pilot</a>
    </nav>
  );
}
