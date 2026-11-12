"use client";

/**
 * The Education world's signature moment: "Your English page, answered in Hindi."
 * On the left, an (example) English fee page. On the right, a student's phone. The visitor picks a
 * question in Hindi, Hinglish or English; the answer types out in the language it was asked in, the
 * sentence it came from lights up on the English page, and a gold line runs from the answer to it:
 * the film's own sign for "an answer and its source". It plays its first question by itself, once.
 *
 * The Hindi answers here are new lines written for this demonstration: they need the same native
 * review as the rest of the Hindi before launch (docs/marketing-docs/website/audit-2026-11-11.md §6).
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { track } from "@/lib/world";

type Q = { id: string; ask: string; askLang: "hi" | "hinglish" | "en"; answer: string; answerHi: boolean; line: number };

// The example fee page, sentence by sentence. Figures are examples.
const PAGE = [
  "The MBA is a two-year, full-time programme with 120 places.",
  "Tuition for the first year is ₹4,80,000, payable in two instalments.",
  "Merit scholarships of up to 25% of tuition are awarded automatically; no separate application is needed.",
  "Hostel places are allotted after admission, on request.",
  "Applications close on 31 March. The application fee is ₹1,500.",
];
const QS: Q[] = [
  { id: "fee", ask: "MBA की फ़ीस कितनी है?", askLang: "hi", answerHi: true, line: 1,
    answer: "MBA के पहले साल की ट्यूशन फ़ीस ₹4,80,000 है। इसे दो किस्तों में भरा जा सकता है।" },
  { id: "scholarship", ask: "Scholarship kaise milegi?", askLang: "hinglish", answerHi: true, line: 2,
    answer: "मेरिट के आधार पर ट्यूशन फ़ीस पर 25% तक की स्कॉलरशिप अपने आप मिलती है। इसके लिए अलग से आवेदन नहीं करना होता।" },
  { id: "deadline", ask: "When do applications close?", askLang: "en", answerHi: false, line: 4,
    answer: "Applications close on 31 March. The application fee is ₹1,500, and I can send you the payment link when you are ready." },
];

export default function HindiAnswer() {
  const [cur, setCur] = useState<Q | null>(null);
  const [shown, setShown] = useState(0);
  const [typing, setTyping] = useState(false);
  const [path, setPath] = useState<string | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const bubble = useRef<HTMLDivElement>(null);
  const lines = useRef<(HTMLSpanElement | null)[]>([]);
  const timers = useRef<number[]>([]);
  const started = useRef(false);

  const clear = () => { timers.current.forEach((t) => window.clearTimeout(t)); timers.current = []; };
  const later = (fn: () => void, ms: number) => { timers.current.push(window.setTimeout(fn, ms)); };

  const ask = useCallback((q: Q, auto = false) => {
    clear();
    setPath(null);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const n = q.answer.split(/\s+/).length;
    setCur(q);
    if (!auto) track("hindi_answer", { question: q.id });
    if (reduced) { setTyping(false); setShown(n); return; }
    setTyping(true); setShown(0);
    later(() => { setTyping(false); for (let i = 1; i <= n; i++) later(() => setShown(i), i * 90); }, 700);
  }, []);

  // the first question plays by itself, once, when the section comes into view
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting) && !started.current) { started.current = true; ask(QS[0], true); io.disconnect(); }
    }, { threshold: 0.4 });
    io.observe(el);
    return () => { io.disconnect(); clear(); };
  }, [ask]);

  const words = cur ? cur.answer.split(/\s+/) : [];
  const done = !!cur && !typing && shown >= words.length;

  // the gold line, from the answer to the sentence it came from (side by side only)
  const measure = useCallback(() => {
    const box = root.current, b = bubble.current, l = cur ? lines.current[cur.line] : null;
    if (!box || !b || !l || !done || window.innerWidth < 900) { setPath(null); return; }
    const r = box.getBoundingClientRect(), rb = b.getBoundingClientRect(), rl = l.getBoundingClientRect();
    const x1 = rb.left - r.left - 6, y1 = rb.top - r.top + Math.min(28, rb.height / 2);
    const x0 = rl.right - r.left + 10, y0 = rl.top - r.top + rl.height / 2;
    const mx = (x0 + x1) / 2;
    setPath(`M${x0.toFixed(1)} ${y0.toFixed(1)} C ${mx.toFixed(1)} ${y0.toFixed(1)}, ${mx.toFixed(1)} ${y1.toFixed(1)}, ${x1.toFixed(1)} ${y1.toFixed(1)}`);
  }, [cur, done]);
  // the line depends on the laid-out positions, so it is measured after layout
  useLayoutEffect(() => { measure(); }, [measure]);
  useEffect(() => {
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [measure]);

  return (
    <div className="ha" ref={root}>
      <figure className="ha-page" aria-label="An example English fee page">
        <div className="ha-page-bar"><span>yourcollege.edu.in/programmes/mba/fees</span></div>
        <h3>MBA: fees and admission</h3>
        <p>
          {PAGE.map((s, i) => (
            <span key={i} ref={(el) => { lines.current[i] = el; }} className={`ha-line${done && cur?.line === i ? " lit" : ""}`}>{s} </span>
          ))}
        </p>
        <figcaption className="note">An example page with example figures. Yours stays in English.</figcaption>
      </figure>

      <div className="ha-phone">
        <div className="ha-screen">
          <div className="ha-top"><span className="ui-orb" aria-hidden /><b>Admissions</b><small>answers from this website</small></div>
          <div className="ha-chat" aria-live="polite">
            {!cur && <p className="ha-idle">Ask in Hindi, Hinglish or English.</p>}
            {cur && <div className="ui-q" lang={cur.askLang === "hi" ? "hi" : undefined}>{cur.ask}</div>}
            {typing && <div className="ui-a ask-typing" aria-label="Answering"><i /><i /><i /></div>}
            {cur && !typing && (
              <div className="ui-a" ref={bubble} lang={cur.answerHi ? "hi" : undefined}>
                <p className={cur.answerHi ? "deva" : undefined}>{words.map((w, i) => <span key={i} className={i < shown ? "w on" : "w"}>{w} </span>)}</p>
                {done && <span className="ui-src">{cur.answerHi ? "स्रोत" : "Source"}: /programmes/mba/fees</span>}
              </div>
            )}
          </div>
          <div className="ha-qs" role="group" aria-label="Questions a student asks">
            {QS.map((q) => (
              <button key={q.id} type="button" className="chip" aria-pressed={cur?.id === q.id} lang={q.askLang === "hi" ? "hi" : undefined} onClick={() => ask(q)}>{q.ask}</button>
            ))}
          </div>
        </div>
      </div>

      {path && (
        <svg className="ha-wire" aria-hidden>
          <path d={path} pathLength={1} />
        </svg>
      )}
    </div>
  );
}
