# FluidBuddha, self-hosted

Everything FluidBuddha runs, on one Linux host you control (your VPC or your
own hardware): the console, the API and voice agent, the widget's files,
Postgres with pgvector, Redis, and optionally the voice-handoff relay. Caddy
in front terminates TLS. Nothing calls home: the licence is checked offline.

| Runbook | |
|---|---|
| [Install](#install) | zero to a working console and widget, about 20 minutes |
| [Licence](#licence) | install, renew, what happens at expiry |
| [Models](#models) | Vertex AI, or your own Anthropic / OpenAI / Azure OpenAI |
| [Upgrade](#upgrade) | new version; migrations run themselves |
| [Backups](#backups) · [Restore](#restore) · [Point-in-time recovery](#point-in-time-recovery) | |
| [Air-gapped](#air-gapped) | no internet on the host |
| [TLS](#tls) · [Operations](#operations) | certificates, health, logs, metrics |

## Install

**You need:** a Linux host (4 vCPU, 8 GB RAM, 40 GB disk is plenty to start)
with [Docker Engine](https://docs.docker.com/engine/install/) and the Compose
plugin; two DNS names pointing at it (for example `api.fluidbuddha.acme.com`
and `console.fluidbuddha.acme.com`); ports 80 and 443 open; your licence file.

```bash
git clone <your FluidBuddha release> /opt/fluidbuddha     # or unpack the release bundle
cd /opt/fluidbuddha/deploy/selfhost
sudo bin/install.sh api.fluidbuddha.acme.com console.fluidbuddha.acme.com ops@acme.com ~/acme.licence
```

`bin/install.sh` writes `.env` with generated secrets (keep a copy of it
somewhere safe: the secrets decrypt stored API keys), prepares the folders,
builds the images (5–10 minutes the first time), starts everything and waits
for the backend to be healthy. Then:

1. Open `https://console.…`, create the first account: it is the Owner.
2. Add a website, crawl it (Onboarding) or add your documents (Ingestion).
3. Copy its install snippet onto your site:
   `<script src="https://api.…/widget/loader.js" data-key="fbk_…" async></script>`.

Without a model yet, set `MOCK_AI=true` in `.env` and `docker compose up -d`
to try everything end to end with canned answers.

## Licence

A licence says who it's for, how many websites and team seats it covers
(counted across the whole install, pending invitations included), which
features it includes, and when it expires. It is a signed text key, checked
offline against the public key built into this version.

- **Install or renew:** Account → Licence in the console (Owner), or
  `LICENCE_KEY=` / `LICENCE_FILE=` in `.env`. One installed in the console wins.
- **30 days before expiry** the console shows a banner to everyone.
- **After expiry** there is a grace period (14 days unless your licence says
  otherwise): everything works, with a banner.
- **After the grace period**, or with no or an invalid licence: the console
  is read-only (you can look at everything; changes are refused) until an
  Owner installs a licence. **Visitors are never affected**: the widget,
  hosted campaign pages and the agent endpoint keep answering.
- Features a licence doesn't include (`byo_model`, `agent_access`,
  `campaigns`, `sso`, `voice_handoff`) are refused in the console; new
  websites or seats beyond the licence are refused.

## Models

Speech and embeddings use Vertex AI: put a service account JSON (roles: Vertex
AI User) in `secrets/`, set `GOOGLE_CLOUD_PROJECT` and
`GOOGLE_APPLICATION_CREDENTIALS=/secrets/<file>.json` in `.env`, then
`docker compose up -d`.

The agent itself can use your own provider instead: Console → AI model
(Owner/Admin) → Anthropic, OpenAI or Azure OpenAI, its API key (stored
encrypted with `SECRETS_KEY`), a fast and a thinking model, "Test connection",
and per website the switch to use it. Azure OpenAI takes the resource endpoint,
deployment names and API version. Spend from your own key isn't counted
against `PUBLIC_DAILY_SPEND_CAP_USD`.

## Upgrade

```bash
cd /opt/fluidbuddha && git pull          # or unpack the new release over it
cd deploy/selfhost && bin/upgrade.sh
```

It takes a backup first, rebuilds, and restarts. The backend runs the database
migrations itself when it starts. Voice sessions in progress get 60 seconds to
finish before the old backend stops. Check `https://api.…/readyz` afterwards.
To go back: restore the backup taken by the upgrade and start the previous
version.

## Backups

`bin/backup.sh` (run it nightly from cron; see the comment at its top) keeps:

- a **base backup** (`pg_basebackup`) in `backups/base/<time>/`, plus the
  write-ahead log archived continuously into `backups/wal/` — together, point-
  in-time recovery to any moment since the oldest base backup;
- a **logical dump** (`pg_dump`, with a SHA-256) in `backups/dumps/`.

Copies older than `RETENTION_DAYS` (14) are pruned. **Copy `backups/` off the
host** (object storage, another site) — a backup on the same disk is not a
backup. Prove restores work: the repository's `backend/scripts/restore_drill.sh`
restores the newest dump into a scratch database and checks it
(`PG_CONTAINER=$(docker compose ps -q postgres) PGUSER=fluidbuddha PGDATABASE=fluidbuddha BACKUP_DIR=backups/dumps …`).

## Restore

```bash
bin/restore.sh backups/dumps/fluidbuddha-20261105T021500Z.dump
```

It checks the checksum, asks you to confirm, stops the app, restores into a new
database, swaps it in (the old one is kept as `fluidbuddha_before_restore`
until you drop it), and starts the app.

## Point-in-time recovery

To roll the database back to a moment (say, just before a bad import):

```bash
docker compose stop web backend postgres
docker run --rm -v fluidbuddha_pgdata:/var/lib/postgresql/data alpine sh -c 'rm -rf /var/lib/postgresql/data/*'
BASE=backups/base/20261105T021500Z            # the newest base backup before the moment
docker run --rm -v fluidbuddha_pgdata:/d -v "$PWD/$BASE:/b:ro" alpine sh -c 'tar xzf /b/base.tar.gz -C /d && chown -R 999:999 /d'
cat > /tmp/recovery.conf <<'EOF'
restore_command = 'cp /backups/wal/%f %p'
recovery_target_time = '2026-11-05 14:32:00+00'
recovery_target_action = 'promote'
EOF
docker run --rm -v fluidbuddha_pgdata:/d -v /tmp/recovery.conf:/r:ro alpine sh -c 'cat /r >> /d/postgresql.auto.conf && touch /d/recovery.signal && chown 999:999 /d/recovery.signal'
docker compose up -d
```

Postgres replays the archived WAL up to the target time, then opens. Check the
data, then take a fresh base backup (`bin/backup.sh`).

## Air-gapped

On a machine with internet and Docker, with the target's `.env` copied into
`deploy/selfhost/` (the console image has the API address built in):

```bash
FB_VERSION=2026.11.1 bin/export-images.sh   # images/*.tar + SHA256SUMS
```

Carry `deploy/selfhost/` (with `images/`) to the host, then run
`bin/install.sh …` there: it sees `images/`, checks the checksums, loads them
and starts without building or pulling anything. Upgrades: export the new
version the same way and run `bin/upgrade.sh images/`. With no internet,
use `CADDY_TLS=tls /certs/fullchain.pem /certs/privkey.pem` (below) and your
own model provider reachable from the host (or Vertex through your proxy).

## TLS

By default Caddy gets Let's Encrypt certificates for both names (ports 80 and
443 must be reachable from the internet) and renews them. Otherwise, put your
certificate and key in `certs/` and set
`CADDY_TLS=tls /certs/fullchain.pem /certs/privkey.pem`. For a trial on a
private network, `CADDY_TLS=tls internal` (browsers will warn).

## Operations

- **Health:** `https://api.…/healthz` (alive) and `/readyz` (database, Redis,
  models); `docker compose ps` shows each service's health.
- **Logs:** `docker compose logs -f backend` — JSON lines, rotated (5 × 20 MB per
  service).
- **Metrics:** `https://api.…/metrics` with `Authorization: Bearer $METRICS_TOKEN`
  (Prometheus). Alert rules: `deploy/monitoring/` in the repository.
- **Voice handoff:** `docker compose --profile voice up -d` starts coturn; open
  3478 (UDP+TCP) and 49160–49200/UDP and set `TURN_URLS` /
  `TURN_SECRET` in `.env`.
- **Email:** set `SMTP_*`; until then invitation links are shown in the console.
