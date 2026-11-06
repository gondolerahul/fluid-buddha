# FluidBuddha — High-Value Use Cases

> **What this document is.** A catalogue of use cases that combine FluidBuddha's capabilities
> into outcomes a website could not deliver before. Every capability used here is built and
> described in the product documents in
> [`docs/product-docs/version_1.0/`](../product-docs/version_1.0/): the
> [Feature List](../product-docs/version_1.0/FeatureList.md), the
> [Functional Specification](../product-docs/version_1.0/FunctionalSpecification.md)
> (requirement IDs such as `FR-ACT-03`) and the
> [Technical Specification](../product-docs/version_1.0/TechnicalSpecification.md).
>
> **How to read the ROI figures.** FluidBuddha's plan prices are real (Growth: ₹33,000 a month
> for 2,000 conversations). Every other number in the worked examples (traffic, conversion
> rates, deal sizes, salaries) is an **illustrative assumption**, labelled as such, for the
> customer to replace with their own. None of them is a measured result. Each use case ends
> with how to *prove* its value with the product's own holdout experiment and analytics, so
> the real figure comes from the customer's own traffic.

---

## Contents

1. [The value levers](#1-the-value-levers)
2. [Use cases at a glance](#2-use-cases-at-a-glance)
3. [Revenue and sales use cases](#3-revenue-and-sales-use-cases) (UC-01 – UC-06)
4. [Marketing and growth use cases](#4-marketing-and-growth-use-cases) (UC-07 – UC-10)
5. [Vertical use cases](#5-vertical-use-cases) (UC-11 – UC-14)
6. [Platform and enterprise use cases](#6-platform-and-enterprise-use-cases) (UC-15 – UC-18)
7. [Feature combination matrix](#7-feature-combination-matrix)
8. [Proving ROI with the product itself](#8-proving-roi-with-the-product-itself)
9. [Claims guidance for marketing](#9-claims-guidance-for-marketing)

---

## 1. The value levers

Every use case below pulls on one or more of these levers. They are what make the ROI large:
the product either creates revenue that a static website leaves on the table, or replaces
expensive human time, at a cost per conversation in the tens of rupees.

| Lever | What changes | Capabilities behind it |
|---|---|---|
| **Revenue capture** | Buyers who would have left get answered, qualified and converted while their intent is highest. | Voice and text agent, components, lead capture and scoring, actions, live handoff |
| **Human time replaced** | Work done by solutions engineers, SDRs, front desks, admissions counsellors and copywriters is done by the agent, at any hour. | Grounded answers, guided tour, ROI configurators, campaign composer, triggers |
| **Speed to revenue** | The gap between interest and action shrinks from days to one conversation. | Confirmable actions, voice confirmation, payment links, meeting links, live calls |
| **Proof** | Spend is defended with causal lift, not anecdotes. | Holdout experiment, variant tests, campaign A/B, analytics, weekly digest |
| **Falling unit cost** | Repeat questions replay from cache at near-zero model cost; costs are capped per site. | Answer and audio cache, lean/heavy routing, spend caps, cost alerts |
| **Market intelligence** | Every question becomes structured data about objections, competitors and missing content. | Insights v1 and v2, knowledge gaps, feature-request grouping |

---

## 2. Use cases at a glance

| ID | Use case | Primary buyer | What was not possible before | Main lever | Min. tier |
|---|---|---|---|---|---|
| UC-01 | The website that gives the demo | B2B SaaS revenue leader | A technical, personalised, *visual* demo at 2 a.m. with no solutions engineer | Revenue capture, human time | advance |
| UC-02 | Anonymous visitor to live sales call in one tab | Head of sales | Spotting a hot buyer mid-conversation and calling them in the browser, with full context, without a phone number or calendar | Speed to revenue | high (voice) |
| UC-03 | Close the sale inside the conversation | SMB, D2C services, education | Saying "yes" out loud and receiving a correct, price-list payment link from a website, safely | Speed to revenue | basic |
| UC-04 | The buying-committee multiplier | Enterprise sales | A champion's conversation becoming a forwardable, interactive brief that also reports how widely it spread | Revenue capture, proof | advance |
| UC-05 | Interactive ROI selling | Any considered purchase | A calculator built on the spot for the visitor's own numbers, with the agent commenting live as they move sliders | Revenue capture | advance |
| UC-06 | Self-serve quote and trial desk | SaaS, B2B services | Quotes and trials provisioned from a conversation, confirmed by the buyer, with a PDF for the sales team | Human time, speed | basic |
| UC-07 | One campaign, a thousand grounded landing pages | Demand generation, ABM | A personalised page per account, persona and search term, composed from real content with numbers verified against sources | Human time, revenue | — (campaigns) |
| UC-08 | The agent that knows when to speak | Growth marketing | A proactive opener written for the exact page, tested against alternatives with false-win-safe statistics, and promoted with one click | Revenue capture, proof | basic |
| UC-09 | Proving AI ROI to the CFO | CMO, CFO | A causal, always-valid measurement of what the website agent adds, built into the product | Proof | basic |
| UC-10 | Voice of the visitor, every Monday | Product marketing, product, content | Every visitor question turned into ranked objections, competitor mentions, grouped feature requests and content gaps you can close in one click | Market intelligence | basic |
| UC-11 | Vernacular voice sales for Bharat | Indian businesses | A Hindi and Hinglish voice agent answering from English content, with no translation project | Revenue capture | high |
| UC-12 | Safe AI front desk for clinics and hospitals | Healthcare | A voice front desk that books appointments in English or Hindi and cannot be talked into medical advice | Human time | high |
| UC-13 | Long-cycle property buying with memory | Real estate | A site that remembers what an opted-in buyer explored weeks ago and picks up where they left off | Revenue capture | advance |
| UC-14 | Admissions counsellor at midnight | Education | Programme guidance, application-fee payment and a recap the student forwards to parents, in one visit | Human time, speed | advance |
| UC-15 | Agentic website, live in an afternoon (agencies) | Agencies, multi-brand groups | Turning a client's existing site into a voice agent with personas, brand styling and a tour from just its URL | Human time | basic |
| UC-16 | Your website as a service for AI assistants | Forward-looking brands | Other AI assistants querying the site's grounded answers and prices, and booking or buying through scoped tokens | Revenue capture | basic (agent access) |
| UC-17 | The regulated enterprise's private agent | BFSI, healthcare, government suppliers | A voice agent inside the customer's own infrastructure, on their own model contract, with SSO, audit and an offline licence | Risk removed | any (self-hosted) |
| UC-18 | The headless site that builds itself | Product-led, catalogue and API-driven businesses | A page composed for each visitor's question from content, live APIs and the brand system, instead of authored pages | Human time, revenue | extreme |

---

## 3. Revenue and sales use cases

### UC-01 — The website that gives the demo

**The moment.** A technical buyer lands on the pricing or integrations page at 11 p.m. They
have three specific questions ("Does it integrate with our ERP?", "What would 40 seats cost?",
"Is our data kept in India?"). A static site makes them book a call and wait days. Many leave.

**What was not possible before.** A *visual*, personalised technical walkthrough with no human
present: the website speaks, draws the integration as a flowchart, builds a cost configurator
for the buyer's seat count, scrolls to the security section and hands over a qualified lead,
all in one conversation.

**How it works (feature combination).**
1. A proactive trigger fires after 30 s on the pricing page (`FR-TRG-01`), or the visitor
   opens the agent.
2. The visitor asks by voice. An acknowledgement is spoken at once while the grounded answer
   is prepared in parallel (`FR-VOICE-05`).
3. The heavy thinker grounds the answer in the site's knowledge (`FR-GRD-01`), draws a
   workflow diagram of the integration and a configurator priced in rupees (`FR-CMP-01`), and
   the speech waits until the visual appears.
4. "Actually we have 60 seats" patches the configurator in place with a count-up animation
   (`FR-CMP-05`).
5. "Show me how you handle security" navigates to the real security page and, at design
   Level 3, spotlights the section (`FR-NAV-01`, `FR-DES-03`).
6. The persona switches to *Enterprise* and the page re-themes (`FR-PER-02`).
7. The visitor leaves an email. The lead is scored with transparent reasons, summarised from
   their questions, and sent to the CRM by signed webhook and to Slack as a hot lead
   (`FR-SCORE-01`, `FR-DEL-02`).
8. Every answer carries citations, so the buyer can check the claim (`FR-GRD-04`).

**Value and ROI (illustrative worked example).**

| Input | Assumption (replace with yours) |
|---|---|
| Conversations a month | 2,000 (the Growth plan allowance) |
| Share that become qualified opportunities *the site would otherwise have lost* | 1.5 % → 30 opportunities |
| Win rate | 20 % → 6 deals |
| Average first-year contract value | ₹6,00,000 |
| **Incremental first-year revenue** | **₹36,00,000 a month** |
| FluidBuddha Growth plan | ₹33,000 a month |
| Solutions-engineer hours freed (first calls avoided: 30 × 1 h × ₹2,500/h) | ₹75,000 a month |

Even if the true incremental rate is a tenth of the assumption, the return is still a multiple
of the plan cost. The point for buyers: one extra deal a quarter typically pays for a year.

**How to prove it.** Run the holdout experiment with the demo-booked page as the goal
(`FR-CON-HOLD-02`). Watch lead scores and sources in Leads, and cost per conversation in
Analytics.

---

### UC-02 — Anonymous visitor to live sales call in one tab

**The moment.** A visitor from a target account is deep in a conversation about enterprise
pricing. The agent has answered well, but this buyer is ready *now*. Today that intent decays
into a form fill and a follow-up email two days later.

**What was not possible before.** A salesperson sees the hot conversation stream in live,
takes it over, and starts a **voice call inside the browser**: no phone number collected, no
calendar link, no app install. When they hand back, the agent knows everything that was said.

**How it works.**
1. The Live inbox lists everyone talking to the agent now, with their last question and lead
   score (`FR-LIVE-01`). When a visitor leaves their details and the lead scores at or above
   the hot-lead threshold, Slack alerts the team (`FR-DEL-02`).
2. The salesperson takes over. The agent stops mid-sentence, and the visitor sees
   "Priya from the team joined the conversation" (`FR-LIVE-03`).
3. They exchange messages. If the visitor is using voice, the salesperson can call them: the
   visitor accepts in the widget, the call runs over WebRTC with a TURN relay, and the agent
   stops listening (`FR-LIVE-07`). Text-mode visitors get the messages only.
4. On hand-back, the agent's history is updated so it never repeats or contradicts the person
   (`FR-LIVE-05`). The call duration is noted in the transcript.
5. Personal details typed during the takeover are masked in storage (`FR-PII-03`).

**Value and ROI.** Response time to a hot inbound buyer drops from hours to seconds, at the
moment of peak intent. Illustrative: if 10 hot conversations a month are converted to calls
that would otherwise have gone cold, and 3 close at ₹6,00,000, that is ₹18,00,000 of revenue
from a few hours of a salesperson's time, on top of UC-01.

**How to prove it.** Compare win rates of taken-over conversations against similar-score leads
that were followed up by email. The transcript, lead score and outcome are on the lead.

---

### UC-03 — Close the sale inside the conversation

**The moment.** A small business sells fixed-price packages (a course, a consultation, a
service plan). Buyers ask a few questions and are ready to pay, but checkout is three clicks
away on another page, and many drop off.

**What was not possible before.** A buyer says "Okay, I'll take the annual plan" (or
"haan, le lete hain") and receives a correct payment link right there, confirmed by voice,
with the amount guaranteed to come from the business's own price list, never from the AI.

**How it works.**
1. The owner sets up a *payment link* action with a price list of up to 20 plans, on their own
   Razorpay account (`FR-CON-ACT-01`).
2. The agent proposes it when the visitor agrees. A confirmation card shows each detail and
   the amount; nothing happens yet (`FR-ACT-02`).
3. The visitor presses Confirm or simply says "yes, go ahead" or "haan" (`FR-ACT-03`).
4. Razorpay creates and emails the payment link. The run turns *paid* from the webhook, and
   the visitor is saved as a lead with source `payment` (`FR-ACT-05`, `FR-ACT-05a`).
5. The agent is told the outcome and can continue the conversation.

**Value and ROI.** Removes the drop-off between "yes" and "paid". Illustrative: a coaching
business with 500 conversations a month, where 2 % more buyers complete a ₹15,000 purchase
because they never leave the conversation, gains ₹1,50,000 a month for a plan that costs a
fraction of that (the Free plan covers 100 conversations; Growth covers 2,000).

**Why it is safe.** Money is never an input the AI controls, every run needs the visitor's own
confirmation within 15 minutes, runs execute once, and proposals are rate-limited
(`FR-ACT-06`, `FR-ACT-07`).

**How to prove it.** Action runs and paid status in the console; holdout experiment with
`FluidBuddha.conversion('purchase')` as the goal.

---

### UC-04 — The buying-committee multiplier

**The moment.** In B2B, the person on the website is rarely the only decision-maker. The
champion must re-explain everything to finance, IT and their manager, usually badly.

**What was not possible before.** The champion's conversation becomes a **branded, interactive
recap page** they can forward: the answers, the diagrams and calculators (still interactive),
the sources and a call to action. Each forward is counted and raises the lead score, so sales
can see the deal spreading inside the account.

**How it works.**
1. After three answers the widget offers a recap, or the visitor says "send me this" or
   "email me a recap at …" (`FR-OFF-01`, `FR-RCP-01`).
2. The recap page is built from the stored, PII-masked conversation, with components redrawn
   by the widget (`FR-RCP-04`).
3. With an email, the link is emailed and the address becomes a lead (`FR-RCP-03`).
4. Views are counted per viewer. The first view adds 5 points and each additional viewer
   (a forward) adds 10 to the lead score (`FR-SCORE-01`, `FR-RCP-06`).
5. Sales sees views and forwards on the lead and in *Shared recaps*.

**Value and ROI.** Fewer stalled deals and shorter cycles: the champion arrives at the internal
meeting with the vendor's own interactive explanation. The forward count is a new buying
signal that did not exist: a recap viewed by four people is a committee forming.

**How to prove it.** Compare close rates and cycle length for leads with recap forwards versus
leads without.

---

### UC-05 — Interactive ROI selling

**The moment.** "Is it worth it for us?" is the question behind every considered purchase.
Static ROI calculators are generic and rarely used.

**What was not possible before.** The agent builds a calculator **for this visitor's
situation, on the spot** (their team size, their costs, in rupees), and as they drag the
sliders it comments out loud on what the new numbers mean.

**How it works.**
1. The visitor describes their situation. The agent renders a configurator or scenario
   simulator with formulas over the visitor's inputs (`FR-CMP-01`, `FR-CMP-02`).
2. Money is shown in the site's currency with Indian digit grouping (`FR-CMP-03`).
3. Each slider change is reported. After a 0.7 s pause the agent speaks one short insight,
   never reading the numbers back (`FR-CMP-04`).
4. Corrections patch the calculator in place (`FR-CMP-05`).
5. The calculator travels into the recap page for the committee (UC-04), and the site's own
   branded calculators can be registered as custom components (`FR-CON-COMP-03`).

**Value and ROI.** Turns the abstract value proposition into the buyer's own number, the
single most persuasive artefact in a sale, without a sales engineer building a spreadsheet.

**How to prove it.** Variant test: the greeting variant that offers to "work out your savings"
against the default (`FR-CON-AB-01`).

---

### UC-06 — Self-serve quote and trial desk

**The moment.** Quote requests and trial sign-ups go through forms, then wait in a queue.

**What was not possible before.** The conversation itself collects exactly what is needed,
the buyer confirms it, and the result is instant: a trial login link from the company's own
backend, or a quote request that lands with the sales team as a PDF.

**How it works.**
1. *Trial* action: on confirmation, a signed request goes to the company's backend, which
   returns a login link shown to the visitor (`FR-ACT-05`).
2. *Quote request* action: on confirmation, a lead (source `quote`) is delivered to the CRM and
   Slack, emailed to the site owners and downloadable as a one-page PDF (`FR-CON-ACT-03`).
3. *Meeting link* action: the company's Calendly or Cal.com page opens pre-filled with the
   visitor's details.
4. Inputs are validated server-side; missing details make the agent ask for them
   (`FR-ACT-02`).

**Value and ROI.** Minutes from interest to trial instead of days. Illustrative: a SaaS where
trial-to-paid is 10 % and a customer is worth ₹2,00,000 a year gains ₹2,00,000 of annual value
for every 10 extra trials started in-conversation.

**How to prove it.** Action run counts and lead sources; holdout with trial activation as the
goal.

---

## 4. Marketing and growth use cases

### UC-07 — One campaign, a thousand grounded landing pages

**The moment.** Account-based and paid campaigns perform better with a page per segment,
account and search term, but no team can write thousands of pages, and AI-written pages risk
invented claims.

**What was not possible before.** One campaign brief produces a **personalised landing page per
link**: "Prepared for Acme", composed for the *Enterprise* persona, answering the exact search
term first, with every number on the page verified against the company's own content, and the
voice agent on the page to continue the conversation.

**How it works.**
1. Marketing writes a brief: goal, audience, key messages, allowed sections, call to action,
   and the proof they supply (testimonials and logos) (`FR-CON-CAMP-01`).
2. Links carry the context: `?persona=enterprise&q=sso+pricing&account=Acme&utm_source=linkedin`
   (`FR-CAMP-02`).
3. The composer uses only the site's knowledge, pinned answers and supplied proof. Factual
   sections must cite sources, every number must appear in its source or the brief,
   testimonials and logos are never invented, and anything that fails is dropped
   (`FR-CAMP-04`).
4. Pages are cached per context, so traffic does not multiply model cost; the account name is
   applied at render time for free (`FR-CAMP-06`).
5. An optional version B is tested with the same false-win-safe statistics, and conversions
   are counted by arm, persona and source (`FR-CAMP-09`).

**Value and ROI.** Replaces weeks of copywriting and design per campaign variant, and lifts
conversion from relevance. Illustrative: an ABM programme targeting 300 accounts would need
300 pages; here it is one brief, with the agent on every page.

**How to prove it.** Campaign analytics (views, engaged, converted by arm, persona and source)
and the version A/B verdict.

---

### UC-08 — The agent that knows when to speak

**The moment.** Pop-ups annoy; silent chat bubbles get ignored. The right message at the right
moment on the right page converts, but nobody can write and test openers for every page.

**What was not possible before.** Triggers that fire on real behaviour (time on page, scroll
depth, exit intent on desktop *and* mobile, return visits), with an opener the agent writes for
each specific page, then A/B-tested against alternatives and promoted to default in one click,
without the false winners that come from checking results every day.

**How it works.**
1. Rules define when, where and how (nudge bubble or opening the agent), with strict caps:
   one per page view, a daily cap per visitor, silence after a dismissal (`FR-TRG-01`,
   `FR-TRG-05`).
2. With *compose* on, the agent writes a page-specific opener, cached per page and language
   (`FR-TRG-03`).
3. Each rule reports shown, clicked, dismissed and engaged rates (`FR-CON-TRG-02`).
4. A trigger A/B test compares variants; *Make default* switches on the winner's triggers and
   the rest off (`FR-CON-AB-04`).

**Value and ROI.** More conversations started by high-intent visitors, especially those about
to leave. Every extra engaged visitor feeds UC-01 to UC-06.

**How to prove it.** Trigger engagement rates, and a trigger variant test with the site goal.

---

### UC-09 — Proving AI ROI to the CFO

**The moment.** Every AI widget vendor claims uplift. Finance asks: "Compared to what?"

**What was not possible before.** A **built-in randomised holdout**: a share of visitors never
sees the agent, both groups are measured on the site's own goal, and the verdict uses an
always-valid interval, so the dashboard can be read every day without inflating false wins.

**How it works.**
1. Switch on the holdout (default 10 % of visitors) and choose the goal: a page (for example
   `/thank-you`) or a `FluidBuddha.conversion()` call (`FR-CON-HOLD-01`).
2. Visitors are assigned deterministically; bots are kept out (`FR-WID-07`).
3. Results show each arm's rate, the difference, relative lift, and a verdict of *collecting*,
   *trending* or *significant* (`FR-CON-HOLD-02`). Leads captured by the agent are excluded
   from the goal, because the holdout cannot produce them.
4. The planner says how many visitors and days are needed (`FR-CON-HOLD-03`).
5. Analytics shows cost per conversation and per stage; the weekly digest brings results to
   leadership every Monday (`FR-CON-ANA-01`, `FR-DIG-01`).

**Value and ROI.** Converts the agent from a cost line into a measured revenue line, which is
what unlocks budget renewal and expansion. ROI here is the formula, not an assumption:
*(lift in conversion rate × visitors × value per conversion) − plan cost*, with a confidence
interval.

**How to prove it.** This use case *is* the proof for all the others.

---

### UC-10 — Voice of the visitor, every Monday

**The moment.** Visitors tell websites exactly what they want, fear and compare against. That
information is lost in chat logs nobody reads.

**What was not possible before.** Every visitor question is classified automatically into
**objections** (price, security, integration, effort, trust, timing), **competitor mentions**,
**feature requests** (grouped by meaning) and **buying signals**, with trends, linked examples
and a one-click way to close knowledge gaps, delivered as a Monday email.

**How it works.**
1. A background job labels each question, using the fast model or keyword rules, on
   PII-masked text (`FR-CON-INSI-03`).
2. Knowledge gaps list what the agent could not answer. *Answer a visitor question* turns a gap
   into new knowledge in one step (`FR-CON-INSI-05`).
3. Feature requests are sent to Slack, a webhook or the product team's email with examples
   (`FR-CON-INSI-04`).
4. The weekly digest summarises conversations, leads, top questions, new gaps, objections,
   competitors, test results and cost (`FR-DIG-01`).

**Value and ROI.** Continuous market research at no extra cost: product prioritises with real
demand, marketing writes content for real objections, sales gets competitor battle cards based
on what buyers actually ask. Each closed knowledge gap also makes the agent answer more
questions, which lifts conversion.

**How to prove it.** The count of knowledge gaps should fall and the share of grounded answers
should rise week on week (Insights, Analytics).

---

## 5. Vertical use cases

### UC-11 — Vernacular voice sales for Bharat

**The moment.** Hundreds of millions of Indian buyers are more comfortable speaking Hindi or
Hinglish than typing English, but most businesses' content exists only in English.

**What was not possible before.** A **Hindi voice agent that answers from English content**,
with no translation project: it detects Devanagari and Hinglish, searches the English knowledge
with an English query it writes itself, and speaks the answer in Hindi.

**How it works.**
1. The site switches Hindi on; the widget shows Hindi labels to Hindi visitors (`FR-WID-09`).
2. Speech recognition listens for Hindi and Indian English (`FR-LANG-04`).
3. The reply language follows the visitor: Devanagari gets Hindi, Hinglish gets clear Indian
   English unless the visitor prefers Hindi, and "Hindi mein bataiye" sets it for the
   conversation (`FR-LANG-02`).
4. The router writes an English search query in the same call as the acknowledgement, so
   grounding works at no extra cost (`FR-LANG-03`).
5. Hindi greetings, starter questions, voice confirmations ("haan") and "forget me" ("मुझे भूल
   जाओ") work end to end.

**Value and ROI.** Opens a market segment that English-only websites under-serve, without
creating or maintaining a second language version of the site.

**How to prove it.** Insights by language, and a holdout run on a Hindi-heavy traffic source.

---

### UC-12 — Safe AI front desk for clinics and hospitals

**The moment.** Clinic phone lines and front desks are swamped with "Which doctor?", "What are
the timings?", "Do you take my insurance?" and booking requests. A general chatbot is a
liability if it gives medical advice.

**What was not possible before.** A voice front desk that books appointments in English or
Hindi and **cannot be talked into medical advice**: diagnosis, treatment and dosage questions
get a fixed, polite refusal with an offer to book, and emergencies get the emergency numbers,
before any AI model is called.

**How it works.**
1. Start from the Healthcare template: calm front-desk voice, patient, caregiver and corporate
   personas, Hindi greeting and starter questions, and medical safety mode (`FR-CON-SET-03`).
2. Safety rules run first, in English, Hindi and Hinglish, and are never cached (`FR-SAFE-01`).
3. A *meeting link* action opens the booking page pre-filled; a quote request handles health
   check packages for corporates.
4. Personal details are masked before the model and storage, consent is asked before
   listening, and transcripts follow the retention window (`FR-PII-01`, `FR-CON-01`).

**Value and ROI.** Illustrative: if the agent handles 1,500 routine enquiries a month that
would each take 4 minutes of front-desk time, that is 100 staff hours a month, plus
appointments booked out of hours that would otherwise be lost.

**How to prove it.** Meeting-link runs, conversation volume by hour, and holdout with the
booking confirmation page as the goal.

---

### UC-13 — Long-cycle property buying with memory

**The moment.** Property buyers visit a developer's site many times over weeks, comparing
projects, sizes and budgets. Every visit starts from zero.

**What was not possible before.** With the buyer's permission, the site **remembers the
conversation** and greets them on their next visit with what they last asked, continues where
they left off, and nudges them towards a site visit at the right moment.

**How it works.**
1. Start from the Real estate template (investor and home-buyer personas, site-visit focus).
2. The buyer explores with a budget configurator (price plus registration, interiors and other
   costs, in rupees) and comparison tables (`FR-CMP-01`).
3. After the first answer the widget asks once whether to remember the conversation
   (`FR-OFF-02`). On the next visit: "Welcome back! Last time you asked: '…'" (`FR-MEM-04`).
4. A return-visit trigger opens the agent on the third visit in a week (`FR-TRG-01`).
5. A meeting-link action books the site visit; the lead score reflects every visit's questions.
6. "Forget me" deletes the memory at any time (`FR-MEM-05`).

**Value and ROI.** Property is a high-ticket purchase where one extra site visit can be worth a
sale. Illustrative: if memory and return-visit triggers convert 5 more site visits a month and
1 becomes a ₹80,00,000 booking, the commission or margin dwarfs the plan cost.

**How to prove it.** Variant test on the return-visit trigger; lead source and site-visit runs.

---

### UC-14 — Admissions counsellor at midnight

**The moment.** Prospective students research programmes at night, in English or Hindi, and
need their parents' agreement before paying anything. Counsellors work office hours.

**What was not possible before.** In one visit, a student gets programme guidance, a fee
comparison, pays the application fee by confirmed payment link, and forwards an interactive
recap to their parents.

**How it works.**
1. Start from the Education template (programmes, fees, admissions personas and questions).
2. A guided tour walks the student through the key pages, ending on a concrete outcome
   (`FR-TOUR-01`).
3. A fee comparison table and a scenario simulator show costs by programme and scholarship.
4. An *application fee* payment-link action, confirmed by the student (`FR-ACT-03`).
5. The student says "send me this" and forwards the recap link to their parents; each extra
   viewer raises the lead score (UC-04).
6. Lead fields from the template (course, city) are asked for naturally (`FR-LEAD-02`).

**Value and ROI.** More completed applications from the same traffic, and counsellors spend
time only on students who are ready. Illustrative: 20 extra completed applications a month at
a ₹1,000 fee is direct revenue, but the real value is the enrolments that follow.

**How to prove it.** Holdout with the application-complete page as the goal.

---

## 6. Platform and enterprise use cases

### UC-15 — Agentic website, live in an afternoon (agencies)

**The moment.** Agencies want to sell AI to every client, but each project means custom
integration work.

**What was not possible before.** From just a client's URL, one job crawls the site, builds its
knowledge, derives visitor personas from its own pages, reads its brand colours and fonts, and
plans a narrated tour. Installation is a plugin and an install code.

**How it works.**
1. *Crawl your website* respects `robots.txt` and the sitemap, ingests pages and linked PDFs
   (`FR-CON-ING-01`, `FR-CON-ING-02`).
2. Personas come from audience URLs such as `/for/startups` or `/industries/healthcare`
   (`FR-CON-ING-04`); brand tokens come from the homepage CSS (`FR-CON-ING-05`).
3. A vertical template sets voice, greeting, rules and triggers without overwriting edits.
4. The tour is planned automatically, ending on a use case with an illustrative saving
   (`FR-TOUR-01`).
5. Install with WordPress, Shopify, GTM, Webflow, Framer, React or Vue; everything else is
   controlled from the console (`FR-CON-INS-01`).
6. Roles apply per account and one person can belong to several accounts, so an agency can
   keep each client in its own account, invite the client's team with the right role, and
   switch between clients from one sign-in (`FR-AUTH-06`).

**Value and ROI.** Turns a multi-week custom build into a repeatable afternoon of work, so an
agency can sell and run the service across its whole client base.

**How to prove it.** Time from site added to first answered conversation; per-client holdout
results as the agency's case studies.

---

### UC-16 — Your website as a service for AI assistants

**The moment.** Buyers increasingly ask AI assistants to research vendors. Those assistants
scrape pages and often get facts wrong.

**What was not possible before.** The website exposes its **own grounded agent** to other AI
assistants through MCP, `llms.txt` and an OpenAPI "ask" endpoint, with the same guardrails and
citations as the widget, and, with tokens the business issues, lets trusted assistants capture
leads or run actions.

**How it works.**
1. An Admin switches on agent access for the site (`FR-AGT-01`).
2. Assistants call `search_knowledge`, `get_page` and `list_offerings` with the public key
   (`FR-AGT-03`).
3. Partners or the business's own agents get scoped tokens for `capture_lead` and actions
   (`FR-AGT-04`).
4. Every call is logged by tool and by assistant, rate-limited and kept out of billing
   (`FR-AGT-05`, `FR-AGT-06`).

**Value and ROI.** Controls how AI assistants describe the business (grounded, cited, current)
and opens a new channel where an assistant can book or buy on a buyer's behalf. This is an
early-market capability: position it as being ready for the agentic web rather than as proven
revenue today.

**How to prove it.** Agent traffic by assistant and leads with source `agent`.

---

### UC-17 — The regulated enterprise's private agent

**The moment.** Banks, insurers, hospitals and government suppliers want an AI website agent,
but cannot send data to a SaaS vendor or accept another model contract.

**What was not possible before.** The whole product runs **on the customer's own
infrastructure**, uses the customer's own Anthropic, OpenAI or Azure OpenAI contract for the
reasoning model, signs staff in with the customer's identity provider, records every change in
an audit log, and is licensed offline with no phone-home.

**How it works.**
1. Self-hosted bundle on one Linux host: TLS, backend, console, widget files, Postgres, Redis,
   optional TURN relay, backups with point-in-time recovery, air-gapped image transfer
   (`FR-SH-01`, `FR-SH-02`).
2. Offline Ed25519-signed licence. If it lapses, the console turns read-only but **visitors are
   never affected** (`FR-LIC-05`).
3. Bring your own model, with automatic fallback to the platform model on provider errors
   (`FR-BYO-01`, `FR-BYO-05`).
4. OIDC SSO for proven email domains, enforced two-factor, session timeouts, audit log,
   quarterly access reviews (`FR-SSO-03`, `FR-MFA-04`, `FR-AUD-01`).
5. PII masking, consent, retention and erasure, plus the SOC 2 control matrix and policies for
   the security review.

**Important caveat.** Speech recognition, speech synthesis and embeddings still run on Google
Vertex AI, even with a customer's own model (`FR-BYO-06`). Position this as "your data store,
your model contract, your identity", and qualify data-residency claims accordingly.

**Value and ROI.** Removes the procurement and security blockers that otherwise make the deal
impossible; the value is the entire contract that a SaaS-only vendor could not sign.

---

### UC-18 — The headless site that builds itself

**The moment.** Businesses with large catalogues, many plans or API-driven data cannot author a
page for every question a visitor might have.

**What was not possible before.** At the `extreme` tier, the agent **composes a full page for
the visitor's question** at runtime (hero, comparison, pricing table, chart, FAQ, enquiry form)
from the site's content, live data from its declared APIs and its brand design system.

**How it works.**
1. The agent decides from the visitor's request and grounds all copy in the knowledge base
   (`FR-CMP-07`).
2. It calls only operations declared in the site's OpenAPI spec for live data
   (`FR-CMP-08`).
3. The page is styled with the brand's design tokens and built from up to 12 typed sections;
   the model never writes HTML, so the page stays safe and on-brand.
4. An enquiry form on the page becomes a lead.

**Important caveat.** The design system and OpenAPI connection are configured by the platform
operator (environment or files), not yet in the console, and API calls are simulated until a
live API address is set. Position this as a premium, assisted-setup capability.

**Value and ROI.** Every long-tail question gets a purpose-built page instead of a generic one,
without content or design work per page.

---

## 7. Feature combination matrix

| Capability | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Voice conversation | ● | ● | ● |  | ● |  |  |  |  |  | ● | ● | ● | ● |  |  | ● |  |
| Grounded answers + citations | ● | ● | ● | ● | ● | ● | ● |  |  | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| Generated components | ● |  |  | ● | ● |  |  |  |  |  |  |  | ● | ● |  |  |  |  |
| Page control (navigate, scroll, spotlight, persona) | ● |  |  |  |  |  |  |  |  |  |  |  |  | ● | ● |  |  |  |
| Guided tour |  |  |  |  |  |  |  |  |  |  |  |  |  | ● | ● |  |  |  |
| Proactive triggers | ● |  |  |  |  |  |  | ● |  |  |  |  | ● |  | ● |  |  |  |
| Lead capture + scoring + delivery | ● | ● | ● | ● |  | ● | ● |  |  |  |  |  | ● | ● |  | ● |  | ● |
| Confirmable actions |  |  | ● |  |  | ● |  |  |  |  |  | ● | ● | ● |  | ● |  |  |
| Recap pages |  |  |  | ● | ● |  |  |  |  |  |  |  |  | ● |  |  |  |  |
| Live takeover + voice call |  | ● |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Visitor memory |  |  |  |  |  |  |  |  |  |  |  |  | ● |  |  |  |  |  |
| Campaign pages |  |  |  |  |  |  | ● |  |  |  |  |  |  |  |  |  |  |  |
| Holdout / A/B tests | ● |  | ● |  | ● | ● | ● | ● | ● |  | ● | ● | ● | ● | ● |  |  |  |
| Insights + digest |  |  |  |  |  |  |  |  | ● | ● | ● |  |  |  | ● |  |  |  |
| Hindi |  |  | ● |  |  |  |  |  |  |  | ● | ● |  | ● |  |  |  |  |
| Templates + crawl onboarding |  |  |  |  |  |  |  |  |  |  |  | ● | ● | ● | ● |  |  |  |
| Medical safety |  |  |  |  |  |  |  |  |  |  |  | ● |  |  |  |  |  |  |
| Agent endpoint (MCP) |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | ● |  |  |
| SSO, audit, BYO model, self-host |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | ● |  |
| Extreme page generation + site APIs |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | ● |

---

## 8. Proving ROI with the product itself

The strongest marketing claim FluidBuddha can make is not a number. It is that **every customer
can measure their own number** inside the product.

| Step | Where in the product |
|---|---|
| 1. Pick the goal that means money: a thank-you page, a booking page, or a `FluidBuddha.conversion('…')` call. | Holdout settings |
| 2. Run the holdout (default 10 %) until the verdict leaves *collecting*. The planner says how long. | Holdout results and planner |
| 3. Read the lift with its interval; it stays valid however often it is checked. | Holdout results |
| 4. Add the agent-only outcomes the holdout cannot see: scored leads, paid action runs, recap forwards, live calls. | Leads, Actions, Live |
| 5. Subtract the cost: plan price plus AI spend per conversation, with replayed answers costing almost nothing. | Billing, Analytics |
| 6. Send it to leadership every Monday. | Weekly digest |

**Unit economics to quote.** On the Growth plan a conversation costs about ₹16.50 (₹33,000 ÷
2,000) and ₹17 beyond the allowance. On Scale it is ₹12.50, then ₹10. Compare that with the
cost of one solutions-engineer hour, one paid click on a competitive keyword, or one inbound
lead from paid media.

---

## 9. Claims guidance for marketing

To keep these use cases credible in a security review or a sales call:

- **Say "illustrative" for every ROI number** in this document; never present an assumption as
  a customer result. Use real customer holdout results once they exist.
- **Say "grounded in your content, with sources", not "zero hallucinations".** The guardrail
  makes the agent say when it does not know; it is not a mathematical guarantee.
- **Say "adapts to the visitor's segment, language and page"**, not "completely personalised to
  each individual". Memory is opt-in per site and per visitor.
- **Say "acts on your site through navigation, scrolling and the actions you set up"**, not "can
  do anything on any website". The agent cannot click arbitrary buttons or fill in the host
  site's own forms.
- **Say "assembles pages and visuals from your content, APIs and brand"** for generative UI; it
  composes from safe, typed building blocks rather than writing free-form UI.
- **Qualify data residency** for self-hosted and BYO-model deals: speech and embeddings run on
  Google Vertex AI.
- **Languages:** English and Hindi only.
- **Capacity:** the recorded single-replica load test met the time-to-first-audio target at
  about 50 concurrent voice sessions; larger sites need more replicas.
