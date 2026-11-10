# FluidBuddha — Ideal Customer Profiles (version 2.0)

> **What this document is.** A description of the customers for whom FluidBuddha changes the
> economics of their website, and of the customers it does not fit yet. Each profile is built
> from what the product actually does at version 2.0 (see the
> [Feature List](../product-docs/version_2.0/FeatureList.md), the
> [Functional Specification](../product-docs/version_2.0/FunctionalSpecification.md) and the
> [Use Cases](UseCases.md)), from the coded plan prices and from the product's known limits.
>
> **What it is not.** It is not based on customer data. FluidBuddha has one named customer in
> the code (HireBuddha, the built-in demo profile) and no recorded win/loss history in this
> repository. Every profile below is a **hypothesis to test in the market**. Firmographic
> ranges, deal sizes and traffic numbers are reasoned estimates, marked as such. Section 8
> says how to check each profile with the product's own measurement.
>
> **Prices used.** Growth is ₹33,000 a month for 2,000 conversations (₹16.50 each, then ₹17).
> Scale is ₹1,25,000 a month for 10,000 conversations (₹12.50 each, then ₹10). Free is 100
> conversations a month. Enterprise and self-hosted are by arrangement.

---

## Contents

1. [What makes a customer a good fit](#1-what-makes-a-customer-a-good-fit)
2. [Profiles at a glance](#2-profiles-at-a-glance)
3. [Tier 1 profiles: sell now](#3-tier-1-profiles-sell-now) (ICP-1 – ICP-5)
4. [Tier 2 profiles: sell with care](#4-tier-2-profiles-sell-with-care) (ICP-6 – ICP-8)
5. [Tier 3 profiles: emerging](#5-tier-3-profiles-emerging) (ICP-9 – ICP-10)
6. [Who is not a fit today](#6-who-is-not-a-fit-today)
7. [Qualification scorecard and discovery questions](#7-qualification-scorecard-and-discovery-questions)
8. [How to validate these profiles](#8-how-to-validate-these-profiles)

---

## 1. What makes a customer a good fit

The product earns its price when five things are true together. They come from how the
product works, not from market research.

| # | Fit condition | Why it matters (from the product) |
|---|---|---|
| 1 | **A considered purchase.** The buyer has questions before buying, and one extra conversion is worth thousands of rupees or more. | A conversation costs ₹10 to ₹17. That only makes sense when an answered question can move a sale worth far more. |
| 2 | **Real content the agent can ground in.** A website with pages about the product, pricing, process and proof. | Every answer and every generated page comes from the site's own content. A thin site gives a thin agent, and the guardrail will say "I don't know" often. |
| 3 | **Enough traffic to measure.** Roughly 5,000 or more visits a month to the pages that matter. | The holdout needs at least 30 visitors per arm and 10 conversions before it leaves "collecting". Below that, value cannot be proven inside the product. |
| 4 | **English or Hindi buyers.** | These are the only two languages. Hindi and Hinglish support is a strength in India and a hard limit elsewhere. |
| 5 | **Someone who owns the website's results.** A growth, marketing or revenue leader with a number to hit. | The product is set up, tuned and measured from a console. Without an owner, triggers, tests and insights go unused. |

Three things raise the fit further:

- **Leads that go cold.** The business already loses buyers between interest and follow-up.
  Lead scoring, Slack alerts, live takeover and in-browser calls address exactly this.
- **Paid traffic.** Money is already spent bringing visitors. Generated regions and triggers
  raise what that spend returns.
- **A component library or headless stack.** A React design system or a Next.js site makes
  the 2.0 generative experience quick to adopt.

---

## 2. Profiles at a glance

| ID | Profile | Tier | Main pain | Lead use cases | Likely plan | Champion |
|---|---|---|---|---|---|---|
| ICP-1 | Indian B2B SaaS, sales-assisted, growth stage | 1 | Technical buyers leave before talking to sales; solutions engineers are the bottleneck | UC-01, 02, 04, 05, 06, 09, 10 | Growth → Scale | Head of growth or VP marketing |
| ICP-2 | Higher education and high-ticket edtech | 1 | Enquiries at night and in Hindi; counsellors work office hours; parents decide | UC-14, 11, 03, 04 | Growth → Scale | Head of admissions or marketing |
| ICP-3 | Real-estate developers and large brokerages | 1 | Long buying cycles; every visit starts from zero; site-visit bookings are the goal | UC-13, 11, 05, 02 | Growth | Head of sales or CRM lead |
| ICP-4 | Performance-marketing teams with heavy paid spend | 1 | Landing pages do not match the ad; cannot build a page per campaign; hard to prove lift | UC-19, 07, 08, 09 | Growth → Scale | Head of performance marketing |
| ICP-5 | Digital agencies and web studios | 1 | Clients want AI; each build is custom work | UC-15, then all | One account per client | Agency founder or head of delivery |
| ICP-6 | Private healthcare: hospital groups, clinic chains, diagnostics | 2 | Front desks flooded with routine questions; a chatbot giving medical advice is a liability | UC-12, 11 | Growth → Scale | Head of patient experience or marketing |
| ICP-7 | Regulated enterprises: banks, NBFCs, insurers, large fintechs | 2 | Cannot send data to a SaaS vendor; brand and legal veto generative UI | UC-17, 22, 21 | Enterprise, self-hosted | Head of digital, with the CISO |
| ICP-8 | Catalogue, marketplace and content businesses on a headless stack | 2 | Thousands of records, few proper pages; long-tail search is unserved | UC-20, 18, 16 | Scale → Enterprise | Head of product or SEO |
| ICP-9 | Enterprises with a mature design system | 3 | Design team blocks AI page tools; personalisation programme is stalled | UC-22, 19, 21 | Enterprise | Head of design systems or digital experience |
| ICP-10 | Small fixed-price service businesses | 3 | Buyers drop off between "yes" and payment | UC-03, 06 | Free → Growth | The owner |

Tier 1 profiles can be sold and proven with what is built and tested today. Tier 2 profiles
fit well but need a caveat stated up front or assisted setup. Tier 3 profiles depend on parts
of version 2.0 that have been verified with test models only, or on a price point that may not
fit.

---

## 3. Tier 1 profiles: sell now

### ICP-1 — Indian B2B SaaS, sales-assisted, growth stage

**Who they are (estimate).** Software companies selling to businesses, roughly 30 to 500
people, Series A to C or profitable and bootstrapped. Contract values from ₹2,00,000 to
₹50,00,000 a year. A sales team that gives demos. 10,000 to 200,000 website visits a month.
Buyers in India, and often in English-speaking markets abroad.

**What triggers the search.** A demo-request rate that has stopped growing. Solutions
engineers booked weeks out. A board question about what the website contributes. A competitor
with a chat widget.

**The pain in their words.** "People read our pricing page at midnight and leave." "Half our
first calls answer the same six questions." "We do not know why visitors do not convert."

**Why FluidBuddha changes the game for them.**

| Need | What the product does |
|---|---|
| Answer technical questions at once | Grounded voice and text answers with citations, an integration drawn as a diagram, a cost configurator for the buyer's seat count (UC-01, UC-05). |
| Catch the hot buyer | Lead scoring with reasons, Slack alert at the hot-lead score, live takeover and an in-browser call (UC-02). |
| Reach the rest of the buying committee | A recap page the champion forwards; each forward raises the lead score (UC-04). |
| Shorten trial and quote | Confirmed actions for trials, quotes and meetings (UC-06). |
| Know what buyers ask | Objections, competitor mentions and feature requests every Monday (UC-10). |
| Defend the budget | A built-in holdout with an always-valid verdict (UC-09). |

**The B2B SaaS template** sets the voice, personas, starter questions, triggers and suggested
actions in one click.

**Buying group.** Champion: head of growth or VP marketing. Economic buyer: CMO or CEO.
Technical check: an engineer, for the script tag and the lead webhook. Users: SDRs in the Live
inbox, product marketing in Insights.

**Economics (arithmetic on stated assumptions).** At Growth, 2,000 conversations cost ₹33,000.
If 1 % become opportunities the site would have lost (20), and 20 % close (4) at ₹6,00,000,
that is ₹24,00,000 of first-year revenue a month. The plan pays for itself if one such deal
closes every eighteen months. These rates are assumptions; the holdout gives the real ones.

**How to win.** Crawl their site during the first call and let them talk to their own
website. Agree on the holdout goal (the demo-booked page) before they buy.

**Objections and honest answers.**
- *"Will it make things up?"* It answers only from your content, shows sources, and says when
  it does not know. That is a guardrail, not a mathematical guarantee.
- *"We already have a chatbot."* Ask what share of its conversations become pipeline, and
  whether it can prove lift against a holdout.
- *"Our buyers are in Germany and Japan."* Then it is not a fit for those visitors today.

**Disqualify if.** Fewer than about 3,000 visits a month. A product-led motion with no
sales-assisted deals and a very low price point. A site with almost no content.

---

### ICP-2 — Higher education and high-ticket edtech

**Who they are (estimate).** Private universities, business schools, test-prep and upskilling
companies, study-abroad consultancies. Fees from ₹50,000 to ₹25,00,000. Enquiries peak in
admission seasons and in the evening. Students and parents across India, many more
comfortable in Hindi.

**What triggers the search.** A new admission season. Counsellor teams that cannot answer
every enquiry within the hour. Rising cost per lead from paid channels.

**The pain.** Enquiries arrive when counsellors are asleep. The student asks, the parent
decides, and the student cannot repeat the answers at home. Application-fee payment is a
separate step that many never finish.

**Why FluidBuddha changes the game for them.**

| Need | What the product does |
|---|---|
| Answer at midnight, in Hindi | A Hindi and Hinglish voice agent that answers from English content with no translation project (UC-11). |
| Guide, do not just answer | A narrated tour of programmes, a fee comparison table, a scholarship scenario simulator (UC-14). |
| Convince the parents | A recap the student forwards; each extra viewer raises the lead score (UC-04). |
| Collect the application fee | A payment link confirmed by the student, with the amount from the institution's own price list (UC-03). |
| Capture the right details | Lead fields from the Education template (course, city), asked for naturally. |

**Buying group.** Champion: head of admissions or marketing. Economic buyer: director or
registrar. Users: counsellors, who get scored leads with a summary of what was asked.

**Economics (assumptions).** If one extra enrolment is worth ₹2,00,000 in first-year fees, the
Growth plan needs one extra enrolment every six months to pay for itself.

**How to win.** Demonstrate in Hindi. Show a counsellor the lead they would have received,
with its summary and score.

**Objections and honest answers.**
- *"Students prefer WhatsApp."* The product is a website agent. It does not run on WhatsApp.
  It turns website visits into scored leads your team can follow up anywhere.
- *"We need Tamil, Telugu, Marathi."* Not supported today.

**Disqualify if.** Admissions are run entirely off-site (aggregators, WhatsApp) and the
website gets little traffic.

---

### ICP-3 — Real-estate developers and large brokerages

**Who they are (estimate).** Residential developers with several projects, and brokerages with
their own site. Ticket sizes from ₹40,00,000 upwards. The goal of the website is a site visit.
Buyers return many times over weeks.

**What triggers the search.** A project launch. Poor conversion from portal and paid leads.
A sales team that calls leads back too late.

**The pain.** Every visit starts from zero. Buyers want a full cost picture (price,
registration, interiors) and get a brochure. Hot buyers are called back the next day.

**Why FluidBuddha changes the game for them.**

| Need | What the product does |
|---|---|
| Remember the buyer | With the buyer's permission, the site greets them with what they asked last time (UC-13). |
| Show the real cost | A budget configurator and comparison tables in rupees, with Indian digit grouping. |
| Bring them back at the right moment | A return-visit trigger on the third visit in a week. |
| Book the site visit | A meeting-link action, pre-filled. |
| Call while they are on the page | Live takeover and an in-browser voice call (UC-02). |
| Speak their language | Hindi and Hinglish (UC-11). |

**The Real estate template** provides investor and home-buyer personas with a site-visit
focus.

**Buying group.** Champion: head of sales or the CRM lead. Economic buyer: director of sales
and marketing. Users: the pre-sales team in the Live inbox.

**Economics (assumptions).** One extra booking a quarter at a margin of even 2 % on an
₹80,00,000 home (₹1,60,000) covers more than a quarter of Growth.

**Objections and honest answers.**
- *"Our leads come from portals."* The product works on your own site. It raises the value of
  the traffic you already send there, and of return visits.
- *"Memory sounds invasive."* It is off by default, opt-in per visitor, and "Forget me"
  deletes it at once.

**Disqualify if.** There is no project website with real content, or site traffic is
negligible.

---

### ICP-4 — Performance-marketing teams with heavy paid spend

**Who they are (estimate).** Lead-generation and subscription businesses spending ₹10,00,000
or more a month on paid search and social: insurance and loan marketplaces, edtech, B2B SaaS
demand generation, home services, travel packages. They have a performance marketer who
watches cost per lead daily.

**What triggers the search.** Rising cost per click. A backlog of landing-page requests with
the web team. A finance question about whether the latest tool really produced lift.

**The pain.** The ad says one thing and the landing page says another. A page per ad group is
the known fix and nobody has the hands. A/B tools need a developer for every variant.

**Why FluidBuddha changes the game for them (2.0).**

| Need | What the product does |
|---|---|
| Match the page to the click | Adaptive regions rewrite the hero, proof and call to action for the visitor's campaign, search term and path (UC-19). |
| Do it without slowing the page | Cache first; the visitor sees the original content until a plan is ready. |
| Stay safe with search engines | Bots always get the page's own content. |
| A page per account or keyword | Campaign landing pages composed from one brief, with numbers checked against sources (UC-07). |
| Speak at the right moment | Behaviour triggers with openers written per page (UC-08). |
| Prove it | A *Generated regions* A/B test against the page's own content, and the holdout (UC-09). |
| Let the best version win | Optional learning shifts traffic to the version with the higher reward rate. |

**Buying group.** Champion: head of performance marketing or growth. Economic buyer: CMO.
Technical check: a front-end developer adds three `<fb-region>` tags.

**Economics (assumptions).** On ₹24,00,000 a month of media, a 10 % relative lift in landing
conversion is worth about ₹2,40,000 a month of media at the same cost per lead, against a
₹33,000 plan.

**How to win.** Offer a four-week pilot on one landing page with a region test agreed in
advance. Do not promise a lift figure.

**Objections and honest answers.**
- *"Will Google penalise us?"* Crawlers get your own content. Nothing generated is shown to
  them, and no facts differ.
- *"Has this been proven?"* The mechanism is tested. Results with live models on production
  traffic are what the pilot is for.

**Disqualify if.** Paid traffic lands on a third-party funnel builder where tags cannot be
added, or monthly paid visits are too few for a test to conclude.

---

### ICP-5 — Digital agencies and web studios

**Who they are (estimate).** Agencies of 10 to 200 people building and running sites on
WordPress, Shopify, Webflow, Framer and Next.js for mid-market clients, with retainers.

**What triggers the search.** Clients asking "what is our AI plan?". Pressure on retainer
margins. A wish for a product-like recurring line of revenue.

**The pain.** Every AI project is custom integration work that does not repeat.

**Why FluidBuddha changes the game for them.**

| Need | What the product does |
|---|---|
| Launch in an afternoon | One job crawls the client's site, builds knowledge, derives personas, reads brand colours and plans a tour (UC-15). |
| Install on anything | Plugins and guides for WordPress, Shopify, GTM, Webflow, Framer, React, Vue and, from 2.0, Next.js and edge workers. |
| Keep clients separate | One person can belong to several accounts with a role in each, and switch between them. |
| Show results | Per-client holdout results become the agency's case studies. |
| Sell upwards | Campaign pages, generated regions and composed pages are further services on the same install. |

**Buying group.** Champion and buyer: the founder or head of delivery. Users: account
managers and developers.

**Economics.** The agency's unit is the client. Each client account carries its own plan. The
agency's margin is its setup and running fee on top.

**Objections and honest answers.**
- *"Is there a partner programme or reseller pricing?"* Nothing of that kind exists in the
  product. Billing is per account. This needs a commercial decision before the profile is
  pursued at scale.
- *"Can we white-label it?"* The agent's name, voice, colours and design level are set per
  site. The console itself is FluidBuddha's.

**Disqualify if.** The agency's clients are mostly small brochure sites with little traffic.

---

## 4. Tier 2 profiles: sell with care

### ICP-6 — Private healthcare: hospital groups, clinic chains, diagnostics

**Who they are (estimate).** Multi-speciality hospitals, clinic chains and diagnostic networks
with online appointment booking and a marketing team. Patients and caregivers who often prefer
Hindi.

**The pain.** Front desks and phone lines are swamped by routine questions (which doctor,
what timings, which insurance). A general chatbot that gives medical advice is a liability.

**Why FluidBuddha fits.**

| Need | What the product does |
|---|---|
| A front desk that never gives advice | Medical safety mode: diagnosis, treatment and dosage questions get a fixed refusal with an offer to book; emergencies get emergency numbers. Rule-based, before any model, in English, Hindi and Hinglish (UC-12). |
| Book appointments | A meeting-link action opens the booking page pre-filled. |
| Protect patient details | Emails, phone and card numbers masked before the model and storage; consent before listening; retention windows; erasure by email. |
| Serve corporates | A quote request for health-check packages. |

**The care to take.** State the limits before the security review, not after:
- PII masking is pattern-based. Names and addresses are not detected.
- Speech and embeddings run on Google Vertex AI, even self-hosted.
- The product is a front desk. It is not a clinical system and holds no patient records.

**Buying group.** Champion: head of patient experience or marketing. Gatekeepers: the medical
director and compliance. Economic buyer: COO.

**Disqualify if.** The buyer expects symptom checking or triage. The product refuses these by
design.

---

### ICP-7 — Regulated enterprises: banks, NBFCs, insurers, large fintechs

**Who they are (estimate).** Institutions with a security review, an identity provider, a
vendor-risk process and their own model contract. Considered products (loans, insurance,
wealth) with long research journeys.

**The pain.** They want an AI website agent and generative personalisation, but they cannot
send data to a SaaS vendor, cannot accept another model contract, and their brand and legal
teams veto anything that writes its own copy.

**Why FluidBuddha fits.**

| Need | What the product does |
|---|---|
| Run it inside | A self-hosted bundle on one Linux host, air-gapped image transfer, backups with point-in-time recovery, an offline signed licence (UC-17). |
| Their model, their identity | Anthropic, OpenAI or Azure OpenAI on their contract; OIDC SSO; enforced two-factor; audit log; quarterly access reviews. |
| Control what AI may say and show (2.0) | Approved components only, source rules that force prices to come from their APIs, Admin approval of every manifest version (UC-22). |
| Personalise within rules (2.0) | Free-form pages with blocked routes, pinned regulatory notices, budgets and a review feed (UC-21). |
| Evidence for the review | SOC 2 control matrix, policies, sub-processor list, DPA template. |

**The care to take.**
- Speech recognition, speech synthesis and embeddings still run on Google Vertex AI.
  Position it as "your data store, your model contract, your identity", and qualify
  data-residency claims.
- The generative composers have been verified with test models. Sell a pilot.
- Pages cannot yet show a signed-in customer's own data.
- Licence features (`byo_model`, `agent_access`, `campaigns`, `sso`, `voice_handoff`) are set
  per licence.

**Buying group.** Champion: head of digital or digital experience. Gatekeepers: CISO, legal,
brand. Economic buyer: CDO or CMO. Expect a long cycle.

**Disqualify if.** Policy requires every model, including speech, to run on the customer's
own cloud. That is not possible today.

---

### ICP-8 — Catalogue, marketplace and content businesses on a headless stack

**Who they are (estimate).** B2B distributors, travel and experience marketplaces, course
catalogues, large publishers and multi-location service brands. Hundreds to tens of thousands
of records. A Next.js site, or any site that can sit behind an edge worker. An in-house
front-end team.

**The pain.** Most records have a thin template page or none. The content team cannot keep
up. Long-tail search and the buyer who wants the exact page are both unserved.

**Why FluidBuddha fits (2.0).**

| Need | What the product does |
|---|---|
| A proper page per record | One route pattern composes a server-rendered page per record from approved components (UC-20). |
| Facts from the source | Props bound to records or read APIs; a region with missing data is not drawn. |
| Keep search engines happy | A canonical plan per route, `noindex` variants, JSON-LD from the page's regions. |
| Bring the data in | JSON or CSV import, a JSON feed, a WordPress feed. |
| Serve it from their domain | `@fluidbuddha/next` or `@fluidbuddha/edge`, with fallback to their own page. |
| Be ready for AI agents | Every page is also a view an assistant can read (UC-16). |

**The care to take.**
- Feeds sync on demand, not on a schedule.
- List bindings filter by simple equality. This is not a query engine.
- The OpenAPI connection is set up by the platform operator.
- It is not a cart or checkout. Checkout and cart paths are blocked from free-form by default.

**Buying group.** Champion: head of product or SEO. Technical buyer: the front-end lead.
Economic buyer: CPO or CMO.

**Disqualify if.** The site is a monolithic commerce platform where neither Next.js nor an
edge worker can be placed in front.

---

## 5. Tier 3 profiles: emerging

### ICP-9 — Enterprises with a mature design system

**Who they are.** Large digital teams with a React component library, a Storybook, a design
system team and a stalled personalisation programme.

**Why they could be the best customers of 2.0.** The product's central claim, "AI composes
only from your approved components", is exactly what a design system team wants to hear. The
draft manifest from Storybook, source rules per prop, tunables for what may vary, and Admin
approval map directly onto how these teams already work (UC-22).

**Why it is tier 3.** It is a platform sale with a long cycle and several gatekeepers. The
generative composers are verified with test models only. Customer components cannot yet send
events back to the agent. Sell to one design-system team as a design partner first.

**Champion.** Head of design systems or digital experience platform.

---

### ICP-10 — Small fixed-price service businesses

**Who they are.** Coaches, consultants, studios, clinics with one location, boutique course
sellers. They sell fixed-price packages and take payment online.

**Why the product fits.** A buyer says "yes" and gets a correct payment link in the
conversation, with the amount from the owner's price list (UC-03). Vertical templates and the
crawl make setup quick.

**Why it is tier 3.** The price point. Free covers 100 conversations a month. The next step is
Growth at ₹33,000 a month, which is too much for most small businesses. Until there is a plan
between the two, this profile is a source of sign-ups and learning, not of revenue.

**Champion.** The owner.

---

## 6. Who is not a fit today

Saying no early protects the product's reputation. Each of these comes from a limit in the
code.

| Not a fit | Reason |
|---|---|
| Businesses whose buyers need languages other than English and Hindi | Only these two are supported, in the widget, the agent and speech. |
| Low-ticket, impulse e-commerce | A conversation costs ₹10 to ₹17. There is no cart or checkout integration. |
| Signed-in SaaS applications wanting an in-app assistant over each user's data | Bindings use site-level credentials only. User-token data access is not built. |
| Sites with very little traffic | The holdout cannot conclude, so value cannot be proven. The Free plan is the right place. |
| Sites with very little content | The agent grounds in the site's content and will often say it does not know. |
| Customer-support desks wanting ticket deflection | The product is a sales agent: leads, actions, handoff. It has no ticketing or help-desk connectors. |
| Organisations that need every model on their own cloud | Speech and embeddings run on Google Vertex AI. |
| Businesses wanting a WhatsApp, phone or app agent | The product runs on websites. |
| Teams wanting AI to design new pages or components freely | By design it composes only from approved components. |
| Clinical triage or symptom checking | Medical safety mode refuses these. |

---

## 7. Qualification scorecard and discovery questions

Score each line 0, 1 or 2. Twelve or more is a strong fit. Below seven, do not pursue.

| # | Question | 0 | 1 | 2 |
|---|---|---|---|---|
| 1 | What is one extra sale worth? | Under ₹5,000 | ₹5,000 – ₹1,00,000 | Over ₹1,00,000 |
| 2 | Monthly visits to product, pricing and landing pages? | Under 3,000 | 3,000 – 20,000 | Over 20,000 |
| 3 | Does the site explain product, pricing, process and proof? | Barely | Partly | Fully |
| 4 | Buyers' languages? | Other | English or Hindi plus others | English and/or Hindi |
| 5 | Is there an owner with a website target? | No | Shared | Named person |
| 6 | Do leads wait hours for a reply? | No | Sometimes | Often |
| 7 | Monthly paid media to the site? | None | Under ₹5,00,000 | Over ₹5,00,000 |
| 8 | Can a script tag (and, for 2.0, a few tags or an adapter) be added? | No | With effort | Easily |

**Discovery questions that reveal fit.**

1. "What happens when a buyer has a question at 11 p.m.?"
2. "How long does a hot lead wait before a person replies?"
3. "What are the six questions your first sales call always answers?"
4. "How many landing pages do you have, and how many campaigns point at them?"
5. "How do you know what your website contributes to revenue?"
6. "Which records (products, programmes, locations) have no proper page?"
7. "Who would have to approve AI-written content, and what would they need to see?"
8. "What share of your buyers would rather speak Hindi than type English?"

---

## 8. How to validate these profiles

These profiles are hypotheses. The product can test them.

| Step | How |
|---|---|
| 1. Run a pilot in each tier 1 profile with a holdout from day one. | Holdout with the customer's own goal page (`FR-CON-HOLD-01`). |
| 2. Record the lift, its interval and the cost per conversation. | Holdout results and Analytics. |
| 3. For 2.0 features, run a region or free-form A/B test. | A/B tests with subjects *Generated regions* and *Free-form pages*. |
| 4. Compare objections and buying signals across profiles. | Insights (deal signals) per site. |
| 5. Track time from site added to first answered conversation. | Console timestamps: a measure of setup effort per profile. |
| 6. Review after ten pilots: which profiles reached "significant", at what conversation volume, and which stalled in setup or security review. | Revise the tiers in this document. |

**What would change this document.** Measured lift per profile; a plan between Free and
Growth (moves ICP-10 up); more languages (opens new regions for ICP-2, ICP-3 and ICP-6);
user-token bindings (opens signed-in applications); scheduled feeds and a console API
catalogue (moves ICP-8 to tier 1); live-model verification of the generative composers (moves
ICP-9 up).
