# Data Processing Agreement (template)

> **Draft for legal review.** Square-bracketed text is to be completed or
> chosen per customer. This template is written for India's Digital Personal
> Data Protection Act, 2023 ("DPDP Act") and works alongside GDPR-style terms
> for customers who need them; counsel should confirm both before use.

This Data Processing Agreement ("**DPA**") forms part of the agreement between
**[Customer legal name]** ("**Customer**") and **[FluidBuddha legal entity]**
("**FluidBuddha**") for the FluidBuddha service (the "**Agreement**").

## 1. Definitions

- **Customer Personal Data:** personal data that FluidBuddha processes on the
  Customer's behalf to provide the service — chiefly data about visitors to the
  Customer's websites (their questions, voice during a conversation, and
  details they share such as name, email and company) and about the Customer's
  console users.
- **Data Principal / Data Subject**, **Data Fiduciary / Controller**,
  **Data Processor / Processor**, **Personal Data Breach**: as defined in the
  DPDP Act (and, where applicable, GDPR).
- **Sub-processor:** a third party FluidBuddha engages to process Customer
  Personal Data.

## 2. Roles

The Customer is the Data Fiduciary (controller) and FluidBuddha the Data
Processor for Customer Personal Data. FluidBuddha processes it only on the
Customer's documented instructions — the Agreement, this DPA, and the
Customer's configuration of the service — unless law requires otherwise, in
which case FluidBuddha tells the Customer first where allowed.

## 3. Details of processing

| | |
|---|---|
| Subject matter | Providing the FluidBuddha AI agent, console, analytics and related features |
| Duration | The term of the Agreement, plus deletion per §10 |
| Nature and purpose | Answering visitors' questions by text and voice; capturing and delivering leads; analytics and insights; recap pages; actions the Customer enables (e.g. payment links, meetings) |
| Data principals | Visitors to the Customer's websites; the Customer's console users |
| Categories of data | Questions and conversation transcripts (with emails, phone and card-like numbers masked); voice audio during a conversation (not stored); lead details the visitor provides; technical data (anonymous visitor id, page, browser); console users' names, emails, sign-in records |
| Sensitive data | Not intended. The Customer won't configure the service to collect sensitive personal data. Healthcare templates refuse medical advice and don't collect health details. |

## 4. FluidBuddha's obligations

1. **Confidentiality.** People authorised to process Customer Personal Data are
   bound by confidentiality.
2. **Security.** FluidBuddha maintains the measures in **Annex A**, appropriate
   to the risk, and may update them provided protection isn't reduced.
3. **Assistance.** FluidBuddha helps the Customer respond to data principals'
   requests (access, correction, erasure, grievance) — including through the
   console's erasure and export tools — and with impact assessments and
   consultations where the Customer reasonably needs it.
4. **Breach notification.** FluidBuddha notifies the Customer of a Personal
   Data Breach affecting Customer Personal Data **without undue delay and in any
   case within 72 hours** of becoming aware, with the information available (and
   more as it becomes known), and assists the Customer with its own
   notifications to the Data Protection Board, CERT-In and data principals.
5. **Records.** FluidBuddha keeps records of its processing as required by law.

## 5. The Customer's obligations

The Customer provides the notices to and obtains any consents from its visitors
that the law requires for the processing (including a notice before visitors
use voice), configures retention and the features it enables, and ensures its
instructions are lawful.

## 6. Sub-processors

The Customer authorises the sub-processors listed at **[URL of
docs/compliance/subprocessors.md or the public page]**. FluidBuddha gives
**30 days' notice** of a new or replacement sub-processor; the Customer may
object on reasonable data-protection grounds, and if the parties can't resolve
it, terminate the affected service with a pro-rata refund. FluidBuddha imposes
data protection obligations on each sub-processor at least as protective as
this DPA and remains responsible for them.

## 7. Location and transfers

Customer Personal Data is stored in **India**. Processing outside India happens
only where a listed sub-processor's service requires it (for example, an AI
model available only in another region), in countries not restricted under the
DPDP Act, and with safeguards required by applicable law [including Standard
Contractual Clauses where GDPR applies].

## 8. Audits

FluidBuddha makes available on request the information needed to demonstrate
compliance: its SOC 2 report when available, this pack's policies, and answers
to reasonable security questionnaires (once a year). Where that isn't enough,
the Customer may audit with 30 days' notice, at its cost, during business hours,
under confidentiality, no more than once a year (unless after a breach or a
regulator's request).

## 9. Liability

As set out in the Agreement.

## 10. Return and deletion

On termination, the Customer may export its data for 30 days; FluidBuddha then
deletes Customer Personal Data, except where law requires keeping it. Backups
containing it age out within **30 days**.

---

## Annex A — Technical and organisational measures

**Access control.** Role-based access (Owner/Admin/Editor/Viewer) enforced on
the server for every console route; invitations single-use and expiring;
optional or account-required two-factor (TOTP); SSO (Google, OIDC) with domain
verification; server-side sessions with 60-minute idle and 12-hour absolute
timeouts, revocation on sign-out, password change or removal; httpOnly cookie
with CSRF protection; lockout after repeated failed sign-ins; quarterly access
reviews.

**Isolation.** Every record is scoped to its account and website; widget keys
are resolved on the server and only accepted from the website's own domain.

**Encryption.** TLS 1.2+ in transit; secrets (signing secrets, payment and SSO
keys, two-factor seeds) encrypted at rest with a separately held key; passwords
and recovery codes hashed (bcrypt / SHA-256); backups optionally encrypted.

**Minimisation.** PII masked before the model, the cache and storage;
microphone only with consent; voice audio not stored.

**Retention and erasure.** Per-website retention with automatic deletion;
visitor erasure; deletion of a website or account removes its data.

**Logging and monitoring.** Per-account audit log of changes and sign-ins (1
year); request ids; metrics and alerting; error reporting with PII scrubbed.

**Application security.** Peer-reviewed changes; automated tests; dependency
and secret scanning in CI; SSRF-safe fetching; rate limits and spend caps;
security headers.

**Availability.** Daily backups with checksums; restore drills; health checks;
documented recovery (RPO 24 h, RTO 4 h).

**People.** Confidentiality obligations; least-privilege production access with
quarterly review; security training; incident response plan.
