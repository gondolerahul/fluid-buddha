import type { World } from "./types";

// Copy: docs/marketing-docs/website/copy-saas.md
export const SAAS_WORLD: World = {
  id: "saas",
  path: "/for/saas",
  name: "SaaS",
  audience: "SaaS teams",
  theme: "dark",
  meta: {
    title: "FluidBuddha for B2B SaaS — your pricing page, answering buyers",
    description:
      "Buyers read your pricing page at night and leave with questions. FluidBuddha answers them from your own content and sends your team a scored lead.",
  },
  nav: [
    { label: "Product", href: "/product" },
    { label: "Proof", href: "/results" },
    { label: "Pricing", href: "/pricing" },
    { label: "Developers", href: "/developers" },
  ],
  cta: { label: "Try it on your site", href: "/demo#start" },
  hero: {
    layout: "stack",
    eyebrow: "For B2B SaaS",
    title: ["Your pricing page gets the traffic.", "Now it answers the questions."],
    scene: "s1",
    roles: [
      { id: "growth", label: "Growth", sub: "More qualified demos from the visitors you already have, with a built-in test that shows the lift.", primary: "Try it on your site", secondary: "See how the test works" },
      { id: "sales", label: "Sales", sub: "It handles the first six questions. Your first call starts at the seventh.", primary: "See a scored lead", secondary: "Try it on your site" },
      { id: "engineering", label: "Engineering", sub: "One script tag, about 38.6 kB, isolated from your CSS and JavaScript.", primary: "Read the install guide", secondary: "See where data goes" },
      { id: "leadership", label: "Leadership", sub: "One more deal a quarter can pay for a year. The product measures whether you are on track.", primary: "See the business case", secondary: "Try it on your site" },
    ],
  },
  film: {
    // Drawn live in characters from the scroll position (components/world/asciiFilm.ts).
    // The `at` stretches sit inside the engine's nine scenes.
    kind: "code",
    layout: "bleed",
    code: { id: "saas", length: 11000, heroAt: [0, 0.055] },
    chapters: [
      { id: "night", label: "23:04", at: [0.075, 0.155], eyebrow: "23:04", title: ["A buyer is on your pricing page", "with three questions."], body: "Your sales team is offline until morning.", scene: "s1" },
      { id: "questions", label: "The questions", at: [0.185, 0.27], eyebrow: "The questions", title: ["\u201cDoes it work with our ERP? What do 40 seats cost?", "Where is our data kept?\u201d"], body: "Today the answer is \u201cContact sales\u201d. Many buyers do not.", scene: "s1" },
      { id: "shows", label: "It shows", at: [0.3, 0.39], eyebrow: "It shows", title: ["It draws", "how the integration works."], body: "A diagram appears while it explains, built from your documentation.", scene: "s3" },
      { id: "calculates", label: "It calculates", at: [0.42, 0.51], eyebrow: "It calculates", title: ["It works out the price", "for their team."], body: "The buyer changes 40 seats to 60 and the figure updates. Prices come from your price list.", note: "Example figures.", scene: "s3" },
      { id: "there", label: "The right page", at: [0.54, 0.62], eyebrow: "It takes them there", title: ["It opens your security page", "at the right paragraph."], body: "The buyer sees your own words, not a summary.", scene: "s3" },
      { id: "lead", label: "The lead", at: [0.65, 0.73], eyebrow: "Your team gets the lead", title: ["A lead with a score", "and what was asked."], body: "It arrives in Slack and in your CRM by webhook.", note: "Example lead.", scene: "s3" },
      { id: "join", label: "Step in", at: [0.76, 0.82], eyebrow: "Step in", title: ["A salesperson can", "join the conversation."], body: "They can take over the chat, or call the visitor in the browser if the visitor is using voice.", scene: "s3" },
      { id: "summary", label: "The summary", at: [0.85, 0.91], eyebrow: "The rest of the buying team", title: ["The buyer forwards", "a summary."], body: "It holds the answers, the diagram and the calculator. You see how many people opened it.", scene: "s3" },
      { id: "prove", label: "Prove it", at: [0.94, 1], eyebrow: "Prove it", title: ["One visitor in ten never sees it.", "The difference is your lift."], body: "The result stays valid however often you check it.", note: "Example chart.", scene: "s9" },
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
      kind: "talk", id: "try", eyebrow: "Try it on your own site", title: ["Enter your website.", "Talk to it in a few minutes."],
      lead: "We read your public pages and set up a private preview. Nothing changes on your live site.",
      questions: ["Does it integrate with our stack?", "What would 60 seats cost?", "Where is our data kept?"],
      cta: { label: "Read my site", href: "/demo#start" },
    },
    {
      kind: "table", id: "questions", eyebrow: "The six questions", title: ["First sales calls keep answering", "the same six questions."],
      head: ["Buyer asks", "What FluidBuddha does"],
      rows: [
        ["\u201cDoes it integrate with X?\u201d", "Answers from your docs and draws the integration."],
        ["\u201cWhat would it cost for our team?\u201d", "Builds a calculator from your price list."],
        ["\u201cWhere is our data kept?\u201d", "Opens your security page at the right section."],
        ["\u201cHow long does setup take?\u201d", "Answers from your onboarding pages, with the source."],
        ["\u201cHow are you different from Y?\u201d", "Shows a comparison table from your own content."],
        ["\u201cCan we try it?\u201d", "Starts a trial or books a demo, after the buyer confirms."],
      ],
    },
    { kind: "lead-install", id: "lead-card" },
    {
      kind: "cards", id: "prove-it", eyebrow: "Prove it", title: ["You do not have to take our word", "for the lift."], cols: 4, steps: true,
      items: [
        { n: "1", title: "Choose the page that means money", body: "For example, the page a buyer reaches after booking a demo." },
        { n: "2", title: "One visitor in ten is held back", body: "FluidBuddha never shows itself to that group." },
        { n: "3", title: "Both groups are measured", body: "On the same page, over the same days." },
        { n: "4", title: "You read the difference", body: "With its margin of error, on any day you like." },
      ],
      note: "We do not quote a lift figure. Your own traffic produces it.",
    },
    {
      kind: "callout", id: "cost", eyebrow: "What it costs", big: "\u20b916.50",
      title: "About \u20b916.50 a conversation on Growth. Compare that with what you pay for one click on your main keyword.",
      note: "Growth: \u20b933,000 a month for 2,000 conversations, then \u20b917 each. Scale: \u20b91,25,000 a month for 10,000, then \u20b910 each. Example sum: one deal of \u20b96,00,000 a year against \u20b93,96,000 a year for Growth.",
    },
    {
      kind: "list", id: "data", eyebrow: "Where data goes", title: ["Five facts", "for your security questionnaire."],
      items: [
        "Emails, phone numbers and card numbers are hidden before the AI sees them.",
        "The microphone is off until the visitor agrees.",
        "You set how long conversations are kept, and can delete one person\u2019s data by email.",
        "Speech and search indexing run on Google Vertex AI.",
        "Names and street addresses are not hidden automatically.",
      ],
    },
    {
      kind: "list", id: "limits", eyebrow: "What it does not do", title: ["Three limits,", "stated plainly."],
      items: [
        "English and Hindi only. Buyers who need other languages are not served yet.",
        "No built-in CRM connectors. Leads go out by signed webhook, Zapier, Make and Slack.",
        "It does not replace your sales team. It gets buyers to them sooner.",
      ],
    },
    {
      kind: "faq", id: "faq", eyebrow: "Questions", title: ["What each team", "asks first."],
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
      kind: "close", id: "close", title: ["Put it on your pricing page", "first."], lead: "One script tag. The Free plan covers 100 conversations a month.",
      primary: { label: "Try it on your site", href: "/demo#start" }, secondary: { label: "Book a demo", href: "/book-demo" },
    },
  ],
};
