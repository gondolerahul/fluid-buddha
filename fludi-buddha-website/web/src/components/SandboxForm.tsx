"use client";

/**
 * "Try it on your own website": the sandbox preview. It posts the website and a work email to
 * /api/sandbox, which checks that the email's domain matches the website and asks the sandbox
 * service to send a one-time code. A link can prefill the website with ?site=.
 */
import { useEffect, useState } from "react";

const FREE_MAIL = /@(gmail|yahoo|outlook|hotmail|icloud|proton|rediffmail|live)\./i;

function domainOf(url: string) {
  try { return new URL(/^https?:\/\//.test(url) ? url : `https://${url}`).hostname.replace(/^www\./, "").toLowerCase(); }
  catch { return ""; }
}

type State = { kind: "idle" | "error" | "sent" | "unavailable" | "busy"; field?: "site" | "email"; msg?: string };

export default function SandboxForm() {
  const [site, setSite] = useState("");
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });

  useEffect(() => {
    const s = new URLSearchParams(window.location.search).get("site");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the link's ?site= is only known in the browser
    if (s) setSite(s);
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const d = domainOf(site);
    const ed = email.split("@")[1]?.toLowerCase() ?? "";
    if (!d) return setState({ kind: "error", field: "site", msg: "Enter your website address, for example yourbusiness.com." });
    if (!ed) return setState({ kind: "error", field: "email", msg: "Enter your work email." });
    const free = FREE_MAIL.test(email);
    if (!free && !(ed === d || ed.endsWith("." + d) || d.endsWith("." + ed)))
      return setState({ kind: "error", field: "email", msg: `Use an email on ${d}, so that nobody can preview a website that is not theirs.` });
    setState({ kind: "busy" });
    try {
      const r = await fetch("/api/sandbox", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ site: d, email }) });
      const j = await r.json();
      if (r.ok) setState({ kind: "sent", msg: free ? "Free-mail addresses get a three-page preview. " + j.message : j.message });
      else if (r.status === 503) setState({ kind: "unavailable", msg: j.message });
      else setState({ kind: "error", msg: j.message || "Something went wrong. Please try again." });
    } catch {
      setState({ kind: "error", msg: "We could not reach the preview service. Please try again." });
    }
  };

  const err = (f: "site" | "email") => state.kind === "error" && state.field === f;
  return (
    <form className="form" onSubmit={submit} noValidate>
      <label className="field">
        <span>Your website</span>
        <input className="input" value={site} onChange={(e) => setSite(e.target.value)} placeholder="yourbusiness.com" autoComplete="url" inputMode="url"
               aria-invalid={err("site") || undefined} aria-describedby={err("site") ? "sb-err" : undefined} />
      </label>
      <label className="field">
        <span>Work email</span>
        <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@yourbusiness.com" type="email" autoComplete="email"
               aria-invalid={err("email") || undefined} aria-describedby={err("email") ? "sb-err" : undefined} />
      </label>
      {state.msg && <p id="sb-err" className={`form-msg ${state.kind}`} role="status">{state.msg}</p>}
      <button className="btn btn-primary btn-lg" disabled={state.kind === "busy"}>{state.kind === "busy" ? "Checking…" : "Hear your website talk"}</button>
      <p className="form-fine">We read a few public pages (up to eight, respecting robots.txt). Your preview and its data are deleted after 24 hours. &ldquo;Keep it&rdquo; turns it into a free account.</p>
    </form>
  );
}
