# Website copy — World 1: B2B SaaS (`/for/saas`)

> Final-draft copy for review. Structure and storyboard: [WebsitePlan.md §7](../WebsitePlan.md#7-world-1-b2b-saas).
> Audience: ICP-1, personas 1.1 to 1.4 in [ICPPersonas.md](../ICPPersonas.md).
> Never say: "zero hallucinations", "guaranteed pipeline", any lift percentage, "replaces your sales team".

**Page title:** FluidBuddha for B2B SaaS — your pricing page, answering buyers
**Description:** Buyers read your pricing page at night and leave with questions. FluidBuddha
answers them from your own content and sends your team a scored lead.

**Nav:** Product · Proof · Pricing · Developers · `Try it on your site`
**Chip:** Showing the SaaS version · Change

---

## 1. Hero

| Part | Copy |
|---|---|
| Eyebrow | `FOR B2B SAAS` |
| Headline | Your pricing page gets the traffic. **Now it answers the questions.** |
| Role chips | I work in: `Growth` · `Sales` · `Engineering` · `Leadership` |

| Role | Sub-line | Main button | Second button |
|---|---|---|---|
| Growth (default) | More qualified demos from the visitors you already have, with a built-in test that shows the lift. | Try it on your site | See how the test works |
| Leadership | One more deal a quarter can pay for a year. The product measures whether you are on track. | See the business case | Try it on your site |
| Sales | It handles the first six questions. Your first call starts at the seventh. | See a scored lead | Try it on your site |
| Engineering | One script tag, about 38.6 kB, isolated from your CSS and JavaScript. | Read the install guide | See where data goes |

## 2. Film chapters

| # | Eyebrow | Headline | Body |
|---|---|---|---|
| S1 | `23:04` | A buyer is on your pricing page **with three questions.** | Your sales team is offline until morning. |
| S2 | `THE QUESTIONS` | "Does it work with our ERP? What do 40 seats cost? **Where is our data kept?**" | Today the answer is "Contact sales". Many buyers do not. |
| S3 | `IT SHOWS` | It draws **how the integration works.** | A diagram appears while it explains, built from your documentation. |
| S4 | `IT CALCULATES` | It works out the price **for their team.** | The buyer changes 40 seats to 60 and the figure updates. Prices come from your price list. *Example figures.* |
| S5 | `IT TAKES THEM THERE` | It opens your security page **at the right paragraph.** | The buyer sees your own words, not a summary. |
| S6 | `YOUR TEAM GETS THE LEAD` | A lead with a score **and what was asked.** | It arrives in Slack and in your CRM by webhook. |
| S7 | `STEP IN` | A salesperson can **join the conversation.** | They can take over the chat, or call the visitor in the browser if the visitor is using voice. |
| S8 | `THE REST OF THE BUYING TEAM` | The buyer forwards **a summary.** | It holds the answers, the diagram and the calculator. You see how many people opened it. |
| S9 | `PROVE IT` | One visitor in ten never sees it. **The difference is your lift.** | The result stays valid however often you check it. *Example chart.* |

## 3. Sections after the film

### 3.1 Try it on your own site
**Enter your website. Talk to it in a few minutes.**
We read your public pages and set up a private preview. Nothing changes on your live site.
Field: `https://yourcompany.com` · Button: **Read my site**

### 3.2 The six questions
**First sales calls keep answering the same six questions.**
| Buyer asks | What FluidBuddha does |
|---|---|
| "Does it integrate with X?" | Answers from your docs and draws the integration. |
| "What would it cost for our team?" | Builds a calculator from your price list. |
| "Where is our data kept?" | Opens your security page at the right section. |
| "How long does setup take?" | Answers from your onboarding pages, with the source. |
| "How are you different from Y?" | Shows a comparison table from your own content. |
| "Can we try it?" | Starts a trial or books a demo, after the buyer confirms. |

### 3.3 The lead your team receives
**A lead you would want to call.**
Annotated card labels: *Score out of 100, with the reasons* · *What they asked, in three lines* · *Which pages they saw* · *How many people opened the summary*
Line under the card: It goes to Slack and to your CRM through a signed webhook, Zapier or Make.

### 3.4 Prove it
**You do not have to take our word for the lift.**
1. Choose the page that means money, such as "demo booked".
2. FluidBuddha holds back one visitor in ten.
3. Both groups are measured on that page.
4. You read the difference, with its margin of error, on any day you like.
We do not quote a lift figure. Your own traffic produces it.

### 3.5 What it costs
**About ₹16.50 a conversation on Growth.**
Compare that with what you pay for one click on your main keyword.
Growth: ₹33,000 a month for 2,000 conversations, then ₹17 each. Scale: ₹1,25,000 a month for 10,000, then ₹10 each.
Example sum (marked as an example): one deal of ₹6,00,000 a year against ₹3,96,000 a year for Growth.

### 3.6 Install
**One line of code.**
`<script src="…/widget/loader.js" data-key="fbk_…" async></script>`
Also: WordPress · Shopify · Google Tag Manager · Webflow · Framer · React · Vue · Next.js
Facts: about 38.6 kB core script · runs in its own isolated container, so it cannot change your styles · every setting is in the console, so the tag never needs editing again

### 3.7 Where data goes
- Emails, phone numbers and card numbers are hidden before the AI sees them.
- The microphone is off until the visitor agrees.
- You set how long conversations are kept, and can delete one person's data by email.
- Speech and search indexing run on Google Vertex AI.
- Names and street addresses are not hidden automatically.

### 3.8 What it does not do
- English and Hindi only. Buyers who need other languages are not served yet.
- No built-in CRM connectors. Leads go out by signed webhook, Zapier, Make and Slack.
- It does not replace your sales team. It gets buyers to them sooner.

### 3.9 Close
**Put it on your pricing page first.**
**Try it on your site** · Book a demo

## 4. FAQ (order changes with the role)

| Role first | Question | Answer |
|---|---|---|
| Growth | Will it make things up? | It answers from your content and shows sources. When it cannot find an answer it says so. This is a guardrail, not a guarantee. |
| Growth | Can it hurt our SEO? | No. The agent does not change your pages. If you add fitted page sections later, search engines still see your own content. |
| Leadership | What if it says something wrong about us? | You can write rules it must follow, fix an approved answer so it is always used, and block questions it must not answer. |
| Leadership | What is the risk if it does not work? | The Free plan covers 100 conversations. Growth is monthly. The test shows early whether it is working. |
| Sales | Will it send me junk leads? | Each lead has a score with its reasons and a summary of what was asked. |
| Sales | Can I talk to someone who is on the site now? | Yes. You can see live conversations, take one over and hand it back. |
| Engineering | Will it clash with our CSS or JavaScript? | No. It runs in an isolated container (Shadow DOM). |
| Engineering | Which languages? | English and Hindi only. |

## 5. Hindi showcase (home page)

| Part | Hindi |
|---|---|
| Headline | आपके प्राइसिंग पेज पर ट्रैफ़िक आता है। **अब वह सवालों के जवाब भी देता है।** |
| Sub-line (Growth) | जो विज़िटर पहले से आ रहे हैं, उन्हीं से ज़्यादा अच्छे डेमो, और एक टेस्ट जो फ़र्क़ दिखाता है। |
| S1 | रात 11:04। एक ख़रीदार आपके प्राइसिंग पेज पर है, **तीन सवालों के साथ।** |
| S3 | यह बनाकर दिखाता है कि **इंटीग्रेशन कैसे काम करता है।** |
| S4 | यह **उनकी टीम के हिसाब से** क़ीमत निकालता है। |
| S6 | आपकी टीम को लीड मिलती है, **स्कोर और पूछे गए सवालों के साथ।** |
| S9 | दस में से एक विज़िटर इसे नहीं देखता। **यही फ़र्क़ आपकी बढ़त है।** |
| Button | अपनी साइट पर आज़माएँ |
