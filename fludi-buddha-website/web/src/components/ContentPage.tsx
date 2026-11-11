// The template for the content pages (product, solutions, industries, developers, trust, company).
// It is drawn entirely from the world tokens, so it takes the look of the visitor's version.
import Image from "next/image";
import Link from "next/link";
import type { Page, Section } from "@/content/pages";
import { MEDIA } from "@/content/media";
import AskButton from "@/components/site/AskButton";

function Title({ t }: { t: [string, string] }) {
  return <>{t[0]} <span className="em">{t[1]}</span></>;
}

function Block({ s, i }: { s: Section; i: number }) {
  switch (s.kind) {
    case "story": {
      const m = s.media ? MEDIA[s.media] : undefined;
      return (
        <section className="section">
          <div className={`wrap cp-story${i % 2 ? " flip" : ""}`}>
            <div className="copy">
              <h2 className="t-h2">{s.title}</h2>
              <p className="t-lead">{s.body}</p>
              {s.bullets && <ul className="cp-ticks">{s.bullets.map((b) => <li key={b}>{b}</li>)}</ul>}
              {s.ask && <AskButton question={s.ask} />}
              {s.note && <p className="note">{s.note}</p>}
            </div>
            {m && (
              <div className="cp-media">
                <Image unoptimized src={m.src} alt={m.alt} fill sizes="(max-width: 960px) 100vw, 55vw" style={{ objectPosition: `${m.focus ?? 50}% 50%` }} />
              </div>
            )}
          </div>
        </section>
      );
    }
    case "grid":
      return (
        <section className="section band">
          <div className="wrap">
            <div className="sh">
              <h2 className="t-h2">{s.title}</h2>
              {s.lead && <p className="t-lead">{s.lead}</p>}
            </div>
            <div className={`cp-grid c${s.cols ?? 3}`}>
              {s.items.map((it) => (
                <div key={it.title} className="cp-cell">
                  {it.tag && <span className="ui-tag tag">{it.tag}</span>}
                  <h3 className="t-h3">{it.title}</h3>
                  <p>{it.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      );
    case "steps":
      return (
        <section className="section">
          <div className="wrap">
            <div className="sh"><h2 className="t-h2">{s.title}</h2></div>
            <ol className="cp-steps">
              {s.items.map((it) => <li key={it.title}><h3 className="t-h3">{it.title}</h3><p>{it.body}</p></li>)}
            </ol>
          </div>
        </section>
      );
    case "prose":
      return (
        <section className="section" id={s.id}>
          <div className="wrap">
            <div className="cp-prose">
              <h2 className="t-h2">{s.title}</h2>
              {s.paragraphs.map((p) => (p.startsWith("<") ? <pre key={p} className="ui-code">{p}</pre> : <p key={p} className="t-lead">{p}</p>))}
            </div>
          </div>
        </section>
      );
    case "faq":
      return (
        <section className="section">
          <div className="wrap faq-split">
            <div className="sh"><h2 className="t-h2">{s.title}</h2></div>
            <div className="faq">{s.items.map((f) => <details key={f.q}><summary>{f.q}</summary><p>{f.a}</p></details>)}</div>
          </div>
        </section>
      );
  }
}

export default function ContentPage({ page }: { page: Page }) {
  const m = MEDIA[page.media];
  return (
    <>
      <section className="cp-hero">
        <div className="cp-hero-media">
          <Image unoptimized src={m.src} alt="" fill priority sizes="100vw" style={{ objectPosition: `${m.focus ?? 70}% 50%` }} />
        </div>
        <div className="wrap">
          <div className="cp-hero-copy" data-enter>
            <h1 className="t-display"><Title t={page.headline} /></h1>
            <p className="t-lead">{page.sub}</p>
            <div className="ctas">
              <Link href={page.primary.href} className="btn btn-primary btn-lg">{page.primary.label}</Link>
              {page.secondary && <Link href={page.secondary.href} className="btn btn-quiet btn-lg">{page.secondary.label}</Link>}
            </div>
            {page.ask && <AskButton question={page.ask} />}
          </div>
        </div>
      </section>

      {page.sections.map((s, i) => <Block key={i} s={s} i={i} />)}

      <section className="section cp-close">
        <div className="wrap">
          <h2 className="t-h2"><Title t={page.closing.title} /></h2>
          {page.closing.body && <p className="t-lead">{page.closing.body}</p>}
          <div className="ctas">
            <Link href={page.closing.primary.href} className="btn btn-primary btn-lg">{page.closing.primary.label}</Link>
            {page.closing.secondary && <Link href={page.closing.secondary.href} className="btn btn-quiet btn-lg">{page.closing.secondary.label}</Link>}
          </div>
        </div>
      </section>
    </>
  );
}
