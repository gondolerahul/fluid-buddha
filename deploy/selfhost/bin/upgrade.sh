#!/usr/bin/env bash
# Upgrade (README.md → Upgrade): back up, then roll to the new version.
# The backend runs the database migrations itself on start; voice sessions get
# 60 s to finish (stop_grace_period) before the old backend stops.
#
#   git pull && bin/upgrade.sh            # from source
#   bin/upgrade.sh images/                # air-gapped: load the new image tarballs first
set -euo pipefail
cd "$(dirname "$0")/.."
bin/backup.sh
if [ -n "${1:-}" ]; then
  bin/import-images.sh "$1"
  docker compose up -d --no-build
else
  docker compose build
  docker compose up -d
fi
docker compose ps
echo "upgraded. Check: curl -fsS https://\$API_DOMAIN/readyz"
