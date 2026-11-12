// The scripted preview answers this site gives until the live agent is connected (AgentLoader).
// Every answer is taken from this site's own pages and says where it came from, like the product.
// Shared by the corner launcher (Ask Pragya) and the default world's "Ask this page" stage.

import type { WorldId } from "@/content/worlds/types";

export type Topic = "price" | "calc" | "how" | "hindi" | "sources" | "book" | "security" | "integrations" | "banks" | "unknown";

export type Answer = {
  topic: Topic;
  text: string;
  hindi?: boolean;
  /** Where the answer came from: a page, and on the default world page a section to point at. */
  src?: { label: string; href: string; spot?: string };
  /** A visual drawn with the answer. */
  visual?: "plans" | "calc" | "confirm" | "flow";
  /** Something the page does after answering. */
  act?: { world: WorldId };
};

export const isHindi = (t: string) => /[ऀ-ॿ]/.test(t) || /\b(hindi|kya|kitna|kitni|batao|bataiye|haan|nahin|mein|hai|kaise)\b/i.test(t);

export function classify(t: string): Topic {
  const s = t.toLowerCase();
  if (/bank|insur|fintech|nbfc|enterprise version|for banks/.test(s)) return "banks";
  if (/\b\d[\d,]*\s*(conversations|chats)|3,?000|calculat/.test(s)) return "calc";
  if (/book|demo|meeting|call|schedule|appointment|बुक/.test(s)) return "book";
  if (/hindi|हिंदी|हिन्दी|language|bhasha|भाषा/.test(s)) return "hindi";
  if (/price|pric|cost|plan|₹|rupee|kitna|कितन|free|कीमत|क़ीमत/.test(s)) return "price";
  if (/source|come from|made up|make things up|hallucinat|grounded|where do the answers/.test(s)) return "sources";
  if (/secur|privacy|data|soc ?2|sso|gdpr|self.?host|सुरक्षा/.test(s)) return "security";
  if (/integrat|wordpress|shopify|webflow|framer|install|crm|slack|react|script/.test(s)) return "integrations";
  if (/how|work|what is|what does|explain|kaise|कैसे|क्या है/.test(s)) return "how";
  return "unknown";
}

export function answer(topic: Topic, hi = false): Answer {
  switch (topic) {
    case "price":
      return hi
        ? { topic, hindi: true, text: "आप बातचीत के हिसाब से भुगतान करते हैं। मुफ़्त प्लान में 100 बातचीत, और ग्रोथ ₹33,000 महीने में 2,000 बातचीत।", visual: "plans", src: { label: "Pricing", href: "/pricing", spot: "#pricing" } }
        : { topic, text: "You pay for conversations, not seats. Free covers 100 a month. Growth is ₹33,000 a month for 2,000, then ₹17 each.", visual: "plans", src: { label: "Pricing", href: "/pricing", spot: "#pricing" } };
    case "calc":
      return { topic, text: "For 3,000 conversations a month, Growth comes to ₹50,000: ₹33,000 for the first 2,000, and 1,000 more at ₹17. Move the slider to try your own number.", visual: "calc", src: { label: "Pricing", href: "/pricing", spot: "#pricing" } };
    case "how":
      return hi
        ? { topic, hindi: true, text: "आप अपनी वेबसाइट पर एक लाइन का कोड जोड़ते हैं। यह आपकी वेबसाइट पढ़ता है, और फिर आपके विज़िटर्स के सवालों का जवाब देता है, सिर्फ़ आपकी वेबसाइट से।", src: { label: "How it works", href: "/product", spot: "#start" } }
        : { topic, text: "You add one line of code. It reads your website, then answers visitors out loud or in text, shows them what they need and books the next step, using only what your site says.", visual: "flow", src: { label: "How it works", href: "/product", spot: "#start" } };
    case "hindi":
      return { topic, hindi: true, text: "हाँ! मैं हिंदी और अंग्रेज़ी दोनों में बात करती हूँ, भले ही आपकी वेबसाइट सिर्फ़ अंग्रेज़ी में हो।", src: { label: "The Education version", href: "/for/education" } };
    case "sources":
      return { topic, text: "Only from your own website: your pages, files and price lists. Every answer shows its source, like this one. If something is not on your site, it says so and offers your team.", src: { label: "What it does", href: "/product", spot: "#does" } };
    case "security":
      return { topic, text: "Emails, phone numbers and card numbers are hidden before any model sees them. There is single sign-on, an audit log and a self-hosted edition. Speech and search indexing run on Google Vertex AI.", src: { label: "Trust and security", href: "/trust" } };
    case "integrations":
      return { topic, text: "It installs with one line of code on WordPress, Shopify, Webflow, Framer, Google Tag Manager, React, Vue or any site, and sends leads to Slack and your CRM.", src: { label: "Integrations", href: "/integrations" } };
    case "book":
      return hi
        ? { topic, hindi: true, text: "ज़रूर। क्या मैं यह डेमो बुक कर दूँ?", visual: "confirm" }
        : { topic, text: "Happy to. Shall I book a 20-minute demo with the team? Nothing is booked until you say yes.", visual: "confirm" };
    case "banks":
      return { topic, text: "There is a version of this site for banks, insurers and fintechs. Changing the site for you now.", act: { world: "enterprise" }, src: { label: "For banks and insurers", href: "/for/enterprise" } };
    default:
      return hi
        ? { topic, hindi: true, text: "यह जानकारी इस वेबसाइट पर नहीं है। मैं टीम से आपसे संपर्क करने को कह सकती हूँ।" }
        : { topic, text: "That is not on this website, so I won't guess. I can ask the team to get back to you." };
  }
}

/** What happens after the visitor confirms a booking in the preview. */
export const BOOKED = "On a live site this books the slot and sends the invite once you say yes. This preview cannot book yet, so nothing was sent.";
export const PREVIEW_NOTE = "Preview: answers are scripted from this site's own pages until the live agent is connected.";
