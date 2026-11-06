// Site-wide navigation, footer and plan data. Source: docs/marketing-docs/WebsiteConcept.md §5, §7.15.

export type NavLink = { label: string; href: string; note?: string };

export const NAV: { label: string; href?: string; menu?: NavLink[] }[] = [
  { label: "Product", href: "/product" },
  {
    label: "Solutions",
    menu: [
      { label: "Sales", href: "/solutions/sales", note: "Turn tonight's visitors into tomorrow's pipeline" },
      { label: "Marketing", href: "/solutions/marketing", note: "Lift conversion, and prove it" },
      { label: "Results and ROI", href: "/results", note: "Measure the extra sales yourself" },
    ],
  },
  {
    label: "Industries",
    menu: [
      { label: "SaaS and B2B", href: "/industries/saas", note: "The technical buyer, answered at 11 PM" },
      { label: "Retail and services", href: "/industries/retail-services", note: "Hinglish questions, Hindi answers" },
      { label: "Healthcare", href: "/industries/healthcare", note: "A front desk that never gives medical advice" },
      { label: "Real estate", href: "/industries/real-estate", note: "Buyers take months. Your website remembers" },
      { label: "Education", href: "/industries/education", note: "An admissions counsellor at midnight" },
      { label: "Agencies", href: "/industries/agencies", note: "A talking client website in an afternoon" },
    ],
  },
  { label: "Pricing", href: "/pricing" },
  { label: "Developers", href: "/developers" },
];

export const FOOTER: { title: string; links: NavLink[] }[] = [
  { title: "Product", links: [
    { label: "How it works", href: "/product" }, { label: "Three ways it appears", href: "/product/design" },
    { label: "Live demo", href: "/demo" }, { label: "Pricing", href: "/pricing" }, { label: "Integrations", href: "/integrations" } ] },
  { title: "Solutions", links: [
    { label: "Sales", href: "/solutions/sales" }, { label: "Marketing", href: "/solutions/marketing" },
    { label: "Results and ROI", href: "/results" }, { label: "Enterprise", href: "/enterprise" } ] },
  { title: "Industries", links: [
    { label: "SaaS and B2B", href: "/industries/saas" }, { label: "Retail and services", href: "/industries/retail-services" },
    { label: "Healthcare", href: "/industries/healthcare" }, { label: "Real estate", href: "/industries/real-estate" },
    { label: "Education", href: "/industries/education" }, { label: "Agencies", href: "/industries/agencies" } ] },
  { title: "Developers", links: [
    { label: "For developers", href: "/developers" }, { label: "Trust and security", href: "/trust" },
  ] },
  { title: "Company", links: [
    { label: "About", href: "/about" }, { label: "Customers", href: "/customers" },
    { label: "Book a demo", href: "/book-demo" }, { label: "Contact", href: "/contact" } ] },
  { title: "Legal", links: [
    { label: "Privacy", href: "/legal/privacy" }, { label: "Terms", href: "/legal/terms" },
    { label: "DPA", href: "/legal/dpa" }, { label: "Sub-processors", href: "/legal/subprocessors" },
    { label: "Cookies", href: "/legal/cookies" } ] },
];

export const PLANS = [
  { name: "Free", price: "₹0", per: "per month", included: "100 conversations", extra: "No overage (hard cap)",
    features: ["Voice and text, English and Hindi", "Answers from your website, with sources", "Lead capture"], cta: "Start free", href: "/demo#start" },
  { name: "Growth", price: "₹33,000", per: "per month", included: "2,000 conversations", extra: "₹17 per extra conversation", hot: true,
    features: ["Everything in Free", "Bookings, quotes, trials and payment links", "Slack alerts and CRM webhooks", "Insights and the Monday digest"], cta: "Start a trial", href: "/book-demo" },
  { name: "Scale", price: "₹1,25,000", per: "per month", included: "10,000 conversations", extra: "₹10 per extra conversation",
    features: ["Everything in Growth", "Holdout measurement and A/B tests", "Live takeover and browser voice calls", "Campaign landing pages"], cta: "Talk to us", href: "/book-demo" },
  { name: "Enterprise", price: "Custom", per: "by arrangement", included: "Unlimited conversations", extra: "—",
    features: ["SSO, MFA and audit log", "Self-hosted edition, offline licence", "Bring your own model", "99.9% SLA tooling"], cta: "Contact sales", href: "/enterprise" },
];
