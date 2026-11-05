"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AgentProfile, Api, ApiError, Integrations, Persona, Privacy, Website, TemplatePlan, TemplateSummary } from "@/lib/api";
import { useWebsite } from "@/components/WebsiteContext";
import { Spinner, useToast } from "@/components/ui";
import { EditOnly, Editable } from "@/components/Permission";

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
      <Editable><SiteForm key={website.id} website={website} onSaved={reload} /></Editable>
      <Editable><ProfileSection id={website.id} /></Editable>
      {/* Integrations hold the signing secret: Admins only, even to look. */}
      <EditOnly role="admin"><IntegrationsSection id={website.id} /></EditOnly>
      <Editable role="admin"><PrivacySection id={website.id} /></Editable>
      <EditOnly role="admin"><DangerZone website={website} /></EditOnly>
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
  const [version, setVersion] = useState(0);
  useEffect(() => {
    Api.getProfile(id)
      .then((profile) => setState({ profile, error: false }))
      .catch(() => setState({ profile: null, error: true }));
  }, [id, version]);

  if (!state) return <div className="skeleton" style={{ height: 320 }} />;
  if (!state.profile) return <div className="notice err">Couldn&apos;t load the agent profile.</div>;
  return <>
    <TemplateCard id={id} current={state.profile.template?.id} onApplied={() => setVersion((v) => v + 1)} />
    <ProfileForm key={version} id={id} initial={state.profile} />
  </>;
}

/** Start from (or switch to) a vertical template (M2-9): preview, then apply. */
function TemplateCard({ id, current, onApplied }: { id: string; current?: string; onApplied: () => void }) {
  const toast = useToast();
  const [list, setList] = useState<TemplateSummary[] | null>(null);
  const [pick, setPick] = useState(current ?? "");
  const [plan, setPlan] = useState<TemplatePlan | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { Api.templates().then((r) => setList(r.templates)).catch(() => setList([])); }, []);
  const name = (tid?: string) => list?.find((t) => t.id === tid)?.name ?? tid;
  const show = (v: unknown) => (Array.isArray(v) ? v.join(" · ") : v === "medical" ? "on" : String(v));

  return (
    <section className="card">
      <h3 style={{ marginBottom: 4 }}>Template</h3>
      <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 12 }}>
        {current ? <>Started from <b>{name(current)}</b>. </> : null}
        A template fills in personas, starter questions, rules, triggers and what the tour covers for a kind of
        business. Anything you&apos;ve changed by hand is kept.
      </p>
      <div className="row" style={{ gap: 8 }}>
        <select className="select" style={{ maxWidth: 280 }} value={pick} aria-label="Template"
          onChange={(e) => { setPick(e.target.value); setPlan(null); }}>
          <option value="">Choose a template…</option>
          {(list ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <button className="btn btn-sm" disabled={!pick} onClick={async () => {
          try { setPlan(await Api.previewTemplate(id, pick)); } catch { toast("Could not preview", "err"); }
        }}>Preview changes</button>
      </div>
      {plan && (
        <div className="stack" style={{ marginTop: 14, fontSize: "0.86rem" }}>
          {plan.set.length > 0 && <div><span className="eyebrow">Will set</span>
            <ul style={{ margin: "4px 0 0 18px" }}>{plan.set.map((s) => <li key={s.field}><b>{s.label}:</b> {show(s.value)}</li>)}</ul></div>}
          {plan.personas_added.length > 0 && <div><span className="eyebrow">Adds personas</span>
            <div>{plan.personas_added.map((p) => p.label).join(", ")}</div></div>}
          {plan.triggers_added.length > 0 && <div><span className="eyebrow">Adds triggers</span>
            <div>{plan.triggers_added.join(", ")}</div></div>}
          {plan.kept.length > 0 && <div><span className="eyebrow">Keeps your edits to</span>
            <div>{plan.kept.map((k) => k.label).join(", ")}</div></div>}
          {plan.suggested_actions.length > 0 && <div><span className="eyebrow">Suggested actions (set up under Actions)</span>
            <ul style={{ margin: "4px 0 0 18px" }}>{plan.suggested_actions.map((a) => <li key={a.label}><b>{a.label}</b> — {a.why}</li>)}</ul></div>}
          {!plan.set.length && !plan.personas_added.length && !plan.triggers_added.length
            ? <div className="faint">Nothing to change.</div> : (
            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button className="btn btn-primary btn-sm" disabled={busy} onClick={async () => {
                setBusy(true);
                try { await Api.applyTemplate(id, pick); toast("Template applied"); setPlan(null); onApplied(); }
                catch { toast("Could not apply", "err"); }
                finally { setBusy(false); }
              }}>{busy ? <Spinner /> : "Apply"}</button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

const EMPTY_PERSONA: Persona = { slug: "", label: "", focus: "", tone: "", landing: "" };

function ProfileForm({ id, initial }: { id: string; initial: AgentProfile }) {
  const toast = useToast();
  const [agentName, setAgentName] = useState(initial.agent_name);
  const [company, setCompany] = useState(initial.company_name);
  const [voice, setVoice] = useState(initial.brand_voice);
  const [closing, setClosing] = useState(initial.closing_use_case);
  const [greeting, setGreeting] = useState(initial.greeting ?? "");
  const [startPersona, setStartPersona] = useState(initial.default_persona ?? "");
  const [tourOn, setTourOn] = useState(initial.tour_enabled ?? true);
  const [ctaLabel, setCtaLabel] = useState(initial.cta_label ?? "");
  const [ctaUrl, setCtaUrl] = useState(initial.cta_url ?? "");
  const [hindi, setHindi] = useState((initial.languages ?? []).includes("hi"));
  const [widgetLang, setWidgetLang] = useState(initial.widget_language ?? "auto");
  const [greetingHi, setGreetingHi] = useState(initial.greeting_hi ?? "");
  const [starters, setStarters] = useState((initial.starter_questions ?? []).join("\n"));
  const [startersHi, setStartersHi] = useState((initial.starter_questions_hi ?? []).join("\n"));
  const [currency, setCurrency] = useState(initial.currency ?? "INR");
  const [rules, setRules] = useState((initial.guardrails ?? []).join("\n"));
  const [medical, setMedical] = useState(initial.safety === "medical");
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
        greeting: greeting.trim(),
        default_persona: startPersona,
        tour_enabled: tourOn,
        cta_label: ctaLabel.trim(),
        cta_url: ctaUrl.trim(),
        languages: hindi ? ["en", "hi"] : ["en"],
        widget_language: widgetLang,
        greeting_hi: greetingHi.trim(),
        starter_questions: lines(starters).slice(0, 4),
        starter_questions_hi: lines(startersHi).slice(0, 4),
        currency,
        guardrails: lines(rules).slice(0, 10),
        safety: medical ? "medical" : "",
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
      setStartPersona(saved.default_persona ?? "");
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
        <label className="label" htmlFor="p-greeting">
          Greeting <span className="faint">(the first thing the agent says when opened)</span>
        </label>
        <input id="p-greeting" className="input" value={greeting} maxLength={300}
          placeholder="Leave empty and the agent writes a short welcome for each page."
          onChange={(e) => setGreeting(e.target.value)} />
      </div>
      <div className="grid grid-2" style={{ gap: 14 }}>
        <div className="field">
          <label className="label" htmlFor="p-start-persona">Start conversations as</label>
          <select id="p-start-persona" className="select" value={startPersona}
            onChange={(e) => setStartPersona(e.target.value)}>
            <option value="">Work it out from the conversation</option>
            {personas.filter((p) => p.slug).map((p) => <option key={p.slug} value={p.slug}>{p.label || p.slug}</option>)}
          </select>
        </div>
        <label className="row" style={{ gap: 8, fontSize: "0.88rem", alignSelf: "end", paddingBottom: 10 }}>
          <input type="checkbox" checked={tourOn} onChange={(e) => setTourOn(e.target.checked)} />
          Offer the guided tour when the agent is opened
        </label>
      </div>
      <div className="field">
        <span className="label">Languages</span>
        <label className="row" style={{ gap: 8, fontSize: "0.88rem" }}>
          <input type="checkbox" checked={hindi} onChange={(e) => setHindi(e.target.checked)} />
          Answer in Hindi when a visitor asks in Hindi
        </label>
        <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
          English is always on. Hindi questions are answered in Hindi, by voice too; product names, prices and
          sources stay as written. Hindi typed in English letters (&ldquo;pricing kya hai?&rdquo;) gets a simple
          English answer unless the visitor prefers Hindi.
        </p>
      </div>
      {hindi && (
        <div className="grid grid-2" style={{ gap: 14 }}>
          <div className="field">
            <label className="label" htmlFor="p-widget-lang">Widget buttons and labels</label>
            <select id="p-widget-lang" className="select" value={widgetLang}
              onChange={(e) => setWidgetLang(e.target.value as "auto" | "en" | "hi")}>
              <option value="auto">Match the visitor&apos;s browser</option>
              <option value="en">Always English</option>
              <option value="hi">Always Hindi</option>
            </select>
          </div>
          <div className="field">
            <label className="label" htmlFor="p-greeting-hi">Greeting in Hindi <span className="faint">(optional)</span></label>
            <input id="p-greeting-hi" className="input" lang="hi" value={greetingHi} maxLength={300}
              placeholder="नमस्ते! पूछिए, मैं मदद करती हूँ।" onChange={(e) => setGreetingHi(e.target.value)} />
          </div>
        </div>
      )}
      <div className="grid grid-2" style={{ gap: 14 }}>
        <div className="field">
          <label className="label" htmlFor="p-cta-label">Next step button <span className="faint">(on recap pages)</span></label>
          <input id="p-cta-label" className="input" value={ctaLabel} maxLength={60} placeholder="Book a demo"
            onChange={(e) => setCtaLabel(e.target.value)} />
        </div>
        <div className="field">
          <label className="label" htmlFor="p-cta-url">Its link</label>
          <input id="p-cta-url" className="input" type="url" value={ctaUrl} maxLength={500}
            placeholder="https://yoursite.com/demo" onChange={(e) => setCtaUrl(e.target.value)} />
        </div>
      </div>
      <div className="grid grid-2" style={{ gap: 14 }}>
        <div className="field">
          <label className="label" htmlFor="p-starters">Starter questions <span className="faint">(the widget&apos;s chips, one per line, up to 4)</span></label>
          <textarea id="p-starters" className="textarea" rows={4} value={starters} onChange={(e) => setStarters(e.target.value)}
            placeholder={"How much does it cost?\nIs there a free trial?"} />
          <label className="label" htmlFor="p-starters-hi" style={{ marginTop: 10 }}>
            Starter questions in Hindi <span className="faint">(chips for Hindi widgets)</span>
          </label>
          <textarea id="p-starters-hi" className="textarea" rows={3} value={startersHi}
            onChange={(e) => setStartersHi(e.target.value)} placeholder={"इसकी कीमत क्या है?\nक्या फ़्री ट्रायल है?"} />
          <label className="label" htmlFor="p-currency" style={{ marginTop: 10 }}>
            Currency <span className="faint">(calculators and configurators)</span>
          </label>
          <select id="p-currency" className="select" value={currency} onChange={(e) => setCurrency(e.target.value)}>
            {["INR", "USD", "EUR", "GBP", "AED", "SGD", "AUD"].map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="label" htmlFor="p-rules">Rules the agent always follows <span className="faint">(one per line)</span></label>
          <textarea id="p-rules" className="textarea" rows={4} value={rules} onChange={(e) => setRules(e.target.value)}
            placeholder="Never promise discounts the site doesn't mention." />
        </div>
      </div>
      <label className="row" style={{ gap: 8, fontSize: "0.88rem" }}>
        <input type="checkbox" checked={medical} onChange={(e) => setMedical(e.target.checked)} />
        Medical safety: never give medical advice, diagnoses or doses; send urgent cases to 112
      </label>
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
  const [costAlert, setCostAlert] = useState(initial.cost_alert_usd == null ? "" : String(initial.cost_alert_usd));
  const [secret, setSecret] = useState(initial.webhook_secret);
  const [busy, setBusy] = useState<"save" | "rotate" | "test" | null>(null);

  const save = async (rotate = false) => {
    const alertUsd = Number(costAlert);
    if (costAlert.trim() && !(alertUsd > 0)) {
      toast("The cost alert must be an amount above zero, or empty", "err");
      return;
    }
    setBusy(rotate ? "rotate" : "save");
    try {
      const cfg = await Api.saveIntegrations(id, {
        webhook_url: webhook.trim() || null, slack_webhook_url: slack.trim() || null,
        hot_lead_score: hot, cost_alert_usd: costAlert.trim() ? alertUsd : null, rotate_secret: rotate,
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
        <div className="field">
          <label className="label">Cost alert <span className="faint">(optional, USD per day)</span></label>
          <input className="input" inputMode="decimal" value={costAlert} placeholder="e.g. 5"
            aria-label="Daily cost alert in USD" onChange={(e) => setCostAlert(e.target.value)} />
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
            Ping Slack (and list it on Analytics) the first time a day this site&apos;s AI cost passes this
            amount. You are also alerted at 80% and 100% of the daily spend cap, if one is set.
          </p>
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

const TRANSCRIPT_DAYS = [30, 90, 180, 365, 0];
const LEAD_DAYS = [90, 180, 365, 730, 0];
const RECAP_DAYS = [7, 30, 90, 180, 365];
const daysLabel = (d: number) => (d === 0 ? "Keep until deleted" : d >= 365 ? `${d / 365} year${d > 365 ? "s" : ""}` : `${d} days`);

function PrivacySection({ id }: { id: string }) {
  const [state, setState] = useState<{ cfg: Privacy | null } | null>(null);
  useEffect(() => {
    Api.getPrivacy(id).then((cfg) => setState({ cfg })).catch(() => setState({ cfg: null }));
  }, [id]);
  if (!state) return <div className="skeleton" style={{ height: 260 }} />;
  if (!state.cfg) return <div className="notice err">Couldn&apos;t load privacy settings.</div>;
  return <PrivacyForm id={id} initial={state.cfg} />;
}

function PrivacyForm({ id, initial }: { id: string; initial: Privacy }) {
  const toast = useToast();
  const [cfg, setCfg] = useState<Privacy>(initial);
  const [busy, setBusy] = useState(false);
  const [erase, setErase] = useState("");
  const [erasing, setErasing] = useState(false);
  const set = <K extends keyof Privacy>(k: K, v: Privacy[K]) => setCfg((c) => ({ ...c, [k]: v }));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      setCfg(await Api.savePrivacy(id, {
        ...cfg, privacy_policy_url: cfg.privacy_policy_url?.trim() || null,
      }));
      toast("Privacy settings saved");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save privacy settings", "err");
    } finally {
      setBusy(false);
    }
  };

  const eraseVisitor = async (e: React.FormEvent) => {
    e.preventDefault();
    const email = erase.trim();
    if (!email || !window.confirm(
      `Delete every lead for ${email} and the conversations they came from? This can't be undone.`,
    )) return;
    setErasing(true);
    try {
      const r = await Api.eraseVisitor(id, email);
      toast(r.leads ? `Deleted ${r.leads} lead${r.leads === 1 ? "" : "s"} and ${r.conversations} conversation${r.conversations === 1 ? "" : "s"}`
        : "No leads with that email");
      setErase("");
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not delete that visitor's data", "err");
    } finally {
      setErasing(false);
    }
  };

  return (
    <section className="card" id="privacy">
      <h3 style={{ marginBottom: 4 }}>Privacy &amp; data</h3>
      <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 16 }}>
        What the agent stores about visitors, for how long, and what they agree to before voice.
      </p>
      <form onSubmit={save} className="stack">
        <label className="check">
          <input type="checkbox" checked={cfg.redact_pii} onChange={(e) => set("redact_pii", e.target.checked)} />
          <span>
            Mask personal details
            <span className="faint">Emails, phone, card, ID and bank numbers are replaced before the AI
              sees them and before transcripts are saved. Leads still get the email the visitor gave.</span>
          </span>
        </label>
        <label className="check">
          <input type="checkbox" checked={cfg.consent_required}
            onChange={(e) => set("consent_required", e.target.checked)} />
          <span>
            Ask before using the microphone
            <span className="faint">Visitors see what voice means and choose to allow it or type.
              Turn off only if your site&apos;s own consent banner already covers it.</span>
          </span>
        </label>
        <div className="field">
          <label className="label">Privacy policy link <span className="faint">(shown in the consent prompt)</span></label>
          <input className="input" type="url" value={cfg.privacy_policy_url ?? ""}
            onChange={(e) => set("privacy_policy_url", e.target.value)} placeholder="https://example.com/privacy" />
        </div>
        <div className="grid grid-2" style={{ gap: 12 }}>
          <div className="field">
            <label className="label">Keep transcripts for</label>
            <select className="select" value={cfg.transcript_retention_days}
              onChange={(e) => set("transcript_retention_days", Number(e.target.value))}>
              {TRANSCRIPT_DAYS.map((d) => <option key={d} value={d}>{daysLabel(d)}</option>)}
            </select>
            <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
              Older conversations and cached answers are deleted. Pinned answers stay.
            </p>
          </div>
          <div className="field">
            <label className="label">Keep leads for</label>
            <select className="select" value={cfg.lead_retention_days}
              onChange={(e) => set("lead_retention_days", Number(e.target.value))}>
              {LEAD_DAYS.map((d) => <option key={d} value={d}>{daysLabel(d)}</option>)}
            </select>
          </div>
          <div className="field">
            <label className="label">Recap links work for</label>
            <select className="select" value={cfg.recap_days ?? 90}
              onChange={(e) => set("recap_days", Number(e.target.value))}>
              {RECAP_DAYS.map((d) => <option key={d} value={d}>{daysLabel(d)}</option>)}
            </select>
            <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
              A recap also goes when its conversation is deleted.
            </p>
          </div>
        </div>
        <div className="field">
          <label className="row" style={{ gap: 8, fontSize: "0.9rem" }}>
            <input type="checkbox" checked={!!cfg.memory_enabled}
              onChange={(e) => set("memory_enabled", e.target.checked)} />
            Remember returning visitors who ask to be remembered
          </label>
          <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
            The agent asks once; visitors who say yes are welcomed back with what they explored last time (topics,
            components, open questions — never their details), on this site only. They can say &ldquo;forget me&rdquo;
            any time. Switching this off deletes every memory.
          </p>
          {cfg.memory_enabled && (
            <div className="row" style={{ gap: 8, marginTop: 8, alignItems: "center" }}>
              <span className="faint" style={{ fontSize: "0.84rem" }}>Keep a memory for</span>
              <select className="select" style={{ width: "auto" }} value={cfg.memory_days ?? 180}
                onChange={(e) => set("memory_days", Number(e.target.value))}>
                {[30, 90, 180, 365].map((d) => <option key={d} value={d}>{daysLabel(d)}</option>)}
              </select>
              <span className="faint" style={{ fontSize: "0.84rem" }}>after their last visit</span>
            </div>
          )}
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save privacy settings"}</button>
        </div>
      </form>

      <form onSubmit={eraseVisitor} className="stack-sm" style={{ marginTop: 18, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
        <label className="label">Delete a visitor&apos;s data</label>
        <p className="faint" style={{ fontSize: "0.78rem" }}>
          For a deletion request: removes their leads and the conversations those leads came from.
        </p>
        <div className="row" style={{ gap: 8 }}>
          <input className="input" type="email" value={erase} onChange={(e) => setErase(e.target.value)}
            placeholder="visitor@example.com" aria-label="Visitor email" />
          <button className="btn btn-danger btn-sm" disabled={erasing || !erase.trim()}>
            {erasing ? <Spinner /> : "Delete data"}
          </button>
        </div>
      </form>
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
