"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Spinner } from "@/components/ui";

export default function RegisterPage() {
  const { register, tenant, loading } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
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
    if (password.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await register(email, password, name || undefined);
      router.replace("/dashboard");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not create account.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="center-screen">
      <div className="card fade-in" style={{ width: 400, maxWidth: "100%" }}>
        <div className="brand" style={{ marginBottom: 8 }}>
          <span className="brand-dot" />
          <span className="brand-name">FluidBuddha</span>
        </div>
        <h1 style={{ fontSize: "1.4rem", marginBottom: 4 }}>Create your account</h1>
        <p className="muted" style={{ marginBottom: 22 }}>Start managing your voice agents.</p>
        <form onSubmit={submit} className="stack">
          <div className="field">
            <label className="label">Name <span className="faint">(optional)</span></label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Acme Inc." />
          </div>
          <div className="field">
            <label className="label">Email</label>
            <input className="input" type="email" required value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          <div className="field">
            <label className="label">Password</label>
            <input className="input" type="password" required value={password}
              onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
          </div>
          {err && <div className="badge err" style={{ alignSelf: "flex-start" }}>{err}</div>}
          <button className="btn btn-primary" disabled={busy} style={{ marginTop: 4 }}>
            {busy ? <Spinner /> : "Create account"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 18, fontSize: "0.88rem" }}>
          Already have an account? <Link href="/login" style={{ color: "var(--accent)" }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
