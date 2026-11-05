# Change management policy

**Owner:** Engineering lead · **Review:** yearly · **Version:** 1.0 (5 Nov 2026, draft)

## 1. Scope

Every change to the code in this repository, to the production configuration,
and to the database schema.

## 2. The normal path

1. **Branch.** Work happens on a branch, never directly on `main`.
2. **Commit.** One workstream per commit, with a message that explains why.
   New behaviour comes with tests (backend pytest, SDK smoke checks, wrapper
   tests); the console's gate is lint + typecheck + build + a live check.
3. **Pull request.** Every change reaches `main` through a pull request
   reviewed and approved by someone other than its author.
4. **CI must pass** (`.github/workflows/ci.yml`):
   - backend tests, twice (reruns must be deterministic), `pip-audit`;
   - SDK typecheck, build, smoke tests (including the widget size budget), `npm audit`;
   - console lint, typecheck, build, `npm audit`;
   - integrations: wrapper tests, Shopify embed, WordPress plugin lint and tests;
   - **secret scanning** of the whole history (gitleaks).
5. **Branch protection on `main`** (set in GitHub → Settings → Branches):
   require a pull request, at least one approval, the CI checks above, and no
   force pushes. _Action for the repository owner: enable this._
6. **Release.** Deployment is from `main`. Database migrations (Alembic) run
   automatically at start-up under an advisory lock, so replicas never race.
   A committed migration is never edited; a fix is a new migration.
7. **Verify** after deploying: `/health` and `/ready`, error rate and time to
   first audio on the metrics dashboard.

## 3. Dependencies

Dependabot (`.github/dependabot.yml`) opens weekly update PRs for pip, npm and
GitHub Actions. They go through the same review and CI. Known high-severity
vulnerabilities fail CI on every push.

## 4. Configuration changes

Production settings (`.env` / secret store) are changed by the Operations lead,
recorded in the change log of the deployment repository or ticket with who,
what and why. Secrets are rotated by adding the new key first
(`SECRETS_KEY` accepts several, newest first), then removing the old one.

## 5. Emergency changes

When production is down or under attack, a fix may be deployed before review.
Within one working day it gets a pull request, a reviewer, and a note in the
incident record explaining the emergency.

## 6. Customer-visible changes

Breaking changes to the widget, the install surfaces or the API are announced
to customers at least 30 days ahead, except for security fixes.

## 7. Evidence

Pull requests with approvals and CI results; the Git history; Dependabot PRs;
deployment logs; the incident log for emergency changes.
