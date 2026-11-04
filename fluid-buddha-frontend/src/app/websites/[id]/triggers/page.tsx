"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Api, ApiError, TriggerKind, TriggerRule, TriggerRuleIn } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Modal, Spinner, useToast } from "@/components/ui";

const KIND_LABEL: Record<TriggerKind, string> = {
  time_on_page: "Time on page",
  scroll_depth: "Scrolled down",
  exit_intent: "About to leave",
  return_visit: "Came back",
};

/** One-click starting points for the most common moments. */
const PRESETS: { label: string; rule: TriggerRuleIn }[] = [
  { label: "Lingering on pricing", rule: { name: "Pricing page dwell", enabled: true, kind: "time_on_page",
    seconds: 25, pages: ["/pricing*"], message: "Comparing plans? I can work out which one fits your team.",
    action: "nudge", max_per_day: 1, priority: 80 } },
  { label: "About to leave", rule: { name: "Exit intent", enabled: true, kind: "exit_intent", pages: [],
    message: "Before you go — any question I can answer in a few seconds?", action: "nudge",
    max_per_day: 1, priority: 60 } },
  { label: "Returning visitor", rule: { name: "Return visit", enabled: true, kind: "return_visit",
    visits: 2, within_days: 30, pages: [], message: "Welcome back! Want to pick up where you left off?",
    action: "nudge", max_per_day: 1, priority: 50 } },
  { label: "Deep reader", rule: { name: "Read most of the page", enabled: true, kind: "scroll_depth",
    percent: 70, pages: [], message: "Got questions about what you've read? Ask me anything.",
    action: "nudge", max_per_day: 1, priority: 40 } },
];

const BLANK: TriggerRuleIn = { name: "", enabled: true, kind: "time_on_page", seconds: 20, pages: [],
  message: "", action: "nudge", max_per_day: 1, priority: 50 };

function when(r: TriggerRuleIn): string {
  const where = r.pages.length ? ` on ${r.pages.join(", ")}` : "";
  switch (r.kind) {
    case "time_on_page": return `After ${r.seconds ?? 20} s${where}`;
    case "scroll_depth": return `Scrolled ${r.percent ?? 60}% of the page${where}`;
    case "exit_intent": return `About to leave${where}`;
    case "return_visit": return `Visit ${r.visits ?? 2}+ within ${r.within_days ?? 30} days${where}`;
  }
}

const pct = (x: number | null | undefined) => (x == null ? "—" : `${Math.round(x * 100)}%`);

export default function TriggersPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const { can } = useAuth();
  const [rules, setRules] = useState<TriggerRule[] | null>(null);
  const [editing, setEditing] = useState<{ id: string | null; rule: TriggerRuleIn } | null>(null);

  const load = useCallback(() => Api.triggers(id).then((r) => setRules(r.rules)).catch(() => setRules([])), [id]);
  useEffect(() => { load(); }, [load]);
  const editor = can("editor");

  const save = async (ruleId: string | null, rule: TriggerRuleIn) => {
    try {
      if (ruleId) await Api.updateTrigger(id, ruleId, rule);
      else await Api.createTrigger(id, rule);
      toast(ruleId ? "Trigger saved" : "Trigger added");
      setEditing(null);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not save", "err");
    }
  };

  const toggle = (r: TriggerRule) => save(r.id, { ...strip(r), enabled: !r.enabled });

  return (
    <div className="fade-in stack">
      <div className="row between wrap page-head" style={{ gap: 12 }}>
        <div>
          <h2>Triggers</h2>
          <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 680 }}>
            Let the agent speak up first at the right moment — a short message by the launcher. At most one
            per page view, never while the visitor is already talking, and a dismiss silences the rest of the visit.
          </p>
        </div>
        {editor && <button className="btn btn-primary btn-sm" onClick={() => setEditing({ id: null, rule: BLANK })}>Add trigger</button>}
      </div>

      {editor && rules && rules.length === 0 && (
        <section className="card">
          <h3 style={{ marginBottom: 10 }}>Start from a common moment</h3>
          <div className="row wrap" style={{ gap: 8 }}>
            {PRESETS.map((p) => (
              <button key={p.label} className="btn btn-sm" onClick={() => setEditing({ id: null, rule: p.rule })}>{p.label}</button>
            ))}
          </div>
        </section>
      )}

      <section className="card">
        {!rules ? <div className="skeleton" style={{ height: 160 }} /> : rules.length === 0 ? (
          <div className="empty">No triggers yet.</div>
        ) : (
          <table className="table">
            <thead><tr><th>Trigger</th><th>When</th><th>Shown</th><th>Clicked</th><th>Then asked</th><th /></tr></thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} style={{ opacity: r.enabled ? 1 : 0.55 }}>
                  <td>
                    <div>{r.name}{!r.enabled && <span className="faint"> (paused)</span>}</div>
                    <div className="faint" style={{ fontSize: "0.8rem", maxWidth: 320 }}>“{r.message}”</div>
                  </td>
                  <td style={{ fontSize: "0.86rem" }}>{when(r)}{r.action === "open" ? " · opens the agent" : ""}</td>
                  <td className="mono">{r.stats?.shown ?? 0}</td>
                  <td className="mono">{pct(r.stats?.click_rate)}</td>
                  <td className="mono">{pct(r.stats?.engage_rate)}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {editor && <>
                      <button className="btn btn-sm btn-ghost" onClick={() => toggle(r)}>{r.enabled ? "Pause" : "Resume"}</button>
                      <button className="btn btn-sm btn-ghost" onClick={() => setEditing({ id: r.id, rule: strip(r) })}>Edit</button>
                      <button className="btn btn-sm btn-ghost" onClick={async () => {
                        if (!window.confirm(`Delete “${r.name}”?`)) return;
                        try { await Api.deleteTrigger(id, r.id); toast("Trigger deleted"); load(); }
                        catch { toast("Could not delete", "err"); }
                      }}>Delete</button>
                    </>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="faint" style={{ fontSize: "0.78rem", marginTop: 10 }}>
          Last 30 days, counted per visitor. “Then asked” is the share of visitors shown the trigger who clicked it and
          went on to ask the agent something.
        </p>
      </section>

      {editing && (
        <Modal open onClose={() => setEditing(null)} title={editing.id ? "Edit trigger" : "Add trigger"} width={560}>
          <TriggerForm key={editing.id ?? "new"} initial={editing.rule} onCancel={() => setEditing(null)}
            onSave={(rule) => save(editing.id, rule)} />
        </Modal>
      )}
    </div>
  );
}

function strip(r: TriggerRule): TriggerRuleIn {
  const { id: _id, updated_at: _u, stats: _s, ...rule } = r;
  void _id; void _u; void _s;
  return rule;
}

function TriggerForm({ initial, onSave, onCancel }: {
  initial: TriggerRuleIn; onSave: (r: TriggerRuleIn) => Promise<void>; onCancel: () => void;
}) {
  const [r, setR] = useState<TriggerRuleIn>(initial);
  const [pages, setPages] = useState(initial.pages.join(", "));
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<TriggerRuleIn>) => setR((x) => ({ ...x, ...patch }));
  const num = (v: string) => (v === "" ? null : Number(v));

  return (
    <form className="stack" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      await onSave({ ...r, pages: pages.split(",").map((p) => p.trim()).filter(Boolean) });
      setBusy(false);
    }}>
      <div className="field">
        <label className="label">Name</label>
        <input className="input" required maxLength={80} value={r.name} onChange={(e) => set({ name: e.target.value })} />
      </div>
      <div className="grid grid-2" style={{ gap: 12 }}>
        <div className="field">
          <label className="label">When</label>
          <select className="select" value={r.kind} aria-label="When"
            onChange={(e) => set({ kind: e.target.value as TriggerKind })}>
            {(Object.keys(KIND_LABEL) as TriggerKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
          </select>
        </div>
        {r.kind === "time_on_page" && <div className="field">
          <label className="label">After (seconds)</label>
          <input className="input" type="number" min={3} max={600} value={r.seconds ?? ""}
            onChange={(e) => set({ seconds: num(e.target.value) })} />
        </div>}
        {r.kind === "scroll_depth" && <div className="field">
          <label className="label">Scrolled (% of the page)</label>
          <input className="input" type="number" min={10} max={100} value={r.percent ?? ""}
            onChange={(e) => set({ percent: num(e.target.value) })} />
        </div>}
        {r.kind === "return_visit" && <div className="field">
          <label className="label">Visit number, within days</label>
          <div className="row" style={{ gap: 6 }}>
            <input className="input" type="number" min={2} max={50} value={r.visits ?? ""} aria-label="Visit number"
              onChange={(e) => set({ visits: num(e.target.value) })} />
            <input className="input" type="number" min={1} max={90} value={r.within_days ?? ""} aria-label="Within days"
              onChange={(e) => set({ within_days: num(e.target.value) })} />
          </div>
        </div>}
        {r.kind === "exit_intent" && <p className="faint" style={{ fontSize: "0.8rem", alignSelf: "end" }}>
          When the pointer heads for the tabs or address bar (desktop), after 5 seconds on the page.</p>}
      </div>
      <div className="field">
        <label className="label">On pages <span className="faint">(optional, comma-separated)</span></label>
        <input className="input mono" value={pages} placeholder="/pricing*, /plans" onChange={(e) => setPages(e.target.value)} />
        <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>Empty means every page. * matches anything, e.g. /blog/*.</p>
      </div>
      <div className="field">
        <label className="label">Message</label>
        <textarea className="input" required maxLength={280} rows={2} value={r.message}
          onChange={(e) => set({ message: e.target.value })} />
      </div>
      <div className="grid grid-2" style={{ gap: 12 }}>
        <div className="field">
          <label className="label">Show as</label>
          <select className="select" value={r.action} aria-label="Show as"
            onChange={(e) => set({ action: e.target.value as "nudge" | "open" })}>
            <option value="nudge">A bubble by the launcher</option>
            <option value="open">Open the agent</option>
          </select>
        </div>
        <div className="field">
          <label className="label">At most, per visitor per day</label>
          <input className="input" type="number" min={1} max={10} value={r.max_per_day}
            onChange={(e) => set({ max_per_day: Number(e.target.value) || 1 })} />
        </div>
      </div>
      <label className="row" style={{ gap: 8, fontSize: "0.88rem" }}>
        <input type="checkbox" checked={r.enabled} onChange={(e) => set({ enabled: e.target.checked })} /> Active
      </label>
      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save"}</button>
      </div>
    </form>
  );
}
