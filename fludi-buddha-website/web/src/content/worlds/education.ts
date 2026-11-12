import type { World } from "./types";

// Copy: docs/marketing-docs/website/copy-education.md, tightened in the redesign
// (docs/marketing-docs/website/audit-2026-11-11.md §4).
// World 2, "Lamp to morning": paper (60), ink (30), gold (10). The photographed film runs from 11 pm
// to 9 am; the page is the morning, and what belongs to the night sits on ink.
export const EDUCATION_WORLD: World = {
  id: "education",
  path: "/for/education",
  name: "Education",
  audience: "universities and edtech",
  meta: {
    title: "FluidBuddha for universities and edtech: admissions answers at night, in Hindi or English",
    description:
      "Students ask at night, in Hindi or English. Your website answers from your own fee and programme pages, takes the application fee and gives them a summary for their parents.",
  },
  hero: {
    title: ["Your counsellors go home at six.", "Your website can keep answering."],
    roles: [
      { id: "admissions", label: "Admissions", sub: "Every enquiry gets a reply at once, in Hindi or English, from your own fee and programme pages.", primary: "Try it in Hindi", primaryHref: "#hindi", secondary: "See what a counsellor receives", secondaryHref: "#counsellor" },
      { id: "leadership", label: "Leadership", sub: "More of the students who already found you finish the application. Student details are hidden before the AI sees them.", primary: "Read about privacy", primaryHref: "#privacy", secondary: "See an example return", secondaryHref: "#return" },
      { id: "marketing", label: "Marketing", sub: "See what prospects ask that your site does not answer. It works on WordPress.", primary: "Try it in Hindi", primaryHref: "#hindi", secondary: "See what parents see", secondaryHref: "#parents" },
      { id: "counselling", label: "Counselling", sub: "You start each call knowing what the student asked.", primary: "See a lead summary", primaryHref: "#counsellor", secondary: "Try it in Hindi", secondaryHref: "#hindi" },
    ],
  },
  film: {
    // Rendered film with people (film/shots_education.py), from the 1080p render.
    kind: "frames",
    frames: { dir: "/film/education/720", mobileDir: "/film/education/480", ext: "webp", count: 561, pxPerFrame: 18, poster: "/film/stills/E1.jpg", heroAt: [0, 0.035], heroFocus: 0.77 },
    chapters: [
      { id: "night", label: "11 pm", at: [0.046, 0.118], focus: 0.8, title: ["A student is on your website.", "Your counsellors are at home."], body: "Students research after class, in the evening and at night." },
      { id: "in-hindi", label: "In Hindi", at: [0.135, 0.2], focus: 0.82, quote: "“फ़ीस कितनी है?”", title: ["It answers", "in Hindi."], body: "Your pages can stay in English. No translation project is needed." },
      { id: "compares", label: "It compares", at: [0.232, 0.342], focus: 0.62, title: ["It puts programmes and fees", "side by side."], body: "The student moves a slider to see what a scholarship changes.", note: "Example figures." },
      { id: "guides", label: "It guides", at: [0.357, 0.492], focus: 0.62, title: ["It walks them through", "your programmes."], body: "A short spoken tour of the pages that matter." },
      { id: "fee", label: "The fee", at: [0.506, 0.602], focus: 0.62, title: ["They say “haan”.", "It sends the application-fee link."], body: "The amount comes from your fee list, never from the AI. Nothing is sent until the student confirms." },
      { id: "family", label: "The family", at: [0.627, 0.731], focus: 0.68, title: ["The student sends", "a summary to their parents."], body: "One page with the answers, the fee table and the sources." },
      { id: "morning", label: "9 am", at: [0.757, 0.859], focus: 0.58, title: ["Your counsellor has the lead", "and knows what was asked."], body: "The first call starts where the website stopped." },
      { id: "timing", label: "Timing", at: [0.886, 1], focus: 0.84, title: ["Start", "before admission season."], body: "A trial that begins before applications open has time to show a result." },
    ],
  },
  hi: {
    title: "आपके काउंसलर छह बजे घर चले जाते हैं।|आपकी वेबसाइट जवाब देती रह सकती है।",
    sub: "हर पूछताछ का तुरंत जवाब, हिंदी या अंग्रेज़ी में, आपके अपने फ़ीस और प्रोग्राम पेजों से।",
    chapters: {
      night: "रात 11 बजे। एक छात्र आपकी वेबसाइट पर है।|आपके काउंसलर घर पर हैं।",
      "in-hindi": "|यह हिंदी में जवाब देती है।",
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
      // the signature moment: an English fee page, answered in Hindi, with the source sentence lit
      kind: "hindi-answer", id: "hindi", tone: "second",
      title: ["Your English page,", "answered in Hindi."],
      lead: "Ask the way a student would. The answer comes in their language, and the line it came from lights up on your English page.",
    },
    {
      kind: "visit", id: "visit", title: ["What a student can do", "in one visit."],
      steps: [
        { title: "Ask", body: "By voice or by typing, in Hindi or English. No form first.", media: "asks" },
        { title: "Compare", body: "Fees, eligibility and programmes in one table.", media: "compare" },
        { title: "Pay the application fee", body: "Through a payment link on your own Razorpay account.", media: "confirm" },
        { title: "Share with family", body: "A summary page they can forward.", media: "family" },
      ],
    },
    {
      kind: "phone", id: "parents", title: ["The page the family", "judges you by."],
      lead: "A plain summary that opens on any phone, even with scripts switched off.",
      ticks: ["What was asked, and the answer", "The fee table", "Where each answer came from", "How to apply"],
    },
    {
      kind: "counsellor", id: "counsellor", title: ["9 am. A lead", "with its story."], media: "counsellor",
      lead: "Your counsellor starts the first call where the website stopped.",
      items: ["Name and contact", "Course and city", "What they asked", "Score, with reasons", "Whether the family opened the summary"],
      note: "Hot leads can alert your team in Slack.",
    },
    {
      kind: "pair", id: "fees", tone: "second",
      left: { title: "Fee answers come from your pages.", items: [
        "Fee answers quote your website and show the source.",
        "You can fix an approved fee answer so the same words are used every time.",
        "For payments, the amount can only come from the fee list you enter.",
      ], note: "These are controls you set. Review them before each admission season." },
      right: { id: "privacy", title: "What happens to student data.", items: [
        "Emails, phone numbers and card numbers are hidden before the AI sees them.",
        "The microphone stays off until the student agrees. “Type instead” always works.",
        "You choose how long conversations are kept.",
        "You can delete one student’s data by their email address.",
        "Names and street addresses are not hidden automatically.",
        "The product does not ask for age. Please review your policy on minors’ data with your own legal adviser.",
      ] },
    },
    {
      kind: "return", id: "return", title: ["One extra enrolment", "pays for months."],
      body: "One extra enrolment at a first-year fee of ₹2,00,000 would cover the Growth plan (₹33,000 a month) for about six months.",
      note: "This is an example, not a result. Measure your own with the built-in test on your “application complete” page.",
    },
    {
      kind: "limits", id: "limits", title: ["Three limits", "to know first."],
      items: [
        "English and Hindi only. Tamil, Telugu, Marathi and other languages are not supported yet.",
        "It works on your website. It does not run on WhatsApp.",
        "It does not replace counsellors. It gives them students who are ready.",
      ],
    },
    {
      kind: "faq", id: "faq", title: ["What each team", "asks first."], ask: "MBA की फ़ीस कितनी है?",
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
      kind: "close", id: "close", tone: "gold", title: ["Let your website answer", "tonight’s enquiries."],
      lead: "Start before admission season. A trial that begins before applications open has time to show a result.",
      primary: { label: "Start free", href: "/demo#start" }, secondary: { label: "Book a demo", href: "/book-demo" },
    },
  ],
};
