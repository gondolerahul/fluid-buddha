"use client";

import { useMemo, useState } from "react";
import styles from "./CostCalculator.module.css";

// Real plan prices (FeatureList §6). The recommendation picks the cheapest plan for the volume.
const PLANS = [
  { name: "Free", base: 0, included: 100, over: null as number | null },
  { name: "Growth", base: 33000, included: 2000, over: 17 },
  { name: "Scale", base: 125000, included: 10000, over: 10 },
];
const inr = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");

export default function CostCalculator() {
  const [conv, setConv] = useState(3000);
  const rows = useMemo(() => PLANS.map((p) => {
    if (p.over === null) return { ...p, total: conv <= p.included ? 0 : null };
    return { ...p, total: p.base + Math.max(0, conv - p.included) * p.over };
  }), [conv]);
  const best = rows.filter((r) => r.total !== null).sort((a, b) => (a.total! - b.total!))[0];

  return (
    <div className={`card ${styles.calc}`}>
      <div className={styles.head}>
        <label htmlFor="conv" className="eyebrow">Conversations a month</label>
        <output className={styles.value}>{conv.toLocaleString("en-IN")}</output>
      </div>
      <input id="conv" type="range" min={50} max={20000} step={50} value={conv} onChange={(e) => setConv(+e.target.value)} className={styles.range} />
      <div className={styles.rows}>
        {rows.map((r) => (
          <div key={r.name} className={`${styles.row} ${best && r.name === best.name ? styles.best : ""}`}>
            <span>{r.name}</span>
            <b>{r.total === null ? "Over the free limit" : inr(r.total)}</b>
            <small>{r.total ? `${inr(r.total / conv)} per conversation` : r.total === 0 ? "Free" : ""}</small>
          </div>
        ))}
      </div>
      {best && <p className={styles.rec}>Best fit: <b>{best.name}</b>. A conversation is a visitor session with at least one answered turn; calls from AI assistants are not counted.</p>}
    </div>
  );
}
