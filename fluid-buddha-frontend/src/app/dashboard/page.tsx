"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/lib/auth";
import { Api, ApiError, Website } from "@/lib/api";
import { AppHeader } from "@/components/Chrome";
import { LoadingScreen, Modal, Spinner, StatusBadge, fmtDate, useToast } from "@/components/ui";

export default function Dashboard() {
  const auth = useRequireAuth();
  const toast = useToast();
  const [sites, setSites] = useState<Website[] | null>(null);
  const [open, setOpen] = useState(false);

  const load = () => Api.listWebsites().then(setSites).catch(() => setSites([]));
  useEffect(() => {
    if (auth.tenant) load();
  }, [auth.tenant]);

  if (auth.loading || !auth.tenant) return <LoadingScreen />;

  return (
    <>
      <AppHeader />
      <main className="content" style={{ margin: "0 auto" }}>
        <div className="row between page-head">
          <div>
            <h1 className="h-page">Your websites</h1>
            <p className="muted">Each website runs a Fluid-Buddha voice agent you control here.</p>
          </div>
          <button className="btn btn-primary" onClick={() => setOpen(true)}>+ Add website</button>
        </div>

        {sites === null ? (
          <div className="grid grid-3">
            {[0, 1, 2].map((i) => <div key={i} className="skeleton" style={{ height: 150 }} />)}
          </div>
        ) : sites.length === 0 ? (
          <div className="empty">
            <p style={{ marginBottom: 14 }}>No websites yet.</p>
            <button className="btn btn-primary" onClick={() => setOpen(true)}>Add your first website</button>
          </div>
        ) : (
          <div className="grid grid-3 fade-in">
            {sites.map((s) => (
              <Link key={s.id} href={`/websites/${s.id}/analytics`} className="card card-pad-sm"
                style={{ display: "block", transition: "border-color .18s, transform .12s" }}>
                <div className="row between" style={{ marginBottom: 12 }}>
                  <h3>{s.name}</h3>
                  <StatusBadge status={s.status} />
                </div>
                <p className="muted mono" style={{ fontSize: "0.8rem", marginBottom: 14 }}>
                  {s.domain || s.site_key}
                </p>
                <div className="row wrap" style={{ gap: 6 }}>
                  <span className="badge accent">{s.intelligence}</span>
                  <span className="badge">{s.design}</span>
                </div>
                <p className="faint" style={{ fontSize: "0.78rem", marginTop: 14 }}>
                  Added {fmtDate(s.created_at)}
                </p>
              </Link>
            ))}
          </div>
        )}
      </main>

      <AddWebsiteModal open={open} onClose={() => setOpen(false)} onCreated={() => { setOpen(false); load(); toast("Website added"); }} onError={(m) => toast(m, "err")} />
    </>
  );
}

function AddWebsiteModal({
  open, onClose, onCreated, onError,
}: {
  open: boolean; onClose: () => void; onCreated: () => void; onError: (m: string) => void;
}) {
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [intelligence, setIntelligence] = useState("advance");
  const [design, setDesign] = useState("level1");
  const [accent, setAccent] = useState("#ffd23f");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await Api.createWebsite({ name, domain: domain || null, intelligence, design, accent });
      setName(""); setDomain("");
      onCreated();
    } catch (e) {
      onError(e instanceof ApiError ? e.message : "Could not create website.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Add a website">
      <form onSubmit={submit} className="stack">
        <div className="field">
          <label className="label">Name</label>
          <input className="input" required value={name} onChange={(e) => setName(e.target.value)}
            placeholder="Acme Store" />
        </div>
        <div className="field">
          <label className="label">Domain <span className="faint">(optional)</span></label>
          <input className="input" value={domain} onChange={(e) => setDomain(e.target.value)}
            placeholder="store.acme.com" />
        </div>
        <div className="grid grid-2" style={{ gap: 14 }}>
          <div className="field">
            <label className="label">Intelligence</label>
            <select className="select" value={intelligence} onChange={(e) => setIntelligence(e.target.value)}>
              <option value="basic">basic</option>
              <option value="high">high</option>
              <option value="advance">advance</option>
              <option value="extreme">extreme</option>
            </select>
          </div>
          <div className="field">
            <label className="label">Design</label>
            <select className="select" value={design} onChange={(e) => setDesign(e.target.value)}>
              <option value="level1">level1 — panel</option>
              <option value="level2">level2 — particle</option>
              <option value="level3">level3 — atmosphere</option>
            </select>
          </div>
        </div>
        <div className="field">
          <label className="label">Accent color</label>
          <div className="row">
            <input type="color" value={accent} onChange={(e) => setAccent(e.target.value)}
              style={{ width: 44, height: 38, border: "1px solid var(--line-strong)", borderRadius: 8, background: "none" }} />
            <input className="input mono" value={accent} onChange={(e) => setAccent(e.target.value)} />
          </div>
        </div>
        <div className="row" style={{ justifyContent: "flex-end", gap: 10, marginTop: 6 }}>
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !name}>
            {busy ? <Spinner /> : "Create website"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
