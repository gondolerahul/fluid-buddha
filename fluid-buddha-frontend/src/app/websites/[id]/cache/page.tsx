"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Api, ApiError, CacheEntry } from "@/lib/api";
import { Modal, Spinner, fmtDate, useToast } from "@/components/ui";

export default function CachePage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [list, setList] = useState<CacheEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<CacheEntry | null>(null);

  const load = (q = search) =>
    Api.listCache(id, { search: q || undefined, limit: 100 })
      .then((r) => { setList(r.items); setTotal(r.total); })
      .catch(() => setList([]));
  useEffect(() => { load(""); }, [id]);

  const remove = async (eid: string) => {
    try { await Api.deleteCache(id, eid); load(); toast("Deleted"); }
    catch { toast("Could not delete", "err"); }
  };

  return (
    <div className="fade-in">
      <div className="row between page-head wrap" style={{ gap: 12 }}>
        <div>
          <h2>Cached responses</h2>
          <p className="muted" style={{ fontSize: "0.88rem" }}>
            Answers &amp; actions the agent replays. Edit them to curate exactly what visitors hear —
            saved straight back to the cache.
          </p>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); load(); }} className="row" style={{ gap: 8 }}>
          <input className="input" placeholder="Search questions / answers…" value={search}
            onChange={(e) => setSearch(e.target.value)} style={{ width: 260 }} />
          <button className="btn">Search</button>
        </form>
      </div>

      <div className="row between" style={{ marginBottom: 14 }}>
        <span className="muted" style={{ fontSize: "0.85rem" }}>{total} cached turn{total === 1 ? "" : "s"}</span>
        <div className="legend">
          <span><span className="dot" style={{ display: "inline-block", color: "var(--ok)" }} /> served from cache</span>
          <span><span className="dot" style={{ display: "inline-block", color: "var(--text-faint)" }} /> not yet replayed</span>
        </div>
      </div>

      {list === null ? (
        <div className="skeleton" style={{ height: 200 }} />
      ) : list.length === 0 ? (
        <div className="empty">No cached responses yet. They appear as visitors talk to the agent.</div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <table className="table">
            <thead>
              <tr><th>Question</th><th>Answer</th><th>Actions</th><th>Served</th><th>Recorded</th><th></th></tr>
            </thead>
            <tbody>
              {list.map((e) => (
                <tr key={e.id}>
                  <td style={{ maxWidth: 260 }}>
                    <div style={{ fontWeight: 500 }}>{e.question}</div>
                    <div className="row" style={{ gap: 6, marginTop: 5 }}>
                      {e.persona && <span className="badge">{e.persona}</span>}
                      {e.channel && <span className="badge">{e.channel}</span>}
                    </div>
                  </td>
                  <td className="muted" style={{ maxWidth: 320 }}>{e.answer_text}</td>
                  <td className="mono faint" style={{ fontSize: "0.78rem" }}>
                    {e.actions.length ? e.actions.map((a, i) => <div key={i}>{(a as any).type}</div>) : "—"}
                  </td>
                  <td>
                    {e.hit_count > 0 ? (
                      <span className="badge ok"><span className="dot" /> {e.hit_count}× cached</span>
                    ) : (
                      <span className="badge"><span className="dot" /> generated</span>
                    )}
                  </td>
                  <td className="muted" style={{ fontSize: "0.82rem" }}>{fmtDate(e.created_at)}</td>
                  <td>
                    <div className="row" style={{ gap: 4 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => setEditing(e)}>Edit</button>
                      <button className="btn btn-ghost btn-sm btn-danger" onClick={() => remove(e.id)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <EditModal id={id} entry={editing} onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); load(); toast("Saved to cache"); }}
        onError={(m) => toast(m, "err")} />
    </div>
  );
}

function EditModal({
  id, entry, onClose, onSaved, onError,
}: {
  id: string; entry: CacheEntry | null; onClose: () => void; onSaved: () => void; onError: (m: string) => void;
}) {
  const [answer, setAnswer] = useState("");
  const [actions, setActions] = useState("[]");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (entry) {
      setAnswer(entry.answer_text);
      setActions(JSON.stringify(entry.actions, null, 2));
    }
  }, [entry]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    let parsed: Record<string, unknown>[];
    try {
      parsed = JSON.parse(actions);
      if (!Array.isArray(parsed)) throw new Error();
    } catch {
      onError("Actions must be a valid JSON array.");
      return;
    }
    setBusy(true);
    try {
      await Api.updateCache(id, entry!.id, { answer_text: answer, actions: parsed });
      onSaved();
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={!!entry} onClose={onClose} title="Edit cached response" width={620}>
      {entry && (
        <form onSubmit={submit} className="stack">
          <div className="field">
            <label className="label">Question</label>
            <input className="input" value={entry.question} disabled />
          </div>
          <div className="field">
            <label className="label">Answer <span className="faint">(spoken / shown)</span></label>
            <textarea className="textarea" value={answer} rows={4} onChange={(e) => setAnswer(e.target.value)} />
          </div>
          <div className="field">
            <label className="label">Actions <span className="faint">(JSON — navigate / scroll_to / set_icp)</span></label>
            <textarea className="textarea mono" value={actions} rows={5}
              onChange={(e) => setActions(e.target.value)} style={{ fontSize: "0.82rem" }} />
          </div>
          <div className="row" style={{ justifyContent: "flex-end", gap: 10 }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save to cache"}</button>
          </div>
        </form>
      )}
    </Modal>
  );
}
