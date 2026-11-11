// Content model for the four worlds (docs/marketing-docs/WebsitePlan.md §3, §4 and §11).
// A world sets theme, film and structure. A role only changes words.
// Redesign of 11 November 2026: docs/marketing-docs/website/audit-2026-11-11.md §5.

import type { MediaKey } from "../media";

export type WorldId = "default" | "saas" | "education" | "enterprise";

/** [plain, emphasised] or [plain, emphasised, plain]. */
export type Title = [string, string] | [string, string, string];

/** A role changes words only, and where its two buttons lead. */
export type Role = { id: string; label: string; sub: string; primary: string; primaryHref: string; secondary: string; secondaryHref: string };
export type Link = { label: string; href: string };

export type Chapter = {
  id: string;
  /** Short name in the chapter rail beside the film. */
  label: string;
  title: Title;
  body?: string;
  note?: string;
  /** A Hindi line shown large above the title. */
  quote?: string;
  /** Whether the picture behind the copy is dark or light. */
  tone?: "dark" | "light";
  /** The stretch of the film this chapter is shown for, as fractions from 0 to 1. */
  at: [number, number];
  /** Where the subject of the picture is, from 0 (left) to 1 (right), kept in view when the picture is cropped. */
  focus?: number;
  /** Shows the "What do you do?" selector under the copy. */
  selector?: boolean;
};

/**
 * The film behind a world's hero and chapters.
 *  - "frames": a rendered film scrubbed by scroll (default, education).
 *  - "code": drawn live in the browser (saas in characters, enterprise as line drawings).
 */
export type Film = {
  kind: "frames" | "code";
  code?: { id: "saas" | "enterprise"; length: number; heroAt: [number, number] };
  frames?: { dir: string; mobileDir?: string; ext?: "jpg" | "webp"; count: number; pxPerFrame: number; poster: string; heroAt: [number, number]; heroFocus?: number;
    /** On upright screens, the share of the screen height the picture fills, from the top. The copy sits below it. */
    portraitTop?: number };
  chapters: Chapter[];
};

export type Item = { n?: string; title: string; body: string };
type Base = { id: string };

export type Section =
  // shared
  | (Base & { kind: "faq"; title: Title; lead?: string; ask?: string; items: { q: string; a: string }[] })
  | (Base & { kind: "close"; title: Title; lead: string; primary: Link; secondary: Link; media?: MediaKey })
  | (Base & { kind: "limits"; title: Title; items: string[]; aside?: { title: string; body: string } })
  // default: amber glass
  | (Base & { kind: "ask"; title: Title; lead: string; questions: { label: string; hi?: boolean }[] })
  | (Base & { kind: "bento"; title: Title; items: { key: "talks" | "shows" | "there" | "sources" | "books" | "proves"; title: string; body: string }[] })
  | (Base & { kind: "fit"; title: Title; lead: string; states: { id: string; label: string; line: string; order: ("hero" | "pricing" | "security" | "proof" | "resume" | "cta")[] }[]; note: string })
  | (Base & { kind: "doors"; title: Title; lead?: string; doors: { to: WorldId; label: string; title: string; media: MediaKey }[]; also: Link[] })
  | (Base & { kind: "start"; title: Title; steps: Item[] })
  | (Base & { kind: "plans"; title: Title; link: Link })
  // saas: night console
  | (Base & { kind: "lead-desk"; title: Title; lead: string })
  | (Base & { kind: "try-site"; title: Title; lead: string })
  | (Base & { kind: "questions"; title: Title; rows: { q: string; a: string; does: string }[] })
  | (Base & { kind: "holdout"; title: Title; steps: Item[]; note: string })
  | (Base & { kind: "cost"; title: Title; body: string; note: string })
  | (Base & { kind: "install"; title: Title; lead: string; tabs: { label: string; code: string }[] })
  | (Base & { kind: "facts"; title: Title; items: { text: string; ok: boolean }[] })
  // education: lamp to morning
  | (Base & { kind: "hindi-answer"; title: Title; lead: string })
  | (Base & { kind: "visit"; title: Title; steps: (Item & { media: MediaKey })[] })
  | (Base & { kind: "phone"; title: Title; lead: string; ticks: string[] })
  | (Base & { kind: "counsellor"; title: Title; lead: string; items: string[]; note: string; media: MediaKey })
  | (Base & { kind: "pair"; left: { title: string; items: string[]; note?: string }; right: { id: string; title: string; items: string[]; note?: string } })
  | (Base & { kind: "return"; title: Title; body: string; note: string })
  // enterprise: the specification
  | (Base & { kind: "spec-table"; num: string; title: Title; head: [string, string]; rows: [string, string][]; note?: string; cta?: Link })
  | (Base & { kind: "flow"; num: string; title: Title; zones: { n: string; title: string; body: string }[]; note: string })
  | (Base & { kind: "controls"; num: string; title: Title; items: Item[] })
  | (Base & { kind: "rules"; num: string; title: Title; lead: string })
  | (Base & { kind: "spec-list"; num: string; title: Title; items: string[]; note?: string; cta?: Link })
  | (Base & { kind: "timeline"; num: string; title: Title; rows: { stage: string; weeks: [number, number]; what: string }[]; cta: Link })
  | (Base & { kind: "visitors"; num: string; title: Title; items: string[] });

export type World = {
  id: WorldId;
  path: string;
  /** Short name used in the morph line. */
  name: string;
  /** "Changing this site for …" */
  audience: string;
  theme: "dark" | "light";
  meta: { title: string; description: string };
  hero: {
    title: Title;
    /** Sub-line when the world has no roles (the default world). */
    sub?: string;
    primary?: Link;
    secondary?: Link;
    roles?: Role[];
    tone?: "dark" | "light";
  };
  film: Film;
  sections: Section[];
  /**
   * Reviewed Hindi for the showcase (WebsitePlan.md §3.5). Only these blocks change when the visitor
   * picks Hindi; everything else stays in English. A headline is written "plain|emphasis" or "plain|emphasis|plain".
   */
  hi?: Hindi;
};

export type Hindi = {
  title: string;
  /** The hero sub-line. In a world with roles it belongs to the first role. */
  sub?: string;
  /** The main button (hero). */
  cta?: string;
  secondary?: string;
  /** Chapter id -> headline. */
  chapters?: Record<string, string>;
  /** Section id -> headline and list items by position. */
  sections?: Record<string, { title?: string; items?: Record<number, string> }>;
};
