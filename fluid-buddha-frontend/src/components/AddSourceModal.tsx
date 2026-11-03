"use client";
import { useState } from "react";
import { Api, ApiError } from "@/lib/api";
import { Modal, Spinner } from "@/components/ui";

/** Add a text or URL source. Used by the Ingestion tab and, pre-filled with the
 *  unanswered question, by the Insights knowledge-gap list. Remount it (via
 *  `key`) to change the pre-filled values. */
export function AddSourceModal({
  id, open, onClose, onAdded, onError, title = "Add a data source",
  initialName = "", contentHint, submitLabel = "Add source",
}: {
  id: string; open: boolean; onClose: () => void; onAdded: () => void; onError: (m: string) => void;
  title?: string; initialName?: string; contentHint?: string; submitLabel?: string;
}) {
  const [kind, setKind] = useState<"text" | "url">("text");
  const [name, setName] = useState(initialName);
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
    <Modal open={open} onClose={onClose} title={title}>
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
              placeholder={contentHint || "Paste the information the agent should know…"} rows={6} />
          )}
        </div>
        <div className="row" style={{ justifyContent: "flex-end", gap: 10, marginTop: 6 }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !name || !content}>
            {busy ? <Spinner /> : submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  );
}
