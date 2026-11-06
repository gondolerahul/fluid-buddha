import Image from "next/image";
import Link from "next/link";
import FilmPlayer from "@/components/FilmPlayer";
import { FOR_YOU } from "@/content/home";
import { PLANS } from "@/content/site";
import styles from "./home.module.css";

export default function Home() {
  return (
    <>
      <FilmPlayer />

      <section className="section">
        <div className="wrap">
          <div className="stack-4 reveal" style={{ maxWidth: 720 }}>
            <div className="eyebrow">For you</div>
            <h2 className="h2">Where it earns its place <span className="gold">first.</span></h2>
          </div>
          <div className={`grid-3 ${styles.for}`}>
            {FOR_YOU.map((f) => (
              <Link key={f.href} href={f.href} className={`card reveal ${styles.tile}`}>
                <div className={styles.tileImg}>
                  <Image src={`/film/posters/${f.poster}.webp`} alt="" fill sizes="(max-width: 960px) 50vw, 33vw" />
                </div>
                <h3 className="h3">{f.title}</h3>
                <p className="muted">{f.body}</p>
                <span className={styles.more}>Explore →</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className={`section ${styles.pricing}`}>
        <div className="wrap">
          <div className="stack-4 reveal" style={{ maxWidth: 720 }}>
            <div className="eyebrow">Pricing</div>
            <h2 className="h2">Start free. <span className="gold">Pay for conversations, not seats.</span></h2>
          </div>
          <div className={`grid-4 ${styles.plans}`}>
            {PLANS.map((p) => (
              <div key={p.name} className={`card reveal ${p.hot ? styles.hot : ""}`}>
                <div className="eyebrow">{p.name}</div>
                <div className={styles.price}>{p.price}</div>
                <div className="subtle">{p.per} · {p.included}</div>
              </div>
            ))}
          </div>
          <div className="reveal" style={{ marginTop: 40 }}><Link href="/pricing" className="btn btn-ghost">Compare plans</Link></div>
        </div>
      </section>
    </>
  );
}
