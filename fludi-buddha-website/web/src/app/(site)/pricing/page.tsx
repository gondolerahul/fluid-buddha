import type { Metadata } from "next";
import Link from "next/link";
import CostCalculator from "@/components/CostCalculator";
import AskButton from "@/components/site/AskButton";
import { LangInit } from "@/components/world/WorldClient";
import { PLANS } from "@/content/site";
import WorldArt from "@/components/world/WorldArt";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Start free with 100 conversations. Growth is ₹33,000 a month for 2,000 conversations. Pay for conversations, not seats.",
  alternates: { canonical: "/pricing" },
};

const FAQ = [
  { q: "What counts as a conversation?", a: "A visitor session with at least one answered turn, counted across all of your websites. Calls from AI assistants through the agent endpoint are not counted." },
  { q: "What happens when the Free plan runs out?", a: "New conversations pause until the next month or until you upgrade. Conversations already in progress can finish." },
  { q: "Do repeat questions cost more?", a: "Repeat and near-identical questions replay from memory at almost no model cost, so your cost per conversation falls as it learns." },
  { q: "Can I cap my spend?", a: "Yes. Each website has a daily spend cap and cost alerts at 80% and 100%." },
  { q: "Which languages are included?", a: "English and Hindi, including Hinglish. It answers in Hindi even when your website is written in English." },
  { q: "Can I get a quote as a PDF?", a: "Yes. Ask the website for a quote and it produces one, or book a demo for Enterprise." },
];

/**
 * Pricing, with the reviewed Hindi of the earlier Hindi pricing page carried as `data-hi`, so the
 * header's Hindi switch changes it in place (WebsitePlan.md §3.5: pricing is the second Hindi page).
 */
export default function PricingPage() {
  return (
    <>
      <LangInit />
      <section className="cp-hero">
        <div className="wrap">
          <div className="cp-hero-copy" data-enter>
            <h1 className="t-display" data-hi="मुफ़्त शुरू करें।|भुगतान बातचीत के हिसाब से, सीटों के हिसाब से नहीं।">Start free. <span className="em">Pay for conversations, not seats.</span></h1>
            <p className="t-lead" data-hi="हर प्लान में हिंदी और अंग्रेज़ी में बोलकर और लिखकर बातचीत, सिर्फ़ आपकी वेबसाइट से स्रोत सहित जवाब, और लीड कैप्चर शामिल है।">
              Every plan includes voice and text in English and Hindi, answers only from your website with sources, and lead capture.
            </p>
            <div className="ctas">
              <a href="#plans" className="btn btn-primary btn-lg">See the plans</a>
              <AskButton question="What would 3,000 conversations cost?" />
            </div>
          </div>
          <WorldArt k="shows" className="cp-hero-art" />
        </div>
      </section>

      <section className="section" id="plans" style={{ paddingTop: "clamp(48px, 7vh, 88px)" }}>
        <div className="wrap">
          <div className="pr-plans">
            {PLANS.map((p) => (
              <article key={p.name} className={`pr-plan${p.lead ? " lead" : ""}`}>
                <h2 data-hi={p.hi?.name}>{p.name}</h2>
                <div className="pr-price num" data-hi={p.hi?.price}>{p.price}</div>
                <div className="pr-per" data-hi={p.hi?.per}>{p.per}</div>
                <div className="pr-inc" data-hi={p.hi?.included}>{p.included}</div>
                <div className="pr-extra" data-hi={p.hi?.extra}>{p.extra}</div>
                <ul className="pr-feat">{p.features.map((f, i) => <li key={f} data-hi={p.hi?.features?.[i] || undefined}>{f}</li>)}</ul>
                <Link href={p.href} className={`btn ${p.lead ? "btn-primary" : "btn-quiet"}`} data-hi={p.hi?.cta}>{p.cta}</Link>
              </article>
            ))}
          </div>
          <p className="note" style={{ marginTop: 24 }}>Prices are in Indian rupees, a month. Paid plans are monthly.</p>
        </div>
      </section>

      <section className="section tone-second" id="calculator">
        <div className="wrap pr-calc">
          <div className="sh" style={{ marginBottom: 0 }}>
            <h2 className="t-h2" data-hi="आपका खर्च|कितना होगा?">What would it <span className="em">cost you?</span></h2>
            <p className="t-lead" data-hi="स्लाइडर को अपनी अनुमानित मासिक बातचीत पर ले जाइए। ग्रोथ पर एक बातचीत लगभग ₹16.50 की पड़ती है, स्केल पर लगभग ₹12.50।">
              Move the slider to your expected monthly conversations. On Growth, a conversation costs about ₹16.50; on Scale, about ₹12.50.
            </p>
          </div>
          <div lang="en"><CostCalculator /></div>
        </div>
      </section>

      <section className="section">
        <div className="wrap faq-split">
          <div className="sh">
            <h2 className="t-h2">Questions about pricing</h2>
            <p className="t-lead">Or ask the website. It answers from this page.</p>
            <div><AskButton question="Can I cap my spend?" /></div>
          </div>
          <div className="faq">{FAQ.map((f) => <details key={f.q}><summary>{f.q}</summary><p>{f.a}</p></details>)}</div>
        </div>
      </section>

      <section className="section cp-close tone-gold">
        <div className="wrap">
          <h2 className="t-h2">Start with 100 conversations, <span className="em">free every month.</span></h2>
          <div className="ctas">
            <Link href="/demo#start" className="btn btn-primary btn-lg">Start free</Link>
            <Link href="/book-demo" className="btn btn-quiet btn-lg">Book a demo</Link>
          </div>
        </div>
      </section>
    </>
  );
}
