#!/usr/bin/env bash
# Backups (README.md → Backups). Run nightly from cron:
#   15 2 * * * /opt/fluidbuddha/deploy/selfhost/bin/backup.sh >> /var/log/fluidbuddha-backup.log 2>&1
#
# 1. A base backup (pg_basebackup) into backups/base/<time>/ — with the WAL
#    archived continuously into backups/wal/, this is point-in-time recovery.
# 2. A logical dump (pg_dump, checksummed) into backups/dumps/ — portable, and
#    what bin/restore.sh restores by default.
# Old copies are pruned after RETENTION_DAYS (default 14). Copy backups/ off
# the host too (object storage, another site).
set -euo pipefail
cd "$(dirname "$0")/.."
RETENTION_DAYS=${RETENTION_DAYS:-14}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
pg=$(docker compose ps -q postgres)
[ -n "$pg" ] || { echo "postgres isn't running"; exit 1; }

docker exec "$pg" sh -c "mkdir -p /backups/base/$STAMP && pg_basebackup -U fluidbuddha -D /backups/base/$STAMP -Ft -z -X none"
echo "base backup: backups/base/$STAMP"

docker exec "$pg" sh -c "mkdir -p /backups/dumps && pg_dump -U fluidbuddha -d fluidbuddha -Fc -f /backups/dumps/fluidbuddha-$STAMP.dump"
( cd backups/dumps && sha256sum "fluidbuddha-$STAMP.dump" > "fluidbuddha-$STAMP.dump.sha256" )
echo "logical dump: backups/dumps/fluidbuddha-$STAMP.dump"

if [ "$RETENTION_DAYS" -gt 0 ]; then
  find backups/dumps -type f -mtime +"$RETENTION_DAYS" -delete
  find backups/base -mindepth 1 -maxdepth 1 -type d -mtime +"$RETENTION_DAYS" -exec rm -rf {} +
  # WAL is kept a day longer than the base backups, so every kept base
  # backup still has all the WAL it needs (from its start onwards).
  find backups/wal -type f -mtime +"$((RETENTION_DAYS + 1))" -delete
fi
printf '{"at":"%s","base":"%s","dump":"fluidbuddha-%s.dump"}\n' "$STAMP" "$STAMP" "$STAMP" >> backups/backup-log.jsonl
