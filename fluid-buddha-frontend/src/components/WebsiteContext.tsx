"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Api, Website } from "@/lib/api";

type Ctx = { website: Website | null; loading: boolean; notFound: boolean; reload: () => void };
const WebsiteCtx = createContext<Ctx>({ website: null, loading: true, notFound: false, reload: () => {} });

export function WebsiteProvider({ id, children }: { id: string; children: React.ReactNode }) {
  const [website, setWebsite] = useState<Website | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  // State is only set when the request settles, never synchronously inside the
  // effect (react-hooks/set-state-in-effect).
  const fetchWebsite = useCallback(
    () =>
      Api.getWebsite(id)
        .then((w) => { setWebsite(w); setNotFound(false); })
        .catch(() => setNotFound(true))
        .finally(() => setLoading(false)),
    [id],
  );
  useEffect(() => { fetchWebsite(); }, [fetchWebsite]);

  const reload = useCallback(() => {
    setLoading(true);
    fetchWebsite();
  }, [fetchWebsite]);

  return <WebsiteCtx.Provider value={{ website, loading, notFound, reload }}>{children}</WebsiteCtx.Provider>;
}

export const useWebsite = () => useContext(WebsiteCtx);
