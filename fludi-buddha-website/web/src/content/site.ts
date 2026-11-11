// Site-wide navigation, footer and plan data, shared by every page and every world.
// One header and one footer for the whole site: docs/marketing-docs/website/audit-2026-11-11.md §5.1.

import type { WorldId } from "./worlds/types";

export type NavLink = { label: string; href: string; note?: string };

/** The header's links. The same five on every page and in every version. */
export const NAV: NavLink[] = [
  { label: "Product", href: "/product" },
  { label: "Solutions", href: "#solutions" },
  { label: "Pricing", href: "/pricing" },
  { label: "Developers", href: "/developers" },
  { label: "Trust", href: "/trust" },
];

/** The Solutions panel: the three persona versions first, then teams and the other industries. */
export const SOLUTIONS: {
  worlds: { to: WorldId; label: string; note: string }[];
  teams: NavLink[];
  industries: NavLink[];
} = {
  worlds: [
    { to: "saas", label: "For B2B SaaS", note: "Buyers on your pricing page at 11 pm, answered" },
    { to: "education", label: "For universities and edtech", note: "Admissions questions at night, in Hindi or English" },
    { to: "enterprise", label: "For banks, insurers and fintechs", note: "On your own servers, inside your rules" },
  ],
  teams: [
    { label: "Sales", href: "/solutions/sales", note: "Tonight's visitors, tomorrow's pipeline" },
    { label: "Marketing", href: "/solutions/marketing", note: "Lift conversion, and measure it" },
    { label: "Results and ROI", href: "/results", note: "The built-in holdout test" },
  ],
  industries: [
    { label: "Retail and services", href: "/industries/retail-services" },
    { label: "Healthcare", href: "/industries/healthcare" },
    { label: "Real estate", href: "/industries/real-estate" },
    { label: "Agencies", href: "/industries/agencies" },
  ],
};

export const FOOTER: { title: string; links: NavLink[] }[] = [
  { title: "Product", links: [
    { label: "How it works", href: "/product" }, { label: "Three ways it appears", href: "/product/design" },
    { label: "Live demo", href: "/demo" }, { label: "Pricing", href: "/pricing" }, { label: "Integrations", href: "/integrations" } ] },
  { title: "Solutions", links: [
    { label: "For B2B SaaS", href: "/for/saas" }, { label: "For universities", href: "/for/education" },
    { label: "For banks and insurers", href: "/for/enterprise" }, { label: "Sales teams", href: "/solutions/sales" },
    { label: "Marketing teams", href: "/solutions/marketing" }, { label: "Results and ROI", href: "/results" } ] },
  { title: "Developers and trust", links: [
    { label: "For developers", href: "/developers" }, { label: "Trust and security", href: "/trust" },
    { label: "Privacy", href: "/legal/privacy" }, { label: "Terms", href: "/legal/terms" },
    { label: "Data processing", href: "/legal/dpa" }, { label: "Sub-processors", href: "/legal/subprocessors" } ] },
  { title: "Company", links: [
    { label: "About", href: "/about" }, { label: "Book a demo", href: "/book-demo" },
    { label: "Contact", href: "/contact" }, { label: "Cookies", href: "/legal/cookies" } ] },
];

export type Plan = {
  name: string; price: string; per: string; included: string; extra: string; features: string[];
  cta: string; href: string; lead?: boolean;
  /**
   * Reviewed Hindi, taken word for word from the earlier Hindi pricing page, for the runtime switch.
   * Only lines that were reviewed are here; a missing line (or an empty feature) stays in English.
   */
  hi?: { name?: string; price?: string; per?: string; included?: string; extra?: string; features?: string[]; cta?: string };
};

export const PLANS: Plan[] = [
  { name: "Free", price: "₹0", per: "a month", included: "100 conversations", extra: "No overage: a hard cap",
    features: ["Voice and text, English and Hindi", "Answers from your website, with sources", "Lead capture"], cta: "Start free", href: "/demo#start",
    hi: { name: "फ़्री", per: "प्रति माह", included: "100 बातचीत", extra: "कोई ओवरेज नहीं", features: ["बोलकर और लिखकर, हिंदी और अंग्रेज़ी", "सिर्फ़ आपकी वेबसाइट से जवाब, स्रोत के साथ", "लीड कैप्चर"], cta: "मुफ़्त शुरू करें" } },
  { name: "Growth", price: "₹33,000", per: "a month", included: "2,000 conversations", extra: "₹17 for each extra conversation", lead: true,
    features: ["Everything in Free", "Bookings, quotes, trials and payment links", "Slack alerts and CRM webhooks", "Insights and the Monday digest"], cta: "Book a demo", href: "/book-demo",
    hi: { name: "ग्रोथ", per: "प्रति माह", included: "2,000 बातचीत", extra: "हर अतिरिक्त बातचीत ₹17", features: ["फ़्री की सारी सुविधाएँ", "बुकिंग, कोटेशन, ट्रायल और पेमेंट लिंक", "Slack अलर्ट और CRM", "इनसाइट्स और सोमवार की रिपोर्ट"] } },
  { name: "Scale", price: "₹1,25,000", per: "a month", included: "10,000 conversations", extra: "₹10 for each extra conversation",
    features: ["Everything in Growth", "Holdout measurement and A/B tests", "Live takeover and browser voice calls", "Campaign landing pages"], cta: "Talk to us", href: "/book-demo",
    hi: { name: "स्केल", per: "प्रति माह", included: "10,000 बातचीत", extra: "हर अतिरिक्त बातचीत ₹10", features: ["ग्रोथ की सारी सुविधाएँ", "होल्डआउट माप और A/B टेस्ट", "लाइव टेकओवर और ब्राउज़र कॉल", "कैंपेन लैंडिंग पेज"], cta: "हमसे बात करें" } },
  { name: "Enterprise", price: "Custom", per: "by arrangement", included: "Unlimited conversations", extra: "Self-hosted or managed",
    features: ["Single sign-on, two-factor sign-in, audit log", "Self-hosted edition with an offline licence", "Your own model contract", "Status page, alerts and runbook"], cta: "Plan a pilot", href: "/for/enterprise",
    hi: { name: "एंटरप्राइज़", price: "कस्टम", per: "आपसी सहमति से", included: "असीमित बातचीत", features: ["SSO, MFA और ऑडिट लॉग", "", "अपना AI मॉडल", ""] } },
];
