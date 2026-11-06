"use client";

import { useEffect, useState } from "react";
import { CAPABILITIES, CAPABILITIES_HI, DEMO_QUESTIONS, DEMO_QUESTIONS_HI } from "@/content/home";
import styles from "./DemoStage.module.css";

/** Suggested questions + capability cards that light up as the agent answers each topic. */
export default function DemoStage({ hindi = false }: { hindi?: boolean }) {
  const [found, setFound] = useState<Set<string>>(new Set());
  useEffect(() => {
    const on = (e: Event) => setFound((s) => new Set(s).add((e as CustomEvent<{ topic: string }>).detail.topic));
    window.addEventListener("fb:answered", on);
    return () => window.removeEventListener("fb:answered", on);
  }, []);
  const ask = (t: string) => window.dispatchEvent(new CustomEvent("fb:ask", { detail: t }));
  const qs = hindi ? DEMO_QUESTIONS_HI : DEMO_QUESTIONS;
  const caps = hindi ? CAPABILITIES_HI : CAPABILITIES;

  return (
    <div className={styles.stage}>
      <div className={styles.chips}>
        {qs.map((q) => (
          <button key={q.label} className={`glass ${styles.chip} ${hindi || ("hi" in q && q.hi) ? "deva" : ""}`} onClick={() => ask(q.ask)}>{q.label}</button>
        ))}
      </div>
      <div className={styles.caps}>
        {caps.map((c) => (
          <div key={c.topic} className={`${styles.cap} ${found.has(c.topic) ? styles.on : ""}`}>
            <i>{found.has(c.topic) ? "✓" : ""}</i>
            <div><b>{c.title}</b><small>{c.body}</small></div>
          </div>
        ))}
      </div>
      <p className={styles.count}>{hindi ? `${caps.length} में से ${found.size} खोजे गए` : `You've discovered ${found.size} of ${caps.length} things it does`}</p>
    </div>
  );
}
