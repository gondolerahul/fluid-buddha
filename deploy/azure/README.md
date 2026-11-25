# FluidBuddha production on Azure

One VM in Central India runs the whole product with Docker Compose. The plan, the owner's steps and the
runbook are in [docs/deployment](../../docs/deployment/README.md).

| Path | What it is |
|---|---|
| `infra/main.bicep`, `infra/modules/` | Everything in Azure: two resource groups (`rg-fb-<env>-core`, `rg-fb-<env>-data`), network, firewall, VM, registry, Key Vault, backup storage, GitHub identities, alerts, budget |
| `infra/provision.ps1` | Runs the Bicep: preflight checks, a what-if preview (`-Preview`), then the deployment and its outputs |
| `infra/cloud-init.yaml`, `infra/bootstrap.sh` | The VM's first boot: Docker, the Azure CLI, swap, updates, folders, the metadata-service firewall |
| `docker-compose.yml` | The stack: edge (Caddy), backend, console, website, postgres, redis, coturn |
| `Caddyfile` | TLS and routing for the four names |
| `prod.env` | The backend's non-secret settings. Secrets come from Key Vault at deploy time. |
| `release.Dockerfile` | Packs this folder (minus `infra/` and `ci/`) as the release bundle image, versioned with the code |
| `vm/fluidbuddha-deploy` | The deploy on the VM: render settings from Key Vault, pre-deploy dump, start, health checks, automatic rollback |
| `vm/fluidbuddha` | The operator's command on the VM: `deploy`, `status`, `logs`, `compose`, `psql`, `backup`, `restore`, `watchdog` |
| `vm/bin/` | Backups to Blob storage, restores and point-in-time recovery, the watchdog |
| `vm/systemd/` | Timers: nightly backup, WAL upload every 15 minutes, watchdog every 15 minutes |
| `ci/` | Used by `.github/workflows/release.yml`: the Run Command deploy and the public checks |

CI validates all of it (job `azure` in `.github/workflows/ci.yml`). Releases go through
`.github/workflows/release.yml`.
