"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Api, ApiError, InvitationInfo } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useQueryParam } from "@/lib/location";
import { Spinner } from "@/components/ui";

/** Accepting an invitation: a new person picks a password; someone who already
 *  has a login accepts while signed in as themselves. */
export default function InvitePage() {
  const token = useQueryParam("token");
  const { tenant, loading, accept, logout } = useAuth();
  const router = useRouter();
  const [info, setInfo] = useState<{ token: string; inv: InvitationInfo | null; err?: string } | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) return;
    let live = true;
    Api.invitation(token)
      .then((inv) => { if (live) setInfo({ token, inv }); })
      .catch((e) => { if (live) setInfo({ token, inv: null, err: e instanceof ApiError ? e.message : "Not found" }); });
    return () => { live = false; };
  }, [token]);

  const inv = info?.inv ?? null;
  const signedInAs = tenant?.user?.email ?? null;
  const rightPerson = inv && signedInAs && signedInAs.toLowerCase() === inv.email.toLowerCase();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setErr("");
    setBusy(true);
    try {
      const res = await Api.acceptInvitation(token, inv?.has_user ? {} : { name: name || undefined, password },
        !!inv?.has_user);
      accept(res);
      router.replace("/dashboard");
    } catch (e2) {
      setErr(e2 instanceof ApiError ? e2.message : "Could not accept the invitation.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="center-screen">
      <div className="card fade-in" style={{ width: 440, maxWidth: "100%" }}>
        <div className="brand" style={{ marginBottom: 8 }}>
          <span className="brand-dot" />
          <span className="brand-name">FluidBuddha</span>
        </div>
        {!token ? <p className="muted">This link is missing its invitation code.</p>
          : !info || loading ? <Spinner />
          : !inv ? (
            <>
              <h1 style={{ fontSize: "1.3rem", marginBottom: 6 }}>Invitation not valid</h1>
              <p className="muted">{info.err} Ask the person who invited you for a new link.</p>
            </>
          ) : (
            <>
              <h1 style={{ fontSize: "1.3rem", marginBottom: 6 }}>Join {inv.account}</h1>
              <p className="muted" style={{ marginBottom: 18 }}>
                You&apos;re invited as <strong>{inv.role}</strong> ({inv.email}).
              </p>
              {inv.has_user && !rightPerson ? (
                <div className="stack">
                  <p className="muted" style={{ fontSize: "0.9rem" }}>
                    You already have a FluidBuddha login. Sign in as {inv.email}, then open this link again.
                    {signedInAs && ` You're signed in as ${signedInAs}.`}
                  </p>
                  <Link className="btn btn-primary" onClick={() => signedInAs && logout()}
                    href={`/login?next=${encodeURIComponent(`/invite?token=${token}`)}`}>Sign in as {inv.email}</Link>
                </div>
              ) : (
                <form onSubmit={submit} className="stack">
                  {!inv.has_user && (
                    <>
                      <div className="field">
                        <label className="label">Your name</label>
                        <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
                      </div>
                      <div className="field">
                        <label className="label">Choose a password</label>
                        <input className="input" type="password" required minLength={8} value={password}
                          onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
                      </div>
                    </>
                  )}
                  {err && <div className="badge err" style={{ alignSelf: "flex-start" }}>{err}</div>}
                  <button className="btn btn-primary" disabled={busy}>
                    {busy ? <Spinner /> : `Join ${inv.account}`}</button>
                </form>
              )}
            </>
          )}
      </div>
    </div>
  );
}
