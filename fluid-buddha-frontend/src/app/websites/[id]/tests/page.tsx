"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Api, ApiError, Persona, TestSubject, TriggerRule, VariantOverrides, VariantTest, VariantTestResults,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Modal, Spinner, fmtDate, useToast } from "@/components/ui";

const SUBJECTS: { key: TestSubject; label: string; hint: string }[] = [
  { key: "greeting", label: "Greeting", hint: "The first thing the agent says when it opens." },
  { key: "trigger", label: "Proactive triggers", hint: "Which triggers are on (or none at all)." },
  { key: "tour", label: "Guided tour", hint: "Offer the tour when the agent opens, or not." },
  { key: "persona", label: "Starting persona", hint: "Who the agent assumes it is talking to at first." },
  { key: "design", label: "Design level", hint: "Companion panel, immersive presence or ambient atmosphere." },
  { key: "regions", label: "Generated regions", hint: "Your page's own content against regions FluidBuddha generates for each visitor's goal (set them up in the Regions tab)." },
  { key: "freeform", label: "Free-form pages", hint: "Composed pages against pages made for each visitor on your free-form routes (set them up in the Pages tab)." },
];
const DESIGNS = [
  { key: "level1", label: "Level 1 · Companion" },
  { key: "level2", label: "Level 2 · Presence" },
  { key: "level3", label: "Level 3 · Atmosphere" },
] as const;
const KEYS = ["a", "b", "c", "d"];
const HOLDOUTS = [0, 5, 10, 20];

const pct = (x: number | null | undefined, d = 1) => (x == null ? "—" : `${(x * 100).toFixed(d)}%`);
const pts = (x: number | null | undefined) =>
  x == null ? "—" : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)}`;
const subjectLabel = (s: TestSubject) => SUBJECTS.find((x) => x.key === s)?.label ?? s;

function describe(o: VariantOverrides, rules: Record<string, string>, personas: Record<string, string>): string {
  if (o.greeting !== undefined) return `“${o.greeting}”`;
  if (o.triggers !== undefined) return o.triggers.length ? o.triggers.map((t) => rules[t] ?? "a deleted trigger").join(", ") : "No triggers";
  if (o.tour !== undefined) return o.tour ? "Tour on" : "Tour off";
  if (o.persona !== undefined) return o.persona ? personas[o.persona] ?? o.persona : "Worked out from the conversation";
  if (o.design !== undefined) return DESIGNS.find((d) => d.key === o.design)?.label ?? o.design;
  if (o.regions !== undefined) return o.regions ? "Generated regions" : "The page's own content";
  if (o.freeform !== undefined) return o.freeform ? "Free-form, per visitor" : "Composed pages";
  return "—";
}

export default function TestsPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const { can } = useAuth();
  const editor = can("editor");
  const [tests, setTests] = useState<VariantTest[] | null>(null);
  const [holdoutRunning, setHoldoutRunning] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [res, setRes] = useState<VariantTestResults | null>(null);
  const [creating, setCreating] = useState(false);
  const [rules, setRules] = useState<TriggerRule[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);

  const load = useCallback(() => {
    Api.tests(id).then((r) => { setTests(r.tests); setHoldoutRunning(r.holdout_running); })
      .catch(() => setTests([]));
    Api.triggers(id).then((r) => setRules(r.rules)).catch(() => {});
    Api.getProfile(id).then((p) => setPersonas(p.personas)).catch(() => {});
  }, [id]);
  useEffect(() => { load(); }, [load]);

  // The test on show: the one picked, else the newest.
  const shown = picked ?? tests?.[0]?.id ?? null;
  useEffect(() => {
    if (!shown) return;
    let live = true;
    Api.testResults(id, shown).then((r) => { if (live) setRes(r); }).catch(() => { if (live) setRes(null); });
    return () => { live = false; };
  }, [id, shown, tests]);

  const ruleNames = Object.fromEntries(rules.map((r) => [r.id, r.name]));
  const personaNames = Object.fromEntries(personas.map((p) => [p.slug, p.label || p.slug]));

  const stop = async (t: VariantTest) => {
    if (!window.confirm(`Stop “${t.name}”? Its results stay readable; visitors go back to the site's defaults.`)) return;
    try { await Api.stopTest(id, t.id); toast("Test stopped"); load(); }
    catch { toast("Could not stop the test", "err"); }
  };
  const promote = async (t: VariantTest, key: string, label: string) => {
    const where = t.subject === "design" ? "the site's design level" : t.subject === "trigger"
      ? "which triggers are on" : t.subject === "regions" ? "whether generated regions are on"
      : t.subject === "freeform" ? "whether free-form pages are on" : "the agent profile";
    if (!window.confirm(`Make “${label}” the default for everyone? This updates ${where} and ends the test.`)) return;
    try {
      await Api.promoteVariant(id, t.id, key);
      toast(`“${label}” is now the default`);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not promote", "err");
    }
  };

  return (
    <div className="fade-in stack">
      <div className="row between wrap page-head" style={{ gap: 12 }}>
        <div>
          <h2>A/B tests</h2>
          <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 700 }}>
            Try 2–4 versions of one thing — the greeting, the triggers, the tour, the starting persona, the
            design or generated regions — and see which wins more of your site&apos;s goal. Each visitor always sees the same version.
            The verdict stays trustworthy however often you check it.
          </p>
        </div>
        {editor && <button className="btn btn-primary btn-sm" onClick={() => setCreating(true)}>New test</button>}
      </div>

      {res && <ResultsCard res={res} editor={editor} ruleNames={ruleNames} personaNames={personaNames}
        onStop={stop} onPromote={promote} />}

      <section className="card">
        <h3 style={{ marginBottom: 10 }}>All tests</h3>
        {!tests ? <div className="skeleton" style={{ height: 120 }} /> : tests.length === 0 ? (
          <div className="empty">No tests yet. Start one to find the greeting or nudge that works best.</div>
        ) : (
          <table className="table">
            <thead><tr><th>Test</th><th>Varies</th><th>Started</th><th>Visitors</th><th>Status</th></tr></thead>
            <tbody>
              {tests.map((t) => (
                <tr key={t.id} onClick={() => setPicked(t.id)}
                  style={{ cursor: "pointer", background: t.id === shown ? "var(--surface-2, rgba(255,255,255,0.04))" : undefined }}>
                  <td>{t.name}</td>
                  <td>{subjectLabel(t.subject)} · {t.variants.length} versions</td>
                  <td>{fmtDate(t.started_at)}</td>
                  <td className="mono">{t.visitors ?? 0}</td>
                  <td>{t.status === "running" ? "Running" : t.promoted_at
                    ? `Done · “${t.variants.find((v) => v.key === t.winner)?.label}” made default` : "Stopped"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {creating && (
        <Modal open onClose={() => setCreating(false)} title="New A/B test" width={640}>
          <TestForm id={id} rules={rules.filter((r) => r.enabled)} personas={personas} holdoutRunning={holdoutRunning}
            onCancel={() => setCreating(false)}
            onStarted={(t) => { setCreating(false); setPicked(t.id); toast("Test started"); load(); }} />
        </Modal>
      )}
    </div>
  );
}

function ResultsCard({ res, editor, ruleNames, personaNames, onStop, onPromote }: {
  res: VariantTestResults; editor: boolean; ruleNames: Record<string, string>;
  personaNames: Record<string, string>;
  onStop: (t: VariantTest) => void; onPromote: (t: VariantTest, key: string, label: string) => void;
}) {
  const t = res.experiment;
  const { verdict, plan } = res;
  const winner = res.variants.find((v) => v.key === verdict.winner);
  const banner = verdict.status === "winner" && winner
    ? { cls: "ok", text: winner.key === "a"
        ? `The control (“${winner.label}”) beats every other version.`
        : `“${winner.label}” wins: it converts better than the control, and that holds however often you've looked.` }
    : verdict.status === "no_difference"
      ? { cls: "", text: "No difference: the planned number of visitors is in and no version stands out. Keep whichever you prefer." }
      : { cls: "", text: "Keep running: not enough evidence yet to call a winner." };
  const needed = plan.needed?.total;

  return (
    <section className="card stack">
      <div className="row between wrap" style={{ gap: 10 }}>
        <div>
          <span className="eyebrow">{subjectLabel(t.subject)} test · {t.status === "running" ? "running" : "ended"}</span>
          <h3 style={{ marginTop: 4 }}>{t.name}</h3>
          <p className="faint" style={{ fontSize: "0.8rem" }}>
            Goal: {t.goal_path ? <span className="mono">{t.goal_path}</span> : "FluidBuddha.conversion() calls"}
            {t.holdout_pct ? ` · ${t.holdout_pct}% holdout` : ""} · started {fmtDate(t.started_at)}
            {t.bots_ignored ? ` · ${t.bots_ignored} bot visits ignored` : ""}
          </p>
        </div>
        {editor && t.status === "running" && <button className="btn btn-sm" onClick={() => onStop(t)}>Stop test</button>}
      </div>

      <div className={`banner ${banner.cls}`} role="status" style={{ padding: "10px 14px", borderRadius: 10,
        background: banner.cls === "ok" ? "rgba(60,170,110,0.12)" : "rgba(255,255,255,0.04)", fontSize: "0.9rem" }}>
        {banner.text}
      </div>

      <table className="table">
        <thead>
          <tr><th>Version</th><th>Visitors</th><th>Converted</th><th>vs control (pts)</th><th>Verdict</th><th /></tr>
        </thead>
        <tbody>
          {res.variants.map((v) => {
            const c = v.vs_control;
            const call = !c ? "Control" : c.status === "significant" ? ((c.diff ?? 0) > 0 ? "Better" : "Worse")
              : c.status === "trending" ? "Promising — keep going" : c.status === "collecting" ? "Collecting" : "Not separated yet";
            const isWinner = v.key === verdict.winner;
            return (
              <tr key={v.key}>
                <td>
                  <div>{v.label}{isWinner && <span style={{ color: "var(--ok, #3caa6e)" }}> · winner</span>}
                    {t.winner === v.key && t.promoted_at && <span className="faint"> · made default</span>}</div>
                  <div className="faint" style={{ fontSize: "0.8rem", maxWidth: 340 }}>{describe(v.overrides, ruleNames, personaNames)}</div>
                </td>
                <td className="mono">{v.visitors}</td>
                <td className="mono">{pct(v.rate)}</td>
                <td className="mono" title="Always-valid interval: safe to read at any time">
                  {c ? `${pts(c.diff)} (${pts(c.seq_low)} to ${pts(c.seq_high)})` : "—"}
                </td>
                <td>{call}</td>
                <td style={{ textAlign: "right" }}>
                  {editor && !t.promoted_at && (
                    <button className={`btn btn-sm ${isWinner ? "btn-primary" : "btn-ghost"}`}
                      onClick={() => onPromote(t, v.key, v.label)}>Make default</button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {res.holdout && (
        <p className="faint" style={{ fontSize: "0.82rem" }}>
          Agent (all versions) vs holdout: {pct(res.holdout.agent.rate)} vs {pct(res.holdout.holdout.rate)}
          {" "}({pts(res.holdout.diff)} pts, {res.holdout.status === "significant" ? "a real difference" : "not separated yet"}).
        </p>
      )}
      <p className="faint" style={{ fontSize: "0.78rem" }}>
        {verdict.status === "winner"
          ? `Decided after ${plan.visitors_so_far.toLocaleString()} visitors${needed ? ` (about ${needed.toLocaleString()} were planned to spot a ${Math.round(plan.mde * 100)}% lift; a bigger difference shows sooner)` : ""}`
          : needed ? `${plan.visitors_so_far.toLocaleString()} of about ${needed.toLocaleString()} visitors needed to spot a ${Math.round(plan.mde * 100)}% lift`
            : `${plan.visitors_so_far.toLocaleString()} visitors so far`}
        {t.status === "running" && verdict.status === "keep_running" && plan.days_left != null && !plan.reached
          ? ` · about ${Math.ceil(plan.days_left)} more days at the current traffic` : ""}.
        {" "}Each version is compared with the control at a {pct(verdict.alpha, 1)} error budget, so the chance of any
        false winner stays under 5%.
      </p>
    </section>
  );
}

type Draft = { label: string; overrides: VariantOverrides };

function blank(subject: TestSubject, i: number): Draft {
  const label = i === 0 ? "Control" : `Version ${KEYS[i].toUpperCase()}`;
  switch (subject) {
    case "greeting": return { label, overrides: { greeting: "" } };
    case "trigger": return { label, overrides: { triggers: [] } };
    case "tour": return { label, overrides: { tour: i === 0 } };
    case "persona": return { label, overrides: { persona: "" } };
    case "design": return { label, overrides: { design: DESIGNS[Math.min(i, 2)].key } };
    case "regions": return { label: i === 0 ? "Page's own content" : "Generated", overrides: { regions: i !== 0 } };
    case "freeform": return { label: i === 0 ? "Composed" : "Free-form", overrides: { freeform: i !== 0 } };
  }
}

function TestForm({ id, rules, personas, holdoutRunning, onCancel, onStarted }: {
  id: string; rules: TriggerRule[]; personas: Persona[]; holdoutRunning: boolean;
  onCancel: () => void; onStarted: (t: VariantTest) => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [subject, setSubject] = useState<TestSubject>("greeting");
  const [variants, setVariants] = useState<Draft[]>([blank("greeting", 0), blank("greeting", 1)]);
  const [holdout, setHoldout] = useState(0);
  const [goal, setGoal] = useState("");
  const [busy, setBusy] = useState(false);
  const [need, setNeed] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    Api.planTest(id, { variants: variants.length, baseline: 0.03, mde: 0.2, holdout_pct: holdout })
      .then((r) => { if (live) setNeed(r.needed?.total ?? null); }).catch(() => {});
    return () => { live = false; };
  }, [id, variants.length, holdout]);

  const pickSubject = (s: TestSubject) => {
    setSubject(s);
    setVariants(variants.map((v, i) => ({ ...blank(s, i), label: v.label })));
  };
  const setOverride = (i: number, o: VariantOverrides) =>
    setVariants((vs) => vs.map((v, j) => (j === i ? { ...v, overrides: o } : v)));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const t = await Api.startTest(id, { name: name.trim(), subject, holdout_pct: holdout,
        goal_path: goal.trim() || null, variants });
      onStarted(t);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not start the test", "err");
    } finally {
      setBusy(false);
    }
  };

  const hint = SUBJECTS.find((s) => s.key === subject)?.hint;
  return (
    <form className="stack" onSubmit={submit}>
      <div className="grid grid-2" style={{ gap: 12 }}>
        <div className="field">
          <label className="label" htmlFor="t-name">Name</label>
          <input id="t-name" className="input" required maxLength={80} value={name}
            placeholder="Opening line, spring 2027" onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="t-subject">What to test</label>
          <select id="t-subject" className="select" value={subject} onChange={(e) => pickSubject(e.target.value as TestSubject)}>
            {SUBJECTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </div>
      </div>
      <p className="faint" style={{ fontSize: "0.8rem", marginTop: -6 }}>{hint} The first version is the control: what visitors get today.</p>
      {subject === "trigger" && rules.length === 0 && (
        <p className="faint" style={{ fontSize: "0.82rem" }}>No active triggers yet: add some on the Triggers tab, or test “some triggers” against “none”.</p>
      )}
      {subject === "persona" && personas.length === 0 && (
        <p className="faint" style={{ fontSize: "0.82rem" }}>No personas yet: add them under Settings → Agent profile first.</p>
      )}

      {variants.map((v, i) => (
        <div key={i} className="card" style={{ padding: 12 }}>
          <div className="row between" style={{ gap: 8, marginBottom: 8 }}>
            <input className="input" aria-label={`Version ${i + 1} name`} value={v.label} maxLength={60} style={{ maxWidth: 260 }}
              onChange={(e) => setVariants((vs) => vs.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} />
            {i >= 2 && <button type="button" className="btn btn-sm btn-ghost"
              onClick={() => setVariants((vs) => vs.filter((_, j) => j !== i))}>Remove</button>}
          </div>
          {subject === "greeting" && (
            <textarea className="textarea" rows={2} required maxLength={300} aria-label={`Version ${i + 1} greeting`}
              value={v.overrides.greeting ?? ""} placeholder={i === 0 ? "Your current greeting" : "Hi! Want to see which plan fits your team?"}
              onChange={(e) => setOverride(i, { greeting: e.target.value })} />
          )}
          {subject === "trigger" && (
            <div className="row wrap" style={{ gap: 12 }}>
              {rules.map((r) => (
                <label key={r.id} className="row" style={{ gap: 6, fontSize: "0.86rem" }}>
                  <input type="checkbox" checked={v.overrides.triggers?.includes(r.id) ?? false}
                    onChange={(e) => {
                      const cur = v.overrides.triggers ?? [];
                      setOverride(i, { triggers: e.target.checked ? [...cur, r.id] : cur.filter((x) => x !== r.id) });
                    }} /> {r.name}
                </label>
              ))}
              {!v.overrides.triggers?.length && <span className="faint" style={{ fontSize: "0.84rem" }}>No triggers</span>}
            </div>
          )}
          {subject === "tour" && (
            <select className="select" aria-label={`Version ${i + 1} tour`} value={v.overrides.tour ? "on" : "off"}
              onChange={(e) => setOverride(i, { tour: e.target.value === "on" })}>
              <option value="on">Offer the guided tour</option>
              <option value="off">No tour</option>
            </select>
          )}
          {subject === "regions" && (
            <select className="select" aria-label={`Version ${i + 1} regions`} value={v.overrides.regions ? "on" : "off"}
              onChange={(e) => setOverride(i, { regions: e.target.value === "on" })}>
              <option value="off">The page&apos;s own content</option>
              <option value="on">Generated regions</option>
            </select>
          )}
          {subject === "freeform" && (
            <select className="select" aria-label={`Version ${i + 1} free-form`} value={v.overrides.freeform ? "on" : "off"}
              onChange={(e) => setOverride(i, { freeform: e.target.value === "on" })}>
              <option value="off">Composed pages</option>
              <option value="on">Free-form, per visitor</option>
            </select>
          )}
          {subject === "persona" && (
            <select className="select" aria-label={`Version ${i + 1} persona`} value={v.overrides.persona ?? ""}
              onChange={(e) => setOverride(i, { persona: e.target.value })}>
              <option value="">Work it out from the conversation</option>
              {personas.map((p) => <option key={p.slug} value={p.slug}>{p.label || p.slug}</option>)}
            </select>
          )}
          {subject === "design" && (
            <select className="select" aria-label={`Version ${i + 1} design`} value={v.overrides.design}
              onChange={(e) => setOverride(i, { design: e.target.value as VariantOverrides["design"] })}>
              {DESIGNS.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
            </select>
          )}
        </div>
      ))}
      {variants.length < 4 && (
        <button type="button" className="btn btn-sm" style={{ alignSelf: "flex-start" }}
          onClick={() => setVariants((vs) => [...vs, blank(subject, vs.length)])}>Add a version</button>
      )}

      <div className="grid grid-2" style={{ gap: 12 }}>
        <div className="field">
          <label className="label" htmlFor="t-goal">Goal page <span className="faint">(optional)</span></label>
          <input id="t-goal" className="input mono" value={goal} placeholder="/thank-you" onChange={(e) => setGoal(e.target.value)} />
          <p className="faint" style={{ fontSize: "0.76rem", marginTop: 4 }}>Or call FluidBuddha.conversion() from your site.</p>
        </div>
        <div className="field">
          <label className="label" htmlFor="t-holdout">Also keep a holdout</label>
          <select id="t-holdout" className="select" value={holdout} onChange={(e) => setHoldout(Number(e.target.value))}>
            {HOLDOUTS.map((h) => <option key={h} value={h}>{h ? `${h}% never see the agent` : "No holdout"}</option>)}
          </select>
        </div>
      </div>
      <p className="faint" style={{ fontSize: "0.8rem" }}>
        {need ? `To spot a 20% lift on a 3% goal rate, this needs about ${need.toLocaleString()} visitors in total.` : ""}
        {holdoutRunning ? " Starting this test ends the holdout experiment that is running now." : ""}
        {" "}One test runs at a time.
      </p>
      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Start test"}</button>
      </div>
    </form>
  );
}
