"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { API_BASE, Api, ApiError, SDK_URL, WIDGET_BACKEND, Website } from "@/lib/api";
import { useWebsite } from "@/components/WebsiteContext";
import { Spinner, useToast } from "@/components/ui";

type Mode = "html" | "spa";
type Check = { label: string; ok: boolean; detail: string };

function htmlSnippet(w: Website): string {
  const attrs = [
    `src="${SDK_URL}"`,
    `data-backend="${WIDGET_BACKEND}"`,
    `data-key="${w.public_key}"`,
    `data-intelligence="${w.intelligence}"`,
    `data-design="${w.design}"`,
    w.accent ? `data-accent="${w.accent}"` : "",
  ].filter(Boolean);
  return `<script ${attrs.join("\n        ")}></script>`;
}

function spaSnippet(w: Website): string {
  const accent = w.accent ? `\n  accent: "${w.accent}",` : "";
  return `import { init } from "fluid-buddha";

init({
  backend: "${WIDGET_BACKEND}",
  key: "${w.public_key}",
  intelligence: "${w.intelligence}",
  design: "${w.design}",${accent}
  hooks: {
    // Route inside your app instead of a full page load.
    onNavigate: (path) => router.push(path),
  },
});`;
}

/** A bookmarklet that drops the widget onto whatever page is open (WS9):
 *  preview the agent on your real site before installing anything. */
function bookmarklet(w: Website): string {
  const attrs: Record<string, string> = {
    "data-backend": WIDGET_BACKEND,
    "data-key": w.public_key ?? "",
    "data-intelligence": w.intelligence,
    "data-design": w.design,
  };
  if (w.accent) attrs["data-accent"] = w.accent;
  const sets = Object.entries(attrs)
    .map(([k, v]) => `s.setAttribute(${JSON.stringify(k)},${JSON.stringify(v)});`)
    .join("");
  const code =
    "(function(){if(document.querySelector('fluid-buddha'))return;" +
    `var s=document.createElement('script');s.src=${JSON.stringify(SDK_URL)};${sets}` +
    "document.body.appendChild(s);})()";
  return "javascript:" + encodeURIComponent(code);
}

/** React refuses javascript: URLs in href, so the link's address is set on
 *  the DOM element directly. */
function BookmarkletLink({ href, label }: { href: string; label: string }) {
  const ref = useRef<HTMLAnchorElement>(null);
  useEffect(() => { ref.current?.setAttribute("href", href); }, [href]);
  return (
    <a ref={ref} className="btn btn-primary btn-sm" onClick={(e) => e.preventDefault()}
      title="Drag me to your bookmarks bar" style={{ cursor: "grab" }}>
      {label}
    </a>
  );
}

export default function InstallPage() {
  const { website, reload } = useWebsite();
  const toast = useToast();
  const [mode, setMode] = useState<Mode>("html");
  const [rotating, setRotating] = useState(false);
  const [testing, setTesting] = useState(false);
  const [checks, setChecks] = useState<Check[] | null>(null);

  if (!website) return <div className="skeleton" style={{ height: 240 }} />;
  const key = website.public_key;

  const copy = async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast(`${what} copied`);
    } catch {
      toast("Copy failed — select the text and copy it manually", "err");
    }
  };

  const rotate = async () => {
    if (key && !window.confirm(
      "Rotate the widget key? The current key stops working immediately, so update the snippet on your site.",
    )) return;
    setRotating(true);
    try {
      await Api.rotateKey(website.id);
      reload();
      setChecks(null);
      toast(key ? "New widget key issued" : "Widget key created");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not rotate the key", "err");
    } finally {
      setRotating(false);
    }
  };

  const test = async () => {
    setTesting(true);
    const out: Check[] = [];
    try {
      const r = await Api.readiness();
      out.push({
        label: "Backend reachable",
        ok: r.status === "ok" && r.db,
        detail: r.db ? API_BASE : "The backend answered but its database isn't ready",
      });
    } catch {
      out.push({ label: "Backend reachable", ok: false, detail: `No response from ${API_BASE}` });
    }
    if (key) {
      try {
        const c = await Api.widgetConfig(key);
        out.push({
          label: "Widget key valid",
          ok: true,
          detail: `${c.agent_name} for ${c.company_name} · ${c.intelligence} tier · ${c.design ?? "level1"}`,
        });
      } catch (e) {
        out.push({ label: "Widget key valid", ok: false, detail: e instanceof ApiError ? e.message : "Check failed" });
      }
    }
    setChecks(out);
    setTesting(false);
  };

  const snippet = key ? (mode === "html" ? htmlSnippet(website) : spaSnippet(website)) : "";

  return (
    <div className="fade-in stack">
      <div className="page-head">
        <h2>Install</h2>
        <p className="muted" style={{ fontSize: "0.88rem" }}>
          Put the agent on your site. The widget key tells the backend which site this is, so
          the agent answers from your knowledge with the tier you set.
        </p>
      </div>

      <section className="card">
        <div className="row between wrap" style={{ gap: 12, marginBottom: 12 }}>
          <div>
            <span className="eyebrow">Widget key</span>
            <p className="faint" style={{ fontSize: "0.82rem", marginTop: 4 }}>
              Public — it ships in your page source. Rotate it if you need to cut off an old embed.
            </p>
          </div>
          <div className="row" style={{ gap: 8 }}>
            {key && <button className="btn btn-sm" onClick={() => copy(key, "Widget key")}>Copy</button>}
            <button className="btn btn-sm" onClick={rotate} disabled={rotating}>
              {rotating ? <Spinner /> : key ? "Rotate key" : "Create key"}
            </button>
          </div>
        </div>
        {key ? (
          <code className="code" style={{ display: "block" }}>{key}</code>
        ) : (
          <div className="notice warn">
            This site was created before widget keys existed. Create a key to install the agent.
          </div>
        )}
      </section>

      {key && (
        <section className="card">
          <div className="row between wrap" style={{ gap: 12, marginBottom: 14 }}>
            <div className="tabs" style={{ margin: 0 }}>
              <button className={`tab ${mode === "html" ? "active" : ""}`} onClick={() => setMode("html")}>
                Any website
              </button>
              <button className={`tab ${mode === "spa" ? "active" : ""}`} onClick={() => setMode("spa")}>
                React / SPA
              </button>
            </div>
            <button className="btn btn-primary btn-sm" onClick={() => copy(snippet, "Snippet")}>Copy snippet</button>
          </div>
          <p className="muted" style={{ fontSize: "0.86rem", marginBottom: 12 }}>
            {mode === "html"
              ? "Paste this just before </body> on every page where the agent should appear."
              : "Call init once when your app starts. The onNavigate hook keeps navigation inside your router."}
          </p>
          <pre className="code">{snippet}</pre>
          <p className="faint" style={{ fontSize: "0.8rem", marginTop: 10 }}>
            Tier, design and accent come from <Link href={`/websites/${website.id}/settings`}>Settings</Link>.
            The backend enforces the tier from the key, whatever the snippet says.
          </p>
        </section>
      )}

      {key && (
        <section className="card" id="preview">
          <span className="eyebrow">Preview on your site</span>
          <p className="muted" style={{ fontSize: "0.86rem", margin: "8px 0 14px" }}>
            Try the agent on your live site before installing anything. Drag this button to your
            bookmarks bar, open any page of {website.domain || "your site"}, and click the bookmark.
            Only you see it, until you reload the page.
          </p>
          <div className="row wrap" style={{ gap: 10, alignItems: "center" }}>
            <BookmarkletLink href={bookmarklet(website)} label={`Preview ${website.name}`} />
            <button className="btn btn-sm" onClick={() => copy(decodeURIComponent(bookmarklet(website)), "Bookmarklet")}>
              Copy as text
            </button>
          </div>
          <p className="faint" style={{ fontSize: "0.8rem", marginTop: 10 }}>
            {website.domain
              ? `The key only answers on ${website.domain}, so preview there. `
              : ""}
            A site with a strict Content-Security-Policy may block it; install the snippet instead.
          </p>
        </section>
      )}

      <section className="card">
        <span className="eyebrow">Allowed origin</span>
        <div style={{ marginTop: 10 }}>
          {website.domain ? (
            <div className="notice">
              The agent only answers pages served from <strong className="mono">{website.domain}</strong> and
              its subdomains.
            </div>
          ) : (
            <div className="notice warn">
              No domain set, so this key works from any website. Add your domain
              in <Link href={`/websites/${website.id}/settings`}>Settings</Link> to restrict it.
            </div>
          )}
        </div>
      </section>

      <section className="card">
        <div className="row between wrap" style={{ gap: 12 }}>
          <div>
            <span className="eyebrow">Test connection</span>
            <p className="faint" style={{ fontSize: "0.82rem", marginTop: 4 }}>
              Checks the backend is up and the key resolves. It doesn&apos;t run an agent turn, so it costs nothing.
            </p>
          </div>
          <button className="btn btn-sm" onClick={test} disabled={testing}>
            {testing ? <Spinner /> : "Test connection"}
          </button>
        </div>
        {checks && (
          <div className="stack-sm" style={{ marginTop: 14 }}>
            {checks.map((c) => (
              <div key={c.label} className={`notice ${c.ok ? "ok" : "err"}`}>
                <strong>{c.ok ? "✓" : "✕"} {c.label}</strong>
                <span style={{ marginLeft: 8 }}>{c.detail}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
