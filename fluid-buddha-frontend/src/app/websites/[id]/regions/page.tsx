"use client";
/**
 * Adaptive regions (Phase 1, G1): the slots on your own pages that FluidBuddha
 * fills for each visitor's goal, the goals it plans for (intent families), and
 * the plans it has made — previewed, pinned or blocked here.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Api, ApiError, IntentFamily, IntentRules, PlanRow, PlanStatus, PlanView, RegionSettings, RegionSlot, ResolvedIntent,
} from "@/lib/api";
import { Modal, Spinner, fmtDate, useToast } from "@/components/ui";
import { EditOnly, Editable } from "@/components/Permission";

const RULE_FIELDS: { key: keyof IntentRules; label: string; hint: string }[] = [
  { key: "paths", label: "Landing pages", hint: "/pricing*, /plans" },
  { key: "utm_campaign", label: "UTM campaign", hint: "switch-*, spring-sale" },
  { key: "utm_source", label: "UTM source", hint: "google, linkedin" },
  { key: "utm_medium", label: "UTM medium", hint: "cpc, email" },
  { key: "referrer_hosts", label: "Referrer hosts", hint: "*.g2.com" },
  { key: "query_terms", label: "Search terms", hint: "vs, alternative, price" },
];
const STAGES = ["", "learn", "evaluate", "buy", "customer"];
const SOURCE_LABEL: Record<string, string> = {
  rule: "matched a rule", embedding: "similar wording", model: "classified earlier", default: "no match: general",
  console: "chosen here",
};
const splitList = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

type SlotDraft = { name: string; label: string; purpose: string; components: string[]; pages: string; enabled: boolean; isNew: boolean };
type FamilyDraft = { slug: string; label: string; description: string; stage: string; priority: number; enabled: boolean;
  rules: Record<string, string>; isNew: boolean };

export default function RegionsPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [slots, setSlots] = useState<RegionSlot[] | null>(null);
  const [components, setComponents] = useState<{ id: string; renderer: string; purpose: string }[]>([]);
  const [families, setFamilies] = useState<IntentFamily[]>([]);
  const [plans, setPlans] = useState<PlanRow[]>([]);
  const [familyFilter, setFamilyFilter] = useState("");
  const [slotDraft, setSlotDraft] = useState<SlotDraft | null>(null);
  const [famDraft, setFamDraft] = useState<FamilyDraft | null>(null);
  const [suggestions, setSuggestions] = useState<Omit<IntentFamily, "id" | "enabled" | "updated_at">[] | null>(null);
  const [preview, setPreview] = useState<PlanView | null>(null);
  const [busy, setBusy] = useState(false);
  const [gen, setGen] = useState({ page: "/", family: "" });
  const [tryIt, setTryIt] = useState({ page: "/pricing", utm_campaign: "", q: "", referrer: "" });
  const [tried, setTried] = useState<ResolvedIntent | null>(null);
  const [bandit, setBandit] = useState<Omit<RegionSettings, "regions_enabled"> | null>(null);

  const loadPlans = useCallback((family = "") =>
    Api.listPlans(id, family || undefined).then((r) => setPlans(r.plans)).catch(() => setPlans([])), [id]);
  const load = useCallback(() =>
    Promise.all([Api.getRegionSettings(id), Api.listRegions(id), Api.listIntentFamilies(id)])
      .then(([s, r, f]) => {
        setEnabled(s.regions_enabled); setSlots(r.regions); setComponents(r.components); setFamilies(f.families);
        setBandit({ bandit_enabled: s.bandit_enabled, max_arms: s.max_arms, explore_pct: s.explore_pct });
      })
      .catch(() => toast("Could not load regions", "err")), [id, toast]);
  useEffect(() => { load(); loadPlans(); }, [load, loadPlans]);

  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true);
    try { await fn(); if (ok) toast(ok); }
    catch (e) { toast(e instanceof ApiError ? e.message : "Something went wrong", "err"); }
    finally { setBusy(false); }
  };

  const toggle = () => run(async () => setEnabled((await Api.setRegionSettings(id, !enabled)).regions_enabled),
    enabled ? "Generated regions are off: visitors see your page's own content" : "Generated regions are on");

  const saveBandit = (patch: Partial<Omit<RegionSettings, "regions_enabled">>) => run(async () => {
    const s = await Api.setRegionSettings(id, !!enabled, patch);
    setBandit({ bandit_enabled: s.bandit_enabled, max_arms: s.max_arms, explore_pct: s.explore_pct });
  }, "Saved");

  const saveSlot = () => slotDraft && run(async () => {
    await Api.saveRegion(id, slotDraft.name.trim(), {
      label: slotDraft.label, purpose: slotDraft.purpose, components: slotDraft.components,
      pages: splitList(slotDraft.pages), enabled: slotDraft.enabled,
    });
    setSlotDraft(null); await load();
  }, "Region saved");

  const saveFamily = (d: FamilyDraft) => run(async () => {
    const rules: IntentRules = {};
    for (const f of RULE_FIELDS) { const v = splitList(d.rules[f.key] || ""); if (v.length) rules[f.key] = v; }
    await Api.saveIntentFamily(id, d.slug.trim(), { label: d.label, description: d.description, stage: d.stage,
      priority: d.priority, enabled: d.enabled, rules });
    setFamDraft(null); await load();
  }, "Intent family saved");

  const openPlan = (p: PlanRow) => run(async () => setPreview(await Api.getPlan(id, p.id)));
  const generate = () => run(async () => {
    const v = await Api.generatePlan(id, { page: gen.page || "/", family: gen.family || undefined });
    setPreview(v); await loadPlans(familyFilter);
  }, "Plan generated and cached");
  const setStatus = (pid: string, status: PlanStatus) => run(async () => {
    await Api.setPlanStatus(id, pid, status);
    await loadPlans(familyFilter);
    if (preview?.id === pid) setPreview(await Api.getPlan(id, pid));
  }, status === "pinned" ? "Pinned: always used for this goal and page" : status === "blocked"
    ? "Blocked: the next visitor gets a fresh plan" : "Back to automatic");
  const removePlan = (pid: string) => run(async () => {
    await Api.deletePlan(id, pid); if (preview?.id === pid) setPreview(null); await loadPlans(familyFilter);
  }, "Plan deleted");

  if (slots === null || enabled === null) return <div className="skeleton" style={{ height: 320 }} />;
  const famLabel = (slug: string) => families.find((f) => f.slug === slug)?.label ?? (slug === "general" ? "General visitor" : slug);

  return (
    <div className="fade-in">
      <div className="row between page-head wrap" style={{ gap: 12 }}>
        <div>
          <h2>Regions</h2>
          <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 700 }}>
            Wrap a part of your page in <code>&lt;fb-region name=&quot;hero&quot;&gt;…&lt;/fb-region&gt;</code> and FluidBuddha
            fills it for each visitor&apos;s likely goal, worked out before they say anything. Your own content shows until a
            region is ready, and stays if one can&apos;t be made. Search engines always see your own content.
          </p>
        </div>
        <EditOnly>
          <button className={`btn ${enabled ? "btn-ghost" : "btn-primary"}`} onClick={toggle} disabled={busy}>
            {enabled ? "Turn generated regions off" : "Turn generated regions on"}
          </button>
        </EditOnly>
      </div>
      {!enabled && <div className="notice" style={{ marginBottom: 14 }}>Generated regions are off: every visitor sees your page&apos;s own content.</div>}

      {/* ---- learning (bandits, Phase 3) ---- */}
      {bandit && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="row between wrap" style={{ gap: 8 }}>
            <div>
              <h3>Learn what works</h3>
              <p className="muted" style={{ fontSize: "0.84rem", maxWidth: 640 }}>
                Try up to {bandit.max_arms} versions of each plan and send more visitors to the one that gets more clicks,
                sign-ups and goals. A share of visitors always sees every version, so new ones get a fair chance.
              </p>
            </div>
            <EditOnly>
              <div className="row wrap" style={{ gap: 10, alignItems: "center" }}>
                <label className="row" style={{ gap: 6, fontSize: "0.86rem" }}>
                  <input type="checkbox" checked={bandit.bandit_enabled} disabled={busy}
                    onChange={(e) => saveBandit({ bandit_enabled: e.target.checked })} /> On
                </label>
                <label className="row" style={{ gap: 6, fontSize: "0.86rem" }}>Versions
                  <select className="select" style={{ width: 70 }} value={bandit.max_arms} disabled={busy}
                    onChange={(e) => saveBandit({ max_arms: Number(e.target.value) })}>
                    {[1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
                <label className="row" style={{ gap: 6, fontSize: "0.86rem" }}>Always explore
                  <select className="select" style={{ width: 80 }} value={bandit.explore_pct} disabled={busy}
                    onChange={(e) => saveBandit({ explore_pct: Number(e.target.value) })}>
                    {[0, 5, 10, 20, 30].map((n) => <option key={n} value={n}>{n}%</option>)}
                  </select>
                </label>
              </div>
            </EditOnly>
          </div>
        </div>
      )}

      {/* ---- slots ---- */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
          <h3>Slots on your pages</h3>
          <EditOnly>
            <button className="btn btn-sm" onClick={() => setSlotDraft({ name: "", label: "", purpose: "", components: [],
              pages: "", enabled: true, isNew: true })}>Add a region</button>
          </EditOnly>
        </div>
        {slots.length === 0 ? (
          <div className="empty">No regions yet. Add one, then put <code>&lt;fb-region name=&quot;…&quot;&gt;</code> around that part of your page.</div>
        ) : (
          <table className="table">
            <thead><tr><th>Name</th><th>Purpose</th><th>Components</th><th>Pages</th><th></th></tr></thead>
            <tbody>
              {slots.map((s) => (
                <tr key={s.id}>
                  <td><span className="mono" style={{ fontSize: "0.82rem" }}>{s.name}</span>
                    {!s.enabled && <span className="badge" style={{ marginLeft: 6 }}>off</span>}
                    <div className="faint" style={{ fontSize: "0.8rem" }}>{s.label}</div></td>
                  <td className="muted" style={{ maxWidth: 260 }}>{s.purpose || "—"}</td>
                  <td className="mono faint" style={{ fontSize: "0.76rem" }}>{s.components.length ? s.components.join(", ") : "any"}</td>
                  <td className="mono faint" style={{ fontSize: "0.76rem" }}>{s.pages.length ? s.pages.join(", ") : "every page"}</td>
                  <td><EditOnly><div className="row" style={{ gap: 4 }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => setSlotDraft({ ...s, pages: s.pages.join(", "), isNew: false })}>Edit</button>
                    <button className="btn btn-ghost btn-sm btn-danger"
                      onClick={() => run(async () => { await Api.deleteRegion(id, s.name); await load(); }, "Region removed")}>Remove</button>
                  </div></EditOnly></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ---- intent families ---- */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="row between wrap" style={{ gap: 8, marginBottom: 6 }}>
          <h3>Visitor goals</h3>
          <EditOnly><div className="row" style={{ gap: 6 }}>
            <button className="btn btn-ghost btn-sm" disabled={busy}
              onClick={() => run(async () => setSuggestions((await Api.suggestIntentFamilies(id)).suggestions))}>Suggest from my pages</button>
            <button className="btn btn-sm" onClick={() => setFamDraft({ slug: "", label: "", description: "", stage: "evaluate",
              priority: 0, enabled: true, rules: {}, isNew: true })}>Add a goal</button>
          </div></EditOnly>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 10 }}>
          Each visitor is matched to a goal from where they landed and how they arrived: your rules first, then similar
          wording, otherwise &quot;general&quot;. Nobody waits for this.
        </p>
        {families.length === 0 ? <div className="empty">No goals yet: everyone is a general visitor.</div> : (
          <table className="table">
            <thead><tr><th>Goal</th><th>Stage</th><th>Rules</th><th>Priority</th><th></th></tr></thead>
            <tbody>
              {families.map((f) => (
                <tr key={f.id}>
                  <td><strong>{f.label}</strong>{!f.enabled && <span className="badge" style={{ marginLeft: 6 }}>off</span>}
                    <div className="mono faint" style={{ fontSize: "0.76rem" }}>{f.slug}</div>
                    <div className="muted" style={{ fontSize: "0.8rem" }}>{f.description}</div></td>
                  <td className="muted">{f.stage || "—"}</td>
                  <td className="mono faint" style={{ fontSize: "0.76rem", maxWidth: 260 }}>
                    {Object.entries(f.rules).map(([k, v]) => <div key={k}>{k}: {(v || []).join(", ")}</div>)}
                    {!Object.keys(f.rules).length && "wording only"}</td>
                  <td>{f.priority}</td>
                  <td><EditOnly><div className="row" style={{ gap: 4 }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => setFamDraft({ ...f, isNew: false,
                      rules: Object.fromEntries(Object.entries(f.rules).map(([k, v]) => [k, (v || []).join(", ")])) })}>Edit</button>
                    <button className="btn btn-ghost btn-sm btn-danger"
                      onClick={() => run(async () => { await Api.deleteIntentFamily(id, f.slug); await load(); }, "Goal removed")}>Remove</button>
                  </div></EditOnly></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {suggestions && (
          <div style={{ marginTop: 12 }}>
            <h4 style={{ marginBottom: 6 }}>Suggestions</h4>
            {suggestions.length === 0 ? <p className="faint">Nothing new to suggest from your pages.</p> : (
              <div className="row wrap" style={{ gap: 8 }}>
                {suggestions.map((sg) => (
                  <button key={sg.slug} className="btn btn-ghost btn-sm" title={sg.description}
                    onClick={() => saveFamily({ ...sg, enabled: true, isNew: true,
                      rules: Object.fromEntries(Object.entries(sg.rules).map(([k, v]) => [k, (v || []).join(", ")])) })
                      .then(() => setSuggestions((x) => x?.filter((y) => y.slug !== sg.slug) ?? null))}>
                    + {sg.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        <div className="row wrap" style={{ gap: 8, marginTop: 14, alignItems: "flex-end" }}>
          {(["page", "utm_campaign", "q", "referrer"] as const).map((k) => (
            <div className="field" key={k} style={{ margin: 0, flex: k === "referrer" ? 2 : 1, minWidth: 120 }}>
              <label className="label" htmlFor={`try-${k}`}>{k === "q" ? "Search terms" : k === "page" ? "Landing page" : k.replace("_", " ")}</label>
              <input id={`try-${k}`} className="input" value={tryIt[k]} onChange={(e) => setTryIt({ ...tryIt, [k]: e.target.value })} />
            </div>
          ))}
          <button className="btn btn-sm" disabled={busy} onClick={() => run(async () => {
            const { page, ...sig } = tryIt;
            setTried((await Api.resolveIntent(id, page, Object.fromEntries(Object.entries(sig).filter(([, v]) => v)))).intent);
          })}>Try it</button>
        </div>
        {tried && (
          <p style={{ fontSize: "0.86rem", marginTop: 8 }}>
            → <strong>{tried.label}</strong> <span className="faint">({SOURCE_LABEL[tried.source] ?? tried.source},
              confidence {Math.round(tried.confidence * 100)}%{tried.matched.length ? `: ${tried.matched.join("; ")}` : ""})</span>
          </p>
        )}
      </div>

      {/* ---- plans ---- */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
          <h3>Plans</h3>
          <select className="select" style={{ width: 220 }} value={familyFilter} aria-label="Filter by goal"
            onChange={(e) => { setFamilyFilter(e.target.value); loadPlans(e.target.value); }}>
            <option value="">All goals</option>
            <option value="general">General visitor</option>
            {families.map((f) => <option key={f.slug} value={f.slug}>{f.label}</option>)}
          </select>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 10 }}>
          A plan is built the first time a goal meets a page, then reused, so later visitors are served instantly.
          Pin one to always use it; block one to have it rebuilt.
        </p>
        <EditOnly>
          <div className="row wrap" style={{ gap: 8, marginBottom: 12, alignItems: "flex-end" }}>
            <div className="field" style={{ margin: 0 }}>
              <label className="label" htmlFor="gen-page">Page</label>
              <input id="gen-page" className="input" value={gen.page} onChange={(e) => setGen({ ...gen, page: e.target.value })} />
            </div>
            <div className="field" style={{ margin: 0 }}>
              <label className="label" htmlFor="gen-family">Goal</label>
              <select id="gen-family" className="select" value={gen.family} onChange={(e) => setGen({ ...gen, family: e.target.value })}>
                <option value="">Worked out from the page</option>
                <option value="general">General visitor</option>
                {families.map((f) => <option key={f.slug} value={f.slug}>{f.label}</option>)}
              </select>
            </div>
            <button className="btn btn-sm" onClick={generate} disabled={busy}>{busy ? <Spinner /> : "Generate a preview"}</button>
          </div>
        </EditOnly>
        {plans.length === 0 ? <div className="empty">No plans yet. They appear as visitors arrive, or generate one above.</div> : (
          <table className="table">
            <thead><tr><th>Goal</th><th>Page</th><th>Regions</th><th>Made by</th><th>Served</th><th>Results</th><th>Made</th><th></th></tr></thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.id}>
                  <td>{famLabel(p.family)}{p.persona && <span className="badge" style={{ marginLeft: 6 }}>{p.persona}</span>}
                    {!!p.taste && <span className="badge" style={{ marginLeft: 6 }} title="Taste bucket">{p.taste}</span>}
                    {!!p.arm && <span className="badge" style={{ marginLeft: 6 }}>version {p.arm + 1}</span>}
                    {p.status !== "auto" && <span className={`badge ${p.status === "pinned" ? "accent" : "err"}`} style={{ marginLeft: 6 }}>{p.status}</span>}</td>
                  <td className="mono" style={{ fontSize: "0.8rem" }}>{p.page}</td>
                  <td className="mono faint" style={{ fontSize: "0.76rem" }}>{p.regions.join(", ")}</td>
                  <td className="muted">{p.composer === "model" ? "the agent" : "site content rules"}</td>
                  <td>{p.hit_count}×</td>
                  <td className="muted" style={{ fontSize: "0.8rem" }}>{p.reward_rate == null ? "—"
                    : `${(p.reward_rate * 100).toFixed(1)}% (${p.rewards})`}</td>
                  <td className="muted" style={{ fontSize: "0.8rem" }}>{fmtDate(p.created_at)}</td>
                  <td><button className="btn btn-ghost btn-sm" onClick={() => openPlan(p)}>Preview</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {preview && (
        <div className="card">
          <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
            <h3>{famLabel(preview.family)} on <span className="mono">{preview.page}</span>
              {preview.status !== "auto" && <span className="badge" style={{ marginLeft: 8 }}>{preview.status}</span>}</h3>
            <div className="row" style={{ gap: 6 }}>
              <EditOnly>
                {preview.status !== "pinned" && <button className="btn btn-sm" onClick={() => setStatus(preview.id, "pinned")}>Pin</button>}
                {preview.status !== "blocked" && <button className="btn btn-ghost btn-sm" onClick={() => setStatus(preview.id, "blocked")}>Block</button>}
                {preview.status === "pinned" && <button className="btn btn-ghost btn-sm" onClick={() => setStatus(preview.id, "auto")}>Unpin</button>}
                <button className="btn btn-ghost btn-sm btn-danger" onClick={() => removePlan(preview.id)}>Delete</button>
              </EditOnly>
              <button className="btn btn-ghost btn-sm" onClick={() => setPreview(null)}>Close</button>
            </div>
          </div>
          {!!preview.dropped?.length && (
            <div className="notice" style={{ marginBottom: 10, fontSize: "0.84rem" }}>
              Left out to stay accurate: {preview.dropped.join("; ")}
            </div>
          )}
          <iframe title="Region preview" sandbox="" srcDoc={preview.preview_html}
            style={{ width: "100%", height: 520, border: "1px solid var(--line)", borderRadius: 12, background: "#fff" }} />
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 6 }}>
            Live data is fetched fresh for every visitor; this preview shows it as of now. Regions drawn by your own
            components appear as labelled boxes here.
          </p>
        </div>
      )}

      {slotDraft && (
        <Modal open title={slotDraft.isNew ? "Add a region" : `Edit ${slotDraft.name}`} onClose={() => setSlotDraft(null)} width={620}>
          <Editable>
            <div className="field">
              <label className="label" htmlFor="sl-name">Name <span className="faint">(what &lt;fb-region name&gt; uses)</span></label>
              <input id="sl-name" className="input mono" value={slotDraft.name} disabled={!slotDraft.isNew}
                placeholder="hero" onChange={(e) => setSlotDraft({ ...slotDraft, name: e.target.value.toLowerCase() })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="sl-label">Label</label>
              <input id="sl-label" className="input" value={slotDraft.label} onChange={(e) => setSlotDraft({ ...slotDraft, label: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="sl-purpose">What it&apos;s for</label>
              <input id="sl-purpose" className="input" value={slotDraft.purpose} placeholder="The opening message under the navigation"
                onChange={(e) => setSlotDraft({ ...slotDraft, purpose: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="sl-pages">Pages <span className="faint">(empty = every page; e.g. /, /pricing*, /blog/*)</span></label>
              <input id="sl-pages" className="input mono" value={slotDraft.pages} onChange={(e) => setSlotDraft({ ...slotDraft, pages: e.target.value })} />
            </div>
            <div className="field">
              <span className="label">Components it may use <span className="faint">(none ticked = any)</span></span>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: 6, maxHeight: 200, overflowY: "auto" }}>
                {components.map((c) => (
                  <label key={c.id} className="row" style={{ gap: 6, fontSize: "0.82rem" }} title={c.purpose}>
                    <input type="checkbox" checked={slotDraft.components.includes(c.id)}
                      onChange={() => setSlotDraft({ ...slotDraft, components: slotDraft.components.includes(c.id)
                        ? slotDraft.components.filter((x) => x !== c.id) : [...slotDraft.components, c.id] })} />
                    <span className="mono">{c.id}</span>
                  </label>
                ))}
              </div>
            </div>
            <label className="row" style={{ gap: 6, fontSize: "0.86rem", marginBottom: 14 }}>
              <input type="checkbox" checked={slotDraft.enabled} onChange={(e) => setSlotDraft({ ...slotDraft, enabled: e.target.checked })} /> On
            </label>
            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setSlotDraft(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={saveSlot} disabled={busy || !slotDraft.name.trim()}>Save region</button>
            </div>
          </Editable>
        </Modal>
      )}

      {famDraft && (
        <Modal open title={famDraft.isNew ? "Add a visitor goal" : `Edit ${famDraft.label}`} onClose={() => setFamDraft(null)} width={620}>
          <Editable>
            <div className="row" style={{ gap: 10 }}>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="fd-slug">Slug</label>
                <input id="fd-slug" className="input mono" value={famDraft.slug} disabled={!famDraft.isNew} placeholder="compare-plans"
                  onChange={(e) => setFamDraft({ ...famDraft, slug: e.target.value.toLowerCase() })} />
              </div>
              <div className="field" style={{ flex: 2 }}>
                <label className="label" htmlFor="fd-label">Name</label>
                <input id="fd-label" className="input" value={famDraft.label} placeholder="Comparing plans"
                  onChange={(e) => setFamDraft({ ...famDraft, label: e.target.value })} />
              </div>
            </div>
            <div className="field">
              <label className="label" htmlFor="fd-desc">Description <span className="faint">(also used to match similar wording)</span></label>
              <input id="fd-desc" className="input" value={famDraft.description}
                onChange={(e) => setFamDraft({ ...famDraft, description: e.target.value })} />
            </div>
            <div className="row" style={{ gap: 10 }}>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="fd-stage">Stage</label>
                <select id="fd-stage" className="select" value={famDraft.stage} onChange={(e) => setFamDraft({ ...famDraft, stage: e.target.value })}>
                  {STAGES.map((s) => <option key={s} value={s}>{s || "—"}</option>)}
                </select>
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="fd-prio">Priority <span className="faint">(higher wins)</span></label>
                <input id="fd-prio" type="number" className="input" value={famDraft.priority}
                  onChange={(e) => setFamDraft({ ...famDraft, priority: Number(e.target.value) || 0 })} />
              </div>
            </div>
            <span className="label">Rules <span className="faint">(any one matches; * is a wildcard; comma-separated)</span></span>
            {RULE_FIELDS.map((f) => (
              <div className="field" key={f.key} style={{ marginBottom: 8 }}>
                <label className="label faint" htmlFor={`fd-${f.key}`} style={{ fontSize: "0.8rem" }}>{f.label}</label>
                <input id={`fd-${f.key}`} className="input mono" placeholder={f.hint} value={famDraft.rules[f.key] || ""}
                  onChange={(e) => setFamDraft({ ...famDraft, rules: { ...famDraft.rules, [f.key]: e.target.value } })} />
              </div>
            ))}
            <label className="row" style={{ gap: 6, fontSize: "0.86rem", margin: "6px 0 14px" }}>
              <input type="checkbox" checked={famDraft.enabled} onChange={(e) => setFamDraft({ ...famDraft, enabled: e.target.checked })} /> On
            </label>
            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setFamDraft(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={() => saveFamily(famDraft)}
                disabled={busy || !famDraft.slug.trim() || !famDraft.label.trim()}>Save goal</button>
            </div>
          </Editable>
        </Modal>
      )}
    </div>
  );
}
