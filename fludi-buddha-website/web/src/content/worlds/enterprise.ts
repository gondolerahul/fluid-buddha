import type { World } from "./types";

// Copy: docs/marketing-docs/website/copy-enterprise.md
// Never say: "SOC 2 certified", "compliant", "regulator-approved", any named regulation, any price.
export const ENTERPRISE_WORLD: World = {
  id: "enterprise",
  path: "/for/enterprise",
  name: "Enterprise",
  audience: "banks, insurers and fintechs",
  theme: "light",
  meta: {
    title: "FluidBuddha for banks, insurers and fintechs — AI on your website, inside your rules",
    description:
      "An AI website agent that runs on your servers, uses your model contract and builds pages only from components you approved.",
  },
  nav: [
    { label: "Deployment", href: "#deployment" },
    { label: "Security", href: "#security" },
    { label: "Governance", href: "#controls" },
    { label: "Pilot", href: "#pilot" },
  ],
  cta: { label: "Plan a pilot", href: "/book-demo" },
  hero: {
    layout: "stack",
    eyebrow: "For banks, insurers and fintechs",
    title: ["AI on your website,", "inside your rules."],
    scene: "r0",
    roles: [
      { id: "digital", label: "Digital", sub: "Your teams decide what AI may build with, what it may say and where it may not go.", primary: "Plan a pilot", secondary: "See the controls" },
      { id: "security", label: "Security", sub: "Here is exactly where data goes, including the parts that still leave your network.", primary: "See the data flow", secondary: "Get the security documents" },
      { id: "compliance", label: "Compliance", sub: "You write the rules. The product enforces them and shows you what it did.", primary: "See the controls", secondary: "Plan a pilot" },
      { id: "brand", label: "Brand and design", sub: "Your components are the only building blocks the AI has. It never writes HTML or CSS.", primary: "See how components are approved", secondary: "Plan a pilot" },
      { id: "architecture", label: "Architecture", sub: "It starts on one Linux host, and falls back to your own page if it is slow or down.", primary: "Read the deployment guide", secondary: "See the data flow" },
      { id: "business", label: "Business", sub: "A 90-day pilot on one product area, with your compliance team reviewing from day one.", primary: "Plan a pilot", secondary: "See what is proven" },
    ],
  },
  film: {
    // Flat line drawings, drawn live from the scroll position (components/world/lineFilm.ts).
    // Each scene moves once and then holds. The `at` stretches sit inside the engine's nine scenes.
    kind: "code",
    layout: "bleed",
    code: { id: "enterprise", length: 10500, heroAt: [0, 0.058] },
    chapters: [
      { id: "runs", label: "Where it runs", at: [0.082, 0.16], eyebrow: "Where it runs", title: ["It runs on", "your own infrastructure."], body: "One Linux host to start. Offline licence. No call back to us." },
      { id: "contracts", label: "Your contracts", at: [0.186, 0.263], eyebrow: "Your contracts", title: ["It uses", "your model contract and your sign-in system."], body: "Anthropic, OpenAI or Azure OpenAI. Single sign-on through your identity provider." },
      { id: "leaves", label: "What leaves", at: [0.289, 0.366], eyebrow: "What still leaves", title: ["One thing still leaves your network.", "We tell you first."], body: "Speech recognition, speech output and search indexing run on Google Vertex AI." },
      { id: "approved", label: "Approved parts", at: [0.392, 0.47], eyebrow: "Approved parts", title: ["An admin approves", "every component the AI may use."], body: "Your own design system components, taken from your Storybook." },
      { id: "check", label: "One check", at: [0.496, 0.573], eyebrow: "One check", title: ["Every page passes", "the same check", "before anyone sees it."], body: "The AI chooses components and fills them in. It never writes HTML or CSS. Anything that fails is left out." },
      { id: "numbers", label: "Your numbers", at: [0.599, 0.676], eyebrow: "Your numbers", title: ["Prices and rates come from", "your systems,", "never from the AI."], body: "You mark which fields may only be filled from your own data." },
      { id: "off-limits", label: "Off limits", at: [0.702, 0.78], eyebrow: "Off limits", title: ["Some pages are", "never touched."], body: "Checkout, legal and privacy pages are excluded by default. Your required notices appear on every page, unchanged." },
      { id: "record", label: "The record", at: [0.806, 0.883], eyebrow: "The record", title: ["Every console change", "is logged."], body: "Generated pages go to a review queue. One click blocks a page." },
      { id: "start", label: "Start small", at: [0.909, 1], eyebrow: "Start small", title: ["Start with one page", "and a measured pilot."], body: "Your compliance team can review every generated page before any visitor sees it." },
    ],
  },
  hi: {
    title: "आपकी वेबसाइट पर AI,|आपके नियमों के भीतर।",
    sub: "आपकी टीमें तय करती हैं कि AI किन हिस्सों से पेज बना सकता है, क्या कह सकता है और कहाँ नहीं जा सकता।",
    cta: "पायलट की योजना बनाइए",
    chapters: {
      runs: "यह|आपके अपने इन्फ़्रास्ट्रक्चर|पर चलता है।",
      leaves: "एक चीज़ अब भी आपके नेटवर्क से बाहर जाती है।|हम यह पहले ही बता देते हैं।",
      approved: "AI जो भी कंपोनेंट इस्तेमाल करे,|उसे पहले एक एडमिन मंज़ूर करता है।",
      numbers: "क़ीमतें और दरें|आपके सिस्टम से|आती हैं, AI से कभी नहीं।",
      start: "एक पेज और|एक मापे हुए पायलट|से शुरू कीजिए।",
    },
  },
  sections: [
    {
      kind: "table", id: "limits", num: "01", eyebrow: "Stated first", title: ["Three limits you should know", "before the security review."],
      head: ["Limit", "What it means for you"],
      rows: [
        ["Speech and search indexing run on Google Vertex AI", "This is true even when you host the product yourself and use your own model. If your policy requires every model on your own cloud, FluidBuddha is not a fit today."],
        ["The page-building features have been verified with test models, not yet with production traffic", "We offer a pilot with a built-in comparison test, not a promised result."],
        ["Pages cannot yet show a signed-in customer\u2019s own data", "Data on pages comes through site-level access only."],
      ],
    },
    {
      kind: "cards", id: "data-flow", num: "02", eyebrow: "Where data goes", title: ["What stays inside,", "and what leaves."], cols: 3,
      items: [
        { n: "Inside your network", title: "The product and its data", body: "The application, the console, the database, visitor conversations, leads and the audit log." },
        { n: "Your contracts", title: "Your providers", body: "Your model provider and your identity provider." },
        { n: "Leaves your network", title: "Speech and search indexing", body: "Speech recognition, speech output and search indexing run on Google Vertex AI." },
      ],
      note: "If your own model provider fails, the product can fall back to the platform model. Ask us to discuss this if your policy does not allow it.",
    },
    {
      kind: "controls", id: "controls", num: "03", eyebrow: "Controls", title: ["You write the rules.", "The product enforces them and shows you what it did."],
      items: [
        { n: "3.1", title: "Approved components", body: "The AI may use only components an admin has approved. Each version is approved separately." },
        { n: "3.2", title: "Field rules", body: "Each field is marked: the AI may write it, or it must come from your data." },
        { n: "3.3", title: "Site rules", body: "Rules you write override everything else the agent has been told." },
        { n: "3.4", title: "Fixed and blocked answers", body: "An approved answer is repeated word for word. A blocked question is never answered by the agent." },
        { n: "3.5", title: "Excluded pages", body: "Checkout, cart, legal, terms and privacy are excluded by default. You can add more." },
        { n: "3.6", title: "Required notices", body: "Content you pin appears on every generated page, unchanged." },
        { n: "3.7", title: "Budgets", body: "A daily limit on newly generated pages, per site and per visitor." },
        { n: "3.8", title: "Review queue", body: "A share of generated pages, and every page with a warning, goes to a reviewer. For a pilot the share can be 100 %." },
        { n: "3.9", title: "Audit log", body: "Every console change and sign-in, kept for one year, searchable, exportable." },
      ],
    },
    {
      kind: "list", id: "deployment", num: "04", eyebrow: "Deployment", title: ["One host", "to start."],
      items: [
        "One Linux host: 4 vCPU, 8 GB memory, 40 GB disk.",
        "Supplied as a Docker Compose bundle, with an install option that needs no internet access. Speech and indexing still use Google Vertex AI.",
        "Backups with point-in-time recovery, and an upgrade script.",
        "If the licence lapses, the console becomes read-only. Visitors are not affected.",
        "Generated pages are served through your own site. If FluidBuddha is slow or down, your own page is served.",
        "One host handled about 50 voice conversations at once in our load test. Plan more capacity for higher peaks.",
      ],
    },
    {
      kind: "list", id: "security", num: "05", eyebrow: "Access and security", title: ["Who can sign in,", "and how."],
      items: [
        "Single sign-on for the email domains you prove you own.",
        "Two-factor sign-in, which an owner can require for everyone.",
        "Sessions end after 60 minutes idle and 12 hours in total.",
        "Ten failed sign-ins lock the account for 15 minutes.",
        "Secrets are encrypted, with keys you can rotate.",
        "A quarterly access review is emailed to owners and admins.",
      ],
    },
    {
      kind: "list", id: "documents", num: "06", eyebrow: "Security documents", title: ["What we can give you", "today."],
      items: ["A control matrix", "Security policies", "A sub-processor list", "A data processing agreement template"],
      note: "These are drafts. We do not hold a security certification or an audit report yet, and we will not say that we do.",
      cta: { label: "Get the security documents", href: "/book-demo" },
    },
    {
      kind: "list", id: "visitors", num: "07", eyebrow: "Your visitors", title: ["What your visitors can", "see and change."],
      items: [
        "\u201cWhy this?\u201d shows up to three plain reasons a page was arranged the way it was.",
        "A preferences panel lets the visitor change or reset every setting.",
        "Only presentation changes: density, format, detail, tone, motion and colour scheme, within the limits your brand team sets.",
        "Prices are never personalised.",
        "Nothing is stored for a visitor unless they choose \u201cRemember me\u201d.",
      ],
    },
    {
      kind: "table", id: "pilot", num: "08", eyebrow: "The pilot", title: ["Ninety days. One product area.", "A measured result."],
      head: ["Stage", "What happens"],
      rows: [
        ["Weeks 1 to 3", "Install in a sandbox. Your security team reviews the data flow and the audit log."],
        ["Weeks 3 to 6", "Your brand team approves the first components. Your compliance team writes the rules."],
        ["Weeks 6 to 12", "The agent runs on one product area, with a share of visitors held back for comparison and the review queue on."],
        ["End", "You get the measured difference, its margin of error and the cost. We promise the measurement, not the outcome."],
      ],
      cta: { label: "Plan a pilot", href: "/book-demo" },
    },
    {
      kind: "faq", id: "faq", num: "09", eyebrow: "Questions", title: ["What each team", "asks first."],
      items: [
        { q: "How do we stop it saying something we have not approved?", a: "Your written rules override all other instructions. Approved answers are repeated exactly, and blocked questions are never answered. You should test your rules in the pilot." },
        { q: "Do you call home?", a: "No. The licence is checked on your host." },
        { q: "What runs in the visitor\u2019s browser?", a: "An isolated widget that never inserts AI-written HTML. Your own components run only from the approved bundle, and only if its integrity check passes." },
        { q: "Which certifications do you hold?", a: "None yet. We have a draft control matrix and policies, and no audit report." },
        { q: "Can the AI quote a rate or a return?", a: "Only from your content, with its source, and only if your rules allow it. Rates shown on pages come from your systems." },
        { q: "Can we see what visitors were shown?", a: "Conversations are stored with contact details hidden, for the period you set. Generated pages are sampled for review. Set the sample to 100 % if you need every page." },
        { q: "Does the AI write HTML or CSS?", a: "No. It chooses from your approved components and fills in their fields." },
        { q: "Can our components send events back to the agent?", a: "Not yet." },
        { q: "How do we monitor it?", a: "Standard metrics, alert rules with a runbook, readiness checks and a status page." },
        { q: "What will we have in 90 days?", a: "A working agent on one product area, reviewed by your own teams, and a measured result." },
        { q: "What does it cost?", a: "Enterprise and self-hosted pricing is agreed with you directly." },
      ],
    },
    {
      kind: "close", id: "close", title: ["Bring your security and compliance teams", "to the first call."], lead: "We will state the limits before they ask.",
      primary: { label: "Plan a pilot", href: "/book-demo" }, secondary: { label: "Get the security documents", href: "/book-demo" },
    },
  ],
};
