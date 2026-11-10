"use client";
/**
 * Composed pages (Phase 2, G2): the routes FluidBuddha composes whole pages
 * for, the canonical page search engines get, and the records (entities)
 * pages bind to — typed in, imported, or synced from a content feed.
 *
 * Free-form pages (Phase 4, G3): routes in free-form mode get a page made for
 * each visitor, assembled from proven fragments or written by the model within
 * a budget. Owners keep control with pinned regions, routes that can never be
 * free-form, a review feed of sampled pages, and pin/block on fragments.
 */
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Api, ApiError, Connector, ConnectorInput, EntityRecord, Fragment, FreeformSettings, IntentFamily, ReviewSample,
  RouteInput, RouteMode, SiteRoute,
} from "@/lib/api";
import { Modal, Spinner, fmtDate, useToast } from "@/components/ui";
import { EditOnly, Editable } from "@/components/Permission";

type Preview = { route: SiteRoute; html: string; planRow: string; composer: string };
type RouteDraft = RouteInput & { isNew: boolean; id?: string; pinnedJson: string };
const blankRoute: RouteDraft = { pattern: "", title: "", purpose: "", enabled: true, priority: 0, mode: "composed",
  pinned_regions: [], pinnedJson: "[]", isNew: true };
const PIN_EXAMPLE = '[\n  { "id": "notice", "component": "fb.text", "props": { "body": "Prices exclude GST." }, "position": "bottom" }\n]';
const FLAG_LABEL: Record<string, string> = {
  validator: "had to be repaired", "few regions": "few regions", "no call to action": "no call to action",
  "pinned region missing": "a pinned region is missing",
};
const blankConnector: ConnectorInput = { kind: "json_feed", name: "", url: "", entity_type: "", items_path: "", key_field: "slug", fields: {} };

export default function PagesPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [routes, setRoutes] = useState<SiteRoute[] | null>(null);
  const [hostedBase, setHostedBase] = useState("");
  const [families, setFamilies] = useState<IntentFamily[]>([]);
  const [types, setTypes] = useState<{ type: string; count: number }[]>([]);
  const [type, setType] = useState("");
  const [records, setRecords] = useState<EntityRecord[]>([]);
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [routeDraft, setRouteDraft] = useState<RouteDraft | null>(null);
  const [ff, setFf] = useState<FreeformSettings | null>(null);
  const [ffDraft, setFfDraft] = useState<(FreeformSettings & { blockedText: string }) | null>(null);
  const [fragments, setFragments] = useState<Fragment[]>([]);
  const [reviews, setReviews] = useState<ReviewSample[]>([]);
  const [reviewOpen, setReviewOpen] = useState<ReviewSample | null>(null);
  const [genFamily, setGenFamily] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Preview | null>(null);
  const [recordDraft, setRecordDraft] = useState<{ type: string; key: string; json: string; isNew: boolean } | null>(null);
  const [importDraft, setImportDraft] = useState<{ type: string; format: "json" | "csv"; key_field: string; content: string } | null>(null);
  const [connDraft, setConnDraft] = useState<ConnectorInput | null>(null);
  const [busy, setBusy] = useState(false);

  const loadRecords = useCallback((t: string) => (t ? Api.listEntities(id, t).then((r) => setRecords(r.records))
    .catch(() => setRecords([])) : Promise.resolve()), [id]);
  const load = useCallback(() =>
    Promise.all([Api.listRoutes(id), Api.listIntentFamilies(id), Api.entityTypes(id), Api.listConnectors(id),
      Api.getFreeform(id), Api.listFragments(id), Api.listReviews(id, "new")])
      .then(([r, f, t, c, s, fr, rv]) => {
        setRoutes(r.routes); setHostedBase(r.hosted_base); setFamilies(f.families); setTypes(t.types); setConnectors(c.connectors);
        setType((cur) => cur || t.types[0]?.type || "");
        setFf(s); setFragments(fr.fragments); setReviews(rv.reviews);
      })
      .catch(() => toast("Could not load pages", "err")), [id, toast]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadRecords(type); }, [type, loadRecords]);

  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true);
    try { await fn(); if (ok) toast(ok); }
    catch (e) { toast(e instanceof ApiError ? e.message : "Something went wrong", "err"); }
    finally { setBusy(false); }
  };

  const saveRoute = () => routeDraft && run(async () => {
    let pinned: RouteInput["pinned_regions"] = [];
    if (routeDraft.mode === "freeform" && routeDraft.pinnedJson.trim()) {
      try { pinned = JSON.parse(routeDraft.pinnedJson); } catch { throw new ApiError(422, "Pinned regions aren't valid JSON"); }
      if (!Array.isArray(pinned)) throw new ApiError(422, "Pinned regions are a list");
    }
    const body: RouteInput = { pattern: routeDraft.pattern, title: routeDraft.title, purpose: routeDraft.purpose,
      enabled: routeDraft.enabled, priority: routeDraft.priority, mode: routeDraft.mode, pinned_regions: pinned };
    if (routeDraft.isNew || !routeDraft.id) await Api.createRoute(id, body);
    else await Api.updateRoute(id, routeDraft.id, body);
    setRouteDraft(null); await load();
  }, "Route saved");

  const generate = (r: SiteRoute) => run(async () => {
    const out = await Api.generateRoutePage(id, r.id, { family: genFamily[r.id] || undefined });
    setPreview({ route: r, html: out.preview_html, planRow: out.id, composer: out.composer }); await load();
  }, "Page composed and cached");

  const saveFreeform = () => ffDraft && run(async () => {
    const blocked = ffDraft.blockedText.split(/[\n,]/).map((s) => s.trim()).filter(Boolean);
    const { blockedText: _ignored, ...rest } = ffDraft;
    void _ignored;
    setFf(await Api.setFreeform(id, { ...rest, g3_blocked_patterns: blocked })); setFfDraft(null);
  }, "Free-form settings saved");
  const setFragment = (f: Fragment, status: Fragment["status"]) => run(async () => {
    await Api.setFragmentStatus(id, f.id, status); await load();
  }, status === "blocked" ? "Fragment blocked: it will not be used again" : status === "pinned" ? "Fragment pinned" : "Fragment back to automatic");
  const review = (r: ReviewSample, verdict: "ok" | "flagged") => run(async () => {
    await Api.reviewSample(id, r.id, verdict); setReviewOpen(null); await load();
  }, verdict === "flagged" ? "Flagged: that page and its fragments are blocked" : "Marked as fine");
  const fragText = (f: Fragment) => {
    const p = (f.region.props || {}) as Record<string, unknown>;
    const v = p.title ?? p.body ?? p.subtitle ?? p.heading ?? Object.values(p).find((x) => typeof x === "string");
    return typeof v === "string" ? v.slice(0, 90) : "";
  };
  const freeformRoutes = routes?.filter((r) => r.mode === "freeform").length ?? 0;

  const samplePath = (pattern: string) => pattern.replace("/*", "/example").replace(/:([a-z_]+)/g, "example");

  if (routes === null) return <div className="skeleton" style={{ height: 320 }} />;
  const famLabel = (slug: string) => families.find((f) => f.slug === slug)?.label ?? (slug === "general" ? "General visitor" : slug);

  return (
    <div className="fade-in">
      <div className="page-head">
        <h2>Pages</h2>
        <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 720 }}>
          Whole pages FluidBuddha composes for each visitor&apos;s goal from your approved components and your own data,
          rendered on the server. Serve them from your Next.js site with <code>@fluidbuddha/next</code>, from an edge worker in front of any site with <code>@fluidbuddha/edge</code>, or preview them here.
          Search engines get the canonical page you choose.
        </p>
      </div>

      {/* ---- routes ---- */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
          <h3>Routes</h3>
          <EditOnly><button className="btn btn-sm" onClick={() => setRouteDraft({ ...blankRoute })}>Add a route</button></EditOnly>
        </div>
        {routes.length === 0 ? (
          <div className="empty">No routes yet. Add one such as <code>/pricing</code> or <code>/products/:slug</code>.</div>
        ) : routes.map((r) => (
          <div key={r.id} style={{ borderTop: "1px solid var(--line)", padding: "12px 0" }}>
            <div className="row between wrap" style={{ gap: 8 }}>
              <div>
                <span className="mono" style={{ fontWeight: 600 }}>{r.pattern}</span>
                {!r.enabled && <span className="badge" style={{ marginLeft: 6 }}>off</span>}
                {r.mode === "freeform" && <span className="badge accent" style={{ marginLeft: 6 }}
                  title="Each visitor gets a page made for them">free-form</span>}
                {(r.pinned_regions?.length ?? 0) > 0 && <span className="badge" style={{ marginLeft: 6 }}>
                  {r.pinned_regions!.length} pinned</span>}
                <span className="muted" style={{ marginLeft: 8 }}>{r.title}</span>
                <div className="faint" style={{ fontSize: "0.8rem" }}>{r.purpose}</div>
              </div>
              <div className="row wrap" style={{ gap: 6 }}>
                <a className="btn btn-ghost btn-sm" href={`${hostedBase}${samplePath(r.pattern)}`} target="_blank" rel="noreferrer">Open served page</a>
                <EditOnly>
                  <select className="select" style={{ width: 190 }} aria-label="Goal to compose for" value={genFamily[r.id] || ""}
                    onChange={(e) => setGenFamily({ ...genFamily, [r.id]: e.target.value })}>
                    <option value="">Goal: worked out</option>
                    <option value="general">General visitor</option>
                    {families.map((f) => <option key={f.slug} value={f.slug}>{f.label}</option>)}
                  </select>
                  <button className="btn btn-sm" onClick={() => generate(r)} disabled={busy}>{busy ? <Spinner /> : "Compose a preview"}</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => setRouteDraft({ ...r, mode: r.mode ?? "composed", isNew: false,
                    pinnedJson: r.pinned_regions?.length ? JSON.stringify(r.pinned_regions, null, 2) : "[]" })}>Edit</button>
                  <button className="btn btn-ghost btn-sm btn-danger"
                    onClick={() => run(async () => { await Api.deleteRoute(id, r.id); await load(); }, "Route removed")}>Remove</button>
                </EditOnly>
              </div>
            </div>
            {r.plans.length > 0 && (
              <table className="table" style={{ marginTop: 8 }}>
                <thead><tr><th>Goal</th><th>Made by</th><th>Served</th><th>Results</th><th>Made</th><th></th></tr></thead>
                <tbody>
                  {r.plans.map((p) => (
                    <tr key={p.id}>
                      <td>{famLabel(p.family)}
                        {r.canonical_plan === p.id && <span className="badge accent" style={{ marginLeft: 6 }}>canonical</span>}
                        {p.status !== "auto" && r.canonical_plan !== p.id && <span className="badge" style={{ marginLeft: 6 }}>{p.status}</span>}</td>
                      <td className="muted">{p.composer === "rules" ? "site content rules" : p.composer === "fallback" ? "reused page" : "the agent"}</td>
                      <td>{p.hit_count}×</td>
                      <td className="muted" style={{ fontSize: "0.8rem" }}>{p.reward_rate == null ? "—"
                        : `${(p.reward_rate * 100).toFixed(1)}%`}{p.arm ? ` · v${p.arm + 1}` : ""}{p.taste ? ` · ${p.taste}` : ""}</td>
                      <td className="muted" style={{ fontSize: "0.8rem" }}>{fmtDate(p.created_at)}</td>
                      <td><EditOnly>
                        {r.canonical_plan === p.id ? (
                          <button className="btn btn-ghost btn-sm" onClick={() => run(async () => { await Api.setCanonical(id, r.id, null); await load(); }, "No canonical page")}>Unset canonical</button>
                        ) : p.status !== "blocked" && (
                          <button className="btn btn-ghost btn-sm" onClick={() => run(async () => { await Api.setCanonical(id, r.id, p.id); await load(); }, "Search engines get this page")}>Make canonical</button>
                        )}
                      </EditOnly></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>

      {preview && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
            <h3>Preview of <span className="mono">{preview.route.pattern}</span>
              <span className="faint" style={{ fontSize: "0.82rem", marginLeft: 8 }}>
                {preview.composer === "rules" ? "composed from site content (no model)" : `composed by ${preview.composer}`}</span></h3>
            <div className="row" style={{ gap: 6 }}>
              <EditOnly><button className="btn btn-sm" onClick={() => run(async () => {
                await Api.setCanonical(id, preview.route.id, preview.planRow); await load();
              }, "Search engines get this page")}>Make canonical</button></EditOnly>
              <button className="btn btn-ghost btn-sm" onClick={() => setPreview(null)}>Close</button>
            </div>
          </div>
          <iframe title="Page preview" sandbox="" srcDoc={preview.html}
            style={{ width: "100%", height: 560, border: "1px solid var(--line)", borderRadius: 12, background: "#fff" }} />
        </div>
      )}

      {/* ---- free-form (Phase 4) ---- */}
      {ff && (
        <div className="card" style={{ marginBottom: 18 }}>
          <div className="row between wrap" style={{ gap: 8, marginBottom: 6 }}>
            <h3>Free-form pages {ff.freeform_enabled ? <span className="badge accent">on</span> : <span className="badge">off</span>}</h3>
            <EditOnly><button className="btn btn-ghost btn-sm"
              onClick={() => setFfDraft({ ...ff, blockedText: ff.g3_blocked_patterns.join("\n") })}>Settings</button></EditOnly>
          </div>
          <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 10, maxWidth: 760 }}>
            On routes set to <strong>free-form</strong>, each visitor gets a page made for them — assembled from fragments
            that worked before, or written by the agent within your budget — and keeps it on later visits. Search engines and
            visitors without an id get the composed page. {freeformRoutes === 0
              ? "No route is free-form yet: edit a route and choose Free-form."
              : `${freeformRoutes} route${freeformRoutes === 1 ? " is" : "s are"} free-form.`}
          </p>
          <div className="row wrap" style={{ gap: 18, fontSize: "0.84rem" }}>
            <span><span className="faint">Budget</span> {ff.g3_daily_budget} new pages a day · {ff.g3_visitor_budget} per visitor</span>
            <span><span className="faint">Review</span> {ff.review_sample_pct}% of pages sampled</span>
            <span><span className="faint">Never free-form</span> <span className="mono">{ff.g3_blocked_patterns.join("  ") || "—"}</span></span>
          </div>

          <h4 style={{ margin: "18px 0 8px" }}>Review feed {reviews.length > 0 && <span className="badge">{reviews.length} to review</span>}</h4>
          {reviews.length === 0 ? <div className="empty">Nothing to review. Sampled and flagged pages appear here.</div> : (
            <table className="table">
              <thead><tr><th>Route</th><th>Why it&apos;s here</th><th>Made</th><th></th></tr></thead>
              <tbody>
                {reviews.map((r) => (
                  <tr key={r.id}>
                    <td className="mono">{r.route}</td>
                    <td>{r.flags.length ? r.flags.map((f) => <span key={f} className="badge" style={{ marginRight: 4 }}>{FLAG_LABEL[f] ?? f}</span>)
                      : <span className="muted">sampled</span>}</td>
                    <td className="muted" style={{ fontSize: "0.8rem" }}>{fmtDate(r.created_at)}</td>
                    <td><div className="row" style={{ gap: 4 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setReviewOpen(r)}>View</button>
                      <EditOnly>
                        <button className="btn btn-ghost btn-sm" onClick={() => review(r, "ok")}>Fine</button>
                        <button className="btn btn-ghost btn-sm btn-danger" onClick={() => review(r, "flagged")}>Flag</button>
                      </EditOnly>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h4 style={{ margin: "18px 0 8px" }}>Fragments</h4>
          <p className="muted" style={{ fontSize: "0.82rem", marginBottom: 8 }}>
            Regions from earlier pages, reused when they fit a visitor&apos;s goal. Ones that earn results are preferred;
            pin one to favour it, block one to never use it again.
          </p>
          {fragments.length === 0 ? <div className="empty">No fragments yet. They are collected as pages are composed.</div> : (
            <table className="table">
              <thead><tr><th>Purpose</th><th>Content</th><th>For</th><th>Used</th><th>Results</th><th></th></tr></thead>
              <tbody>
                {fragments.slice(0, 50).map((f) => (
                  <tr key={f.id}>
                    <td>{f.purpose} {f.status !== "auto" && <span className={`badge ${f.status === "pinned" ? "accent" : ""}`}>{f.status}</span>}
                      <div className="mono faint" style={{ fontSize: "0.74rem" }}>{f.component}</div></td>
                    <td className="muted" style={{ fontSize: "0.82rem", maxWidth: 360 }}>{fragText(f) || "—"}</td>
                    <td className="faint" style={{ fontSize: "0.78rem" }}>{f.conditions.family ? famLabel(f.conditions.family) : "anyone"}
                      {f.conditions.lang ? ` · ${f.conditions.lang}` : ""}</td>
                    <td>{f.hit_count}×</td>
                    <td className="muted">{f.hit_count ? `${((f.rewards / f.hit_count) * 100).toFixed(0)}%` : "—"}</td>
                    <td><EditOnly><div className="row" style={{ gap: 4 }}>
                      {f.status !== "pinned" && <button className="btn btn-ghost btn-sm" onClick={() => setFragment(f, "pinned")}>Pin</button>}
                      {f.status !== "auto" && <button className="btn btn-ghost btn-sm" onClick={() => setFragment(f, "auto")}>Automatic</button>}
                      {f.status !== "blocked" && <button className="btn btn-ghost btn-sm btn-danger" onClick={() => setFragment(f, "blocked")}>Block</button>}
                    </div></EditOnly></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ---- entities ---- */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
          <h3>Records pages can show</h3>
          <EditOnly><div className="row" style={{ gap: 6 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setImportDraft({ type: type || "Product", format: "json", key_field: "slug", content: "" })}>Import JSON or CSV</button>
            <button className="btn btn-sm" onClick={() => setRecordDraft({ type: type || "Product", key: "", json: "{\n  \"name\": \"\"\n}", isNew: true })}>Add a record</button>
          </div></EditOnly>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 10 }}>
          Products, plans, case studies, posts… Pages bind to them (<code>entity:Product</code>), so details come from
          your records, never from the model.
        </p>
        {types.length === 0 ? <div className="empty">No records yet. Import some, add one, or connect a content feed below.</div> : (
          <>
            <div className="row wrap" style={{ gap: 6, marginBottom: 10 }}>
              {types.map((t) => (
                <button key={t.type} className={`btn btn-sm ${t.type === type ? "" : "btn-ghost"}`} onClick={() => setType(t.type)}>
                  {t.type} <span className="faint">({t.count})</span>
                </button>
              ))}
            </div>
            <table className="table">
              <thead><tr><th>Key</th><th>Fields</th><th>Source</th><th></th></tr></thead>
              <tbody>
                {records.map((rec) => (
                  <tr key={rec.id}>
                    <td className="mono" style={{ fontSize: "0.82rem" }}>{rec.key}</td>
                    <td className="muted" style={{ fontSize: "0.8rem", maxWidth: 420 }}>
                      {Object.entries(rec.data).slice(0, 4).map(([k, v]) => `${k}: ${typeof v === "object" ? "…" : String(v).slice(0, 40)}`).join(" · ")}</td>
                    <td className="faint" style={{ fontSize: "0.78rem" }}>{rec.source.startsWith("connector:") ? "feed" : rec.source}</td>
                    <td><EditOnly><div className="row" style={{ gap: 4 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setRecordDraft({ type: rec.type, key: rec.key, json: JSON.stringify(rec.data, null, 2), isNew: false })}>Edit</button>
                      <button className="btn btn-ghost btn-sm btn-danger" onClick={() => run(async () => {
                        await Api.deleteEntity(id, rec.type, rec.key); await load(); await loadRecords(type);
                      }, "Record deleted")}>Delete</button>
                    </div></EditOnly></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      {/* ---- connectors ---- */}
      <div className="card" style={{ marginBottom: 18 }}>
        <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
          <h3>Content feeds</h3>
          <EditOnly><button className="btn btn-sm" onClick={() => setConnDraft({ ...blankConnector })}>Connect a feed</button></EditOnly>
        </div>
        {connectors.length === 0 ? (
          <div className="empty">No feeds. Connect WordPress, or any JSON feed from your CMS, to keep records in sync.</div>
        ) : (
          <table className="table">
            <thead><tr><th>Feed</th><th>Fills</th><th>Last sync</th><th></th></tr></thead>
            <tbody>
              {connectors.map((c) => (
                <tr key={c.id}>
                  <td><strong>{c.name || (c.kind === "wordpress" ? "WordPress" : "JSON feed")}</strong>
                    <div className="mono faint" style={{ fontSize: "0.76rem" }}>{c.url}</div></td>
                  <td className="mono">{c.entity_type}</td>
                  <td className="muted" style={{ fontSize: "0.82rem" }}>{c.last_sync_at ? `${fmtDate(c.last_sync_at)} · ${c.last_status}` : "never"}</td>
                  <td><EditOnly><div className="row" style={{ gap: 4 }}>
                    <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => run(async () => {
                      const r = await Api.syncConnector(id, c.id); await load(); await loadRecords(type);
                      if (!r.status.startsWith("ok")) throw new ApiError(422, r.status);
                    }, "Synced")}>Sync now</button>
                    <button className="btn btn-ghost btn-sm btn-danger" onClick={() => run(async () => { await Api.deleteConnector(id, c.id); await load(); await loadRecords(type); }, "Feed and its records removed")}>Remove</button>
                  </div></EditOnly></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {routeDraft && (
        <Modal open title={routeDraft.isNew ? "Add a route" : `Edit ${routeDraft.pattern}`} onClose={() => setRouteDraft(null)}>
          <Editable>
            <div className="field">
              <label className="label" htmlFor="rt-pattern">Pattern <span className="faint">(/pricing, /products/:slug, /guides/*)</span></label>
              <input id="rt-pattern" className="input mono" value={routeDraft.pattern} disabled={!routeDraft.isNew}
                onChange={(e) => setRouteDraft({ ...routeDraft, pattern: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="rt-title">Title</label>
              <input id="rt-title" className="input" value={routeDraft.title} onChange={(e) => setRouteDraft({ ...routeDraft, title: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="rt-purpose">What this page is for</label>
              <input id="rt-purpose" className="input" value={routeDraft.purpose} placeholder="Help visitors choose a plan"
                onChange={(e) => setRouteDraft({ ...routeDraft, purpose: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="rt-mode">Pages</label>
              <select id="rt-mode" className="select" value={routeDraft.mode ?? "composed"}
                onChange={(e) => setRouteDraft({ ...routeDraft, mode: e.target.value as RouteMode })}>
                <option value="composed">Composed for each visitor&apos;s goal</option>
                <option value="freeform">Free-form: a page made for each visitor</option>
              </select>
            </div>
            {routeDraft.mode === "freeform" && (
              <div className="field">
                <label className="label" htmlFor="rt-pinned">Pinned regions <span className="faint">(kept unchanged on every page; JSON)</span></label>
                <textarea id="rt-pinned" className="textarea mono" style={{ minHeight: 110 }} value={routeDraft.pinnedJson}
                  placeholder={PIN_EXAMPLE} spellCheck={false}
                  onChange={(e) => setRouteDraft({ ...routeDraft, pinnedJson: e.target.value })} />
                <div className="faint" style={{ fontSize: "0.76rem", marginTop: 4 }}>
                  For a legal notice or your brand header. <code>position</code> is <code>top</code> or <code>bottom</code>.</div>
              </div>
            )}
            <label className="row" style={{ gap: 6, fontSize: "0.86rem", marginBottom: 14 }}>
              <input type="checkbox" checked={routeDraft.enabled} onChange={(e) => setRouteDraft({ ...routeDraft, enabled: e.target.checked })} /> On
            </label>
            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setRouteDraft(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={saveRoute} disabled={busy || !routeDraft.pattern.trim()}>Save route</button>
            </div>
          </Editable>
        </Modal>
      )}

      {ffDraft && (
        <Modal open title="Free-form settings" onClose={() => setFfDraft(null)} width={560}>
          <Editable>
            <label className="row" style={{ gap: 6, fontSize: "0.86rem", marginBottom: 14 }}>
              <input type="checkbox" checked={ffDraft.freeform_enabled}
                onChange={(e) => setFfDraft({ ...ffDraft, freeform_enabled: e.target.checked })} /> Free-form pages on
            </label>
            <div className="row" style={{ gap: 10 }}>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="ff-day">New pages a day</label>
                <input id="ff-day" className="input" type="number" min={0} value={ffDraft.g3_daily_budget}
                  onChange={(e) => setFfDraft({ ...ffDraft, g3_daily_budget: Number(e.target.value) })} />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="ff-vis">Per visitor a day</label>
                <input id="ff-vis" className="input" type="number" min={0} max={50} value={ffDraft.g3_visitor_budget}
                  onChange={(e) => setFfDraft({ ...ffDraft, g3_visitor_budget: Number(e.target.value) })} />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="ff-rev">Review sample %</label>
                <input id="ff-rev" className="input" type="number" min={0} max={100} value={ffDraft.review_sample_pct}
                  onChange={(e) => setFfDraft({ ...ffDraft, review_sample_pct: Number(e.target.value) })} />
              </div>
            </div>
            <p className="faint" style={{ fontSize: "0.78rem", marginTop: -4, marginBottom: 12 }}>
              Pages the agent writes count against the budget; pages assembled from fragments don&apos;t. Past the budget,
              visitors get the composed page.</p>
            <div className="field">
              <label className="label" htmlFor="ff-block">Never free-form <span className="faint">(one per line; * matches the rest)</span></label>
              <textarea id="ff-block" className="textarea mono" style={{ minHeight: 110 }} value={ffDraft.blockedText}
                onChange={(e) => setFfDraft({ ...ffDraft, blockedText: e.target.value })} spellCheck={false} />
            </div>
            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setFfDraft(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={saveFreeform} disabled={busy}>Save</button>
            </div>
          </Editable>
        </Modal>
      )}

      {reviewOpen && (
        <Modal open title={`Page made for a visitor on ${reviewOpen.route}`} onClose={() => setReviewOpen(null)} width={900}>
          <iframe title="Free-form page" sandbox="" srcDoc={reviewOpen.preview_html}
            style={{ width: "100%", height: 520, border: "1px solid var(--line)", borderRadius: 12, background: "#fff" }} />
          <div className="row" style={{ gap: 8, justifyContent: "flex-end", marginTop: 12 }}>
            <button className="btn btn-ghost" onClick={() => setReviewOpen(null)}>Close</button>
            <EditOnly>
              <button className="btn btn-ghost btn-danger" onClick={() => review(reviewOpen, "flagged")} disabled={busy}>Flag</button>
              <button className="btn btn-primary" onClick={() => review(reviewOpen, "ok")} disabled={busy}>Fine</button>
            </EditOnly>
          </div>
        </Modal>
      )}

      {recordDraft && (
        <Modal open title={recordDraft.isNew ? "Add a record" : `Edit ${recordDraft.type} ${recordDraft.key}`} onClose={() => setRecordDraft(null)} width={600}>
          <Editable>
            <div className="row" style={{ gap: 10 }}>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="rc-type">Type</label>
                <input id="rc-type" className="input mono" value={recordDraft.type} disabled={!recordDraft.isNew}
                  onChange={(e) => setRecordDraft({ ...recordDraft, type: e.target.value })} />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="rc-key">Key</label>
                <input id="rc-key" className="input mono" value={recordDraft.key} disabled={!recordDraft.isNew}
                  onChange={(e) => setRecordDraft({ ...recordDraft, key: e.target.value })} />
              </div>
            </div>
            <div className="field">
              <label className="label" htmlFor="rc-json">Fields (JSON)</label>
              <textarea id="rc-json" className="textarea mono" style={{ minHeight: 200 }} value={recordDraft.json}
                onChange={(e) => setRecordDraft({ ...recordDraft, json: e.target.value })} spellCheck={false} />
            </div>
            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setRecordDraft(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy || !recordDraft.key.trim()} onClick={() => run(async () => {
                let data: Record<string, unknown>;
                try { data = JSON.parse(recordDraft.json); } catch { throw new ApiError(422, "The fields aren't valid JSON"); }
                await Api.saveEntity(id, recordDraft.type.trim(), recordDraft.key.trim(), data);
                setType(recordDraft.type.trim()); setRecordDraft(null); await load(); await loadRecords(recordDraft.type.trim());
              }, "Record saved")}>Save record</button>
            </div>
          </Editable>
        </Modal>
      )}

      {importDraft && (
        <Modal open title="Import records" onClose={() => setImportDraft(null)} width={620}>
          <Editable>
            <div className="row" style={{ gap: 10 }}>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="im-type">Type</label>
                <input id="im-type" className="input mono" value={importDraft.type} onChange={(e) => setImportDraft({ ...importDraft, type: e.target.value })} />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="im-format">Format</label>
                <select id="im-format" className="select" value={importDraft.format}
                  onChange={(e) => setImportDraft({ ...importDraft, format: e.target.value as "json" | "csv" })}>
                  <option value="json">JSON</option><option value="csv">CSV</option>
                </select>
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="im-key">Key field</label>
                <input id="im-key" className="input mono" value={importDraft.key_field} onChange={(e) => setImportDraft({ ...importDraft, key_field: e.target.value })} />
              </div>
            </div>
            <div className="field">
              <label className="label" htmlFor="im-content">Paste the data</label>
              <textarea id="im-content" className="textarea mono" style={{ minHeight: 220 }} value={importDraft.content}
                onChange={(e) => setImportDraft({ ...importDraft, content: e.target.value })} spellCheck={false} />
            </div>
            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setImportDraft(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy || !importDraft.content.trim()} onClick={() => run(async () => {
                const r = await Api.importEntities(id, importDraft);
                setType(importDraft.type); setImportDraft(null); await load(); await loadRecords(importDraft.type);
                if (r.problems.length) toast(`Imported ${r.imported}; skipped: ${r.problems.slice(0, 3).join("; ")}`, "err");
                else toast(`Imported ${r.imported} records`);
              })}>Import</button>
            </div>
          </Editable>
        </Modal>
      )}

      {connDraft && (
        <Modal open title="Connect a content feed" onClose={() => setConnDraft(null)} width={600}>
          <Editable>
            <div className="row" style={{ gap: 10 }}>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="cn-kind">Kind</label>
                <select id="cn-kind" className="select" value={connDraft.kind}
                  onChange={(e) => setConnDraft({ ...connDraft, kind: e.target.value as ConnectorInput["kind"] })}>
                  <option value="json_feed">JSON feed (any CMS)</option><option value="wordpress">WordPress</option>
                </select>
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="cn-type">Fills records of type</label>
                <input id="cn-type" className="input mono" placeholder="Post" value={connDraft.entity_type}
                  onChange={(e) => setConnDraft({ ...connDraft, entity_type: e.target.value })} />
              </div>
            </div>
            <div className="field">
              <label className="label" htmlFor="cn-name">Name</label>
              <input id="cn-name" className="input" value={connDraft.name} onChange={(e) => setConnDraft({ ...connDraft, name: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="cn-url">{connDraft.kind === "wordpress" ? "Your WordPress site" : "Feed address"} <span className="faint">(https)</span></label>
              <input id="cn-url" className="input mono" value={connDraft.url} placeholder={connDraft.kind === "wordpress" ? "https://blog.example.com" : "https://cms.example.com/api/products"}
                onChange={(e) => setConnDraft({ ...connDraft, url: e.target.value })} />
            </div>
            {connDraft.kind === "json_feed" && (
              <div className="row" style={{ gap: 10 }}>
                <div className="field" style={{ flex: 1 }}>
                  <label className="label" htmlFor="cn-items">Items path <span className="faint">(e.g. $.data[*])</span></label>
                  <input id="cn-items" className="input mono" value={connDraft.items_path} onChange={(e) => setConnDraft({ ...connDraft, items_path: e.target.value })} />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label className="label" htmlFor="cn-keyf">Key field</label>
                  <input id="cn-keyf" className="input mono" value={connDraft.key_field} onChange={(e) => setConnDraft({ ...connDraft, key_field: e.target.value })} />
                </div>
              </div>
            )}
            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost" onClick={() => setConnDraft(null)}>Cancel</button>
              <button className="btn btn-primary" disabled={busy || !connDraft.url.trim() || !connDraft.entity_type.trim()}
                onClick={() => run(async () => { await Api.createConnector(id, connDraft); setConnDraft(null); await load(); }, "Feed connected: sync it to fetch records")}>
                Connect
              </button>
            </div>
          </Editable>
        </Modal>
      )}
    </div>
  );
}
