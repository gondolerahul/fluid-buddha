"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useParams } from "next/navigation";
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Analytics, Api } from "@/lib/api";
import { fmtUSD } from "@/components/ui";

type Group = "day" | "hour" | "session";

const subscribeNoop = () => () => {};

const CATS = [
  { key: "asr_cost", label: "ASR", color: "var(--c-asr)" },
  { key: "tts_cost", label: "TTS", color: "var(--c-tts)" },
  { key: "fast_llm_cost", label: "Fast LLM", color: "var(--c-fast)" },
  { key: "thinker_llm_cost", label: "Thinker LLM", color: "var(--c-thinker)" },
  { key: "tool_cost", label: "Tool calls", color: "var(--c-tool)" },
] as const;

// resolve CSS var → hex for recharts (which can't read CSS vars in SVG fills cleanly)
const COLORS: Record<string, string> = {
  "var(--c-asr)": "#60a5fa",
  "var(--c-tts)": "#a78bfa",
  "var(--c-fast)": "#4ade80",
  "var(--c-thinker)": "#ffd23f",
  "var(--c-tool)": "#fb7185",
};

export default function AnalyticsPage() {
  const id = String(useParams().id);
  const [group, setGroup] = useState<Group>("day");
  // Each result remembers which (site, grouping) it is for, so switching the
  // grouping shows the skeleton until the matching data arrives — without a
  // synchronous setState inside the effect.
  const [result, setResult] = useState<{ key: string; data: Analytics | null } | null>(null);
  const key = `${id}:${group}`;
  const data = result?.key === key ? result.data : null;
  // recharts measures the DOM, so charts render only on the client.
  const mounted = useSyncExternalStore(subscribeNoop, () => true, () => false);

  useEffect(() => {
    Api.analytics(id, group)
      .then((d) => setResult({ key, data: d }))
      .catch(() => setResult({ key, data: null }));
  }, [id, group, key]);

  const t = data?.totals;
  const perf = data?.performance;
  const split = data?.cache_split;

  const pieData = data
    ? CATS.map((c) => ({ name: c.label, value: t?.[c.key] || 0, color: COLORS[c.color] }))
        .filter((d) => d.value > 0)
    : [];
  const splitData = split
    ? [
        { name: "Generated", value: split.generated.turns, color: "#ffd23f" },
        { name: "Cached", value: split.cached.turns, color: "#4ade80" },
      ].filter((d) => d.value > 0)
    : [];

  return (
    <div className="fade-in">
      <div className="row between page-head wrap" style={{ gap: 12 }}>
        <div>
          <h2>Cost &amp; performance</h2>
          <p className="muted" style={{ fontSize: "0.88rem" }}>
            Spend by stage, and what the cache saves you.
          </p>
        </div>
        <div className="tabs" style={{ border: "none", margin: 0 }}>
          {(["day", "hour", "session"] as Group[]).map((g) => (
            <button key={g} className={`tab ${group === g ? "active" : ""}`}
              onClick={() => setGroup(g)} style={{ textTransform: "capitalize" }}>
              {g}-wise
            </button>
          ))}
        </div>
      </div>

      {/* KPI row */}
      <div className="grid" style={{ marginBottom: 20,
        gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}>
        <Kpi label="Total cost" value={t ? fmtUSD(t.total_cost) : "…"}
          hint={perf?.cost_per_conversation != null
            ? `${fmtUSD(perf.cost_per_conversation)} per conversation · ${perf.conversations} conversations` : ""} />
        <Kpi label="Turns" value={t ? String(t.turns) : "…"}
          hint={t ? `${t.generated_turns} generated · ${t.cached_turns} cached` : ""} />
        <Kpi label="Cache hit rate" value={perf ? `${(perf.cache_hit_rate * 100).toFixed(0)}%` : "…"}
          hint="Served without an LLM call" />
        <Kpi label="Latency p95" value={perf ? `${Math.round(perf.p95_latency_ms)} ms` : "…"}
          hint={perf ? `p50 ${Math.round(perf.p50_latency_ms)} ms` : ""} />
        <Kpi label="Time to first audio"
          value={!perf ? "…" : perf.p50_ttfa_ms == null ? "—" : `${Math.round(perf.p50_ttfa_ms)} ms`}
          hint={!perf ? "" : perf.p95_ttfa_ms == null ? "No spoken turns yet"
            : `median · p95 ${Math.round(perf.p95_ttfa_ms)} ms · ${perf.ttfa_turns} voice turns`} />
      </div>

      {/* Stacked cost-over-time */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="row between" style={{ marginBottom: 16 }}>
          <h3>Cost by stage — {group}-wise</h3>
          <div className="legend">
            {CATS.map((c) => (
              <span key={c.key}><span className="swatch" style={{ background: COLORS[c.color] }} />{c.label}</span>
            ))}
          </div>
        </div>
        {!mounted || !data ? (
          <div className="skeleton" style={{ height: 300 }} />
        ) : data.series.length === 0 ? (
          <div className="empty">No usage in this range yet. Talk to the agent to generate data.</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.series} margin={{ top: 4, right: 8, left: 4, bottom: 4 }}>
              <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="bucket" tick={{ fill: "#aab1c0", fontSize: 11 }}
                tickFormatter={shortBucket} stroke="rgba(255,255,255,0.12)" />
              <YAxis tick={{ fill: "#aab1c0", fontSize: 11 }} stroke="rgba(255,255,255,0.12)"
                tickFormatter={(v) => fmtUSD(v)} width={70} />
              <Tooltip {...tooltipStyle} formatter={(v: number) => fmtUSD(v)} />
              {CATS.map((c) => (
                <Bar key={c.key} dataKey={c.key} name={c.label} stackId="cost"
                  fill={COLORS[c.color]} radius={c.key === "tool_cost" ? [3, 3, 0, 0] : undefined} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Breakdown + cache split */}
      <div className="grid grid-2">
        <div className="card">
          <h3 style={{ marginBottom: 14 }}>Cost breakdown</h3>
          {mounted && pieData.length > 0 ? (
            <div className="row" style={{ gap: 18 }}>
              <ResponsiveContainer width="50%" height={200}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={78} paddingAngle={2}>
                    {pieData.map((d, i) => <Cell key={i} fill={d.color} stroke="none" />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} formatter={(v: number) => fmtUSD(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className="stack-sm" style={{ flex: 1 }}>
                {CATS.map((c) => (
                  <div key={c.key} className="row between">
                    <span className="row" style={{ gap: 8 }}>
                      <span className="swatch" style={{ background: COLORS[c.color] }} />
                      <span className="muted">{c.label}</span>
                    </span>
                    <span className="mono">{fmtUSD(t?.[c.key] || 0)}</span>
                  </div>
                ))}
                <div className="divider" />
                <div className="row between">
                  <strong>Total</strong>
                  <strong className="mono">{fmtUSD(t?.total_cost || 0)}</strong>
                </div>
              </div>
            </div>
          ) : (
            <div className="empty">No cost recorded yet.</div>
          )}
        </div>

        <div className="card">
          <h3 style={{ marginBottom: 4 }}>Generated vs cached</h3>
          <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 14 }}>
            Cached turns skip the LLM — that&apos;s your saving.
          </p>
          {mounted && splitData.length > 0 ? (
            <div className="row" style={{ gap: 18 }}>
              <ResponsiveContainer width="50%" height={200}>
                <PieChart>
                  <Pie data={splitData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={78} paddingAngle={2}>
                    {splitData.map((d, i) => <Cell key={i} fill={d.color} stroke="none" />)}
                  </Pie>
                  <Tooltip {...tooltipStyle} />
                </PieChart>
              </ResponsiveContainer>
              <div className="stack-sm" style={{ flex: 1 }}>
                <div className="row between">
                  <span className="row" style={{ gap: 8 }}><span className="swatch" style={{ background: "#ffd23f" }} /><span className="muted">Generated</span></span>
                  <span className="mono">{split?.generated.turns} · {fmtUSD(split?.generated.cost || 0)}</span>
                </div>
                <div className="row between">
                  <span className="row" style={{ gap: 8 }}><span className="swatch" style={{ background: "#4ade80" }} /><span className="muted">Cached</span></span>
                  <span className="mono">{split?.cached.turns} · {fmtUSD(split?.cached.cost || 0)}</span>
                </div>
                <div className="divider" />
                <div className="row between">
                  <strong>Cache hit rate</strong>
                  <strong className="mono">{perf ? `${(perf.cache_hit_rate * 100).toFixed(0)}%` : "—"}</strong>
                </div>
              </div>
            </div>
          ) : (
            <div className="empty">No turns recorded yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}

const tooltipStyle = {
  contentStyle: {
    background: "#171b24",
    border: "1px solid rgba(255,255,255,0.16)",
    borderRadius: 10,
    fontSize: 12,
  },
  labelStyle: { color: "#eef1f6" },
  itemStyle: { color: "#aab1c0" },
} as const;

function shortBucket(v: string): string {
  if (v.includes("T")) return v.split("T")[1] || v;
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return v.slice(5);
  return v.length > 10 ? v.slice(0, 8) + "…" : v;
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card card-pad-sm">
      <div className="eyebrow">{label}</div>
      <div className="metric" style={{ marginTop: 8 }}>{value}</div>
      {hint && <div className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>{hint}</div>}
    </div>
  );
}
