"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Api, ApiError, ConversationSummary, Insights, QuestionStat } from "@/lib/api";
import { fmtDate, useToast } from "@/components/ui";
import { AddSourceModal } from "@/components/AddSourceModal";
import { TranscriptModal } from "@/components/TranscriptModal";
import { DealSignals } from "@/components/DealSignals";
import { EditOnly } from "@/components/Permission";

const RANGES = [7, 30, 90];

export default function InsightsPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [days, setDays] = useState(30);
  // Each result remembers its (site, range) so a range switch shows the
  // skeleton until matching data arrives — no synchronous setState in effects.
  const [result, setResult] = useState<{ key: string; data: Insights | null } | null>(null);
  const [convs, setConvs] = useState<ConversationSummary[] | null>(null);
  const [openConv, setOpenConv] = useState<string | null>(null);
  const [gap, setGap] = useState<QuestionStat | null>(null);
  const key = `${id}:${days}`;
  const data = result?.key === key ? result.data : null;

  const load = useCallback(() => {
    Api.insights(id, days)
      .then((d) => setResult({ key, data: d }))
      .catch(() => setResult({ key, data: null }));
    Api.conversations(id).then((c) => setConvs(c.items)).catch(() => setConvs([]));
  }, [id, days, key]);
  useEffect(() => { load(); }, [load]);

  const answered = async () => {
    setGap(null);
    try {
      await Api.runIngestion(id);
      toast("Answer added — ingesting it now");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Added, but ingestion didn't start", "err");
    }
  };

  return (
    <div className="fade-in">
      <div className="row between page-head wrap" style={{ gap: 12 }}>
        <div>
          <h2>Insights</h2>
          <p className="muted" style={{ fontSize: "0.88rem" }}>
            What visitors ask, what holds them back, who they compare you with, and every conversation.
          </p>
        </div>
        <div className="tabs" style={{ border: "none", margin: 0 }}>
          {RANGES.map((d) => (
            <button key={d} className={`tab ${days === d ? "active" : ""}`} onClick={() => setDays(d)}>
              {d} days
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        <Kpi label="Conversations" value={data ? String(data.conversations) : "…"} />
        <Kpi label="Engaged" value={data ? String(data.engaged) : "…"}
          hint={data && data.funnel[1] ? data.funnel[1].label : ""} />
        <Kpi label="Questions" value={data ? String(data.turns) : "…"} />
        <Kpi label="Answered from your content"
          value={data ? (data.grounded_rate === null ? "—" : `${Math.round(data.grounded_rate * 100)}%`) : "…"}
          hint="Grounded in your sources" />
      </div>

      <DealSignals id={id} days={days} onOpen={setOpenConv} />

      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <h3 style={{ marginBottom: 4 }}>Knowledge gaps</h3>
          <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 14 }}>
            Questions your content didn&apos;t cover. Answer one and the agent knows it next time.
          </p>
          {!data ? <div className="skeleton" style={{ height: 160 }} />
            : data.gaps.length === 0 ? <div className="empty">No gaps — every question was grounded.</div>
            : (
              <div className="stack-sm">
                {data.gaps.map((g) => (
                  <div key={g.question} className="row between" style={{ gap: 12 }}>
                    <span style={{ minWidth: 0 }}>
                      {g.question} <span className="faint">· {g.count}×</span>
                    </span>
                    <EditOnly><button className="btn btn-sm" onClick={() => setGap(g)}>Answer this</button></EditOnly>
                  </div>
                ))}
              </div>
            )}
        </div>

        <div className="card">
          <h3 style={{ marginBottom: 14 }}>Top questions</h3>
          {!data ? <div className="skeleton" style={{ height: 160 }} />
            : data.top_questions.length === 0 ? <div className="empty">No questions yet.</div>
            : (
              <div className="stack-sm">
                {data.top_questions.map((q) => (
                  <div key={q.question} className="row between" style={{ gap: 12 }}>
                    <span style={{ minWidth: 0 }}>{q.question}</span>
                    <span className="mono faint">{q.count}×</span>
                  </div>
                ))}
              </div>
            )}
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 14 }}>Conversations</h3>
        {convs === null ? <div className="skeleton" style={{ height: 160 }} />
          : convs.length === 0 ? <div className="empty">No conversations yet. Talk to the agent to see them here.</div>
          : (
            <table className="table">
              <thead>
                <tr><th>First question</th><th>Questions</th><th>Unanswered</th><th>Channel</th><th>Last active</th><th /></tr>
              </thead>
              <tbody>
                {convs.map((c) => (
                  <tr key={c.id}>
                    <td>{c.first_question || "—"}</td>
                    <td className="mono">{c.turns}</td>
                    <td className="mono">{c.ungrounded}</td>
                    <td>{c.channel}</td>
                    <td className="faint">{fmtDate(c.last_at)}</td>
                    <td><button className="btn btn-ghost btn-sm" onClick={() => setOpenConv(c.id)}>Transcript</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>

      {gap && (
        <AddSourceModal key={gap.question} id={id} open onClose={() => setGap(null)}
          title="Answer a visitor question" submitLabel="Add answer" initialName={gap.question}
          contentHint="Write the answer the agent should give, in your own words…"
          onAdded={answered} onError={(m) => toast(m, "err")} />
      )}
      {openConv && <TranscriptModal id={id} cid={openConv} onClose={() => setOpenConv(null)} />}
    </div>
  );
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
