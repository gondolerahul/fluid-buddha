"use client";
import { ReactNode, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { API_BASE, Api, ApiError, SDK_URL, WIDGET_BACKEND, Website } from "@/lib/api";
import { useWebsite } from "@/components/WebsiteContext";
import { Spinner, useToast } from "@/components/ui";
import { EditOnly } from "@/components/Permission";

type Check = { label: string; ok: boolean; detail: string };

/** The server every install surface loads /widget/loader.js from (M2-10): the
 *  public widget backend, as http(s). The loader points the widget back at it. */
const SERVER = WIDGET_BACKEND.replace(/^ws/, "http").replace(/\/$/, "");

/** `https://fbk_…@server` — the key and the server in one string, for plugins. */
function installCode(key: string): string {
  const m = /^(https?):\/\/(.*)$/.exec(SERVER);
  return m ? `${m[1]}://${key}@${m[2]}` : key;
}

function loaderSnippet(key: string): string {
  return `<script src="${SERVER}/widget/loader.js" data-key="${key}" async></script>`;
}

type Platform = "html" | "wordpress" | "shopify" | "webflow" | "framer" | "gtm" | "react" | "vue";

const PLATFORMS: { id: Platform; label: string }[] = [
  { id: "html", label: "Any website" },
  { id: "wordpress", label: "WordPress" },
  { id: "shopify", label: "Shopify" },
  { id: "webflow", label: "Webflow" },
  { id: "framer", label: "Framer" },
  { id: "gtm", label: "Tag Manager" },
  { id: "react", label: "React" },
  { id: "vue", label: "Vue" },
];

type Guide = { steps: ReactNode[]; copy: { label: string; text: string; pre?: boolean }[] };

function guide(p: Platform, key: string): Guide {
  const code = installCode(key);
  const codeCopy = { label: "Install code", text: code };
  const snippetCopy = { label: "Snippet", text: loaderSnippet(key), pre: true };
  switch (p) {
    case "html":
      return {
        steps: ["Paste this just before </body> on every page where the agent should appear."],
        copy: [snippetCopy],
      };
    case "wordpress":
      return {
        steps: [
          <>Install the <strong>FluidBuddha AI Agent</strong> plugin and activate it.</>,
          <>Go to <strong>Settings → FluidBuddha</strong>, paste the install code and save. The page confirms the connection.</>,
          "Optional: hide it on pages such as /checkout*, or from your logged-in team.",
        ],
        copy: [codeCopy],
      };
    case "shopify":
      return {
        steps: [
          <>Install the <strong>FluidBuddha AI Agent</strong> app.</>,
          <>Open <strong>Online Store → Themes → Customize → App embeds</strong>.</>,
          <>Switch on <strong>FluidBuddha agent</strong>, paste the install code and save.</>,
        ],
        copy: [codeCopy],
      };
    case "webflow":
      return {
        steps: [
          <>Open <strong>Site settings → Custom code</strong>.</>,
          <>Paste the snippet into <strong>Footer code</strong>, save, and publish the site.</>,
        ],
        copy: [snippetCopy],
      };
    case "framer":
      return {
        steps: [
          <>Add the <strong>FluidBuddha</strong> code component (Assets → Code → New component) and drop it on a page.</>,
          "Paste the install code in its properties and publish.",
          <>Or paste the snippet in <strong>Site settings → Custom code → End of &lt;body&gt;</strong>.</>,
        ],
        copy: [codeCopy, snippetCopy],
      };
    case "gtm":
      return {
        steps: [
          <>Download the template below, then in GTM <strong>Templates → Tag Templates → New → ⋮ → Import</strong>.</>,
          <>Add a tag of type <strong>FluidBuddha AI agent</strong>, paste the widget key, trigger on <strong>All Pages</strong>, and publish.</>,
          "Or use a Custom HTML tag with the snippet.",
        ],
        copy: [{ label: "Widget key", text: key }, snippetCopy],
      };
    case "react":
      return {
        steps: [
          <>Install <span className="mono">@fluidbuddha/react</span> and render the component once, near the root.</>,
          "onNavigate keeps the agent's page changes inside your router.",
        ],
        copy: [{
          label: "Code", pre: true,
          text: `npm install @fluidbuddha/react

import { FluidBuddha } from "@fluidbuddha/react";

<FluidBuddha
  installCode="${code}"
  onNavigate={(path) => navigate(path)}
/>`,
        }],
      };
    case "vue":
      return {
        steps: [
          <>Install <span className="mono">@fluidbuddha/vue</span> and use the component once, e.g. in App.vue.</>,
          "@navigate keeps the agent's page changes inside your router.",
        ],
        copy: [{
          label: "Code", pre: true,
          text: `npm install @fluidbuddha/vue

import { FluidBuddha } from "@fluidbuddha/vue";

<FluidBuddha
  install-code="${code}"
  @navigate="(path) => router.push(path)"
/>`,
        }],
      };
  }
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
  const [platform, setPlatform] = useState<Platform>("html");
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

  const g = key ? guide(platform, key) : null;

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
            <EditOnly role="admin">
              <button className="btn btn-sm" onClick={rotate} disabled={rotating}>
                {rotating ? <Spinner /> : key ? "Rotate key" : "Create key"}
              </button>
            </EditOnly>
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

      {key && g && (
        <section className="card">
          <div className="tabs" style={{ marginBottom: 16, flexWrap: "wrap" }}>
            {PLATFORMS.map((p) => (
              <button key={p.id} className={`tab ${platform === p.id ? "active" : ""}`} onClick={() => setPlatform(p.id)}>
                {p.label}
              </button>
            ))}
          </div>
          <ol className="muted" style={{ fontSize: "0.88rem", margin: "0 0 14px", paddingLeft: 20, lineHeight: 1.7 }}>
            {g.steps.map((step, i) => <li key={i}>{step}</li>)}
          </ol>
          <div className="stack-sm">
            {g.copy.map((c) => (
              <div key={c.label}>
                <div className="row between" style={{ gap: 12, marginBottom: 6 }}>
                  <span className="eyebrow">{c.label}</span>
                  <button className="btn btn-primary btn-sm" onClick={() => copy(c.text, c.label)}>Copy</button>
                </div>
                {c.pre
                  ? <pre className="code">{c.text}</pre>
                  : <code className="code" style={{ display: "block", wordBreak: "break-all" }}>{c.text}</code>}
              </div>
            ))}
          </div>
          {platform === "gtm" && (
            <div className="row wrap" style={{ gap: 10, marginTop: 12, alignItems: "center" }}>
              <a className="btn btn-sm" href={`${SERVER}/widget/gtm-template.tpl`} download>
                Download GTM template
              </a>
              <span className="faint" style={{ fontSize: "0.8rem" }}>
                Made for this server, so GTM allows it to load the agent from here.
              </span>
            </div>
          )}
          <p className="faint" style={{ fontSize: "0.8rem", marginTop: 12 }}>
            {g.copy.some((c) => c.label === "Install code")
              ? "The install code is your widget key and this server's address in one string. "
              : "The snippet carries only the key. "}
            Tier, design, colour and greeting come from <Link href={`/websites/${website.id}/settings`}>Settings</Link>,
            so changes there reach your site without editing it again.
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
