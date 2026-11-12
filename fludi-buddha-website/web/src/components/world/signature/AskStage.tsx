"use client";

/**
 * The default world's signature moment: "Don't read about it. Talk to it."
 * The visitor picks a question; the page answers word by word with its source, draws what the answer
 * needs (a calculator, a confirm card), and the source chip takes the visitor to the section of this
 * very page it came from and rings it in gold, the product's own "section spotlight". One question
 * changes the whole site into the version for banks. It plays its first question by itself, once,
 * when it comes into view. Scripted from this site's pages until the live agent is connected.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { answer, BOOKED, classify, PREVIEW_NOTE, type Answer } from "@/lib/answers";
import { goWorld, track } from "@/lib/world";

const inr = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");

function MiniCalc() {
  const [n, setN] = useState(3000);
  const growth = 33000 + Math.max(0, n - 2000) * 17, scale = 125000 + Math.max(0, n - 10000) * 10;
  const best = n <= 100 ? "Free" : growth <= scale ? "Growth" : "Scale";
  return (
    <div className="as-calc">
      <div className="as-calc-top"><label htmlFor="as-n">Conversations a month</label><output htmlFor="as-n" className="num">{n.toLocaleString("en-IN")}</output></div>
      <input id="as-n" type="range" className="range" min={100} max={15000} step={100} value={n} onChange={(e) => setN(+e.target.value)}
             style={{ ["--fill" as string]: `${((n - 100) / 14900) * 100}%` }} />
      <div className="as-calc-rows num">
        <span className={best === "Growth" ? "on" : undefined}>Growth <b>{inr(growth)}</b></span>
        <span className={best === "Scale" ? "on" : undefined}>Scale <b>{inr(scale)}</b></span>
      </div>
    </div>
  );
}

export default function AskStage({ questions }: { questions: { label: string; hi?: boolean }[] }) {
  const [q, setQ] = useState<string | null>(null);
  const [a, setA] = useState<Answer | null>(null);
  const [shown, setShown] = useState(0); // words of the answer on screen
  const [typing, setTyping] = useState(false);
  const [booked, setBooked] = useState<boolean | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);
  const started = useRef(false);

  const clear = () => { timers.current.forEach((t) => window.clearTimeout(t)); timers.current = []; };
  const later = (fn: () => void, ms: number) => { timers.current.push(window.setTimeout(fn, ms)); };

  const ask = useCallback((label: string, auto = false) => {
    clear();
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ans = answer(classify(label));
    const words = ans.text.split(/\s+/).length;
    setQ(label); setA(ans); setBooked(null);
    if (!auto) track("ask_stage", { question: label, topic: ans.topic });
    if (reduced) { setTyping(false); setShown(words); }
    else {
      setTyping(true); setShown(0);
      later(() => {
        setTyping(false);
        for (let i = 1; i <= words; i++) later(() => setShown(i), i * 55);
      }, 650);
    }
    window.dispatchEvent(new CustomEvent("fb:answered", { detail: { topic: ans.topic } }));
    if (ans.act) later(() => goWorld(ans.act!.world, "ask"), reduced ? 900 : 650 + words * 55 + 900);
  }, []);

  // the first question plays by itself, once, when the stage comes into view
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting) && !started.current) { started.current = true; ask(questions[0].label, true); io.disconnect(); }
    }, { threshold: 0.45 });
    io.observe(el);
    return () => { io.disconnect(); clear(); };
  }, [ask, questions]);

  /** The source chip: go to the section of this page the answer came from, and ring it in gold. */
  const spotlight = (sel?: string, href?: string) => {
    const target = sel ? document.querySelector<HTMLElement>(sel) : null;
    if (!target) { if (href) window.location.href = href; return; }
    track("ask_stage_source", { to: sel });
    const ring = target.querySelector<HTMLElement>(".wrap") ?? target;
    target.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
    ring.classList.remove("is-spot"); void ring.offsetWidth; ring.classList.add("is-spot");
    window.setTimeout(() => ring.classList.remove("is-spot"), 3200);
  };

  const words = a ? a.text.split(/\s+/) : [];
  const done = !!a && !typing && shown >= words.length;
  return (
    <div className="as" ref={box}>
      <div className="as-qs" role="group" aria-label="Questions to ask">
        {questions.map((x) => (
          <button key={x.label} type="button" className="as-q" aria-pressed={q === x.label} onClick={() => ask(x.label)} lang={x.hi ? "hi" : undefined}>
            <span>{x.label}</span><span className="arrow" aria-hidden>&rarr;</span>
          </button>
        ))}
        <p className="note">{PREVIEW_NOTE}</p>
      </div>

      <div className="ui-frame as-frame tone-main">
        <div className="ui-bar"><span className="ui-orb" aria-hidden /><b>Pragya</b><span>answering from this site</span></div>
        <div className="ui-body as-body" aria-live="polite">
          {!q && <p className="as-idle">Pick a question.</p>}
          {q && <div className="ui-q">{q}</div>}
          {typing && <div className="ui-a ask-typing" aria-label="Thinking"><i /><i /><i /></div>}
          {a && !typing && (
            <div className="ui-a as-a" lang={a.hindi ? "hi" : undefined}>
              <p className={a.hindi ? "deva" : undefined}>
                {words.map((w, i) => <span key={i} className={i < shown ? "w on" : "w"}>{w} </span>)}
              </p>
              {done && a.visual === "plans" && (
                <div className="ask-plans">
                  <div><small>Free</small><b>₹0</b><small>100 a month</small></div>
                  <div className="on"><small>Growth</small><b>₹33,000</b><small>2,000 a month</small></div>
                  <div><small>Scale</small><b>₹1,25,000</b><small>10,000 a month</small></div>
                </div>
              )}
              {done && a.visual === "calc" && <MiniCalc />}
              {done && a.visual === "confirm" && booked === null && (
                <div className="ask-confirm">
                  <b>20-minute demo with the team</b><span>Nothing is booked until you say yes</span>
                  <div className="ctas">
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => setBooked(true)}>Yes, book it</button>
                    <button type="button" className="btn btn-quiet btn-sm" onClick={() => setBooked(false)}>Not now</button>
                  </div>
                </div>
              )}
              {done && booked !== null && <p className="as-after">{booked ? BOOKED : "No problem. Nothing was booked."}</p>}
              {done && a.act && <p className="as-after">One moment&hellip;</p>}
              {done && a.src && (
                <button type="button" className="ui-src" onClick={() => spotlight(a.src!.spot, a.src!.href)}>
                  Source: {a.src.label} <span aria-hidden>{a.src.spot ? "↓" : "↗"}</span>
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
