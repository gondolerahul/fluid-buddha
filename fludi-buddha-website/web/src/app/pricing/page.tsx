import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import CostCalculator from "@/components/CostCalculator";
import { PLANS } from "@/content/site";
import styles from "./pricing.module.css";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Start free with 100 conversations. Growth is ₹33,000 a month for 2,000 conversations. Pay for conversations, not seats.",
};

const FAQ = [
  { q: "What counts as a conversation?", a: "A visitor session with at least one answered turn, counted across all of your websites. Calls from AI assistants through the agent endpoint are not counted." },
  { q: "What happens when the Free plan runs out?", a: "New conversations are paused until the next month or until you upgrade. Conversations already in progress can finish." },
  { q: "Do repeat questions cost more?", a: "Repeat and near-identical questions replay from memory at almost no model cost, so your cost per conversation falls as it learns." },
  { q: "Can I cap my spend?", a: "Yes. Each website has a daily spend cap and cost alerts at 80% and 100%." },
  { q: "Which languages are supported?", a: "English and Hindi, including Hinglish. It answers in Hindi even when your website is written in English." },
  { q: "Can I get a quote as a PDF?", a: "Yes. Ask the website for a quote and it produces one, or contact sales for Enterprise." },
];

export default function PricingPage() {
  return (
    <>
      <section className={styles.hero}>
        <div className={styles.heroImg}><Image src="/film/posters/K14.webp" alt="" fill priority sizes="100vw" /></div>
        <div className={styles.veil} />
        <div className="wrap stack-5" style={{ position: "relative", maxWidth: 1200 }}>
          <div className="eyebrow">Pricing</div>
          <h1 className="h1" style={{ maxWidth: 820 }}>Start free. <span className="gold">Pay for conversations, not seats.</span></h1>
          <p className="lead">Every plan includes voice and text in English and Hindi, answers only from your website with sources, and lead capture.</p>
        </div>
      </section>

      <section className={styles.plansWrap}>
        <div className={`wrap grid-4 ${styles.plans}`}>
          {PLANS.map((p) => (
            <div key={p.name} className={`card reveal ${styles.plan} ${p.hot ? styles.hot : ""}`}>
              {p.hot && <span className={styles.badge}>Most chosen</span>}
              <div className="eyebrow">{p.name}</div>
              <div className={styles.price}>{p.price}</div>
              <div className="subtle">{p.per}</div>
              <hr className="rule" style={{ margin: "22px 0" }} />
              <div className={styles.inc}>{p.included}</div>
              <div className="subtle" style={{ fontSize: 14 }}>{p.extra}</div>
              <ul className={styles.feat}>{p.features.map((f) => <li key={f}>{f}</li>)}</ul>
              <Link href={p.href} className={`btn ${p.hot ? "btn-metal" : "btn-ghost"}`} style={{ marginTop: "auto" }}>{p.cta}</Link>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <div className={`wrap ${styles.calcGrid}`}>
          <div className="stack-5 reveal">
            <div className="eyebrow">Calculator</div>
            <h2 className="h2">What would it <span className="gold">cost you?</span></h2>
            <p className="lead">Move the slider to your expected monthly conversations. On Growth, a conversation costs about ₹16.50; on Scale, about ₹12.50.</p>
          </div>
          <div className="reveal"><CostCalculator /></div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap" style={{ maxWidth: 860 }}>
          <h2 className="h2 reveal">Questions, <span className="gold">answered.</span></h2>
          <p className="muted reveal" style={{ marginTop: 12 }}>Or ask the website in the bar below. It answers from this page.</p>
          <div className={styles.faq}>
            {FAQ.map((f) => <details key={f.q} className="reveal"><summary>{f.q}</summary><p className="muted">{f.a}</p></details>)}
          </div>
        </div>
      </section>
    </>
  );
}
