# SOC 2 control matrix

**Owner:** Security lead · **Version:** 1.0 (5 Nov 2026, draft) · Trust Services
Criteria (2017, revised points of focus 2022): Security (Common Criteria),
Availability, Confidentiality.

Each row: the criterion, how FluidBuddha meets it, who owns it, the policy, and
the evidence an auditor (or Vanta / Drata) collects. "Code" evidence is in this
repository; "Record" evidence is produced while operating and kept by the owner.

Owners: **SEC** Security lead · **ENG** Engineering lead · **OPS** Operations
lead · **PRIV** Privacy lead · **LEAD** Leadership.

## CC1 — Control environment

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC1.1 Integrity and ethics | Acceptable use policy accepted at joining and yearly | SEC | [Acceptable use](acceptable-use-policy.md) | Record: signed acknowledgements |
| CC1.2 Board oversight | Leadership approves policies and accepted risks yearly | LEAD | [InfoSec policy](information-security-policy.md) | Record: approval minutes |
| CC1.3 Structure and authority | Roles defined for security, engineering, operations, privacy | LEAD | [README](README.md) | Doc: roles table filled in |
| CC1.4 Competence | Security awareness training at joining and yearly | SEC | [InfoSec policy](information-security-policy.md) §3 | Record: training completions |
| CC1.5 Accountability | Policy breaches handled; owners named per control | LEAD | [InfoSec policy](information-security-policy.md) §6 | This matrix; records |

## CC2 — Communication and information

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC2.1 Quality information | Audit log of changes and sign-ins; metrics; request ids in every log line | ENG | [Access control](access-control-policy.md) | Code: `backend/app/audit.py`, `app/observability/`; console Audit log |
| CC2.2 Internal communication | Policies in the repository; incident reporting channel | SEC | [Incident plan](incident-response-plan.md) | Doc: this pack |
| CC2.3 External communication | DPA, sub-processor list with 30-day notice, security contact | PRIV | [DPA](dpa-template.md), [Sub-processors](subprocessors.md) | Doc; record: customer notices |

## CC3 — Risk assessment

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC3.1 Objectives | Security objectives in the InfoSec policy | SEC | [InfoSec policy](information-security-policy.md) | Doc |
| CC3.2 Risk identification | Risk register scored and reviewed yearly | SEC | [Risk assessment](risk-assessment.md) | Doc: register with review dates |
| CC3.3 Fraud risk | Insider and abuse risks in the register (R8, R10); spend caps, rate limits | SEC | [Risk assessment](risk-assessment.md) | Code: `app/tenancy/public_access.py` |
| CC3.4 Change in risk | Register reviewed after major changes and incidents | SEC | [Risk assessment](risk-assessment.md) | Record: review notes |

## CC4 — Monitoring

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC4.1 Ongoing evaluation | CI on every push; quarterly access reviews; quarterly restore drills | SEC | [Change mgmt](change-management-policy.md), [Continuity](business-continuity.md) | Record: CI runs, `drills/*.json`, review CSVs |
| CC4.2 Deficiencies | Post-incident reviews with tracked actions | SEC | [Incident plan](incident-response-plan.md) §4.6 | Record: post-incident reports |

## CC5 — Control activities

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC5.1 Selection of controls | Controls chosen against the register; this matrix | SEC | [Risk assessment](risk-assessment.md) | This matrix |
| CC5.2 Technology controls | Automated tests, role matrix test over every route, security tests | ENG | [Change mgmt](change-management-policy.md) | Code: `backend/tests/test_teams.py`, `test_security.py` |
| CC5.3 Policies deployed | Policies approved and published to staff | LEAD | [README](README.md) | Record: approvals |

## CC6 — Logical and physical access

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC6.1 Access security | Roles enforced centrally; account isolation; widget keys bound to domains; secrets encrypted with `SECRETS_KEY` | ENG | [Access control](access-control-policy.md) | Code: `app/auth/roles.py`, `app/security/secrets.py`, migration `0024_security`; tests |
| CC6.1 Authentication | Two-factor (TOTP) optional or account-required; SSO (OIDC/PKCE); bcrypt passwords; lockout after 10 failures | ENG | [Access control](access-control-policy.md) | Code: `app/auth/mfa.py`, `app/auth/sso.py`, `app/routes/auth.py`; `tests/test_security.py` |
| CC6.1 Sessions | Server-side sessions, 60 min idle / 12 h absolute, revocable; httpOnly Secure cookie + CSRF | ENG | [Access control](access-control-policy.md) | Code: `app/auth/sessions.py`; `tests/test_security.py` |
| CC6.2 Provisioning | Invitations (single use, 7 days, hashed), SSO just-in-time for verified domains; internal access approved by SEC | SEC | [Access control](access-control-policy.md) | Audit log `invitation.accept`; record: internal access requests |
| CC6.3 Changes and removal | Removing a member ends their sessions; role changes take effect on the next request; leaver checklist | SEC | [Access control](access-control-policy.md) | Code + audit log; record: leaver checklists |
| CC6.3 Periodic review | Quarterly access-review email + CSV for customers; quarterly internal review | SEC | [Access control](access-control-policy.md) | `email_outbox` kind `access_review`; `/tenant/team/access-review.csv`; record: internal review |
| CC6.4 Physical access | Hosting provider's data centres (inherited) | OPS | [Vendor mgmt](vendor-management-policy.md) | Provider's SOC 2 report |
| CC6.5 Disposal | Retention sweeps; deletion cascade; backup pruning | PRIV | [Retention](data-classification-retention.md) | Code: `app/trust/retention.py`, `scripts/backup.sh` |
| CC6.6 External threats | Origin checks, rate limits, spend caps, SSRF-safe fetching, security headers, TLS | ENG | [InfoSec policy](information-security-policy.md) | Code: `app/tenancy/`, `app/security/headers.py`, console `next.config.ts` |
| CC6.7 Data in transit | TLS everywhere; HSTS outside dev; signed webhooks | OPS | [InfoSec policy](information-security-policy.md) | Config; `app/leads/delivery.py` |
| CC6.8 Malicious software | Dependency audits in CI, Dependabot, managed devices | ENG | [Change mgmt](change-management-policy.md), [AUP](acceptable-use-policy.md) | CI logs; `.github/dependabot.yml` |

## CC7 — System operations

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC7.1 Vulnerability detection | `pip-audit` / `npm audit` in CI; gitleaks secret scanning; Dependabot | ENG | [Change mgmt](change-management-policy.md) | `.github/workflows/ci.yml`, `.gitleaks.toml` |
| CC7.2 Anomaly monitoring | Prometheus metrics (errors, latency, cost), cost alerts, failed sign-ins in the audit log | OPS | [Incident plan](incident-response-plan.md) | `/metrics`; alert rules (M3-6); audit log |
| CC7.3 Evaluate events | Severity levels and triage | SEC | [Incident plan](incident-response-plan.md) §2 | Record: incident log |
| CC7.4 Respond | Containment playbook (key rotation, session revocation…), notices within 72 h / CERT-In 6 h | SEC | [Incident plan](incident-response-plan.md) | Record: incident reports |
| CC7.5 Recover | Restore runbook; post-incident review | OPS | [Continuity](business-continuity.md) | Record: drills, reviews |

## CC8 — Change management

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC8.1 Change authorisation and testing | PR review by someone else; CI must pass; branch protection; migrations reviewed and never edited | ENG | [Change mgmt](change-management-policy.md) | GitHub PRs and checks; branch protection settings; `backend/migrations/` |

## CC9 — Risk mitigation

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| CC9.1 Business disruption | Backups, restore drills, RPO/RTO, dependency fallbacks | OPS | [Continuity](business-continuity.md) | `backup-log.jsonl`, `drills/*.json` |
| CC9.2 Vendors | Vendor reviews, DPAs, sub-processor list | OPS / PRIV | [Vendor mgmt](vendor-management-policy.md) | Vendor register; DPAs |

## A1 — Availability

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| A1.1 Capacity | Metrics on load and latency; horizontal replicas with Redis | OPS | [Continuity](business-continuity.md) | `/metrics`; deployment config |
| A1.2 Backups and environment | Daily encrypted backups off-site; checksums; retention | OPS | [Continuity](business-continuity.md) | `scripts/backup.sh`, `backup-log.jsonl` |
| A1.3 Recovery testing | Quarterly restore drills | OPS | [Continuity](business-continuity.md) | `scripts/restore_drill.sh`, `drills/*.json` |

## C1 — Confidentiality

| Criterion | Control | Owner | Policy | Evidence |
|---|---|---|---|---|
| C1.1 Identify and protect | Data classes; PII masking; encryption of secrets; account isolation | PRIV | [Retention](data-classification-retention.md) | Code: `app/trust/pii.py`, `app/security/secrets.py` |
| C1.2 Disposal | Retention per website; erasure; deletion cascade | PRIV | [Retention](data-classification-retention.md) | Code: `app/trust/retention.py`; Privacy tab |

## Open items before an audit

1. Fill in the named owners ([README](README.md)) and get policies approved.
2. Enable branch protection on `main` in GitHub.
3. Production: secret store, daily off-site encrypted backups, managed PITR,
   alert rules on the metrics (M3-6), a status page.
4. Start the records: training, quarterly access reviews (internal), restore
   drills, vendor register, incident log.
5. Engage an auditor (and optionally Vanta/Drata); legal review of the DPA.
