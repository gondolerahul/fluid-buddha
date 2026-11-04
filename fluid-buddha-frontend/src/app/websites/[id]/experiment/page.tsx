"use client";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { useParams } from "next/navigation";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Api, ApiError, ExperimentPlan, ExperimentResults, ExperimentSettings, LiftArm } from "@/lib/api";
import { Spinner, fmtDate, useToast } from "@/components/ui";

// Series colours, validated as a pair on the card surface (#12151c): lightness
// band, chroma, CVD and normal-vision separation, contrast.
const AGENT = "#c98500";
const HOLDOUT = "#3987e5";
const SHARES = [5, 10, 20, 30, 50];
const LIFTS = [0.1, 0.2, 0.3, 0.5, 1];

const subscribeNoop = () => () => {};
const pct = (x: number | null | undefined, d = 1) => (x == null ? "—" : `${(x * 100).toFixed(d)}%`);
const pts = (x: number | null | undefined) =>
  x == null ? "—" : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)} pts`;

export default function ExperimentPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [cfg, setCfg] = useState<ExperimentSettings | null>(null);
  const [res, setRes] = useState<ExperimentResults | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    Api.getExperiment(id).then(setCfg).catch(() => {});
    Api.experimentResults(id).then(setRes).catch(() => setRes(null));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const save = async (next: ExperimentSettings) => {
    setBusy(true);
    try {
      const r = await Api.saveExperiment(id, {
        enabled: next.enabled, holdout_pct: next.holdout_pct,
        goal_path: next.goal_path?.trim() || null,
      });
      toast(!r.enabled ? "Experiment stopped" : r.started_new_run ? "Experiment started" : "Saved");
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not save", "err");
    } finally {
      setBusy(false);
    }
  };

  const restart = async () => {
    if (!window.confirm("Start a fresh run? Results so far stay with the old run and the new one starts from zero.")) return;
    try {
      await Api.restartExperiment(id);
      toast("New run started");
      load();
    } catch {
      toast("Could not restart", "err");
    }
  };

  return (
    <div className="fade-in stack">
      <div className="page-head">
        <h2>Holdout test</h2>
        <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 680 }}>
          Does the agent win you more customers? A holdout share of visitors never sees it; everyone
          else does. Both groups are measured on your site&apos;s own goal, so the difference is what the
          agent causes.
        </p>
      </div>

      {cfg ? <SettingsCard key={JSON.stringify(cfg)} cfg={cfg} busy={busy} onSave={save} onRestart={restart} /> :
        <div className="skeleton" style={{ height: 200 }} />}

      {res === undefined ? <div className="skeleton" style={{ height: 260 }} /> :
        res === null ? null : <Results res={res} />}

      {cfg && <Planner id={id} cfg={cfg} />}
    </div>
  );
}

function SettingsCard({ cfg, busy, onSave, onRestart }: {
  cfg: ExperimentSettings; busy: boolean;
  onSave: (c: ExperimentSettings) => void; onRestart: () => void;
}) {
  // Remounted (keyed) whenever the saved settings change, so this resets.
  const [draft, setDraft] = useState(cfg);
  const running = cfg.enabled;
  const shareChanged = running && draft.holdout_pct !== cfg.holdout_pct;

  return (
    <section className="card">
      <div className="row between wrap" style={{ gap: 12 }}>
        <div>
          <span className="eyebrow">Holdout test</span>
          <div style={{ marginTop: 6, fontSize: "0.92rem" }}>
            {running
              ? <><span className="badge ok">Running</span> since {fmtDate(cfg.started_at)}</>
              : cfg.status === "stopped"
                ? <><span className="badge">Stopped</span> {fmtDate(cfg.ended_at)}</>
                : <span className="muted">Not running</span>}
          </div>
        </div>
        <div className="row" style={{ gap: 8 }}>
          {running && <button className="btn btn-sm" onClick={onRestart} disabled={busy}>Restart</button>}
          <button className={`btn btn-sm ${running ? "btn-danger" : "btn-primary"}`} disabled={busy}
            onClick={() => onSave({ ...draft, enabled: !running })}>
            {busy ? <Spinner /> : running ? "Stop" : "Start experiment"}
          </button>
        </div>
      </div>

      <div className="grid grid-2" style={{ gap: 14, marginTop: 16 }}>
        <div className="field">
          <label className="label">Visitors held out (no agent)</label>
          <select className="select" value={draft.holdout_pct} aria-label="Visitors held out (no agent)"
            onChange={(e) => setDraft({ ...draft, holdout_pct: Number(e.target.value) })}>
            {SHARES.map((s) => <option key={s} value={s}>{s}%</option>)}
          </select>
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
            {shareChanged ? "Saving a new share starts a fresh run."
              : "A small share keeps most visitors with the agent; a larger one gives results sooner."}
          </p>
        </div>
        <div className="field">
          <label className="label">Goal page <span className="faint">(optional)</span></label>
          <input className="input" value={draft.goal_path ?? ""} placeholder="/thank-you" aria-label="Goal page"
            onChange={(e) => setDraft({ ...draft, goal_path: e.target.value })} />
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
            A visit to this page (or below it) counts as a conversion, in both groups.
          </p>
        </div>
      </div>
      {running && (draft.goal_path !== cfg.goal_path || shareChanged) && (
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 8 }}>
          <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => onSave({ ...draft, enabled: true })}>
            Save changes
          </button>
        </div>
      )}

      <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--line)" }}>
        <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 8 }}>
          Or count a goal from your own code, e.g. when a demo is booked. It works the same for
          visitors who don&apos;t see the agent:
        </p>
        <pre className="code">{`window.FluidBuddha.conversion("demo_booked");`}</pre>
        <p className="faint" style={{ fontSize: "0.78rem", marginTop: 8 }}>
          Leads the agent captures aren&apos;t counted: only visitors with the agent can produce them,
          so they would build the answer into the test.
        </p>
      </div>
    </section>
  );
}

function headline(res: ExperimentResults): { tone: string; text: string } {
  const l = res.lift;
  if (l.status === "collecting") {
    return {
      tone: "",
      text: `Collecting data: ${l.agent.visitors} visitors with the agent and ${l.holdout.visitors} held out so far. ` +
        "Results firm up once each group has at least 30 visitors and some conversions.",
    };
  }
  const ci = `(95% CI ${pts(l.seq_low)} to ${pts(l.seq_high)})`;
  const rel = l.relative != null ? `, ${l.relative >= 0 ? "+" : "−"}${Math.abs(l.relative * 100).toFixed(0)}% relative` : "";
  if (l.status === "significant" && (l.diff ?? 0) > 0)
    return { tone: "ok", text: `The agent lifts conversion by ${pts(l.diff)} ${ci}${rel}.` };
  if (l.status === "significant")
    return { tone: "err", text: `Visitors with the agent convert less: ${pts(l.diff)} ${ci}${rel}.` };
  if (l.status === "trending")
    return { tone: "", text: `${(l.diff ?? 0) > 0 ? "Promising" : "Leaning negative"}: ${pts(l.diff)}${rel}, but not ` +
      `conclusive yet ${ci}. Keep the experiment running — stopping now risks a false result.` };
  return { tone: "", text: `No clear difference yet: ${pts(l.diff)} ${ci}. Keep the experiment running.` };
}

function Results({ res }: { res: ExperimentResults }) {
  const mounted = useSyncExternalStore(subscribeNoop, () => true, () => false);
  const h = headline(res);
  const l = res.lift;
  const goals = groupGoals(res.goals);

  return (
    <>
      <section className="card">
        <span className="eyebrow">Result{res.experiment.status === "stopped" ? " (last run)" : ""}</span>
        <p style={{ fontSize: "1.05rem", marginTop: 8, lineHeight: 1.5,
          color: h.tone === "ok" ? "var(--ok)" : h.tone === "err" ? "var(--err)" : undefined }}>
          {h.tone === "ok" ? "✓ " : h.tone === "err" ? "! " : ""}{h.text}
        </p>
        {l.seq_p_value != null && l.status !== "collecting" && (
          <p className="faint" style={{ fontSize: "0.8rem", marginTop: 4 }}>
            {l.seq_p_value < 0.001 ? "p < 0.001" : l.seq_p_value > 0.5 ? "p > 0.5"
              : `p = ${l.seq_p_value.toFixed(3)}`} · {res.experiment.holdout_pct}% held out
          </p>
        )}
        {res.experiment.bots_ignored > 0 && (
          <p className="faint" style={{ fontSize: "0.8rem", marginTop: 2 }}>
            {res.experiment.bots_ignored} bot visit{res.experiment.bots_ignored === 1 ? "" : "s"} kept out of the test
          </p>
        )}
        {l.diff != null && l.seq_low != null && l.seq_high != null &&
          <DiffStrip low={l.seq_low} diff={l.diff} high={l.seq_high} />}
        {l.status !== "collecting" && (
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 8 }}>
            This interval stays valid however often you look, so checking daily is fine. It is wider than a
            one-look test: that is the price of being able to stop as soon as the answer is clear.
          </p>
        )}
      </section>

      <div className="grid grid-2">
        <ArmTile name="With the agent" color={AGENT} arm={l.agent} />
        <ArmTile name="Held out (no agent)" color={HOLDOUT} arm={l.holdout} />
      </div>

      <section className="card">
        <div className="row between wrap" style={{ marginBottom: 12, gap: 10 }}>
          <h3>Conversion rate over time</h3>
          <div className="legend">
            <span><span className="swatch" style={{ background: AGENT }} />With the agent</span>
            <span><span className="swatch" style={{ background: HOLDOUT }} />Held out</span>
          </div>
        </div>
        {!mounted ? <div className="skeleton" style={{ height: 240 }} /> :
          res.series.length === 0 ? <div className="empty">No visitors yet.</div> :
          res.series.length < 2 ? (
            <div className="empty">The trend appears after a second day of data.</div>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={res.series} margin={{ top: 6, right: 12, left: 4, bottom: 4 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis dataKey="day" tick={{ fill: "#aab1c0", fontSize: 11 }} stroke="rgba(255,255,255,0.12)"
                  tickFormatter={(d: string) => d.slice(5)} />
                <YAxis tick={{ fill: "#aab1c0", fontSize: 11 }} stroke="rgba(255,255,255,0.12)"
                  tickFormatter={(v: number) => pct(v, 0)} width={48} />
                <Tooltip contentStyle={{ background: "#171b24", border: "1px solid rgba(255,255,255,0.16)",
                  borderRadius: 10, fontSize: 12 }} labelStyle={{ color: "#eef1f6" }}
                  itemStyle={{ color: "#aab1c0" }}
                  formatter={(v: number, name: string) => [pct(v), name]} />
                <Line type="monotone" dataKey="agent_rate" name="With the agent" stroke={AGENT}
                  strokeWidth={2} dot={{ r: 4, strokeWidth: 0, fill: AGENT }} connectNulls />
                <Line type="monotone" dataKey="holdout_rate" name="Held out" stroke={HOLDOUT}
                  strokeWidth={2} dot={{ r: 4, strokeWidth: 0, fill: HOLDOUT }} connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        <p className="faint" style={{ fontSize: "0.78rem", marginTop: 6 }}>
          Cumulative since the run started, by the day visitors first arrived.
        </p>
      </section>

      {goals.length > 0 && (
        <section className="card">
          <h3 style={{ marginBottom: 12 }}>Goals reached</h3>
          <table className="table">
            <thead><tr><th>Goal</th><th>With the agent</th><th>Held out</th></tr></thead>
            <tbody>
              {goals.map((g) => (
                <tr key={g.name}>
                  <td className="mono">{g.name === "goal_page" ? `goal page (${res.experiment.goal_path ?? "—"})` : g.name}</td>
                  <td>{g.agent}</td><td>{g.holdout}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}

function ArmTile({ name, color, arm }: { name: string; color: string; arm: LiftArm }) {
  return (
    <div className="card card-pad-sm">
      <div className="eyebrow"><span className="swatch" style={{ background: color, width: 10, height: 10,
        borderRadius: 3, display: "inline-block", marginRight: 6 }} />{name}</div>
      <div className="metric" style={{ marginTop: 8 }}>{pct(arm.rate)}</div>
      <div className="muted" style={{ fontSize: "0.84rem", marginTop: 4 }}>
        {arm.converters} of {arm.visitors} visitors converted
      </div>
      <div className="faint" style={{ fontSize: "0.78rem", marginTop: 2 }}>
        95% CI {pct(arm.rate_low)} – {pct(arm.rate_high)}
      </div>
    </div>
  );
}

/** The difference (agent − holdout) with its 95% interval, against zero. */
function DiffStrip({ low, diff, high }: { low: number; diff: number; high: number }) {
  const span = Math.max(Math.abs(low), Math.abs(high), 0.01) * 1.15;
  const x = (v: number) => 50 + (v / span) * 50; // percent across the strip
  const label = `Difference ${pts(diff)}, 95% CI ${pts(low)} to ${pts(high)}`;
  return (
    <div style={{ marginTop: 16 }} role="img" aria-label={label} title={label}>
      <div style={{ position: "relative", height: 28 }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 13, height: 1, background: "var(--line)" }} />
        <div style={{ position: "absolute", left: "50%", top: 2, bottom: 2, width: 1, background: "var(--line-strong)" }} />
        <div style={{ position: "absolute", left: `${x(low)}%`, width: `${x(high) - x(low)}%`, top: 10, height: 8,
          borderRadius: 4, background: "var(--accent-soft)", border: "1px solid rgba(255,210,63,0.45)" }} />
        <div style={{ position: "absolute", left: `calc(${x(diff)}% - 5px)`, top: 9, width: 10, height: 10,
          borderRadius: "50%", background: "var(--accent)", boxShadow: "0 0 0 2px var(--bg-elev)" }} />
      </div>
      <div className="row between faint" style={{ fontSize: "0.74rem" }}>
        <span>{pts(-span)}</span><span>no difference</span><span>{pts(span)}</span>
      </div>
    </div>
  );
}

function groupGoals(rows: ExperimentResults["goals"]) {
  const by = new Map<string, { name: string; agent: number; holdout: number }>();
  for (const r of rows) {
    const g = by.get(r.name) ?? { name: r.name, agent: 0, holdout: 0 };
    g[r.arm] += r.events;
    by.set(r.name, g);
  }
  return [...by.values()];
}

/** How many visitors the test needs to show a given lift, and how long that takes. */
function Planner({ id, cfg }: { id: string; cfg: ExperimentSettings }) {
  const [mde, setMde] = useState(0.2);
  const [baselineText, setBaselineText] = useState("");
  const [plan, setPlan] = useState<ExperimentPlan | null>(null);

  const typed = Number(baselineText);
  const baseline = baselineText.trim() && typed > 0 && typed < 100 ? typed / 100 : undefined;
  useEffect(() => {
    let live = true;
    Api.experimentPlan(id, { mde, baseline, holdout_pct: cfg.holdout_pct })
      .then((p) => { if (live) setPlan(p); }).catch(() => {});
    return () => { live = false; };
  }, [id, mde, baseline, cfg.holdout_pct]);

  const n = plan?.needed;
  const progress = plan && n ? Math.min(1, plan.visitors_so_far / n.total) : 0;
  const days = plan?.days_left;
  const source = plan?.baseline_source === "observed" ? "the held-out group's rate so far"
    : plan?.baseline_source === "given" ? "your figure" : "a typical 3% until your holdout has data";
  let pace = "";
  if (plan?.reached) pace = " This run has reached that size.";
  else if (days != null && plan?.visitors_per_day) {
    const d = Math.ceil(days);
    pace = ` At ${Math.round(plan.visitors_per_day).toLocaleString()} visitors a day that is roughly ` +
      (days < 1 ? "under a day." : `${d} more day${d === 1 ? "" : "s"}.`);
  }

  return (
    <section className="card">
      <span className="eyebrow">Planner</span>
      <h3 style={{ marginTop: 6 }}>How long will it take?</h3>
      <div className="grid grid-2" style={{ gap: 14, marginTop: 12 }}>
        <div className="field">
          <label className="label">Lift to detect</label>
          <select className="select" value={mde} aria-label="Lift to detect"
            onChange={(e) => setMde(Number(e.target.value))}>
            {LIFTS.map((m) => <option key={m} value={m}>+{Math.round(m * 100)}% more conversions</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label">Goal rate without the agent <span className="faint">(optional, %)</span></label>
          <input className="input" inputMode="decimal" value={baselineText} aria-label="Goal rate without the agent"
            placeholder={plan ? (plan.baseline * 100).toFixed(1) : "3"}
            onChange={(e) => setBaselineText(e.target.value)} />
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
            {plan ? `Using ${(plan.baseline * 100).toFixed(1)}% — ${source}.` : " "}
          </p>
        </div>
      </div>
      {!plan ? <div className="skeleton" style={{ height: 60, marginTop: 8 }} /> : !n ? (
        <p className="muted" style={{ marginTop: 8 }}>That lift would push the rate past 100%; pick a smaller one.</p>
      ) : (
        <div style={{ marginTop: 8 }}>
          <p style={{ lineHeight: 1.5 }}>
            About <strong>{n.total.toLocaleString()}</strong> visitors ({n.holdout.toLocaleString()} held out,{" "}
            {n.agent.toLocaleString()} with the agent) to show a +{Math.round(plan.mde * 100)}% lift with 80% confidence
            {cfg.enabled ? "." : ` at a ${plan.holdout_pct}% holdout.`}{pace}
          </p>
          {plan.visitors_so_far > 0 && (
            <div style={{ marginTop: 10 }} role="img"
              aria-label={`${plan.visitors_so_far} of ${n.total} visitors so far`}>
              <div style={{ height: 8, borderRadius: 4, background: "var(--line)" }}>
                <div style={{ width: `${progress * 100}%`, height: 8, borderRadius: 4, background: "var(--accent)" }} />
              </div>
              <div className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
                {plan.visitors_so_far.toLocaleString()} of {n.total.toLocaleString()} visitors so far
              </div>
            </div>
          )}
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 8 }}>
            Smaller lifts, rarer goals and smaller holdouts all need more visitors. A larger holdout gets an
            answer sooner, at the cost of more visitors without the agent meanwhile.
          </p>
        </div>
      )}
    </section>
  );
}
