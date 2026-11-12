// Pictures for the pages.
//
// ART: a picture is described once, as a moment in a film, and drawn in the material of whichever
// world is on screen: painted (default), in characters (SaaS), as a line drawing (Enterprise), or
// as a photograph from the Education film. So a content page never shows one world's picture in
// another world's colours. Drawn by components/world/WorldArt.tsx.
//
// MEDIA: photographs from the Education film (1280 x 720 WebP frames in /public/film/education),
// used by the Education world's own sections.

const frame = (n: number) => `/film/education/720/f${String(n).padStart(5, "0")}.webp`;

/** A photograph and where its subject sits (object-position x, as a percentage). */
export type Media = { src: string; focus?: number; alt: string };

export const MEDIA = {
  night: { src: frame(5), focus: 70, alt: "A student at a desk at night, lit by a lamp and a phone" },
  asks: { src: frame(55), focus: 72, alt: "The student asks a question out loud, holding the phone up" },
  compare: { src: frame(180), focus: 62, alt: "A phone showing programmes side by side, in the student's hand" },
  scholarship: { src: frame(205), focus: 62, alt: "The student moves a slider on the phone to see a scholarship" },
  confirm: { src: frame(330), focus: 62, alt: "A tick on the phone screen: the application-fee link is sent" },
  family: { src: frame(380), focus: 52, alt: "The student shows his mother the summary on her phone" },
  counsellor: { src: frame(455), focus: 40, alt: "A counsellor at her desk in the morning, reading a lead on her laptop" },
  calendar: { src: frame(505), focus: 76, alt: "A calendar on a sunlit wall, one month ringed in gold" },
} satisfies Record<string, Media>;

export type MediaKey = keyof typeof MEDIA;

/**
 * One picture in four materials: the moment (progress, 0 to 1) in the painted film, the character
 * film and the line film at which it is complete, and the Education photograph that says the same.
 */
export type Art = { alt: string; wash: number; ascii: number; line: number; photo: MediaKey };

export const ART = {
  waiting: { alt: "A website as seven panels, waiting to be read", wash: 0.03, ascii: 0.12, line: 0.03, photo: "night" },
  stream: { alt: "A visitor on the way to the website", wash: 0.1, ascii: 0.12, line: 0.147, photo: "night" },
  arrives: { alt: "A visitor arrives at one panel of the website with a question", wash: 0.112, ascii: 0.255, line: 0.147, photo: "asks" },
  talks: { alt: "The website answers, and the two pages the answer came from are marked", wash: 0.243, ascii: 0.255, line: 0.25, photo: "asks" },
  sources: { alt: "An answer with the pages it came from marked in gold", wash: 0.243, ascii: 0.6, line: 0.664, photo: "compare" },
  shows: { alt: "A chart and a table drawn on the page while it answers", wash: 0.378, ascii: 0.375, line: 0.457, photo: "scholarship" },
  there: { alt: "The right page, with the sentence that answers ringed in gold", wash: 0.522, ascii: 0.6, line: 0.767, photo: "compare" },
  rings: { alt: "One sentence on a page ringed in gold", wash: 0.522, ascii: 0.6, line: 0.56, photo: "confirm" },
  books: { alt: "A meeting confirmed with a tick, and a lead sent to the team", wash: 0.626, ascii: 0.71, line: 0.87, photo: "confirm" },
  compose: { alt: "A page arranged for one kind of visitor", wash: 0.686, ascii: 0.495, line: 0.56, photo: "family" },
  warm: { alt: "A page arranged for one kind of visitor", wash: 0.686, ascii: 0.81, line: 0.457, photo: "family" },
  rearranged: { alt: "The same page arranged differently for another visitor", wash: 0.772, ascii: 0.495, line: 0.56, photo: "family" },
  three: { alt: "Three versions of one website, side by side", wash: 0.866, ascii: 0.9, line: 0.354, photo: "counsellor" },
  stacks: { alt: "Three versions of one website, side by side", wash: 0.866, ascii: 0.9, line: 0.25, photo: "counsellor" },
  ten: { alt: "Ten visitors in a row; one is held back", wash: 0.94, ascii: 0.985, line: 0.974, photo: "calendar" },
  measure: { alt: "Two lines of a chart parting: the difference is the result", wash: 1, ascii: 0.985, line: 0.974, photo: "calendar" },
} satisfies Record<string, Art>;

export type ArtKey = keyof typeof ART;
