# Risk assessment

**Owner:** Security lead · **Review:** yearly, after major changes and incidents ·
**Version:** 1.0 (5 Nov 2026, draft)

## 1. Method

Each risk is scored for **likelihood** (1 rare – 5 almost certain) and **impact**
(1 minor – 5 severe: data breach, long outage, regulatory action). Score =
likelihood × impact. **15+** needs treatment now; **8–14** a planned
treatment; **under 8** may be accepted by Leadership. Residual scores are after
current controls. The register is reviewed yearly by the Security lead with
Leadership, who sign off accepted risks.

## 2. Register

| # | Risk | L | I | Score | Controls in place | Residual / next step | Owner |
|---|---|---|---|---|---|---|---|
| R1 | One customer sees another's data (tenant isolation bug) | 2 | 5 | 10 | Account-scoped queries; key → site resolution on the server; isolation tests; role matrix test over every route | Keep isolation tests mandatory for new routes; external pen test before GA | Engineering |
| R2 | Console account takeover (phishing, reused password) | 3 | 4 | 12 | Two-factor (can be required), SSO, lockout, session timeouts and revocation, audit of sign-ins | Encourage customers to require two-factor; consider breached-password check | Security |
| R3 | Leaked production secret | 2 | 5 | 10 | Secrets out of the repo, gitleaks in CI, encrypted stored secrets, app refuses default secrets | Secret store for production; rotation runbook test yearly | Operations |
| R4 | Prompt injection makes the agent leak data or misbehave | 3 | 3 | 9 | Grounding with citations, blocked topics, PII masking, actions need visitor confirmation and server-side price lists, medical guardrail | Red-team eval set for injections | Engineering |
| R5 | SSRF through crawling / webhooks | 2 | 4 | 8 | SSRF-safe fetcher (address checks, no redirects to private ranges) | DNS-rebinding gap: egress-restricted fetcher in production | Engineering |
| R6 | Data loss (database failure, bad migration) | 2 | 5 | 10 | Daily backups with checksums, restore drills, migrations under a lock, review | Managed PITR in production; drill quarterly | Operations |
| R7 | Outage of Vertex AI | 3 | 3 | 9 | Text fallback, enquiry form, health checks | M3-4 alternative model providers | Engineering |
| R8 | Runaway cost (abuse of a public widget) | 3 | 3 | 9 | Origin check per key, rate limits, daily spend cap, cost alerts | — accepted | Operations |
| R9 | Vulnerable dependency | 3 | 3 | 9 | pip-audit / npm audit in CI, Dependabot weekly | — accepted | Engineering |
| R10 | Insider misuse of production access | 1 | 5 | 5 | Few people with access, named accounts, quarterly reviews | Production access logging at the database | Security |
| R11 | Supplier breach (sub-processor) | 2 | 4 | 8 | Vendor reviews, DPAs, data minimisation (PII masked before models) | — accepted | Privacy |
| R12 | Regulatory non-compliance (DPDP Act, CERT-In timelines) | 2 | 4 | 8 | Retention controls, erasure, incident plan with 6 h / 72 h notices, DPA | Legal review of DPA and notices | Privacy |

## 3. Accepted exceptions

None yet.
