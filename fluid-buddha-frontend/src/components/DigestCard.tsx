"use client";
// Weekly digest settings (M2-5): who gets the Monday summary, in which time
// zone, a preview, and a test send to yourself.
import { useEffect, useState } from "react";
import { Api, ApiError, DigestPreview, DigestSettings } from "@/lib/api";
import { Modal, Spinner, useToast } from "@/components/ui";

const ZONES = ["Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Europe/London", "Europe/Berlin",
  "America/New_York", "America/Chicago", "America/Los_Angeles", "Australia/Sydney", "UTC"];

export function DigestCard() {
  const [cfg, setCfg] = useState<DigestSettings | null>(null);
  useEffect(() => { Api.digest().then(setCfg).catch(() => {}); }, []);
  return (
    <section className="card stack">
      <div>
        <h3>Weekly digest</h3>
        <p className="faint" style={{ fontSize: "0.84rem", marginTop: 4 }}>
          Every Monday at 9:00: the week&apos;s conversations, leads, top questions, new gaps, objections,
          competitors, A/B test results and cost, across all your websites. Quiet weeks send nothing.
        </p>
      </div>
      {!cfg ? <div className="skeleton" style={{ height: 120 }} /> : <DigestForm key={JSON.stringify(cfg)} cfg={cfg} onSaved={setCfg} />}
    </section>
  );
}

function DigestForm({ cfg, onSaved }: { cfg: DigestSettings; onSaved: (c: DigestSettings) => void }) {
  const toast = useToast();
  const [enabled, setEnabled] = useState(cfg.enabled);
  const [list, setList] = useState(cfg.recipients.map((r) => r.email).join("\n"));
  const [tz, setTz] = useState(cfg.timezone);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<DigestPreview | null>(null);
  const unsub = new Set(cfg.recipients.filter((r) => r.unsubscribed).map((r) => r.email));
  const zones = ZONES.includes(tz) ? ZONES : [tz, ...ZONES];

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const saved = await Api.saveDigest({ enabled, timezone: tz,
        recipients: list.split(/[\n,]/).map((x) => x.trim()).filter(Boolean) });
      toast("Digest settings saved");
      onSaved(saved);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save", "err");
    } finally {
      setBusy(false);
    }
  };
  const test = async () => {
    try {
      const r = await Api.sendTestDigest();
      toast(`Sent to ${r.to}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not send", "err");
    }
  };

  return (
    <form className="stack" onSubmit={save}>
      <label className="row" style={{ gap: 8, fontSize: "0.9rem" }}>
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Send the weekly digest
      </label>
      <div className="grid grid-2" style={{ gap: 14 }}>
        <div className="field">
          <label className="label" htmlFor="dg-to">Recipients <span className="faint">(one per line)</span></label>
          <textarea id="dg-to" className="textarea" rows={4} value={list} onChange={(e) => setList(e.target.value)} />
          <p className="faint" style={{ fontSize: "0.76rem", marginTop: 4 }}>
            {cfg.chosen ? "" : "Until you choose, the account's Owners get it. "}
            Anyone who unsubscribes stays unsubscribed; only they can turn it back on, by adding themselves here.
          </p>
          {unsub.size > 0 && <p className="faint" style={{ fontSize: "0.78rem" }}>Unsubscribed: {[...unsub].join(", ")}</p>}
        </div>
        <div className="field">
          <label className="label" htmlFor="dg-tz">Time zone</label>
          <select id="dg-tz" className="select" value={tz} onChange={(e) => setTz(e.target.value)}>
            {zones.map((z) => <option key={z} value={z}>{z}</option>)}
          </select>
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 6 }}>
            Next one: {new Date(cfg.next_send).toLocaleString(undefined, { weekday: "long", day: "numeric",
              month: "short", hour: "2-digit", minute: "2-digit", timeZone: cfg.timezone })} ({cfg.timezone})
          </p>
        </div>
      </div>
      <div className="row wrap" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-ghost btn-sm"
          onClick={() => Api.previewDigest().then(setPreview).catch(() => toast("Could not build a preview", "err"))}>
          Preview this week</button>
        <button type="button" className="btn btn-sm" onClick={test}>Send me a test</button>
        <button className="btn btn-primary btn-sm" disabled={busy}>{busy ? <Spinner /> : "Save"}</button>
      </div>
      {preview && (
        <Modal open onClose={() => setPreview(null)} title={preview.subject} width={640}>
          <iframe title="Digest preview" srcDoc={preview.html} sandbox="allow-same-origin"
            style={{ width: "100%", height: 520, border: 0, borderRadius: 8, background: "#f5f5f2" }} />
        </Modal>
      )}
    </form>
  );
}
