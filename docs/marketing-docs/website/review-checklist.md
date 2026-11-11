# Website review checklist (phase 9)

> Date: 11 November 2026. Scope: the four world pages (`/`, `/for/saas`, `/for/education`,
> `/for/enterprise`). The older pages under `(site)` (for example `/pricing`, `/demo`, `/hi`)
> were not reviewed.
> Plan: [WebsitePlan.md §12](../WebsitePlan.md#12-phases-deliverables-and-acceptance).

**Result in one line.** No blocker was found in the pages themselves. Two things were not
tested at all and are the open items before launch: Firefox and Safari, and a real phone.
Six copy lines were flagged; four were reworded after your approval and two are kept.

---

## 1. Claims check

Checked against [UseCases.md §10](../UseCases.md#10-claims-guidance-for-marketing), the "never
say" lines in the four copy documents, and your instructions (no customers, no version
numbers, people only in the Education film).

### 1.1 Rules that pass

| Rule | Result |
|---|---|
| No product version ("2.0", "new in") anywhere on the four pages | Pass |
| No customer names, logos, quotes or customer results | Pass |
| Every money or lift figure is marked as an example | Pass: "Example figures", "Example lead", "Example chart", "Example sum", "This is an example, not a result" |
| "Grounded in your content, with sources", never "zero hallucinations" | Pass: "That is a strong guardrail, not a guarantee" (default), "a guardrail, not a guarantee" (SaaS) |
| Languages: English and Hindi only | Pass: stated in the limits of all three persona pages and the default page |
| Speech and search indexing run on Google Vertex AI, stated for self-hosting | Pass: film scene 3, limits table and data-flow section on the Enterprise page; data list on the SaaS page |
| "Composes from approved components", never "AI designs your website" | Pass |
| "Prices come from your systems" | Pass, with one wording note in 1.2 |
| What is proven: test models, not production traffic; a pilot, not a promised lift | Pass: Enterprise limits table; "We do not quote a lift figure" (SaaS) |
| Signed-in customer data not covered | Pass: Enterprise limits table |
| Capacity: about 50 voice conversations on one host | Pass: Enterprise deployment list |
| Search engines see your own page; no SEO-multiplier claim | Pass |
| Enterprise: no certification, "compliant", regulator, named regulation or price | Pass: "We do not hold a security certification or an audit report yet" |
| Education: never "replaces counsellors" or "guarantees admissions"; no legal advice on minors | Pass: "It does not replace counsellors"; "review your policy … with your own legal adviser" |
| People appear only in the Education film | Pass |
| Not WhatsApp, phone or app | Pass: stated on the default and Education pages |

### 1.2 Lines flagged in the review

These were in copy you approved. **Lines 1, 2, 3 and 5 were changed to the wording in the last column on 11 November 2026**, on the pages and in the copy documents. Lines 4 and 6 are kept.

The Hindi showcase still carries the earlier meaning in two places, because no new Hindi was written: the default chapter "पेज हर विज़िटर के हिसाब से बदलता है।" (line 1) and the Education sub-line "हर पूछताछ का तुरंत जवाब…" (line 3). They need a matching Hindi line from you.

| # | Page | Line | Concern | Possible wording |
|---|---|---|---|---|
| 1 | Default | "The page **changes to fit each visitor.**" | §10 says "adapts to the visitor's segment, language and page", not "to each individual". The first visitor for a new goal also sees the default page. | "The page changes to fit the kind of visitor." |
| 2 | Default | "Prices **always** come from your own systems." | §10 asks for "prices and plans come from your systems" and warns against absolute wording. | "Prices come from your own systems." |
| 3 | Education | "**Every enquiry answered at once**, in Hindi or English" | When the answer is not on the site, the agent says so and offers the team. That is a reply, but not an answer. | "Every enquiry gets a reply at once" |
| 4 | SaaS | "The result stays valid however often you check it." | True only if the built-in test uses a method made for repeated checking. Please confirm against the product before launch. | Keep if confirmed |
| 5 | Enterprise | "…with an **air-gapped install option**." | Speech and search indexing still need Google Vertex AI, so the running product is not air-gapped. The page says this elsewhere, but this line alone can mislead. | "…with an install option that needs no internet access. Speech and indexing still use Google Vertex AI." |
| 6 | Default | Headline "Your website can **answer every visitor.**" | Reads as a capability, and the limits section qualifies it. Low risk. | Keep |

### 1.3 Not verified here

- The plan prices on the SaaS page (₹33,000, ₹1,25,000, ₹17, ₹10) were not compared with the live price list.
- The Hindi lines were taken from the copy documents as you reviewed them; no new Hindi was written or checked.

---

## 2. Accessibility check

Method: a script run in the browser on each page (`fludi-buddha-website/look/review/a11y-audit.js`),
at 1440 px and, for Education, at 390 px; plus a read of the markup. It checks structure, names,
keyboard reach and text contrast outside the film. It is not a full audit and no screen reader was used.

### 2.1 Found and fixed

| Finding | Where | Fix |
|---|---|---|
| Small grey text below 4.5 : 1 (3.5 to 4.3) | Notes, table headings, section numbers, the "Showing … version" chip, footer, on all four pages | The grey is now lighter on dark pages and darker on light pages |
| Gold text on cream below the minimum (2.4 to 2.8) | Education: gold part of headlines, eyebrows, step numbers, the large ₹ figure. Enterprise: "Change" in the chip | A deeper gold for text on light pages. Gold fills, lines and the films are unchanged. **This slightly changes the approved Education look.** |
| Film slides that are not showing could still take keyboard focus | All four films | Hidden slides are now inert |
| Heading level skipped (h2 to h4) | Education, "What parents see" | Now h3 |
| Click targets under 24 px tall | Nav links (18 px), film chapter index (10 px) | Padding added; all are 24 px or more |
| The Hindi typeface was named but not applied | All Hindi text | Fixed in phase 8 |

After the fixes the script reports no finding on any of the four pages.

### 2.2 Checked and passing

| Check | Result |
|---|---|
| One h1 per page; headings in order | Pass |
| Landmarks: header, nav, main, footer; a skip link to the content | Pass |
| Every link and button has a name; images have alt text | Pass |
| All film copy is real HTML, readable without the picture; canvases are hidden from assistive technology | Pass |
| Film chapters reachable by keyboard (chapter index buttons; `#chapter` links) | Pass |
| Role chips and language switch are buttons with pressed state | Pass |
| FAQ uses native disclosure elements | Pass |
| Visible focus ring | Pass (one global rule) |
| Hindi blocks carry `lang="hi"` | Pass |
| Reduced motion: films step instead of scrubbing, Hindi change and morph become a cross-fade | Built; **not tested with the system setting on** |
| No sideways scrolling at 390 px | Pass on all four pages |

### 2.3 Not covered

- No screen reader test (NVDA, VoiceOver, TalkBack).
- Contrast of copy that sits over the films was judged by eye from captures, not measured. Gradient gold headlines on dark pages are the same.
- On phones the labels inside the Enterprise drawings are about 8 px. The same information is in the HTML copy beside them.
- Keyboard order was not walked through by hand from start to end.

---

## 3. Cross-browser check

**Only Chromium was tested** (the built-in browser and headless Edge). Firefox and Safari are
not installed on this machine, so nothing below about them is a test result.

| Item | Chromium | Firefox and Safari (from reading the code, not tested) |
|---|---|---|
| Four pages render, no console errors, no failed requests | Pass | Not tested |
| Scroll films at 1440 px and 390 px | Pass, from still captures | Not tested |
| Morph between worlds, all identification paths | Pass (phase 3) | Not tested |
| Hindi switch | Pass | Not tested |
| WebP film frames | Pass | Supported in current versions; Safari before 14 would show only the poster |
| `inert` on hidden slides | Pass | Needs Safari 15.5 or Firefox 112; older versions fall back to the earlier behaviour |
| `svh` units for the film stage | Pass | A `vh` fallback is in place |
| Canvas letter spacing in the Enterprise drawings | Pass | Ignored by Safari before 17; labels are just set tighter |
| Frosted-glass plates (`backdrop-filter`) | Pass | Prefixed for Safari; without it the plate is a flat tint |
| Balanced headline wrapping | Pass | Ignored where unsupported |
| Drawing on the scroll event rather than on animation frames | Pass | Safari on iOS fires scroll events during momentum scrolling in current versions; this is the item most worth watching on a real iPhone |

---

## 4. Open items before launch

| # | Item | Kind |
|---|---|---|
| 1 | Test in Firefox and Safari, and on a real iPhone and a mid-range Android phone (film smoothness, memory, the phone layouts) | Not done |
| 2 | Measure page weight and load time against the budgets in the plan | Not done |
| 3 | Confirm line 4 in 1.2 against the product, and supply Hindi for the two reworded lines | Your decision |
| 4 | Finish the Hindi showcase: the lines listed in the phase 8 status still have no Hindi | Needs Hindi from you |
| 5 | "Get the security documents" has no page of its own and links to demo booking | Needs a destination |
| 6 | FAQ order does not change with the role | Not built |
| 7 | Connect the measurement events to a destination | Not done |
| 8 | Screen reader pass | Not done |
| 9 | Old pages under `(site)` still exist beside the new worlds (missing film posters, old `/hi`) | Done on 11 November 2026: rebuilt on the worlds' system, duplicates redirected ([audit](audit-2026-11-11.md) §6) |
| 10 | Nothing is committed to git | Your decision |
