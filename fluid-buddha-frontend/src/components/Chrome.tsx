"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Account, Api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Shown only to people in more than one account. */
function AccountSwitcher() {
  const { tenant, switchAccount } = useAuth();
  const router = useRouter();
  const [accounts, setAccounts] = useState<Account[]>([]);
  useEffect(() => {
    let live = true;
    if (tenant) Api.accounts().then((a) => { if (live) setAccounts(a); }).catch(() => {});
    return () => { live = false; };
  }, [tenant]);
  if (!tenant || accounts.length < 2) return null;
  return (
    <select className="select" style={{ width: "auto", padding: "4px 8px", fontSize: "0.84rem" }}
      aria-label="Switch account" value={tenant.id}
      onChange={async (e) => { await switchAccount(e.target.value); router.push("/dashboard"); }}>
      {accounts.map((a) => <option key={a.id} value={a.id}>{a.name} ({a.role})</option>)}
    </select>
  );
}

export function AppHeader() {
  const { tenant, logout, can } = useAuth();
  return (
    <header
      style={{
        borderBottom: "1px solid var(--line)",
        background: "rgba(11,13,18,0.7)",
        backdropFilter: "blur(10px)",
        position: "sticky",
        top: 0,
        zIndex: 20,
      }}
    >
      <div
        className="row between"
        style={{ maxWidth: 1180, margin: "0 auto", padding: "14px 40px" }}
      >
        <Link href="/dashboard" className="brand" style={{ margin: 0 }}>
          <span className="brand-dot" />
          <span className="brand-name">FluidBuddha</span>
          <span className="badge" style={{ marginLeft: 4 }}>Console</span>
        </Link>
        <div className="row" style={{ gap: 14 }}>
          <AccountSwitcher />
          {tenant && <Link href="/live" className="btn btn-ghost btn-sm">Live</Link>}
          {tenant && <Link href="/team" className="btn btn-ghost btn-sm">Team</Link>}
          {tenant && can("admin") && <Link href="/audit" className="btn btn-ghost btn-sm">Audit log</Link>}
          {tenant && can("admin") && <Link href="/billing" className="btn btn-ghost btn-sm">Billing</Link>}
          {tenant && <span className="muted" style={{ fontSize: "0.86rem" }}
            title={tenant.role ? `Your role: ${tenant.role}` : undefined}>
            {tenant.user?.email ?? tenant.email}{tenant.role && tenant.role !== "owner" ? ` · ${tenant.role}` : ""}
          </span>}
          <button className="btn btn-ghost btn-sm" onClick={logout}>Sign out</button>
        </div>
      </div>
    </header>
  );
}

const TABS = [
  { key: "install", label: "Install" },
  { key: "ingestion", label: "Ingestion" },
  { key: "tour", label: "Tour" },
  { key: "insights", label: "Insights" },
  { key: "leads", label: "Leads" },
  { key: "cache", label: "Responses" },
  { key: "analytics", label: "Analytics" },
  { key: "experiment", label: "Holdout" },
  { key: "tests", label: "A/B tests" },
  { key: "triggers", label: "Triggers" },
  { key: "settings", label: "Settings" },
];

export function WebsiteTabs({ id, name }: { id: string; name: string }) {
  const path = usePathname();
  const active = TABS.find((t) => path?.endsWith(`/${t.key}`))?.key;
  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "28px 40px 0" }}>
      <Link href="/dashboard" className="faint" style={{ fontSize: "0.84rem" }}>
        ← All websites
      </Link>
      <h1 className="h-page" style={{ marginTop: 10 }}>{name}</h1>
      <div className="tabs" style={{ marginTop: 18 }}>
        {TABS.map((t) => (
          <Link
            key={t.key}
            href={`/websites/${id}/${t.key}`}
            className={`tab ${active === t.key ? "active" : ""}`}
          >
            {t.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
