"use client";

/**
 * "Ask Pragya": a small light in the corner of every page that opens a conversation, like the
 * product's own Companion design level. Pragya is the agent's default name (FeatureList §1).
 *
 * If the real FluidBuddha widget is loaded (AgentLoader), questions go to it through its public
 * `ask()` method. Until then the panel runs a clearly labelled preview with scripted answers taken
 * from this site's own pages (lib/answers.ts).
 *
 * Other components can ask:            window.dispatchEvent(new CustomEvent("fb:ask", { detail: "…" }))
 * Each answered topic is announced:     window.addEventListener("fb:answered", e => e.detail.topic)
 */
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { answer, BOOKED, classify, isHindi, PREVIEW_NOTE, type Answer } from "@/lib/answers";
import { goWorld } from "@/lib/world";
import { getLang } from "@/lib/lang";

type Msg = { who: "me" | "ai"; text: string; hindi?: boolean; a?: Answer; booked?: boolean };
type FBElement = HTMLElement & { ask?: (t: string) => void };
const realAgent = () => document.querySelector("fluid-buddha") as FBElement | null;

const SUGGEST = ["What does it cost?", "Does it speak Hindi?", "Where do the answers come from?", "Book a demo"];

export default function AskPragya() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const body = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { body.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [msgs, busy]);
  useEffect(() => { if (open) input.current?.focus({ preventScroll: true }); }, [open]);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [open]);

  const ask = useCallback(async (text: string) => {
    const t = text.trim();
    if (!t) return;
    const agent = realAgent();
    if (agent?.ask) { agent.ask(t); return; } // the live agent answers
    setOpen(true);
    const hi = isHindi(t) || getLang() === "hi";
    setMsgs((m) => [...m, { who: "me", text: t, hindi: isHindi(t) }]);
    setBusy(true);
    await new Promise((r) => setTimeout(r, 650));
    const a = answer(classify(t), hi);
    setMsgs((m) => [...m, { who: "ai", text: a.text, hindi: a.hindi, a }]);
    setBusy(false);
    window.dispatchEvent(new CustomEvent("fb:answered", { detail: { topic: a.topic } }));
    if (a.act) window.setTimeout(() => goWorld(a.act!.world, "ask"), 1400);
  }, []);

  useEffect(() => {
    const on = (e: Event) => ask((e as CustomEvent<string>).detail);
    window.addEventListener("fb:ask", on);
    return () => window.removeEventListener("fb:ask", on);
  }, [ask]);

  const confirm = (i: number, yes: boolean) => {
    setMsgs((m) => m.map((x, k) => (k === i ? { ...x, booked: yes, a: x.a && { ...x.a, visual: undefined } } : x)).concat(
      { who: "me", text: yes ? "Yes, book it" : "Not now" },
      { who: "ai", text: yes ? BOOKED : "No problem. Nothing was booked." },
    ));
    if (yes) window.dispatchEvent(new CustomEvent("fb:answered", { detail: { topic: "book", confirmed: true } }));
  };

  const listen = () => {
    type SR = { lang: string; interimResults: boolean; onresult: (e: { results: { 0: { 0: { transcript: string } } } }) => void; onend: () => void; start: () => void };
    const W = window as unknown as { SpeechRecognition?: new () => SR; webkitSpeechRecognition?: new () => SR };
    const Ctor = W.SpeechRecognition || W.webkitSpeechRecognition;
    if (!Ctor) { setOpen(true); input.current?.focus(); return; }
    const r = new Ctor(); r.lang = getLang() === "hi" ? "hi-IN" : "en-IN"; r.interimResults = false;
    r.onresult = (e) => ask(e.results[0][0].transcript);
    r.onend = () => setListening(false);
    setListening(true); r.start();
  };

  return (
    <div className="ask tone-ink" data-open={open || undefined}>
      {open && (
        <div className="ask-panel" role="dialog" aria-label="Ask Pragya">
          <div className="ask-head">
            <span className="ui-orb" aria-hidden />
            <div><b>Pragya</b><small aria-live="polite">{busy ? "thinking" : "answers from this site"}</small></div>
            <button type="button" className="ask-x" onClick={() => setOpen(false)} aria-label="Close">
              <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
            </button>
          </div>
          <div className="ask-body" ref={body}>
            {msgs.length === 0 && (
              <div className="ask-empty">
                <p>Ask about pricing, Hindi, security or how it works. I answer from this site&apos;s pages and show where each answer came from.</p>
                <div className="ask-sugg">{SUGGEST.map((s) => <button key={s} type="button" className="chip" onClick={() => ask(s)}>{s}</button>)}</div>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={m.who === "me" ? "ui-q" : "ui-a"} lang={m.hindi ? "hi" : undefined}>
                <p className={m.hindi ? "deva" : undefined}>{m.text}</p>
                {m.a?.visual === "plans" && (
                  <div className="ask-plans">
                    <div><small>Free</small><b>₹0</b><small>100 a month</small></div>
                    <div className="on"><small>Growth</small><b>₹33,000</b><small>2,000 a month</small></div>
                    <div><small>Scale</small><b>₹1,25,000</b><small>10,000 a month</small></div>
                  </div>
                )}
                {m.a?.visual === "confirm" && m.booked === undefined && (
                  <div className="ask-confirm">
                    <b>20-minute demo with the team</b>
                    <span>Nothing is booked until you say yes</span>
                    <div className="ctas"><button type="button" className="btn btn-primary btn-sm" onClick={() => confirm(i, true)}>Yes, book it</button><button type="button" className="btn btn-quiet btn-sm" onClick={() => confirm(i, false)}>Not now</button></div>
                  </div>
                )}
                {m.a?.src && <Link href={m.a.src.href} className="ui-src">Source: {m.a.src.label}</Link>}
              </div>
            ))}
            {busy && <div className="ui-a ask-typing" aria-hidden><i /><i /><i /></div>}
          </div>
          <form className="ask-form" onSubmit={(e) => { e.preventDefault(); ask(value); setValue(""); }}>
            <label className="sr-only" htmlFor="ask-input">Your question</label>
            <input id="ask-input" ref={input} value={value} onChange={(e) => setValue(e.target.value)} placeholder="Ask in English or Hindi" autoComplete="off" />
            <button type="button" className={`ask-mic${listening ? " on" : ""}`} onClick={listen} aria-label="Ask by voice">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" aria-hidden><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
            </button>
          </form>
          <p className="ask-note">{PREVIEW_NOTE}</p>
        </div>
      )}
      <button type="button" className="ask-launch" aria-expanded={open} aria-label={open ? "Close the conversation" : "Ask Pragya, this site's agent"} onClick={() => setOpen(!open)}>
        <span className="ask-light" aria-hidden />
        <span className="ask-label">Ask Pragya</span>
      </button>
    </div>
  );
}
