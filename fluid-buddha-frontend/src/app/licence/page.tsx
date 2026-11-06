"use client";
import { useEffect, useState } from "react";
import { useRequireAuth } from "@/lib/auth";
import { Api, ApiError, LicenceState } from "@/lib/api";
import { AppHeader } from "@/components/Chrome";
import { LoadingScreen, Spinner, fmtDate, useToast } from "@/components/ui";

const STATE: Record<string, { label: string; cls: string }> = {
  valid: { label: "Valid", cls: "ok" }, expiring: { label: "Expiring soon", cls: "warn" },
  grace: { label: "Expired — in grace period", cls: "warn" }, expired: { label: "Expired", cls: "err" },
  missing: { label: "None installed", cls: "err" }, invalid: { label: "Invalid", cls: "err" },
};
const SOURCE: Record<string, string> = { console: "installed here", env: "from LICENCE_KEY", file: "from LICENCE_FILE" };

/** A self-hosted install's licence (M3-5): what it covers; the Owner installs a new one. */
export default function LicencePage() {
  const auth = useRequireAuth();
  const toast = useToast();
  const [st, setSt] = useState<LicenceState | null>(null);
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (auth.tenant) Api.licence().then(setSt).catch(() => {}); }, [auth.tenant]);
  if (auth.loading || !auth.tenant) return <LoadingScreen />;
  const owner = auth.can("owner");

  const install = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      setSt(await Api.installLicence(key));
      setKey("");
      window.dispatchEvent(new Event("fluidbuddha:licence"));
      toast("Licence installed");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not install it", "err");
    } finally {
      setBusy(false);
    }
  };

  const lic = st?.licence;
  const s = STATE[st?.state || "missing"];
  return (
    <>
      <AppHeader />
      <main className="content stack" style={{ margin: "0 auto", maxWidth: 760 }}>
        <div className="page-head">
          <h1 className="h-page">Licence</h1>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            This install&apos;s FluidBuddha licence, checked offline. If it lapses, the console turns read-only after the
            grace period; your visitors are never affected.
          </p>
        </div>
        {!st ? <div className="skeleton" style={{ height: 160 }} /> : !st.self_hosted ? (
          <div className="notice">This is the hosted service: there&apos;s no licence to manage.</div>
        ) : (
          <>
            <section className="card stack-sm">
              <div className="row between">
                <strong>Status</strong>
                <span className={`badge ${s.cls}`}>{s.label}</span>
              </div>
              {lic ? (
                <table className="table">
                  <tbody>
                    <tr><td>Licensed to</td><td>{lic.customer}</td></tr>
                    <tr><td>Expires</td><td>{fmtDate(lic.expires_at)}{typeof st.days_left === "number" && st.days_left >= 0
                      ? ` · ${st.days_left} day${st.days_left === 1 ? "" : "s"} left` : ""}
                      {st.state === "grace" && st.grace_until ? ` · grace until ${fmtDate(st.grace_until)}` : ""}</td></tr>
                    <tr><td>Websites</td><td className="mono">{st.usage?.sites ?? 0} of {lic.sites}</td></tr>
                    <tr><td>Team seats</td><td className="mono">{st.usage?.seats ?? 0} of {lic.seats}</td></tr>
                    <tr><td>Features</td><td>{lic.features.join(", ")}</td></tr>
                    <tr><td>Licence id</td><td className="mono">{lic.lid}{st.source ? ` · ${SOURCE[st.source] || st.source}` : ""}</td></tr>
                  </tbody>
                </table>
              ) : (
                <p className="faint" style={{ fontSize: "0.86rem" }}>
                  {st.state === "invalid" ? "The configured licence key doesn't verify." : "No licence is installed."}
                </p>
              )}
            </section>
            <section className="card stack-sm">
              <strong>Install a licence</strong>
              {owner ? (
                <form className="stack-sm" onSubmit={install}>
                  <textarea className="input mono" rows={4} required value={key} onChange={(e) => setKey(e.target.value)}
                    placeholder="FBL1.…" style={{ fontSize: "0.8rem" }} />
                  <div className="row" style={{ justifyContent: "flex-end" }}>
                    <button className="btn btn-primary" disabled={busy || key.trim().length < 10}>{busy ? <Spinner /> : "Install"}</button>
                  </div>
                  <p className="faint" style={{ fontSize: "0.8rem" }}>It replaces the current one straight away.</p>
                </form>
              ) : <p className="faint" style={{ fontSize: "0.86rem" }}>Only the account Owner can install a licence.</p>}
            </section>
          </>
        )}
      </main>
    </>
  );
}
