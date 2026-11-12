// Working out which world a visitor belongs in (docs/marketing-docs/WebsitePlan.md §3.2), and what each
// world calls itself in the shared header and footer. Plain logic with no React, so it can be tested on its own.

import type { WorldId } from "@/content/worlds/types";

export const WORLD_KEY = "fb:world";
export const GO_EVENT = "fb:go-world";
export const WORLD_IDS: WorldId[] = ["default", "saas", "education", "enterprise"];

/** How each version is named in the version switch, and the main button the header shows for it. */
export const VERSIONS: Record<WorldId, { label: string; short: string; line: string; cta: { label: string; href: string } }> = {
  default: { label: "General", short: "General", line: "For any business website", cta: { label: "Start free", href: "/demo#start" } },
  saas: { label: "SaaS teams", short: "SaaS", line: "Pricing pages, technical buyers, scored leads", cta: { label: "Try it on your site", href: "/demo#your-site" } },
  education: { label: "Universities", short: "Education", line: "Admissions at night, in Hindi or English", cta: { label: "See it in Hindi", href: "/for/education?lang=hi" } },
  enterprise: { label: "Banks and insurers", short: "Banks", line: "On your servers, inside your rules", cta: { label: "Plan a pilot", href: "/book-demo" } },
};

export type Resolution =
  /** Land directly in that world, no morph (a link said so). */
  | { how: "link"; world: WorldId }
  /** The visitor chose this world before: morph after first paint. */
  | { how: "remembered"; world: WorldId }
  /** A weaker hint: offer the world, do not switch without a click. */
  | { how: "referrer"; world: WorldId }
  | null;

const PERSONA: WorldId[] = ["saas", "education", "enterprise"];

/** Maps a free-form word (campaign name, persona name, path) to a world. */
export function matchWorld(text: string | null | undefined): WorldId | null {
  if (!text) return null;
  const t = text.toLowerCase();
  if (/(^|[^a-z])(saas|b2b|software|startup)/.test(t)) return "saas";
  if (/(^|[^a-z])(edu|universit|college|school|admission|student|edtech)/.test(t)) return "education";
  if (/(^|[^a-z])(enterprise|bank|insur|fintech|nbfc|bfsi|regulated)/.test(t)) return "enterprise";
  return null;
}

export function isPersonaWorld(v: string | null | undefined): v is WorldId {
  return !!v && (PERSONA as string[]).includes(v);
}
export function isWorld(v: string | null | undefined): v is WorldId {
  return !!v && (WORLD_IDS as string[]).includes(v);
}

export function worldPath(id: WorldId) {
  return id === "default" ? "/" : `/for/${id}`;
}

export function worldFromPath(pathname: string): WorldId {
  const m = pathname.match(/^\/for\/([a-z]+)/);
  return m && isPersonaWorld(m[1]) ? m[1] : "default";
}

/** A world's own page (as opposed to a content page that only borrows the visitor's world). */
export function isWorldPage(pathname: string) {
  return pathname === "/" || /^\/for\/(saas|education|enterprise)\/?$/.test(pathname);
}

/**
 * The script that sets <html data-world> before the first paint (app/layout.tsx), so the page never
 * flashes another world's colours: a world page takes its own world; any other page takes the
 * visitor's remembered choice.
 */
export const WORLD_BOOT = `(function(){try{var p=location.pathname,m=p.match(/^\\/for\\/(saas|education|enterprise)\\/?$/),w=m?m[1]:(p==="/"?"default":localStorage.getItem("${WORLD_KEY}"));if(!/^(default|saas|education|enterprise)$/.test(w||""))w="default";document.documentElement.setAttribute("data-world",w)}catch(e){}})()`;

/**
 * Decides what to do for a visitor arriving on the default site.
 * Order: link parameter, remembered choice, referrer. (The selector and the agent act later, on events.)
 */
export function resolveWorld(input: { search: string; referrer: string; origin: string; remembered: string | null }): Resolution {
  const q = new URLSearchParams(input.search);
  const explicit = q.get("for");
  if (isPersonaWorld(explicit)) return { how: "link", world: explicit };
  const campaign = matchWorld(q.get("utm_campaign")) ?? matchWorld(q.get("utm_content"));
  if (campaign) return { how: "link", world: campaign };

  if (isPersonaWorld(input.remembered)) return { how: "remembered", world: input.remembered };

  // Only our own pages count as a hint (for example arriving from /solutions/sales).
  try {
    const ref = new URL(input.referrer);
    if (ref.origin === input.origin) {
      const hint = matchWorld(ref.pathname);
      if (hint) return { how: "referrer", world: hint };
    }
  } catch { /* no referrer */ }
  return null;
}

/** Reads the persona out of a `fluidbuddha:set_persona` event from the agent (FR-NAV-05). */
export function worldFromPersonaEvent(detail: unknown): WorldId | null {
  if (typeof detail === "string") return matchWorld(detail);
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    for (const k of ["persona", "id", "name", "label"]) if (typeof d[k] === "string") { const w = matchWorld(d[k] as string); if (w) return w; }
  }
  return null;
}

// ---- browser helpers (safe to call only on the client)
export function remembered(): string | null {
  try { return window.localStorage.getItem(WORLD_KEY); } catch { return null; }
}
export function remember(id: WorldId) {
  try { if (id === "default") window.localStorage.removeItem(WORLD_KEY); else window.localStorage.setItem(WORLD_KEY, id); } catch { /* storage unavailable */ }
}
/** The world now on screen. */
export function currentWorld(): WorldId {
  const w = typeof document === "undefined" ? null : document.documentElement.getAttribute("data-world");
  return isWorld(w) ? w : "default";
}
/** Puts a world's colours, type and buttons on the whole page. */
export function applyWorld(id: WorldId) {
  document.documentElement.setAttribute("data-world", id);
}

/** Ask the site to change to another world. Handled by <WorldSwitch>. */
export function goWorld(id: WorldId, how: "selector" | "chip" | "offer" | "agent" | "remembered" | "menu" | "ask" = "selector") {
  window.dispatchEvent(new CustomEvent(GO_EVENT, { detail: { id, how } }));
}

/** Measurement hook: pushes to window.dataLayer when one exists (WebsitePlan.md §11). */
export function track(event: string, data: Record<string, unknown> = {}) {
  const w = window as unknown as { dataLayer?: unknown[] };
  w.dataLayer?.push({ event: `fb_${event}`, ...data });
  window.dispatchEvent(new CustomEvent("fb:track", { detail: { event, ...data } }));
}
