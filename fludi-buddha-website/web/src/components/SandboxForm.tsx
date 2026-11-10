"use client";

/**
 * "Try it on your own website": the real sandbox preview (WebsiteConcept.md §7.3, §10.1).
 * Step 1 posts the website and a work email to /api/sandbox, which checks that the email's
 * domain matches the website and asks the sandbox service to send a one-time code.
 */
import { useState } from "react";
import styles from "./SandboxForm.module.css";

const FREE_MAIL = /@(gmail|yahoo|outlook|hotmail|icloud|proton|rediffmail|live)\./i;

function domainOf(url: string) {
  try { return new URL(/^https?:\/\//.test(url) ? url : `https://${url}`).hostname.replace(/^www\./, "").toLowerCase(); }
  catch { return ""; }
}

export default function SandboxForm() {
  const [site, setSite] = useState("");
  const [email, setEmail] = useState("");
  const [state, setState] = useState<{ kind: "idle" | "error" | "sent" | "unavailable" | "busy"; msg?: string }>({ kind: "idle" });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const d = domainOf(site);
    const ed = email.split("@")[1]?.toLowerCase() ?? "";
    if (!d) return setState({ kind: "error", msg: "Please enter your website address, for example yourbusiness.com." });
    if (!ed) return setState({ kind: "error", msg: "Please enter your work email." });
    const free = FREE_MAIL.test(email);
    if (!free && !(ed === d || ed.endsWith("." + d) || d.endsWith("." + ed)))
      return setState({ kind: "error", msg: `Your email should be on ${d}, so nobody can preview a website that isn't theirs.` });
    setState({ kind: "busy" });
    try {
      const r = await fetch("/api/sandbox", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ site: d, email }) });
      const j = await r.json();
      if (r.ok) setState({ kind: "sent", msg: free ? "Free-mail addresses get a 3-page preview. " + j.message : j.message });
      else if (r.status === 503) setState({ kind: "unavailable", msg: j.message });
      else setState({ kind: "error", msg: j.message || "Something went wrong. Please try again." });
    } catch {
      setState({ kind: "error", msg: "We couldn't reach the preview service. Please try again." });
    }
  };

  return (
    <form className={`glass ${styles.form}`} onSubmit={submit}>
      <label className={styles.field}>
        <span>Your website</span>
        <input value={site} onChange={(e) => setSite(e.target.value)} placeholder="yourbusiness.com" autoComplete="url" inputMode="url" />
      </label>
      <label className={styles.field}>
        <span>Work email</span>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@yourbusiness.com" type="email" autoComplete="email" />
      </label>
      <button className="btn btn-metal btn-lg" disabled={state.kind === "busy"}>{state.kind === "busy" ? "Checking…" : "Hear it talk"}</button>
      {state.msg && <p className={`${styles.msg} ${styles[state.kind]}`} role="status">{state.msg}</p>}
      <p className={styles.fine}>We read a few public pages (up to 8, respecting robots.txt). Your preview and its data are deleted after 24 hours. “Keep it” turns it into a free account.</p>
    </form>
  );
}
