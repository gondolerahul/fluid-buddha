# Deployment

How FluidBuddha runs in production. Start here.

| Document | For | Covers |
|---|---|---|
| [azure-production-plan.md](azure-production-plan.md) | Everyone | Architecture, decisions, resources, secrets, release flow, backups, security, monitoring, costs, risks, and the phased plan with owners |
| [azure-operator-guide.md](azure-operator-guide.md) | The account owner | The steps only the account owner can do (Google Cloud, Microsoft 365, GoDaddy, GitHub, secrets) and the go-live checks |
| [azure-runbook.md](azure-runbook.md) | Whoever is on call | Deploy, roll back, back up, restore, point-in-time recovery, rotate secrets, resize, rebuild, troubleshooting |
| [azure-launch-record.md](azure-launch-record.md) | Anyone rebuilding or adding an environment | What is live, the launch sequence of 26 November 2026, every problem hit and its fix, what is still open |

Production: a single Azure VM in Central India serving `fluidbuddha.com`, `app.fluidbuddha.com` and
`gateway.fluidbuddha.com`, with AI on Google Vertex AI (`us-central1`) and email through Microsoft 365. Dev and
staging come later from the same templates. The code is in [`deploy/azure`](../../deploy/azure/README.md).

## Status

| Phase | Owner | Status |
|---|---|---|
| 0. Prerequisites | Account owner + Eng | Done |
| 1. Build the deployment (PR) | Eng | Done, merged to `main` |
| 2. Provision Azure | Eng, with the account owner's approval | Done, 26 November. The VM is Standard_B2s_v2: Central India had no capacity for B2as_v2. |
| 3. Configure secrets and DNS | Account owner | Done, 26 November |
| 4. First deploy and checks | Together | Done, 26 November: all names on HTTPS, `/readyz` green, STUN answers, first backups in Blob, restore drill passed |
| 5. Go live, website integration | Together | Widget live on `fluidbuddha.com` (release `bba3010`). Open: the owner's end-to-end tests, uptime monitors, two-step sign-in |
| 6. First two weeks | Together | Not started |

Related: [incident runbook](../operations/incident-runbook.md), [SLA](../operations/sla.md), and the
customer self-hosted stack in [`deploy/selfhost`](../../deploy/selfhost/README.md).
