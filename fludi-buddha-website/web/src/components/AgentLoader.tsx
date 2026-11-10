"use client";

import { useEffect } from "react";

/**
 * Loads the real FluidBuddha widget when configured, so this site runs on its own product.
 *   NEXT_PUBLIC_FB_LOADER_URL  e.g. https://<server>/widget/loader.js
 *   NEXT_PUBLIC_FB_KEY         the site's widget key (fbk_…)
 * Set the site to design Level 3 ("The Atmosphere") in the console; the site's own ask bar forwards
 * questions to it through the element's public ask() method.
 */
export default function AgentLoader() {
  useEffect(() => {
    const src = process.env.NEXT_PUBLIC_FB_LOADER_URL;
    const key = process.env.NEXT_PUBLIC_FB_KEY;
    if (!src || !key || document.querySelector("script[data-fb-loader]")) return;
    const s = document.createElement("script");
    s.src = src; s.async = true;
    s.dataset.key = key; s.dataset.fbLoader = "1";
    document.body.appendChild(s);
  }, []);
  return null;
}
