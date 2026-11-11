import type { World } from "./types";

// Copy: docs/marketing-docs/website/copy-education.md
export const EDUCATION_WORLD: World = {
  id: "education",
  path: "/for/education",
  name: "Education",
  audience: "universities and edtech",
  theme: "light",
  meta: {
    title: "FluidBuddha for universities and edtech — admissions answers at night, in Hindi or English",
    description:
      "Students ask at night, in Hindi or English. Your website answers from your own fee and programme pages, takes the application fee and gives them a summary for their parents.",
  },
  nav: [
    { label: "How it works", href: "/product" },
    { label: "Hindi", href: "#hindi" },
    { label: "Pricing", href: "/pricing" },
    { label: "Privacy", href: "/trust" },
  ],
  cta: { label: "See it in Hindi", href: "#hindi" },
  hero: {
    layout: "bleed",
    eyebrow: "For universities and edtech · 11 pm",
    title: ["Your counsellors go home at six.", "Your website can keep answering."],
    still: "E1",
    tone: "dark",
    langSwitch: true,
    roles: [
      { id: "admissions", label: "Admissions", sub: "Every enquiry gets a reply at once, in Hindi or English, from your own fee and programme pages.", primary: "See it in Hindi", secondary: "See what a counsellor receives" },
      { id: "leadership", label: "Leadership", sub: "More of the students who already found you finish the application. Student details are hidden before the AI sees them.", primary: "Read about privacy", secondary: "See an example return" },
      { id: "marketing", label: "Marketing", sub: "See what prospects ask that your site does not answer. It works on WordPress.", primary: "See the weekly report", secondary: "See it in Hindi" },
      { id: "counselling", label: "Counselling", sub: "You start each call knowing what the student asked.", primary: "See a lead summary", secondary: "See it in Hindi" },
    ],
  },
  film: {
    // Rendered film with people (film/shots_education.py), from the 1080p render.
    kind: "frames",
    layout: "bleed",
    frames: { dir: "/film/education/720", mobileDir: "/film/education/480", ext: "webp", count: 561, pxPerFrame: 18, poster: "/film/stills/E1.jpg", heroAt: [0, 0.035], heroFocus: 0.77, portraitTop: 0.6 },
    chapters: [
      { id: "night", label: "11 pm", at: [0.046, 0.118], focus: 0.8, tone: "dark", eyebrow: "11 pm", title: ["A student is on your website.", "Your counsellors are at home."], body: "Students research after class, in the evening and at night." },
      { id: "hindi", label: "In Hindi", at: [0.135, 0.2], focus: 0.82, tone: "dark", eyebrow: "They ask in Hindi", quote: "\u201c\u092b\u093c\u0940\u0938 \u0915\u093f\u0924\u0928\u0940 \u0939\u0948?\u201d", title: ["It answers", "in Hindi."], body: "Your pages can stay in English. No translation project is needed." },
      { id: "compares", label: "It compares", at: [0.232, 0.342], focus: 0.62, tone: "dark", eyebrow: "It compares", title: ["It puts programmes and fees", "side by side."], body: "The student moves a slider to see what a scholarship changes.", note: "Example figures." },
      { id: "guides", label: "It guides", at: [0.357, 0.492], focus: 0.62, tone: "dark", eyebrow: "It guides", title: ["It walks them through", "your programmes."], body: "A short spoken tour of the pages that matter." },
      { id: "fee", label: "The fee", at: [0.506, 0.602], focus: 0.62, tone: "dark", eyebrow: "It takes the fee", title: ["They say \u201chaan\u201d.", "It sends the application-fee link."], body: "The amount comes from your fee list, never from the AI. Nothing is sent until the student confirms." },
      { id: "family", label: "The family", at: [0.627, 0.731], focus: 0.68, eyebrow: "The family decides", title: ["The student sends", "a summary to their parents."], body: "One page with the answers, the fee table and the sources." },
      { id: "morning", label: "9 am", at: [0.757, 0.859], focus: 0.58, eyebrow: "9 am", title: ["Your counsellor has the lead", "and knows what was asked."], body: "The first call starts where the website stopped." },
      { id: "timing", label: "Timing", at: [0.886, 1], focus: 0.84, eyebrow: "Timing", title: ["Start", "before admission season."], body: "A trial that begins before applications open has time to show a result." },
    ],
  },
  hi: {
    title: "आपके काउंसलर छह बजे घर चले जाते हैं।|आपकी वेबसाइट जवाब देती रह सकती है।",
    sub: "हर पूछताछ का तुरंत जवाब, हिंदी या अंग्रेज़ी में, आपके अपने फ़ीस और प्रोग्राम पेजों से।",
    cta: "हिंदी में देखिए",
    chapters: {
      night: "रात 11 बजे। एक छात्र आपकी वेबसाइट पर है।|आपके काउंसलर घर पर हैं।",
      hindi: "|यह हिंदी में जवाब देती है।",
      compares: "यह प्रोग्राम और फ़ीस|साथ-साथ रखकर|दिखाती है।",
      fee: "छात्र कहता है “हाँ”।|यह आवेदन शुल्क का लिंक भेज देती है।",
      family: "छात्र|अपने माता-पिता को|पूरा सार भेज देता है।",
      morning: "सुबह 9 बजे। आपके काउंसलर के पास लीड है,|और यह भी कि क्या पूछा गया था।",
    },
    sections: {
      privacy: { items: {
        0: "ईमेल, फ़ोन नंबर और कार्ड नंबर AI तक पहुँचने से पहले छिपा दिए जाते हैं।",
        1: "जब तक छात्र हाँ न कहे, माइक्रोफ़ोन बंद रहता है।",
      } },
    },
  },
  sections: [
    {
      kind: "talk", id: "try", eyebrow: "Try it in Hindi", title: ["Ask it a question.", "In Hindi, if you like."],
      lead: "This demo answers about FluidBuddha. On your site it answers about your programmes.",
      questions: ["MBA \u0915\u0940 \u092b\u093c\u0940\u0938 \u0915\u093f\u0924\u0928\u0940 \u0939\u0948?", "Which programme suits me?", "Scholarship kaise milegi?", "How do I apply?"],
      cta: { label: "Talk to it", href: "/demo" },
    },
    {
      kind: "cards", id: "visit", eyebrow: "In one visit", title: ["What a student can do", "in one visit."], cols: 4, steps: true, dots: true,
      items: [
        { n: "1", title: "Ask", body: "By voice or by typing, in Hindi or English. No form first." },
        { n: "2", title: "Compare", body: "Fees, eligibility and programmes in one table." },
        { n: "3", title: "Pay the application fee", body: "Through a payment link on your own Razorpay account." },
        { n: "4", title: "Share with family", body: "A summary page they can forward." },
      ],
    },
    {
      kind: "phone", id: "parents", eyebrow: "What parents see", title: ["The page the family", "judges you by."],
      lead: "A plain summary that opens on any phone, even with scripts switched off.",
      ticks: ["What was asked, and the answer", "The fee table", "Where each answer came from", "How to apply"],
    },
    {
      kind: "list", id: "counsellor", eyebrow: "What your counsellor receives", title: ["A lead", "with its story."],
      items: ["Name and contact", "Course and city", "What they asked", "Score, with reasons", "Whether the family opened the summary"],
      note: "Hot leads can alert your team in Slack.",
    },
    {
      kind: "list", id: "fees", eyebrow: "Getting fees right", title: ["Fee answers come from your pages,", "not from guesswork."],
      items: [
        "Fee answers quote your website and show the source.",
        "You can fix an approved fee answer so the same words are used every time.",
        "For payments, the amount can only come from the fee list you enter.",
      ],
      note: "These are controls you set. Review them before each admission season.",
    },
    {
      kind: "list", id: "privacy", eyebrow: "Student privacy", title: ["What happens", "to student data."],
      items: [
        "Emails, phone numbers and card numbers are hidden before the AI sees them.",
        "The microphone stays off until the student agrees. \u201cType instead\u201d always works.",
        "You choose how long conversations are kept.",
        "You can delete one student\u2019s data by their email address.",
        "Names and street addresses are not hidden automatically.",
        "The product does not ask for age. Please review your policy on minors\u2019 data with your own legal adviser.",
      ],
    },
    {
      kind: "callout", id: "return", eyebrow: "An example return", big: "\u20b92,00,000", dots: true,
      title: "One extra enrolment at this first-year fee would cover the Growth plan (\u20b933,000 a month) for about six months.",
      note: "This is an example, not a result. Measure your own with the built-in test on your \u201capplication complete\u201d page.",
    },
    {
      kind: "list", id: "limits", eyebrow: "What it does not do", title: ["Three limits,", "stated plainly."],
      items: [
        "English and Hindi only. Tamil, Telugu, Marathi and other languages are not supported yet.",
        "It works on your website. It does not run on WhatsApp.",
        "It does not replace counsellors. It gives them students who are ready.",
      ],
    },
    {
      kind: "faq", id: "faq", eyebrow: "Questions", title: ["What each team", "asks first."],
      items: [
        { q: "Can it answer in Hindi if our site is in English?", a: "Yes. It understands Hindi and Hinglish, finds the answer in your English pages and replies in Hindi." },
        { q: "What if a student asks something that is not on our site?", a: "It says it does not know and offers to connect them with your team. You see these questions in a weekly list." },
        { q: "Is student data safe?", a: "Contact details are hidden before the AI sees them, the microphone needs consent, and you control retention and deletion. Names and addresses are not hidden automatically." },
        { q: "Does it work on WordPress?", a: "Yes, with a plugin." },
        { q: "Can we test it before admission season?", a: "Yes. Start on the Free plan and switch on the built-in test." },
        { q: "Will I be compared with the AI?", a: "No. It handles first questions at any hour so that your calls start with students who are ready." },
      ],
    },
    {
      kind: "close", id: "close", title: ["Let your website answer", "tonight\u2019s enquiries."], lead: "Students ask at night, in Hindi or English. Your own pages hold the answers.",
      primary: { label: "See it in Hindi", href: "#hindi" }, secondary: { label: "Book a demo", href: "/book-demo" },
    },
  ],
};
