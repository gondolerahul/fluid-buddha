"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import {
  Api, ApiError, Campaign, CampaignAnalytics, CampaignIn, CampaignList, CampaignLogo, Testimonial,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Modal, Spinner, fmtDate, useToast } from "@/components/ui";

/** Generative landing pages (M3-1): a brief per campaign; a page per visitor. */
export default function CampaignsPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const { can } = useAuth();
  const editor = can("editor");
  const [data, setData] = useState<CampaignList | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [editing, setEditing] = useState<Campaign | "new" | null>(null);
  const load = useCallback(() => Api.campaigns(id).then(setData).catch(() => {}), [id]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <div className="skeleton" style={{ height: 240 }} />;
  const shown = data.campaigns.find((c) => c.id === picked) || data.campaigns[0] || null;

  return (
    <div className="fade-in stack">
      <div className="page-head row between wrap" style={{ gap: 12 }}>
        <div>
          <h2>Campaigns</h2>
          <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 720 }}>
            A landing page composed for each visitor from your own content: give it a goal, the audience and what it
            must say, and every link (per persona, per question, per account) gets its own grounded page — cited,
            using only the proof you supply, with your agent on it. Pages are cached, so most visits cost nothing.
          </p>
        </div>
        {editor && <button className="btn btn-primary btn-sm" onClick={() => setEditing("new")}>New campaign</button>}
      </div>

      <section className="card">
        {data.campaigns.length === 0 ? (
          <div className="empty">No campaigns yet. Create one for your next ad, email or outbound sequence.</div>
        ) : (
          <table className="table">
            <thead><tr><th>Campaign</th><th>Status</th><th>Views (30 days)</th><th>Conversions</th><th>Updated</th></tr></thead>
            <tbody>
              {data.campaigns.map((c) => (
                <tr key={c.id} onClick={() => setPicked(c.id)} style={{ cursor: "pointer",
                  background: shown?.id === c.id ? "var(--surface-2, rgba(255,255,255,0.04))" : undefined }}>
                  <td><div>{c.name}</div><div className="faint mono" style={{ fontSize: "0.78rem" }}>/{c.slug}</div></td>
                  <td><span className={`badge ${c.status === "live" ? "ok" : ""}`}>{c.status}</span>
                    {c.variant && <span className="badge" style={{ marginLeft: 6 }}>A/B</span>}</td>
                  <td className="mono">{c.views_30d ?? 0}</td>
                  <td className="mono">{c.conversions_30d ?? 0}</td>
                  <td>{fmtDate(c.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {shown && <CampaignCard key={shown.id} id={id} c={shown} personas={data.personas} editor={editor}
        onEdit={() => setEditing(shown)} onDeleted={() => { setPicked(null); load(); }} />}

      {editing && (
        <Modal open onClose={() => setEditing(null)} title={editing === "new" ? "New campaign" : `Edit “${editing.name}”`} width={760}>
          <CampaignForm id={id} list={data} initial={editing === "new" ? null : editing}
            onCancel={() => setEditing(null)}
            onSaved={(c) => { setEditing(null); setPicked(c.id); toast("Campaign saved"); load(); }} />
        </Modal>
      )}
    </div>
  );
}

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

function CampaignCard({ id, c, personas, editor, onEdit, onDeleted }: {
  id: string; c: Campaign; personas: { slug: string; label: string }[]; editor: boolean;
  onEdit: () => void; onDeleted: () => void;
}) {
  const toast = useToast();
  const [a, setA] = useState<CampaignAnalytics | null>(null);
  const [question, setQuestion] = useState("");
  const [account, setAccount] = useState("");
  const load = useCallback(() => Api.campaignAnalytics(id, c.id).then(setA).catch(() => {}), [id, c.id]);
  useEffect(() => { load(); }, [load]);
  const personaName = Object.fromEntries(personas.map((p) => [p.slug, p.label]));

  const copy = (text: string, what: string) =>
    navigator.clipboard.writeText(text).then(() => toast(`${what} copied`), () => toast("Copy failed", "err"));
  const link = (persona?: string) => {
    const q = new URLSearchParams();
    if (persona) q.set("persona", persona);
    if (question.trim()) q.set("q", question.trim());
    if (account.trim()) q.set("account", account.trim());
    const base = c.status === "live" ? c.url : c.preview_url;
    const s = q.toString();
    return s ? `${base}${base.includes("?") ? "&" : "?"}${s}` : base;
  };

  const clear = async () => {
    try {
      const r = await Api.clearCampaignCache(id, c.id);
      toast(`${r.cleared} cached page${r.cleared === 1 ? "" : "s"} cleared`);
      load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not clear it", "err");
    }
  };
  const remove = async () => {
    if (!window.confirm(`Delete “${c.name}”? Its link stops working and its numbers go.`)) return;
    try {
      await Api.deleteCampaign(id, c.id);
      toast("Campaign deleted");
      onDeleted();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not delete it", "err");
    }
  };

  const exp = a?.experiment;
  return (
    <section className="card stack">
      <div className="row between wrap" style={{ gap: 10 }}>
        <div>
          <span className="eyebrow">{c.status === "live" ? "Live" : c.status === "paused" ? "Paused" : "Draft"}
            {c.variant ? " · A/B test running" : ""}</span>
          <h3 style={{ marginTop: 4 }}>{c.name}</h3>
          {c.goal && <p className="faint" style={{ fontSize: "0.84rem" }}>Goal: {c.goal}</p>}
        </div>
        {editor && (
          <div className="row" style={{ gap: 8 }}>
            <button className="btn btn-sm" onClick={onEdit}>Edit</button>
            <button className="btn btn-sm" onClick={clear}>Clear cache</button>
            <button className="btn btn-sm btn-danger" onClick={remove}>Delete</button>
          </div>
        )}
      </div>

      <div className="stack-sm">
        <div className="row between" style={{ gap: 12 }}>
          <span className="eyebrow" style={{ minWidth: 90 }}>{c.status === "live" ? "Page" : "Preview"}</span>
          <code className="code" style={{ flex: 1, wordBreak: "break-all", padding: "6px 10px" }}>
            {c.status === "live" ? c.url : c.preview_url}</code>
          <button className="btn btn-sm" onClick={() => copy(c.status === "live" ? c.url : c.preview_url, "Link")}>Copy</button>
        </div>
        {c.status !== "live" && (
          <p className="faint" style={{ fontSize: "0.8rem" }}>
            Only this preview link opens the page until the campaign is live; previews aren&apos;t counted.
          </p>
        )}
      </div>

      <div className="stack-sm">
        <strong style={{ fontSize: "0.9rem" }}>Try it as a visitor</strong>
        <div className="row wrap" style={{ gap: 8 }}>
          <input className="input" style={{ flex: 2, minWidth: 220 }} placeholder="A question on the link (?q=), optional"
            value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={200} />
          <input className="input" style={{ flex: 1, minWidth: 160 }} placeholder="Account (?account=), optional"
            value={account} onChange={(e) => setAccount(e.target.value)} maxLength={60} />
        </div>
        <div className="row wrap" style={{ gap: 8 }}>
          <a className="btn btn-sm" href={link()} target="_blank" rel="noopener noreferrer">Open general page</a>
          {personas.map((p) => (
            <a key={p.slug} className="btn btn-sm" href={link(p.slug)} target="_blank" rel="noopener noreferrer">As {p.label}</a>
          ))}
        </div>
        <p className="faint" style={{ fontSize: "0.8rem" }}>
          Links also take <span className="mono">utm_content</span> (a persona), <span className="mono">utm_term</span> (a
          question) and <span className="mono">utm_source</span> (shown below). Add <span className="mono">lang=hi</span> for Hindi.
        </p>
      </div>

      <details>
        <summary style={{ cursor: "pointer", fontSize: "0.9rem" }}>Embed on your own page</summary>
        <div className="stack-sm" style={{ marginTop: 10 }}>
          <code className="code" style={{ display: "block", whiteSpace: "pre-wrap", padding: "8px 10px" }}>{c.embed_snippet}</code>
          <div className="row between" style={{ gap: 8 }}>
            <span className="faint" style={{ fontSize: "0.8rem" }}>{c.embed_note}</span>
            <button className="btn btn-sm" onClick={() => copy(c.embed_snippet, "Embed code")}>Copy</button>
          </div>
        </div>
      </details>

      {!a ? <div className="skeleton" style={{ height: 120 }} /> : (
        <div className="stack">
          <div className="grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            {([["Visitors", a.total.views], ["Engaged", a.total.engaged], ["Converted", a.total.converted],
               ["Conversion", pct(a.total.conversion_rate)], ["Served from cache", pct(a.cache.hit_rate)]] as const).map(([k, v]) => (
              <div key={k} className="card" style={{ padding: "12px 14px" }}>
                <div className="faint" style={{ fontSize: "0.78rem" }}>{k} · {a.days} days</div>
                <div className="mono" style={{ fontSize: "1.3rem", marginTop: 4 }}>{v}</div>
              </div>
            ))}
          </div>

          {c.variant && (
            <div className="stack-sm">
              <strong style={{ fontSize: "0.9rem" }}>A/B test</strong>
              <div role="status" style={{ padding: "10px 14px", borderRadius: 10, fontSize: "0.9rem",
                background: exp?.status === "winner" ? "rgba(60,170,110,0.12)" : "rgba(255,255,255,0.04)" }}>
                {exp?.status === "winner" ? `Version ${exp.winner?.toUpperCase()} converts better, and that holds however often you've looked.`
                  : exp?.status === "no_difference" ? "No difference between the versions."
                  : "Keep running: not enough evidence yet to call a winner."}
              </div>
              <Breakdown rows={a.by_arm.map((r) => ({ ...r, label: r.arm === "b" ? `B — ${c.variant?.headline || "variant"}` : "A — original" }))} />
            </div>
          )}

          <div className="grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 16 }}>
            <div className="stack-sm">
              <strong style={{ fontSize: "0.9rem" }}>By persona</strong>
              <Breakdown rows={a.by_persona.map((r) => ({ ...r, label: r.persona ? personaName[r.persona] || r.persona : "General" }))} />
            </div>
            <div className="stack-sm">
              <strong style={{ fontSize: "0.9rem" }}>By source</strong>
              <Breakdown rows={a.by_source.map((r) => ({ ...r, label: r.source || "Direct / unknown" }))} />
            </div>
          </div>
          <p className="faint" style={{ fontSize: "0.8rem" }}>
            {a.cache.pages} page{a.cache.pages === 1 ? "" : "s"} composed (about {a.cache.avg_build_ms} ms each),
            served {a.cache.hits} more time{a.cache.hits === 1 ? "" : "s"} from the cache. A page is composed again when you
            edit the campaign or your content is re-ingested. Engaged: scrolled, stayed 15 s or used a component or the
            agent. Converted: sent the form or clicked the call to action.
          </p>
        </div>
      )}
    </section>
  );
}

function Breakdown({ rows }: { rows: { label: string; views: number; engaged: number; converted: number; conversion_rate: number }[] }) {
  if (!rows.length) return <div className="faint" style={{ fontSize: "0.85rem" }}>No visits yet.</div>;
  return (
    <table className="table">
      <thead><tr><th /><th>Visitors</th><th>Engaged</th><th>Converted</th><th>Rate</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label}><td>{r.label}</td><td className="mono">{r.views}</td><td className="mono">{r.engaged}</td>
            <td className="mono">{r.converted}</td><td className="mono">{pct(r.conversion_rate)}</td></tr>
        ))}
      </tbody>
    </table>
  );
}

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

function CampaignForm({ id, list, initial, onCancel, onSaved }: {
  id: string; list: CampaignList; initial: Campaign | null; onCancel: () => void; onSaved: (c: Campaign) => void;
}) {
  const toast = useToast();
  const [f, setF] = useState<CampaignIn>(() => initial ? { ...initial } : {
    name: "", status: "draft", goal: "", audience: "", persona: null, key_messages: [], sections: list.default_sections,
    cta_label: "", cta_url: "", testimonials: [], logos: [], variant: null, embed_origins: [],
  });
  const [slug, setSlug] = useState(initial?.slug || "");
  const [messages, setMessages] = useState((initial?.key_messages || []).join("\n"));
  const [variantMessages, setVariantMessages] = useState((initial?.variant?.key_messages || []).join("\n"));
  const [origins, setOrigins] = useState((initial?.embed_origins || []).join("\n"));
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof CampaignIn>(k: K, v: CampaignIn[K]) => setF((x) => ({ ...x, [k]: v }));
  const sectionLabels = useMemo(() => Object.fromEntries(list.sections.map((s) => [s.type, s.label])), [list.sections]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const body: CampaignIn = {
      ...f, slug: slug.trim() || undefined, key_messages: lines(messages), embed_origins: lines(origins),
      variant: f.variant ? { ...f.variant, key_messages: lines(variantMessages) } : null,
    };
    try {
      onSaved(initial ? await Api.saveCampaign(id, initial.id, body) : await Api.createCampaign(id, body));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save it", "err");
    } finally {
      setBusy(false);
    }
  };

  const setTestimonial = (i: number, patch: Partial<Testimonial>) =>
    set("testimonials", f.testimonials.map((t, j) => (j === i ? { ...t, ...patch } : t)));
  const setLogo = (i: number, patch: Partial<CampaignLogo>) =>
    set("logos", f.logos.map((t, j) => (j === i ? { ...t, ...patch } : t)));

  return (
    <form className="stack" onSubmit={save}>
      <div className="row wrap" style={{ gap: 12 }}>
        <div className="field" style={{ flex: 2, minWidth: 220 }}>
          <label className="label">Name</label>
          <input className="input" required maxLength={120} value={f.name} onChange={(e) => set("name", e.target.value)}
            placeholder="Orbit for healthcare — Q4 ads" />
        </div>
        <div className="field" style={{ flex: 1, minWidth: 160 }}>
          <label className="label">Link name</label>
          <input className="input mono" maxLength={60} value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase())}
            placeholder="from the name" />
        </div>
        <div className="field" style={{ width: 130 }}>
          <label className="label">Status</label>
          <select className="select" value={f.status} onChange={(e) => set("status", e.target.value as CampaignIn["status"])}>
            <option value="draft">Draft</option><option value="live">Live</option><option value="paused">Paused</option>
          </select>
        </div>
      </div>
      <div className="field">
        <label className="label">Goal</label>
        <input className="input" maxLength={500} value={f.goal} onChange={(e) => set("goal", e.target.value)}
          placeholder="Book demos with clinic owners" />
      </div>
      <div className="row wrap" style={{ gap: 12 }}>
        <div className="field" style={{ flex: 2, minWidth: 240 }}>
          <label className="label">Audience</label>
          <input className="input" maxLength={300} value={f.audience} onChange={(e) => set("audience", e.target.value)}
            placeholder="Clinics and small hospitals in India" />
        </div>
        <div className="field" style={{ flex: 1, minWidth: 180 }}>
          <label className="label">Persona when the link names none</label>
          <select className="select" value={f.persona || ""} onChange={(e) => set("persona", e.target.value || null)}>
            <option value="">General visitor</option>
            {list.personas.map((p) => <option key={p.slug} value={p.slug}>{p.label}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label className="label">Key messages, one per line (the first is the headline)</label>
        <textarea className="input" rows={4} value={messages} onChange={(e) => setMessages(e.target.value)}
          placeholder={"Scheduling that fills every slot\nReminders cut no-shows"} />
        <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>
          Facts and numbers on the page come only from your knowledge (cited); these steer what it says.
        </p>
      </div>
      <div className="field">
        <label className="label">Sections the page may use</label>
        <div className="row wrap" style={{ gap: 12 }}>
          {list.sections.map((s) => (
            <label key={s.type} className="row" style={{ gap: 6, fontSize: "0.86rem" }}>
              <input type="checkbox" checked={f.sections.includes(s.type)}
                onChange={(e) => set("sections", e.target.checked ? [...f.sections, s.type] : f.sections.filter((x) => x !== s.type))} />
              {sectionLabels[s.type]}
            </label>
          ))}
        </div>
      </div>
      <div className="row wrap" style={{ gap: 12 }}>
        <div className="field" style={{ flex: 1, minWidth: 180 }}>
          <label className="label">Call to action</label>
          <input className="input" maxLength={60} value={f.cta_label} onChange={(e) => set("cta_label", e.target.value)} placeholder="Book a demo" />
        </div>
        <div className="field" style={{ flex: 2, minWidth: 240 }}>
          <label className="label">Its link (https; empty = the page&apos;s form)</label>
          <input className="input" maxLength={500} value={f.cta_url} onChange={(e) => set("cta_url", e.target.value)}
            placeholder="https://your-site.com/demo" />
        </div>
      </div>

      <div className="field">
        <label className="label">Testimonials — quoted exactly, never written for you</label>
        {f.testimonials.map((t, i) => (
          <div key={i} className="row wrap" style={{ gap: 8, marginBottom: 6 }}>
            <input className="input" style={{ flex: 3, minWidth: 220 }} placeholder="Quote" maxLength={400} value={t.quote}
              onChange={(e) => setTestimonial(i, { quote: e.target.value })} />
            <input className="input" style={{ flex: 1, minWidth: 120 }} placeholder="Name" maxLength={80} value={t.name}
              onChange={(e) => setTestimonial(i, { name: e.target.value })} />
            <input className="input" style={{ flex: 1, minWidth: 120 }} placeholder="Role, company" maxLength={80} value={t.role || ""}
              onChange={(e) => setTestimonial(i, { role: e.target.value })} />
            <button type="button" className="btn btn-sm" onClick={() => set("testimonials", f.testimonials.filter((_, j) => j !== i))}>Remove</button>
          </div>
        ))}
        {f.testimonials.length < 8 && <button type="button" className="btn btn-sm"
          onClick={() => set("testimonials", [...f.testimonials, { quote: "", name: "", role: "" }])}>Add testimonial</button>}
      </div>
      <div className="field">
        <label className="label">Customer logos (https image links)</label>
        {f.logos.map((lg, i) => (
          <div key={i} className="row wrap" style={{ gap: 8, marginBottom: 6 }}>
            <input className="input" style={{ flex: 3, minWidth: 220 }} placeholder="https://…/logo.svg" maxLength={500} value={lg.src}
              onChange={(e) => setLogo(i, { src: e.target.value })} />
            <input className="input" style={{ flex: 1, minWidth: 120 }} placeholder="Company" maxLength={80} value={lg.alt}
              onChange={(e) => setLogo(i, { alt: e.target.value })} />
            <button type="button" className="btn btn-sm" onClick={() => set("logos", f.logos.filter((_, j) => j !== i))}>Remove</button>
          </div>
        ))}
        {f.logos.length < 12 && <button type="button" className="btn btn-sm"
          onClick={() => set("logos", [...f.logos, { src: "", alt: "" }])}>Add logo</button>}
      </div>

      <div className="field">
        <label className="row" style={{ gap: 8, fontSize: "0.9rem" }}>
          <input type="checkbox" checked={!!f.variant} onChange={(e) => set("variant", e.target.checked ? { headline: "", cta_label: "" } : null)} />
          A/B test a second version (half the visitors see it; measured on conversions)
        </label>
        {f.variant && (
          <div className="stack-sm" style={{ marginTop: 8 }}>
            <input className="input" maxLength={160} placeholder="Version B headline" value={f.variant.headline || ""}
              onChange={(e) => set("variant", { ...f.variant, headline: e.target.value })} />
            <textarea className="input" rows={3} placeholder="Version B key messages, one per line (empty = the same)"
              value={variantMessages} onChange={(e) => setVariantMessages(e.target.value)} />
            <input className="input" maxLength={60} placeholder="Version B call to action (empty = the same)"
              value={f.variant.cta_label || ""} onChange={(e) => set("variant", { ...f.variant, cta_label: e.target.value })} />
          </div>
        )}
      </div>
      <div className="field">
        <label className="label">Other sites that may embed it (one https origin per line)</label>
        <textarea className="input" rows={2} value={origins} onChange={(e) => setOrigins(e.target.value)}
          placeholder="https://partner.example.com" />
        <p className="faint" style={{ fontSize: "0.78rem", marginTop: 4 }}>Your own domain may always embed it.</p>
      </div>

      <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Save campaign"}</button>
      </div>
    </form>
  );
}
