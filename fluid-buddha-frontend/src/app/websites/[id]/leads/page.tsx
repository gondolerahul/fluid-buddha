"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Api, ApiError, Lead, LeadStatus, Recap } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Modal, fmtDate, useToast } from "@/components/ui";
import { TranscriptModal } from "@/components/TranscriptModal";

const STATUSES: LeadStatus[] = ["new", "contacted", "qualified", "won", "lost"];

function scoreBadge(score: number): string {
  return score >= 70 ? "badge ok" : score >= 40 ? "badge warn" : "badge";
}

export default function LeadsPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [open, setOpen] = useState<Lead | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);

  const load = useCallback(() => {
    Api.leads(id).then((r) => setLeads(r.items)).catch(() => setLeads([]));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const setStatus = async (lead: Lead, status: LeadStatus) => {
    try {
      const updated = await Api.updateLead(id, lead.id, status);
      setLeads((ls) => ls?.map((l) => (l.id === updated.id ? updated : l)) ?? null);
      setOpen((o) => (o?.id === updated.id ? updated : o));
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not update the lead", "err");
    }
  };

  return (
    <div className="fade-in">
      <div className="row between page-head wrap" style={{ gap: 12 }}>
        <div>
          <h2>Leads</h2>
          <p className="muted" style={{ fontSize: "0.88rem" }}>
            Visitors who left their details — from the enquiry form or mid-conversation.
          </p>
        </div>
        <Link href={`/websites/${id}/settings#integrations`} className="btn btn-sm">
          Send leads to your CRM or Slack
        </Link>
      </div>

      <div className="card">
        {leads === null ? <div className="skeleton" style={{ height: 200 }} />
          : leads.length === 0 ? (
            <div className="empty">
              No leads yet. They appear here when a visitor shares their email with the agent
              or submits a form it shows.
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr><th>Score</th><th>Contact</th><th>Company</th><th>Source</th><th>Status</th><th>Received</th><th /></tr>
              </thead>
              <tbody>
                {leads.map((l) => (
                  <tr key={l.id}>
                    <td><span className={scoreBadge(l.score)}>{l.score}</span></td>
                    <td>
                      <div>{l.name || "—"}</div>
                      <div className="faint mono" style={{ fontSize: "0.8rem" }}>{l.email}</div>
                    </td>
                    <td>{l.company || "—"}</td>
                    <td>
                      {l.source}
                      {l.paid_at && <div><span className="badge ok">paid{l.paid_amount
                        ? ` ₹${(l.paid_amount / 100).toLocaleString("en-IN")}` : ""}</span></div>}
                      {l.recap && <div className="faint" style={{ fontSize: "0.78rem" }}>
                        recap: {l.recap.views} view{l.recap.views === 1 ? "" : "s"}
                        {l.recap.forwards ? `, ${l.recap.forwards} forward${l.recap.forwards === 1 ? "" : "s"}` : ""}</div>}
                    </td>
                    <td>
                      <select className="select" value={l.status} aria-label="Lead status"
                        onChange={(e) => setStatus(l, e.target.value as LeadStatus)}>
                        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                    <td className="faint">{fmtDate(l.created_at)}</td>
                    <td><button className="btn btn-ghost btn-sm" onClick={() => setOpen(l)}>Details</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>

      {open && (
        <Modal open onClose={() => setOpen(null)} title={open.name || open.email}>
          <div className="stack">
            <div className="row" style={{ gap: 8 }}>
              <span className={scoreBadge(open.score)}>Score {open.score}</span>
              <span className="badge">{open.source}</span>
              {open.persona && <span className="badge info">{open.persona}</span>}
            </div>
            <div className="stack-sm">
              <div><span className="eyebrow">Email</span><div className="mono">{open.email}</div></div>
              {open.company && <div><span className="eyebrow">Company</span><div>{open.company}</div></div>}
              {open.phone && <div><span className="eyebrow">Phone</span><div>{open.phone}</div></div>}
              {open.summary && <div><span className="eyebrow">Summary</span><div className="muted">{open.summary}</div></div>}
              {open.message && <div><span className="eyebrow">Message</span><div style={{ whiteSpace: "pre-wrap" }}>{open.message}</div></div>}
              {open.recap && <div><span className="eyebrow">Recap</span><div>
                Opened {open.recap.views} time{open.recap.views === 1 ? "" : "s"}
                {open.recap.forwards ? `, forwarded to ${open.recap.forwards} more ${open.recap.forwards === 1 ? "person" : "people"}` : ""}
                {open.recap.last_viewed_at ? ` · last ${fmtDate(open.recap.last_viewed_at)}` : ""}</div></div>}
            </div>
            <div className="faint" style={{ fontSize: "0.8rem" }}>
              {open.delivery_error ? `Delivery failed: ${open.delivery_error}`
                : open.delivered_at ? `Sent to your integrations ${fmtDate(open.delivered_at)}`
                : "Not sent anywhere — no integration configured."}
            </div>
            {open.conversation_id && (
              <button className="btn btn-sm" style={{ alignSelf: "flex-start" }}
                onClick={() => { setTranscript(open.conversation_id); setOpen(null); }}>
                View conversation
              </button>
            )}
          </div>
        </Modal>
      )}
      <RecapsCard id={id} onOpen={setTranscript} />
      {transcript && <TranscriptModal id={id} cid={transcript} onClose={() => setTranscript(null)} />}
    </div>
  );
}

/** Shared recaps (M2-6): links visitors made, with views and forwards. */
function RecapsCard({ id, onOpen }: { id: string; onOpen: (cid: string) => void }) {
  const toast = useToast();
  const { can } = useAuth();
  const [items, setItems] = useState<Recap[] | null>(null);
  const load = useCallback(() => {
    Api.recaps(id).then((r) => setItems(r.recaps)).catch(() => setItems([]));
  }, [id]);
  useEffect(() => { load(); }, [load]);
  const revoke = async (r: Recap) => {
    if (!window.confirm("Take this recap link down? Anyone who has it will see that it's no longer available.")) return;
    try { await Api.revokeRecap(id, r.id); toast("Recap link taken down"); load(); }
    catch { toast("Could not take it down", "err"); }
  };
  return (
    <div className="card" style={{ marginTop: 20 }}>
      <h3 style={{ marginBottom: 4 }}>Shared recaps</h3>
      <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 14 }}>
        When a visitor types &ldquo;send me this&rdquo;, they get a link to a recap of the conversation they can
        forward to their team. Each new person who opens it is counted as a forward and raises the lead&apos;s score.
      </p>
      {items === null ? <div className="skeleton" style={{ height: 100 }} />
        : items.length === 0 ? <div className="empty">No recaps yet.</div> : (
          <table className="table">
            <thead><tr><th>Recap</th><th>Lead</th><th>Views</th><th>Forwards</th><th>Last opened</th><th /></tr></thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} style={{ opacity: r.expired ? 0.55 : 1 }}>
                  <td style={{ maxWidth: 320 }}>
                    <div style={{ fontSize: "0.86rem" }}>{r.summary || "—"}</div>
                    <div className="faint" style={{ fontSize: "0.76rem" }}>
                      {r.expired ? "expired" : `works until ${fmtDate(r.expires_at)}`}</div>
                  </td>
                  <td className="mono" style={{ fontSize: "0.82rem" }}>{r.lead_email || "—"}</td>
                  <td className="mono">{r.views}</td>
                  <td className="mono">{r.forwards}</td>
                  <td className="faint">{r.last_viewed_at ? fmtDate(r.last_viewed_at) : "—"}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {!r.expired && <a className="btn btn-ghost btn-sm" href={r.url} target="_blank" rel="noopener noreferrer">Open</a>}
                    <button className="btn btn-ghost btn-sm" onClick={() => onOpen(r.conversation_id)}>Conversation</button>
                    {can("editor") && <button className="btn btn-ghost btn-sm" onClick={() => revoke(r)}>Take down</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
    </div>
  );
}
