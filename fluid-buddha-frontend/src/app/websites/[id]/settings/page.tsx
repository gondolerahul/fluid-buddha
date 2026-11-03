"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AgentProfile, Api, ApiError, Integrations, Persona, Website } from "@/lib/api";
import { useWebsite } from "@/components/WebsiteContext";
import { Spinner, useToast } from "@/components/ui";

const INTELLIGENCE: [string, string][] = [
  ["basic", "Basic — text answers and navigation"],
  ["high", "High — adds voice"],
  ["advance", "Advance — adds diagrams and interactive components"],
  ["extreme", "Extreme — adds generated pages"],
];
const DESIGNS: [string, string][] = [
  ["level1", "Level 1 — Companion panel"],
  ["level2", "Level 2 — Immersive presence"],
  ["level3", "Level 3 — Page atmosphere"],
];

/** "https://www.acme.com/pricing" → "acme.com". The origin check allows a domain
 *  and its subdomains, so storing the apex covers www and every other subdomain. */
function hostOnly(value: string): string {
  return value.trim().toLowerCase()
    .replace(/^[a-z]+:\/\//, "").replace(/[/:?#].*$/, "").replace(/^www\./, "");
}

const lines = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean);

export default function SettingsPage() {
  const { website, reload } = useWebsite();
  if (!website) return <div className="skeleton" style={{ height: 240 }} />;
  return (
    <div className="fade-in stack">
      <div className="page-head">
        <h2>Settings</h2>
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          How this site&apos;s agent behaves, what it&apos;s called, and where it can take visitors.
        </p>
      </div>
      <SiteForm key={website.id} website={website} onSaved={reload} />
      <ProfileSection id={website.id} />
      <IntegrationsSection id={website.id} />
      <DangerZone website={website} />
    </div>
  );
}

// ---- site ------------------------------------------------------------------

function SiteForm({ website, onSaved }: { website: Website; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(website.name);
  const [domain, setDomain] = useState(website.domain ?? "");
  const [intelligence, setIntelligence] = useState(website.intelligence);
  const [design, setDesign] = useState(website.design);
  const [accent, setAccent] = useState(website.accent ?? "#ffd23f");
  const [busy, setBusy] = useState(false);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { toast("Name is required", "err"); return; }
    setBusy(true);
    try {
      const host = hostOnly(domain);
      await Api.updateWebsite(website.id, { name: name.trim(), domain: host, intelligence, design, accent });
      setDomain(host);
      onSaved();
      toast("Site settings saved");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save", "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card stack" onSubmit={save}>
      <span className="eyebrow">Site</span>
      <div className="grid grid-2" style={{ gap: 14 }}>
        <div className="field">
          <label className="label" htmlFor="s-name">Name</label>
          <input id="s-name" className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="s-domain">Domain <span className="faint">(allowed origin)</span></label>
          <input id="s-domain" className="input mono" value={domain} placeholder="acme.com"
            onChange={(e) => setDomain(e.target.value)} />
          <span className="faint" style={{ fontSize: "0.78rem" }}>
            Hostname only. Subdomains are allowed automatically. Leave empty to allow any site.
          </span>
        </div>
        <div className="field">
          <label className="label" htmlFor="s-intel">Intelligence tier</label>
          <select id="s-intel" className="select" value={intelligence} onChange={(e) => setIntelligence(e.target.value)}>
            {INTELLIGENCE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="s-design">Design</label>
          <select id="s-design" className="select" value={design} onChange={(e) => setDesign(e.target.value)}>
            {DESIGNS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="s-accent">Accent colour</label>
          <div className="row" style={{ gap: 8 }}>
            <input type="color" value={accent} onChange={(e) => setAccent(e.target.value)}
              aria-label="Pick accent colour" style={{ width: 42, height: 36, border: "none", background: "none" }} />
            <input id="s-accent" className="input mono" value={accent} onChange={(e) => setAccent(e.target.value)} />
          </div>
        </div>
      </div>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save site settings"}</button>
      </div>
    </form>
  );
}

// ---- agent profile -----------------------------------------------------------

function ProfileSection({ id }: { id: string }) {
  const [state, setState] = useState<{ profile: AgentProfile | null; error: boolean } | null>(null);
  useEffect(() => {
    Api.getProfile(id)
      .then((profile) => setState({ profile, error: false }))
      .catch(() => setState({ profile: null, error: true }));
  }, [id]);

  if (!state) return <div className="skeleton" style={{ height: 320 }} />;
  if (!state.profile) return <div className="notice err">Couldn&apos;t load the agent profile.</div>;
  return <ProfileForm id={id} initial={state.profile} />;
}

const EMPTY_PERSONA: Persona = { slug: "", label: "", focus: "", tone: "", landing: "" };

function ProfileForm({ id, initial }: { id: string; initial: AgentProfile }) {
  const toast = useToast();
  const [agentName, setAgentName] = useState(initial.agent_name);
  const [company, setCompany] = useState(initial.company_name);
  const [voice, setVoice] = useState(initial.brand_voice);
  const [closing, setClosing] = useState(initial.closing_use_case);
  const [personas, setPersonas] = useState<Persona[]>(initial.personas);
  const [routes, setRoutes] = useState(initial.routes.join("\n"));
  const [prefixes, setPrefixes] = useState(initial.dynamic_prefixes.join("\n"));
  const [busy, setBusy] = useState(false);

  const editPersona = (i: number, patch: Partial<Persona>) =>
    setPersonas((ps) => ps.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agentName.trim() || !company.trim() || !voice.trim()) {
      toast("Agent name, company and voice are required", "err");
      return;
    }
    setBusy(true);
    try {
      const saved = await Api.updateProfile(id, {
        agent_name: agentName.trim(),
        company_name: company.trim(),
        brand_voice: voice.trim(),
        closing_use_case: closing.trim(),
        personas: personas
          .filter((p) => p.slug.trim() || p.label.trim())
          .map((p) => ({
            slug: p.slug.trim(), label: p.label.trim(), focus: p.focus.trim(),
            tone: p.tone.trim(), landing: p.landing.trim(),
          })),
        routes: lines(routes),
        dynamic_prefixes: lines(prefixes),
      });
      setRoutes(saved.routes.join("\n"));
      setPrefixes(saved.dynamic_prefixes.join("\n"));
      setPersonas(saved.personas);
      toast("Agent profile saved");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save", "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card stack" onSubmit={save}>
      <div>
        <span className="eyebrow">Agent profile</span>
        <p className="faint" style={{ fontSize: "0.82rem", marginTop: 4 }}>
          Who the agent is and who it talks to. Changes apply to new conversations.
        </p>
      </div>

      <div className="grid grid-2" style={{ gap: 14 }}>
        <div className="field">
          <label className="label" htmlFor="p-agent">Agent name</label>
          <input id="p-agent" className="input" value={agentName} maxLength={40}
            onChange={(e) => setAgentName(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="p-company">Company</label>
          <input id="p-company" className="input" value={company} maxLength={80}
            onChange={(e) => setCompany(e.target.value)} />
        </div>
      </div>
      <div className="field">
        <label className="label" htmlFor="p-voice">Voice <span className="faint">(how the agent sounds)</span></label>
        <input id="p-voice" className="input" value={voice} maxLength={300}
          onChange={(e) => setVoice(e.target.value)} />
      </div>
      <div className="field">
        <label className="label" htmlFor="p-closing">
          Tour closing example <span className="faint">(spoken at the end of the guided tour)</span>
        </label>
        <textarea id="p-closing" className="textarea" rows={3} value={closing} maxLength={800}
          placeholder="Leave empty for a short generic sign-off."
          onChange={(e) => setClosing(e.target.value)} />
      </div>

      <div className="divider" />
      <div className="row between">
        <div>
          <span className="label">Visitor personas</span>
          <p className="faint" style={{ fontSize: "0.8rem" }}>
            Segments the agent can recognise and tailor to. The slug is sent to your site&apos;s
            <span className="mono"> onSetPersona</span> hook. No personas means no persona switching.
          </p>
        </div>
        <button type="button" className="btn btn-sm" disabled={personas.length >= 8}
          onClick={() => setPersonas((ps) => [...ps, { ...EMPTY_PERSONA }])}>+ Add persona</button>
      </div>
      {personas.length === 0 && <div className="empty">No personas.</div>}
      {personas.map((p, i) => (
        <div key={i} className="card card-pad-sm">
          <div className="grid grid-2" style={{ gap: 10 }}>
            <input className="input" placeholder="Label, e.g. Developers" value={p.label} aria-label="Persona label"
              onChange={(e) => editPersona(i, { label: e.target.value })} />
            <input className="input mono" placeholder="slug, e.g. developers" value={p.slug} aria-label="Persona slug"
              onChange={(e) => editPersona(i, { slug: e.target.value.toLowerCase() })} />
            <input className="input" placeholder="Focus, e.g. APIs and integrations" value={p.focus} aria-label="Persona focus"
              onChange={(e) => editPersona(i, { focus: e.target.value })} />
            <input className="input" placeholder="Tone, e.g. precise and technical" value={p.tone} aria-label="Persona tone"
              onChange={(e) => editPersona(i, { tone: e.target.value })} />
            <input className="input mono" placeholder="Landing page, e.g. /for/developers" value={p.landing}
              aria-label="Persona landing page" onChange={(e) => editPersona(i, { landing: e.target.value })} />
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-ghost btn-sm btn-danger"
                onClick={() => setPersonas((ps) => ps.filter((_, j) => j !== i))}>Remove</button>
            </div>
          </div>
        </div>
      ))}

      <div className="divider" />
      <div className="grid grid-2" style={{ gap: 14 }}>
        <div className="field">
          <label className="label" htmlFor="p-routes">Pages the agent can open</label>
          <textarea id="p-routes" className="textarea mono" rows={6} value={routes}
            placeholder={"/\n/pricing\n/docs"} onChange={(e) => setRoutes(e.target.value)} />
          <span className="faint" style={{ fontSize: "0.78rem" }}>
            One path per line. URLs you ingest are added automatically.
          </span>
        </div>
        <div className="field">
          <label className="label" htmlFor="p-prefixes">Sections with many pages</label>
          <textarea id="p-prefixes" className="textarea mono" rows={6} value={prefixes}
            placeholder={"/blog/\n/docs/"} onChange={(e) => setPrefixes(e.target.value)} />
          <span className="faint" style={{ fontSize: "0.78rem" }}>
            Any page under these prefixes is allowed, e.g. /blog/ allows every post.
          </span>
        </div>
      </div>

      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save agent profile"}</button>
      </div>
    </form>
  );
}

// ---- danger zone -------------------------------------------------------------

function IntegrationsSection({ id }: { id: string }) {
  const [state, setState] = useState<{ cfg: Integrations | null } | null>(null);
  useEffect(() => {
    Api.getIntegrations(id).then((cfg) => setState({ cfg })).catch(() => setState({ cfg: null }));
  }, [id]);
  if (!state) return <div className="skeleton" style={{ height: 240 }} />;
  if (!state.cfg) return <div className="notice err">Couldn&apos;t load integrations.</div>;
  return <IntegrationsForm id={id} initial={state.cfg} />;
}

function IntegrationsForm({ id, initial }: { id: string; initial: Integrations }) {
  const toast = useToast();
  const [webhook, setWebhook] = useState(initial.webhook_url || "");
  const [slack, setSlack] = useState(initial.slack_webhook_url || "");
  const [hot, setHot] = useState(initial.hot_lead_score);
  const [secret, setSecret] = useState(initial.webhook_secret);
  const [busy, setBusy] = useState<"save" | "rotate" | "test" | null>(null);

  const save = async (rotate = false) => {
    setBusy(rotate ? "rotate" : "save");
    try {
      const cfg = await Api.saveIntegrations(id, {
        webhook_url: webhook.trim() || null, slack_webhook_url: slack.trim() || null,
        hot_lead_score: hot, rotate_secret: rotate,
      });
      setSecret(cfg.webhook_secret);
      toast(rotate ? "Signing secret rotated" : "Integrations saved");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not save integrations", "err");
    } finally {
      setBusy(null);
    }
  };

  const test = async () => {
    setBusy("test");
    try {
      const r = await Api.testIntegrations(id);
      toast(r.ok ? "Test lead sent" : `Test failed: ${r.error}`, r.ok ? undefined : "err");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Test failed", "err");
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="card" id="integrations">
      <h3 style={{ marginBottom: 4 }}>Lead integrations</h3>
      <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 16 }}>
        Every new lead is POSTed to your webhook (Zapier, Make, your CRM or your own endpoint),
        and hot leads ping Slack.
      </p>
      <div className="stack">
        <div className="field">
          <label className="label">Webhook URL</label>
          <input className="input mono" value={webhook} onChange={(e) => setWebhook(e.target.value)}
            placeholder="https://hooks.zapier.com/hooks/catch/…" />
        </div>
        <div className="field">
          <label className="label">Signing secret</label>
          <div className="row" style={{ gap: 8 }}>
            <input className="input mono" readOnly value={secret} aria-label="Signing secret" />
            <button type="button" className="btn btn-sm" onClick={() => save(true)} disabled={busy !== null}>
              {busy === "rotate" ? <Spinner /> : "Rotate"}
            </button>
          </div>
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
            Requests carry <span className="mono">X-FluidBuddha-Signature: t=…,v1=…</span> —
            HMAC-SHA256 of <span className="mono">{"{t}.{body}"}</span> with this secret.
          </p>
        </div>
        <div className="grid grid-2" style={{ gap: 12 }}>
          <div className="field">
            <label className="label">Slack incoming webhook</label>
            <input className="input mono" value={slack} onChange={(e) => setSlack(e.target.value)}
              placeholder="https://hooks.slack.com/services/…" />
          </div>
          <div className="field">
            <label className="label">Alert Slack when the score is at least</label>
            <input className="input" type="number" min={0} max={100} value={hot}
              onChange={(e) => setHot(Math.max(0, Math.min(100, Number(e.target.value) || 0)))} />
          </div>
        </div>
        <div className="row" style={{ gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn" onClick={test} disabled={busy !== null}>
            {busy === "test" ? <Spinner /> : "Send a test lead"}
          </button>
          <button type="button" className="btn btn-primary" onClick={() => save(false)} disabled={busy !== null}>
            {busy === "save" ? <Spinner /> : "Save integrations"}
          </button>
        </div>
      </div>
    </section>
  );
}

function DangerZone({ website }: { website: Website }) {
  const router = useRouter();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const remove = async () => {
    if (!window.confirm(
      `Delete "${website.name}"? This removes its knowledge, tour, cached answers, analytics, conversations and leads, ` +
      "and its widget key stops working. This can't be undone.",
    )) return;
    setBusy(true);
    try {
      await Api.deleteWebsite(website.id);
      toast("Website deleted");
      router.push("/dashboard");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not delete", "err");
      setBusy(false);
    }
  };

  return (
    <section className="card" style={{ borderColor: "rgba(248, 113, 113, 0.3)" }}>
      <div className="row between wrap" style={{ gap: 12 }}>
        <div>
          <span className="eyebrow" style={{ color: "var(--err)" }}>Delete website</span>
          <p className="faint" style={{ fontSize: "0.82rem", marginTop: 4 }}>
            Removes everything built for this site: knowledge, tour, cached answers, analytics, conversations, leads and the widget key.
          </p>
        </div>
        <button className="btn btn-danger btn-sm" onClick={remove} disabled={busy}>
          {busy ? <Spinner /> : "Delete website"}
        </button>
      </div>
    </section>
  );
}
