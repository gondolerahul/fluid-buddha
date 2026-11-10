// Home film chapters (docs/marketing-docs/WebsiteConcept.md §7.1 and §8).
// Frame ranges are positions in the stitched draft film (24 fps, 3,182 frames).

export const FILM = {
  frames: 3182,
  fps: 24,
  src: (i: number) => `/film/home/16x9/f${String(i + 1).padStart(5, "0")}.jpg`,
  night: [410, 2250] as [number, number], // ink theme between these frames
  pxPerFrame: 9,                          // scroll distance per frame
};

export type Chapter = {
  id: string;
  label: string;
  from: number;
  to: number;
  eyebrow: string;
  title: [string, string];
  body?: string;
  lines?: string[];
  note?: string;
  kind?: "hero" | "demo" | "start";
};

export const CHAPTERS: Chapter[] = [
  { id: "hero", label: "Your website", from: 0, to: 140, kind: "hero",
    eyebrow: "FluidBuddha · your website, answering",
    title: ["Your website,", "answering every visitor."],
    body: "It listens, speaks, shows and books, using only what your website says." },
  { id: "liquid", label: "Liquid", from: 190, to: 335,
    eyebrow: "Generative interface", title: ["Liquid until", "you ask."],
    body: "Nothing is pre-drawn. When a visitor asks, your website pours itself into the answer." },
  { id: "question", label: "9:40 PM", from: 400, to: 560,
    eyebrow: "9:40 PM", title: ["Meera has two questions.", "Your website has no answers."],
    body: "She runs sales at a 40-person company and is comparing CRMs tonight. Does it work with Tally? What would 25 users cost?" },
  { id: "before", label: "Before", from: 580, to: 676,
    eyebrow: "Without FluidBuddha", title: ["Most websites go quiet", "the moment someone has a question."],
    body: "“Contact sales for pricing.” The next call is on Thursday. She leaves for a competitor." },
  { id: "after", label: "After", from: 700, to: 821,
    eyebrow: "With FluidBuddha", title: ["Same website. Same visitor.", "Different result."] },
  { id: "answer", label: "The answer", from: 900, to: 1062,
    eyebrow: "She asks out loud", title: ["It answers in a second,", "from your price list."],
    lines: ["₹37,475 a month for 25 users", "How the Tally sync works, drawn as she listens"],
    note: "Northwind CRM · example figures, illustrative" },
  { id: "page", label: "Right page", from: 1100, to: 1255,
    eyebrow: "It acts on the page", title: ["It takes her to", "your security page."],
    body: "Data stored in India. Exactly what she needed to see." },
  { id: "booked", label: "Booked", from: 1300, to: 1496,
    eyebrow: "She says yes", title: ["Demo booked for 10 AM.", "Your team has the lead."],
    body: "Nothing runs until the visitor confirms. The hot lead lands in Slack." },
  { id: "happened", label: "What happened", from: 1520, to: 1689,
    eyebrow: "What just happened", title: ["One conversation", "did it all."],
    lines: ["It listened", "It answered from your website", "It drew the integration", "It took her to the right page", "It booked the demo", "Your team got the lead"] },
  { id: "talk", label: "Talk to it", from: 1695, to: 1834, kind: "demo",
    eyebrow: "Live demo", title: ["Don't read about it.", "Talk to it."],
    body: "This page runs on FluidBuddha. Ask it anything." },
  { id: "grounded", label: "Only your site", from: 1900, to: 2027,
    eyebrow: "Grounded in your content", title: ["It only answers", "from your website."],
    body: "Every answer comes from your pages, with a link to the source." },
  { id: "honest", label: "Honest", from: 2040, to: 2172,
    eyebrow: "When it doesn't know", title: ["It can't shine", "with what isn't there."],
    body: "If something isn't on your site, it says so, and offers your team." },
  { id: "morning", label: "Morning", from: 2200, to: 2365,
    eyebrow: "8:00 AM", title: ["You wake up to customers,", "not missed chances."],
    lines: ["The hot lead is already in Slack", "Last night's summary is in your inbox", "You know what customers asked"] },
  { id: "install", label: "One line", from: 2420, to: 2606,
    eyebrow: "How it works", title: ["One line of code.", "Live this afternoon."],
    lines: ["Add one line to your site", "It reads your website", "It starts answering, day and night"] },
  { id: "proof", label: "Proof", from: 2650, to: 2799,
    eyebrow: "Measure it yourself", title: ["See the extra sales,", "measured properly."],
    body: "One in ten visitors never meets it. The difference is your lift, safe to check every day.",
    note: "Example chart · illustrative" },
  { id: "start", label: "Start", from: 2880, to: 3181, kind: "start",
    eyebrow: "Free plan · 100 conversations", title: ["One drop,", "on your site."],
    body: "Start free. Pay for conversations, not seats." },
];

export const DEMO_QUESTIONS = [
  { label: "How much does it cost?", ask: "How much does it cost?" },
  { label: "Show me how it works", ask: "Show me how it works" },
  { label: "क्या ये हिंदी में बात करता है?", ask: "क्या ये हिंदी में बात करता है?", hi: true },
  { label: "Who will win the IPL this year?", ask: "Who will win the IPL this year?" },
  { label: "Book a demo", ask: "Book a demo" },
];

export const CAPABILITIES = [
  { topic: "price", title: "It talks and shows", body: "Answers out loud, with a pricing table." },
  { topic: "how", title: "It explains your product", body: "In plain words, from your pages." },
  { topic: "hindi", title: "English and Hindi", body: "Even if your site is English only." },
  { topic: "honest", title: "It doesn't guess", body: "If it isn't on your site, it says so." },
  { topic: "book", title: "It books meetings", body: "Only after the visitor says yes." },
];

export const FOR_YOU = [
  { title: "Sales", body: "Turn tonight's visitors into tomorrow's pipeline.", href: "/solutions/sales", poster: "K8" },
  { title: "Marketing", body: "Every campaign, a page that talks back.", href: "/solutions/marketing", poster: "K14" },
  { title: "SaaS and B2B", body: "The technical buyer, answered at 11 PM.", href: "/industries/saas", poster: "K6" },
  { title: "Retail and services", body: "Hinglish questions, Hindi answers.", href: "/industries/retail-services", poster: "K3" },
  { title: "Education", body: "An admissions counsellor at midnight.", href: "/industries/education", poster: "K15" },
  { title: "Healthcare", body: "A front desk that never gives medical advice.", href: "/industries/healthcare", poster: "K13" },
];

// ---------------------------------------------------------------- Hindi (/hi)
export const CHAPTERS_HI: Chapter[] = [
  { id: "hero", label: "आपकी वेबसाइट", from: 0, to: 140, kind: "hero",
    eyebrow: "FluidBuddha · आपकी वेबसाइट, जवाब देती हुई",
    title: ["आपकी वेबसाइट,", "हर विज़िटर को जवाब देती है।"],
    body: "यह सुनती है, बोलती है, दिखाती है और बुक करती है, सिर्फ़ वही बताकर जो आपकी वेबसाइट पर लिखा है।" },
  { id: "liquid", label: "तरल", from: 190, to: 335,
    eyebrow: "जेनरेटिव इंटरफ़ेस", title: ["जब तक आप न पूछें,", "सब तरल है।"],
    body: "कुछ भी पहले से बना नहीं है। विज़िटर पूछता है, और आपकी वेबसाइट जवाब का रूप ले लेती है।" },
  { id: "question", label: "रात 9:40", from: 400, to: 560,
    eyebrow: "रात 9:40", title: ["मीरा के दो सवाल हैं।", "आपकी वेबसाइट के पास कोई जवाब नहीं।"],
    body: "वह 40 लोगों की कंपनी में सेल्स संभालती है और आज रात CRM की तुलना कर रही है। क्या यह Tally के साथ काम करता है? 25 यूज़र्स का खर्च कितना होगा?" },
  { id: "before", label: "पहले", from: 580, to: 676,
    eyebrow: "FluidBuddha के बिना", title: ["ज़्यादातर वेबसाइटें चुप हो जाती हैं,", "जैसे ही किसी के मन में सवाल आता है।"],
    body: "“कीमत के लिए सेल्स से संपर्क करें।” अगली कॉल गुरुवार को है। वह किसी और के पास चली जाती है।" },
  { id: "after", label: "बाद में", from: 700, to: 821,
    eyebrow: "FluidBuddha के साथ", title: ["वही वेबसाइट। वही विज़िटर।", "अलग नतीजा।"] },
  { id: "answer", label: "जवाब", from: 900, to: 1062,
    eyebrow: "वह बोलकर पूछती है", title: ["यह एक सेकंड में जवाब देती है,", "आपकी प्राइस लिस्ट से।"],
    lines: ["25 यूज़र्स के लिए ₹37,475 महीना", "Tally सिंक कैसे काम करता है, बोलते-बोलते बनाकर दिखाया"],
    note: "Northwind CRM · उदाहरण के आंकड़े" },
  { id: "page", label: "सही पेज", from: 1100, to: 1255,
    eyebrow: "यह पेज पर काम करती है", title: ["यह उसे ले जाती है", "आपके सिक्योरिटी पेज पर।"],
    body: "डेटा भारत में रखा जाता है। ठीक वही, जो उसे देखना था।" },
  { id: "booked", label: "बुक", from: 1300, to: 1496,
    eyebrow: "वह हाँ कहती है", title: ["सुबह 10 बजे का डेमो बुक।", "लीड आपकी टीम के पास।"],
    body: "विज़िटर की पुष्टि के बिना कुछ नहीं होता। हॉट लीड सीधे Slack में पहुँचती है।" },
  { id: "happened", label: "क्या हुआ", from: 1520, to: 1689,
    eyebrow: "अभी क्या हुआ", title: ["एक बातचीत ने", "सब कर दिया।"],
    lines: ["उसने सुना", "आपकी वेबसाइट से जवाब दिया", "इंटीग्रेशन बनाकर दिखाया", "सही पेज पर ले गई", "डेमो बुक किया", "आपकी टीम को लीड मिली"] },
  { id: "talk", label: "बात कीजिए", from: 1695, to: 1834, kind: "demo",
    eyebrow: "लाइव डेमो", title: ["इसके बारे में पढ़िए नहीं।", "इससे बात कीजिए।"],
    body: "यह वेबसाइट FluidBuddha पर चलती है। कुछ भी पूछिए।" },
  { id: "grounded", label: "सिर्फ़ आपकी साइट", from: 1900, to: 2027,
    eyebrow: "आपके कंटेंट पर आधारित", title: ["यह सिर्फ़ आपकी वेबसाइट से", "जवाब देती है।"],
    body: "हर जवाब आपके पेजों से आता है, स्रोत के लिंक के साथ।" },
  { id: "honest", label: "ईमानदार", from: 2040, to: 2172,
    eyebrow: "जब इसे पता न हो", title: ["जो वहाँ नहीं है,", "उससे यह चमक नहीं सकती।"],
    body: "अगर कुछ आपकी वेबसाइट पर नहीं है, तो यह साफ़ कहती है, और आपकी टीम से जोड़ती है।" },
  { id: "morning", label: "सुबह", from: 2200, to: 2365,
    eyebrow: "सुबह 8 बजे", title: ["आप ग्राहकों के साथ जागते हैं,", "छूटे मौक़ों के साथ नहीं।"],
    lines: ["हॉट लीड पहले से Slack में है", "रात की रिपोर्ट आपके इनबॉक्स में है", "आपको पता है ग्राहकों ने क्या पूछा"] },
  { id: "install", label: "एक लाइन", from: 2420, to: 2606,
    eyebrow: "यह कैसे काम करता है", title: ["कोड की एक लाइन।", "आज दोपहर से लाइव।"],
    lines: ["अपनी साइट पर एक लाइन जोड़िए", "यह आपकी वेबसाइट पढ़ता है", "यह दिन-रात जवाब देने लगता है"] },
  { id: "proof", label: "प्रमाण", from: 2650, to: 2799,
    eyebrow: "ख़ुद मापिए", title: ["अतिरिक्त बिक्री देखिए,", "सही तरीक़े से मापी हुई।"],
    body: "दस में से एक विज़िटर इससे नहीं मिलता। यही फ़र्क़ आपकी बढ़त है, जिसे आप रोज़ देख सकते हैं।",
    note: "उदाहरण चार्ट" },
  { id: "start", label: "शुरू करें", from: 2880, to: 3181, kind: "start",
    eyebrow: "फ़्री प्लान · 100 बातचीत", title: ["एक बूंद,", "आपकी साइट पर।"],
    body: "मुफ़्त शुरू करें। भुगतान बातचीत के हिसाब से, सीटों के हिसाब से नहीं।" },
];

export const DEMO_QUESTIONS_HI = [
  { label: "इसकी कीमत क्या है?", ask: "इसकी कीमत क्या है?", hi: true },
  { label: "यह कैसे काम करता है?", ask: "यह कैसे काम करता है?", hi: true },
  { label: "क्या ये हिंदी में बात करता है?", ask: "क्या ये हिंदी में बात करता है?", hi: true },
  { label: "आईपीएल कौन जीतेगा?", ask: "आईपीएल कौन जीतेगा?", hi: true },
  { label: "डेमो बुक करें", ask: "डेमो बुक करें", hi: true },
];

export const CAPABILITIES_HI = [
  { topic: "price", title: "यह बोलती है और दिखाती है", body: "बोलकर जवाब, प्राइस टेबल के साथ।" },
  { topic: "how", title: "आपका प्रोडक्ट समझाती है", body: "सरल शब्दों में, आपके पेजों से।" },
  { topic: "hindi", title: "हिंदी और अंग्रेज़ी", body: "भले ही साइट सिर्फ़ अंग्रेज़ी में हो।" },
  { topic: "honest", title: "यह अंदाज़ा नहीं लगाती", body: "जो साइट पर नहीं, वह साफ़ बताती है।" },
  { topic: "book", title: "मीटिंग बुक करती है", body: "विज़िटर के हाँ कहने के बाद ही।" },
];
