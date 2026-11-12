import type { World } from "./types";

// Copy: docs/marketing-docs/website/copy-saas.md, tightened in the redesign
// (docs/marketing-docs/website/audit-2026-11-11.md §4).
// World 1, "Night console": ink (60), raised ink (30), gold (10). A film drawn in characters in a
// console window; mono data, hairline cells.
export const SAAS_WORLD: World = {
  id: "saas",
  path: "/for/saas",
  name: "SaaS",
  audience: "SaaS teams",
  meta: {
    title: "FluidBuddha for B2B SaaS: your pricing page, answering buyers",
    description:
      "Buyers read your pricing page at night and leave with questions. FluidBuddha answers them from your own content and sends your team a scored lead.",
  },
  hero: {
    title: ["Your pricing page gets the traffic.", "Now it answers the questions."],
    roles: [
      { id: "growth", label: "Growth", sub: "More qualified demos from the visitors you already have, with a built-in test that shows the lift.", primary: "Try it on your site", primaryHref: "#try", secondary: "See the lead it sends", secondaryHref: "#lead" },
      { id: "sales", label: "Sales", sub: "It handles the first six questions. Your first call starts at the seventh.", primary: "See the lead it sends", primaryHref: "#lead", secondary: "Try it on your site", secondaryHref: "#try" },
      { id: "engineering", label: "Engineering", sub: "One script tag, about 38.6 kB, isolated from your CSS and JavaScript.", primary: "Read the install code", primaryHref: "#install", secondary: "See where data goes", secondaryHref: "#data" },
      { id: "leadership", label: "Leadership", sub: "One more deal a quarter can pay for a year. The product measures whether you are on track.", primary: "See the cost", primaryHref: "#cost", secondary: "See how the test works", secondaryHref: "#prove-it" },
    ],
  },
  film: {
    // Drawn live in characters from the scroll position (components/world/asciiFilm.ts).
    kind: "code",
    code: { id: "saas", length: 11000, heroAt: [0, 0.055] },
    chapters: [
      { id: "night", label: "23:04", at: [0.075, 0.155], title: ["A buyer is on your pricing page", "with three questions."], body: "Your sales team is offline until morning." },
      { id: "questions", label: "The questions", at: [0.185, 0.27], title: ["“Does it work with our ERP? What do 40 seats cost?", "Where is our data kept?”"], body: "Today the answer is “Contact sales”. Many buyers do not." },
      { id: "shows", label: "It shows", at: [0.3, 0.39], title: ["It draws", "how the integration works."], body: "A diagram appears while it explains, built from your documentation." },
      { id: "calculates", label: "It calculates", at: [0.42, 0.51], title: ["It works out the price", "for their team."], body: "The buyer changes 40 seats to 60 and the figure updates. Prices come from your price list.", note: "Example figures." },
      { id: "there", label: "The right page", at: [0.54, 0.62], title: ["It opens your security page", "at the right paragraph."], body: "The buyer reads your own words, not a summary." },
      { id: "lead", label: "The lead", at: [0.65, 0.73], title: ["A lead with a score", "and what was asked."], body: "It arrives in Slack and in your CRM by webhook.", note: "Example lead." },
      { id: "join", label: "Step in", at: [0.76, 0.82], title: ["A salesperson can", "join the conversation."], body: "They can take over the chat, or call the visitor in the browser if the visitor is using voice." },
      { id: "summary", label: "The summary", at: [0.85, 0.91], title: ["The buyer forwards", "a summary."], body: "It holds the answers, the diagram and the calculator. You see how many people opened it." },
      { id: "prove", label: "Prove it", at: [0.94, 1], title: ["One visitor in ten never sees it.", "The difference is your lift."], body: "The result stays valid however often you check it.", note: "Example chart." },
    ],
  },
  hi: {
    title: "आपके प्राइसिंग पेज पर ट्रैफ़िक आता है।|अब वह सवालों के जवाब भी देता है।",
    sub: "जो विज़िटर पहले से आ रहे हैं, उन्हीं से ज़्यादा अच्छे डेमो, और एक टेस्ट जो फ़र्क़ दिखाता है।",
    cta: "अपनी साइट पर आज़माएँ",
    chapters: {
      night: "रात 11:04। एक ख़रीदार आपके प्राइसिंग पेज पर है,|तीन सवालों के साथ।",
      shows: "यह बनाकर दिखाता है कि|इंटीग्रेशन कैसे काम करता है।",
      calculates: "यह|उनकी टीम के हिसाब से|क़ीमत निकालता है।",
      lead: "आपकी टीम को लीड मिलती है,|स्कोर और पूछे गए सवालों के साथ।",
      prove: "दस में से एक विज़िटर इसे नहीं देखता।|यही फ़र्क़ आपकी बढ़त है।",
    },
  },
  sections: [
    {
      // the signature moment: the visitor plays the buyer and watches the lead build
      kind: "lead-desk", id: "lead", tone: "second",
      title: ["Be the buyer.", "Watch the lead build."],
      lead: "Ask the three questions a buyer asks at 11 pm. On the right is what your sales team receives, as it would arrive. Nothing leaves your browser.",
    },
    {
      kind: "questions", id: "questions", title: ["First sales calls keep answering", "the same six questions."],
      rows: [
        { q: "“Does it integrate with X?”", a: "Answers from your docs and draws the integration.", does: "diagram" },
        { q: "“What would it cost for our team?”", a: "Builds a calculator from your price list.", does: "calculator" },
        { q: "“Where is our data kept?”", a: "Opens your security page at the right section.", does: "navigates" },
        { q: "“How long does setup take?”", a: "Answers from your onboarding pages, with the source.", does: "source" },
        { q: "“How are you different from Y?”", a: "Shows a comparison table from your own content.", does: "table" },
        { q: "“Can we try it?”", a: "Starts a trial or books a demo, after the buyer confirms.", does: "action" },
      ],
    },
    {
      kind: "holdout", id: "prove-it", title: ["You do not have to take our word", "for the lift."],
      steps: [
        { title: "Choose the page that means money", body: "For example, the page a buyer reaches after booking a demo." },
        { title: "One visitor in ten is held back", body: "FluidBuddha never shows itself to that group." },
        { title: "Both groups are measured", body: "On the same page, over the same days." },
        { title: "You read the difference", body: "With its margin of error, on any day you like." },
      ],
      note: "We do not quote a lift figure. Your own traffic produces it.",
    },
    {
      kind: "cost", id: "cost", title: ["About ₹16.50 a conversation", "on Growth."],
      body: "Compare that with what you pay for one click on your main keyword.",
      note: "Growth: ₹33,000 a month for 2,000 conversations, then ₹17 each. Scale: ₹1,25,000 a month for 10,000, then ₹10 each. Example sum: one deal of ₹6,00,000 a year against ₹3,96,000 a year for Growth.",
    },
    {
      kind: "install", id: "install", title: ["One script tag.", "Nothing else to edit."],
      lead: "About 38.6 kB, loaded asynchronously, in its own isolated container (Shadow DOM), so it cannot change your CSS or clash with your JavaScript.",
      // Real install paths only: the loader tag, the SDK's init() and its window events (fluid-buddha-sdk/README.md).
      tabs: [
        { label: "Script tag", code: "<script src=\"https://<server>/widget/loader.js\"\n        data-key=\"fbk_…\" async></script>" },
        { label: "Tag Manager", code: "<!-- Custom HTML tag, trigger: All Pages -->\n<script src=\"https://<server>/widget/loader.js\"\n        data-key=\"fbk_…\" async></script>" },
        { label: "JavaScript", code: "import { init } from \"fluid-buddha\";\n\ninit({\n  backend: \"wss://<server>\",\n  key: \"fbk_…\",\n  hooks: { onNavigate: (path) => router.push(path) },\n});" },
        { label: "Your router", code: "// Every agent command is also a cancelable window event\nwindow.addEventListener(\"fluidbuddha:navigate\", (e) => {\n  e.preventDefault();\n  router.push(e.detail.path);\n});" },
      ],
    },
    {
      kind: "facts", id: "data", tone: "second", title: ["Five facts", "for your security questionnaire."],
      items: [
        { text: "Emails, phone numbers and card numbers are hidden before the AI sees them.", ok: true },
        { text: "The microphone is off until the visitor agrees.", ok: true },
        { text: "You set how long conversations are kept, and can delete one person’s data by email.", ok: true },
        { text: "Speech and search indexing run on Google Vertex AI.", ok: true },
        { text: "Names and street addresses are not hidden automatically.", ok: false },
      ],
    },
    {
      kind: "limits", id: "limits", title: ["Three limits", "to know first."],
      items: [
        "English and Hindi only. Buyers who need other languages are not served yet.",
        "No built-in CRM connectors. Leads go out by signed webhook, Zapier, Make and Slack.",
        "It does not replace your sales team. It gets buyers to them sooner.",
      ],
    },
    {
      kind: "try-site", id: "try", tone: "second", title: ["Enter your website.", "Talk to it in a few minutes."],
      lead: "We read your public pages and set up a private preview. Nothing changes on your live site.",
    },
    {
      kind: "faq", id: "faq", title: ["What each team", "asks first."], ask: "Will it clash with our CSS?",
      items: [
        { q: "Will it make things up?", a: "It answers from your content and shows sources. When it cannot find an answer it says so. This is a guardrail, not a guarantee." },
        { q: "Can it hurt our SEO?", a: "No. The agent does not change your pages. If you add fitted page sections later, search engines still see your own content." },
        { q: "What if it says something wrong about us?", a: "You can write rules it must follow, fix an approved answer so it is always used, and block questions it must not answer." },
        { q: "What is the risk if it does not work?", a: "The Free plan covers 100 conversations. Growth is monthly. The test shows early whether it is working." },
        { q: "Will it send me junk leads?", a: "Each lead has a score with its reasons and a summary of what was asked." },
        { q: "Can I talk to someone who is on the site now?", a: "Yes. You can see live conversations, take one over and hand it back." },
        { q: "Will it clash with our CSS or JavaScript?", a: "No. It runs in an isolated container (Shadow DOM)." },
        { q: "Which languages?", a: "English and Hindi only." },
      ],
    },
    {
      kind: "close", id: "close", tone: "gold", title: ["Put it on your pricing page", "first."], lead: "One script tag. The Free plan covers 100 conversations a month.",
      primary: { label: "Try it on your site", href: "/demo#your-site" }, secondary: { label: "Book a demo", href: "/book-demo" },
    },
  ],
};
