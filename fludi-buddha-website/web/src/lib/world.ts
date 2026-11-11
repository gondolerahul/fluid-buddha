// Working out which world a visitor belongs in (docs/marketing-docs/WebsitePlan.md §3.2).
// Everything here is plain logic with no React, so it can be tested on its own.

import type { WorldId } from "@/content/worlds/types";

export const WORLD_KEY = "fb:world";
export const GO_EVENT = "fb:go-world";

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

export function worldPath(id: WorldId) {
  return id === "default" ? "/" : `/for/${id}`;
}

export function worldFromPath(pathname: string): WorldId {
  const m = pathname.match(/^\/for\/([a-z]+)/);
  return m && isPersonaWorld(m[1]) ? m[1] : "default";
}

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

  // Only our own pages count as a hint (for example arriving from /industries/education).
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

/** Ask the site to change to another world. Handled by <WorldSwitch>. */
export function goWorld(id: WorldId, how: "selector" | "chip" | "offer" | "agent" | "remembered" = "selector") {
  window.dispatchEvent(new CustomEvent(GO_EVENT, { detail: { id, how } }));
}

/** Measurement hook: pushes to window.dataLayer when one exists (WebsitePlan.md §11). */
export function track(event: string, data: Record<string, unknown> = {}) {
  const w = window as unknown as { dataLayer?: unknown[] };
  w.dataLayer?.push({ event: `fb_${event}`, ...data });
  window.dispatchEvent(new CustomEvent("fb:track", { detail: { event, ...data } }));
}
