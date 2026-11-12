"use client";

/**
 * The Enterprise world's signature moment: the rule console.
 * "You write the rules. The product enforces them and shows you what it did", shown rather than said.
 * Five controls from the product (approved components, fields from your systems, excluded pages,
 * pinned notices, the review queue) and a page the AI has proposed for an example home-loans page.
 * Running the check walks the blocks one by one: each passes, is left out with its reason, or
 * passes with a warning when its rule is switched off. Every switch and every run is written to the
 * audit log. A simulation of the product's own check, in the browser; it runs once by itself.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { track } from "@/lib/world";

type RuleId = "approved" | "numbers" | "excluded" | "notice" | "review";
const RULES: { id: RuleId; label: string; ref: string }[] = [
  { id: "approved", label: "Only approved components", ref: "3.1" },
  { id: "numbers", label: "Rates only from your systems", ref: "3.2" },
  { id: "excluded", label: "Never link into checkout, legal or privacy", ref: "3.5" },
  { id: "notice", label: "Pin the required notice", ref: "3.6" },
  { id: "review", label: "Hold every page for review", ref: "3.8" },
];

type Status = "pass" | "out" | "warn";
type Block = { id: string; name: string; comp: string; judge: (r: Record<RuleId, boolean>) => { status: Status; why: string; mark?: string } };
const BLOCKS: Block[] = [
  { id: "notice", name: "Required notice", comp: "Pinned content", judge: (r) => r.notice
    ? { status: "pass", why: "Pinned by your compliance team. Shown unchanged.", mark: "pinned" }
    : { status: "warn", why: "No required notice on this page." } },
  { id: "hero", name: "Hero", comp: "HeroBanner v3", judge: () => ({ status: "pass", why: "Approved component.", mark: "approved" }) },
  { id: "rates", name: "Rate table", comp: "RateTable v2", judge: (r) => r.numbers
    ? { status: "pass", why: "Rate filled from your rates API, not by the AI.", mark: "from your systems" }
    : { status: "warn", why: "Rate written by the AI." } },
  { id: "quotes", name: "Customer quotes", comp: "QuoteCarousel v1", judge: (r) => r.approved
    ? { status: "out", why: "Left out: not an approved component." }
    : { status: "warn", why: "Unapproved component shown." } },
  { id: "apply", name: "Apply button", comp: "ApplyCTA v2 → /checkout/home-loan", judge: (r) => r.excluded
    ? { status: "out", why: "Left out: it links into checkout, an excluded page." }
    : { status: "warn", why: "Links into checkout." } },
  { id: "faq", name: "Questions", comp: "FAQ v2", judge: () => ({ status: "pass", why: "Approved component.", mark: "approved" }) },
];

const clock = () => new Date().toLocaleTimeString("en-GB", { hour12: false });

export default function RuleConsole() {
  const [rules, setRules] = useState<Record<RuleId, boolean>>({ approved: true, numbers: true, excluded: true, notice: true, review: true });
  const [step, setStep] = useState(-1);          // how many blocks have been checked in this run (-1: not run)
  const [running, setRunning] = useState(false);
  const [log, setLog] = useState<{ t: string; who: string; what: string }[]>([]);
  const [verdict, setVerdict] = useState<Record<RuleId, boolean> | null>(null); // the rules the last run used
  const root = useRef<HTMLDivElement>(null);
  const timers = useRef<number[]>([]);
  const started = useRef(false);

  const write = (who: string, what: string) => setLog((l) => [{ t: clock(), who, what }, ...l].slice(0, 9));

  const run = useCallback((auto = false) => {
    timers.current.forEach((t) => window.clearTimeout(t)); timers.current = [];
    const snapshot = { ...rules };
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!auto) track("rule_console_run", { ...snapshot });
    setVerdict(snapshot); setRunning(true); setStep(0);
    const finish = () => {
      const res = BLOCKS.map((b) => b.judge(snapshot));
      const out = res.filter((r) => r.status === "out").length, warn = res.filter((r) => r.status === "warn").length;
      write("check", `/home-loans: ${BLOCKS.length - out} shown, ${out} left out${warn ? `, ${warn} warning${warn > 1 ? "s" : ""}` : ""}`);
      write("review", snapshot.review ? "/home-loans held in the review queue" : `/home-loans published${warn ? " with warnings" : ""}`);
      setRunning(false);
    };
    if (reduced) { setStep(BLOCKS.length); finish(); return; }
    BLOCKS.forEach((_, i) => timers.current.push(window.setTimeout(() => setStep(i + 1), 360 * (i + 1))));
    timers.current.push(window.setTimeout(finish, 360 * BLOCKS.length + 200));
  }, [rules]);

  // it runs once by itself when it comes into view
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting) && !started.current) { started.current = true; run(true); io.disconnect(); }
    }, { threshold: 0.35 });
    io.observe(el);
    return () => io.disconnect();
  }, [run]);
  useEffect(() => () => timers.current.forEach((t) => window.clearTimeout(t)), []);

  const flip = (id: RuleId) => {
    const on = !rules[id];
    setRules((r) => ({ ...r, [id]: on }));
    setStep(-1); setVerdict(null);
    write("you", `${on ? "turned on" : "turned off"} “${RULES.find((r) => r.id === id)!.label}”`);
  };

  const results = verdict ? BLOCKS.map((b) => b.judge(verdict)) : null;
  const done = !!results && step >= BLOCKS.length && !running;
  const out = results?.filter((r) => r.status === "out").length ?? 0;
  const warn = results?.filter((r) => r.status === "warn").length ?? 0;

  return (
    <div className="rc" ref={root}>
      <div className="rc-col rc-rules">
        <h3 className="rc-h">Your rules</h3>
        <ul>
          {RULES.map((r) => (
            <li key={r.id}>
              <button type="button" role="switch" aria-checked={rules[r.id]} className="rc-switch" onClick={() => flip(r.id)}>
                <span className="rc-knob" aria-hidden />
                <span className="rc-label">{r.label}</span>
                <span className="rc-ref num">{r.ref}</span>
              </button>
            </li>
          ))}
        </ul>
        <button type="button" className="btn btn-primary rc-run" onClick={() => run()} disabled={running}>{running ? "Checking…" : "Run the check"}</button>
      </div>

      <div className="rc-col rc-plan">
        <h3 className="rc-h">Page proposed by the AI <span className="t-mono">/home-loans</span></h3>
        <ol>
          {BLOCKS.map((b, i) => {
            const res = results?.[i];
            const state = !results || step < i + 1 ? (running && step === i ? "checking" : "pending") : res!.status;
            return (
              <li key={b.id} className={`rc-block ${state}`}>
                <span className="rc-icon" aria-hidden />
                <div>
                  <b>{b.name}</b> <span className="t-mono">{b.comp}</span>
                  <p>{state === "pending" ? "Waiting for the check." : state === "checking" ? "Checking…" : res!.why}</p>
                </div>
                {state === "pass" && res!.mark && <em className="rc-mark">{res!.mark}</em>}
                <span className="sr-only">{state === "out" ? "Left out" : state === "warn" ? "Warning" : state === "pass" ? "Passed" : ""}</span>
              </li>
            );
          })}
        </ol>
      </div>

      <div className="rc-col rc-log">
        <h3 className="rc-h">Result</h3>
        <div className="rc-result" aria-live="polite">
          {done ? (
            <>
              <p><b className="num">{BLOCKS.length - out}</b> shown <span>&middot;</span> <b className="num">{out}</b> left out <span>&middot;</span> <b className="num">{warn}</b> warnings</p>
              <p className={verdict?.review ? "held" : warn ? "risk" : undefined}>{verdict?.review ? "Held for review before any visitor sees it." : warn ? "Published with warnings. Your rules were off." : "Published."}</p>
            </>
          ) : <p className="rc-wait">{running ? "Checking the page against your rules…" : "Switch a rule, then run the check."}</p>}
        </div>
        <h3 className="rc-h">Audit log</h3>
        <ol className="rc-lines">
          {log.length === 0 && <li className="rc-wait">Every change is written here.</li>}
          {log.map((l, i) => <li key={`${l.t}-${i}`}><span className="num">{l.t}</span><b>{l.who}</b><span>{l.what}</span></li>)}
        </ol>
      </div>
    </div>
  );
}
