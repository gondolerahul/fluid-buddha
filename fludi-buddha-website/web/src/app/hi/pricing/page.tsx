import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import CostCalculator from "@/components/CostCalculator";
import styles from "../../pricing/pricing.module.css";

export const metadata: Metadata = {
  title: { absolute: "कीमतें · FluidBuddha" },
  description: "100 बातचीत के साथ मुफ़्त शुरू करें। ग्रोथ ₹33,000 महीने में 2,000 बातचीत। भुगतान बातचीत के हिसाब से, सीटों के हिसाब से नहीं।",
  alternates: { canonical: "/hi/pricing", languages: { "en-IN": "/pricing" } },
};

const PLANS_HI = [
  { name: "फ़्री", price: "₹0", per: "प्रति माह", included: "100 बातचीत", extra: "कोई ओवरेज नहीं", features: ["बोलकर और लिखकर, हिंदी और अंग्रेज़ी", "सिर्फ़ आपकी वेबसाइट से जवाब, स्रोत के साथ", "लीड कैप्चर"], cta: "मुफ़्त शुरू करें", href: "/hi/demo#start" },
  { name: "ग्रोथ", price: "₹33,000", per: "प्रति माह", included: "2,000 बातचीत", extra: "हर अतिरिक्त बातचीत ₹17", hot: true, features: ["फ़्री की सारी सुविधाएँ", "बुकिंग, कोटेशन, ट्रायल और पेमेंट लिंक", "Slack अलर्ट और CRM", "इनसाइट्स और सोमवार की रिपोर्ट"], cta: "ट्रायल शुरू करें", href: "/book-demo" },
  { name: "स्केल", price: "₹1,25,000", per: "प्रति माह", included: "10,000 बातचीत", extra: "हर अतिरिक्त बातचीत ₹10", features: ["ग्रोथ की सारी सुविधाएँ", "होल्डआउट माप और A/B टेस्ट", "लाइव टेकओवर और ब्राउज़र कॉल", "कैंपेन लैंडिंग पेज"], cta: "हमसे बात करें", href: "/book-demo" },
  { name: "एंटरप्राइज़", price: "कस्टम", per: "आपसी सहमति से", included: "असीमित बातचीत", extra: "—", features: ["SSO, MFA और ऑडिट लॉग", "सेल्फ़-होस्टेड संस्करण", "अपना AI मॉडल", "99.9% SLA"], cta: "सेल्स से संपर्क", href: "/enterprise" },
];

export default function HindiPricing() {
  return (
    <div lang="hi" className="deva">
      <section className={styles.hero}>
        <div className={styles.heroImg}><Image src="/film/posters/K14.webp" alt="" fill priority sizes="100vw" /></div>
        <div className={styles.veil} />
        <div className="wrap stack-5" style={{ position: "relative" }}>
          <div className="eyebrow">कीमतें</div>
          <h1 className="h1" style={{ maxWidth: 820 }}>मुफ़्त शुरू करें। <span className="gold">भुगतान बातचीत के हिसाब से, सीटों के हिसाब से नहीं।</span></h1>
          <p className="lead">हर प्लान में हिंदी और अंग्रेज़ी में बोलकर और लिखकर बातचीत, सिर्फ़ आपकी वेबसाइट से स्रोत सहित जवाब, और लीड कैप्चर शामिल है।</p>
        </div>
      </section>
      <section className={styles.plansWrap}>
        <div className={`wrap grid-4 ${styles.plans}`}>
          {PLANS_HI.map((p) => (
            <div key={p.name} className={`card reveal ${styles.plan} ${p.hot ? styles.hot : ""}`}>
              {p.hot && <span className={styles.badge}>सबसे लोकप्रिय</span>}
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
      <section className="section" style={{ paddingTop: 0 }}>
        <div className={`wrap ${styles.calcGrid}`}>
          <div className="stack-5 reveal">
            <div className="eyebrow">कैलकुलेटर</div>
            <h2 className="h2">आपका खर्च <span className="gold">कितना होगा?</span></h2>
            <p className="lead">स्लाइडर को अपनी अनुमानित मासिक बातचीत पर ले जाइए। ग्रोथ पर एक बातचीत लगभग ₹16.50 की पड़ती है, स्केल पर लगभग ₹12.50।</p>
          </div>
          <div className="reveal" lang="en"><CostCalculator /></div>
        </div>
      </section>
    </div>
  );
}
