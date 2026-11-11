# FluidBuddha — Buyer Personas for ICP-1, ICP-2 and ICP-7

> **What this document is.** A deeper cut of three of the profiles in
> [IdealCustomerProfiles.md](IdealCustomerProfiles.md): **ICP-1** (Indian B2B SaaS,
> sales-assisted), **ICP-2** (higher education and high-ticket edtech) and **ICP-7**
> (regulated enterprises). For each, it names the people we need to reach, what each one cares
> about, what they will object to, what to show them and what to say.
>
> **How to read the personas.** They are **hypotheses built from the product, not from
> interviews.** The repository holds no customer research, so job titles, motivations and
> quotes are reasoned estimates and are labelled as such. Treat every persona as a script to
> test in the first ten conversations and then correct. Section 5 says how.
>
> **Where product claims come from.** Capabilities are cited by use case (UC-xx, in
> [UseCases.md](UseCases.md)) and requirement ID (FR-xx, in the
> [Functional Specification](../product-docs/version_2.0/FunctionalSpecification.md)).
> Limits are stated where a persona will probe them. Prices are the coded ones: Growth
> ₹33,000 a month for 2,000 conversations, Scale ₹1,25,000 for 10,000, Enterprise and
> self-hosted by arrangement.

---

## Contents

1. [How personas are organised](#1-how-personas-are-organised)
2. [ICP-1: Indian B2B SaaS, sales-assisted](#2-icp-1-indian-b2b-saas-sales-assisted)
3. [ICP-2: Higher education and high-ticket edtech](#3-icp-2-higher-education-and-high-ticket-edtech)
4. [ICP-7: Regulated enterprises](#4-icp-7-regulated-enterprises)
5. [Testing and correcting these personas](#5-testing-and-correcting-these-personas)

---

## 1. How personas are organised

Every sale has several people with different jobs. Each persona below has one of these roles.

| Role | What they do in the deal |
|---|---|
| **Champion** | Feels the pain daily, finds us, argues for us internally. |
| **Economic buyer** | Owns the budget and signs. Cares about return and risk. |
| **Technical evaluator** | Checks that it installs safely and fits the stack. |
| **Gatekeeper** | Can say no: security, legal, compliance, brand. Rarely says yes. |
| **End user** | Uses the console or the output after launch. Decides whether it sticks. |

Each persona is described with the same fields so they can be compared:

- **Who they are** (title variants, seniority, what they report on)
- **Their day** and what they are measured on
- **What they want** and **what they fear**
- **What they will ask us**, and the honest answer
- **What to show them** in the product
- **What to say** (a one-line message) and **what not to say**
- **Proof they will trust**

A card at the end of each ICP shows how the personas fit together in one deal.

---

## 2. ICP-1: Indian B2B SaaS, sales-assisted

**The company (estimate).** 30 to 500 people, Series A to C or profitable. Contracts of about
₹2,00,000 to ₹50,00,000 a year. A sales team that runs demos. 10,000 to 200,000 website visits
a month. Buyers in India and often abroad (English only abroad; see limits in persona 1.4).

**The central problem.** A technical buyer reads the pricing or integrations page late in the
evening, has three specific questions, finds no answer and leaves. Sales and solutions
engineers become the bottleneck for first calls.

**The deal in one line.** The head of growth champions it, the CMO or CEO signs, an engineer
checks the install, and the sales team uses the output every day.

### Persona 1.1: The Growth Owner (champion)

| | |
|---|---|
| **Role in deal** | Champion. Often the first person to look at the product. |
| **Titles (estimate)** | Head of Growth, VP Marketing, Director of Demand Generation, Growth Marketing Manager at the smaller end. |
| **Reports** | Pipeline from the website, demo requests, cost per opportunity. |

**Their day.** Reviews a weekly funnel. Fights for developer time to change the site. Gets
asked by the CEO what the website contributes. Has a number to hit each quarter.

**Wants.** More qualified demos from the same traffic. Proof of what works. A tool they can
run without a developer.

**Fears.** Another widget that annoys visitors, adds a cost line and shows nothing in a
quarter. Being blamed if the agent says something wrong.

**What they will ask, and the honest answer.**

| Question | Answer |
|---|---|
| "Will it make things up?" | It answers from your content, shows sources, and says when it does not know (FR-GRD-01 to FR-GRD-04). That is a guardrail, not a guarantee. |
| "How do I know it works?" | Switch on the holdout: a share of visitors never sees it, both groups are measured on your goal page, and the verdict is safe to read daily (UC-09, FR-CON-HOLD-01 to FR-CON-HOLD-03). |
| "How long to launch?" | Add a script tag, run the crawl. The crawl derives personas and brand colours and plans a tour (FR-CON-ING-01 to FR-CON-ING-05). The B2B SaaS template sets voice, personas and triggers. |
| "What does it cost per month?" | Growth is ₹33,000 for 2,000 conversations, about ₹16.50 each, then ₹17. |
| "Can it hurt our SEO?" | The conversation widget does not change your pages. If you add generated regions, crawlers always get your own content (FR-REG-04). |

**Show them.** Their own site, crawled live in the first call, with the agent answering a
pricing question and drawing a cost configurator (UC-01, UC-05). Then the Insights page
(objections, competitors, knowledge gaps) and the Holdout setup.

**Say.** "Your pricing page already gets the traffic. This answers the questions that make
people leave, and the product itself proves the lift."

**Do not say.** "Zero hallucinations", "guaranteed pipeline", or any lift percentage as a
promise.

**Proof they trust.** A holdout on their own goal page. A competitor-question report from
their own first week. A cost-per-conversation figure they can compare with a paid click.

### Persona 1.2: The Revenue Leader (economic buyer)

| | |
|---|---|
| **Role in deal** | Economic buyer. Signs, or approves the signature. |
| **Titles (estimate)** | CMO, Chief Revenue Officer, VP Sales, or the CEO or co-founder at a smaller company. |
| **Reports** | Revenue, win rate, sales cycle length, cost of acquisition. |

**Wants.** More closed revenue per sales head. A shorter first-call stage. A cost they can
defend to the board.

**Fears.** Brand risk from an AI speaking for the company. Spend with no attributable return.
Sales team resistance.

**What they will ask.**

| Question | Answer |
|---|---|
| "What is the return?" | The formula is lift in conversion × visitors × value per conversion, minus plan cost, with a confidence interval. We do not quote a figure; the holdout produces it (UC-09). |
| "What if it says something wrong about us?" | Site rules override everything else (FR-GRD-06). Pinned answers always replay, blocked questions never do (FR-CCH-03). Every answer carries sources. |
| "Does sales lose control of the lead?" | Hot leads alert Slack. A salesperson can take over a live conversation and hand back (UC-02, FR-LIVE-03 to FR-LIVE-05). |
| "What is the downside if it does not work?" | The Free plan covers 100 conversations. Growth is monthly. The holdout shows early whether it is working. |

**Show them.** A one-page view of the weekly digest (conversations, leads, top questions,
objections, cost) and the holdout result (FR-DIG-01). A single lead with its score, reasons
and summary.

**Say.** "One more deal a quarter pays for a year. Here is how you will know within weeks
whether you are on track." (This is illustrative arithmetic: one deal of ₹6,00,000 against
₹3,96,000 a year. Show the sum, mark it as an example.)

**Do not say.** Anything that implies it replaces the sales team.

**Proof they trust.** A peer SaaS company with a measured holdout result. Until one exists,
offer a paid pilot with the holdout agreed in advance.

### Persona 1.3: The Sales Floor (end user)

| | |
|---|---|
| **Role in deal** | End user and internal influencer. Can make or break adoption. |
| **Titles (estimate)** | Head of Sales Development, SDR or BDR team lead, Solutions Engineering Manager, Account Executives. |

**Their day.** Work inbound leads. Give first calls that repeat the same six answers.

**Wants.** Leads that are already qualified, with context. Fewer repeat first calls. A way
to catch a hot buyer while they are still on the page.

**Fears.** Being replaced. Leads of poor quality. Another tool to log into.

**What they will ask.**

| Question | Answer |
|---|---|
| "Does it send me junk?" | Each lead has a transparent score (contact details, questions asked, persona, buying words, recap forwards) and a summary of what was asked (FR-SCORE-01, FR-SCORE-02). |
| "Where do leads land?" | A signed webhook to your CRM, Zapier or Make, and a Slack alert for hot leads (FR-DEL-01, FR-DEL-02). There are no native CRM connectors. |
| "Can I speak to someone who is on the site now?" | Yes, from the Live inbox: take over, message, and start a voice call in the browser if the visitor is on voice (UC-02). |

**Show them.** The Live inbox and one scored lead with its transcript. Let them take over a
conversation themselves.

**Say.** "It does the first six answers so your first call starts at the seventh."

**Do not say.** "Fewer people needed."

**Proof they trust.** Seeing a real conversation turn into a lead they would want.

### Persona 1.4: The Integrator (technical evaluator)

| | |
|---|---|
| **Role in deal** | Technical evaluator. Can slow or stop a deal. |
| **Titles (estimate)** | Marketing operations manager, web or front-end developer, engineering manager, in some cases the CTO at a small company. |

**Wants.** A safe install that does not slow the site or break it. Control over where data
goes.

**Fears.** Page-weight regressions, third-party scripts, data leaving the company, a
vendor they have to babysit.

**What they will ask.**

| Question | Answer |
|---|---|
| "How heavy is the script?" | The script-tag core is about 38.6 kB gzipped per the build record. Other parts load only when needed (Hindi strings, Three.js for design level 2, component renderers). |
| "Will it clash with our CSS and JS?" | The widget lives in a Shadow DOM and does not affect host styles or scripts. |
| "Where is visitor data?" | In your account on FluidBuddha, with PII masking before the model and storage, microphone consent, retention windows and erasure by email. Speech and embeddings run on Google Vertex AI. |
| "How do we install it?" | One script tag; plugins for WordPress, Shopify and Google Tag Manager; React and Vue wrappers (FR-WID-01, FR-CON-INS-01). |
| "Which languages?" | English and Hindi only. Buyers abroad who need other languages are not served today. |

**Show them.** The Install tab and the Test connection button. The Shadow DOM isolation.
The privacy settings.

**Say.** "One tag, isolated from your page, and every setting you will want is in the
console."

**Proof they trust.** The security artefacts: the SOC 2 control matrix and policies, the
sub-processor list and a DPA template (all draft status in the repository; say so).

### How the four fit together in ICP-1

| Stage | Who is in the room | What moves the deal |
|---|---|---|
| First call | Growth Owner | Their own site, live. |
| Evaluation | Growth Owner, Integrator | Install check and the privacy answers. |
| Business case | Growth Owner, Revenue Leader | The holdout plan and the pilot terms. |
| Adoption | Sales Floor | A scored, summarised lead and live takeover. |

**Anti-persona for ICP-1.** The product-led growth leader with a low price point and no
sales-assisted deals: a conversation costs ₹10 to ₹17, so each visitor must be worth a great
deal more than that.

---

## 3. ICP-2: Higher education and high-ticket edtech

**The institution (estimate).** Private universities, business schools, test-prep and
upskilling companies, study-abroad consultancies. Fees from about ₹50,000 to ₹25,00,000.
Enquiries peak in admission seasons and at night. Students and parents across India, many
more comfortable in Hindi.

**The central problem.** Students research at night, a counsellor answers the next morning,
and the parent who decides never hears the answers first-hand. Application-fee payment is a
separate step that many do not finish.

**The deal in one line.** The head of admissions champions it, the director or registrar
approves, marketing runs the traffic and the counsellors use the leads. A parent is not a
buyer of the product but is a target of the product.

### Persona 2.1: The Admissions Head (champion)

| | |
|---|---|
| **Role in deal** | Champion. |
| **Titles (estimate)** | Head of Admissions, Director of Admissions, Dean of Enrolment, Head of Counselling. |
| **Reports** | Applications started and completed, enrolments, counsellor response time, cost per enrolment. |

**Their day.** Manage a counselling team through peak season. Chase leads that went cold.
Explain the same fee structure in dozens of calls.

**Wants.** Every enquiry answered quickly, in the student's language. More completed
applications from the same enquiries. Counsellors spending time on ready students.

**Fears.** A tool that gives wrong fee or eligibility information. Parents confused by an AI.
Counsellors feeling replaced.

**What they will ask.**

| Question | Answer |
|---|---|
| "Can it answer in Hindi?" | Yes. It detects Devanagari and Hinglish, searches your English content and answers in Hindi, with Hindi speech recognition and synthesis (UC-11, FR-LANG-01 to FR-LANG-04). |
| "What if it gives wrong fee information?" | Fee answers come from your content with sources. For application fees the amount is only ever from your own price list, never from the AI (FR-ACT-06). Pin the approved fee answer so it always replays (FR-CCH-03). |
| "Can it collect the application fee?" | Yes, as a payment link on your Razorpay account, confirmed by the student, with a voice "yes" or "haan" (UC-03, FR-ACT-03). |
| "Can parents see what was discussed?" | The student can say "send me this" and forward a recap page to their parents (UC-04, FR-RCP-01). |
| "What about other Indian languages?" | Not supported. English and Hindi only. |

**Show them.** A Hindi conversation about fees, then a fee comparison table, a scholarship
scenario simulator and a guided tour of programmes (UC-14). Then the lead the counsellor
would have received.

**Say.** "Your counsellors sleep at night. Your website does not have to."

**Do not say.** "It replaces counsellors" or "it guarantees admissions".

**Proof they trust.** A counsellor reading a real lead summary. A test in Hindi by someone on
their own team.

### Persona 2.2: The Institution Leader (economic buyer)

| | |
|---|---|
| **Role in deal** | Economic buyer and risk owner. |
| **Titles (estimate)** | Director, Pro Vice-Chancellor, Registrar, Chief Business Officer, founder or COO of an edtech. |

**Wants.** Enrolment targets met. Reputation protected. Spend that is easy to defend.

**Fears.** Reputational damage from wrong information. Parent complaints. A vendor handling
student data carelessly.

**What they will ask.**

| Question | Answer |
|---|---|
| "What about student data?" | PII (email, phone, card numbers) is masked before the model and storage. The microphone is off until the visitor consents. Retention windows and erasure by email exist (FR-PII-01 to FR-PII-05, FR-CON-SET-04, FR-CON-SET-05). Names and addresses are not detected, which we state. |
| "Are minors a concern?" | The product does not collect age. Your policy on minors' data should be reviewed with your counsel before launch. (Do not give a legal opinion.) |
| "What is the return?" | One extra enrolment worth ₹2,00,000 in first-year fees would cover the Growth plan for about six months. This is an example. Measure with a holdout on the application-complete page. |

**Show them.** The weekly digest and the privacy settings page.

**Say.** "More of the students who already found you finish the application, and your team
meets them when they are ready."

### Persona 2.3: The Enrolment Marketer (technical and growth evaluator)

| | |
|---|---|
| **Role in deal** | Evaluator and day-to-day owner of the console. |
| **Titles (estimate)** | Head of Marketing, Digital Marketing Manager, Performance Marketing Lead, web manager. |
| **Reports** | Cost per lead, cost per application, campaign performance in admission season. |

**Wants.** Better return from paid traffic. Landing pages per programme and per city.
Knowing which questions prospects ask.

**Fears.** A site change they cannot reverse. Peak-season downtime.

**What they will ask.**

| Question | Answer |
|---|---|
| "Can we have landing pages per programme?" | Campaign pages compose from one brief, with numbers checked against sources, and the agent on the page (UC-07). From 2.0, generated regions can adapt the hero and call to action to the campaign that brought the visitor (UC-19). |
| "Which insights will we get?" | Top questions, knowledge gaps, objections (price, trust, timing), competitor mentions and feature requests, delivered every Monday (UC-10). |
| "Will it work on WordPress?" | Yes, via the plugin (FR-CON-INS-01). |
| "Can we test it first?" | Yes: the holdout, plus A/B tests on greeting and triggers. |

**Show them.** Insights (knowledge gaps and objections) and Triggers (exit intent on mobile,
return visit).

**Say.** "Every question a prospect asks that your site cannot answer is a page you did not
know you needed."

### Persona 2.4: The Counsellor (end user)

| | |
|---|---|
| **Role in deal** | End user. |
| **Titles (estimate)** | Admissions counsellor, enquiry desk executive, programme advisor. |

**Wants.** Leads who are ready, with what they asked. Fewer repeat questions.

**Fears.** Being measured against an AI. Leads with no context.

**Show them.** A lead with its score, reasons and summary (FR-SCORE-01, FR-SCORE-02), and a
Slack alert for a hot lead.

**Say.** "You start the call knowing what they asked."

### Persona 2.5: The Student and the Parent (the people the product serves)

These two are not buyers of the product. They decide whether the product works, so the
messaging to the buyers should describe them.

| | **The Student (visitor)** | **The Parent (influencer of the visitor)** |
|---|---|---|
| **Who (estimate)** | 17 to 28 years old, researching late, often on a phone. | The family member who decides and pays. Less fluent online, often more comfortable in Hindi. |
| **Wants** | Quick, honest answers about fees, eligibility, outcomes. No form first. | Reassurance on cost, safety, recognition and return. |
| **Fears** | Being sold to. Waiting days. | Being pushed. Hidden costs. |
| **How the product serves them** | Voice or text, instant, in Hindi or English. A fee comparison and scenario simulator. | A forwardable recap page with the answers, sources and a call to action (UC-04). |
| **Watch-out** | Consent before the microphone; "Type instead" must always work (FR-CON-01). | The recap is the page they judge the institution by: check that it reads well in plain text and without scripts (FR-RCP-04). |

### How the personas fit together in ICP-2

| Stage | Who is in the room | What moves the deal |
|---|---|---|
| First call | Admissions Head | A Hindi demo on their own site. |
| Evaluation | Admissions Head, Enrolment Marketer | Insights and install. |
| Approval | Institution Leader | Privacy and the example return. |
| Adoption | Counsellor | A lead with a summary. |
| Proof | Admissions Head | Holdout on the application-complete page. |

**Seasonality.** Admission season sets the clock. A pilot that starts after applications
open has less time to show a result, so aim to start before.

**Anti-persona for ICP-2.** An admissions operation that runs entirely through aggregators
and WhatsApp, with a website that gets little traffic.

---

## 4. ICP-7: Regulated enterprises

**The institution (estimate).** Banks, NBFCs, insurers, large fintechs and similar
regulated enterprises, with a security review, an identity provider, a vendor-risk process
and often their own model contract. Considered products (loans, insurance, wealth) with long
research journeys.

**The central problem.** They want an AI website agent and generative personalisation, but
they cannot send data to a SaaS vendor, may not accept another model contract, and their
brand and legal teams veto anything that writes its own copy.

**The deal in one line.** The head of digital champions it. The CISO, legal, compliance and
brand teams each hold a veto. The CDO or CMO signs. Expect a long cycle and a pilot first.

**Product fit.** Self-hosted on one Linux host (UC-17), bring-your-own model, OIDC SSO,
enforced two-factor, audit log, offline licence, approved-components-only generative pages
with Admin approval (UC-22), free-form pages with blocked routes, pinned regions, budgets and
a review feed (UC-21).

**Three limits to state before the security review, not after.**

1. Speech recognition, speech synthesis and embeddings still run on Google Vertex AI, even
   self-hosted and with the customer's own model (FR-BYO-06). Position the product as "your
   data store, your model contract, your identity", and qualify any data-residency claim.
2. The generative composers were verified with test models, not production traffic. Sell a
   pilot.
3. Pages cannot yet show a signed-in customer's own data. Bindings use site-level
   credentials only.

### Persona 7.1: The Digital Head (champion)

| | |
|---|---|
| **Role in deal** | Champion. |
| **Titles (estimate)** | Head of Digital, Head of Digital Experience, VP Digital Channels, Head of Online Acquisition. |
| **Reports** | Digital leads and applications, completion rates, cost per acquisition, digital share of sales. |

**Their day.** Balance growth targets with a compliance function that can stop any change.
Struggle to personalise because every change needs approvals.

**Wants.** More completed journeys from the website. A route to personalisation that
compliance will accept. A vendor that survives the security review.

**Fears.** A launch pulled by compliance. A public error. Spending months on a review for a
pilot that never ships.

**What they will ask.**

| Question | Answer |
|---|---|
| "Can we keep data inside?" | The whole product runs on your infrastructure with Docker Compose, with air-gapped image transfer and an offline licence (FR-SH-01, FR-SH-02, FR-LIC-01). The exception is speech and embeddings (limit 1). |
| "Can we use our own model contract?" | Yes: Anthropic, OpenAI or Azure OpenAI, with fallback to the platform model if your provider fails (FR-BYO-01 to FR-BYO-05). Ask whether fallback is acceptable to your policy; it can send a call to the platform model. |
| "How do we stop it saying something non-compliant?" | Site rules override all else. Pinned answers replay verbatim and blocked questions are never answered by the agent. Medical-style safety logic exists only for the healthcare mode; for regulated finance, the owner writes the rules. Test them in a pilot. |
| "Who approves what generative pages may use?" | Only components in the manifest, and an Admin approves each version (FR-MAN-01, FR-CON-GX-06). Prices and facts the business owns are bound to its systems and never written by the model (FR-MAN-03, FR-BIND-07). |
| "What can go on a personalised page?" | Free-form is off on checkout, cart, legal, terms and privacy routes by default. Required notices are pinned regions on every page. Prices are never personalised (FR-G3-01, FR-G3-08, FR-TASTE-06). |

**Show them.** Draft manifest, diff and Admin approval (UC-22). The free-form review feed.
The "Why this?" explanation and the preferences panel.

**Say.** "Your teams decide what AI may build with, what it may say and where it may not go.
Everything outside those lines never reaches a visitor."

**Do not say.** "Fully compliant", "regulator-approved" or any statement about a specific
regulation. The compliance pack is draft documentation, and the customer's own counsel
decides what satisfies their regulator.

**Proof they trust.** A scoped pilot on one product page, with the review feed switched on
and compliance seeing every generated page before any visitor does (set the review share to
100 % for the pilot).

### Persona 7.2: The Information Security Lead (gatekeeper)

| | |
|---|---|
| **Role in deal** | Gatekeeper. Holds a veto. |
| **Titles (estimate)** | CISO, Head of Information Security, Vendor Risk Manager, Application Security Lead. |

**Wants.** A vendor that passes the questionnaire. Clear data flows. Control over access.

**Fears.** Data leaving the perimeter, third-party scripts on customer-facing pages,
credentials sprawl.

**What they will ask.**

| Question | Answer |
|---|---|
| "How do people sign in?" | OIDC SSO for proven email domains, enforced two-factor (an Owner can require it; SSO counts as two-factor), session timeouts (60 minutes idle, 12 hours absolute) and a lockout after 10 failures (FR-SSO-03, FR-MFA-04, FR-SES-01, FR-AUTH-04). |
| "Is there an audit trail?" | Every successful console change and every sign-in is logged for one year, searchable, CSV export (FR-AUD-01 to FR-AUD-03). Quarterly access review emails (FR-ACR-01). |
| "How are secrets stored?" | Fernet-encrypted with rotatable keys: SSO secrets, model keys, action secrets, webhook secrets and two-factor seeds. |
| "What about SSRF and outbound calls?" | Outbound fetches refuse private, loopback and link-local addresses, credentials in URLs and unsafe schemes, and re-check every redirect. DNS rebinding remains a residual risk (known limitation). |
| "What runs in the visitor's browser?" | A Shadow DOM widget that never injects model HTML. Customer Web Components run only from the approved bundle and only if its integrity hash matches (FR-MAN-06). |
| "What certifications do you hold?" | None are claimed in this repository. There is a SOC 2 control matrix and policies, all draft, with no audit report. Say exactly that. |
| "Do you phone home?" | The offline licence is checked locally with no phone-home. A lapsed licence makes the console read-only; visitors are never affected (FR-LIC-02, FR-LIC-05). |

**Show them.** The control matrix, the policies, the audit log, the Security page and the
sub-processor list.

**Say.** "Here is exactly where data goes, including the parts that still leave your
perimeter."

**Do not say.** "SOC 2 certified" or "compliant". Neither is true yet.

**Proof they trust.** Their own team running the self-hosted bundle in a sandbox and reading
the audit log.

### Persona 7.3: The Compliance and Legal Counsel (gatekeeper)

| | |
|---|---|
| **Role in deal** | Gatekeeper. Holds a veto over what visitors see and what is stored. |
| **Titles (estimate)** | Chief Compliance Officer, Head of Regulatory Compliance, General Counsel, Data Protection Officer, Marketing compliance reviewer. |

**Wants.** No misleading statements to customers. A record of what was shown. Data handled
lawfully.

**Fears.** An AI making a statement about returns, eligibility or terms that the institution
did not approve.

**What they will ask.**

| Question | Answer |
|---|---|
| "Can the AI quote a rate or a return?" | Only from your content with sources, and only if your rules allow. You can block any question so the agent will not answer it. Rates in pages come from bindings to your systems, not from the model. |
| "Can we see what visitors were shown?" | Transcripts are stored masked for the retention window you set. Cached plans are listed in the console. Free-form pages are sampled, and flagged ones can be blocked (FR-G3-10). The review feed is a sample, not a record of every page, unless the share is set to 100 %. |
| "How is consent handled?" | The microphone needs consent before the agent listens, and the consent time is stored (FR-CON-01 to FR-CON-04). Memory is off by default and opt-in per visitor (FR-MEM-01). |
| "Can a customer ask for deletion?" | Erasure by email deletes their leads, conversations and memory (FR-CON-SET-05). |
| "Where is data processed?" | State it exactly, including Google Vertex AI for speech and embeddings. |

**Show them.** The privacy settings, the site rules and blocked questions, the review feed
and the erasure tool.

**Say.** "You write the rules. The product enforces them, and shows you what it did."

**Do not say.** Anything that sounds like legal advice or regulatory approval.

### Persona 7.4: The Brand and Design Systems Owner (gatekeeper turned champion)

| | |
|---|---|
| **Role in deal** | Gatekeeper, and often the best champion for the 2.0 generative features. |
| **Titles (estimate)** | Head of Brand, Head of Design Systems, Design Operations Lead, Frontend Platform Lead. |

**Wants.** Every page on brand. Components reused, not reinvented. No AI-written markup.

**Fears.** Off-brand pages, accessibility regressions, a tool that undermines the design
system.

**What they will ask.**

| Question | Answer |
|---|---|
| "Does AI write HTML or CSS?" | No. The model writes a plan that picks components and fills props. It never writes markup or styles (FR-PLAN-01). |
| "Which components can it use?" | Only those in the manifest, with each prop marked who may fill it (FR-MAN-03). An Admin approves each version. |
| "How do we get our components in?" | Draft from your published Storybook, or wrap React components with `@fluidbuddha/components` and generate the manifest with an integrity hash (FR-CON-GX-07, UC-22). |
| "What can personalisation change?" | Only the axes you allow (density, colour scheme, motion, type scale) and only to values you list (FR-DSN-03, FR-TASTE-07). |
| "Is there any event feedback from our components?" | Not yet. Customer components cannot send events back to the agent. |

**Show them.** The manifest with a diff, the design system with tunables and the "Why this?"
explanation.

**Say.** "Your system is the only vocabulary the AI has."

**Proof they trust.** Their own component rendering inside a generated region in a staging
environment.

### Persona 7.5: The Enterprise Architect (technical evaluator)

| | |
|---|---|
| **Role in deal** | Technical evaluator for the self-hosted installation. |
| **Titles (estimate)** | Enterprise Architect, Platform Engineering Lead, Cloud Infrastructure Lead, SRE Manager. |

**Wants.** A deployment that fits the platform and can be run by a small team.

**What they will ask.**

| Question | Answer |
|---|---|
| "What does it need to run?" | One Linux host to start (4 vCPU, 8 GB RAM, 40 GB disk per the bundle's sizing): Caddy, backend, console, Postgres with pgvector, Redis and an optional TURN relay. |
| "How do we upgrade and back up?" | `upgrade.sh` runs migrations; backups include base backup plus WAL archive for point-in-time recovery and a logical dump (FR-SH-02). |
| "How does it scale?" | Stateless HTTP, Redis for shared sessions and rate limits, jobs coordinated by database locks. The recorded load test on one replica met the first-audio target at about 50 concurrent voice sessions and not at 100, so size replicas for peak. |
| "How do we monitor it?" | Prometheus metrics, alert rules with a runbook, readiness checks, optional OpenTelemetry and Sentry, and a public status page. |
| "How are generated pages delivered?" | Through `@fluidbuddha/next` or `@fluidbuddha/edge`, with fallback to your own page if FluidBuddha is slow or down (FR-PAGE-08, FR-PAGE-10). |

**Show them.** The compose file, the alert rules, the incident runbook and the SLA document.

**Say.** "It runs on one host to start, and it fails back to your own page."

### Persona 7.6: The Business Sponsor (economic buyer)

| | |
|---|---|
| **Role in deal** | Economic buyer. |
| **Titles (estimate)** | Chief Digital Officer, CMO, Head of Retail or Consumer Banking, Head of Direct Sales for an insurer. |

**Wants.** Digital sales and applications up, with controlled risk, in time for a target.

**Fears.** A reputational incident. A long project with no visible result.

**What they will ask.**

| Question | Answer |
|---|---|
| "What will we have in 90 days?" | A scoped pilot: the conversation widget on one product area, optionally generated regions on one page, with the holdout and compliance review in place. No promised lift. |
| "What do we pay?" | Enterprise and self-hosted pricing is by arrangement. Do not quote figures that are not in the code. |
| "Is it proven?" | The conversation agent is in production use in the repository's flagship profile. The generative composers are verified with test models and need a pilot to prove value. |

**Say.** "A controlled pilot with your compliance team inside the loop from the first day,
and a measured result at the end."

### How the personas fit together in ICP-7

| Stage | Who is in the room | What moves the deal |
|---|---|---|
| Discovery | Digital Head | The three limits stated up front. |
| Brand check | Brand and Design Systems Owner | A manifest and diff on their components. |
| Security review | Security Lead, Enterprise Architect | Control matrix, audit log, sandbox install. |
| Legal and compliance | Compliance and Legal Counsel | Rules, blocked questions, privacy, review feed. |
| Approval | Business Sponsor | A scoped pilot with a measured result. |

**Sequence.** Meet the Digital Head and the Brand and Design Systems Owner first. They create
momentum. Bring the Security Lead and Compliance in early, with the limits written down, so
that the review is a confirmation and not a surprise.

**Anti-persona for ICP-7.** An organisation whose policy requires every model, including
speech and embeddings, to run on its own cloud. That is not possible today.

---

## 5. Testing and correcting these personas

Personas become useful when they are corrected by real conversations. The product helps
measure some of this.

| What to test | How |
|---|---|
| Is the champion who we think it is? | Record who first replies and who attends the second meeting for the first ten opportunities in each ICP. |
| Which objections come up, in which order? | Note them per persona. Compare with the "What they will ask" tables and update the answers. |
| Which proof closes? | Track which artefact (live crawl, holdout plan, control matrix, sandbox) preceded each yes. |
| Does the message land? | Run two versions of the one-line message in outreach and compare replies. |
| Is the value real? | A holdout from day one in every pilot, with the goal agreed before purchase (FR-CON-HOLD-01). |
| Where do deals stall? | Record the stage and the gatekeeper. For ICP-7 this is likely to be the security or compliance review. |

**What would change these personas.** Measured lift in the first pilots; a plan between Free
and Growth; additional languages; user-token bindings; live-model verification of the
generative composers; formal security certification. Revisit this document after each of
those.
