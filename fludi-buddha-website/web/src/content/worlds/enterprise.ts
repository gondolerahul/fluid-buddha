import type { World } from "./types";

// Copy: docs/marketing-docs/website/copy-enterprise.md, tightened in the redesign
// (docs/marketing-docs/website/audit-2026-11-11.md §4).
// World 3, "The specification": white (60), ink (30), gold (10). Section numbers are the
// genre here, because a security review refers to them. Gold appears only where something is approved.
// Never say: "SOC 2 certified", "compliant", "regulator-approved", any named regulation, any price.
export const ENTERPRISE_WORLD: World = {
  id: "enterprise",
  path: "/for/enterprise",
  name: "Enterprise",
  audience: "banks, insurers and fintechs",
  meta: {
    title: "FluidBuddha for banks, insurers and fintechs: AI on your website, inside your rules",
    description:
      "An AI website agent that runs on your servers, uses your model contract and builds pages only from components you approved.",
  },
  hero: {
    title: ["AI on your website,", "inside your rules."],
    roles: [
      { id: "digital", label: "Digital", sub: "Your teams decide what AI may build with, what it may say and where it may not go.", primary: "Plan a pilot", primaryHref: "#pilot", secondary: "Try the rules", secondaryHref: "#console" },
      { id: "security", label: "Security", sub: "Here is exactly where data goes, including the parts that still leave your network.", primary: "See the data flow", primaryHref: "#data-flow", secondary: "Get the security documents", secondaryHref: "#documents" },
      { id: "compliance", label: "Compliance", sub: "You write the rules. The product enforces them and shows you what it did.", primary: "Try the rules", primaryHref: "#console", secondary: "See the controls", secondaryHref: "#controls" },
      { id: "brand", label: "Brand and design", sub: "Your components are the only building blocks the AI has. It never writes HTML or CSS.", primary: "See how components are checked", primaryHref: "#console", secondary: "Plan a pilot", secondaryHref: "#pilot" },
      { id: "architecture", label: "Architecture", sub: "It starts on one Linux host, and falls back to your own page if it is slow or down.", primary: "Read the deployment notes", primaryHref: "#deployment", secondary: "See the data flow", secondaryHref: "#data-flow" },
      { id: "business", label: "Business", sub: "A 90-day pilot on one product area, with your compliance team reviewing from day one.", primary: "Plan a pilot", primaryHref: "#pilot", secondary: "See what is proven", secondaryHref: "#limits" },
    ],
  },
  film: {
    // Flat line drawings, drawn live from the scroll position (components/world/lineFilm.ts).
    // Each scene moves once and then holds.
    kind: "code",
    code: { id: "enterprise", length: 10500, heroAt: [0, 0.058] },
    chapters: [
      { id: "runs", label: "Where it runs", at: [0.082, 0.16], title: ["It runs on", "your own infrastructure."], body: "One Linux host to start. Offline licence. No call back to us." },
      { id: "contracts", label: "Your contracts", at: [0.186, 0.263], title: ["It uses", "your model contract and your sign-in system."], body: "Anthropic, OpenAI or Azure OpenAI. Single sign-on through your identity provider." },
      { id: "leaves", label: "What leaves", at: [0.289, 0.366], title: ["One thing still leaves your network.", "We tell you first."], body: "Speech recognition, speech output and search indexing run on Google Vertex AI." },
      { id: "approved", label: "Approved parts", at: [0.392, 0.47], title: ["An admin approves", "every component the AI may use."], body: "Your own design system components, taken from your Storybook." },
      { id: "check", label: "One check", at: [0.496, 0.573], title: ["Every page passes", "the same check", "before anyone sees it."], body: "The AI chooses components and fills them in. It never writes HTML or CSS. Anything that fails is left out." },
      { id: "numbers", label: "Your numbers", at: [0.599, 0.676], title: ["Prices and rates come from", "your systems,", "never from the AI."], body: "You mark which fields may only be filled from your own data." },
      { id: "off-limits", label: "Off limits", at: [0.702, 0.78], title: ["Some pages are", "never touched."], body: "Checkout, legal and privacy pages are excluded by default. Your required notices appear on every page, unchanged." },
      { id: "record", label: "The record", at: [0.806, 0.883], title: ["Every console change", "is logged."], body: "Generated pages go to a review queue. One click blocks a page." },
      { id: "start", label: "Start small", at: [0.909, 1], title: ["Start with one page", "and a measured pilot."], body: "Your compliance team can review every generated page before any visitor sees it." },
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
      kind: "spec-table", id: "limits", num: "1", title: ["Three limits you should know", "before the security review."],
      head: ["Limit", "What it means for you"],
      rows: [
        ["Speech and search indexing run on Google Vertex AI", "This is true even when you host the product yourself and use your own model. If your policy requires every model on your own cloud, FluidBuddha is not a fit today."],
        ["The page-building features have been verified with test models, not yet with production traffic", "We offer a pilot with a built-in comparison test, not a promised result."],
        ["Pages cannot yet show a signed-in customer’s own data", "Data on pages comes through site-level access only."],
      ],
    },
    {
      kind: "flow", id: "data-flow", num: "2", title: ["What stays inside,", "and what leaves."],
      zones: [
        { n: "Inside your network", title: "The product and its data", body: "The application, the console, the database, visitor conversations, leads and the audit log." },
        { n: "Your contracts", title: "Your providers", body: "Your model provider and your identity provider." },
        { n: "Leaves your network", title: "Speech and search indexing", body: "Speech recognition, speech output and search indexing run on Google Vertex AI." },
      ],
      note: "If your own model provider fails, the product can fall back to the platform model. Ask us to discuss this if your policy does not allow it.",
    },
    {
      kind: "controls", id: "controls", num: "3", title: ["You write the rules.", "The product enforces them and shows you what it did."],
      items: [
        { n: "3.1", title: "Approved components", body: "The AI may use only components an admin has approved. Each version is approved separately." },
        { n: "3.2", title: "Field rules", body: "Each field is marked: the AI may write it, or it must come from your data." },
        { n: "3.3", title: "Site rules", body: "Rules you write override everything else the agent has been told." },
        { n: "3.4", title: "Fixed and blocked answers", body: "An approved answer is repeated word for word. A blocked question is never answered by the agent." },
        { n: "3.5", title: "Excluded pages", body: "Checkout, cart, legal, terms and privacy are excluded by default. You can add more." },
        { n: "3.6", title: "Required notices", body: "Content you pin appears on every generated page, unchanged." },
        { n: "3.7", title: "Budgets", body: "A daily limit on newly generated pages, per site and per visitor." },
        { n: "3.8", title: "Review queue", body: "A share of generated pages, and every page with a warning, goes to a reviewer. For a pilot the share can be 100%." },
        { n: "3.9", title: "Audit log", body: "Every console change and sign-in, kept for one year, searchable, exportable." },
      ],
    },
    {
      // the signature moment: switch the controls, run the check, read the log
      kind: "rules", id: "console", num: "4", title: ["Try the rules", "on a generated page."],
      lead: "Switch a control, then run the check. Every block passes or is left out with its reason, and each change is written to the log. A simulation of the product's own check, running in your browser.",
    },
    {
      kind: "spec-list", id: "deployment", num: "5", title: ["One host", "to start."],
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
      kind: "spec-list", id: "security", num: "6", title: ["Who can sign in,", "and how."],
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
      kind: "spec-list", id: "documents", num: "7", title: ["What we can give you", "today."],
      items: ["A control matrix", "Security policies", "A sub-processor list", "A data processing agreement template"],
      note: "These are drafts. We do not hold a security certification or an audit report yet, and we will not say that we do.",
      cta: { label: "Ask for the security documents", href: "/contact" },
    },
    {
      kind: "visitors", id: "visitors", num: "8", title: ["What your visitors can", "see and change."],
      items: [
        "“Why this?” shows up to three plain reasons a page was arranged the way it was.",
        "A preferences panel lets the visitor change or reset every setting.",
        "Only presentation changes: density, format, detail, tone, motion and colour scheme, within the limits your brand team sets.",
        "Prices are never personalised.",
        "Nothing is stored for a visitor unless they choose “Remember me”.",
      ],
    },
    {
      kind: "timeline", id: "pilot", tone: "gold", num: "9", title: ["Ninety days, one product area,", "a measured result."],
      rows: [
        { stage: "Weeks 1 to 3", weeks: [0, 3], what: "Install in a sandbox. Your security team reviews the data flow and the audit log." },
        { stage: "Weeks 3 to 6", weeks: [3, 6], what: "Your brand team approves the first components. Your compliance team writes the rules." },
        { stage: "Weeks 6 to 12", weeks: [6, 12], what: "The agent runs on one product area, with a share of visitors held back for comparison and the review queue on." },
        { stage: "End", weeks: [12, 13], what: "You get the measured difference, its margin of error and the cost. We promise the measurement, not the outcome." },
      ],
      cta: { label: "Plan a pilot", href: "/book-demo" },
    },
    {
      kind: "faq", id: "faq", title: ["What each team", "asks first."], ask: "Is my data safe?",
      items: [
        { q: "How do we stop it saying something we have not approved?", a: "Your written rules override all other instructions. Approved answers are repeated exactly, and blocked questions are never answered. You should test your rules in the pilot." },
        { q: "Do you call home?", a: "No. The licence is checked on your host." },
        { q: "What runs in the visitor’s browser?", a: "An isolated widget that never inserts AI-written HTML. Your own components run only from the approved bundle, and only if its integrity check passes." },
        { q: "Which certifications do you hold?", a: "None yet. We have a draft control matrix and policies, and no audit report." },
        { q: "Can the AI quote a rate or a return?", a: "Only from your content, with its source, and only if your rules allow it. Rates shown on pages come from your systems." },
        { q: "Can we see what visitors were shown?", a: "Conversations are stored with contact details hidden, for the period you set. Generated pages are sampled for review. Set the sample to 100% if you need every page." },
        { q: "Does the AI write HTML or CSS?", a: "No. It chooses from your approved components and fills in their fields." },
        { q: "Can our components send events back to the agent?", a: "Not yet." },
        { q: "How do we monitor it?", a: "Standard metrics, alert rules with a runbook, readiness checks and a status page." },
        { q: "What will we have in 90 days?", a: "A working agent on one product area, reviewed by your own teams, and a measured result." },
        { q: "What does it cost?", a: "Enterprise and self-hosted pricing is agreed with you directly." },
      ],
    },
    {
      kind: "close", id: "close", tone: "gold", title: ["Bring your security and compliance teams", "to the first call."], lead: "We will state the limits before they ask.",
      primary: { label: "Plan a pilot", href: "/book-demo" }, secondary: { label: "Ask for the security documents", href: "/contact" },
    },
  ],
};
