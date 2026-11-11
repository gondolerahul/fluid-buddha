// Pictures for the pages, taken from the two rendered films (1280 x 720 WebP frames in /public/film).
// They replace the old film's posters, which were deleted with that film on 10 November 2026.

const frame = (film: "default" | "education", n: number) => `/film/${film}/720/f${String(n).padStart(5, "0")}.webp`;

/** A picture and where its subject sits (object-position x, as a percentage). */
export type Media = { src: string; focus?: number; alt: string };

export const MEDIA = {
  // default film: the website as amber glass panels over black water
  waiting: { src: frame("default", 10), focus: 66, alt: "A website drawn as glass panels, waiting in the dark" },
  stream: { src: frame("default", 40), focus: 66, alt: "A thread of gold light running beneath the glass panels" },
  arrives: { src: frame("default", 100), focus: 62, alt: "A stream of gold dots arriving at one panel of the website" },
  talks: { src: frame("default", 160), focus: 64, alt: "A voice wave of gold light running through the website's panels" },
  sources: { src: frame("default", 190), focus: 60, alt: "An answer glowing on one panel, with lines back to the panels it came from" },
  shows: { src: frame("default", 250), focus: 58, alt: "A gold bar chart and a table rising out of a panel" },
  there: { src: frame("default", 340), focus: 76, alt: "A ring of light marking one section of the website" },
  books: { src: frame("default", 400), focus: 40, alt: "A small card with a confirmation ring leaving the website" },
  rings: { src: frame("default", 370), focus: 60, alt: "Two rings of light over the lower panels of the website" },
  compose: { src: frame("default", 460), focus: 50, alt: "Gold dots gathering into the panels of a new page" },
  warm: { src: frame("default", 520), focus: 62, alt: "The website's panels lit warm from within" },
  rearranged: { src: frame("default", 550), focus: 50, alt: "The panels rearranged into a new layout, lit gold" },
  three: { src: frame("default", 580), focus: 56, alt: "Three glass slabs of light, three versions of one page" },
  stacks: { src: frame("default", 610), focus: 60, alt: "Three stacks of panels standing in warm light" },
  ten: { src: frame("default", 670), focus: 58, alt: "Ten points of light in a row; one is dimmed" },
  measure: { src: frame("default", 698), focus: 58, alt: "Two lines of light separating over a row of ten lights" },

  // education film: a student at night, the family, the counsellor in the morning
  night: { src: frame("education", 5), focus: 70, alt: "A student at a desk at night, lit by a lamp and a phone" },
  asks: { src: frame("education", 55), focus: 72, alt: "The student asks a question out loud, holding the phone up" },
  compare: { src: frame("education", 180), focus: 62, alt: "A phone showing programmes side by side, in the student's hand" },
  scholarship: { src: frame("education", 205), focus: 62, alt: "The student moves a slider on the phone to see a scholarship" },
  confirm: { src: frame("education", 330), focus: 62, alt: "A tick on the phone screen: the application-fee link is sent" },
  family: { src: frame("education", 380), focus: 52, alt: "The student shows his mother the summary on her phone" },
  counsellor: { src: frame("education", 455), focus: 40, alt: "A counsellor at her desk in the morning, reading a lead on her laptop" },
  calendar: { src: frame("education", 505), focus: 76, alt: "A calendar on a sunlit wall, one month ringed in gold" },
} satisfies Record<string, Media>;

export type MediaKey = keyof typeof MEDIA;
