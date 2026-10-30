"use client";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Api, ApiError, IngestionStatus } from "@/lib/api";
import { Modal, Spinner, StatusBadge, fmtDate, useToast } from "@/components/ui";

export default function IngestionPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [data, setData] = useState<IngestionStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => Api.ingestion(id).then(setData).catch(() => {});
  useEffect(() => { load(); }, [id]);

  const run = async () => {
    setRunning(true);
    try {
      const r = await Api.runIngestion(id);
      toast(r.status === "noop" ? "Nothing pending to ingest" : "Ingestion started");
      // poll a few times for status to settle
      for (let i = 0; i < 6; i++) {
        await new Promise((res) => setTimeout(res, 1200));
        await load();
      }
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Ingestion failed", "err");
    } finally {
      setRunning(false);
    }
  };

  const upload = async (file: File) => {
    try {
      await Api.uploadSource(id, file);
      toast(`Uploaded ${file.name}`);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Upload failed", "err");
    }
  };

  const remove = async (sid: string) => {
    try {
      await Api.deleteSource(id, sid);
      load();
    } catch {
      toast("Could not delete source", "err");
    }
  };

  const counts = data?.counts || {};
  const pending = counts.pending || 0;

  return (
    <div className="fade-in">
      <div className="grid grid-3" style={{ marginBottom: 22 }}>
        <Stat label="Knowledge nodes" value={data ? String(data.document_count) : "—"} hint="Ingested into the agent's memory" />
        <Stat label="Sources" value={data ? String(data.sources.length) : "—"} hint={`${pending} pending`} />
        <div className="card card-pad-sm row between">
          <div>
            <div className="eyebrow">Actions</div>
            <p className="muted" style={{ fontSize: "0.84rem", marginTop: 6 }}>
              {pending > 0 ? `${pending} source${pending > 1 ? "s" : ""} ready to ingest` : "All sources ingested"}
            </p>
          </div>
          <button className="btn btn-primary" disabled={running || pending === 0} onClick={run}>
            {running ? <Spinner /> : "Run ingestion"}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="row between" style={{ marginBottom: 16 }}>
          <div>
            <h2>Data sources</h2>
            <p className="muted" style={{ fontSize: "0.86rem" }}>
              Add the content the agent should know. Missing something? Add it here.
            </p>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <input ref={fileRef} type="file" hidden accept=".txt,.md,.markdown,.html,.csv,.json"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
            <button className="btn" onClick={() => fileRef.current?.click()}>Upload file</button>
            <button className="btn btn-primary" onClick={() => setOpen(true)}>+ Add text / URL</button>
          </div>
        </div>

        {!data ? (
          <div className="skeleton" style={{ height: 120 }} />
        ) : data.sources.length === 0 ? (
          <div className="empty">No sources yet. Upload a file or paste text/URL to begin.</div>
        ) : (
          <table className="table">
            <thead>
              <tr><th>Name</th><th>Type</th><th>Status</th><th>Nodes</th><th>Added</th><th></th></tr>
            </thead>
            <tbody>
              {data.sources.map((s) => (
                <tr key={s.id}>
                  <td>
                    <div style={{ fontWeight: 500 }}>{s.name}</div>
                    <div className="faint" style={{ fontSize: "0.78rem", maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.preview}
                    </div>
                    {s.error && <div className="badge err" style={{ marginTop: 4 }}>{s.error}</div>}
                  </td>
                  <td><span className="badge">{s.kind}</span></td>
                  <td><StatusBadge status={s.status} /></td>
                  <td className="mono">{s.nodes || "—"}</td>
                  <td className="muted" style={{ fontSize: "0.82rem" }}>{fmtDate(s.created_at)}</td>
                  <td><button className="btn btn-ghost btn-sm btn-danger" onClick={() => remove(s.id)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <AddSourceModal id={id} open={open} onClose={() => setOpen(false)}
        onAdded={() => { setOpen(false); load(); toast("Source added"); }}
        onError={(m) => toast(m, "err")} />
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card card-pad-sm">
      <div className="eyebrow">{label}</div>
      <div className="metric" style={{ marginTop: 8 }}>{value}</div>
      {hint && <div className="faint" style={{ fontSize: "0.8rem", marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

function AddSourceModal({
  id, open, onClose, onAdded, onError,
}: {
  id: string; open: boolean; onClose: () => void; onAdded: () => void; onError: (m: string) => void;
}) {
  const [kind, setKind] = useState<"text" | "url">("text");
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await Api.addSource(id, { kind, name, content });
      setName(""); setContent("");
      onAdded();
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Could not add source.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Add a data source">
      <form onSubmit={submit} className="stack">
        <div className="field">
          <label className="label">Type</label>
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value as "text" | "url")}>
            <option value="text">Pasted text</option>
            <option value="url">URL to crawl</option>
          </select>
        </div>
        <div className="field">
          <label className="label">Name</label>
          <input className="input" required value={name} onChange={(e) => setName(e.target.value)}
            placeholder={kind === "url" ? "Pricing page" : "FAQ snippet"} />
        </div>
        <div className="field">
          <label className="label">{kind === "url" ? "URL" : "Content"}</label>
          {kind === "url" ? (
            <input className="input" required value={content} onChange={(e) => setContent(e.target.value)}
              placeholder="https://example.com/pricing" />
          ) : (
            <textarea className="textarea" required value={content} onChange={(e) => setContent(e.target.value)}
              placeholder="Paste the information the agent should know…" rows={6} />
          )}
        </div>
        <div className="row" style={{ justifyContent: "flex-end", gap: 10, marginTop: 6 }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !name || !content}>
            {busy ? <Spinner /> : "Add source"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
