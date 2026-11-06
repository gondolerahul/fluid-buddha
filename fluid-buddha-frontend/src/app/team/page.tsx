"use client";
import { useCallback, useEffect, useState } from "react";
import { useRequireAuth } from "@/lib/auth";
import { AccountSecurity, Api, ApiError, Member, ROLES, Role, SSOConfig, Team } from "@/lib/api";
import { AppHeader } from "@/components/Chrome";
import { DigestCard } from "@/components/DigestCard";
import { LoadingScreen, Spinner, fmtDate, useToast } from "@/components/ui";

const ROLE_HELP: Record<Role, string> = {
  viewer: "Can look at everything, change nothing.",
  editor: "Works on the websites: knowledge, tours, answers, experiments, leads.",
  admin: "Also manages the team, integrations, privacy and deleting websites.",
  owner: "Everything, including billing and single sign-on.",
};

export default function TeamPage() {
  const auth = useRequireAuth();
  const toast = useToast();
  const [team, setTeam] = useState<Team | null>(null);
  const load = useCallback(() => Api.team().then(setTeam).catch(() => {}), []);
  useEffect(() => { if (auth.tenant) load(); }, [auth.tenant, load]);

  if (auth.loading || !auth.tenant) return <LoadingScreen />;
  const isAdmin = auth.can("admin");

  const act = async (fn: () => Promise<unknown>, done: string) => {
    try {
      await fn();
      toast(done);
      await load();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Something went wrong", "err");
    }
  };

  return (
    <>
      <AppHeader />
      <main className="content stack" style={{ margin: "0 auto" }}>
        <div className="page-head">
          <h1 className="h-page">Team</h1>
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            Everyone who can use {auth.tenant.name || "this account"}. Your role:{" "}
            <strong>{auth.role}</strong> — {auth.role && ROLE_HELP[auth.role]}
          </p>
        </div>

        {isAdmin && <InviteCard canOwner={auth.role === "owner"} onDone={load} />}

        <section className="card">
          <h3 style={{ marginBottom: 12 }}>Members</h3>
          {!team ? <div className="skeleton" style={{ height: 120 }} /> : (
            <table className="table">
              <thead><tr><th>Person</th><th>Role</th><th>Two-factor</th><th>Last sign-in</th><th /></tr></thead>
              <tbody>
                {team.members.map((m) => (
                  <MemberRow key={m.id} m={m} me={team.me.id === m.id} viewerRole={auth.role!}
                    onRole={(r) => act(() => Api.changeRole(m.id, r), `${m.email} is now ${r}`)}
                    onRemove={() => {
                      if (window.confirm(`Remove ${m.email} from this account?`))
                        act(() => Api.removeMember(m.id), `${m.email} removed`);
                    }} />
                ))}
              </tbody>
            </table>
          )}
        </section>

        {team && team.invitations.length > 0 && (
          <section className="card">
            <h3 style={{ marginBottom: 12 }}>Pending invitations</h3>
            <table className="table">
              <thead><tr><th>Email</th><th>Role</th><th>Expires</th><th /></tr></thead>
              <tbody>
                {team.invitations.map((i) => (
                  <tr key={i.id}>
                    <td>{i.email}</td><td>{i.role}</td><td>{fmtDate(i.expires_at)}</td>
                    <td style={{ textAlign: "right" }}>
                      {isAdmin && <button className="btn btn-sm btn-ghost"
                        onClick={() => act(() => Api.revokeInvitation(i.id), "Invitation withdrawn")}>
                        Withdraw</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {isAdmin && <AccountSecurityCard isOwner={auth.role === "owner"}
          meHasMfa={!!auth.tenant.security?.mfa_enabled} onChange={load} />}
        {isAdmin && <DigestCard />}
        {isAdmin && <SSOCard isOwner={auth.role === "owner"} />}
      </main>
    </>
  );
}

function MemberRow({ m, me, viewerRole, onRole, onRemove }: {
  m: Member; me: boolean; viewerRole: Role; onRole: (r: Role) => void; onRemove: () => void;
}) {
  const isOwnerViewer = viewerRole === "owner";
  const canManage = (viewerRole === "admin" || isOwnerViewer) && (m.role !== "owner" || isOwnerViewer);
  const choices = ROLES.filter((r) => r !== "owner" || isOwnerViewer);
  return (
    <tr>
      <td>
        <div>{m.name || m.email}{me && <span className="faint"> (you)</span>}</div>
        {m.name && <div className="faint" style={{ fontSize: "0.8rem" }}>{m.email}</div>}
        {!m.has_password && <div className="faint" style={{ fontSize: "0.76rem" }}>signs in with SSO</div>}
      </td>
      <td>
        {canManage ? (
          <select className="select" style={{ width: "auto" }} value={m.role}
            aria-label={`Role of ${m.email}`} onChange={(e) => onRole(e.target.value as Role)}>
            {choices.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        ) : m.role}
      </td>
      <td>{!m.has_password ? <span className="faint">via SSO</span>
        : m.mfa_enabled ? <span className="badge ok">On</span> : <span className="badge">Off</span>}</td>
      <td className="faint">{fmtDate(m.last_login_at)}</td>
      <td style={{ textAlign: "right" }}>
        {canManage && !me && <button className="btn btn-sm btn-ghost" onClick={onRemove}>Remove</button>}
      </td>
    </tr>
  );
}

function InviteCard({ canOwner, onDone }: { canOwner: boolean; onDone: () => void }) {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("editor");
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<{ link: string; emailed: boolean } | null>(null);

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await Api.invite(email.trim(), role);
      setLink({ link: r.link, emailed: r.emailed });
      toast(r.emailed ? `Invitation sent to ${email}` : "Invitation created — copy the link below");
      setEmail("");
      onDone();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not invite", "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h3 style={{ marginBottom: 12 }}>Invite someone</h3>
      <form onSubmit={send} className="row wrap" style={{ gap: 10, alignItems: "flex-end" }}>
        <div className="field" style={{ flex: "1 1 260px" }}>
          <label className="label">Email</label>
          <input className="input" type="email" required value={email} placeholder="colleague@company.com"
            onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label className="label">Role</label>
          <select className="select" value={role} aria-label="Role for the invitation"
            onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.filter((r) => r !== "owner" || canOwner).map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <button className="btn btn-primary" disabled={busy}>{busy ? <Spinner /> : "Send invitation"}</button>
      </form>
      <p className="faint" style={{ fontSize: "0.8rem", marginTop: 8 }}>{ROLE_HELP[role]}</p>
      {link && (
        <div style={{ marginTop: 12 }}>
          <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 6 }}>
            {link.emailed ? "Also shareable directly (works once, for 7 days):"
              : "Email isn't set up on this server, so share this link yourself (works once, for 7 days):"}
          </p>
          <div className="row" style={{ gap: 8 }}>
            <input className="input mono" readOnly value={link.link} aria-label="Invitation link" />
            <button type="button" className="btn btn-sm"
              onClick={() => { navigator.clipboard.writeText(link.link); toast("Link copied"); }}>Copy</button>
          </div>
        </div>
      )}
    </section>
  );
}

function SSOCard({ isOwner }: { isOwner: boolean }) {
  const toast = useToast();
  const [cfg, setCfg] = useState<SSOConfig | null>(null);
  const load = useCallback(() => Api.ssoConfig().then(setCfg).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  if (!cfg) return <div className="skeleton" style={{ height: 160 }} />;
  return <SSOForm key={JSON.stringify(cfg)} cfg={cfg} isOwner={isOwner} reload={load} toast={toast} />;
}

function SSOForm({ cfg, isOwner, reload, toast }: {
  cfg: SSOConfig; isOwner: boolean; reload: () => void; toast: ReturnType<typeof useToast>;
}) {
  const [issuer, setIssuer] = useState(cfg.issuer ?? "");
  const [clientId, setClientId] = useState(cfg.client_id ?? "");
  const [secret, setSecret] = useState("");
  const [defaultRole, setDefaultRole] = useState(cfg.default_role ?? "viewer");
  const [requireSSO, setRequireSSO] = useState(cfg.require_sso ?? false);
  const [domain, setDomain] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const run = async (key: string, fn: () => Promise<unknown>, done: string) => {
    setBusy(key);
    try {
      await fn();
      toast(done);
      reload();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Something went wrong", "err");
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="card">
      <h3 style={{ marginBottom: 4 }}>Single sign-on</h3>
      <p className="muted" style={{ fontSize: "0.84rem", marginBottom: 14 }}>
        Let your team sign in with your company&apos;s identity provider (Okta, Microsoft Entra, Auth0,
        Keycloak or any OpenID Connect provider). Anyone can also use “Sign in with Google” if they&apos;re
        already a member. {!isOwner && "Only the Owner can change these settings."}
      </p>
      <fieldset disabled={!isOwner} className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
        <div className="grid grid-2" style={{ gap: 12 }}>
          <div className="field">
            <label className="label">Issuer URL</label>
            <input className="input mono" value={issuer} placeholder="https://your-company.okta.com"
              onChange={(e) => setIssuer(e.target.value)} />
          </div>
          <div className="field">
            <label className="label">Redirect URI <span className="faint">(enter this at your provider)</span></label>
            <input className="input mono" readOnly value={cfg.redirect_uri} aria-label="Redirect URI" />
          </div>
          <div className="field">
            <label className="label">Client ID</label>
            <input className="input mono" value={clientId} onChange={(e) => setClientId(e.target.value)} />
          </div>
          <div className="field">
            <label className="label">Client secret</label>
            <input className="input mono" type="password" value={secret}
              placeholder={cfg.has_secret ? "•••••••• (saved — leave empty to keep)" : ""}
              onChange={(e) => setSecret(e.target.value)} />
          </div>
          <div className="field">
            <label className="label">Role for people joining through SSO</label>
            <select className="select" value={defaultRole} aria-label="Default role"
              onChange={(e) => setDefaultRole(e.target.value as typeof defaultRole)}>
              {(["viewer", "editor", "admin"] as const).map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <label className="row" style={{ gap: 8, alignSelf: "end", fontSize: "0.88rem" }}>
            <input type="checkbox" checked={requireSSO} onChange={(e) => setRequireSSO(e.target.checked)} />
            Require SSO for your domains (the Owner can still use a password)
          </label>
        </div>
        <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
          {cfg.configured && <button type="button" className="btn btn-danger btn-sm" disabled={busy !== null}
            onClick={() => window.confirm("Turn off single sign-on?") &&
              run("off", () => Api.deleteSSO(), "Single sign-on removed")}>Remove</button>}
          <button type="button" className="btn btn-primary btn-sm" disabled={busy !== null || !issuer || !clientId}
            onClick={() => run("save", () => Api.saveSSO({
              issuer: issuer.trim(), client_id: clientId.trim(), client_secret: secret || undefined,
              default_role: defaultRole, require_sso: requireSSO, enabled: true,
            }), "Single sign-on saved")}>
            {busy === "save" ? <Spinner /> : "Save"}
          </button>
        </div>

        <div style={{ borderTop: "1px solid var(--line)", paddingTop: 14 }}>
          <h4 style={{ marginBottom: 6 }}>Your email domains</h4>
          <p className="faint" style={{ fontSize: "0.8rem", marginBottom: 10 }}>
            SSO signs in people whose email is on a domain you&apos;ve proven. Add the domain, publish the TXT
            record at your DNS provider, then press Verify.
          </p>
          {cfg.domains.map((d) => (
            <div key={d.domain} className="card card-pad-sm" style={{ marginBottom: 8 }}>
              <div className="row between wrap" style={{ gap: 8 }}>
                <strong>{d.domain}</strong>
                <div className="row" style={{ gap: 6 }}>
                  {d.verified ? <span className="badge ok">verified</span> : (
                    <button type="button" className="btn btn-sm" disabled={busy !== null}
                      onClick={() => run(`v-${d.domain}`, () => Api.verifySSODomain(d.domain), `${d.domain} verified`)}>
                      {busy === `v-${d.domain}` ? <Spinner /> : "Verify"}</button>
                  )}
                  <button type="button" className="btn btn-sm btn-ghost" disabled={busy !== null}
                    onClick={() => run(`d-${d.domain}`, () => Api.deleteSSODomain(d.domain), `${d.domain} removed`)}>
                    Remove</button>
                </div>
              </div>
              {!d.verified && (
                <div className="faint" style={{ fontSize: "0.8rem", marginTop: 6 }}>
                  TXT record on <span className="mono">{d.txt_name}</span>:{" "}
                  <span className="mono" style={{ userSelect: "all" }}>{d.txt_value}</span>
                </div>
              )}
            </div>
          ))}
          <div className="row" style={{ gap: 8 }}>
            <input className="input" value={domain} placeholder="your-company.com" aria-label="Domain"
              onChange={(e) => setDomain(e.target.value)} />
            <button type="button" className="btn btn-sm" disabled={busy !== null || !domain.trim()}
              onClick={() => run("add", async () => { await Api.addSSODomain(domain.trim()); setDomain(""); },
                "Domain added — publish the TXT record, then Verify")}>Add domain</button>
          </div>
        </div>
      </fieldset>
    </section>
  );
}

/** Two-factor for the whole account and the quarterly access review (M2-11). */
function AccountSecurityCard({ isOwner, meHasMfa, onChange }: {
  isOwner: boolean; meHasMfa: boolean; onChange: () => void;
}) {
  const toast = useToast();
  const [sec, setSec] = useState<AccountSecurity | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => Api.security().then(setSec).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);

  const toggle = async () => {
    if (!sec) return;
    setBusy(true);
    try {
      await Api.saveSecurity(!sec.require_mfa);
      toast(sec.require_mfa ? "Two-factor is optional again" : "Two-factor is now required");
      await load();
      onChange();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not save", "err");
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    try {
      const blob = await Api.accessReviewCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `access-review-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Could not download", "err");
    }
  };

  return (
    <section className="card" id="access-review">
      <h3>Account security</h3>
      {!sec ? <div className="skeleton" style={{ height: 80, marginTop: 12 }} /> : (
        <div className="stack" style={{ marginTop: 12 }}>
          <div className="row between wrap" style={{ gap: 12 }}>
            <div>
              <strong>Require two-factor</strong>
              <p className="faint" style={{ fontSize: "0.84rem", marginTop: 4 }}>
                {sec.require_mfa
                  ? "Everyone signing in with a password must enter a code from an authenticator app."
                  : "Password sign-ins can skip the code. SSO sign-ins always use your identity provider's two-factor."}
                {sec.members_without_mfa.length > 0 &&
                  ` Without two-factor: ${sec.members_without_mfa.join(", ")}${sec.require_mfa ? " (asked at their next request)" : ""}.`}
              </p>
            </div>
            {isOwner ? (
              <button className={`btn btn-sm ${sec.require_mfa ? "" : "btn-primary"}`} disabled={busy || (!sec.require_mfa && !meHasMfa)}
                title={!sec.require_mfa && !meHasMfa ? "Turn on two-factor for yourself first (Security)" : undefined}
                onClick={toggle}>
                {busy ? <Spinner /> : sec.require_mfa ? "Make optional" : "Require"}
              </button>
            ) : <span className="badge">{sec.require_mfa ? "Required" : "Optional"}</span>}
          </div>
          {isOwner && !sec.require_mfa && !meHasMfa && (
            <p className="faint" style={{ fontSize: "0.8rem" }}>
              Turn on two-factor for yourself on the <a href="/security">Security</a> page first, so you can&apos;t be locked out.
            </p>
          )}
          <p className="faint" style={{ fontSize: "0.82rem" }}>
            Sessions end after {sec.session_idle_minutes} minutes without activity and after {sec.session_absolute_hours} hours
            in any case. {sec.login_max_attempts} wrong passwords or codes in a row lock a person out for {sec.login_lockout_minutes} minutes.
          </p>
          <div className="row between wrap" style={{ gap: 12 }}>
            <div>
              <strong>Access review</strong>
              <p className="faint" style={{ fontSize: "0.84rem", marginTop: 4 }}>
                Everyone who can sign in, their role, last activity and two-factor. Owners and Admins get a reminder
                each quarter; keep the downloaded list as your record of the review.
              </p>
            </div>
            <button className="btn btn-sm" onClick={download}>Download CSV</button>
          </div>
        </div>
      )}
    </section>
  );
}
