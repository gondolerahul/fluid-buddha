"use client";
/**
 * Client-side auth context. Holds the current account (with your role in it
 * and who you are), persists the JWT in localStorage, and exposes
 * login/register/logout, `adopt` (a token from SSO or an accepted
 * invitation) and `switchAccount`. ``useRequireAuth`` redirects
 * unauthenticated visitors to /login. ``can`` mirrors the server's role rules
 * for showing or hiding controls; the server enforces them regardless.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Api, AuthResponse, ROLES, Role, Tenant, clearToken, getToken, setToken } from "./api";

type AuthState = {
  tenant: Tenant | null;
  role: Role | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  adopt: (token: string) => Promise<void>;
  accept: (res: AuthResponse) => void;
  switchAccount: (tenantId: string) => Promise<void>;
  logout: () => void;
  can: (needed: Role) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

function fromResponse(res: AuthResponse): Tenant {
  return { ...res.tenant, role: res.role, user: res.user };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const me = await Api.me();
        if (active) setTenant(me);
      } catch {
        clearToken();
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const accept = useCallback((res: AuthResponse) => {
    setToken(res.access_token);
    setTenant(fromResponse(res));
  }, []);
  const login = async (email: string, password: string) => accept(await Api.login(email, password));
  const register = async (email: string, password: string, name?: string) =>
    accept(await Api.register(email, password, name));
  const adopt = useCallback(async (token: string) => {
    setToken(token);
    try {
      setTenant(await Api.me());
    } catch (e) {
      clearToken();
      throw e;
    }
  }, []);
  const switchAccount = async (tenantId: string) => accept(await Api.switchAccount(tenantId));
  const logout = () => {
    clearToken();
    setTenant(null);
  };
  const role = tenant?.role ?? null;
  const can = (needed: Role) => role != null && ROLES.indexOf(role) >= ROLES.indexOf(needed);

  return (
    <AuthContext.Provider value={{ tenant, role, loading, login, register, adopt, accept,
      switchAccount, logout, can }}>
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
  useEffect(() => {
    if (!auth.loading && !auth.tenant) router.replace("/login");
  }, [auth.loading, auth.tenant, router]);
  return auth;
}
