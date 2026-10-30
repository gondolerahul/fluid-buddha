"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Spinner } from "@/components/ui";

export default function LoginPage() {
  const { login, tenant, loading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && tenant) router.replace("/dashboard");
  }, [tenant, loading, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="center-screen">
      <div className="card fade-in" style={{ width: 400, maxWidth: "100%" }}>
        <div className="brand" style={{ marginBottom: 8 }}>
          <span className="brand-dot" />
          <span className="brand-name">Fluid-Buddha</span>
        </div>
        <h1 style={{ fontSize: "1.4rem", marginBottom: 4 }}>Welcome back</h1>
        <p className="muted" style={{ marginBottom: 22 }}>Sign in to your console.</p>
        <form onSubmit={submit} className="stack">
          <div className="field">
            <label className="label">Email</label>
            <input className="input" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          <div className="field">
            <label className="label">Password</label>
            <input className="input" type="password" required value={password}
              onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
          {err && <div className="badge err" style={{ alignSelf: "flex-start" }}>{err}</div>}
          <button className="btn btn-primary" disabled={busy} style={{ marginTop: 4 }}>
            {busy ? <Spinner /> : "Sign in"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 18, fontSize: "0.88rem" }}>
          New here? <Link href="/register" style={{ color: "var(--accent)" }}>Create an account</Link>
        </p>
      </div>
    </div>
  );
}
