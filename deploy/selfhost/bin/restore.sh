#!/usr/bin/env bash
# Restore a logical dump (README.md → Restore). Stops the app, replaces the
# database with the dump, starts the app (migrations bring an older dump up to
# this version). For point-in-time recovery from base backups + WAL, follow
# README.md → Point-in-time recovery instead.
#
#   bin/restore.sh backups/dumps/fluidbuddha-20261105T021500Z.dump
set -euo pipefail
cd "$(dirname "$0")/.."
DUMP=${1:?usage: bin/restore.sh backups/dumps/<file>.dump}
[ -f "$DUMP" ] || { echo "no such file: $DUMP"; exit 1; }
if [ -f "$DUMP.sha256" ]; then ( cd "$(dirname "$DUMP")" && sha256sum -c "$(basename "$DUMP").sha256" ); fi
read -r -p "This replaces the current database with $DUMP. Type RESTORE to go on: " ok
[ "$ok" = RESTORE ] || { echo "stopped"; exit 1; }

docker compose stop web backend
pg=$(docker compose ps -q postgres)
name=$(basename "$DUMP")
docker cp "$DUMP" "$pg:/tmp/$name"
docker exec "$pg" sh -c "dropdb -U fluidbuddha --if-exists fluidbuddha_restore && createdb -U fluidbuddha fluidbuddha_restore \
  && pg_restore -U fluidbuddha -d fluidbuddha_restore --no-owner /tmp/$name"
# Swap only once the restore succeeded; keep the old database until you drop it.
docker exec "$pg" psql -U fluidbuddha -d postgres -v ON_ERROR_STOP=1 -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'fluidbuddha' AND pid <> pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS fluidbuddha_before_restore;" \
  -c "ALTER DATABASE fluidbuddha RENAME TO fluidbuddha_before_restore;" \
  -c "ALTER DATABASE fluidbuddha_restore RENAME TO fluidbuddha;"
docker exec "$pg" rm -f "/tmp/$name"
docker compose up -d
echo "restored. The previous database is kept as fluidbuddha_before_restore; drop it once you're happy:"
echo "  docker compose exec postgres dropdb -U fluidbuddha fluidbuddha_before_restore"
