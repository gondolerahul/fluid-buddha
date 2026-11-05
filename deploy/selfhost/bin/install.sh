#!/usr/bin/env bash
# First install on a fresh Linux host (README.md → Install).
#
#   bin/install.sh api.example.com console.example.com ops@example.com [licence-file]
#
# Checks Docker, writes .env with generated secrets (an existing .env is kept),
# prepares the folders, builds (or loads, for air-gapped installs) the images
# and starts everything. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."

API=${1:-}; CONSOLE=${2:-}; EMAIL=${3:-}; LICENCE=${4:-}
command -v docker >/dev/null || { echo "Docker is not installed: https://docs.docker.com/engine/install/"; exit 1; }
docker compose version >/dev/null || { echo "The Docker Compose plugin is missing."; exit 1; }

secret() { head -c 48 /dev/urandom | base64 | tr -d '\n/+=' | head -c 48; }
fernet() { head -c 32 /dev/urandom | base64 | tr '+/' '-_'; }

if [ ! -f .env ]; then
  [ -n "$API" ] && [ -n "$CONSOLE" ] || { echo "usage: bin/install.sh API_DOMAIN CONSOLE_DOMAIN [ACME_EMAIL] [licence-file]"; exit 1; }
  sed -e "s|^API_DOMAIN=.*|API_DOMAIN=$API|" \
      -e "s|^CONSOLE_DOMAIN=.*|CONSOLE_DOMAIN=$CONSOLE|" \
      -e "s|^ACME_EMAIL=.*|ACME_EMAIL=$EMAIL|" \
      -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(secret)|" \
      -e "s|^JWT_SECRET=.*|JWT_SECRET=$(secret)|" \
      -e "s|^SECRETS_KEY=.*|SECRETS_KEY=$(fernet)|" \
      -e "s|^METRICS_TOKEN=.*|METRICS_TOKEN=$(secret)|" \
      -e "s|^STATUS_TOKEN=.*|STATUS_TOKEN=$(secret)|" \
      .env.example > .env
  chmod 600 .env
  echo "wrote .env (secrets generated; keep a copy somewhere safe)"
fi

mkdir -p secrets certs backups/wal backups/base backups/dumps
# Postgres (uid 999 in the image) writes the WAL archive.
if [ "$(id -u)" = 0 ]; then chown -R 999:999 backups/wal backups/base; else
  echo "note: run 'sudo chown -R 999:999 backups/wal backups/base' so Postgres can archive WAL"; fi

if [ -n "$LICENCE" ]; then
  cp "$LICENCE" secrets/fluidbuddha.licence
  grep -q '^LICENCE_FILE=/secrets/fluidbuddha.licence' .env || \
    sed -i "s|^LICENCE_FILE=.*|LICENCE_FILE=/secrets/fluidbuddha.licence|" .env
fi

if ls images/*.tar >/dev/null 2>&1; then
  bin/import-images.sh
  docker compose up -d --no-build
else
  docker compose up -d --build
fi

echo "waiting for the backend to be healthy…"
for _ in $(seq 1 60); do
  state=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q backend)" 2>/dev/null || echo starting)
  [ "$state" = healthy ] && break
  sleep 5
done
docker compose ps
. ./.env
echo
echo "Console: https://$CONSOLE_DOMAIN  (create the first account: it becomes the Owner)"
echo "Widget:  <script src=\"https://$API_DOMAIN/widget/loader.js\" data-key=\"…\" async></script>"
