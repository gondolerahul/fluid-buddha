"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Api, ApiError, IngestionStatus } from "@/lib/api";
import { Spinner, StatusBadge, fmtDate, useToast } from "@/components/ui";
import { AddSourceModal } from "@/components/AddSourceModal";
import { CrawlCard } from "@/components/CrawlCard";
import { EditOnly } from "@/components/Permission";

export default function IngestionPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [data, setData] = useState<IngestionStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => Api.ingestion(id).then(setData).catch(() => {}), [id]);
  useEffect(() => { load(); }, [load]);

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
      <EditOnly><CrawlCard id={id} onIngested={load} /></EditOnly>

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
          <EditOnly>
            <button className="btn btn-primary" disabled={running || pending === 0} onClick={run}>
              {running ? <Spinner /> : "Run ingestion"}
            </button>
          </EditOnly>
        </div>
      </div>

      <div className="card">
        <div className="row between" style={{ marginBottom: 16 }}>
          <div>
            <h2>Data sources</h2>
            <p className="muted" style={{ fontSize: "0.86rem" }}>
              Add the content the agent should know: PDFs, Word documents, text or single pages.
            </p>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <input ref={fileRef} type="file" hidden accept=".pdf,.docx,.txt,.md,.markdown,.html,.csv,.json"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
            <EditOnly>
              <button className="btn" onClick={() => fileRef.current?.click()}>Upload file</button>
              <button className="btn btn-primary" onClick={() => setOpen(true)}>+ Add text / URL</button>
            </EditOnly>
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
                  <td><EditOnly><button className="btn btn-ghost btn-sm btn-danger" onClick={() => remove(s.id)}>Delete</button></EditOnly></td>
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
