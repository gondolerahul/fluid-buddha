# Access control policy

**Owner:** Security lead · **Review:** yearly · **Version:** 1.0 (5 Nov 2026, draft)

Two kinds of access are covered: **customer access** to their account in the
FluidBuddha console, and **internal access** by our own team to production
systems.

## 1. Customer access (the product)

| Control | How it works |
|---|---|
| Unique identities | One login per person (email); people are separate from accounts and can belong to several. |
| Roles | Owner, Admin, Editor, Viewer, each including the ones below. Enforced on the server for every `/tenant` route from one rule table (`backend/app/auth/roles.py`); a test walks every route so a new one can't skip it. |
| Least privilege | Billing changes and SSO: Owner. Team, integrations (signing secrets), payment keys, privacy, deleting a site: Admin. Content and behaviour: Editor. Read-only: Viewer. |
| Joining | By invitation only: single use, expires in 7 days, token stored hashed. Or just-in-time through the account's own SSO for email domains the account proved with DNS. |
| Leaving | Removing a member ends their sessions in that account at once. |
| Two-factor | Any person can turn on TOTP; an Owner can require it for the whole account. Password sessions without it can only reach the two-factor setup. SSO sign-ins rely on the identity provider's two-factor. Recovery codes: ten, single use, stored hashed. |
| SSO | Google and any OIDC provider (PKCE, signed ID tokens checked against the provider's keys). "Require SSO" stops password sign-ins for the account's domains; the Owner keeps a password as break-glass. |
| Sessions | Server-side; end after 60 minutes idle, 12 hours absolute, on sign-out, "sign out everywhere" or a password change. The console keeps the session in an httpOnly cookie with CSRF protection. |
| Brute force | 10 wrong passwords or codes in a row lock the person out for 15 minutes; each failure is in the audit log. |
| Passwords | At least 8 characters; bcrypt (over SHA-256) hashes; changing a password signs out every other session. |
| Audit | Sign-ins, failed sign-ins, two-factor changes, session revocations, password changes and every console change are logged per account (who, what, when, IP, request id), kept a year, exportable as CSV. |
| Reviews | Each quarter Owners and Admins receive an access summary; the full list downloads as CSV from the Team page. Customers keep it as their own evidence. |

Settings live in `backend/.env` (`SESSION_*`, `LOGIN_*`).

## 2. Internal access (our team)

| Control | Requirement |
|---|---|
| Accounts | Named accounts only; no shared logins. Every provider (cloud, GitHub, Razorpay, SMTP, Google Cloud) uses SSO or a password manager plus two-factor. |
| Production | Production database, servers and secrets: Operations lead and Engineering lead only. Access is granted by the Security lead and recorded. |
| Customer data | Staff don't open customer data except to support that customer at their request or to handle an incident; the reason is recorded in the support ticket or incident log. |
| Secrets | In the deployment's secret store / `.env` on the server, never in the repository (CI scans every commit with gitleaks). `JWT_SECRET` and `SECRETS_KEY` are generated per environment; the app refuses to start outside dev with the default. |
| Joiners | Access requested by their manager, approved by the Security lead, granted on the day it's needed. |
| Leavers | All access removed on their last day (checklist: GitHub, cloud, database, Razorpay, SMTP, password manager, Slack). |
| Reviews | Quarterly: the Security lead reviews every internal account and production credential, removes what isn't needed, and records the review. |
| Devices | Disk encryption, screen lock, supported OS with updates ([acceptable use](acceptable-use-policy.md)). |

## 3. Evidence

- Role rules and tests: `backend/app/auth/roles.py`, `backend/tests/test_teams.py`.
- Two-factor, sessions, lockout, cookie/CSRF, access review: `backend/tests/test_security.py`.
- Audit log export from the console; quarterly access-review emails (`email_outbox`, kind `access_review`).
- Internal quarterly review records (kept by the Security lead).
