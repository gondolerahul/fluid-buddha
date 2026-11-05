"use client";
// Insights v2 (M2-5): what visitors' questions say about the deal — objections,
// competitor mentions, feature requests (sendable to the product team) and
// buying signals. Each example opens its conversation.
import { useCallback, useEffect, useState } from "react";
import { Api, ApiError, FeatureRequest, SignalExample, Signals } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Modal, Spinner, useToast } from "@/components/ui";

function trend(now: number, prev: number): string {
  if (!prev) return now ? "new" : "";
  const d = Math.round(((now - prev) / prev) * 100);
  return d === 0 ? "same as before" : `${d > 0 ? "↑" : "↓"} ${Math.abs(d)}% vs previous`;
}

const LANG_LABELS: Record<string, string> = {
  en: "English", hi: "Hindi", hinglish: "Hinglish (Hindi in English letters)",
};

export function DealSignals({ id, days, onOpen }: { id: string; days: number; onOpen: (cid: string) => void }) {
  const { can } = useAuth();
  const editor = can("editor");
  const [res, setRes] = useState<{ key: string; data: Signals | null } | null>(null);
  const [sending, setSending] = useState<FeatureRequest | null>(null);
  const [editing, setEditing] = useState(false);
  const key = `${id}:${days}`;
  const data = res?.key === key ? res.data : null;

  const load = useCallback(() => {
    Api.signals(id, days).then((d) => setRes({ key, data: d })).catch(() => setRes({ key, data: null }));
  }, [id, days, key]);
  useEffect(() => { load(); }, [load]);

  const Example = ({ e }: { e: SignalExample }) => (
    <button className="link-btn" onClick={() => onOpen(e.conversation_id)}
      style={{ display: "block", textAlign: "left", fontSize: "0.82rem", color: "inherit", opacity: 0.8,
        background: "none", border: 0, padding: "2px 0", cursor: "pointer", font: "inherit" }}>
      “{e.question}”
    </button>
  );

  return (
    <>
      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <h3 style={{ marginBottom: 4 }}>Objections</h3>
          <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 14 }}>
            Worries that could stop a purchase, by type. Click a quote to read the conversation.
          </p>
          {!data ? <div className="skeleton" style={{ height: 140 }} />
            : data.objections.length === 0 ? <div className="empty">No objections raised.</div>
            : (
              <div className="stack-sm">
                {data.objections.map((o) => (
                  <div key={o.type}>
                    <div className="row between" style={{ gap: 12 }}>
                      <strong style={{ fontWeight: 600 }}>{o.label}</strong>
                      <span><span className="mono">{o.count}×</span>
                        <span className="faint" style={{ fontSize: "0.78rem" }}> {trend(o.count, o.previous)}</span></span>
                    </div>
                    {o.examples.slice(0, 2).map((e) => <Example key={e.at + e.question} e={e} />)}
                  </div>
                ))}
              </div>
            )}
        </div>

        <div className="card">
          <div className="row between" style={{ marginBottom: 4 }}>
            <h3>Competitors mentioned</h3>
            {editor && <button className="btn btn-sm btn-ghost" onClick={() => setEditing(true)}>Edit list</button>}
          </div>
          <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 14 }}>
            Names on your list are always caught; the model spots others too.
          </p>
          {!data ? <div className="skeleton" style={{ height: 140 }} />
            : data.competitors.length === 0 ? <div className="empty">No competitors mentioned.</div>
            : (
              <div className="stack-sm">
                {data.competitors.map((c) => (
                  <div key={c.name}>
                    <div className="row between" style={{ gap: 12 }}>
                      <strong style={{ fontWeight: 600 }}>{c.name}</strong>
                      <span><span className="mono">{c.count}×</span>
                        <span className="faint" style={{ fontSize: "0.78rem" }}> {trend(c.count, c.previous)}</span></span>
                    </div>
                    {c.examples.slice(0, 2).map((e) => <Example key={e.at + e.question} e={e} />)}
                  </div>
                ))}
              </div>
            )}
        </div>
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <div className="card">
          <h3 style={{ marginBottom: 4 }}>Feature requests</h3>
          <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 14 }}>
            Things visitors want, with similar asks grouped together.
          </p>
          {!data ? <div className="skeleton" style={{ height: 140 }} />
            : data.requests.length === 0 ? <div className="empty">No feature requests.</div>
            : (
              <div className="stack-sm">
                {data.requests.slice(0, 10).map((r) => (
                  <div key={r.text + r.last_at} className="row between" style={{ gap: 12, alignItems: "flex-start" }}>
                    <div style={{ minWidth: 0 }}>
                      <span>{r.text}</span> <span className="faint">· {r.count}×</span>
                      {r.examples.length > 1 && <Example e={r.examples[1]} />}
                    </div>
                    {editor && <button className="btn btn-sm" onClick={() => setSending(r)}>Send to product</button>}
                  </div>
                ))}
              </div>
            )}
        </div>

        <div className="card">
          <h3 style={{ marginBottom: 4 }}>Buying signals</h3>
          <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 14 }}>
            Questions about trials, demos, seats, contracts or getting started.
          </p>
          {!data ? <div className="skeleton" style={{ height: 80 }} /> : (
            <>
              <div className="metric">{data.buying_signals.conversations}</div>
              <div className="faint" style={{ fontSize: "0.82rem" }}>
                conversations ({data.buying_signals.turns} questions) in the last {days} days
              </div>
              {(data.languages ?? []).some((l) => l.lang !== "en") && (
                <div className="faint" style={{ fontSize: "0.82rem", marginTop: 14 }}>
                  Asked in: {(data.languages ?? []).map((l) =>
                    `${LANG_LABELS[l.lang] ?? l.lang} ${l.turns}`).join(" · ")}
                </div>
              )}
              {data.pending > 0 && <p className="faint" style={{ fontSize: "0.78rem", marginTop: 12 }}>
                {data.pending} recent questions are still being read; they show within a minute.</p>}
            </>
          )}
        </div>
      </div>

      {sending && (
        <Modal open onClose={() => setSending(null)} title="Send to product" width={520}>
          <SendForm id={id} req={sending} onDone={() => setSending(null)} />
        </Modal>
      )}
      {editing && (
        <Modal open onClose={() => setEditing(false)} title="Competitors" width={480}>
          <CompetitorForm id={id} onDone={() => { setEditing(false); load(); }} />
        </Modal>
      )}
    </>
  );
}

function SendForm({ id, req, onDone }: { id: string; req: FeatureRequest; onDone: () => void }) {
  const toast = useToast();
  const [channel, setChannel] = useState<"slack" | "webhook" | "email">("slack");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await Api.sendRequest(id, { channel, text: req.text, count: req.count,
        examples: req.examples.map((x) => x.question).slice(0, 3), email: channel === "email" ? email : undefined });
      toast("Sent to product");
      onDone();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not send", "err");
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="stack" onSubmit={send}>
      <p style={{ fontSize: "0.9rem" }}>“{req.text}” <span className="faint">· asked {req.count}×</span></p>
      <div className="field">
        <label className="label" htmlFor="sr-channel">Send to</label>
        <select id="sr-channel" className="select" value={channel}
          onChange={(e) => setChannel(e.target.value as typeof channel)}>
          <option value="slack">This site&apos;s Slack channel</option>
          <option value="webhook">This site&apos;s webhook (event feature_request)</option>
          <option value="email">An email address</option>
        </select>
      </div>
      {channel === "email" && (
        <div className="field">
          <label className="label" htmlFor="sr-email">Email</label>
          <input id="sr-email" className="input" type="email" required value={email}
            placeholder="product@yourcompany.com" onChange={(e) => setEmail(e.target.value)} />
        </div>
      )}
      <p className="faint" style={{ fontSize: "0.78rem" }}>Slack and the webhook are set up under Leads → Integrations.</p>
      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onDone}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Send"}</button>
      </div>
    </form>
  );
}

function CompetitorForm({ id, onDone }: { id: string; onDone: () => void }) {
  const toast = useToast();
  const [names, setNames] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    Api.getProfile(id).then((p) => setNames((p.competitors ?? []).join("\n"))).catch(() => setNames(""));
  }, [id]);
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await Api.updateProfile(id, { competitors: (names ?? "").split(/[\n,]/).map((n) => n.trim()).filter(Boolean) });
      toast("Competitor list saved");
      onDone();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save", "err");
    } finally {
      setBusy(false);
    }
  };
  if (names === null) return <div className="skeleton" style={{ height: 120 }} />;
  return (
    <form className="stack" onSubmit={save}>
      <div className="field">
        <label className="label" htmlFor="cmp-names">One per line</label>
        <textarea id="cmp-names" className="textarea" rows={6} value={names}
          placeholder={"Intercom\nDrift"} onChange={(e) => setNames(e.target.value)} />
      </div>
      <p className="faint" style={{ fontSize: "0.78rem" }}>Applies to questions asked from now on.</p>
      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onDone}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save"}</button>
      </div>
    </form>
  );
}
