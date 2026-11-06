"use client";
/**
 * Design system (P0-7): the brand tokens generated pages are themed with, and
 * the "tunables" personalisation may vary within. Saving here takes precedence
 * over a design-system file and the tokens read off the site at onboarding.
 */
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Api, ApiError, DesignSystemInput, DesignSystemView, Tunable } from "@/lib/api";
import { Spinner, fmtDate, useToast } from "@/components/ui";
import { EditOnly, Editable } from "@/components/Permission";

const COLOR_KEYS = ["primary", "secondary", "accent", "background", "surface", "text", "muted"];
const AXES: { key: string; label: string; options: string[] }[] = [
  { key: "density", label: "Density", options: ["airy", "balanced", "compact"] },
  { key: "scheme", label: "Colour scheme", options: ["light", "dark", "auto"] },
  { key: "motion", label: "Motion", options: ["calm", "standard", "lively"] },
  { key: "type_scale", label: "Type scale", options: ["small", "standard", "large"] },
];
const SOURCE_LABEL: Record<DesignSystemView["source"], string> = {
  console: "Saved here",
  file: "From a design-system file on the server",
  extracted: "Read off your website at onboarding",
  default: "FluidBuddha defaults",
};

type Form = {
  name: string; logo_url: string; colors: Record<string, string>; font_family: string;
  heading_family: string; base_size: string; scale: string; radius: string; brand_voice: string;
  tunables: Record<string, Tunable>;
};

function toForm(v: DesignSystemView): Form {
  const e = v.effective;
  return {
    name: e.name || "", logo_url: e.logo_url || "",
    colors: Object.fromEntries(COLOR_KEYS.map((k) => [k, e.colors?.[k] || "#000000"])),
    font_family: String(e.typography?.font_family ?? ""), heading_family: String(e.typography?.heading_family ?? ""),
    base_size: String(e.typography?.base_size ?? "16px"), scale: String(e.typography?.scale ?? "1.25"),
    radius: e.radius || "", brand_voice: e.brand_voice || "",
    tunables: v.current?.data.tunables || e.tunables || {},
  };
}

function toInput(f: Form): DesignSystemInput {
  return {
    name: f.name, logo_url: f.logo_url, colors: f.colors, radius: f.radius, brand_voice: f.brand_voice,
    typography: { font_family: f.font_family, heading_family: f.heading_family, base_size: f.base_size,
      scale: Number(f.scale) || 1.25 },
    tunables: Object.fromEntries(Object.entries(f.tunables).filter(([, t]) => t.allowed.length > 0)),
  };
}

export default function DesignPage() {
  const id = String(useParams().id);
  const toast = useToast();
  const [view, setView] = useState<DesignSystemView | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [busy, setBusy] = useState(false);

  const apply = (v: DesignSystemView) => { setView(v); setForm(toForm(v)); };
  useEffect(() => { Api.getDesignSystem(id).then(apply).catch(() => toast("Could not load the design system", "err")); },
    [id, toast]);

  const set = (patch: Partial<Form>) => setForm((f) => (f ? { ...f, ...patch } : f));
  const toggleTunable = (axis: string, option: string) => setForm((f) => {
    if (!f) return f;
    const cur = f.tunables[axis] || { allowed: [], default: null };
    const allowed = cur.allowed.includes(option) ? cur.allowed.filter((o) => o !== option) : [...cur.allowed, option];
    const def = cur.default && allowed.includes(cur.default) ? cur.default : allowed[0] ?? null;
    return { ...f, tunables: { ...f.tunables, [axis]: { allowed, default: def } } };
  });

  const save = async () => {
    if (!form) return;
    setBusy(true);
    try { apply(await Api.saveDesignSystem(id, toInput(form))); toast("Design system saved"); }
    catch (e) { toast(e instanceof ApiError ? e.message : "Could not save", "err"); }
    finally { setBusy(false); }
  };
  const reset = async () => {
    setBusy(true);
    try { apply(await Api.resetDesignSystem(id)); toast("Back to the file / extracted tokens"); }
    catch (e) { toast(e instanceof ApiError ? e.message : "Could not reset", "err"); }
    finally { setBusy(false); }
  };

  if (!view || !form) return <div className="skeleton" style={{ height: 320 }} />;
  const tokens = view.effective.tokens || {};

  return (
    <div className="fade-in">
      <div className="row between page-head wrap" style={{ gap: 12 }}>
        <div>
          <h2>Design system</h2>
          <p className="muted" style={{ fontSize: "0.88rem", maxWidth: 680 }}>
            The brand tokens every generated page is drawn with. The agent never invents colours or fonts; it
            uses these. <strong>Tunables</strong> say which settings personalisation may change for a visitor, and
            to what. Anything not listed stays fixed.
          </p>
        </div>
        <span className="badge">{SOURCE_LABEL[view.source]}</span>
      </div>
      {view.current && (
        <p className="faint" style={{ fontSize: "0.8rem", marginTop: -8, marginBottom: 14 }}>
          Last saved {fmtDate(view.current.updated_at)}{view.current.updated_by ? ` by ${view.current.updated_by}` : ""}
        </p>
      )}

      <div className="grid-2" style={{ display: "grid", gridTemplateColumns: "minmax(0,1.3fr) minmax(0,1fr)", gap: 18 }}>
        <Editable>
          <div className="card">
            <h3 style={{ marginBottom: 12 }}>Brand</h3>
            <div className="field">
              <label className="label" htmlFor="ds-name">Brand name</label>
              <input id="ds-name" className="input" value={form.name} onChange={(e) => set({ name: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="ds-logo">Logo URL <span className="faint">(https)</span></label>
              <input id="ds-logo" className="input" value={form.logo_url} onChange={(e) => set({ logo_url: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="ds-voice">Brand voice</label>
              <textarea id="ds-voice" className="textarea" value={form.brand_voice}
                onChange={(e) => set({ brand_voice: e.target.value })} />
            </div>

            <h3 style={{ margin: "18px 0 10px" }}>Colours</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
              {COLOR_KEYS.map((k) => (
                <label key={k} className="row" style={{ gap: 8 }}>
                  <input type="color" aria-label={k} value={form.colors[k]}
                    onChange={(e) => set({ colors: { ...form.colors, [k]: e.target.value } })} />
                  <span style={{ fontSize: "0.85rem" }}>{k}</span>
                  <span className="mono faint" style={{ fontSize: "0.75rem" }}>{form.colors[k]}</span>
                </label>
              ))}
            </div>

            <h3 style={{ margin: "18px 0 10px" }}>Type and shape</h3>
            <div className="field">
              <label className="label" htmlFor="ds-font">Body font</label>
              <input id="ds-font" className="input" value={form.font_family} onChange={(e) => set({ font_family: e.target.value })} />
            </div>
            <div className="field">
              <label className="label" htmlFor="ds-hfont">Heading font <span className="faint">(optional)</span></label>
              <input id="ds-hfont" className="input" value={form.heading_family} onChange={(e) => set({ heading_family: e.target.value })} />
            </div>
            <div className="row" style={{ gap: 10 }}>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="ds-size">Base size</label>
                <input id="ds-size" className="input" value={form.base_size} onChange={(e) => set({ base_size: e.target.value })} />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="ds-scale">Scale</label>
                <input id="ds-scale" className="input" value={form.scale} onChange={(e) => set({ scale: e.target.value })} />
              </div>
              <div className="field" style={{ flex: 1 }}>
                <label className="label" htmlFor="ds-radius">Corner radius</label>
                <input id="ds-radius" className="input" value={form.radius} onChange={(e) => set({ radius: e.target.value })} />
              </div>
            </div>

            <h3 style={{ margin: "18px 0 6px" }}>Tunables</h3>
            <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 10 }}>
              Tick the values personalisation may use. The first ticked value is the default. Stored now; visitors get
              them when personal experience ships.
            </p>
            {AXES.map((a) => (
              <div key={a.key} className="row wrap" style={{ gap: 12, marginBottom: 8 }}>
                <span style={{ width: 120, fontSize: "0.86rem" }}>{a.label}</span>
                {a.options.map((o) => (
                  <label key={o} className="row" style={{ gap: 4, fontSize: "0.85rem" }}>
                    <input type="checkbox" checked={(form.tunables[a.key]?.allowed || []).includes(o)}
                      onChange={() => toggleTunable(a.key, o)} /> {o}
                  </label>
                ))}
              </div>
            ))}

            <EditOnly>
              <div className="row" style={{ gap: 8, marginTop: 16 }}>
                <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? <Spinner /> : "Save design system"}</button>
                {view.current && (
                  <button className="btn btn-ghost" onClick={reset} disabled={busy}>Remove saved version</button>
                )}
              </div>
            </EditOnly>
          </div>
        </Editable>

        <div className="card" style={{ alignSelf: "start" }}>
          <h3 style={{ marginBottom: 12 }}>Preview</h3>
          <div style={{
            background: form.colors.background, color: form.colors.text, borderRadius: form.radius || 12,
            padding: 20, fontFamily: form.font_family || undefined,
          }}>
            <div style={{ fontFamily: form.heading_family || form.font_family || undefined, fontSize: "1.4rem", fontWeight: 600 }}>
              {form.name || "Your brand"}
            </div>
            <p style={{ color: form.colors.muted, margin: "8px 0 14px" }}>{form.brand_voice || "A short line in your brand voice."}</p>
            <div style={{ background: form.colors.surface, borderRadius: form.radius || 12, padding: 14, marginBottom: 12 }}>
              A card on the surface colour.
            </div>
            <span style={{ background: form.colors.primary, color: form.colors.background, borderRadius: form.radius || 12,
              padding: "8px 14px", display: "inline-block", fontWeight: 600 }}>Primary action</span>
          </div>
          <h3 style={{ margin: "16px 0 8px", fontSize: "0.95rem" }}>Tokens in use</h3>
          <div className="mono faint" style={{ fontSize: "0.74rem", lineHeight: 1.6 }}>
            {Object.entries(tokens).map(([k, v]) => <div key={k}>{k}: {v}</div>)}
          </div>
        </div>
      </div>
    </div>
  );
}
