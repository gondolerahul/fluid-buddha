# Website copy — World 3: Regulated enterprise (`/for/enterprise`)

> Final-draft copy for review. Structure and storyboard: [WebsitePlan.md §9](../WebsitePlan.md#9-world-3-regulated-enterprise).
> Audience: ICP-7, personas 7.1 to 7.6 in [ICPPersonas.md](../ICPPersonas.md).
> Never say: "SOC 2 certified", "compliant", "regulator-approved", the name of any regulation, or any price.

**Page title:** FluidBuddha for banks, insurers and fintechs — AI on your website, inside your rules
**Description:** An AI website agent that runs on your servers, uses your model contract and
builds pages only from components you approved.

**Nav:** Deployment · Security · Governance · Pilot · `Plan a pilot`
**Chip:** Showing the Enterprise version · Change

---

## 1. Hero

| Part | Copy |
|---|---|
| Eyebrow | `FOR BANKS, INSURERS AND FINTECHS` |
| Headline | AI on your website, **inside your rules.** |
| Role chips | I work in: `Digital` · `Security` · `Compliance` · `Brand and design` · `Architecture` · `Business` |

| Role | Sub-line | Main button | Second button |
|---|---|---|---|
| Digital (default) | Your teams decide what AI may build with, what it may say and where it may not go. | Plan a pilot | See the controls |
| Security | Here is exactly where data goes, including the parts that still leave your network. | See the data flow | Get the security documents |
| Compliance | You write the rules. The product enforces them and shows you what it did. | See the controls | Plan a pilot |
| Brand and design | Your components are the only building blocks the AI has. It never writes HTML or CSS. | See how components are approved | Plan a pilot |
| Architecture | It starts on one Linux host, and falls back to your own page if it is slow or down. | Read the deployment guide | See the data flow |
| Business | A 90-day pilot on one product area, with your compliance team reviewing from day one. | Plan a pilot | See what is proven |

## 2. Film chapters

| # | Eyebrow | Headline | Body |
|---|---|---|---|
| R1 | `01 · WHERE IT RUNS` | It runs on **your own infrastructure.** | One Linux host to start. Offline licence. No call back to us. |
| R2 | `02 · YOUR CONTRACTS` | It uses **your model contract and your sign-in system.** | Anthropic, OpenAI or Azure OpenAI. Single sign-on through your identity provider. |
| R3 | `03 · WHAT STILL LEAVES` | One thing still leaves your network. **We tell you first.** | Speech recognition, speech output and search indexing run on Google Vertex AI. |
| R4 | `04 · APPROVED PARTS` | An admin approves **every component the AI may use.** | Your own design system components, taken from your Storybook. |
| R5 | `05 · ONE CHECK` | Every page passes **the same check** before anyone sees it. | The AI chooses components and fills them in. It never writes HTML or CSS. Anything that fails is left out. |
| R6 | `06 · YOUR NUMBERS` | Prices and rates come from **your systems,** never from the AI. | You mark which fields may only be filled from your own data. |
| R7 | `07 · OFF LIMITS` | Some pages are **never touched.** | Checkout, legal and privacy pages are excluded by default. Your required notices appear on every page, unchanged. |
| R8 | `08 · THE RECORD` | Every console change **is logged.** | Generated pages go to a review queue. One click blocks a page. |
| R9 | `09 · START SMALL` | Start with one page **and a measured pilot.** | Your compliance team can review every generated page before any visitor sees it. |

## 3. Sections after the film

### 3.1 Three limits, stated first
| Limit | What it means for you |
|---|---|
| Speech and search indexing run on Google Vertex AI | This is true even when you host the product yourself and use your own model. If your policy requires every model on your own cloud, FluidBuddha is not a fit today. |
| The page-building features have been verified with test models, not yet with production traffic | We offer a pilot with a built-in comparison test, not a promised result. |
| Pages cannot yet show a signed-in customer's own data | Data on pages comes through site-level access only. |

### 3.2 Where data goes
Diagram labels.
**Inside your network:** the application · the console · the database · visitor conversations · leads · the audit log
**Your contracts:** your model provider · your identity provider
**Leaves your network:** speech recognition, speech output and search indexing (Google Vertex AI)
Note: if your own model provider fails, the product can fall back to the platform model. Ask us to discuss this if your policy does not allow it.

### 3.3 Controls
| Control | What it does |
|---|---|
| Approved components | The AI may use only components an admin has approved. Each version is approved separately. |
| Field rules | Each field is marked: the AI may write it, or it must come from your data. |
| Site rules | Rules you write override everything else the agent has been told. |
| Fixed and blocked answers | An approved answer is repeated word for word. A blocked question is never answered by the agent. |
| Excluded pages | Checkout, cart, legal, terms and privacy are excluded by default. You can add more. |
| Required notices | Content you pin appears on every generated page, unchanged. |
| Budgets | A daily limit on newly generated pages, per site and per visitor. |
| Review queue | A share of generated pages, and every page with a warning, goes to a reviewer. For a pilot the share can be 100 %. |
| Audit log | Every console change and sign-in, kept for one year, searchable, exportable. |

### 3.4 Deployment
**One host to start.**
- One Linux host: 4 vCPU, 8 GB memory, 40 GB disk.
- Supplied as a Docker Compose bundle, with an install option that needs no internet access. Speech and indexing still use Google Vertex AI.
- Backups with point-in-time recovery, and an upgrade script.
- If the licence lapses, the console becomes read-only. Visitors are not affected.
- Generated pages are served through your own site. If FluidBuddha is slow or down, your own page is served.
- One host handled about 50 voice conversations at once in our load test. Plan more capacity for higher peaks.

### 3.5 Access and security
- Single sign-on for the email domains you prove you own.
- Two-factor sign-in, which an owner can require for everyone.
- Sessions end after 60 minutes idle and 12 hours in total.
- Ten failed sign-ins lock the account for 15 minutes.
- Secrets are encrypted, with keys you can rotate.
- A quarterly access review is emailed to owners and admins.

### 3.6 Security documents
**What we can give you today.**
A control matrix, security policies, a sub-processor list and a data processing agreement
template. These are drafts. We do not hold a security certification or an audit report yet,
and we will not say that we do.
Button: **Get the security documents**

### 3.7 What your visitors can see and change
- "Why this?" shows up to three plain reasons a page was arranged the way it was.
- A preferences panel lets the visitor change or reset every setting.
- Only presentation changes: density, format, detail, tone, motion and colour scheme, within the limits your brand team sets.
- Prices are never personalised.
- Nothing is stored for a visitor unless they choose "Remember me".

### 3.8 The pilot
**Ninety days. One product area. A measured result.**
| Stage | What happens |
|---|---|
| Weeks 1 to 3 | Install in a sandbox. Your security team reviews the data flow and the audit log. |
| Weeks 3 to 6 | Your brand team approves the first components. Your compliance team writes the rules. |
| Weeks 6 to 12 | The agent runs on one product area, with a share of visitors held back for comparison and the review queue on. |
| End | You get the measured difference, its margin of error and the cost. We promise the measurement, not the outcome. |
Button: **Plan a pilot**

### 3.9 Close
**Bring your security and compliance teams to the first call.**
We will state the limits before they ask.
**Plan a pilot** · Get the security documents

## 4. FAQ (order changes with the role)

| Role first | Question | Answer |
|---|---|---|
| Digital | How do we stop it saying something we have not approved? | Your written rules override all other instructions. Approved answers are repeated exactly, and blocked questions are never answered. You should test your rules in the pilot. |
| Security | Do you call home? | No. The licence is checked on your host. |
| Security | What runs in the visitor's browser? | An isolated widget that never inserts AI-written HTML. Your own components run only from the approved bundle, and only if its integrity check passes. |
| Security | Which certifications do you hold? | None yet. We have a draft control matrix and policies, and no audit report. |
| Compliance | Can the AI quote a rate or a return? | Only from your content, with its source, and only if your rules allow it. Rates shown on pages come from your systems. |
| Compliance | Can we see what visitors were shown? | Conversations are stored with contact details hidden, for the period you set. Generated pages are sampled for review. Set the sample to 100 % if you need every page. |
| Brand and design | Does the AI write HTML or CSS? | No. It chooses from your approved components and fills in their fields. |
| Brand and design | Can our components send events back to the agent? | Not yet. |
| Architecture | How do we monitor it? | Standard metrics, alert rules with a runbook, readiness checks and a status page. |
| Business | What will we have in 90 days? | A working agent on one product area, reviewed by your own teams, and a measured result. |
| Business | What does it cost? | Enterprise and self-hosted pricing is agreed with you directly. |

## 5. Hindi showcase (home page and Controls)

| Part | Hindi |
|---|---|
| Headline | आपकी वेबसाइट पर AI, **आपके नियमों के भीतर।** |
| Sub-line (Digital) | आपकी टीमें तय करती हैं कि AI किन हिस्सों से पेज बना सकता है, क्या कह सकता है और कहाँ नहीं जा सकता। |
| R1 | यह **आपके अपने इन्फ़्रास्ट्रक्चर** पर चलता है। |
| R3 | एक चीज़ अब भी आपके नेटवर्क से बाहर जाती है। **हम यह पहले ही बता देते हैं।** |
| R4 | AI जो भी कंपोनेंट इस्तेमाल करे, **उसे पहले एक एडमिन मंज़ूर करता है।** |
| R6 | क़ीमतें और दरें **आपके सिस्टम से** आती हैं, AI से कभी नहीं। |
| R9 | एक पेज और **एक मापे हुए पायलट** से शुरू कीजिए। |
| Button | पायलट की योजना बनाइए |
