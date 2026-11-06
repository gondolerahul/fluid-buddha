"use client";

import { useEffect } from "react";

/** Sets the page's canvas (paper or ink) on <html>, so the nav, ask bar and footer follow it. */
export default function Theme({ theme }: { theme: "paper" | "ink" }) {
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    return () => { document.documentElement.dataset.theme = "paper"; };
  }, [theme]);
  return null;
}
