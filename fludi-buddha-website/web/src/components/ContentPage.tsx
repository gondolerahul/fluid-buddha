import Image from "next/image";
import Link from "next/link";
import type { Page, Section } from "@/content/pages";
import Theme from "./Theme";
import styles from "./ContentPage.module.css";

const poster = (k: string) => `/film/posters/${k}.webp`;

function Block({ s, i }: { s: Section; i: number }) {
  switch (s.kind) {
    case "story":
      return (
        <section className={`section ${styles.story} ${i % 2 ? styles.flip : ""}`}>
          <div className={`wrap ${styles.storyGrid}`}>
            <div className="stack-5 reveal">
              {s.eyebrow && <div className="eyebrow">{s.eyebrow}</div>}
              <h2 className="h2">{s.title}</h2>
              <p className="lead">{s.body}</p>
              {s.bullets && <ul className={styles.bullets}>{s.bullets.map((b) => <li key={b}>{b}</li>)}</ul>}
              {s.tag && <p className={styles.try}>{s.tag}</p>}
              {s.note && <p className="illustrative">{s.note}</p>}
            </div>
            {s.poster && (
              <div className={`${styles.visual} reveal`}>
                <Image src={poster(s.poster)} alt="" fill sizes="(max-width: 960px) 100vw, 50vw" />
              </div>
            )}
          </div>
        </section>
      );
    case "grid":
      return (
        <section className="section">
          <div className="wrap">
            <div className="stack-4 reveal" style={{ maxWidth: 760 }}>
              {s.eyebrow && <div className="eyebrow">{s.eyebrow}</div>}
              <h2 className="h2">{s.title}</h2>
              {s.lead && <p className="lead">{s.lead}</p>}
            </div>
            <div className={`${s.cols === 2 ? "grid-2" : s.cols === 4 ? "grid-4" : "grid-3"} ${styles.cards}`}>
              {s.items.map((it) => (
                <div key={it.title} className="card reveal">
                  {it.tag && <div className="eyebrow" style={{ marginBottom: 12 }}>{it.tag}</div>}
                  <h3 className="h3">{it.title}</h3>
                  <p className="muted" style={{ marginTop: 10 }}>{it.body}</p>
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
            <div className="stack-4 reveal" style={{ maxWidth: 760 }}>
              {s.eyebrow && <div className="eyebrow">{s.eyebrow}</div>}
              <h2 className="h2">{s.title}</h2>
            </div>
            <ol className={styles.steps}>
              {s.items.map((it, n) => (
                <li key={it.title} className="reveal">
                  <span className={styles.num}>{String(n + 1).padStart(2, "0")}</span>
                  <h3 className="h3">{it.title}</h3>
                  <p className="muted">{it.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>
      );
    case "prose":
      return (
        <section className="section">
          <div className={`wrap ${styles.prose}`}>
            <div className="stack-5 reveal">
              {s.eyebrow && <div className="eyebrow">{s.eyebrow}</div>}
              <h2 className="h2">{s.title}</h2>
              {s.paragraphs.map((p) =>
                p.startsWith("<") ? <pre key={p} className={styles.code}>{p}</pre> : <p key={p} className="lead">{p}</p>,
              )}
            </div>
          </div>
        </section>
      );
    case "faq":
      return (
        <section className="section">
          <div className={`wrap ${styles.prose}`}>
            <h2 className="h2 reveal">{s.title}</h2>
            <div className={styles.faq}>
              {s.items.map((f) => (
                <details key={f.q} className="reveal"><summary>{f.q}</summary><p className="muted">{f.a}</p></details>
              ))}
            </div>
          </div>
        </section>
      );
  }
}

export default function ContentPage({ page }: { page: Page }) {
  return (
    <>
      <Theme theme={page.theme ?? "paper"} />
      <section className={styles.hero}>
        <div className={styles.heroImg}>
          <Image src={poster(page.poster)} alt="" fill priority sizes="100vw" />
        </div>
        <div className={styles.heroVeil} />
        <div className={`wrap ${styles.heroCopy}`}>
          <div className="stack-5">
            <div className="eyebrow">{page.eyebrow}</div>
            <h1 className="h1">{page.headline[0]} <span className="gold">{page.headline[1]}</span></h1>
            <p className="lead">{page.sub}</p>
            <div className={styles.ctas}>
              <Link href={page.primary.href} className="btn btn-metal btn-lg">{page.primary.label}</Link>
              {page.secondary && <Link href={page.secondary.href} className="btn btn-ghost btn-lg">{page.secondary.label}</Link>}
            </div>
          </div>
        </div>
      </section>

      {page.sections.map((s, i) => <Block key={i} s={s} i={i} />)}

      <section className={`section ${styles.closing}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/favicon.svg" alt="" aria-hidden className={styles.mark} />
        <div className="wrap stack-5 reveal" style={{ textAlign: "center" }}>
          <h2 className="h1">{page.closing.title[0]} <span className="gold">{page.closing.title[1]}</span></h2>
          {page.closing.body && <p className="lead" style={{ marginInline: "auto" }}>{page.closing.body}</p>}
          <div className={styles.ctas} style={{ justifyContent: "center" }}>
            <Link href={page.closing.primary.href} className="btn btn-metal btn-lg">{page.closing.primary.label}</Link>
            {page.closing.secondary && <Link href={page.closing.secondary.href} className="btn btn-ghost btn-lg">{page.closing.secondary.label}</Link>}
          </div>
        </div>
      </section>
    </>
  );
}
