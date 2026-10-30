"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { Api, Website } from "@/lib/api";

type Ctx = { website: Website | null; loading: boolean; notFound: boolean; reload: () => void };
const WebsiteCtx = createContext<Ctx>({ website: null, loading: true, notFound: false, reload: () => {} });

export function WebsiteProvider({ id, children }: { id: string; children: React.ReactNode }) {
  const [website, setWebsite] = useState<Website | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const reload = () => {
    setLoading(true);
    Api.getWebsite(id)
      .then((w) => { setWebsite(w); setNotFound(false); })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  };
  useEffect(reload, [id]);

  return <WebsiteCtx.Provider value={{ website, loading, notFound, reload }}>{children}</WebsiteCtx.Provider>;
}

export const useWebsite = () => useContext(WebsiteCtx);
