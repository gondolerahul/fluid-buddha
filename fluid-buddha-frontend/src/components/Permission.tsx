"use client";
/**
 * Showing only what your role can do (M2-1 follow-up). The server refuses
 * anything a role can't do regardless; these keep Viewers from seeing buttons
 * that would only fail.
 *
 *   <EditOnly>…</EditOnly>          rendered for Editors and above
 *   <EditOnly role="admin">…</EditOnly>
 *   <Editable>…form…</Editable>     inputs read-only (disabled) below Editor
 */
import { Role } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function EditOnly({ children, role = "editor" }: { children: React.ReactNode; role?: Role }) {
  return useAuth().can(role) ? <>{children}</> : null;
}

export function Editable({ children, role = "editor" }: { children: React.ReactNode; role?: Role }) {
  const ok = useAuth().can(role);
  return (
    <fieldset disabled={!ok} className="plain-fieldset" aria-readonly={!ok || undefined}>
      {children}
    </fieldset>
  );
}

/** The note a Viewer sees at the top of a website's pages. */
export function ViewOnlyNote() {
  const { can, role } = useAuth();
  if (can("editor")) return null;
  return (
    <div className="notice" style={{ marginBottom: 18 }}>
      You can look at everything here but not change it — your role is <strong>{role}</strong>. Ask an Admin
      if you need to edit.
    </div>
  );
}
