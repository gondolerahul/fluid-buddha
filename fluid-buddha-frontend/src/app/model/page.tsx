"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRequireAuth } from "@/lib/auth";
import { Api, ApiError, ModelPrice, ModelProvider, ModelProviderKind } from "@/lib/api";
import { AppHeader } from "@/components/Chrome";
import { LoadingScreen, Spinner, fmtDate, useToast } from "@/components/ui";

const LABEL: Record<ModelProviderKind, string> = {
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI",
  azure_openai: "Azure OpenAI",
};

/** Bring your own model (M3-4): the account's own provider and key. */
export default function ModelPage() {
  const auth = useRequireAuth();
  const toast = useToast();
  const [data, setData] = useState<ModelProvider | null>(null);
  const load = useCallback(() => Api.modelProvider().then(setData).catch(() => {}), []);
  useEffect(() => { if (auth.tenant && auth.can("admin")) load(); }, [auth, load]);

  if (auth.loading || !auth.tenant) return <LoadingScreen />;
  if (!auth.can("admin")) {
    return (
      <>
        <AppHeader />
        <main className="content" style={{ margin: "0 auto" }}>
          <div className="notice">Only Owners and Admins can see the account&apos;s AI model settings.</div>
        </main>
      </>
    );
  }

  return (
    <>
      <AppHeader />
      <main className="content stack" style={{ margin: "0 auto", maxWidth: 820 }}>
        <div className="page-head">
          <h1 className="h-page">AI model</h1>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            By default your agent runs on FluidBuddha&apos;s models. Use your own Anthropic, OpenAI or Azure OpenAI
            account instead — your contract, your keys, your data terms. Voice (speech in and out) and search stay
            on FluidBuddha.
          </p>
        </div>
        {!data ? <div className="skeleton" style={{ height: 300 }} /> : (
          <>
            <ProviderForm data={data} onSaved={load} toast={toast} />
            {data.configured && <SitesCard data={data} onChange={load} toast={toast} />}
          </>
        )}
      </main>
    </>
  );
}

type Toast = ReturnType<typeof useToast>;

function priceText(p?: ModelPrice) {
  return p && p.in != null && p.out != null ? `${p.in} / ${p.out}` : "";
}

function ProviderForm({ data, onSaved, toast }: { data: ModelProvider; onSaved: () => void; toast: Toast }) {
  const [provider, setProvider] = useState<ModelProviderKind>(data.provider ?? "anthropic");
  const [fast, setFast] = useState(data.fast_model ?? data.defaults.anthropic.fast_model);
  const [thinker, setThinker] = useState(data.thinker_model ?? data.defaults.anthropic.thinker_model);
  const [key, setKey] = useState("");
  const [endpoint, setEndpoint] = useState(data.endpoint ?? "");
  const [apiVersion, setApiVersion] = useState(data.api_version ?? "2024-10-21");
  const [fastPrice, setFastPrice] = useState(priceText(data.prices?.fast));
  const [thinkerPrice, setThinkerPrice] = useState(priceText(data.prices?.thinker));
  const [enabled, setEnabled] = useState(data.enabled ?? true);
  const [busy, setBusy] = useState<"save" | "test" | "remove" | null>(null);
  const [results, setResults] = useState<Awaited<ReturnType<typeof Api.testModelProvider>> | null>(null);

  const pick = (p: ModelProviderKind) => {
    setProvider(p);
    if (p !== data.provider) {
      setFast(data.defaults[p].fast_model);
      setThinker(data.defaults[p].thinker_model);
    }
  };
  const parsePrice = (t: string): ModelPrice | undefined => {
    const m = t.split("/").map((x) => Number(x.trim()));
    return m.length === 2 && m.every((n) => Number.isFinite(n) && n >= 0) ? { in: m[0], out: m[1] } : undefined;
  };
  const listed = (model: string) => data.list_prices[model];

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy("save");
    try {
      const prices: Record<string, ModelPrice> = {};
      const fp = parsePrice(fastPrice);
      const tp = parsePrice(thinkerPrice);
      if (fp) prices.fast = fp;
      if (tp) prices.thinker = tp;
      await Api.saveModelProvider({ provider, fast_model: fast, thinker_model: thinker,
        api_key: key || undefined, endpoint: provider === "azure_openai" ? endpoint : null,
        api_version: provider === "azure_openai" ? apiVersion : null, prices, enabled });
      setKey("");
      toast("Saved. Test the connection to make sure it works.");
      onSaved();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save", "err");
    } finally {
      setBusy(null);
    }
  };
  const test = async () => {
    setBusy("test");
    try {
      const r = await Api.testModelProvider();
      setResults(r);
      toast(r.ok ? "Both models answered" : "A model didn't answer — see below", r.ok ? "ok" : "err");
      onSaved();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Test failed", "err");
    } finally {
      setBusy(null);
    }
  };
  const remove = async () => {
    if (!window.confirm("Stop using your own model? Every site goes back to FluidBuddha's models.")) return;
    setBusy("remove");
    try {
      await Api.deleteModelProvider();
      toast("Back on FluidBuddha's models");
      onSaved();
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="card">
      <div className="row between wrap" style={{ gap: 12, marginBottom: 12 }}>
        <h3>Your provider</h3>
        {data.configured && (
          <span className={`badge ${data.last_test_ok ? "ok" : data.last_test_ok === false ? "err" : ""}`}>
            {data.last_test_ok ? "Connected" : data.last_test_ok === false ? "Not working" : "Not tested"}
            {data.last_test_at ? ` · ${fmtDate(data.last_test_at)}` : ""}
          </span>
        )}
      </div>
      {data.last_error && (
        <div className="notice err" style={{ marginBottom: 12 }}>
          {data.last_error} — conversations fall back to FluidBuddha&apos;s models until this is fixed.
        </div>
      )}
      <form className="stack" onSubmit={save}>
        <div className="tabs" style={{ margin: 0 }}>
          {(Object.keys(LABEL) as ModelProviderKind[]).map((p) => (
            <button key={p} type="button" className={`tab ${provider === p ? "active" : ""}`} onClick={() => pick(p)}>
              {LABEL[p]}
            </button>
          ))}
        </div>
        <div className="field">
          <label className="label" htmlFor="m-key">API key</label>
          <input id="m-key" className="input mono" type="password" autoComplete="off" value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={data.configured && provider === data.provider ? `Stored (${data.key_hint}) — leave empty to keep` : "Paste the key"} />
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
            Stored encrypted and never shown again. Use a key made for FluidBuddha so you can revoke it on its own.
          </p>
        </div>
        {provider === "azure_openai" && (
          <div className="grid grid-2" style={{ gap: 12 }}>
            <div className="field">
              <label className="label" htmlFor="m-endpoint">Endpoint</label>
              <input id="m-endpoint" className="input mono" value={endpoint} placeholder="https://my-resource.openai.azure.com"
                onChange={(e) => setEndpoint(e.target.value)} />
            </div>
            <div className="field">
              <label className="label" htmlFor="m-version">API version</label>
              <input id="m-version" className="input mono" value={apiVersion} onChange={(e) => setApiVersion(e.target.value)} />
            </div>
          </div>
        )}
        <div className="grid grid-2" style={{ gap: 12 }}>
          <div className="field">
            <label className="label" htmlFor="m-fast">
              Fast model <span className="faint">(routing, quick answers{provider === "azure_openai" ? "; deployment name" : ""})</span>
            </label>
            <input id="m-fast" className="input mono" required value={fast} onChange={(e) => setFast(e.target.value)} />
            {listed(fast) && <p className="faint" style={{ fontSize: "0.76rem", marginTop: 4 }}>
              List price ${listed(fast).in} / ${listed(fast).out} per million tokens (in / out)</p>}
          </div>
          <div className="field">
            <label className="label" htmlFor="m-thinker">
              Thinking model <span className="faint">(grounded answers with tools{provider === "azure_openai" ? "; deployment name" : ""})</span>
            </label>
            <input id="m-thinker" className="input mono" required value={thinker} onChange={(e) => setThinker(e.target.value)} />
            {listed(thinker) && <p className="faint" style={{ fontSize: "0.76rem", marginTop: 4 }}>
              List price ${listed(thinker).in} / ${listed(thinker).out} per million tokens (in / out)</p>}
          </div>
        </div>
        <details>
          <summary className="faint" style={{ cursor: "pointer", fontSize: "0.84rem" }}>Your prices, for cost tracking</summary>
          <div className="grid grid-2" style={{ gap: 12, marginTop: 10 }}>
            <div className="field">
              <label className="label" htmlFor="m-fp">Fast model, USD per 1M tokens (in / out)</label>
              <input id="m-fp" className="input mono" value={fastPrice} placeholder="e.g. 0.10 / 0.50"
                onChange={(e) => setFastPrice(e.target.value)} />
            </div>
            <div className="field">
              <label className="label" htmlFor="m-tp">Thinking model, USD per 1M tokens (in / out)</label>
              <input id="m-tp" className="input mono" value={thinkerPrice} placeholder="e.g. 4 / 20"
                onChange={(e) => setThinkerPrice(e.target.value)} />
            </div>
          </div>
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 6 }}>
            Leave empty to use the provider&apos;s list price where we know it. This model spend is yours (you pay your
            provider), so it shows separately on Analytics and doesn&apos;t count towards FluidBuddha&apos;s daily spend cap.
          </p>
        </details>
        <label className="row" style={{ gap: 8, fontSize: "0.88rem" }}>
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Use this provider
        </label>
        <div className="row wrap" style={{ gap: 8 }}>
          <button className="btn btn-primary btn-sm" disabled={busy !== null}>{busy === "save" ? <Spinner /> : "Save"}</button>
          {data.configured && <button type="button" className="btn btn-sm" disabled={busy !== null} onClick={test}>
            {busy === "test" ? <Spinner /> : "Test connection"}</button>}
          {data.configured && <button type="button" className="btn btn-ghost btn-sm btn-danger" disabled={busy !== null}
            onClick={remove}>Remove</button>}
        </div>
      </form>
      {results && (
        <div className="stack-sm" style={{ marginTop: 14 }}>
          {results.results.map((r) => (
            <div key={r.role} className={`notice ${r.ok ? "ok" : "err"}`}>
              <strong>{r.ok ? "✓" : "✕"} {r.role === "fast" ? "Fast" : "Thinking"} model</strong>{" "}
              <span className="mono">{r.model}</span>{r.ok ? ` answered (${r.answered_by})` : ` — ${r.error}`}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function SitesCard({ data, onChange, toast }: { data: ModelProvider; onChange: () => void; toast: Toast }) {
  const flip = async (id: string, on: boolean) => {
    try {
      await Api.siteModel(id, on);
      onChange();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not change", "err");
    }
  };
  return (
    <section className="card">
      <h3>Websites</h3>
      <p className="faint" style={{ fontSize: "0.84rem", margin: "4px 0 12px" }}>
        Which sites answer with your model. A site switched off uses FluidBuddha&apos;s.
      </p>
      {data.sites.length === 0 ? <div className="empty">No websites yet.</div> : (
        <table className="table">
          <tbody>
            {data.sites.map((s) => (
              <tr key={s.id}>
                <td><Link href={`/websites/${s.id}/analytics`}>{s.name}</Link></td>
                <td style={{ textAlign: "right" }}>
                  <label className="row" style={{ gap: 8, justifyContent: "flex-end", fontSize: "0.86rem" }}>
                    <input type="checkbox" checked={s.byo_model} onChange={(e) => flip(s.id, e.target.checked)} />
                    {s.byo_model ? `Your ${LABEL[data.provider!]}` : "FluidBuddha"}
                  </label>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
