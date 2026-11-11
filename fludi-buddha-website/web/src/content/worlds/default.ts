import type { World } from "./types";

// Copy: docs/marketing-docs/website/copy-default.md
export const DEFAULT_WORLD: World = {
  id: "default",
  path: "/",
  name: "General",
  audience: "everyone",
  theme: "dark",
  meta: {
    title: "FluidBuddha — your website, answering every visitor",
    description:
      "FluidBuddha lets your website answer visitors by voice or text, using only your own content. It shows prices and charts, takes people to the right page and books the meeting.",
  },
  nav: [
    { label: "Product", href: "/product" },
    { label: "Solutions", href: "#who" },
    { label: "Pricing", href: "/pricing" },
    { label: "Developers", href: "/developers" },
  ],
  cta: { label: "Start free", href: "/demo#start" },
  hero: {
    layout: "bleed",
    eyebrow: "FluidBuddha",
    title: ["Your website can", "answer every visitor."],
    sub: "It answers by voice or text, using only what your site says. It shows prices and charts, takes people to the right page and books the meeting.",
    primary: { label: "Start free", href: "/demo#start" },
    secondary: { label: "Watch how it works", href: "#film" },
    still: "D3",
    tone: "dark",
    selector: true,
  },
  film: {
    // 8 shots, 58 s, rendered at 1080p and delivered at 12 frames a second as 720p and 480p WebP (film/shots_default.py).
    kind: "frames",
    layout: "bleed",
    frames: { dir: "/film/default/720", mobileDir: "/film/default/480", ext: "webp", count: 700, pxPerFrame: 16, poster: "/film/stills/D0.jpg", heroAt: [0, 0.05], heroFocus: 0.6, portraitTop: 0.58 },
    chapters: [
      { id: "question", label: "A question", at: [0.07, 0.115], eyebrow: "A visitor arrives", title: ["Someone has", "a question."], body: "They want to know what it costs for their team.", still: "D1", tone: "dark" },
      { id: "talks", label: "It talks", at: [0.15, 0.245], eyebrow: "It talks", title: ["It answers out loud,", "from your own pages."], body: "Every answer shows where it came from. If the answer is not on your site, it says so.", still: "D3", tone: "dark" },
      { id: "shows", label: "It shows", at: [0.285, 0.38], eyebrow: "It shows", title: ["It draws", "charts, tables and calculators", "while it talks."], body: "The visitor can move a slider and see the price change.", still: "D4", tone: "dark" },
      { id: "there", label: "The right page", at: [0.42, 0.52], eyebrow: "It takes them there", title: ["It opens", "the right page."], body: "It scrolls to the part that answers the question and highlights it.", still: "D4", tone: "dark" },
      { id: "books", label: "It books", at: [0.555, 0.622], eyebrow: "It books", title: ["It books the meeting", "after the visitor says yes."], body: "Nothing happens without their confirmation. Your team gets the lead, with what was asked.", still: "D7", tone: "dark" },
      { id: "fits", label: "It fits", at: [0.66, 0.76], eyebrow: "It fits each visitor", title: ["The page", "changes to fit the kind of visitor."], body: "It is built only from parts you approved. Prices come from your own systems.", still: "D7", tone: "dark" },
      { id: "you", label: "For you", at: [0.795, 0.865], eyebrow: "Try it now", title: ["Tell us what you do.", "This site will change for you."], selector: true, still: "D7", tone: "dark" },
      { id: "measure", label: "Measure it", at: [0.905, 1], eyebrow: "Measure it", title: ["One visitor in ten never sees it.", "The difference is your extra sales."], body: "The product runs this test for you.", note: "Example chart.", still: "D7", tone: "dark" },
    ],
  },
  hi: {
    title: "आपकी वेबसाइट|हर विज़िटर को जवाब दे सकती है।",
    sub: "यह बोलकर या लिखकर जवाब देती है, सिर्फ़ वही बताकर जो आपकी साइट पर है। यह क़ीमतें और चार्ट दिखाती है, सही पेज पर ले जाती है और मीटिंग बुक करती है।",
    cta: "मुफ़्त शुरू करें",
    secondary: "देखिए यह कैसे काम करता है",
    chapters: {
      question: "किसी के मन में|एक सवाल है।",
      talks: "यह बोलकर जवाब देती है,|आपके अपने पेजों से।",
      shows: "बोलते-बोलते यह|चार्ट, टेबल और कैलकुलेटर|बनाकर दिखाती है।",
      there: "यह|सही पेज|खोल देती है।",
      books: "विज़िटर के|हाँ कहने के बाद|ही मीटिंग बुक होती है।",
      fits: "पेज|हर विज़िटर के हिसाब से|बदलता है।",
      measure: "दस में से एक विज़िटर इसे नहीं देखता।|यही फ़र्क़ आपकी अतिरिक्त बिक्री है।",
    },
    sections: { talk: { title: "इसके बारे में पढ़िए नहीं।|इससे बात कीजिए।" } },
  },
  sections: [
    {
      kind: "talk", id: "talk", eyebrow: "Talk to it", title: ["Don\u2019t read about it.", "Talk to it."],
      lead: "The live demo runs on FluidBuddha. Ask it anything, out loud or by typing.",
      questions: ["How much does it cost?", "Show me how it works", "क्या ये हिंदी में बात करता है?", "Book a demo"],
      cta: { label: "Open the live demo", href: "/demo" },
    },
    {
      kind: "cards", id: "does", eyebrow: "What it does", title: ["One conversation", "does all of this."], cols: 3, overFilm: "D3",
      items: [
        { n: "01", title: "It talks", body: "Visitors ask by voice or text. It starts replying straight away, in English or Hindi." },
        { n: "02", title: "It shows", body: "It draws diagrams, charts, comparison tables and calculators as it explains." },
        { n: "03", title: "It takes them there", body: "It opens the right page, scrolls to the right section and highlights it." },
        { n: "04", title: "It uses only your content", body: "Every answer comes from your website, with a link to the source." },
        { n: "05", title: "It books and sells", body: "Meetings, quotes, trials and payment links, each confirmed by the visitor first." },
        { n: "06", title: "It proves its value", body: "A built-in test compares visitors who had it with visitors who did not." },
      ],
    },
    {
      kind: "cards", id: "fits-each", eyebrow: "It fits each visitor", title: ["Your pages change", "for each visitor."], cols: 3,
      lead: "FluidBuddha builds these versions from the components you have approved. It never writes its own HTML, and prices come from your systems, not from the AI.",
      items: [
        { n: "A", title: "Came for pricing", body: "A visitor who came from a pricing ad sees pricing first." },
        { n: "B", title: "Came for security", body: "A visitor who came for security sees security first." },
        { n: "C", title: "Came back a second time", body: "A returning visitor picks up where they left off, if they chose to be remembered." },
      ],
      note: "Your own page shows until the fitted version is ready. Search engines always see your own page.",
    },
    {
      kind: "doors", id: "who", eyebrow: "Who it is for", title: ["Pick the one", "closest to you."], lead: "This site changes its look, its film and its words for you.",
      doors: [
        { to: "saas", eyebrow: "B2B SaaS", title: "Buyers on your pricing page at 11 pm, answered.", still: "D4" },
        { to: "education", eyebrow: "Education", title: "Students answered at night, in Hindi or English.", still: "E6" },
        { to: "enterprise", eyebrow: "Banks, insurers and fintechs", title: "AI on your website, inside your rules.", still: "D1" },
      ],
      also: [
        { label: "Real estate", href: "/industries/real-estate" }, { label: "Healthcare", href: "/industries/healthcare" },
        { label: "Marketing", href: "/solutions/marketing" }, { label: "Agencies", href: "/industries/agencies" },
      ],
    },
    {
      kind: "cards", id: "start", eyebrow: "How to start", title: ["Three steps.", "It can be answering the same day."], cols: 3, steps: true,
      items: [
        { n: "1", title: "Add one line of code", body: "One script tag on your website. Plugins exist for WordPress, Shopify and Google Tag Manager." },
        { n: "2", title: "It reads your site", body: "It learns your pages, your prices and your brand colours." },
        { n: "3", title: "It starts answering", body: "By voice or text, in English or Hindi, day and night." },
      ],
    },
    { kind: "plans", id: "pricing", eyebrow: "Pricing", title: ["Pay for conversations,", "not seats."], link: { label: "See full pricing", href: "/pricing" } },
    {
      kind: "callout", id: "ourselves", eyebrow: "We use it ourselves",
      title: "Launching on our own sites first.",
      note: "We are putting FluidBuddha on our own websites before we ask you to put it on yours. This page will list each one as it goes live.",
    },
    {
      kind: "list", id: "limits", eyebrow: "What it does not do", title: ["Three things", "to know first."],
      items: [
        "It speaks English and Hindi only.",
        "It works on websites. It is not a WhatsApp, phone or app agent.",
        "It answers from your content with sources. That is a strong guardrail, not a guarantee.",
      ],
    },
    {
      kind: "faq", id: "faq", eyebrow: "Questions", title: ["What people", "ask first."],
      items: [
        { q: "Will it make things up?", a: "It answers from your website and shows its sources. When it cannot find an answer, it says so and offers to connect the visitor with your team." },
        { q: "How long does setup take?", a: "You add one line of code and it reads your site. It can be answering the same day." },
        { q: "Does it slow my site down?", a: "The main script is about 38.6 kB. Other parts load only when they are used." },
        { q: "Which languages?", a: "English and Hindi." },
        { q: "What does it cost?", a: "Free covers 100 conversations a month. Growth is ₹33,000 a month for 2,000 conversations." },
        { q: "Can I see whether it works?", a: "Yes. It can hold back one visitor in ten and compare the two groups on your own goal." },
      ],
    },
    {
      kind: "close", id: "close", title: ["Put it on one page", "and see."], lead: "Start free with 100 conversations a month.",
      primary: { label: "Start free", href: "/demo#start" }, secondary: { label: "Book a demo", href: "/book-demo" },
    },
  ],
};
