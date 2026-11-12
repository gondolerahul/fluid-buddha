"use client";

import { useMemo, useState } from "react";

// Real plan prices (FeatureList §6). The recommendation picks the cheapest plan for the volume.
const PLANS = [
  { name: "Free", base: 0, included: 100, over: null as number | null },
  { name: "Growth", base: 33000, included: 2000, over: 17 },
  { name: "Scale", base: 125000, included: 10000, over: 10 },
];
const MIN = 50, MAX = 20000;
const inr = (n: number) => "₹" + Math.round(n).toLocaleString("en-IN");

export default function CostCalculator({ initial = 3000, id = "conv" }: { initial?: number; id?: string }) {
  const [conv, setConv] = useState(initial);
  const rows = useMemo(() => PLANS.map((p) => {
    if (p.over === null) return { ...p, total: conv <= p.included ? 0 : null };
    return { ...p, total: p.base + Math.max(0, conv - p.included) * p.over };
  }), [conv]);
  const best = rows.filter((r) => r.total !== null).sort((a, b) => a.total! - b.total!)[0];
  const fill = `${((conv - MIN) / (MAX - MIN)) * 100}%`;

  return (
    <div className="calc">
      <div className="calc-head">
        <label htmlFor={id} className="label">Conversations a month</label>
        <output htmlFor={id} className="calc-val num">{conv.toLocaleString("en-IN")}</output>
      </div>
      <input id={id} type="range" min={MIN} max={MAX} step={50} value={conv} onChange={(e) => setConv(+e.target.value)}
             className="range" style={{ ["--fill" as string]: fill }} aria-valuetext={`${conv.toLocaleString("en-IN")} conversations a month`} />
      <div className="calc-rows" aria-live="polite">
        {rows.map((r) => (
          <div key={r.name} className={`calc-row${best && r.name === best.name ? " best" : ""}`}>
            <span>{r.name}</span>
            <b>{r.total === null ? "Over the limit" : inr(r.total)}</b>
            <small>{r.total ? `${inr(r.total / conv)} a conversation` : r.total === 0 ? "Free" : "Free covers 100 a month"}</small>
          </div>
        ))}
      </div>
      {best && <p className="calc-rec">Best fit: <b>{best.name}</b>. A conversation is a visitor session with at least one answered turn; calls from AI assistants are not counted.</p>}
    </div>
  );
}
