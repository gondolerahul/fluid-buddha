"use client";
/**
 * Component manifest (P0-7, P0-9): the components generated pages may use.
 * Drafts are typed in or generated from Storybook or the live site; an Admin
 * approves one, and only the approved version reaches the agent. Approved
 * versions never change: edits make a new draft.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  Api, ApiError, ManifestEntryDoc, ManifestVersion, ManifestVersionSummary, ManifestView,
} from "@/lib/api";
import { Modal, Spinner, fmtDate, useToast } from "@/components/ui";
import { EditOnly } from "@/components/Permission";

const SOURCE_LABEL: Record<string, string> = {
  manual: "typed in", storybook: "from Storybook", site: "from the live site", file: "from a file",
};
const STATUS_BADGE: Record<string, string> = { draft: "badge", approved: "badge ok", archived: "badge" };

type Diff = { added: string[]; removed: string[]; changed: string[] };

function customEntries(data: Record<string, unknown> | undefined): Record<string, unknown> {
  const list = Array.isArray(data?.components) ? (data!.components as Record<string, unknown>[]) : [];
  return Object.fromEntries(list.filter((c) => c && typeof c.id === "string").map((c) => [String(c.id), c]));
}

function diff(next: Record<string, unknown> | undefined, base: Record<string, unknown> | undefined): Diff {
  const a = customEntries(next), b = customEntries(base);
  return {
    added: Object.keys(a).filter((k) => !(k in b)),
    removed: Object.keys(b).filter((k) => !(k in a)),
    changed: Object.keys(a).filter((k) => k in b && JSON.stringify(a[k]) !== JSON.stringify(b[k])),
  };
}

function PropsCell({ e }: { e: ManifestEntryDoc }) {
  const items = Object.entries(e.props);
  if (!items.length) return <span className="faint">none</span>;
  return (
    <div className="row wrap" style={{ gap: 4 }}>
      {items.map(([k, p]) => (
        <span key={k} className="badge" title={`${p.type}${p.required ? ", required" : ""}, ${p.source}`}>
          {k}{p.required ? "*" : ""}{p.source === "binding_only" ? " ⇢ data" : ""}
        </span>
      ))}
    </div>
  );
}

export default function ComponentsPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [view, setView] = useState<ManifestView | null>(null);
  const [open, setOpen] = useState<ManifestVersion | null>(null);
  const [json, setJson] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<null | "storybook" | "site">(null);

  const load = useCallback(() => Api.getManifest(id).then(setView)
    .catch(() => toast("Could not load the components", "err")), [id, toast]);
  useEffect(() => { load(); }, [load]);

  const show = (v: ManifestVersion) => {
    setOpen(v); setJson(JSON.stringify(v.data, null, 2)); setNotes(v.notes || "");
  };
  const openVersion = async (s: ManifestVersionSummary) => {
    try { show(await Api.getManifestVersion(id, s.version)); }
    catch { toast("Could not open that version", "err"); }
  };

  const parsedJson = (): Record<string, unknown> | null => {
    try {
      const d = JSON.parse(json);
      if (!d || typeof d !== "object" || Array.isArray(d)) throw new Error("not an object");
      return d;
    } catch {
      toast("The manifest isn't valid JSON (it must be an object)", "err");
      return null;
    }
  };

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setBusy(true);
    try { await fn(); toast(ok); await load(); }
    catch (e) { toast(e instanceof ApiError ? e.message : "Something went wrong", "err"); }
    finally { setBusy(false); }
  };

  const newDraft = () => run(async () => {
    const base = view?.active?.data ?? { include_defaults: true, components: [] };
    show(await Api.createManifestVersion(id, base, view?.active ? `Based on version ${view.active.version}` : ""));
  }, "Draft created");
  const saveDraft = () => {
    const data = parsedJson();
    if (!data || !open) return;
    run(async () => show(await Api.updateManifestDraft(id, open.version, data, notes)), "Draft saved");
  };
  const approve = () => open && run(async () => show(await Api.approveManifestVersion(id, open.version)),
    `Version ${open.version} approved — the agent uses it now`);
  const remove = () => open && run(async () => { await Api.deleteManifestDraft(id, open.version); setOpen(null); },
    "Draft deleted");

  const d = useMemo(() => (open ? diff(open.data, view?.active?.data) : null), [open, view]);

  if (!view) return <div className="skeleton" style={{ height: 320 }} />;
  const custom = view.effective.components.filter((c) => !c.id.startsWith("fb."));
  const builtIn = view.effective.components.length - custom.length;

  return (
    <div className="fade-in">
      <div className="row between page-head wrap" style={{ gap: 12 }}>
        <div>
          <h2>Components</h2>
          <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 700 }}>
            The building blocks the agent may compose pages from. Props marked <strong>⇢ data</strong> can only be
            filled from your APIs, never written by the model. Start from your Storybook or your live site, review,
            then have an Admin approve.
          </p>
        </div>
        <EditOnly>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn btn-ghost" onClick={() => setModal("site")} disabled={busy}>From live site</button>
            <button className="btn btn-ghost" onClick={() => setModal("storybook")} disabled={busy}>From Storybook</button>
            <button className="btn" onClick={newDraft} disabled={busy}>New draft</button>
          </div>
        </EditOnly>
      </div>

      <div className="card" style={{ marginBottom: 18 }}>
        <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
          <h3>In use now</h3>
          <span className="badge">
            {view.source === "console" ? `Approved version ${view.active_version}`
              : view.source === "file" ? "From a manifest file on the server" : "Built-in components only"}
          </span>
        </div>
        <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 10 }}>
          {custom.length} of your own component{custom.length === 1 ? "" : "s"}
          {builtIn ? ` + ${builtIn} built-in` : ""}.
          {view.effective.bundle && <> Bundle: <span className="mono">{view.effective.bundle.url}</span></>}
        </p>
        {custom.length > 0 && (
          <table className="table">
            <thead><tr><th>Component</th><th>Drawn by</th><th>Purpose</th><th>Props</th></tr></thead>
            <tbody>
              {custom.map((c) => (
                <tr key={c.id}>
                  <td className="mono" style={{ fontSize: "0.82rem" }}>{c.id}</td>
                  <td className="mono faint" style={{ fontSize: "0.78rem" }}>{c.renderer}</td>
                  <td className="muted" style={{ maxWidth: 280 }}>{c.purpose}</td>
                  <td><PropsCell e={c} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ padding: 0, marginBottom: 18 }}>
        {view.versions.length === 0 ? (
          <div className="empty">No versions yet. Create a draft, or generate one from Storybook or your site.</div>
        ) : (
          <table className="table">
            <thead><tr><th>Version</th><th>Status</th><th>Source</th><th>Components</th><th>Created</th><th>Approved</th><th></th></tr></thead>
            <tbody>
              {view.versions.map((v) => (
                <tr key={v.id} style={open?.version === v.version ? { background: "var(--bg-soft, rgba(127,127,127,0.08))" } : undefined}>
                  <td>v{v.version}</td>
                  <td><span className={STATUS_BADGE[v.status]}>{v.status}</span></td>
                  <td className="muted">{SOURCE_LABEL[v.source] || v.source}</td>
                  <td>{v.components ?? "—"}</td>
                  <td className="muted" style={{ fontSize: "0.82rem" }}>{fmtDate(v.created_at)}{v.created_by ? ` · ${v.created_by}` : ""}</td>
                  <td className="muted" style={{ fontSize: "0.82rem" }}>{v.approved_at ? `${fmtDate(v.approved_at)} · ${v.approved_by ?? ""}` : "—"}</td>
                  <td><button className="btn btn-ghost btn-sm" onClick={() => openVersion(v)}>Open</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {open && (
        <div className="card">
          <div className="row between wrap" style={{ gap: 8, marginBottom: 10 }}>
            <h3>Version {open.version} <span className={STATUS_BADGE[open.status]} style={{ marginLeft: 6 }}>{open.status}</span></h3>
            <button className="btn btn-ghost btn-sm" onClick={() => setOpen(null)}>Close</button>
          </div>

          {open.check.problems.length > 0 && (
            <div className="notice" style={{ marginBottom: 12 }}>
              <strong>Needs fixing before approval:</strong>
              <ul style={{ margin: "6px 0 0 18px" }}>{open.check.problems.map((p, i) => <li key={i}>{p}</li>)}</ul>
            </div>
          )}
          {d && view.active && open.status === "draft" && (
            <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 10 }}>
              Compared with approved v{view.active.version}:{" "}
              {d.added.length + d.removed.length + d.changed.length === 0 ? "no component changes." : (
                <>
                  {d.added.length > 0 && <span className="badge ok">+ {d.added.join(", ")}</span>}{" "}
                  {d.removed.length > 0 && <span className="badge err">− {d.removed.join(", ")}</span>}{" "}
                  {d.changed.length > 0 && <span className="badge accent">changed {d.changed.join(", ")}</span>}
                </>
              )}
            </p>
          )}

          {open.check.components.length > 0 && (
            <table className="table" style={{ marginBottom: 12 }}>
              <thead><tr><th>Component</th><th>Drawn by</th><th>Props</th></tr></thead>
              <tbody>
                {open.check.components.map((c) => (
                  <tr key={c.id}>
                    <td className="mono" style={{ fontSize: "0.82rem" }}>{c.id}</td>
                    <td className="mono faint" style={{ fontSize: "0.78rem" }}>{c.renderer}</td>
                    <td><PropsCell e={c} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="field">
            <label className="label" htmlFor="mf-notes">Notes</label>
            <input id="mf-notes" className="input" value={notes} readOnly={open.status !== "draft"}
              onChange={(e) => setNotes(e.target.value)} />
          </div>
          <div className="field">
            <label className="label" htmlFor="mf-json">Manifest JSON {open.status !== "draft" && <span className="faint">(read-only)</span>}</label>
            <textarea id="mf-json" className="textarea mono" style={{ minHeight: 320, fontSize: "0.78rem" }}
              value={json} readOnly={open.status !== "draft"} onChange={(e) => setJson(e.target.value)} spellCheck={false} />
          </div>

          {open.status === "draft" && (
            <EditOnly>
              <div className="row" style={{ gap: 8 }}>
                <button className="btn" onClick={saveDraft} disabled={busy}>{busy ? <Spinner /> : "Save draft"}</button>
                <EditOnly role="admin">
                  <button className="btn btn-primary" onClick={approve} disabled={busy || open.check.problems.length > 0}
                    title={open.check.problems.length ? "Fix the problems listed above first" : undefined}>
                    Approve and use
                  </button>
                </EditOnly>
                <button className="btn btn-ghost btn-danger" onClick={remove} disabled={busy}>Delete draft</button>
              </div>
              <p className="faint" style={{ fontSize: "0.78rem", marginTop: 8 }}>Save before approving. Only Admins can approve.</p>
            </EditOnly>
          )}
        </div>
      )}

      {modal === "storybook" && (
        <StorybookModal id={id} onClose={() => setModal(null)} onDone={async (v) => { setModal(null); await load(); show(v); }} />
      )}
      {modal === "site" && (
        <SiteModal id={id} onClose={() => setModal(null)} onDone={async (v) => { setModal(null); await load(); show(v); }} />
      )}
    </div>
  );
}

function StorybookModal({ id, onClose, onDone }: {
  id: string; onClose: () => void; onDone: (v: ManifestVersion) => void;
}) {
  const toast = useToast();
  const [url, setUrl] = useState("");
  const [index, setIndex] = useState("");
  const [docgen, setDocgen] = useState("");
  const [busy, setBusy] = useState(false);

  const go = async () => {
    let parsedIndex: unknown, parsedDocgen: unknown;
    try {
      parsedIndex = index.trim() ? JSON.parse(index) : undefined;
      parsedDocgen = docgen.trim() ? JSON.parse(docgen) : undefined;
    } catch { toast("Pasted JSON isn't valid", "err"); return; }
    if (!url.trim() && !parsedIndex) { toast("Give your Storybook's address or paste its index.json", "err"); return; }
    setBusy(true);
    try {
      const v = await Api.draftManifestFromStorybook(id, { url: url.trim() || undefined, index: parsedIndex, docgen: parsedDocgen });
      toast(`Draft v${v.version} created`); onDone(v);
    } catch (e) { toast(e instanceof ApiError ? e.message : "Could not read the Storybook", "err"); }
    finally { setBusy(false); }
  };

  return (
    <Modal open title="Draft from Storybook" onClose={onClose} width={620}>
      <p className="muted" style={{ fontSize: "0.85rem", marginBottom: 12 }}>
        Each story title becomes one of your components, drawn by your own Web Component. Add your bundle URL and its
        integrity hash to the draft before approving.
      </p>
      <div className="field">
        <label className="label" htmlFor="sb-url">Published Storybook address</label>
        <input id="sb-url" className="input" placeholder="https://storybook.example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
      </div>
      <div className="field">
        <label className="label" htmlFor="sb-index">…or paste its index.json <span className="faint">(optional)</span></label>
        <textarea id="sb-index" className="textarea mono" value={index} onChange={(e) => setIndex(e.target.value)} />
      </div>
      <div className="field">
        <label className="label" htmlFor="sb-docgen">react-docgen JSON for props <span className="faint">(optional)</span></label>
        <textarea id="sb-docgen" className="textarea mono" value={docgen} onChange={(e) => setDocgen(e.target.value)} />
      </div>
      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={go} disabled={busy}>{busy ? <Spinner /> : "Generate draft"}</button>
      </div>
    </Modal>
  );
}

function SiteModal({ id, onClose, onDone }: {
  id: string; onClose: () => void; onDone: (v: ManifestVersion) => void;
}) {
  const toast = useToast();
  const [url, setUrl] = useState("");
  const [pages, setPages] = useState(5);
  const [busy, setBusy] = useState(false);

  const go = async () => {
    setBusy(true);
    try {
      const v = await Api.draftManifestFromSite(id, { url: url.trim() || undefined, max_pages: pages });
      toast(`Draft v${v.version} created`); onDone(v);
    } catch (e) { toast(e instanceof ApiError ? e.message : "Could not read the site", "err"); }
    finally { setBusy(false); }
  };

  return (
    <Modal open title="Draft from your live site" onClose={onClose}>
      <p className="muted" style={{ fontSize: "0.85rem", marginBottom: 12 }}>
        Reads a few pages and maps the sections it recognises (hero, pricing, FAQ, testimonials…) onto FluidBuddha&apos;s
        built-in components, drawn in your design tokens.
      </p>
      <div className="field">
        <label className="label" htmlFor="site-url">Address <span className="faint">(defaults to the website&apos;s domain)</span></label>
        <input id="site-url" className="input" placeholder="https://www.example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
      </div>
      <div className="field">
        <label className="label" htmlFor="site-pages">Pages to read</label>
        <input id="site-pages" className="input" type="number" min={1} max={8} value={pages}
          onChange={(e) => setPages(Math.max(1, Math.min(8, Number(e.target.value) || 1)))} />
      </div>
      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={go} disabled={busy}>{busy ? <Spinner /> : "Generate draft"}</button>
      </div>
    </Modal>
  );
}
