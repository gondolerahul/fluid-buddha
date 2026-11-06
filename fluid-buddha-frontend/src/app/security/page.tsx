"use client";
import { useCallback, useEffect, useState } from "react";
import QRCode from "qrcode";
import { useRequireAuth } from "@/lib/auth";
import { Api, ApiError, MFAStatus, SessionInfo } from "@/lib/api";
import { useQueryParam } from "@/lib/location";
import { AppHeader } from "@/components/Chrome";
import { LoadingScreen, Spinner, fmtDate, useToast } from "@/components/ui";

/** Your own sign-in security (M2-11): two-factor, password, sessions. */
export default function SecurityPage() {
  const auth = useRequireAuth();
  const setupAsked = useQueryParam("setup");
  if (auth.loading || !auth.tenant) return <LoadingScreen />;
  const required = !!auth.tenant.security?.mfa_setup_required;
  return (
    <>
      {!required && <AppHeader />}
      <main className="content stack" style={{ margin: "0 auto", maxWidth: 760 }}>
        <div className="page-head">
          <h1 className="h-page">Security</h1>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            How you sign in as {auth.tenant.user?.email}. Sessions end after{" "}
            {auth.tenant.security?.idle_minutes ?? 60} minutes without activity.
          </p>
        </div>
        {(required || setupAsked) && (
          <div className="notice warn">
            {auth.tenant.name || "This account"} requires two-factor sign-in. Set it up below to carry on.
          </div>
        )}
        <TwoFactorCard onChange={auth.refresh} />
        {!required && <PasswordCard />}
        {!required && <SessionsCard />}
        {required && (
          <button className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }} onClick={auth.logout}>
            Sign out
          </button>
        )}
      </main>
    </>
  );
}

function errText(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.message : fallback;
}

function RecoveryCodes({ codes }: { codes: string[] }) {
  const toast = useToast();
  const text = codes.join("\n");
  return (
    <div className="stack-sm" style={{ marginTop: 12 }}>
      <div className="notice ok">
        Save these recovery codes somewhere safe. Each works once if you lose your phone. They won&apos;t be shown again.
      </div>
      <pre className="code" style={{ columns: 2 }}>{text}</pre>
      <div className="row" style={{ gap: 8 }}>
        <button className="btn btn-sm" onClick={() => navigator.clipboard.writeText(text).then(() => toast("Codes copied"))}>
          Copy
        </button>
        <a className="btn btn-sm" download="fluidbuddha-recovery-codes.txt"
          href={`data:text/plain;charset=utf-8,${encodeURIComponent(text + "\n")}`}>Download</a>
      </div>
    </div>
  );
}

function TwoFactorCard({ onChange }: { onChange: () => Promise<unknown> }) {
  const toast = useToast();
  const [status, setStatus] = useState<MFAStatus | null>(null);
  const [setup, setSetup] = useState<{ secret: string; uri: string; qr: string } | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [mode, setMode] = useState<"idle" | "disable" | "regenerate">("idle");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => Api.mfaStatus().then(setStatus).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const start = async () => {
    setBusy(true);
    try {
      const s = await Api.mfaSetup();
      const qr = await QRCode.toDataURL(s.otpauth_uri, { margin: 1, width: 200 });
      setSetup({ secret: s.secret, uri: s.otpauth_uri, qr });
      setCode("");
    } catch (e) {
      toast(errText(e, "Could not start the setup"), "err");
    } finally {
      setBusy(false);
    }
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      toast(errText(e, "That didn't work"), "err");
    } finally {
      setBusy(false);
    }
  };

  const enable = () => run(async () => {
    const r = await Api.mfaEnable(code);
    setCodes(r.recovery_codes);
    setSetup(null);
    setCode("");
    toast("Two-factor is on");
    await load();
    await onChange();
  });
  const disable = () => run(async () => {
    await Api.mfaDisable(code, password);
    setMode("idle");
    setCode("");
    setPassword("");
    toast("Two-factor is off");
    await load();
    await onChange();
  });
  const regenerate = () => run(async () => {
    const r = await Api.mfaRecoveryCodes(code);
    setCodes(r.recovery_codes);
    setMode("idle");
    setCode("");
    await load();
  });

  return (
    <section className="card" id="two-factor">
      <div className="row between wrap" style={{ gap: 12 }}>
        <div>
          <h3>Two-factor sign-in</h3>
          <p className="faint" style={{ fontSize: "0.84rem", marginTop: 4 }}>
            A code from an authenticator app (Google Authenticator, 1Password, Authy…) after your password.
            Sign-ins through your company&apos;s SSO use its own two-factor.
          </p>
        </div>
        {status && <span className={`badge ${status.enabled ? "ok" : ""}`}>{status.enabled ? "On" : "Off"}</span>}
      </div>

      {!status ? <div className="skeleton" style={{ height: 60, marginTop: 12 }} /> : !status.enabled ? (
        setup ? (
          <div className="row wrap" style={{ gap: 20, marginTop: 14, alignItems: "flex-start" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={setup.qr} alt="QR code for your authenticator app" width={180} height={180}
              style={{ borderRadius: 8, background: "#fff" }} />
            <div className="stack-sm" style={{ flex: 1, minWidth: 240 }}>
              <p className="muted" style={{ fontSize: "0.86rem" }}>
                Scan this with your authenticator app, or enter the key by hand:
              </p>
              <code className="code" style={{ display: "block", wordBreak: "break-all" }}>
                {setup.secret.replace(/(.{4})/g, "$1 ").trim()}
              </code>
              <label className="label" style={{ marginTop: 6 }}>Then enter the 6-digit code it shows</label>
              <div className="row" style={{ gap: 8 }}>
                <input className="input mono" inputMode="numeric" autoComplete="one-time-code" maxLength={6}
                  value={code} onChange={(e) => setCode(e.target.value.trim())} placeholder="123456"
                  style={{ maxWidth: 140 }} />
                <button className="btn btn-primary btn-sm" disabled={busy || code.length !== 6} onClick={enable}>
                  {busy ? <Spinner /> : "Turn on"}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => setSetup(null)}>Cancel</button>
              </div>
            </div>
          </div>
        ) : (
          <button className="btn btn-primary btn-sm" style={{ marginTop: 14 }} disabled={busy} onClick={start}>
            {busy ? <Spinner /> : "Set up two-factor"}
          </button>
        )
      ) : (
        <div className="stack-sm" style={{ marginTop: 12 }}>
          <p className="muted" style={{ fontSize: "0.86rem" }}>
            On since {status.enabled_at ? fmtDate(status.enabled_at) : "—"} · {status.recovery_codes_left} recovery
            code{status.recovery_codes_left === 1 ? "" : "s"} left
            {status.required ? " · required by your account" : ""}.
          </p>
          {mode === "idle" ? (
            <div className="row" style={{ gap: 8 }}>
              <button className="btn btn-sm" onClick={() => { setMode("regenerate"); setCode(""); }}>New recovery codes</button>
              {!status.required && (
                <button className="btn btn-sm" onClick={() => { setMode("disable"); setCode(""); }}>Turn off</button>
              )}
            </div>
          ) : (
            <div className="row wrap" style={{ gap: 8 }}>
              <input className="input mono" placeholder="Code or recovery code" value={code}
                onChange={(e) => setCode(e.target.value.trim())} style={{ maxWidth: 200 }} />
              {mode === "disable" && (
                <input className="input" type="password" placeholder="Your password" value={password}
                  onChange={(e) => setPassword(e.target.value)} style={{ maxWidth: 200 }} />
              )}
              <button className="btn btn-primary btn-sm" disabled={busy || !code}
                onClick={mode === "disable" ? disable : regenerate}>
                {busy ? <Spinner /> : mode === "disable" ? "Turn off" : "Make new codes"}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => setMode("idle")}>Cancel</button>
            </div>
          )}
        </div>
      )}
      {codes && <RecoveryCodes codes={codes} />}
    </section>
  );
}

function PasswordCard() {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await Api.changePassword(current, next);
      toast(r.other_sessions_ended
        ? `Password changed; signed out of ${r.other_sessions_ended} other session${r.other_sessions_ended === 1 ? "" : "s"}`
        : "Password changed");
      setCurrent("");
      setNext("");
    } catch (e2) {
      toast(errText(e2, "Could not change the password"), "err");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="card">
      <h3>Password</h3>
      <p className="faint" style={{ fontSize: "0.84rem", margin: "4px 0 12px" }}>
        Changing it signs you out everywhere else.
      </p>
      <form className="row wrap" style={{ gap: 8 }} onSubmit={save}>
        <input className="input" type="password" placeholder="Current password" value={current}
          autoComplete="current-password" onChange={(e) => setCurrent(e.target.value)} style={{ maxWidth: 220 }} />
        <input className="input" type="password" placeholder="New password (8+ characters)" value={next} minLength={8}
          autoComplete="new-password" required onChange={(e) => setNext(e.target.value)} style={{ maxWidth: 240 }} />
        <button className="btn btn-sm" disabled={busy || next.length < 8}>{busy ? <Spinner /> : "Change"}</button>
      </form>
    </section>
  );
}

function describe(s: SessionInfo): string {
  const ua = s.user_agent || "";
  const browser = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox"
    : /Safari\//.test(ua) ? "Safari" : ua ? "Browser" : "API client";
  const os = /Windows/.test(ua) ? "Windows" : /Mac OS/.test(ua) ? "macOS" : /Android/.test(ua) ? "Android"
    : /iPhone|iPad/.test(ua) ? "iOS" : /Linux/.test(ua) ? "Linux" : "";
  return [browser, os].filter(Boolean).join(" on ");
}

function SessionsCard() {
  const toast = useToast();
  const [data, setData] = useState<{ current: string; sessions: SessionInfo[] } | null>(null);
  const load = useCallback(() => Api.sessions().then(setData).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  const others = data ? data.sessions.filter((s) => s.id !== data.current).length : 0;
  return (
    <section className="card">
      <div className="row between wrap" style={{ gap: 12, marginBottom: 12 }}>
        <h3>Where you&apos;re signed in</h3>
        <button className="btn btn-sm" disabled={!others}
          onClick={() => Api.endOtherSessions().then((r) => { toast(`Signed out of ${r.ended} other session${r.ended === 1 ? "" : "s"}`); load(); })}>
          Sign out everywhere else
        </button>
      </div>
      {!data ? <div className="skeleton" style={{ height: 80 }} /> : (
        <table className="table">
          <thead><tr><th>Device</th><th>How</th><th>Last active</th><th /></tr></thead>
          <tbody>
            {data.sessions.map((s) => (
              <tr key={s.id}>
                <td>{describe(s)}{s.ip ? <span className="faint"> · {s.ip}</span> : null}
                  <div className="faint" style={{ fontSize: "0.78rem" }}>{s.account}</div></td>
                <td>{s.method.startsWith("sso") ? "SSO" : s.method === "password+totp" ? "Password + code" : "Password"}</td>
                <td>{fmtDate(s.last_seen_at)}</td>
                <td style={{ textAlign: "right" }}>
                  {s.id === data.current ? <span className="badge">This one</span> : (
                    <button className="btn btn-ghost btn-sm"
                      onClick={() => Api.endSession(s.id).then(() => { toast("Signed out"); load(); })}>Sign out</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
