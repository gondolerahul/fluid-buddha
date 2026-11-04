"use client";
import { useCallback, useEffect, useState } from "react";
import { useRequireAuth } from "@/lib/auth";
import { Api, ApiError, AuditEvent } from "@/lib/api";
import { AppHeader } from "@/components/Chrome";
import { LoadingScreen, Spinner, useToast } from "@/components/ui";

/** Plain-language names for the most common actions; others show as-is. */
const LABELS: Record<string, string> = {
  "account.register": "Created the account",
  login: "Signed in",
  "login.failed": "Failed sign-in",
  "invitation.accept": "Joined from an invitation",
  create_invitation: "Invited someone",
  change_role: "Changed a role",
  remove_member: "Removed someone",
  create_website: "Created a website",
  update_website: "Changed website settings",
  delete_website: "Deleted a website",
  update_profile: "Changed the agent profile",
  put_integrations: "Changed integrations",
  put_sso: "Changed single sign-on",
};

export default function AuditPage() {
  const auth = useRequireAuth();
  const toast = useToast();
  const [rows, setRows] = useState<AuditEvent[] | null>(null);
  const [more, setMore] = useState(false);
  const [filter, setFilter] = useState({ action: "", actor: "" });
  const [busy, setBusy] = useState(false);

  const query = useCallback((before?: number) =>
    Api.audit({ before, action: filter.action || undefined, actor: filter.actor || undefined }), [filter]);

  useEffect(() => {
    if (!auth.tenant) return;
    let live = true;
    query().then((page) => {
      if (!live) return;
      setMore(page.length === 100);
      setRows(page);
    }).catch(() => { if (live) setRows([]); });
    return () => { live = false; };
  }, [auth.tenant, query]);

  const loadMore = async (before: number) => {
    const page = await query(before);
    setMore(page.length === 100);
    setRows((prev) => [...(prev ?? []), ...page]);
  };

  if (auth.loading || !auth.tenant) return <LoadingScreen />;

  const exportCsv = async () => {
    setBusy(true);
    try {
      const blob = await Api.auditCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "audit-log.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Export failed", "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <AppHeader />
      <main className="content stack" style={{ margin: "0 auto" }}>
        <div className="row between wrap page-head" style={{ gap: 12 }}>
          <div>
            <h1 className="h-page">Audit log</h1>
            <p className="muted" style={{ fontSize: "0.9rem" }}>
              Every change and sign-in in this account, newest first. Kept for a year.
            </p>
          </div>
          <button className="btn btn-sm" onClick={exportCsv} disabled={busy}>
            {busy ? <Spinner /> : "Export CSV"}</button>
        </div>
        {!auth.can("admin") ? <div className="notice">Only Admins and Owners can see the audit log.</div> : (
          <section className="card">
            <form className="row wrap" style={{ gap: 10, marginBottom: 14 }}
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                setFilter({ action: String(f.get("action") || ""), actor: String(f.get("actor") || "") });
              }}>
              <input className="input" name="action" placeholder="Action contains…" aria-label="Filter by action"
                defaultValue={filter.action} style={{ maxWidth: 220 }} />
              <input className="input" name="actor" placeholder="Person contains…" aria-label="Filter by person"
                defaultValue={filter.actor} style={{ maxWidth: 260 }} />
              <button className="btn btn-sm">Filter</button>
            </form>
            {!rows ? <div className="skeleton" style={{ height: 200 }} /> : rows.length === 0 ? (
              <div className="empty">Nothing recorded yet.</div>
            ) : (
              <table className="table">
                <thead><tr><th>When</th><th>Who</th><th>What</th><th>On</th><th>From</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id}>
                      <td className="faint" style={{ whiteSpace: "nowrap" }}>{new Date(r.at).toLocaleString()}</td>
                      <td>{r.actor_email ?? "—"}</td>
                      <td>
                        {LABELS[r.action] ?? r.action}
                        {typeof r.details?.method === "string" && r.action === "login" &&
                          <span className="faint"> ({String(r.details.method)})</span>}
                      </td>
                      <td className="mono faint" style={{ fontSize: "0.78rem" }}>
                        {r.target_type ? `${r.target_type} ${r.target_id?.slice(0, 8) ?? ""}` : "—"}
                      </td>
                      <td className="faint" style={{ fontSize: "0.8rem" }}>{r.ip ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {more && rows && (
              <div className="row" style={{ justifyContent: "center", marginTop: 12 }}>
                <button className="btn btn-sm" onClick={() => loadMore(rows[rows.length - 1].id)}>Load more</button>
              </div>
            )}
          </section>
        )}
      </main>
    </>
  );
}
