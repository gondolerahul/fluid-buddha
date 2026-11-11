import type { MetadataRoute } from "next";
import { WORLDS } from "@/content/worlds";
import { LEGAL, PAGES } from "@/content/pages";

const BASE = "https://fluidbuddha.com";

/** Every public page. Link parameters (?for=, ?role=, ?lang=) are never listed: each page has one clean URL. */
export default function sitemap(): MetadataRoute.Sitemap {
  const worlds = Object.values(WORLDS).map((w) => ({
    url: `${BASE}${w.path === "/" ? "" : w.path}`,
    changeFrequency: "weekly" as const,
    priority: w.id === "default" ? 1 : 0.9,
  }));
  const fixed = ["/pricing", "/demo"].map((p) => ({ url: `${BASE}${p}`, changeFrequency: "weekly" as const, priority: 0.8 }));
  const pages = PAGES.map((p) => ({ url: `${BASE}/${p.path}`, changeFrequency: "monthly" as const, priority: 0.6 }));
  const legal = Object.keys(LEGAL).map((k) => ({ url: `${BASE}/legal/${k}`, changeFrequency: "yearly" as const, priority: 0.2 }));
  return [...worlds, ...fixed, ...pages, ...legal];
}
