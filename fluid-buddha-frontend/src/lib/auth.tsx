"use client";
/**
 * Client-side auth context. Holds the current tenant, persists the JWT in
 * localStorage, and exposes login/register/logout. ``useRequireAuth`` redirects
 * unauthenticated visitors to /login.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Api, Tenant, clearToken, getToken, setToken } from "./api";

type AuthState = {
  tenant: Tenant | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

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

  const login = async (email: string, password: string) => {
    const res = await Api.login(email, password);
    setToken(res.access_token);
    setTenant(res.tenant);
  };
  const register = async (email: string, password: string, name?: string) => {
    const res = await Api.register(email, password, name);
    setToken(res.access_token);
    setTenant(res.tenant);
  };
  const logout = () => {
    clearToken();
    setTenant(null);
  };

  return (
    <AuthContext.Provider value={{ tenant, loading, login, register, logout }}>
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
