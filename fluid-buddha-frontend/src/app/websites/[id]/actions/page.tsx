"use client";
// Actions (M2-8): what the agent may do for a visitor — take a payment, request
// a quote, start a trial, book a meeting, call a webhook — each confirmed by the
// visitor first; recent runs; and the site's own components.
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  ActionField, ActionIn, ActionKind, ActionRun, Api, ApiError, CustomComponent, CustomComponentIn,
  Price, SiteAction,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { Modal, Spinner, fmtDate, useToast } from "@/components/ui";

const KIND_LABEL: Record<ActionKind, string> = {
  payment_link: "Take a payment (Razorpay link)",
  quote_request: "Request a quote",
  trial: "Start a trial",
  meeting_link: "Book a meeting",
  webhook: "Call a webhook",
};

const BLANK: Record<ActionKind, ActionIn> = {
  payment_link: { kind: "payment_link", name: "buy_plan", label: "Pay for a plan", enabled: true,
    description: "When the visitor wants to buy or pay for a plan.",
    config: { key_id: "", prices: [{ key: "growth", label: "Growth plan", amount: 1499900 }], max_per_hour: 20 } },
  quote_request: { kind: "quote_request", name: "get_quote", label: "Request a quote", enabled: true,
    description: "When the visitor wants a custom quote or volume pricing.", config: { max_per_hour: 20 } },
  trial: { kind: "trial", name: "start_trial", label: "Start a free trial", enabled: true,
    description: "When the visitor wants to try the product.", config: { url: "", max_per_hour: 20 } },
  meeting_link: { kind: "meeting_link", name: "book_meeting", label: "Book a call", enabled: true,
    description: "When the visitor wants to talk to the team or see a demo.",
    config: { booking_url: "", style: "calendly", max_per_hour: 20 } },
  webhook: { kind: "webhook", name: "send_request", label: "Send a request", enabled: true, description: "",
    config: { url: "", fields: [{ key: "email", label: "Email", type: "email", required: true }], max_per_hour: 20 } },
};

const STATUS: Record<ActionRun["status"], string> = {
  proposed: "waiting", cancelled: "cancelled", expired: "expired", done: "done", failed: "failed", paid: "paid",
};

const inr = (paise: number | null | undefined) =>
  paise == null ? "—" : `₹${(paise / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

export default function ActionsPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const { can } = useAuth();
  const admin = can("admin");
  const editor = can("editor");
  const [actions, setActions] = useState<SiteAction[] | null>(null);
  const [runs, setRuns] = useState<ActionRun[] | null>(null);
  const [editing, setEditing] = useState<{ id: string | null; action: ActionIn; has_secret: boolean } | null>(null);
  const [secret, setSecret] = useState<{ label: string; signing?: string | null; webhook?: string | null } | null>(null);

  const load = useCallback(() => {
    Api.actions(id).then((r) => setActions(r.actions)).catch(() => setActions([]));
    Api.actionRuns(id).then((r) => setRuns(r.runs)).catch(() => setRuns([]));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const save = async (actionId: string | null, a: ActionIn) => {
    try {
      if (actionId) await Api.updateAction(id, actionId, a);
      else await Api.createAction(id, a);
      toast(actionId ? "Action saved" : "Action added");
      setEditing(null);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not save", "err");
    }
  };

  const showSecret = async (a: SiteAction) => {
    try {
      const s = await Api.actionSecret(id, a.id);
      setSecret({ label: a.label, signing: s.signing_secret, webhook: s.razorpay_webhook_url });
    } catch { toast("Could not load it", "err"); }
  };

  return (
    <div className="fade-in stack">
      <div className="row between wrap page-head" style={{ gap: 12 }}>
        <div>
          <h2>Actions</h2>
          <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 700 }}>
            Let the agent do things for a visitor, not just explain them. It offers an action when the visitor asks;
            the visitor sees the details (and the amount) and nothing happens until they press Confirm.
          </p>
        </div>
        {admin && (
          <select className="select" style={{ width: "auto" }} value="" aria-label="Add action"
            onChange={(e) => { const k = e.target.value as ActionKind; if (k) setEditing({ id: null, action: BLANK[k], has_secret: false }); }}>
            <option value="">Add an action…</option>
            {(Object.keys(KIND_LABEL) as ActionKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
          </select>
        )}
      </div>

      <section className="card">
        {!actions ? <div className="skeleton" style={{ height: 120 }} /> : actions.length === 0 ? (
          <div className="empty">No actions yet.{admin ? "" : " An Admin can add them."}</div>
        ) : (
          <table className="table">
            <thead><tr><th>Action</th><th>Kind</th><th>Details</th><th /></tr></thead>
            <tbody>
              {actions.map((a) => (
                <tr key={a.id} style={{ opacity: a.enabled ? 1 : 0.55 }}>
                  <td>
                    <div>{a.label}{!a.enabled && <span className="faint"> (off)</span>}</div>
                    <div className="faint mono" style={{ fontSize: "0.78rem" }}>{a.name}</div>
                  </td>
                  <td style={{ fontSize: "0.86rem" }}>{KIND_LABEL[a.kind]}</td>
                  <td style={{ fontSize: "0.84rem", maxWidth: 320 }}>
                    {a.kind === "payment_link" && (a.config.prices ?? []).map((p) => `${p.label} ${inr(p.amount)}`).join(" · ")}
                    {a.kind === "meeting_link" && a.config.booking_url}
                    {(a.kind === "trial" || a.kind === "webhook") && a.config.url}
                    {a.kind === "quote_request" && "Sent to your leads (webhook, Slack) and owners' email"}
                  </td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {admin && <>
                      {a.kind !== "quote_request" && a.kind !== "meeting_link" &&
                        <button className="btn btn-sm btn-ghost" onClick={() => showSecret(a)}>
                          {a.kind === "payment_link" ? "Razorpay webhook" : "Signing secret"}</button>}
                      <button className="btn btn-sm btn-ghost" onClick={() => setEditing({
                        id: a.id, has_secret: a.has_secret,
                        action: { name: a.name, label: a.label, description: a.description, enabled: a.enabled, config: a.config, kind: a.kind } })}>
                        Edit</button>
                      <button className="btn btn-sm btn-ghost" onClick={async () => {
                        if (!window.confirm(`Delete “${a.label}”? The agent stops offering it.`)) return;
                        try { await Api.deleteAction(id, a.id); toast("Action deleted"); load(); }
                        catch { toast("Could not delete", "err"); }
                      }}>Delete</button>
                    </>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h3 style={{ marginBottom: 4 }}>Recent runs</h3>
        <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 12 }}>
          Every time the agent offered an action, and what the visitor did.
        </p>
        {!runs ? <div className="skeleton" style={{ height: 100 }} /> : runs.length === 0 ? (
          <div className="empty">Nothing yet.</div>
        ) : (
          <table className="table">
            <thead><tr><th>When</th><th>Action</th><th>Visitor</th><th>Amount</th><th>Status</th><th>Outcome</th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td className="faint">{fmtDate(r.created_at)}</td>
                  <td className="mono" style={{ fontSize: "0.82rem" }}>{r.action_name}</td>
                  <td style={{ fontSize: "0.84rem" }}>{String(r.inputs.email ?? "—")}</td>
                  <td className="mono">{inr(r.amount)}</td>
                  <td><span className={`badge ${r.status === "paid" || r.status === "done" ? "ok" : r.status === "failed" ? "err" : ""}`}>
                    {STATUS[r.status]}</span></td>
                  <td style={{ fontSize: "0.82rem", maxWidth: 280 }}>
                    {r.error ? <span className="faint">{r.error}</span>
                      : r.result.url ? <a href={r.result.url} target="_blank" rel="noopener noreferrer">open link</a>
                      : r.result.message ?? "—"}
                    {r.kind === "quote_request" && r.status === "done" && (
                      <button className="btn btn-ghost btn-sm" style={{ marginLeft: 6 }}
                        onClick={() => Api.quotePdf(id, r.id).then((b) => {
                          const url = URL.createObjectURL(b);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `quote-${r.id.slice(0, 8)}.pdf`;
                          a.click();
                          URL.revokeObjectURL(url);
                        }).catch(() => toast("Could not download the quote", "err"))}>PDF</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <ComponentsCard id={id} editor={editor} />

      {editing && (
        <Modal open onClose={() => setEditing(null)} width={620}
          title={`${editing.id ? "Edit" : "Add"}: ${KIND_LABEL[editing.action.kind ?? "webhook"]}`}>
          <ActionForm key={editing.id ?? editing.action.kind} initial={editing.action} hasSecret={editing.has_secret}
            onCancel={() => setEditing(null)} onSave={(a) => save(editing.id, a)} />
        </Modal>
      )}
      {secret && (
        <Modal open onClose={() => setSecret(null)} title={secret.label} width={560}>
          <div className="stack">
            {secret.webhook && <>
              <p style={{ fontSize: "0.88rem" }}>In Razorpay → Settings → Webhooks, add this URL for the
                <span className="mono"> payment_link.paid</span> event, with the webhook secret you saved here:</p>
              <code className="mono" style={{ wordBreak: "break-all" }}>{secret.webhook}</code>
              <p className="faint" style={{ fontSize: "0.8rem" }}>Without it the paid status still arrives: links are checked with Razorpay every few minutes.</p>
            </>}
            {secret.signing && <>
              <p style={{ fontSize: "0.88rem" }}>Requests to your endpoint carry <span className="mono">X-FluidBuddha-Signature: t=…,v1=…</span> —
                HMAC-SHA256 of <span className="mono">t.body</span> with this secret:</p>
              <code className="mono" style={{ wordBreak: "break-all" }}>{secret.signing}</code>
            </>}
          </div>
        </Modal>
      )}
    </div>
  );
}

function ActionForm({ initial, hasSecret, onSave, onCancel }: {
  initial: ActionIn; hasSecret: boolean; onSave: (a: ActionIn) => Promise<void>; onCancel: () => void;
}) {
  const [a, setA] = useState<ActionIn>(initial);
  const [keySecret, setKeySecret] = useState("");
  const [hookSecret, setHookSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const kind = a.kind ?? "webhook";
  const cfg = a.config;
  const setCfg = (patch: Partial<ActionIn["config"]>) => setA((x) => ({ ...x, config: { ...x.config, ...patch } }));
  const prices = cfg.prices ?? [];
  const setPrice = (i: number, p: Partial<Price>) => setCfg({ prices: prices.map((q, j) => (j === i ? { ...q, ...p } : q)) });
  const fields = cfg.fields ?? [];
  const setField = (i: number, f: Partial<ActionField>) => setCfg({ fields: fields.map((q, j) => (j === i ? { ...q, ...f } : q)) });

  return (
    <form className="stack" onSubmit={async (e) => {
      e.preventDefault();
      setBusy(true);
      await onSave({ ...a, secrets: { key_secret: keySecret || undefined, webhook_secret: hookSecret || undefined } });
      setBusy(false);
    }}>
      <div className="grid grid-2" style={{ gap: 12 }}>
        <div className="field">
          <label className="label" htmlFor="a-label">What the visitor sees</label>
          <input id="a-label" className="input" required maxLength={80} value={a.label} onChange={(e) => setA({ ...a, label: e.target.value })} />
        </div>
        <div className="field">
          <label className="label" htmlFor="a-name">Name <span className="faint">(for the agent)</span></label>
          <input id="a-name" className="input mono" required maxLength={40} pattern="[a-z][a-z0-9_]{1,39}" value={a.name}
            onChange={(e) => setA({ ...a, name: e.target.value })} />
        </div>
      </div>
      <div className="field">
        <label className="label" htmlFor="a-desc">When to offer it</label>
        <input id="a-desc" className="input" maxLength={400} value={a.description} onChange={(e) => setA({ ...a, description: e.target.value })} />
      </div>

      {kind === "payment_link" && <>
        <div className="grid grid-2" style={{ gap: 12 }}>
          <div className="field">
            <label className="label" htmlFor="a-key">Razorpay key id</label>
            <input id="a-key" className="input mono" required placeholder="rzp_test_…" value={cfg.key_id ?? ""} onChange={(e) => setCfg({ key_id: e.target.value })} />
          </div>
          <div className="field">
            <label className="label" htmlFor="a-secret">Key secret</label>
            <input id="a-secret" className="input mono" type="password" autoComplete="off" value={keySecret}
              placeholder={hasSecret ? "Saved — leave blank to keep" : ""} onChange={(e) => setKeySecret(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label className="label" htmlFor="a-wh">Razorpay webhook secret <span className="faint">(optional; for the paid status)</span></label>
          <input id="a-wh" className="input mono" type="password" autoComplete="off" value={hookSecret}
            placeholder={hasSecret ? "Leave blank to keep" : ""} onChange={(e) => setHookSecret(e.target.value)} />
        </div>
        <div className="field">
          <span className="label">Price list <span className="faint">(the agent only picks a plan; the amount always comes from here)</span></span>
          {prices.map((p, i) => (
            <div key={i} className="row" style={{ gap: 6, marginBottom: 6 }}>
              <input className="input mono" style={{ width: 120 }} aria-label="Plan key" value={p.key} onChange={(e) => setPrice(i, { key: e.target.value })} />
              <input className="input" aria-label="Plan label" value={p.label} onChange={(e) => setPrice(i, { label: e.target.value })} />
              <input className="input" style={{ width: 130 }} type="number" min={1} step="0.01" aria-label="Amount in rupees"
                value={p.amount / 100} onChange={(e) => setPrice(i, { amount: Math.round(Number(e.target.value) * 100) })} />
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setCfg({ prices: prices.filter((_, j) => j !== i) })}>Remove</button>
            </div>
          ))}
          <button type="button" className="btn btn-sm" onClick={() => setCfg({ prices: [...prices, { key: "", label: "", amount: 100000 }] })}>Add a price</button>
        </div>
      </>}

      {(kind === "trial" || kind === "webhook") && (
        <div className="field">
          <label className="label" htmlFor="a-url">{kind === "trial" ? "Your endpoint that creates the trial" : "Endpoint"}</label>
          <input id="a-url" className="input mono" type="url" required placeholder="https://" value={cfg.url ?? ""} onChange={(e) => setCfg({ url: e.target.value })} />
          {kind === "trial" && <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
            We POST the visitor&apos;s email, name and company (signed); answer with JSON <span className="mono">{"{\"login_url\": \"https://…\"}"}</span>.</p>}
        </div>
      )}
      {kind === "webhook" && (
        <div className="field">
          <span className="label">What the agent collects</span>
          {fields.map((f, i) => (
            <div key={i} className="row" style={{ gap: 6, marginBottom: 6 }}>
              <input className="input mono" style={{ width: 120 }} aria-label="Field key" value={f.key} onChange={(e) => setField(i, { key: e.target.value })} />
              <input className="input" aria-label="Field label" value={f.label} onChange={(e) => setField(i, { label: e.target.value })} />
              <select className="select" style={{ width: 110 }} aria-label="Field type" value={f.type}
                onChange={(e) => setField(i, { type: e.target.value as ActionField["type"] })}>
                {["text", "email", "number", "integer", "boolean"].map((t) => <option key={t}>{t}</option>)}
              </select>
              <label className="row" style={{ gap: 4, fontSize: "0.8rem" }}>
                <input type="checkbox" checked={f.required} onChange={(e) => setField(i, { required: e.target.checked })} /> required</label>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setCfg({ fields: fields.filter((_, j) => j !== i) })}>Remove</button>
            </div>
          ))}
          {fields.length < 8 && <button type="button" className="btn btn-sm"
            onClick={() => setCfg({ fields: [...fields, { key: "", label: "", type: "text", required: false }] })}>Add a field</button>}
        </div>
      )}
      {kind === "meeting_link" && (
        <div className="grid grid-2" style={{ gap: 12 }}>
          <div className="field">
            <label className="label" htmlFor="a-book">Booking page</label>
            <input id="a-book" className="input mono" type="url" required placeholder="https://calendly.com/…" value={cfg.booking_url ?? ""}
              onChange={(e) => setCfg({ booking_url: e.target.value })} />
          </div>
          <div className="field">
            <label className="label" htmlFor="a-style">It&apos;s a</label>
            <select id="a-style" className="select" value={cfg.style ?? "plain"} onChange={(e) => setCfg({ style: e.target.value as "calendly" | "cal" | "plain" })}>
              <option value="calendly">Calendly page</option><option value="cal">Cal.com page</option><option value="plain">Other page</option>
            </select>
          </div>
        </div>
      )}

      <div className="grid grid-2" style={{ gap: 12 }}>
        <div className="field">
          <label className="label" htmlFor="a-rate">At most, per hour</label>
          <input id="a-rate" className="input" type="number" min={1} max={500} value={cfg.max_per_hour ?? 20}
            onChange={(e) => setCfg({ max_per_hour: Number(e.target.value) || 20 })} />
        </div>
        <label className="row" style={{ gap: 8, fontSize: "0.88rem", alignSelf: "end", paddingBottom: 10 }}>
          <input type="checkbox" checked={a.enabled} onChange={(e) => setA({ ...a, enabled: e.target.checked })} /> On
        </label>
      </div>
      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save"}</button>
      </div>
    </form>
  );
}

// ---- the site's own components ----------------------------------------------------

const EXAMPLE: CustomComponentIn = {
  name: "plan_builder", label: "Plan builder", kind: "template", enabled: true, iframe_url: null,
  description: "Lets the visitor size a plan by seats.",
  props_schema: { type: "object", properties: { seats: { type: "integer", minimum: 1, maximum: 500, default: 10 } }, required: [] },
  template: { base: "configurator", state: {
    controls: [{ key: "seats", label: "Seats", type: "slider", min: 1, max: 500, value: "{{seats}}" }],
    outputs: [{ label: "Monthly", expr: "seats * 999", format: "currency" }] } },
};

function ComponentsCard({ id, editor }: { id: string; editor: boolean }) {
  const toast = useToast();
  const [items, setItems] = useState<CustomComponent[] | null>(null);
  const [editing, setEditing] = useState<{ id: string | null; spec: CustomComponentIn } | null>(null);
  const load = useCallback(() => {
    Api.components(id).then((r) => setItems(r.components)).catch(() => setItems([]));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  return (
    <section className="card">
      <div className="row between" style={{ gap: 12, marginBottom: 4 }}>
        <h3>Your components</h3>
        {editor && <button className="btn btn-sm" onClick={() => setEditing({ id: null, spec: EXAMPLE })}>Add component</button>}
      </div>
      <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 12, maxWidth: 720 }}>
        Components the agent can show besides the built-in ones: a template over a built-in component (say, a
        configurator with your prices), or your own page in a sandboxed frame. No code of yours runs on the
        visitor&apos;s page itself.
      </p>
      {!items ? <div className="skeleton" style={{ height: 80 }} /> : items.length === 0 ? <div className="empty">None yet.</div> : (
        <table className="table">
          <thead><tr><th>Component</th><th>Kind</th><th>Props</th><th /></tr></thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.id} style={{ opacity: c.enabled ? 1 : 0.55 }}>
                <td><div>{c.label}</div><div className="faint mono" style={{ fontSize: "0.78rem" }}>{c.name}</div></td>
                <td style={{ fontSize: "0.86rem" }}>{c.kind === "template" ? `Template · ${c.template?.base}` : "Sandboxed frame"}</td>
                <td className="mono" style={{ fontSize: "0.8rem" }}>
                  {Object.keys((c.props_schema as { properties?: object }).properties ?? {}).join(", ")}</td>
                <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                  {editor && <>
                    <button className="btn btn-sm btn-ghost" onClick={() => {
                      const { id: cid, ...spec } = c;
                      setEditing({ id: cid, spec });
                    }}>Edit</button>
                    <button className="btn btn-sm btn-ghost" onClick={async () => {
                      if (!window.confirm(`Delete “${c.label}”?`)) return;
                      try { await Api.deleteComponent(id, c.id); toast("Component deleted"); load(); }
                      catch { toast("Could not delete", "err"); }
                    }}>Delete</button>
                  </>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <Modal open onClose={() => setEditing(null)} title={editing.id ? "Edit component" : "Add component"} width={680}>
          <ComponentForm id={id} initial={editing.spec} onCancel={() => setEditing(null)} onSave={async (spec) => {
            try {
              if (editing.id) await Api.updateComponent(id, editing.id, spec);
              else await Api.createComponent(id, spec);
              toast("Component saved");
              setEditing(null);
              load();
            } catch (e) { toast(e instanceof ApiError ? e.message : "Could not save", "err"); }
          }} />
        </Modal>
      )}
    </section>
  );
}

function ComponentForm({ id, initial, onSave, onCancel }: {
  id: string; initial: CustomComponentIn; onSave: (s: CustomComponentIn) => Promise<void>; onCancel: () => void;
}) {
  const [s, setS] = useState(initial);
  const [schema, setSchema] = useState(JSON.stringify(initial.props_schema, null, 2));
  const [state, setState] = useState(JSON.stringify(initial.template?.state ?? {}, null, 2));
  const [base, setBase] = useState(initial.template?.base ?? "configurator");
  const [props, setProps] = useState("{}");
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const build = (): CustomComponentIn | string => {
    try {
      return {
        ...s, props_schema: JSON.parse(schema),
        template: s.kind === "template" ? { base, state: JSON.parse(state) } : null,
        iframe_url: s.kind === "iframe" ? s.iframe_url : null,
      };
    } catch { return "The props schema or template isn't valid JSON."; }
  };

  return (
    <form className="stack" onSubmit={async (e) => {
      e.preventDefault();
      const spec = build();
      if (typeof spec === "string") { setPreview(spec); return; }
      setBusy(true);
      await onSave(spec);
      setBusy(false);
    }}>
      <div className="grid grid-2" style={{ gap: 12 }}>
        <div className="field">
          <label className="label" htmlFor="c-label">Label</label>
          <input id="c-label" className="input" required maxLength={80} value={s.label} onChange={(e) => setS({ ...s, label: e.target.value })} />
        </div>
        <div className="field">
          <label className="label" htmlFor="c-name">Name <span className="faint">(for the agent)</span></label>
          <input id="c-name" className="input mono" required pattern="[a-z][a-z0-9_]{1,39}" value={s.name} onChange={(e) => setS({ ...s, name: e.target.value })} />
        </div>
      </div>
      <div className="field">
        <label className="label" htmlFor="c-desc">When the agent should use it</label>
        <input id="c-desc" className="input" maxLength={400} value={s.description} onChange={(e) => setS({ ...s, description: e.target.value })} />
      </div>
      <div className="grid grid-2" style={{ gap: 12 }}>
        <div className="field">
          <label className="label" htmlFor="c-kind">Kind</label>
          <select id="c-kind" className="select" value={s.kind} onChange={(e) => setS({ ...s, kind: e.target.value as "template" | "iframe" })}>
            <option value="template">Template over a built-in component</option>
            <option value="iframe">My page in a sandboxed frame</option>
          </select>
        </div>
        {s.kind === "template" ? (
          <div className="field">
            <label className="label" htmlFor="c-base">Built on</label>
            <select id="c-base" className="select" value={base} onChange={(e) => setBase(e.target.value)}>
              {["configurator", "scenario_simulator", "roi_calculator", "table", "chart", "tabs", "timeline", "flowchart",
                "workflow", "mind_map", "sankey", "graph", "component_diagram"].map((b) => <option key={b}>{b}</option>)}
            </select>
          </div>
        ) : (
          <div className="field">
            <label className="label" htmlFor="c-url">Page URL</label>
            <input id="c-url" className="input mono" type="url" placeholder="https://" value={s.iframe_url ?? ""}
              onChange={(e) => setS({ ...s, iframe_url: e.target.value })} />
          </div>
        )}
      </div>
      <div className="field">
        <label className="label" htmlFor="c-schema">Props the agent fills in <span className="faint">(JSON schema: string, number, integer, boolean, array)</span></label>
        <textarea id="c-schema" className="textarea mono" rows={6} value={schema} onChange={(e) => setSchema(e.target.value)} />
      </div>
      {s.kind === "template" ? (
        <div className="field">
          <label className="label" htmlFor="c-state">{base} state <span className="faint">(use {"{{prop}}"} for the props)</span></label>
          <textarea id="c-state" className="textarea mono" rows={8} value={state} onChange={(e) => setState(e.target.value)} />
        </div>
      ) : (
        <p className="faint" style={{ fontSize: "0.8rem" }}>
          Your page gets <span className="mono">{"{type: \"fb:init\", props}"}</span> by postMessage and may send
          <span className="mono"> {"{type: \"fb:resize\", height}"}</span> and <span className="mono">{"{type: \"fb:state\", state}"}</span>.
          It runs sandboxed: scripts only, no access to the visitor&apos;s page.</p>
      )}
      <div className="field">
        <label className="label" htmlFor="c-props">Try it with props</label>
        <div className="row" style={{ gap: 6 }}>
          <input id="c-props" className="input mono" value={props} onChange={(e) => setProps(e.target.value)} />
          <button type="button" className="btn btn-sm" onClick={async () => {
            const spec = build();
            if (typeof spec === "string") { setPreview(spec); return; }
            try {
              const out = await Api.previewComponent(id, spec, JSON.parse(props || "{}"));
              setPreview(JSON.stringify(out, null, 2));
            } catch (e) { setPreview(e instanceof ApiError ? e.message : "Props aren't valid JSON."); }
          }}>Preview</button>
        </div>
        {preview && <pre className="mono" style={{ fontSize: "0.76rem", maxHeight: 200, overflow: "auto", marginTop: 8 }}>{preview}</pre>}
      </div>
      <label className="row" style={{ gap: 8, fontSize: "0.88rem" }}>
        <input type="checkbox" checked={s.enabled} onChange={(e) => setS({ ...s, enabled: e.target.checked })} /> On
      </label>
      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save"}</button>
      </div>
    </form>
  );
}
