// Content model for the four worlds (docs/marketing-docs/WebsitePlan.md §3, §4 and §11).
// A world sets theme, film and structure. A role only changes words.

export type WorldId = "default" | "saas" | "education" | "enterprise";

/** [plain, gold] or [plain, gold, plain]. The gold part is the emphasised phrase. */
export type Title = [string, string] | [string, string, string];

export type Role = { id: string; label: string; sub: string; primary: string; secondary: string };

export type SceneId = "s1" | "s3" | "s9" | "r0" | "r1" | "r5" | "r6";

export type Chapter = {
  id: string;
  eyebrow: string;
  title: Title;
  body?: string;
  note?: string;
  /** A Hindi line shown large above the title. */
  quote?: string;
  /** Rendered film: a still in /public/film/stills (without extension). */
  still?: string;
  /** Code film: a scene drawn in the browser. */
  scene?: SceneId;
  /** Whether the picture behind the copy is dark or light. */
  tone?: "dark" | "light";
  /** Scrubbed film only: the stretch of the film this chapter is shown for, as fractions from 0 to 1. */
  at?: [number, number];
  /** Short name for the chapter index beside the film. */
  label?: string;
  /**
   * Scrubbed film only: where the subject of the picture is, from 0 (left edge) to 1 (right edge).
   * On screens narrower than the film, the picture is moved so this point stays in view.
   */
  focus?: number;
  /** Shows the "What do you do?" selector under the copy. */
  selector?: boolean;
};

/**
 * The film behind a world's chapters.
 *  - "stills": one generated still per chapter, shown full screen (phase 3; replaced by scrubbed
 *    frames in phases 4 and 6 without changing the chapters).
 *  - "scenes": drawn in code (SaaS characters, Enterprise line drawings).
 */
export type Film = {
  kind: "stills" | "scenes" | "frames" | "code";
  /**
   * "code": a film drawn live in the browser from the scroll position: "saas" in characters
   * (components/world/asciiFilm.ts), "enterprise" as line drawings (components/world/lineFilm.ts).
   * `length` is its scroll distance in pixels. The scenes stay as stills for the look pages.
   */
  code?: { id: "saas" | "enterprise"; length: number; heroAt: [number, number] };
  /**
   * "frames": a rendered film scrubbed by scroll. `dir` holds f00001.jpg and so on; the hero is
   * shown for `heroAt` and each chapter for its own `at`.
   */
  frames?: { dir: string; mobileDir?: string; ext?: "jpg" | "webp"; count: number; pxPerFrame: number; poster: string; heroAt: [number, number]; heroFocus?: number;
    /** On upright screens, the share of the screen height the picture fills, from the top. The copy sits below it. */
    portraitTop?: number };
  /** "bleed" = every chapter fills the screen; "strip" = three framed figures in a row. */
  layout: "bleed" | "strip";
  intro?: { eyebrow: string; title: Title; lead?: string };
  chapters: Chapter[];
};

export type Item = { n?: string; title: string; body: string };

export type Section =
  | { kind: "cards"; id?: string; num?: string; eyebrow: string; title: Title; lead?: string; items: Item[]; cols: 3 | 4; overFilm?: string; steps?: boolean; dots?: boolean; note?: string }
  | { kind: "talk"; id?: string; eyebrow: string; title: Title; lead: string; questions: string[]; cta: { label: string; href: string } }
  | { kind: "list"; id?: string; num?: string; eyebrow: string; title: Title; items: string[]; note?: string; cta?: { label: string; href: string } }
  | { kind: "faq"; id?: string; num?: string; eyebrow: string; title: Title; items: { q: string; a: string }[] }
  | { kind: "close"; id?: string; title: Title; lead: string; primary: { label: string; href: string }; secondary: { label: string; href: string } }
  | { kind: "table"; id?: string; num?: string; eyebrow: string; title: Title; head: [string, string]; rows: [string, string][]; note?: string; cta?: { label: string; href: string } }
  | { kind: "doors"; id?: string; eyebrow: string; title: Title; lead?: string; doors: { to: WorldId; eyebrow: string; title: string; still: string }[]; also?: { label: string; href: string }[] }
  | { kind: "plans"; id?: string; eyebrow: string; title: Title; link?: { label: string; href: string } }
  | { kind: "lead-install"; id?: string }
  | { kind: "phone"; id?: string; eyebrow: string; title: Title; lead: string; ticks: string[] }
  | { kind: "callout"; id?: string; eyebrow: string; big?: string; title: string; note: string; dots?: boolean }
  | { kind: "controls"; id?: string; num?: string; eyebrow: string; title: Title; items: Item[] };

export type World = {
  id: WorldId;
  path: string;
  /** Short name used in the chip and the morph line. */
  name: string;
  /** "Changing this site for …" */
  audience: string;
  theme: "dark" | "light";
  meta: { title: string; description: string };
  nav: { label: string; href: string }[];
  cta: { label: string; href: string };
  hero: {
    layout: "bleed" | "stack" | "split";
    eyebrow: string;
    title: Title;
    /** Sub-line when the world has no roles (the default world). */
    sub?: string;
    primary?: { label: string; href: string };
    secondary?: { label: string; href: string };
    roles?: Role[];
    still?: string;
    scene?: SceneId;
    tone?: "dark" | "light";
    langSwitch?: boolean;
    selector?: boolean;
  };
  film: Film;
  sections: Section[];
  /**
   * Reviewed Hindi for the showcase (WebsitePlan.md §3.5). Only these blocks change when the visitor
   * picks Hindi; everything else stays in English. A headline is written "plain|gold" or "plain|gold|plain".
   */
  hi?: Hindi;
};

export type Hindi = {
  title: string;
  /** The hero sub-line. In a world with roles it belongs to the first role. */
  sub?: string;
  /** The main button (nav and hero). */
  cta?: string;
  secondary?: string;
  /** Chapter id -> headline. */
  chapters?: Record<string, string>;
  /** Section id -> headline and list items by position. */
  sections?: Record<string, { title?: string; items?: Record<number, string> }>;
};
