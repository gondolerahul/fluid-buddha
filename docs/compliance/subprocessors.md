# Sub-processors

**Owner:** Privacy lead · **Last updated:** 5 November 2026 (draft)

Suppliers that may process customer data (Customer Personal Data as defined in
the [DPA](dpa-template.md)) to provide FluidBuddha. Customers are told **30
days** before a new one is added.

| Sub-processor | Purpose | Data | Location |
|---|---|---|---|
| **Google Cloud** (Vertex AI: Gemini models, speech-to-text, text-to-speech, embeddings) | Understanding questions, generating answers, voice | Visitors' questions (PII masked before sending), voice audio during a conversation, the customer's website content | India (asia-south1) where the service is available; otherwise the region configured, see note |
| **Hosting provider** _(to name at deployment)_ | Servers, managed Postgres and Redis, backups | Everything the service stores | India |
| **Razorpay** | Billing for FluidBuddha plans; payment links customers enable for their own visitors (customer's own Razorpay account) | Customer billing contact and payment details (held by Razorpay); for payment actions, the visitor's name, email and amount | India |
| **SMTP provider** _(to name at deployment)_ | Invitations, digests, recap emails, access reviews, quote requests | Recipient email addresses and the email content | _to confirm_ |
| **Sentry** _(optional, only if `SENTRY_DSN` is set)_ | Error reports | Stack traces with PII scrubbed | _per Sentry region chosen_ |

**Not sub-processors, but customer-chosen destinations:** Slack, webhook
endpoints, Calendly/Cal.com, a customer's own backend for trial provisioning.
Data goes there only when the customer configures it, and under the customer's
own agreement with that service.

**Model providers chosen by the customer** (M3-4, bring your own model:
Anthropic, OpenAI, Azure OpenAI) process data under the customer's own contract
with them.

_Note on regions:_ some Vertex AI models and voices may only be offered from
regions outside India; the deployment's `VERTEX_LOCATION` determines this.
Confirm and record the actual region before signing DPAs.
