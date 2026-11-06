"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";

/** Where single sign-on lands. The backend already set the session cookie on
 *  its redirect (M2-11), so all that's left is to read who signed in. */
export default function SSOReturnPage() {
  const { refresh } = useAuth();
  const router = useRouter();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    refresh().then((me) => (me ? router.replace("/dashboard") : setFailed(true)));
  }, [refresh, router]);

  return (
    <div className="center-screen">
      <div className="card fade-in" style={{ width: 380, maxWidth: "100%", textAlign: "center" }}>
        {failed ? (
          <>
            <p className="muted" style={{ marginBottom: 12 }}>That sign-in didn&apos;t work. Please try again.</p>
            <Link className="btn btn-primary" href="/login">Back to sign in</Link>
          </>
        ) : <><Spinner /><p className="muted" style={{ marginTop: 10 }}>Signing you in…</p></>}
      </div>
    </div>
  );
}
