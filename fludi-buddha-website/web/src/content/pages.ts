// Content for every template page in the sitemap (docs/marketing-docs/WebsiteConcept.md §7).
// Copy rules (§11): "answers only from your website, with sources"; English and Hindi only;
// ROI figures are illustrative unless they are real, consented results.

export type Cta = { label: string; href: string };
export type Item = { title: string; body: string; tag?: string };
export type Section =
  | { kind: "story"; eyebrow?: string; title: string; body: string; bullets?: string[]; tag?: string; poster?: string; note?: string }
  | { kind: "grid"; eyebrow?: string; title: string; lead?: string; items: Item[]; cols?: 2 | 3 | 4 }
  | { kind: "steps"; eyebrow?: string; title: string; items: Item[] }
  | { kind: "prose"; eyebrow?: string; title: string; paragraphs: string[] }
  | { kind: "faq"; eyebrow?: string; title: string; items: { q: string; a: string }[] };

export type Page = {
  path: string;
  title: string;
  description: string;
  theme?: "paper" | "ink";
  poster: string; // keyframe still used as the hero visual until the page's own hero film is made
  eyebrow: string;
  headline: [string, string]; // second half renders in gold
  sub: string;
  primary: Cta;
  secondary?: Cta;
  sections: Section[];
  closing: { title: [string, string]; body?: string; primary: Cta; secondary?: Cta };
};

const START: Cta = { label: "Start free", href: "/demo#start" };
const DEMO: Cta = { label: "Book a demo", href: "/book-demo" };
const TRY: Cta = { label: "Try the live demo", href: "/demo" };

export const PAGES: Page[] = [
  // ------------------------------------------------------------------ Product
  {
    path: "product", title: "How it works", poster: "K6",
    description: "FluidBuddha turns your website into a voice-first agent that talks, shows and acts, using only your content.",
    eyebrow: "Product", headline: ["Everything your best salesperson does,", "on every visit."],
    sub: "It listens, answers out loud, draws what it explains, takes visitors to the right page and books the next step. It answers only from your website, with sources.",
    primary: TRY, secondary: START,
    sections: [
      { kind: "story", eyebrow: "It talks", title: "A spoken reply in under a second.", poster: "K1",
        body: "A short acknowledgement starts in under a second while the full answer is prepared. Visitors can interrupt at any time. It speaks English and Hindi, and understands Hinglish.",
        bullets: ["Voice or text, on any device", "Interrupt it mid-sentence, like a person", "Hindi answers from English content"], tag: "Try: “Can I ask in Hindi?”" },
      { kind: "story", eyebrow: "It shows", title: "It draws what it explains.", poster: "K6",
        body: "Comparison tables, charts, flowcharts, calculators and timelines appear while it talks, and update when a visitor changes a number. They are built from safe, typed components, never free-form code.",
        bullets: ["13 kinds of visual", "Live reactions when a visitor moves a slider", "Rupee amounts with Indian digit grouping"], tag: "Try: “Compare your plans.”" },
      { kind: "story", eyebrow: "It takes them there", title: "The website moves with the conversation.", poster: "K7",
        body: "It navigates to the right page, scrolls to the right section and highlights it. It can adapt the page for the visitor's role and give a narrated guided tour.",
        bullets: ["Never sends visitors to a missing page", "Adapts to role, language and page", "Narrated tours you can edit"], tag: "Try: “Give me a tour.”" },
      { kind: "story", eyebrow: "Only from your website", title: "It can't shine with what isn't there.", poster: "K10",
        body: "Every factual answer comes from your pages, files and price lists, with a link to the source. When something isn't covered, it says so and offers your team. You can pin approved answers and block topics.",
        bullets: ["Sources on every grounded answer", "Pinned and blocked answers", "Safety mode for healthcare"] },
      { kind: "story", eyebrow: "Revenue", title: "Conversations become customers.", poster: "K8",
        body: "It captures and scores leads, sends quotes, starts trials, books meetings and shares payment links, but only after the visitor says yes. Recap pages can be forwarded, and your team can take over live, even with a browser voice call.",
        bullets: ["Nothing runs until the visitor confirms", "Hot leads to Slack and your CRM", "Live takeover and voice handoff"] },
      { kind: "grid", eyebrow: "And more", title: "Built to earn its place.", cols: 2, items: [
        { title: "It knows when to speak", body: "Openers written for each page, triggered by time, scroll depth, exit intent or a return visit, and capped so they never nag." },
        { title: "It remembers, if invited", body: "Visitors who opt in pick up where they left off. “Forget me” deletes it." },
        { title: "It proves its value", body: "A built-in control group, A/B tests, insights on what visitors ask, and a Monday digest." },
        { title: "It gets cheaper as it learns", body: "Repeat questions replay from memory at almost no model cost. Spend caps and alerts per site." },
      ] },
    ],
    closing: { title: ["See it work on", "this website."], primary: TRY, secondary: { label: "Three ways it appears", href: "/product/design" } },
  },
  {
    path: "product/design", title: "Three ways it appears", poster: "K9", theme: "ink",
    description: "The Companion, the Presence and the Atmosphere: three ways FluidBuddha can appear on your website, from one script.",
    eyebrow: "Design levels", headline: ["Three ways to appear.", "One line of code."],
    sub: "Choose how present it should be. Switch at any time from your dashboard, and test them against each other.",
    primary: TRY,
    sections: [
      { kind: "grid", title: "From quiet to immersive.", cols: 3, items: [
        { title: "The Companion", tag: "Default", body: "A breathing light in the corner opens a glass panel with the conversation, suggestions and a microphone. Full screen on mobile." },
        { title: "The Presence", tag: "Immersive", body: "A full-screen field of light that reacts to the voice, with a central surface for visuals. Made for launches and showrooms." },
        { title: "The Atmosphere", tag: "Invisible", body: "No widget at all. The page itself glows, highlights sections and shows captions. Summon it with ⌘K or a small light." },
      ] },
      { kind: "prose", title: "The same states, everywhere.", paragraphs: [
        "All three share one language of light: resting, listening, thinking and speaking. All three respect reduced motion, high contrast, focus rings and safe areas on phones.",
      ] },
    ],
    closing: { title: ["Find the one that", "fits your brand."], primary: DEMO },
  },

  // ------------------------------------------------------------------ Solutions
  {
    path: "solutions/sales", title: "For sales teams", poster: "K8",
    description: "Turn website visitors into qualified pipeline: answers at 11 PM, live takeover, quotes, trials and recap pages.",
    eyebrow: "Solutions · Sales", headline: ["Turn tonight's visitors into", "tomorrow's pipeline."],
    sub: "Your website answers the technical questions, prices the deal, books the meeting and hands your team a qualified lead, at any hour.",
    primary: DEMO, secondary: { label: "Results and ROI", href: "/results" },
    sections: [
      { kind: "story", eyebrow: "The 11 PM demo", title: "The demo, given by your website.", poster: "K6",
        body: "A technical buyer asks about your integration, the price for 60 seats and where data is kept. Your website answers out loud, draws the integration, builds the configurator and hands over a qualified lead.",
        bullets: ["Answers with sources from your own pages", "A configurator priced for their seats", "A scored lead in your CRM and Slack"] },
      { kind: "story", eyebrow: "Live takeover", title: "Spot the hot buyer. Call them in the browser.", poster: "K3",
        body: "Your team sees live visitors and the conversation as it happens. Take over with one click, reply, and hand back. Start a voice call in the browser, with no phone number needed." },
      { kind: "story", eyebrow: "Close in the conversation", title: "“Haan” is enough.", poster: "K8",
        body: "The visitor confirms on a card or says yes out loud, and receives a payment link with the price from your price list, never from the model." },
      { kind: "grid", eyebrow: "More ways it sells", title: "The rest of the sales desk.", cols: 3, items: [
        { title: "The committee recap", body: "A forwardable page with every answer and live chart. You see how far it travels." },
        { title: "ROI, built on the spot", body: "A calculator for the visitor's own numbers, with comments as they move the sliders." },
        { title: "Quotes and trials", body: "PDF quotes and trial accounts, confirmed by the buyer and sent to your team." },
      ] },
    ],
    closing: { title: ["One extra deal a quarter", "usually pays for a year."], body: "Illustrative. Measure your own lift with the built-in control group.", primary: DEMO, secondary: TRY },
  },
  {
    path: "solutions/marketing", title: "For marketing teams", poster: "K14",
    description: "Generated landing pages, openers that test themselves, measured lift and a Monday digest of what visitors ask.",
    eyebrow: "Solutions · Marketing", headline: ["Every campaign,", "a page that talks back."],
    sub: "Lift conversion on every page you already pay to fill, and show the CFO the lift with statistics that hold up.",
    primary: { label: "Start a trial", href: "/book-demo" }, secondary: { label: "Results and ROI", href: "/results" },
    sections: [
      { kind: "story", eyebrow: "Campaign pages", title: "One campaign. A thousand landing pages.", poster: "K13",
        body: "A page for every account, role and search term, composed from your own content, with numbers and quotes checked against your sources. Personalised by the link that brought the visitor." },
      { kind: "story", eyebrow: "Openers", title: "It knows when to speak.", poster: "K2",
        body: "Openers written for each page, tested against each other with statistics that resist false wins, and promoted to default in one click." },
      { kind: "story", eyebrow: "Proof", title: "Show the CFO the lift.", poster: "K14",
        body: "A share of visitors never meets it. The difference on your own goal is your lift, with an interval that stays valid however often you check." },
      { kind: "story", eyebrow: "Insight", title: "What your visitors asked, every Monday.", poster: "K10",
        body: "Top questions, objections, competitors mentioned and the questions your website couldn't answer, delivered by email. Close a gap in one click." },
    ],
    closing: { title: ["Your traffic already has questions.", "Let it convert."], primary: { label: "Start a trial", href: "/book-demo" }, secondary: TRY },
  },

  // ------------------------------------------------------------------ Industries
  {
    path: "industries/saas", title: "SaaS and B2B", poster: "K6", theme: "ink",
    description: "Answer the technical buyer at 11 PM: integrations, pricing for their seats, security, and a booked demo.",
    eyebrow: "Industries · SaaS and B2B", headline: ["The technical buyer, answered", "before they ask for a call."],
    sub: "Integrations drawn as diagrams, prices for their exact seats, your security page highlighted, and a demo booked, all from your own content.",
    primary: DEMO, secondary: TRY,
    sections: [
      { kind: "story", eyebrow: "Integrations", title: "“Does it work with Tally?”", poster: "K6",
        body: "It answers from your integration pages and draws the sync as a flowchart while it speaks, with a link to the source." },
      { kind: "story", eyebrow: "Pricing", title: "“What would 25 users cost?”", poster: "K8",
        body: "A price card from your own price list, and a configurator that updates when they say “actually, 40”." },
      { kind: "story", eyebrow: "Security", title: "Your trust pages, highlighted.", poster: "K7",
        body: "It scrolls to your security section and highlights it. For enterprise buyers, SSO, audit logs and a self-hosted edition are ready." },
      { kind: "grid", title: "The rest of the SaaS playbook.", cols: 3, items: [
        { title: "Live takeover", body: "See the hot account and join the conversation, or call them in the browser." },
        { title: "Committee recaps", body: "A forwardable brief with live charts, and a view count." },
        { title: "Self-serve trials", body: "Trial accounts started from the conversation, confirmed by the buyer." },
      ] },
    ],
    closing: { title: ["Your next demo can start", "without you."], primary: DEMO, secondary: TRY },
  },
  {
    path: "industries/retail-services", title: "Retail, D2C and services", poster: "K3", theme: "ink",
    description: "Hindi and Hinglish voice answers from English content, and payment links confirmed by a spoken “haan”.",
    eyebrow: "Industries · Retail and services", headline: ["Your customers ask in Hinglish.", "Your website answers in Hindi."],
    sub: "No translation project. It answers in Hindi from your English website, and closes the sale when the customer says “haan”.",
    primary: START, secondary: TRY,
    sections: [
      { kind: "story", eyebrow: "Vernacular voice", title: "Hindi answers, English website.", poster: "K3",
        body: "It detects Hindi and Hinglish, searches your English content and answers in Hindi, by voice or text." },
      { kind: "story", eyebrow: "Close the sale", title: "“Haan” closes the sale.", poster: "K8",
        body: "Payment links on your own Razorpay account, with prices from your price list. UPI Autopay handled. Nothing runs until the customer confirms." },
      { kind: "story", eyebrow: "After hours", title: "Most questions arrive after you close.", poster: "K4",
        body: "Evenings and weekends are when people browse. Your website keeps answering, and the leads are waiting in the morning." },
    ],
    closing: { title: ["Start free.", "Answer tonight."], primary: START, secondary: { label: "हिन्दी में देखें", href: "/hi" } },
  },
  {
    path: "industries/healthcare", title: "Clinics and hospitals", poster: "K13",
    description: "A voice front desk that books appointments in English or Hindi and never gives medical advice.",
    eyebrow: "Industries · Healthcare", headline: ["A front desk that books appointments", "and never gives medical advice."],
    sub: "Timings, treatments, prices and bookings, in English or Hindi. Requests for diagnosis or dosage get a polite refusal and an offer to book.",
    primary: DEMO, secondary: { label: "Trust and security", href: "/trust" },
    sections: [
      { kind: "story", eyebrow: "Safety mode", title: "It can't be talked into medical advice.", poster: "K11",
        body: "Requests for diagnosis, treatment or dosage get a fixed, polite refusal with an offer to book. Emergencies get emergency numbers. This check runs before any AI model is called, in English, Hindi and Hinglish." },
      { kind: "story", eyebrow: "Bookings", title: "Appointments, day and night.", poster: "K13",
        body: "Opening hours, doctors, treatments and prices from your own pages, and a booking link confirmed by the patient." },
      { kind: "story", eyebrow: "Privacy", title: "Personal details stay masked.", poster: "K2",
        body: "Emails, phone numbers and card numbers are masked before any model or log sees them. Retention windows and erasure on request." },
    ],
    closing: { title: ["A calmer front desk,", "every hour of the day."], primary: DEMO },
  },
  {
    path: "industries/real-estate", title: "Real estate", poster: "K14",
    description: "Returning-visitor memory, EMI calculators with live comments, and site visits booked from the conversation.",
    eyebrow: "Industries · Real estate", headline: ["Buyers take months.", "Your website remembers."],
    sub: "Buyers who opt in are welcomed back with what they explored last time. Floor plans, prices and EMIs, explained out loud.",
    primary: DEMO, secondary: TRY,
    sections: [
      { kind: "story", eyebrow: "Memory", title: "“Welcome back. Last time you asked about the 3 BHK.”", poster: "K10",
        body: "Opt-in memory picks up where the buyer left off. “Forget me” deletes it. Off by default." },
      { kind: "story", eyebrow: "Numbers", title: "An EMI calculator that talks.", poster: "K14",
        body: "Built for the buyer's own numbers, with a comment each time they move a slider." },
      { kind: "story", eyebrow: "Visits", title: "Site visits, booked and shared.", poster: "K8",
        body: "A visit booked in the conversation, and a recap the buyer forwards to family." },
    ],
    closing: { title: ["Keep every buyer", "warm for months."], primary: DEMO },
  },
  {
    path: "industries/education", title: "Education and admissions", poster: "K3", theme: "ink",
    description: "Programme guidance at midnight, application-fee payment, and a recap students forward to their parents.",
    eyebrow: "Industries · Education", headline: ["An admissions counsellor", "at midnight."],
    sub: "Programme guidance from your prospectus, fees paid when the student confirms, and a recap to share with parents in the morning.",
    primary: START, secondary: TRY,
    sections: [
      { kind: "story", eyebrow: "Guidance", title: "Programmes compared, out loud.", poster: "K6",
        body: "It compares courses, fees, dates and eligibility from your own pages, and shows the comparison while it speaks." },
      { kind: "story", eyebrow: "Applications", title: "Fees paid in the conversation.", poster: "K8",
        body: "An application-fee payment link, confirmed by the student, with the amount from your fee list." },
      { kind: "story", eyebrow: "Parents", title: "A recap for the family.", poster: "K15",
        body: "“Send me this” creates a page with every answer and chart, ready to forward. In English or Hindi." },
    ],
    closing: { title: ["Answer every applicant,", "whenever they ask."], primary: START },
  },
  {
    path: "industries/agencies", title: "Agencies and multi-brand groups", poster: "K13",
    description: "Turn a client's website into a talking one in an afternoon: crawl, personas, brand and tour from a URL.",
    eyebrow: "Industries · Agencies", headline: ["A client's website, talking,", "by this afternoon."],
    sub: "From a URL to a working agent: it reads the site, finds the audiences, picks up the brand and plans a tour. One account for every client.",
    primary: { label: "Become a partner", href: "/contact" }, secondary: { label: "Try it on a client's site", href: "/demo#your-site" },
    sections: [
      { kind: "steps", title: "From URL to agent.", items: [
        { title: "Paste the client's URL", body: "It reads the site, respecting robots.txt." },
        { title: "Review what it learned", body: "Audiences, brand colours, a tour and starter questions." },
        { title: "Add one line of code", body: "WordPress, Shopify, Webflow, Framer or any site." },
      ] },
      { kind: "grid", title: "Built for many clients.", cols: 3, items: [
        { title: "Industry templates", body: "SaaS, education, real estate and healthcare, set up in one click." },
        { title: "Campaign pages", body: "Landing pages per account and search term, from the client's content." },
        { title: "Teams and roles", body: "Owners, admins, editors and viewers, per client account." },
      ] },
    ],
    closing: { title: ["Add a talking website", "to every proposal."], primary: { label: "Become a partner", href: "/contact" } },
  },

  // ------------------------------------------------------------------ Enterprise, developers, results
  {
    path: "enterprise", title: "Enterprise", poster: "K9", theme: "ink",
    description: "Self-hosted edition, your own identity provider and model, audit logs and a SOC 2 control pack.",
    eyebrow: "Enterprise", headline: ["Your agent, on your infrastructure,", "under your rules."],
    sub: "Run the whole product on your own host with an offline licence, sign in with your identity provider, and bring your own model.",
    primary: { label: "Talk to an engineer", href: "/book-demo" }, secondary: { label: "Trust and security", href: "/trust" },
    sections: [
      { kind: "grid", title: "Fits a security review.", cols: 2, items: [
        { title: "Self-hosted edition", body: "A one-host install with backups and point-in-time recovery, and an offline signed licence. Visitor-facing features keep working if the licence lapses." },
        { title: "Your identity provider", body: "OIDC single sign-on for domains you prove, MFA, sessions with idle timeouts, and sign-out everywhere." },
        { title: "Your model", body: "Anthropic, OpenAI or Azure OpenAI on your own contract, with automatic fallback. Speech and embeddings run on Google Vertex AI." },
        { title: "Governance", body: "Roles, access reviews, a one-year audit log, a SOC 2 control pack and policies, a DPA and a sub-processor list." },
      ] },
      { kind: "prose", title: "Reliable by design.", paragraphs: [
        "Readiness checks, graceful voice drain on deploys, multi-replica state, alert rules with a runbook, and a public status page with incident history.",
      ] },
    ],
    closing: { title: ["Bring it inside", "your walls."], primary: { label: "Talk to an engineer", href: "/book-demo" } },
  },
  {
    path: "developers", title: "For developers and AI assistants", poster: "K9", theme: "ink",
    description: "MCP server, llms.txt, an OpenAPI ask endpoint, React and Vue components, hooks, events and signed webhooks.",
    eyebrow: "Developers", headline: ["Your website, as a service", "other AI assistants can ask."],
    sub: "Expose your grounded answers to other assistants, compose pages per question, and wire every action into your stack.",
    primary: { label: "Read the docs", href: "/developers#docs" }, secondary: TRY,
    sections: [
      { kind: "grid", title: "Open to the agent ecosystem.", cols: 2, items: [
        { title: "Agent endpoint", body: "An MCP server, llms.txt and an OpenAPI “ask” endpoint, with scoped tokens for leads and actions." },
        { title: "Pages per question", body: "The top tier composes whole pages from typed sections, your brand tokens and your site's APIs." },
        { title: "SDK and installs", body: "A script tag, @fluidbuddha/react and @fluidbuddha/vue, onNavigate / onScrollTo / onSetPersona hooks, and cancelable events." },
        { title: "Webhooks", body: "HMAC-SHA256 signed webhooks to your CRM, Zapier or Make, plus Slack alerts for hot leads." },
      ] },
      { kind: "prose", eyebrow: "Install", title: "One line.", paragraphs: [
        "<script src=\"https://<server>/widget/loader.js\" data-key=\"fbk_…\" async></script>",
        "Everything else (tier, design, greeting, languages, knowledge, triggers, tests) is set from the console.",
      ] },
    ],
    closing: { title: ["Build with", "a website that answers."], primary: { label: "Read the docs", href: "/developers#docs" } },
  },
  {
    path: "results", title: "Results and ROI", poster: "K14",
    description: "Measure the extra sales FluidBuddha brings with a built-in control group and always-valid statistics.",
    eyebrow: "Results and ROI", headline: ["Measure the extra sales.", "Don't take our word for it."],
    sub: "A share of visitors never meets it. The difference on your own goal is your lift, with statistics that stay valid however often you look.",
    primary: { label: "Start a trial", href: "/book-demo" }, secondary: { label: "See pricing", href: "/pricing" },
    sections: [
      { kind: "steps", title: "How to prove it, in six steps.", items: [
        { title: "Pick the goal that means money", body: "A thank-you page, a booking page, or a conversion call." },
        { title: "Run the holdout", body: "By default 10% of visitors never see it. The planner says how long to run." },
        { title: "Read the lift", body: "With its interval, valid however often you check." },
        { title: "Add what the holdout can't see", body: "Scored leads, paid actions, forwarded recaps, live calls." },
        { title: "Subtract the cost", body: "Plan price plus AI spend; replayed answers cost almost nothing." },
        { title: "Send it to leadership", body: "Every Monday, in the digest." },
      ] },
      { kind: "grid", eyebrow: "Unit economics", title: "What a conversation costs.", cols: 3, items: [
        { title: "≈ ₹16.50", tag: "Growth", body: "Per conversation (₹33,000 ÷ 2,000), then ₹17 each." },
        { title: "≈ ₹12.50", tag: "Scale", body: "Per conversation (₹1,25,000 ÷ 10,000), then ₹10 each." },
        { title: "Compare", tag: "Your numbers", body: "One paid click on a competitive keyword, or one hour of a sales engineer." },
      ] },
    ],
    closing: { title: ["Your lift,", "measured on your traffic."], body: "Every ROI figure on this site is illustrative until it comes from your own holdout.", primary: { label: "Start a trial", href: "/book-demo" } },
  },

  // ------------------------------------------------------------------ Integrations, trust, company
  {
    path: "integrations", title: "Integrations", poster: "K13",
    description: "Install on WordPress, Shopify, Webflow, Framer, Google Tag Manager, React or Vue, and connect Slack, CRMs, Razorpay and calendars.",
    eyebrow: "Integrations", headline: ["One line of code.", "Any website."],
    sub: "Install it once. Everything else is set from your dashboard, so the site never needs editing again.",
    primary: START,
    sections: [
      { kind: "grid", title: "Where it installs.", cols: 4, items: [
        { title: "WordPress", body: "A plugin: paste the install code in settings." },
        { title: "Shopify", body: "A theme app embed with position and page controls." },
        { title: "Webflow and Framer", body: "A guide, plus a Framer code component." },
        { title: "Google Tag Manager", body: "A ready template, or a custom HTML tag." },
        { title: "React and Vue", body: "@fluidbuddha/react and @fluidbuddha/vue, with navigation hooks." },
        { title: "Any website", body: "One script tag, or FluidBuddha.init({...})." },
      ] },
      { kind: "grid", title: "What it connects to.", cols: 4, items: [
        { title: "Slack", body: "Hot-lead alerts and cost alerts." },
        { title: "CRMs, Zapier, Make", body: "Signed webhooks for every lead." },
        { title: "Razorpay", body: "Payment links on your own account." },
        { title: "Calendly and Cal.com", body: "Meetings booked, pre-filled." },
      ] },
    ],
    closing: { title: ["Install it this afternoon.", "Answer tonight."], primary: START },
  },
  {
    path: "trust", title: "Trust and security", poster: "K2",
    description: "Answers only from your content, PII masking, consent, retention and erasure, SOC 2 controls and data processing details.",
    eyebrow: "Trust and security", headline: ["Calm, careful,", "and on the record."],
    sub: "How FluidBuddha handles your content, your visitors' data and your security review.",
    primary: { label: "Request the security pack", href: "/contact" },
    sections: [
      { kind: "grid", title: "What we commit to.", cols: 2, items: [
        { title: "Answers only from your content", body: "Grounded answers carry their sources. Below a confidence threshold it says it doesn't know and offers your team." },
        { title: "Personal details masked", body: "Emails, phone numbers, card numbers, SSNs and IBANs are replaced before any model, history or storage sees them. Names and street addresses are not detected." },
        { title: "Consent and retention", body: "Microphone consent is recorded. Transcripts are kept 90 days by default, recap links expire, and an hourly sweep enforces it. Erasure by email." },
        { title: "Healthcare safety mode", body: "Diagnosis, treatment and dosage requests get a fixed refusal before any model call." },
        { title: "Where data is processed", body: "With bring-your-own-model, speech and embeddings still run on Google Vertex AI." },
        { title: "Controls and paperwork", body: "SOC 2 control matrix and policies, sub-processor list, DPA template, audit log and access reviews." },
      ] },
    ],
    closing: { title: ["Questions from", "your security team?"], primary: { label: "Request the security pack", href: "/contact" } },
  },
  {
    path: "customers", title: "Customers", poster: "K2",
    description: "Customer stories, starting with Hire Buddha. Only real, consented results are published.",
    eyebrow: "Customers", headline: ["Real stories,", "real numbers only."],
    sub: "We publish results only when they come from a customer's own holdout, with their consent. Until then, we show the story and how it will be measured.",
    primary: DEMO,
    sections: [
      { kind: "story", eyebrow: "Hire Buddha", title: "The first website to talk.", poster: "K6",
        body: "Hire Buddha, also from Buddha Cognitive Lab, was the first customer and is the built-in demo profile. Its measurement plan: a 10% holdout, with booked demos as the goal.",
        note: "Results will be published once the holdout leaves “collecting”." },
    ],
    closing: { title: ["Be one of", "the first stories."], primary: DEMO },
  },
  {
    path: "about", title: "About", poster: "K15",
    description: "FluidBuddha is a Buddha Cognitive Lab product. Towards digital enlightenment.",
    eyebrow: "About", headline: ["A Buddha Cognitive Lab product.", "Towards digital enlightenment."],
    sub: "We research intelligence that does real work in the real world. FluidBuddha is our second product, after Hire Buddha.",
    primary: { label: "Contact us", href: "/contact" },
    sections: [
      { kind: "prose", title: "Why we built it.", paragraphs: [
        "Most websites are frozen. When a visitor has a question at 9:40 PM, nothing answers, and they leave. We wanted every website to listen, answer from what it already says, and turn that attention into customers, calmly and honestly.",
      ] },
    ],
    closing: { title: ["Say hello.", "We read everything."], primary: { label: "Contact us", href: "/contact" } },
  },
  {
    path: "contact", title: "Contact", poster: "K15",
    description: "Contact the FluidBuddha team.",
    eyebrow: "Contact", headline: ["Talk to", "a person."],
    sub: "Or ask this website first. It answers from these pages, and hands over to us when it should.",
    primary: { label: "Book a demo", href: "/book-demo" },
    sections: [
      { kind: "grid", title: "How to reach us.", cols: 3, items: [
        { title: "Sales", body: "Book a demo, and the agent finds a slot in the conversation." },
        { title: "Partners and agencies", body: "Ask about the partner programme." },
        { title: "Security reviews", body: "Request the security pack and DPA." },
      ] },
    ],
    closing: { title: ["Or just ask", "the website."], primary: TRY },
  },
  {
    path: "book-demo", title: "Book a demo", poster: "K8", theme: "ink",
    description: "Book a demo with the FluidBuddha team. The website books it in the conversation.",
    eyebrow: "Book a demo", headline: ["Ask the website", "to book it."],
    sub: "Say “book a demo” in the bar below. It finds a slot, asks you to confirm, and sends the invite. During staffed hours, a person can join live.",
    primary: TRY,
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
