"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Api, ApiError } from "@/lib/api";
import { useQueryParam } from "@/lib/location";
import { Spinner } from "@/components/ui";

/** Only same-site paths, so `?next=` can't send people elsewhere. */
function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
}

export default function LoginPage() {
  const { login, loginMfa, tenant, loading } = useAuth();
  const router = useRouter();
  const ssoError = useQueryParam("sso_error");
  const expired = useQueryParam("expired");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const next = safeNext(useQueryParam("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState<"password" | "google" | "sso" | null>(null);
  const [ssoMode, setSsoMode] = useState(false);

  useEffect(() => {
    if (!loading && tenant) router.replace(next);
  }, [tenant, loading, router, next]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    if (ssoMode) return startSSO("oidc");
    setBusy("password");
    try {
      if (mfaToken) {
        await loginMfa(mfaToken, useRecovery ? { recovery_code: code } : { code });
        router.replace(next);
        return;
      }
      const challenge = await login(email, password);
      if (challenge) {
        setMfaToken(challenge.mfaToken);   // the password was right; now the code
        return;
      }
      router.replace(next);
    } catch (e) {
      if (mfaToken && e instanceof ApiError && e.status === 401 && /too long|password again/.test(e.message)) {
        setMfaToken(null);
        setCode("");
      }
      setErr(e instanceof ApiError ? e.message : "Could not sign in.");
    } finally {
      setBusy(null);
    }
  };

  const startSSO = async (provider: "google" | "oidc") => {
    setErr("");
    setBusy(provider === "google" ? "google" : "sso");
    try {
      const { url } = await Api.ssoStart(provider, provider === "oidc" ? email : undefined);
      window.location.assign(url);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not start single sign-on.");
      setBusy(null);
    }
  };

  return (
    <div className="center-screen">
      <div className="card fade-in" style={{ width: 400, maxWidth: "100%" }}>
        <div className="brand" style={{ marginBottom: 8 }}>
          <span className="brand-dot" />
          <span className="brand-name">FluidBuddha</span>
        </div>
        <h1 style={{ fontSize: "1.4rem", marginBottom: 4 }}>Welcome back</h1>
        <p className="muted" style={{ marginBottom: 22 }}>Sign in to your console.</p>
        {ssoError && <div className="notice err" style={{ marginBottom: 14 }}>{ssoError}</div>}
        {expired && !mfaToken && (
          <div className="notice warn" style={{ marginBottom: 14 }}>
            Your session ended, so you were signed out. Sign in again to carry on.
          </div>
        )}
        {mfaToken ? (
          <form onSubmit={submit} className="stack">
            <div className="field">
              <label className="label">{useRecovery ? "Recovery code" : "Code from your authenticator app"}</label>
              <input className="input mono" autoFocus required value={code}
                inputMode={useRecovery ? "text" : "numeric"} autoComplete="one-time-code"
                maxLength={useRecovery ? 20 : 6} placeholder={useRecovery ? "xxxxx-xxxxx" : "123456"}
                onChange={(e) => setCode(e.target.value.trim())} />
            </div>
            {err && <div className="badge err" style={{ alignSelf: "flex-start" }}>{err}</div>}
            <button className="btn btn-primary" disabled={busy !== null}>
              {busy ? <Spinner /> : "Verify"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm"
              onClick={() => { setUseRecovery(!useRecovery); setCode(""); setErr(""); }}>
              {useRecovery ? "Use a code from the app" : "Lost your phone? Use a recovery code"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm"
              onClick={() => { setMfaToken(null); setCode(""); setErr(""); }}>
              Back
            </button>
          </form>
        ) : (<>
        <form onSubmit={submit} className="stack">
          <div className="field">
            <label className="label">{ssoMode ? "Work email" : "Email"}</label>
            <input className="input" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          {!ssoMode && (
            <div className="field">
              <label className="label">Password</label>
              <input className="input" type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
          )}
          {err && <div className="badge err" style={{ alignSelf: "flex-start" }}>{err}</div>}
          <button className="btn btn-primary" disabled={busy !== null} style={{ marginTop: 4 }}>
            {busy === "password" || busy === "sso" ? <Spinner /> : ssoMode ? "Continue with SSO" : "Sign in"}
          </button>
        </form>
        <div className="stack" style={{ marginTop: 14, gap: 8 }}>
          <button type="button" className="btn" disabled={busy !== null} onClick={() => startSSO("google")}>
            {busy === "google" ? <Spinner /> : "Sign in with Google"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setSsoMode(!ssoMode); setErr(""); }}>
            {ssoMode ? "Use a password instead" : "Sign in with your company's SSO"}
          </button>
        </div>
        </>)}
        <p className="muted" style={{ marginTop: 18, fontSize: "0.88rem" }}>
          New here? <Link href="/register" style={{ color: "var(--accent)" }}>Create an account</Link>
        </p>
      </div>
    </div>
  );
}
