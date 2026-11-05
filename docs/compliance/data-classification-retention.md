# Data classification and retention

**Owner:** Privacy lead · **Review:** yearly · **Version:** 1.0 (5 Nov 2026, draft)

## 1. Classes

| Class | Meaning | Examples | Handling |
|---|---|---|---|
| **Restricted** | Would cause serious harm if exposed | Passwords (hashes), two-factor seeds, session tokens, `JWT_SECRET`, `SECRETS_KEY`, payment keys, webhook signing secrets, SSO client secrets, backups | Encrypted at rest (secrets with `SECRETS_KEY`; hashes for passwords and recovery codes); never logged; production access limited to named people |
| **Confidential** | Customer and visitor data | Visitors' questions and transcripts (PII masked), leads (name, email, company), recaps, insights, customer knowledge base, audit log | Isolated per account; TLS in transit; retained per §3; deleted on request |
| **Internal** | Our own operational data | Metrics, aggregated usage and cost, non-customer logs | Staff only |
| **Public** | Meant to be public | Widget keys (they ship in page source), the widget code, marketing site, `llms.txt` | No restriction |

## 2. Personal data minimisation

- PII in what visitors say (emails, phone numbers, card-like numbers…) is
  masked before it reaches the model, the cache, transcripts or insights; a
  lead still gets the real email the visitor typed into it.
- Microphone use only after the visitor agrees (enforced on the server).
- Recap links show the masked conversation unless the visitor entered the data.
- Logs carry request ids, not message bodies; error reports scrub PII.

## 3. Retention

| Data | Kept for | Mechanism |
|---|---|---|
| Conversations, transcripts, turns, insights labels | Per website setting (Privacy tab), default 365 days | Hourly retention sweep (`backend/app/trust/retention.py`) |
| Leads | Per website setting, default 730 days | Retention sweep |
| Recap pages | Per website setting, 7–365 days, default 90 | Expiry sweep |
| Action runs | With their conversation | Retention sweep |
| Audit log | 1 year | Daily job |
| Email outbox | 30 days after sending | Daily job |
| Console sessions | 30 days after they end | Daily job |
| Backups | 30 days (`RETENTION_DAYS`) | `backup.sh` pruning |
| Deleted account / website | Removed at once with everything under it; gone from backups when they age out | Deletion cascade |

## 4. Requests

- **Visitor erasure:** the customer erases a visitor's data from the Privacy tab
  (by visitor id or email); it removes conversations, leads, recaps and runs.
- **Customer export / deletion:** on request through support; deleting a
  website or account removes its data immediately.
- Requests are answered within 30 days (sooner where law requires).

## 5. Known gaps

- Names and street addresses aren't detected by the masking yet (pattern-based).
- The agent's long-term (CORTEX episodic) memory isn't covered by the per-site
  retention setting yet (planned with M3-3 visitor memory).
