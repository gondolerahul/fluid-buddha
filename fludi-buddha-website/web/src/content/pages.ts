// Content for the template pages (product, solutions, industries, developers, trust, company).
// Copy rules: "answers only from your website, with sources"; English and Hindi only; every ROI
// figure is an example until it comes from a customer's own holdout; no customers are claimed.
// Pages folded into a world redirect there (next.config.ts): /industries/saas, /industries/education,
// /enterprise and /customers. Audit: docs/marketing-docs/website/audit-2026-11-11.md §2.3 and §4.

import type { ArtKey } from "./media";

export type Cta = { label: string; href: string };
export type Item = { title: string; body: string; tag?: string };
export type Section =
  | { kind: "story"; title: string; body: string; bullets?: string[]; ask?: string; media?: ArtKey; note?: string }
  | { kind: "grid"; title: string; lead?: string; items: Item[]; cols?: 2 | 3 | 4 }
  | { kind: "steps"; title: string; items: Item[] }
  | { kind: "prose"; id?: string; title: string; paragraphs: string[] }
  | { kind: "faq"; title: string; items: { q: string; a: string }[] };

export type Page = {
  path: string;
  title: string;
  description: string;
  media: ArtKey;
  headline: [string, string]; // the second half is the emphasised phrase
  sub: string;
  primary: Cta;
  secondary?: Cta;
  /** A question the hero offers to ask the site's own agent. */
  ask?: string;
  sections: Section[];
  closing: { title: [string, string]; body?: string; primary: Cta; secondary?: Cta };
};

const START: Cta = { label: "Start free", href: "/demo#start" };
const DEMO: Cta = { label: "Book a demo", href: "/book-demo" };
const TRY: Cta = { label: "Try the live demo", href: "/demo" };

export const PAGES: Page[] = [
  // ------------------------------------------------------------------ Product
  {
    path: "product", title: "How it works", media: "sources",
    description: "FluidBuddha turns your website into a voice-first agent that talks, shows and acts, using only your content.",
    headline: ["Everything your best salesperson does,", "on every visit."],
    sub: "It answers out loud from your own pages, draws what it explains, takes visitors to the right page and books the next step.",
    primary: TRY, secondary: START, ask: "How does it work?",
    sections: [
      { kind: "story", title: "It answers out loud, in under a second.", media: "talks", ask: "Can I ask in Hindi?",
        body: "A short spoken acknowledgement starts in under a second while the full answer is prepared. Visitors can interrupt at any time. It speaks English and Hindi, and understands Hinglish.",
        bullets: ["Voice or text, on any device", "Interrupt it mid-sentence, like a person", "Hindi answers from English pages"] },
      { kind: "story", title: "It draws what it explains.", media: "shows", ask: "Compare your plans",
        body: "Comparison tables, charts, flowcharts, calculators and timelines appear while it talks, and update when a visitor changes a number. They are built from 13 safe, typed components, never free-form code.",
        bullets: ["Live reactions when a visitor moves a slider", "Rupee amounts with Indian digit grouping", "Your own components, if you add them"] },
      { kind: "story", title: "The website moves with the conversation.", media: "there",
        body: "It opens the right page, scrolls to the right section and highlights it. It can adapt the page for the kind of visitor and give a narrated guided tour.",
        bullets: ["Never sends visitors to a missing page", "Adapts to the visitor's segment, language and page", "Narrated tours you can edit"] },
      { kind: "story", title: "It answers only from your website.", media: "arrives", ask: "Where do the answers come from?",
        body: "Every factual answer comes from your pages, files and price lists, with a link to the source. When something is not covered, it says so and offers your team. You can pin approved answers and block topics.",
        bullets: ["A source on every grounded answer", "Pinned and blocked answers", "A safety mode for healthcare"] },
      { kind: "story", title: "Conversations become customers.", media: "books", ask: "Book a demo",
        body: "It captures and scores leads, sends quotes, starts trials, books meetings and shares payment links, each only after the visitor says yes. Recap pages can be forwarded, and your team can take over live, even with a browser voice call.",
        bullets: ["Nothing runs until the visitor confirms", "Hot leads to Slack and your CRM", "Live takeover and voice handoff"] },
      { kind: "grid", title: "Four more things it does.", cols: 2, items: [
        { title: "It knows when to speak", body: "Openers written for each page, triggered by time, scroll depth, exit intent or a return visit, and capped so they never nag." },
        { title: "It remembers, if invited", body: "Visitors who opt in pick up where they left off. “Forget me” deletes it." },
        { title: "It proves its value", body: "A built-in holdout group, A/B tests, insights on what visitors ask, and a Monday digest." },
        { title: "It gets cheaper as it learns", body: "Repeat questions replay from memory at almost no model cost. Spend caps and alerts for each site." },
      ] },
    ],
    closing: { title: ["See it work on", "this website."], primary: TRY, secondary: { label: "Three ways it appears", href: "/product/design" } },
  },
  {
    path: "product/design", title: "Three ways it appears", media: "three",
    description: "The Companion, the Presence and the Atmosphere: three ways FluidBuddha can appear on your website, from one script.",
    headline: ["Choose how present it is,", "from one line of code."],
    sub: "Switch between the three at any time from your dashboard, and test them against each other.",
    primary: TRY, secondary: DEMO,
    sections: [
      { kind: "grid", title: "From quiet to immersive.", cols: 3, items: [
        { title: "The Companion", tag: "The default", body: "A breathing light in the corner opens a glass panel with the conversation, suggestions and a microphone. Full screen on phones. The light in the corner of this site works the same way." },
        { title: "The Presence", tag: "Immersive", body: "A full-screen field of light that reacts to the voice, with a central surface for visuals. Made for launches and showrooms." },
        { title: "The Atmosphere", tag: "No widget", body: "The page itself glows, highlights sections and shows captions. Visitors summon it with ⌘K or a small light." },
      ] },
      { kind: "prose", title: "The same states, everywhere.", paragraphs: [
        "All three share one language of light: resting, listening, thinking and speaking. All three respect reduced motion, high contrast, focus rings and the safe areas of phones.",
      ] },
    ],
    closing: { title: ["Find the one that", "fits your brand."], primary: DEMO, secondary: TRY },
  },

  // ------------------------------------------------------------------ Solutions
  {
    path: "solutions/sales", title: "For sales teams", media: "books",
    description: "Turn website visitors into qualified pipeline: answers at 11 pm, live takeover, quotes, trials and recap pages.",
    headline: ["Turn tonight's visitors into", "tomorrow's pipeline."],
    sub: "Your website answers the technical questions, prices the deal, books the meeting and hands your team a scored lead, at any hour.",
    primary: DEMO, secondary: { label: "Results and ROI", href: "/results" },
    sections: [
      { kind: "story", title: "The demo, given by your website.", media: "shows",
        body: "A technical buyer asks about your integration, the price for 60 seats and where data is kept. Your website answers out loud, draws the integration, builds the configurator and hands over a scored lead.",
        bullets: ["Answers with sources from your own pages", "A configurator priced for their seats", "A scored lead in your CRM and Slack"] },
      { kind: "story", title: "See who is on the site now, and join them.", media: "arrives",
        body: "Your team sees live visitors and each conversation as it happens. Take over with one click, reply, and hand back. Start a voice call in the browser, with no phone number needed." },
      { kind: "story", title: "“Haan” is enough.", media: "rings",
        body: "The visitor confirms on a card or says yes out loud, and receives a payment link with the price from your price list, never from the model." },
      { kind: "grid", title: "The rest of the sales desk.", cols: 3, items: [
        { title: "The committee recap", body: "A forwardable page with every answer and chart. You see how many people opened it." },
        { title: "ROI, built on the spot", body: "A calculator for the visitor's own numbers, with a comment each time they move a slider." },
        { title: "Quotes and trials", body: "PDF quotes and trial accounts, confirmed by the buyer and sent to your team." },
      ] },
    ],
    closing: { title: ["One extra deal a quarter", "can pay for a year."], body: "An example, not a result. Measure your own lift with the built-in holdout test.", primary: DEMO, secondary: TRY },
  },
  {
    path: "solutions/marketing", title: "For marketing teams", media: "measure",
    description: "Generated landing pages, openers that test themselves, measured lift and a Monday digest of what visitors ask.",
    headline: ["Every campaign,", "a page that talks back."],
    sub: "Lift conversion on the pages you already pay to fill, and show the lift with statistics that hold up when you check them every day.",
    primary: DEMO, secondary: { label: "Results and ROI", href: "/results" },
    sections: [
      { kind: "story", title: "A landing page for every account and search term.", media: "stacks",
        body: "Pages composed from your own content and approved components, with numbers and quotes checked against your sources, and fitted to the link that brought the visitor." },
      { kind: "story", title: "It knows when to speak.", media: "arrives",
        body: "Openers written for each page, tested against each other with statistics that resist false wins, and made the default in one click." },
      { kind: "story", title: "Show the lift to your CFO.", media: "ten",
        body: "A share of visitors never meets it. The difference on your own goal is your lift, with an interval that stays valid however often you check." },
      { kind: "story", title: "What your visitors asked, every Monday.", media: "sources",
        body: "Top questions, objections, competitors mentioned and the questions your website could not answer, delivered by email. Close a gap in one click." },
    ],
    closing: { title: ["Answer the questions", "your campaigns bring in."], primary: DEMO, secondary: TRY },
  },

  // ------------------------------------------------------------------ Industries
  {
    path: "industries/retail-services", title: "Retail, D2C and services", media: "talks",
    description: "Hindi and Hinglish voice answers from English content, and payment links confirmed by a spoken “haan”.",
    headline: ["Your customers ask in Hinglish.", "Your website answers in Hindi."],
    sub: "No translation project. It answers in Hindi from your English website, and closes the sale when the customer says “haan”.",
    primary: START, secondary: TRY, ask: "Does it speak Hindi?",
    sections: [
      { kind: "story", title: "It answers in Hindi from your English pages.", media: "sources",
        body: "It detects Hindi and Hinglish, searches your English content and answers in Hindi, by voice or text." },
      { kind: "story", title: "“Haan” closes the sale.", media: "books",
        body: "Payment links on your own Razorpay account, with prices from your price list. UPI Autopay is handled. Nothing runs until the customer confirms." },
      { kind: "story", title: "Questions after closing time still get answers.", media: "waiting",
        body: "People browse in the evening and at weekends. Your website keeps answering, and the leads are waiting in the morning." },
    ],
    closing: { title: ["Start free and answer", "tonight's questions."], primary: START, secondary: { label: "See it in Hindi", href: "/?lang=hi" } },
  },
  {
    path: "industries/healthcare", title: "Clinics and hospitals", media: "warm",
    description: "A voice front desk that books appointments in English or Hindi and never gives medical advice.",
    headline: ["A front desk that books appointments", "and never gives medical advice."],
    sub: "Timings, treatments, prices and bookings, in English or Hindi. Requests for diagnosis or dosage get a polite refusal and an offer to book.",
    primary: DEMO, secondary: { label: "Trust and security", href: "/trust" },
    sections: [
      { kind: "story", title: "It cannot be talked into medical advice.", media: "there",
        body: "Requests for diagnosis, treatment or dosage get a fixed, polite refusal with an offer to book. Emergencies get emergency numbers. This check runs before any AI model is called, in English, Hindi and Hinglish." },
      { kind: "story", title: "Appointments, day and night.", media: "rings",
        body: "Opening hours, doctors, treatments and prices from your own pages, and a booking link confirmed by the patient." },
      { kind: "story", title: "Personal details stay hidden.", media: "waiting",
        body: "Emails, phone numbers and card numbers are hidden before any model or log sees them. You set how long conversations are kept, and can delete a person's data on request." },
    ],
    closing: { title: ["A calmer front desk,", "every hour of the day."], primary: DEMO },
  },
  {
    path: "industries/real-estate", title: "Real estate", media: "rearranged",
    description: "Returning-visitor memory, EMI calculators with live comments, and site visits booked from the conversation.",
    headline: ["Buyers take months.", "Your website remembers."],
    sub: "Buyers who opt in are welcomed back with what they explored last time. Floor plans, prices and EMIs, explained out loud.",
    primary: DEMO, secondary: TRY,
    sections: [
      { kind: "story", title: "“Welcome back. Last time you asked about the 3 BHK.”", media: "sources",
        body: "Opt-in memory picks up where the buyer left off. “Forget me” deletes it. It is off by default." },
      { kind: "story", title: "An EMI calculator that talks.", media: "shows",
        body: "Built for the buyer's own numbers, with a comment each time they move a slider." },
      { kind: "story", title: "Site visits, booked and shared.", media: "books",
        body: "A visit booked in the conversation, and a recap the buyer forwards to family." },
    ],
    closing: { title: ["Keep every buyer", "warm for months."], primary: DEMO },
  },
  {
    path: "industries/agencies", title: "Agencies and multi-brand groups", media: "stacks",
    description: "Turn a client's website into a talking one in an afternoon: crawl, personas, brand and tour from a URL.",
    headline: ["A client's website, talking,", "by this afternoon."],
    sub: "From a URL to a working agent: it reads the site, finds the audiences, picks up the brand and plans a tour. One account for every client.",
    primary: { label: "Become a partner", href: "/contact" }, secondary: { label: "Try it on a client's site", href: "/demo#your-site" },
    sections: [
      { kind: "steps", title: "From a URL to an agent.", items: [
        { title: "Paste the client's URL", body: "It reads the site, respecting robots.txt." },
        { title: "Review what it learned", body: "Audiences, brand colours, a tour and starter questions." },
        { title: "Add one line of code", body: "WordPress, Shopify, Webflow, Framer or any site." },
      ] },
      { kind: "grid", title: "Built for many clients.", cols: 3, items: [
        { title: "Industry templates", body: "SaaS, education, real estate and healthcare, set up in one click." },
        { title: "Campaign pages", body: "Landing pages for each account and search term, from the client's content." },
        { title: "Teams and roles", body: "Owners, admins, editors and viewers, for each client account." },
      ] },
    ],
    closing: { title: ["Add a talking website", "to every proposal."], primary: { label: "Become a partner", href: "/contact" } },
  },

  // ------------------------------------------------------------------ Developers, results
  {
    path: "developers", title: "For developers and AI assistants", media: "arrives",
    description: "MCP server, llms.txt, an OpenAPI ask endpoint, React and Vue components, hooks, events and signed webhooks.",
    headline: ["Your website, as a service", "other AI assistants can ask."],
    sub: "Expose your grounded answers to other assistants, compose pages for each question, and wire every action into your stack.",
    primary: { label: "See the install code", href: "#install" }, secondary: TRY, ask: "How do I install it?",
    sections: [
      { kind: "grid", title: "Open to other agents.", cols: 2, items: [
        { title: "Agent endpoint", body: "An MCP server, llms.txt and an OpenAPI “ask” endpoint, with scoped tokens for leads and actions." },
        { title: "Pages for each question", body: "The top tier composes whole pages from typed sections, your brand tokens and your site's APIs." },
        { title: "SDK and installs", body: "A script tag, @fluidbuddha/react and @fluidbuddha/vue, onNavigate, onScrollTo and onSetPersona hooks, and cancelable events." },
        { title: "Webhooks", body: "HMAC-SHA256 signed webhooks to your CRM, Zapier or Make, plus Slack alerts for hot leads." },
      ] },
      { kind: "prose", id: "install", title: "One line to install.", paragraphs: [
        "<script src=\"https://<server>/widget/loader.js\" data-key=\"fbk_…\" async></script>",
        "The core script is about 38.6 kB gzipped and runs in its own isolated container (Shadow DOM), so it cannot change your styles. Everything else (tier, design, greeting, languages, knowledge, triggers, tests) is set from the console.",
      ] },
    ],
    closing: { title: ["Build with", "a website that answers."], primary: { label: "See the install code", href: "#install" }, secondary: DEMO },
  },
  {
    path: "results", title: "Results and ROI", media: "ten",
    description: "Measure the extra sales FluidBuddha brings with a built-in holdout group and always-valid statistics.",
    headline: ["Measure the extra sales", "on your own traffic."],
    sub: "A share of visitors never meets it. The difference on your own goal is your lift, with statistics that stay valid however often you look.",
    primary: DEMO, secondary: { label: "See pricing", href: "/pricing" },
    sections: [
      { kind: "steps", title: "How to prove it, in six steps.", items: [
        { title: "Pick the goal that means money", body: "A thank-you page, a booking page, or a conversion call." },
        { title: "Run the holdout", body: "By default one visitor in ten never sees it. The planner says how long to run." },
        { title: "Read the lift", body: "With its interval, valid however often you check." },
        { title: "Add what the holdout cannot see", body: "Scored leads, paid actions, forwarded recaps, live calls." },
        { title: "Subtract the cost", body: "The plan price plus AI spend; replayed answers cost almost nothing." },
        { title: "Send it to leadership", body: "Every Monday, in the digest." },
      ] },
      { kind: "grid", title: "What a conversation costs.", cols: 3, items: [
        { title: "About ₹16.50", tag: "Growth", body: "For each conversation (₹33,000 for 2,000), then ₹17 each." },
        { title: "About ₹12.50", tag: "Scale", body: "For each conversation (₹1,25,000 for 10,000), then ₹10 each." },
        { title: "Compare it", tag: "Your numbers", body: "With one paid click on a competitive keyword, or one hour of a sales engineer." },
      ] },
    ],
    closing: { title: ["Start measuring", "on your first day."], body: "Every ROI figure on this site is an example until it comes from your own holdout.", primary: DEMO },
  },

  // ------------------------------------------------------------------ Integrations, trust, company
  {
    path: "integrations", title: "Integrations", media: "stream",
    description: "Install on WordPress, Shopify, Webflow, Framer, Google Tag Manager, React or Vue, and connect Slack, CRMs, Razorpay and calendars.",
    headline: ["One line of code", "on any website."],
    sub: "Install it once. Everything else is set from your dashboard, so the site never needs editing again.",
    primary: START, secondary: { label: "For developers", href: "/developers" },
    sections: [
      { kind: "grid", title: "Where it installs.", cols: 3, items: [
        { title: "WordPress", body: "A plugin: paste the install code in its settings." },
        { title: "Shopify", body: "A theme app embed with position and page controls." },
        { title: "Webflow and Framer", body: "A guide, plus a Framer code component." },
        { title: "Google Tag Manager", body: "A ready template, or a custom HTML tag." },
        { title: "React and Vue", body: "@fluidbuddha/react and @fluidbuddha/vue, with navigation hooks." },
        { title: "Any website", body: "One script tag, or FluidBuddha.init({...})." },
      ] },
      { kind: "grid", title: "What it connects to.", cols: 2, items: [
        { title: "Slack", body: "Hot-lead alerts and cost alerts." },
        { title: "CRMs, Zapier and Make", body: "Signed webhooks for every lead." },
        { title: "Razorpay", body: "Payment links on your own account." },
        { title: "Calendly and Cal.com", body: "Meetings booked, with the details filled in." },
      ] },
    ],
    closing: { title: ["Install it this afternoon", "and answer tonight."], primary: START },
  },
  {
    path: "trust", title: "Trust and security", media: "waiting",
    description: "Answers only from your content, personal details hidden, consent, retention and erasure, and the security documents we can share.",
    headline: ["What happens to your content,", "your visitors and their data."],
    sub: "How FluidBuddha handles your content, your visitors' details and your security review.",
    primary: { label: "Ask for the security documents", href: "/contact" }, secondary: { label: "For banks and insurers", href: "/for/enterprise" }, ask: "Is my data safe?",
    sections: [
      { kind: "grid", title: "What we commit to.", cols: 2, items: [
        { title: "Answers only from your content", body: "Grounded answers carry their sources. Below a confidence threshold it says it does not know and offers your team." },
        { title: "Personal details hidden", body: "Emails, phone numbers, card numbers, SSNs and IBANs are replaced before any model, history or storage sees them. Names and street addresses are not detected." },
        { title: "Consent and retention", body: "Microphone consent is recorded. Transcripts are kept 90 days by default, recap links expire, and an hourly sweep enforces it. Erasure by email." },
        { title: "Healthcare safety mode", body: "Diagnosis, treatment and dosage requests get a fixed refusal before any model is called." },
        { title: "Where data is processed", body: "With your own model, speech and search indexing still run on Google Vertex AI." },
        { title: "Documents we can share", body: "A draft control matrix and policies, a sub-processor list, a data processing agreement template, the audit log and access reviews. No certification is held yet." },
      ] },
    ],
    closing: { title: ["Questions from", "your security team?"], primary: { label: "Ask for the security documents", href: "/contact" }, secondary: { label: "For banks and insurers", href: "/for/enterprise" } },
  },
  {
    path: "about", title: "About", media: "three",
    description: "FluidBuddha is a Buddha Cognitive Lab product. Towards digital enlightenment.",
    headline: ["A Buddha Cognitive Lab product.", "Towards digital enlightenment."],
    sub: "We research intelligence that does real work in the real world. FluidBuddha is our second product, after Hire Buddha.",
    primary: { label: "Contact us", href: "/contact" }, secondary: TRY,
    sections: [
      { kind: "prose", title: "Why we built it.", paragraphs: [
        "Most websites are frozen. When a visitor has a question at 9:40 pm, nothing answers, and they leave. We wanted every website to listen, answer from what it already says, and turn that attention into customers.",
      ] },
      { kind: "prose", title: "We use it ourselves first.", paragraphs: [
        "We are putting FluidBuddha on our own websites before we ask you to put it on yours: buddhalab.in, hirebuddha.in and chantingbuddha.in. Each one will be listed here, with a link, once the agent is live on it. Until then, this site is the demonstration.",
      ] },
    ],
    closing: { title: ["Say hello", "to the team."], primary: { label: "Contact us", href: "/contact" } },
  },
  {
    path: "contact", title: "Contact", media: "talks",
    description: "Contact the FluidBuddha team.",
    headline: ["Talk to", "a person."],
    sub: "Or ask this website first. It answers from these pages, and hands over to us when it should.",
    primary: DEMO, ask: "I want to talk to the team",
    sections: [
      { kind: "grid", title: "How to reach us.", cols: 3, items: [
        { title: "Sales", body: "Book a demo, and the agent finds a slot in the conversation." },
        { title: "Partners and agencies", body: "Ask about the partner programme." },
        { title: "Security reviews", body: "Ask for the security documents and the data processing agreement." },
      ] },
    ],
    closing: { title: ["Or just ask", "the website."], primary: TRY },
  },
  {
    path: "book-demo", title: "Book a demo", media: "books",
    description: "Book a demo with the FluidBuddha team. The website books it in the conversation.",
    headline: ["Ask the website", "to book it."],
    sub: "Ask Pragya, the light in the corner, to book a demo. It finds a slot, asks you to confirm, and sends the invite. During staffed hours, a person can join live.",
    primary: TRY, secondary: START, ask: "Book a demo",
    sections: [
      { kind: "steps", title: "What happens next.", items: [
        { title: "Ask", body: "“Book a demo for Thursday morning.”" },
        { title: "Confirm", body: "Nothing is booked until you say yes." },
        { title: "Meet", body: "A 20-minute walkthrough on your own website's questions." },
      ] },
    ],
    closing: { title: ["Prefer to start", "on your own?"], primary: START },
  },
];

// Legal pages: placeholders until the legal team supplies the final text.
export const LEGAL: Record<string, { title: string }> = {
  privacy: { title: "Privacy policy" },
  terms: { title: "Terms of service" },
  dpa: { title: "Data processing agreement" },
  subprocessors: { title: "Sub-processors" },
  cookies: { title: "Cookie policy" },
};

export function getPage(path: string) {
  return PAGES.find((p) => p.path === path);
}
