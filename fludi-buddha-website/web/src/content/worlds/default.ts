import type { World } from "./types";

// Copy: docs/marketing-docs/website/copy-default.md, tightened in the redesign
// (docs/marketing-docs/website/audit-2026-11-11.md §4).
// World 0, "Amber glass": warm black, liquid-glass plates over the amber film, gold light.
export const DEFAULT_WORLD: World = {
  id: "default",
  path: "/",
  name: "General",
  audience: "everyone",
  theme: "dark",
  meta: {
    title: "FluidBuddha: your website, answering every visitor",
    description:
      "FluidBuddha lets your website answer visitors by voice or text, using only your own content. It shows prices and charts, takes people to the right page and books the meeting.",
  },
  hero: {
    title: ["Your website can", "answer every visitor."],
    sub: "It answers by voice or text from your own pages, shows prices and charts, and books the meeting.",
    primary: { label: "Start free", href: "/demo#start" },
    secondary: { label: "Watch how it works", href: "#question" },
    tone: "dark",
  },
  film: {
    // 8 shots, 58 s, rendered at 1080p and delivered at 12 frames a second as 720p and 480p WebP (film/shots_default.py).
    kind: "frames",
    frames: { dir: "/film/default/720", mobileDir: "/film/default/480", ext: "webp", count: 700, pxPerFrame: 16, poster: "/film/stills/D0.jpg", heroAt: [0, 0.05], heroFocus: 0.6, portraitTop: 0.58 },
    chapters: [
      { id: "question", label: "A question", at: [0.07, 0.115], title: ["Someone has", "a question."], body: "They want to know what it costs for their team.", tone: "dark" },
      { id: "talks", label: "It talks", at: [0.15, 0.245], title: ["It answers out loud,", "from your own pages."], body: "Every answer shows where it came from. If the answer is not on your site, it says so.", tone: "dark" },
      { id: "shows", label: "It shows", at: [0.285, 0.38], title: ["It draws", "charts, tables and calculators", "while it talks."], body: "The visitor can move a slider and see the price change.", tone: "dark" },
      { id: "there", label: "The right page", at: [0.42, 0.52], title: ["It opens", "the right page."], body: "It scrolls to the part that answers the question and highlights it.", tone: "dark" },
      { id: "books", label: "It books", at: [0.555, 0.622], title: ["It books the meeting", "after the visitor says yes."], body: "Nothing happens without their confirmation. Your team gets the lead, with what was asked.", tone: "dark" },
      { id: "fits", label: "It fits", at: [0.66, 0.76], title: ["The page", "changes to fit the kind of visitor."], body: "It is built only from parts you approved. Prices come from your own systems.", tone: "dark" },
      { id: "you", label: "For you", at: [0.795, 0.865], title: ["Tell us what you do.", "This site will change for you."], selector: true, tone: "dark" },
      { id: "measure", label: "Measure it", at: [0.905, 1], title: ["One visitor in ten never sees it.", "The difference is your extra sales."], body: "The product runs this test for you.", note: "Example chart.", tone: "dark" },
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
      // the signature moment: the page answers back, shows, points and changes
      kind: "ask", id: "talk", title: ["Don’t read about it.", "Talk to it."],
      lead: "This site runs on FluidBuddha. Pick a question and watch the page answer, show its source and point to it.",
      questions: [
        { label: "What would 3,000 conversations cost?" },
        { label: "Does it speak Hindi?" },
        { label: "Where do the answers come from?" },
        { label: "Can it book a meeting?" },
        { label: "Show me the version for banks" },
      ],
    },
    {
      kind: "bento", id: "does", title: ["One conversation", "does all of this."],
      items: [
        { key: "talks", title: "It talks", body: "Visitors ask by voice or text. It starts replying straight away, in English or Hindi." },
        { key: "shows", title: "It shows", body: "Diagrams, charts, comparison tables and calculators, drawn as it explains." },
        { key: "there", title: "It takes them there", body: "It opens the right page, scrolls to the right section and highlights it." },
        { key: "sources", title: "It uses only your content", body: "Every answer comes from your website, with a link to the source." },
        { key: "books", title: "It books and sells", body: "Meetings, quotes, trials and payment links, each confirmed by the visitor first." },
        { key: "proves", title: "It proves its value", body: "A built-in test compares visitors who had it with visitors who did not." },
      ],
    },
    {
      kind: "fit", id: "fits-each", title: ["Your pages change", "for the kind of visitor."],
      lead: "FluidBuddha arranges these versions from components you have approved. It never writes its own HTML, and prices come from your systems.",
      states: [
        { id: "pricing", label: "Came for pricing", line: "A visitor from a pricing ad sees pricing first.", order: ["pricing", "hero", "proof", "cta"] },
        { id: "security", label: "Came for security", line: "A visitor who came for security sees security first.", order: ["security", "hero", "pricing", "cta"] },
        { id: "back", label: "Came back", line: "A returning visitor picks up where they left off, if they chose to be remembered.", order: ["resume", "pricing", "security", "cta"] },
      ],
      note: "Your own page shows until the fitted version is ready. Search engines always see your own page.",
    },
    {
      kind: "doors", id: "who", title: ["Pick the one", "closest to you."], lead: "This site changes its look, its film and its words for you.",
      doors: [
        { to: "saas", label: "B2B SaaS", title: "Buyers on your pricing page at 11 pm, answered.", media: "shows" },
        { to: "education", label: "Universities and edtech", title: "Students answered at night, in Hindi or English.", media: "family" },
        { to: "enterprise", label: "Banks, insurers and fintechs", title: "AI on your website, inside your rules.", media: "there" },
      ],
      also: [
        { label: "Retail and services", href: "/industries/retail-services" }, { label: "Healthcare", href: "/industries/healthcare" },
        { label: "Real estate", href: "/industries/real-estate" }, { label: "Agencies", href: "/industries/agencies" },
        { label: "Marketing teams", href: "/solutions/marketing" },
      ],
    },
    {
      kind: "start", id: "start", title: ["It can be answering", "the same day."],
      steps: [
        { title: "Add one line of code", body: "One script tag on your website. Plugins exist for WordPress, Shopify and Google Tag Manager." },
        { title: "It reads your site", body: "It learns your pages, your prices and your brand colours." },
        { title: "It starts answering", body: "By voice or text, in English or Hindi, day and night." },
      ],
    },
    { kind: "plans", id: "pricing", title: ["Pay for conversations,", "not seats."], link: { label: "See full pricing", href: "/pricing" } },
    {
      kind: "limits", id: "limits", title: ["Three things", "to know first."],
      items: [
        "It speaks English and Hindi only.",
        "It works on websites. It is not a WhatsApp, phone or app agent.",
        "It answers from your content with sources. That is a strong guardrail, not a guarantee.",
      ],
      aside: { title: "Launching on our own sites first.", body: "We are putting FluidBuddha on our own websites before we ask you to put it on yours. This page will list each one, with a link, as it goes live." },
    },
    {
      kind: "faq", id: "faq", title: ["What people", "ask first."], ask: "Will it make things up?",
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
      kind: "close", id: "close", title: ["Put it on one page", "and see."], lead: "Start free with 100 conversations a month.", media: "three",
      primary: { label: "Start free", href: "/demo#start" }, secondary: { label: "Book a demo", href: "/book-demo" },
    },
  ],
};
