"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

export function AppHeader() {
  const { tenant, logout } = useAuth();
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
          <span className="brand-name">Fluid-Buddha</span>
          <span className="badge" style={{ marginLeft: 4 }}>Console</span>
        </Link>
        <div className="row" style={{ gap: 14 }}>
          {tenant && <span className="muted" style={{ fontSize: "0.86rem" }}>{tenant.email}</span>}
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
