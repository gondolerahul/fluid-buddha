"use client";
/**
 * Client-side auth context. The session itself is an httpOnly cookie the
 * backend sets (M2-11), so this only holds who is signed in (the account,
 * your role in it, who you are) and the CSRF token for changes. It exposes
 * login (which may ask for a two-factor code), register, logout, `refresh`
 * (after SSO or anything else that changed the session), `accept` (a fresh
 * sign-in response) and `switchAccount`. ``useRequireAuth`` sends signed-out
 * visitors to /login, and anyone whose account requires two-factor they
 * haven't set up to /security. ``can`` mirrors the server's role rules for
 * showing or hiding controls; the server enforces them regardless.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Api, AuthResponse, MFA_REQUIRED, ROLES, Role, SESSION_ENDED, Tenant, clearLegacyToken, setCsrf,
} from "./api";

export type LoginResult = { mfaToken: string } | null;

type AuthState = {
  tenant: Tenant | null;
  role: Role | null;
  loading: boolean;
  /** Set when the last session ended by itself (timeout, revoked). */
  ended: boolean;
  login: (email: string, password: string) => Promise<LoginResult>;
  loginMfa: (mfaToken: string, code: { code?: string; recovery_code?: string }) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  refresh: () => Promise<Tenant | null>;
  accept: (res: AuthResponse) => void;
  switchAccount: (tenantId: string) => Promise<void>;
  logout: () => Promise<void>;
  can: (needed: Role) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

function fromResponse(res: AuthResponse): Tenant {
  return { ...res.tenant, role: res.role, user: res.user,
    security: { mfa_enabled: false, mfa_required: false, session_mfa: false, mfa_setup_required: false,
      idle_minutes: 60 } };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [ended, setEnded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const me = await Api.me();
      setCsrf(me.csrf_token);
      setTenant(me);
      setEnded(false);
      return me;
    } catch {
      setCsrf(null);
      setTenant(null);
      return null;
    }
  }, []);

  useEffect(() => {
    clearLegacyToken();
    let active = true;
    (async () => {
      try {
        const me = await Api.me();
        if (!active) return;
        setCsrf(me.csrf_token);
        setTenant(me);
      } catch {
        setCsrf(null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // A request answered "session ended": forget who was signed in.
  useEffect(() => {
    const onEnded = () => {
      setCsrf(null);
      setTenant((t) => {
        if (t) setEnded(true);
        return null;
      });
    };
    window.addEventListener(SESSION_ENDED, onEnded);
    return () => window.removeEventListener(SESSION_ENDED, onEnded);
  }, []);

  const accept = useCallback((res: AuthResponse) => {
    setCsrf(res.csrf_token);
    setTenant(fromResponse(res));
    setEnded(false);
    // The full picture (two-factor state) comes from /auth/me.
    void refresh();
  }, [refresh]);

  const login = async (email: string, password: string): Promise<LoginResult> => {
    const res = await Api.login(email, password);
    if ("mfa_required" in res) return { mfaToken: res.mfa_token };
    accept(res);
    return null;
  };
  const loginMfa = async (mfaToken: string, code: { code?: string; recovery_code?: string }) =>
    accept(await Api.loginMfa(mfaToken, code));
  const register = async (email: string, password: string, name?: string) =>
    accept(await Api.register(email, password, name));
  const switchAccount = async (tenantId: string) => accept(await Api.switchAccount(tenantId));
  const logout = async () => {
    try {
      await Api.logout();
    } finally {
      setCsrf(null);
      setTenant(null);
      setEnded(false);
    }
  };
  const role = tenant?.role ?? null;
  const can = (needed: Role) => role != null && ROLES.indexOf(role) >= ROLES.indexOf(needed);

  return (
    <AuthContext.Provider value={{ tenant, role, loading, ended, login, loginMfa, register, refresh,
      accept, switchAccount, logout, can }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useRequireAuth(): AuthState {
  const auth = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const setupNeeded = !!auth.tenant?.security?.mfa_setup_required;
  useEffect(() => {
    if (auth.loading) return;
    if (!auth.tenant) {
      const next = pathname && pathname !== "/" ? `&next=${encodeURIComponent(pathname)}` : "";
      router.replace(auth.ended ? `/login?expired=1${next}` : `/login${next ? `?${next.slice(1)}` : ""}`);
    } else if (setupNeeded && pathname !== "/security") {
      router.replace("/security?setup=1");
    }
  }, [auth.loading, auth.tenant, auth.ended, setupNeeded, pathname, router]);
  // A request refused for a missing second factor: go set it up.
  useEffect(() => {
    const onMfa = () => router.replace("/security?setup=1");
    window.addEventListener(MFA_REQUIRED, onMfa);
    return () => window.removeEventListener(MFA_REQUIRED, onMfa);
  }, [router]);
  return auth;
}
