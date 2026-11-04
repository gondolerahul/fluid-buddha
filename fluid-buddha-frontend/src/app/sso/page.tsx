"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";

const noop = () => () => {};

/** Where single sign-on lands: the token is in the URL fragment (never sent
 *  to a server); keep it and go to the dashboard. */
export default function SSOReturnPage() {
  // Read once: the fragment is cleared right after, so later renders can't see it.
  const [token] = useState(() =>
    typeof window === "undefined" ? null : new URLSearchParams(window.location.hash.slice(1)).get("token"));
  const mounted = useSyncExternalStore(noop, () => true, () => false);
  const { adopt } = useAuth();
  const router = useRouter();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!token) return;
    window.history.replaceState(null, "", "/sso");   // drop the token from the address bar
    adopt(token).then(() => router.replace("/dashboard")).catch(() => setFailed(true));
  }, [token, adopt, router]);

  return (
    <div className="center-screen">
      <div className="card fade-in" style={{ width: 380, maxWidth: "100%", textAlign: "center" }}>
        {failed || (mounted && !token) ? (
          <>
            <p className="muted" style={{ marginBottom: 12 }}>That sign-in didn&apos;t work. Please try again.</p>
            <Link className="btn btn-primary" href="/login">Back to sign in</Link>
          </>
        ) : <><Spinner /><p className="muted" style={{ marginTop: 10 }}>Signing you in…</p></>}
      </div>
    </div>
  );
}
