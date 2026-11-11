import type { MetadataRoute } from "next";
import { WORLDS } from "@/content/worlds";

const BASE = "https://fluidbuddha.com";

/** The four world pages. Each has one clean URL; link parameters (?for=, ?role=, ?lang=) are never listed. */
export default function sitemap(): MetadataRoute.Sitemap {
  return Object.values(WORLDS).map((w) => ({
    url: `${BASE}${w.path === "/" ? "" : w.path}`,
    changeFrequency: "weekly",
    priority: w.id === "default" ? 1 : 0.8,
  }));
}
