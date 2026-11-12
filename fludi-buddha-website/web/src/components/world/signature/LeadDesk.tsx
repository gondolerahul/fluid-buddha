"use client";

/**
 * The SaaS world's signature moment: "Be the buyer. Watch the lead build."
 * The visitor asks the three questions a buyer asks at 11 pm on a (fictional) inventory software's
 * pricing page. Each answer shows what the product does (draws, calculates, opens the right page),
 * and on the right the lead the sales team receives builds as it would arrive: score and reasons,
 * questions, pages. The same lead can be read as the card, the Slack message or the signed webhook.
 * All example data; nothing leaves the browser.
 */
import { useEffect, useRef, useState } from "react";
import { track } from "@/lib/world";

type Step = { id: "erp" | "seats" | "data"; q: string; a: string; points: number; reason: string; page: string; src: string };
const STEPS: Step[] = [
  { id: "erp", q: "Does it work with our ERP?", a: "Yes. Orders, stock and invoices sync both ways through the connector. Here is how it fits together.", points: 26, reason: "asked about integration", page: "/docs/integrations", src: "Integrations guide" },
  { id: "seats", q: "What would 60 seats cost?", a: "On the Team plan, 60 seats come to the figure below. Move the slider to try another size.", points: 30, reason: "priced a 60-seat team", page: "/pricing", src: "Price list" },
  { id: "data", q: "Where is our data kept?", a: "Section 4 of the security page answers that. I have opened it at the right paragraph.", points: 22, reason: "read the security page", page: "/security#data", src: "Security, section 4" },
];
const PER_SEAT = 1150; // example price list: ₹ per seat a month
const inr = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");

function Visual({ id, seats, setSeats }: { id: Step["id"]; seats: number; setSeats: (n: number) => void }) {
  if (id === "erp") {
    return (
      <div className="ld-flow" aria-label="Diagram: your ERP, the sync, your app">
        <span>ERP</span><i aria-hidden /><span>Sync</span><i aria-hidden /><span className="on">Your app</span>
        <small>orders, stock, invoices</small>
      </div>
    );
  }
  if (id === "seats") {
    return (
      <div className="ld-calc">
        <div className="ld-calc-top"><label htmlFor="ld-seats">Seats</label><output htmlFor="ld-seats" className="num">{seats}</output></div>
        <input id="ld-seats" type="range" className="range" min={10} max={150} step={5} value={seats} onChange={(e) => setSeats(+e.target.value)}
               style={{ ["--fill" as string]: `${((seats - 10) / 140) * 100}%` }} />
        <p className="num"><b>{inr(seats * PER_SEAT)}</b> a month <span>from the price list</span></p>
      </div>
    );
  }
  return (
    <div className="ld-page" aria-label="The security page, opened at section 4">
      <b>/security</b>
      <span className="ln" /><span className="ln short" />
      <span className="ln hot"><em>4. Where your data is kept</em></span>
      <span className="ln hot" /><span className="ln" />
    </div>
  );
}

export default function LeadDesk() {
  const [asked, setAsked] = useState<Step["id"][]>([]);
  const [typing, setTyping] = useState<Step["id"] | null>(null);
  const [seats, setSeats] = useState(60);
  const [view, setView] = useState<"card" | "slack" | "json">("card");
  const [score, setScore] = useState(0);
  const target = asked.reduce((s, id) => s + STEPS.find((x) => x.id === id)!.points, 0);
  const shown = useRef(0);
  const chat = useRef<HTMLDivElement>(null);

  // the score counts up to its new value
  useEffect(() => {
    // under reduced motion the score takes its new value in one frame
    const dur = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 1 : 900;
    let raf = 0; const from = shown.current, t0 = performance.now();
    const tick = (now: number) => {
      const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      const v = Math.round(from + (target - from) * e);
      shown.current = v; setScore(v);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  useEffect(() => { chat.current?.scrollTo({ top: 1e5, behavior: "smooth" }); }, [asked, typing]);

  const ask = (s: Step) => {
    if (asked.includes(s.id) || typing) return;
    track("lead_desk", { question: s.id });
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setTyping(s.id);
    window.setTimeout(() => { setTyping(null); setAsked((a) => [...a, s.id]); }, reduced ? 0 : 700);
  };
  const reset = () => { setAsked([]); setTyping(null); setSeats(60); setView("card"); };

  const steps = asked.map((id) => STEPS.find((x) => x.id === id)!);
  const hot = target >= 70;
  const json = JSON.stringify({
    event: "lead.created", score: target,
    reasons: steps.map((s) => `+${s.points} ${s.reason}`),
    asked: steps.map((s) => s.q),
    pages: ["/pricing", ...steps.map((s) => s.page).filter((p) => p !== "/pricing")],
    team_size: asked.includes("seats") ? seats : null,
  }, null, 2);

  return (
    <div className="ld">
      <div className="ld-pane ld-buyer">
        <div className="ld-head"><span className="ui-orb" aria-hidden /><b>Your pricing page, 23:04</b><span className="label">Example</span></div>
        <div className="ld-chat" ref={chat} aria-live="polite">
          {steps.length === 0 && !typing && <p className="ld-idle">You are a buyer with three questions. Ask the first one.</p>}
          {steps.map((s) => (
            <div key={s.id} className="ld-turn">
              <div className="ui-q">{s.q}</div>
              <div className="ui-a">
                <p>{s.a}</p>
                <Visual id={s.id} seats={seats} setSeats={setSeats} />
                <span className="ui-src">Source: {s.src}</span>
              </div>
            </div>
          ))}
          {typing && <><div className="ui-q">{STEPS.find((x) => x.id === typing)!.q}</div><div className="ui-a ask-typing" aria-label="Answering"><i /><i /><i /></div></>}
        </div>
        <div className="ld-ask" role="group" aria-label="The buyer's questions">
          {STEPS.map((s) => (
            <button key={s.id} type="button" className="chip" aria-pressed={asked.includes(s.id)} disabled={asked.includes(s.id) || !!typing} onClick={() => ask(s)}>{s.q}</button>
          ))}
          {asked.length === STEPS.length && <button type="button" className="chip" onClick={reset}>Start again</button>}
        </div>
      </div>

      <div className="ld-pane ld-team">
        <div className="ld-head">
          <b>What your team receives</b>
          <div className="ld-views" role="tablist" aria-label="View the lead as">
            {(["card", "slack", "json"] as const).map((v) => (
              <button key={v} type="button" role="tab" aria-selected={view === v} onClick={() => setView(v)}>{v === "card" ? "Lead" : v === "slack" ? "Slack" : "Webhook"}</button>
            ))}
          </div>
        </div>
        {view === "card" && (
          <div className="ld-card">
            <div className="ld-score">
              <svg viewBox="0 0 44 44" aria-hidden><circle cx="22" cy="22" r="19" className="trk" /><circle cx="22" cy="22" r="19" className="val" style={{ strokeDashoffset: 119.4 * (1 - score / 100) }} /></svg>
              <span className="num"><b>{score}</b>/100</span>
              <em className={hot ? "hot" : undefined}>{asked.length === 0 ? "Waiting for a question" : hot ? "Hot lead" : "Warming up"}</em>
            </div>
            <dl className="ld-kv">
              <dt>Why</dt><dd>{steps.length ? steps.map((s) => <span key={s.id} className="ld-reason">+{s.points} {s.reason}</span>) : <span className="ld-empty">Each answered question adds a reason.</span>}</dd>
              <dt>Asked</dt><dd>{steps.length ? steps.map((s) => s.q).join(" · ") : "Not yet"}</dd>
              <dt>Team size</dt><dd className="num">{asked.includes("seats") ? `${seats} seats` : "Not yet"}</dd>
              <dt>Pages</dt><dd className="t-mono">{["/pricing", ...steps.map((s) => s.page).filter((p) => p !== "/pricing")].join(" → ")}</dd>
              <dt>Sent to</dt><dd>{hot ? "#sales in Slack, and your CRM by signed webhook" : "Your CRM by signed webhook, once the visitor shares an email"}</dd>
            </dl>
          </div>
        )}
        {view === "slack" && (
          <div className="ld-slack">
            <div className="ld-slack-ch"># sales</div>
            <div className="ld-slack-msg">
              <span className="ui-orb" aria-hidden />
              <div>
                <b>FluidBuddha</b> <small>23:07</small>
                <p>{asked.length ? <>{hot ? "Hot lead" : "New lead"} on /pricing, score <b className="num">{target}</b>. Asked: {steps.map((s) => s.q).join(" ")}</> : "Nothing yet. Ask a question on the left."}</p>
                {asked.length > 0 && <span className="ld-slack-btn">Open the conversation</span>}
              </div>
            </div>
          </div>
        )}
        {view === "json" && <pre className="ui-code ld-json" aria-label="The webhook payload">{json}</pre>}
        <p className="note">Example lead on a fictional inventory software&apos;s site, with an example price list. Nothing leaves your browser.</p>
      </div>
    </div>
  );
}
