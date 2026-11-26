# Runbook: FluidBuddha production on Azure

How to operate the single-VM production described in [azure-production-plan.md](azure-production-plan.md).
For incidents in general (severity, communication), see the [incident runbook](../operations/incident-runbook.md).

## At a glance

| What | Where |
|---|---|
| VM | `vm-fb-prod-01` in `rg-fb-prod-core` (Central India). Ubuntu 24.04, 2 vCPU / 8 GiB. |
| Secrets | Key Vault `kv-fb-prod-<sfx>` in `rg-fb-prod-data` |
| Backups | Storage account `stfbprodbk<sfx>`, container `backups`: `dumps/`, `base/`, `wal/` |
| Images | Registry `acrfbprod<sfx>`: `fluidbuddha/{backend,console,website,edge,release}:<sha>` |
| On the VM | `/opt/fluidbuddha`: `releases/<sha>/`, `current` (the live release), `.env`, `backend.env`, `turnserver.conf`, `secrets/`, `data/postgres`, `data/caddy`, `backups/` |
| Logs | `fluidbuddha logs [service]`; deploy logs in `/var/log/fluidbuddha/`; timers in `journalctl -u fluidbuddha-*` |
| State | `/var/lib/fluidbuddha/`: last backup times, alert state, `releases.log` |

Every operation below goes through the `fluidbuddha` command on the VM (installed by each deploy). Names
with `<sfx>` are in the provisioning outputs (`deploy/azure/infra/outputs.prod.json`).

## Getting onto the VM

**Run Command** (no SSH needed; your Azure login is enough). From PowerShell on your machine:

```powershell
az vm run-command invoke -g rg-fb-prod-core -n vm-fb-prod-01 --command-id RunShellScript --scripts "fluidbuddha status" --query "value[0].message" -o tsv
```

Replace `fluidbuddha status` with any command below. Run Command shows the last 4 KB of output and runs one
command at a time; long jobs belong in SSH.

**SSH**, from the address allowed in `nsg-fb-prod-app` (rule `ssh-operator`):

```powershell
ssh -i "$env:USERPROFILE\.ssh\fluidbuddha_prod" fbadmin@<PUBLIC_IP>
```

**Serial console**, when the VM doesn't answer at all: Portal → `vm-fb-prod-01` → Help → Serial console
(boot diagnostics are on).

## Deploy and roll back

- **Deploy:** GitHub → Actions → **Release** → Run workflow from `main` with the commit (default `main`).
  Approve the "production" step when it pauses.
- **Roll back:** the same, with an older commit. The images for the last 10 releases are still in the
  registry; older ones are rebuilt from that commit.
- **On the VM:** `sudo fluidbuddha deploy <full sha>` does the same thing, without GitHub.
- **Automatic rollback:** when a new release fails its health checks, the deploy starts the previous release
  again and the workflow fails. Read the log it prints (the full log is in `/var/log/fluidbuddha/`).
- **Migrations:** they run forward when the backend starts. If a release migrated the schema and then had to
  roll back, the older code may not run on the new schema. Then restore the pre-deploy dump (below), which
  every deploy takes first.
- **Apply a changed secret:** edit it in Key Vault, then run Release with the commit that is live now.
- **Change the website's widget key:** set the GitHub repository variable `NEXT_PUBLIC_FB_KEY` to the new
  `fbk_…` (it is public, so a variable, not a secret), then run Release with the commit that is live now. The
  website image is rebuilt even for the same commit, because the key is baked in at build time.
- **Which release is live:** `fluidbuddha status` on the VM, or the newest green run under Actions → Release.

## Status and logs

```
fluidbuddha status                 live release, containers, disk, memory, last backups and drills
fluidbuddha logs backend           follow one service (edge, backend, console, website, postgres, redis, coturn)
fluidbuddha compose ps             anything docker compose can do, for the live release
fluidbuddha psql                   a database shell
fluidbuddha watchdog               run the watchdog's checks now
```

`https://gateway.fluidbuddha.com/readyz` shows every dependency; `/status` is the public status page.

## Backups

| What | When | Kept on the VM | Kept in Blob |
|---|---|---|---|
| Dump (`pg_dump`) | 02:15 IST, and before every deploy | 3 days | 35 days |
| Base backup | 02:15 IST, after the dump | 3 days | 15 days |
| WAL | Archived at least every 15 min, uploaded every 15 min | 3 days | 15 days |

Timers: `fluidbuddha-backup.timer`, `fluidbuddha-wal-upload.timer`. A dump now: `fluidbuddha backup dump`.
What exists: `fluidbuddha restore list`.

The watchdog emails when a nightly backup or a WAL upload is late, or when Postgres can't archive WAL.

## Restore

### Drills (monthly, production untouched)

```
fluidbuddha restore drill                                   latest dump → scratch database → row counts → dropped
fluidbuddha restore pitr-drill "2026-11-23 14:05:00+05:30"   base backup + WAL → scratch container → row counts
```

A drill passes when it ends with "drill passed". `fluidbuddha status` shows when each last passed.

### Replace the database with a dump

For a bad migration or bad data where the last dump is recent enough:

```
sudo fluidbuddha restore list
sudo fluidbuddha restore dump latest --yes          or: dump fluidbuddha-20261123T024500Z-predeploy.dump
```

The backend stops, the dump restores into a new database, the two swap, the backend starts. The old database
stays as `fluidbuddha_before_restore` until you drop it:
`fluidbuddha psql -c 'DROP DATABASE fluidbuddha_before_restore'`.

### Point-in-time recovery

To undo something that happened at a known time, for example a bad bulk delete at 14:06:

```
sudo fluidbuddha restore pitr "2026-11-23 14:05:00+05:30" --yes
```

It takes the newest base backup before that time, replays the WAL up to it, and starts everything. Today's
data folder is kept as `data/postgres.before-pitr-<time>`; delete it once you're happy. A fresh base backup
runs at the end, because the database is now on a new timeline. Try the time with `pitr-drill` first if
you're unsure.

## Secrets

| Secret | How to rotate |
|---|---|
| `GRAPH-CLIENT-SECRET` | Before it expires: new client secret on `fluidbuddha-mail` in Entra → Key Vault → Release (current commit) → delete the old secret in Entra |
| `GOOGLE-CLOUD-PROJECT`, `VERTEX-SA-JSON` | New key in Google Cloud → Key Vault → Release → delete the old key in Google Cloud |
| `RAZORPAY-*`, `GOOGLE-CLIENT-*`, `SENTRY-DSN` | Key Vault → Release |
| `TURN-SECRET`, `METRICS-TOKEN`, `STATUS-TOKEN` | Key Vault (any long random value) → Release |
| `JWT-SECRET` | Key Vault → Release. Everyone is signed out. |
| `POSTGRES-PASSWORD` | Change the role first: `fluidbuddha psql -c "ALTER ROLE fluidbuddha PASSWORD '<new>'"`, then Key Vault → Release |
| `SECRETS-KEY` | **Don't.** It decrypts the API keys stored in the database. If it is compromised, set `<new key>,<old key>` (newest first) so both decrypt, and plan re-encryption with engineering. Generate a key with `openssl rand -base64 32 \| tr '+/' '-_'`. |

Secrets never go into git, chat or the VM by hand: Key Vault is the only source.

## Resize the VM

When CPU credits keep running out or memory is tight (the alerts say so):

```powershell
az vm resize -g rg-fb-prod-core -n vm-fb-prod-01 --size Standard_D2as_v5
```

About 5 minutes of downtime; everything comes back by itself. Check quota first
(`az vm list-usage --location centralindia -o table`). Larger: `Standard_B4as_v2` (4 vCPU, 16 GiB, burstable)
or `Standard_D4as_v5`.

## Rebuild the VM

When the VM is broken beyond repair. Data comes back from Blob storage.

1. Delete the VM and its OS disk (Portal, or `az vm delete -g rg-fb-prod-core -n vm-fb-prod-01 --yes`,
   then delete the disk). The network, the public IP and the data resource group stay, so DNS doesn't change.
2. Run provisioning again (engineering: `provision.ps1`). It sees no VM and creates a new one, and gives the
   new identity its roles.
3. Run Release with the commit that was live. The internal secrets come back from Key Vault.
4. Restore: `sudo fluidbuddha restore dump latest --yes`, or `restore pitr "<time just before the loss>" --yes`
   for the newest possible data.
5. Old role assignments for the deleted VM show as "Identity not found" in the portal; delete them.

If the whole core resource group is gone: the same steps (provisioning recreates it; the public IP changes, so
update the A records), then restore. If the data resource group is gone despite its lock: provisioning recovers
the soft-deleted Key Vault, but backups older than 14 days of soft delete are lost; recover blobs in the
storage account's portal page first.

## When something is wrong

| Symptom | Look at | Usual fix |
|---|---|---|
| Site down, `fluidbuddha status` shows a container restarting | `fluidbuddha logs <service>` | Fix and release; or roll back |
| `/readyz` 503 | Its JSON: which dependency | Database: `fluidbuddha logs postgres`; Redis: restart it (`fluidbuddha compose restart redis`) |
| Disk alert | `df -h /`, `du -sh /opt/fluidbuddha/* /var/lib/docker` | WAL piling up: check `journalctl -u fluidbuddha-wal-upload`; images: `docker image prune -af` |
| Memory alert | `docker stats --no-stream` | A runaway container: restart it; persistent: resize |
| CPU credits low | Azure metrics, voice traffic | Resize to `D2as_v5` (non-burstable) |
| Certificate errors | `fluidbuddha logs edge` | DNS must point at the VM; Caddy retries by itself |
| Email not sending | `/readyz` email check, `fluidbuddha logs backend` (search "email") | `401`/`invalid_client`: the client secret expired or is wrong. `403 ErrorAccessDenied`: the Exchange scope isn't applied yet (up to 2 h) or doesn't cover the sender. |
| Voice handoff doesn't connect | The Release workflow's STUN check; `fluidbuddha logs coturn` | NSG rules 120 and 130; on strict office networks, TURN over TLS (plan §12, 6.4) |
| A deploy failed and rolled back | The workflow log; `/var/log/fluidbuddha/deploy-*.log` | Fix forward; the previous release is serving |
| Backups late | `journalctl -u fluidbuddha-backup -n 100` | Blob access: the VM identity needs Blob Data Contributor on `backups` (re-run provisioning) |

## Provisioning and release problems

Each of these happened at launch; the [launch record](azure-launch-record.md) has the full story.

| Symptom | Cause | Fix |
|---|---|---|
| Release fails at Azure login: `AADSTS700213 No matching federated identity record found` | The federated credential's subject doesn't match what GitHub sends. The repository uses immutable subjects (`repo:<owner>@<id>/<repo>@<id>:…`). | `gh api repos/OWNER/REPO/actions/oidc/customization/sub` shows the prefix; set `githubSubjectPrefix` in `main.bicep` and re-run provisioning, or fix both credentials with `az identity federated-credential update` |
| Release stops before building: CI not green | Release only builds commits whose CI passed | Fix CI on `main` first (in an emergency only: Run workflow with `skip_ci_check`) |
| Provisioning: `AllocationFailed` / `SkuNotAvailable` for the VM | The region has no capacity for that size right now, even with quota | Delete the half-created VM and its OS disk, then `provision.ps1 -VmSize <fallback>` (B2s_v2, B2as_v2, B2ms, D2as_v5) |
| Provisioning: `ResourceNotFound` on the VM's identity | Azure was still creating the VM | Run provisioning again; the template already orders this |
| Provisioning changes nothing on the VM | The VM exists, so `provision.ps1` leaves it alone (its custom data can't change) | Resize with `az vm resize`, or rebuild (above) |
| Certificates not issued after the first deploy | DNS didn't point at the VM yet, or GoDaddy forwarding is on | Check with `Resolve-DnsName <name> -Server 8.8.8.8`; Caddy retries by itself once DNS is right |
