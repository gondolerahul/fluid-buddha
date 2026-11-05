"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AgentAccess, Api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Spinner, fmtDate, useToast } from "@/components/ui";

/** Let AI assistants ask this website, through MCP, llms.txt and REST (M3-2). */
export default function AgentAccessPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const { can } = useAuth();
  const isAdmin = can("admin");
  const [data, setData] = useState<AgentAccess | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => Api.agentAccess(id).then(setData).catch(() => {}), [id]);
  useEffect(() => { load(); }, [load]);

  const copy = (text: string, what: string) =>
    navigator.clipboard.writeText(text).then(() => toast(`${what} copied`), () => toast("Copy failed", "err"));

  const toggle = async () => {
    if (!data) return;
    setBusy(true);
    try {
      await Api.setAgentAccess(id, !data.enabled);
      toast(data.enabled ? "AI assistants can no longer ask this site" : "AI assistants can ask this site now");
      await load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not change it", "err");
    } finally {
      setBusy(false);
    }
  };

  if (!data) return <div className="skeleton" style={{ height: 240 }} />;
  const e = data.endpoints;

  return (
    <div className="fade-in stack">
      <div className="page-head">
        <h2>Agent access</h2>
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          AI assistants (Claude, ChatGPT and others) increasingly research and buy for people. Let them ask this
          site&apos;s agent directly: the same grounded answers, with sources, from your own content.
        </p>
      </div>

      <section className="card">
        <div className="row between wrap" style={{ gap: 12 }}>
          <div>
            <strong>Answer AI assistants</strong>
            <p className="faint" style={{ fontSize: "0.84rem", marginTop: 4 }}>
              Reading needs no sign-in: questions, pages and prices, like your widget. Rate-limited, and under your
              daily spend cap. Anything that acts — taking a lead, a payment — needs a token you issue below.
            </p>
          </div>
          {isAdmin ? (
            <button className={`btn btn-sm ${data.enabled ? "" : "btn-primary"}`} disabled={busy || !e} onClick={toggle}>
              {busy ? <Spinner /> : data.enabled ? "Switch off" : "Switch on"}
            </button>
          ) : <span className="badge">{data.enabled ? "On" : "Off"}</span>}
        </div>
        {!e && <div className="notice warn" style={{ marginTop: 12 }}>Create a widget key first (Install tab).</div>}
        {data.enabled && e && (
          <div className="stack-sm" style={{ marginTop: 16 }}>
            {([["MCP server", e.mcp], ["llms.txt", e.llms_txt], ["OpenAPI", e.openapi], ["REST ask", e.ask]] as const).map(([label, url]) => (
              <div key={label} className="row between" style={{ gap: 12 }}>
                <span className="eyebrow" style={{ minWidth: 90 }}>{label}</span>
                <code className="code" style={{ flex: 1, wordBreak: "break-all", padding: "6px 10px" }}>{url}</code>
                <button className="btn btn-sm" onClick={() => copy(url, label)}>Copy</button>
              </div>
            ))}
            <p className="faint" style={{ fontSize: "0.8rem", marginTop: 6 }}>
              In Claude, add a custom connector with the MCP server address. To have assistants find it from your
              own site, serve <span className="mono">/llms.txt</span> on your domain as a redirect or copy of the llms.txt above.
            </p>
          </div>
        )}
      </section>

      {data.enabled && <TokensCard id={id} data={data} isAdmin={isAdmin} onChange={load} />}
      {data.enabled && <TrafficCard data={data} />}
    </div>
  );
}

function TokensCard({ id, data, isAdmin, onChange }: { id: string; data: AgentAccess; isAdmin: boolean; onChange: () => void }) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>(["leads"]);
  const [made, setMade] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const flip = (s: string) => setScopes((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));
  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const t = await Api.createAgentToken(id, name.trim(), scopes);
      setMade(t.token);
      setName("");
      onChange();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not create the token", "err");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="card">
      <h3>Tokens for assistants that act</h3>
      <p className="faint" style={{ fontSize: "0.84rem", margin: "4px 0 12px" }}>
        Give one to an assistant you trust to pass on leads or run your actions (payment links, quotes, trials).
        The assistant sends it as <span className="mono">Authorization: Bearer …</span>. Amounts always come from
        your price lists.
      </p>
      {made && (
        <div className="notice ok" style={{ marginBottom: 12 }}>
          Copy this token now — it won&apos;t be shown again.
          <div className="row" style={{ gap: 8, marginTop: 8 }}>
            <code className="code" style={{ flex: 1, wordBreak: "break-all", padding: "6px 10px" }}>{made}</code>
            <button className="btn btn-sm" onClick={() => navigator.clipboard.writeText(made).then(() => toast("Token copied"))}>Copy</button>
          </div>
        </div>
      )}
      {data.tokens.length > 0 && (
        <table className="table" style={{ marginBottom: 12 }}>
          <thead><tr><th>Name</th><th>May</th><th>Last used</th><th /></tr></thead>
          <tbody>
            {data.tokens.map((t) => (
              <tr key={t.id}>
                <td>{t.name}</td>
                <td>{t.scopes.map((s) => (s === "leads" ? "take leads" : "run actions")).join(", ")}</td>
                <td className="faint">{t.last_used_at ? fmtDate(t.last_used_at) : "never"}</td>
                <td style={{ textAlign: "right" }}>
                  {isAdmin && <button className="btn btn-ghost btn-sm btn-danger"
                    onClick={() => Api.revokeAgentToken(id, t.id).then(() => { toast("Token revoked"); onChange(); })}>Revoke</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {isAdmin && (
        <form className="row wrap" style={{ gap: 10, alignItems: "center" }} onSubmit={create}>
          <input className="input" required maxLength={80} value={name} placeholder="Which assistant (e.g. Acme buying agent)"
            onChange={(e) => setName(e.target.value)} style={{ maxWidth: 300 }} />
          <label className="row" style={{ gap: 6, fontSize: "0.86rem" }}>
            <input type="checkbox" checked={scopes.includes("leads")} onChange={() => flip("leads")} /> take leads
          </label>
          <label className="row" style={{ gap: 6, fontSize: "0.86rem" }}>
            <input type="checkbox" checked={scopes.includes("actions")} onChange={() => flip("actions")} /> run actions
          </label>
          <button className="btn btn-sm" disabled={busy || !scopes.length || !name.trim()}>{busy ? <Spinner /> : "Create token"}</button>
        </form>
      )}
    </section>
  );
}

function TrafficCard({ data }: { data: AgentAccess }) {
  const t = data.traffic;
  return (
    <section className="card">
      <h3>Agent traffic <span className="faint" style={{ fontSize: "0.84rem", fontWeight: 400 }}>· last {t.days} days</span></h3>
      {t.total === 0 ? <div className="empty" style={{ marginTop: 10 }}>No AI assistant has asked yet.</div> : (
        <div className="grid grid-2" style={{ gap: 16, marginTop: 12 }}>
          <div>
            <span className="eyebrow">What they asked for</span>
            <table className="table" style={{ marginTop: 6 }}><tbody>
              {t.by_tool.map((r) => (
                <tr key={r.tool}><td className="mono" style={{ fontSize: "0.84rem" }}>{r.tool}</td>
                  <td style={{ textAlign: "right" }}>{r.count}{r.failed ? <span className="faint"> ({r.failed} failed)</span> : null}</td></tr>
              ))}
            </tbody></table>
          </div>
          <div>
            <span className="eyebrow">Which assistants</span>
            <table className="table" style={{ marginTop: 6 }}><tbody>
              {t.by_client.map((r) => (
                <tr key={r.client}><td style={{ fontSize: "0.84rem" }}>{r.client}</td><td style={{ textAlign: "right" }}>{r.count}</td></tr>
              ))}
            </tbody></table>
          </div>
        </div>
      )}
    </section>
  );
}
