"use client";

import { useEffect, useState } from "react";
import { CAPABILITIES, DEMO_QUESTIONS } from "@/content/demo";

/** Questions to try, and the capabilities they reveal as the agent answers each one. */
export default function DemoStage() {
  const [found, setFound] = useState<Set<string>>(new Set());
  useEffect(() => {
    const on = (e: Event) => setFound((s) => new Set(s).add((e as CustomEvent<{ topic: string }>).detail.topic));
    window.addEventListener("fb:answered", on);
    return () => window.removeEventListener("fb:answered", on);
  }, []);
  const ask = (t: string) => window.dispatchEvent(new CustomEvent("fb:ask", { detail: t }));

  return (
    <div className="dm-panel">
      <p className="dm-hint">Questions to try</p>
      <div className="dm-chips">
        {DEMO_QUESTIONS.map((q) => (
          <button key={q.label} type="button" className={`chip${q.hi ? " deva" : ""}`} lang={q.hi ? "hi" : undefined} onClick={() => ask(q.label)}>{q.label}</button>
        ))}
      </div>
      <div className="dm-caps">
        {CAPABILITIES.map((c) => (
          <div key={c.topic} className={`dm-cap${found.has(c.topic) ? " on" : ""}`}>
            <i aria-hidden />
            <div><b>{c.title}</b><small>{c.body}</small></div>
          </div>
        ))}
      </div>
      <p className="dm-count" aria-live="polite">You have found {found.size} of {CAPABILITIES.length} things it does.</p>
    </div>
  );
}
