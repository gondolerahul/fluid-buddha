# Information security policy

**Owner:** Security lead · **Approved by:** Leadership · **Review:** yearly ·
**Version:** 1.0 (5 Nov 2026, draft)

## 1. Purpose and scope

FluidBuddha runs an AI sales agent that businesses embed on their websites. Our
customers trust us with their content, their visitors' questions and the leads
those visitors become. This policy sets how we protect that information and the
systems that hold it.

It covers everyone who works on FluidBuddha (employees, contractors), every
system that stores or processes customer data (the backend, its database and
Redis, the console, the widget, backups, logs) and every supplier that touches
that data ([sub-processors](subprocessors.md)).

## 2. Principles

1. **Least privilege.** People and services get the access their work needs,
   no more ([access control](access-control-policy.md)).
2. **Isolation between customers.** Every query is scoped to the account and
   website it belongs to; a widget key only works on its own domain.
3. **Minimise and mask.** Visitors' personal data is masked before it reaches
   the model or storage; we keep data only as long as the customer's retention
   settings say ([data classification and retention](data-classification-retention.md)).
4. **Encrypt.** TLS for everything in transit; stored secrets encrypted with a
   key held outside the database; backups optionally encrypted.
5. **Every change reviewed and tested** ([change management](change-management-policy.md)).
6. **Record and watch.** Console changes and sign-ins go in a per-account audit
   log; the platform exports metrics and alerts on errors and spend.
7. **Plan for failure** ([incident response](incident-response-plan.md),
   [continuity](business-continuity.md)).

## 3. Responsibilities

The roles are listed in the [pack's README](README.md). In addition, everyone:

- follows the [acceptable use policy](acceptable-use-policy.md);
- reports a suspected incident immediately (see the incident plan);
- completes security awareness training when they join and yearly.

## 4. Key controls (summary)

| Area | Control | Where |
|---|---|---|
| Identity | Roles (Owner/Admin/Editor/Viewer) enforced on every console route | `backend/app/auth/roles.py` |
| Identity | Two-factor (TOTP), account-wide requirement, SSO (Google/OIDC) | `backend/app/auth/mfa.py`, `sso.py` |
| Sessions | Server-side sessions, 60 min idle / 12 h absolute, revocable; httpOnly cookie + CSRF | `backend/app/auth/sessions.py` |
| Sign-in | Lockout after 10 wrong passwords or codes | `backend/app/routes/auth.py` |
| Audit | Per-account audit log of changes and sign-ins, 1 year | `backend/app/audit.py` |
| Data | PII masking, retention sweep, visitor erasure | `backend/app/trust/` |
| Secrets | Fernet encryption with `SECRETS_KEY` (rotatable) | `backend/app/security/secrets.py` |
| Public surface | Origin checks, rate limits, spend caps, SSRF-safe fetching | `backend/app/tenancy/` |
| Change | PR review, CI (tests, audits, secret scanning), Dependabot | `.github/` |
| Availability | Backups with checksums, restore drills, health checks, metrics | `backend/scripts/`, `/health`, `/metrics` |
| Web | Security headers on API and console | `backend/app/security/headers.py`, console `next.config.ts` |

## 5. Exceptions

An exception to any policy is requested from the Security lead in writing, with
the reason, the risk, compensating controls and an end date. Approved
exceptions are listed in the [risk register](risk-assessment.md).

## 6. Enforcement

Breaching a policy may lead to losing access and disciplinary action. Breaches
by suppliers are handled under their contract.

## Change log

| Date | Version | Change |
|---|---|---|
| 2026-11-05 | 1.0 | First version (M2-11) |
