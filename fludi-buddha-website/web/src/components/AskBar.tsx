"use client";

/**
 * The ask bar: "Ask this website anything", fixed at the bottom of every page.
 *
 * If the real FluidBuddha widget is loaded (see AgentLoader), questions are forwarded to it
 * through its public `ask()` control surface and the widget answers. Until then the bar runs a
 * clearly labelled preview with scripted replies drawn from this site's own content, so the
 * page is fully explorable before the agent is connected.
 *
 * Other components can ask through the bar:  window.dispatchEvent(new CustomEvent("fb:ask", { detail: "…" }))
 * The bar announces each answered topic:     window.addEventListener("fb:answered", e => e.detail.topic)
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./AskBar.module.css";

type Msg = { who: "me" | "ai"; text: string; src?: { label: string; href: string }; extra?: "plans" | "book" | "booked"; hi?: boolean };
export type Topic = "price" | "how" | "hindi" | "honest" | "book" | "security" | "integrations";

const isHindi = (t: string) => /[ऀ-ॿ]/.test(t) || /\b(hindi|kya|kitna|batao|bataiye|haan|nahin|mein|hai)\b/i.test(t);

function classify(t: string): Topic {
  const s = t.toLowerCase();
  if (/book|demo|meeting|call|schedule|appointment|बुक/.test(s)) return "book";
  if (/hindi|हिंदी|हिन्दी|language|bhasha|भाषा/.test(s)) return "hindi";
  if (/price|pric|cost|plan|₹|rupee|kitna|कितन|free|कीमत/.test(s)) return "price";
  if (/secur|privacy|data|soc ?2|sso|gdpr|self.?host|सुरक्षा/.test(s)) return "security";
  if (/integrat|wordpress|shopify|webflow|framer|install|crm|slack|tally|react/.test(s)) return "integrations";
  if (/how|work|what is|what does|explain|kaise|कैसे|क्या है/.test(s)) return "how";
  return "honest";
}

function reply(topic: Topic, hi: boolean): Msg {
  switch (topic) {
    case "price":
      return hi
        ? { who: "ai", hi: true, text: "आप बातचीत के हिसाब से भुगतान करते हैं। मुफ़्त प्लान में 100 बातचीत, और ग्रोथ ₹33,000 महीने में 2,000 बातचीत।", extra: "plans", src: { label: "Pricing", href: "/hi/pricing" } }
        : { who: "ai", text: "You pay per conversation, not per seat. Free includes 100 conversations; Growth is ₹33,000 a month for 2,000.", extra: "plans", src: { label: "Pricing", href: "/pricing" } };
    case "how":
      return hi
        ? { who: "ai", hi: true, text: "आप अपनी वेबसाइट पर एक लाइन का कोड जोड़ते हैं। यह आपकी वेबसाइट पढ़ता है, और फिर आपके विज़िटर्स के सवालों का जवाब देता है, सिर्फ़ आपकी वेबसाइट से।", src: { label: "How it works", href: "/product" } }
        : { who: "ai", text: "You add one line of code. It reads your website, then answers your visitors out loud, shows them what they need and books the next step, using only what your website says.", src: { label: "How it works", href: "/product" } };
    case "hindi":
      return { who: "ai", hi: true, text: "हाँ! मैं हिंदी और अंग्रेज़ी दोनों में बात करती हूँ, भले ही आपकी वेबसाइट सिर्फ़ अंग्रेज़ी में हो।", src: { label: "Languages", href: "/industries/retail-services" } };
    case "security":
      return { who: "ai", text: "Personal details like emails and phone numbers are masked before any model sees them. There's SSO, an audit log, a SOC 2 control pack and a self-hosted edition.", src: { label: "Trust and security", href: "/trust" } };
    case "integrations":
      return { who: "ai", text: "It installs with one line of code on WordPress, Shopify, Webflow, Framer, Google Tag Manager, React, Vue or any site, and sends leads to Slack and your CRM.", src: { label: "Integrations", href: "/integrations" } };
    case "book":
      return hi
        ? { who: "ai", hi: true, text: "ज़रूर। क्या मैं यह डेमो बुक कर दूँ?", extra: "book" }
        : { who: "ai", text: "Sure. Shall I book this for you?", extra: "book" };
    default:
      return hi
        ? { who: "ai", hi: true, text: "यह जानकारी इस वेबसाइट पर नहीं है। मैं टीम से आपसे संपर्क करने को कह सकती हूँ।" }
        : { who: "ai", text: "I don't have that on this website. I can ask the team to get back to you." };
  }
}

type FBElement = HTMLElement & { ask?: (t: string) => void };
const realAgent = (): FBElement | null => (document.querySelector("fluid-buddha") as FBElement | null);

export default function AskBar() {
  const pathname = usePathname();
  const hiPage = pathname.startsWith("/hi");
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const body = useRef<HTMLDivElement>(null);

  useEffect(() => { body.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [msgs, busy]);

  const ask = useCallback(async (text: string) => {
    const t = text.trim();
    if (!t) return;
    const agent = realAgent();
    if (agent?.ask) { agent.ask(t); return; }          // the live agent answers
    setOpen(true);
    setMsgs((m) => [...m, { who: "me", text: t, hi: isHindi(t) }]);
    setBusy(true);
    await new Promise((r) => setTimeout(r, 650));
    const topic = classify(t);
    setMsgs((m) => [...m, reply(topic, isHindi(t) || hiPage)]);
    setBusy(false);
    window.dispatchEvent(new CustomEvent("fb:answered", { detail: { topic } }));
  }, [hiPage]);

  useEffect(() => {
    const on = (e: Event) => ask((e as CustomEvent<string>).detail);
    window.addEventListener("fb:ask", on);
    return () => window.removeEventListener("fb:ask", on);
  }, [ask]);

  const confirmBooking = (yes: boolean) => {
    setMsgs((m) => m.map((x): Msg => (x.extra === "book" ? { ...x, extra: yes ? "booked" : undefined } : x)).concat(
      { who: "me", text: yes ? (hiPage ? "हाँ" : "Yes") : (hiPage ? "अभी नहीं" : "Not now") },
      yes ? { who: "ai", text: hiPage ? "बुक हो गया। आपको ईमेल पर निमंत्रण मिलेगा।" : "Done. You'll get an email with the invite.", hi: hiPage }
          : { who: "ai", text: hiPage ? "कोई बात नहीं। कुछ भी बुक नहीं हुआ।" : "No problem. Nothing was booked.", hi: hiPage },
    ));
    if (yes) window.dispatchEvent(new CustomEvent("fb:answered", { detail: { topic: "book", confirmed: true } }));
  };

  const listen = () => {
    type SR = { lang: string; interimResults: boolean; onresult: (e: { results: { 0: { 0: { transcript: string } } } }) => void; onend: () => void; start: () => void };
    const W = window as unknown as { SpeechRecognition?: new () => SR; webkitSpeechRecognition?: new () => SR };
    const Ctor = W.SpeechRecognition || W.webkitSpeechRecognition;
    if (!Ctor) { setOpen(true); return; }
    const r = new Ctor(); r.lang = hiPage ? "hi-IN" : "en-IN"; r.interimResults = false;
    r.onresult = (e) => ask(e.results[0][0].transcript);
    r.onend = () => setListening(false);
    setListening(true); r.start();
  };

  const placeholder = hiPage ? "इस वेबसाइट से कुछ भी पूछिए" : "Ask this website anything";

  return (
    <div className={`${styles.root} ${open ? styles.open : ""}`}>
      {open && (
        <div className={`glass glass-strong ${styles.panel}`} role="dialog" aria-label="Conversation">
          <div className={styles.head}>
            <span className={styles.orb} />
            <div><b>Pragya</b><small>{busy ? (hiPage ? "सोच रही है" : "thinking") : (hiPage ? "तैयार" : "ready")}</small></div>
            <button className={styles.close} onClick={() => setOpen(false)} aria-label="Close">×</button>
          </div>
          <div className={styles.body} ref={body}>
            {msgs.length === 0 && (
              <p className={styles.empty}>{hiPage ? "कुछ भी पूछिए: कीमत, यह कैसे काम करता है, या डेमो बुक करें।" : "Ask about pricing, how it works, languages, security, or book a demo."}</p>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`${styles.msg} ${m.who === "me" ? styles.me : styles.ai} ${m.hi ? "deva" : ""}`}>
                <p>{m.text}</p>
                {m.extra === "plans" && (
                  <div className={styles.plans}>
                    <div><small>Free</small><b>₹0</b><small>100</small></div>
                    <div className={styles.hot}><small>Growth</small><b>₹33,000</b><small>2,000 / mo</small></div>
                    <div><small>Scale</small><b>₹1,25,000</b><small>10,000 / mo</small></div>
                  </div>
                )}
                {(m.extra === "book" || m.extra === "booked") && (
                  <div className={styles.book}>
                    <b>20-minute demo</b><span>Thursday, 11:00 AM · with our team</span>
                    {m.extra === "book" ? (
                      <div className={styles.row}>
                        <button className="btn btn-metal" onClick={() => confirmBooking(true)}>{hiPage ? "हाँ, बुक करें" : "Yes, book it"}</button>
                        <button className="btn btn-ghost" onClick={() => confirmBooking(false)}>{hiPage ? "अभी नहीं" : "Not now"}</button>
                      </div>
                    ) : <em className={styles.stamp}>Booked ✓</em>}
                  </div>
                )}
                {m.src && <Link href={m.src.href} className={styles.src}>Source · {m.src.label} ↗</Link>}
              </div>
            ))}
            {busy && <div className={`${styles.msg} ${styles.ai}`}><span className={styles.dots}><i /><i /><i /></span></div>}
          </div>
          <p className={styles.note}>Preview: replies are scripted from this site until the live agent is connected.</p>
        </div>
      )}
      <form className={`glass ${styles.bar}`} onSubmit={(e) => { e.preventDefault(); ask(value); setValue(""); }}>
        <input value={value} onChange={(e) => setValue(e.target.value)} onFocus={() => msgs.length && setOpen(true)}
               placeholder={placeholder} aria-label={placeholder} className={hiPage ? "deva" : ""} />
        <button type="button" className={`${styles.mic} ${listening ? styles.listening : ""}`} onClick={listen} aria-label="Speak">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
        </button>
      </form>
    </div>
  );
}
