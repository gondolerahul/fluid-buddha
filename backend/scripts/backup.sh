#!/usr/bin/env bash
# Database backup (M2-11, SOC 2 A1.2 / CC9.1).
#
# A compressed custom-format pg_dump with a SHA-256 checksum, optionally
# encrypted with `age`, old copies pruned, and a line appended to
# backup-log.jsonl as evidence. Run it from cron / a scheduled task, then prove
# the copies restore with scripts/restore_drill.sh.
#
#   # straight to a server (the app's URL works; +asyncpg is dropped):
#   DATABASE_URL=postgresql://user:pass@db.internal:5432/cortex scripts/backup.sh
#   # or through the Postgres container (no client tools needed on the host):
#   PG_CONTAINER=a2ui-cortex-db PGUSER=cortex PGDATABASE=cortex scripts/backup.sh
#
# Settings (environment):
#   BACKUP_DIR            where copies go (default ./backups)
#   RETENTION_DAYS        delete copies older than this (default 30; 0 = keep all)
#   BACKUP_AGE_RECIPIENT  an `age` public key: encrypt the copy (needs `age`)
set -euo pipefail

BACKUP_DIR=${BACKUP_DIR:-./backups}
RETENTION_DAYS=${RETENTION_DAYS:-30}
URL=${DATABASE_URL:-${CORTEX_DB_URL:-}}
URL=${URL/+asyncpg/}

pg() {
  if [ -n "${PG_CONTAINER:-}" ]; then
    docker exec -i -e PGPASSWORD="${PGPASSWORD:-}" "$PG_CONTAINER" "$@"
  else
    "$@"
  fi
}

target() {
  if [ -n "${PG_CONTAINER:-}" ] || [ -z "$URL" ]; then
    echo "-U ${PGUSER:-postgres} -d ${PGDATABASE:-postgres}"
  else
    echo "--dbname=$URL"
  fi
}

mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
name="fluidbuddha-$stamp.dump"
tmp="$BACKUP_DIR/.$name.partial"
start=$(date +%s)

# shellcheck disable=SC2046
revision=$(pg psql $(target) -Atc "SELECT version_num FROM alembic_version" 2>/dev/null || echo unknown)

# shellcheck disable=SC2046
if [ -n "${BACKUP_AGE_RECIPIENT:-}" ]; then
  command -v age >/dev/null || { echo "BACKUP_AGE_RECIPIENT is set but 'age' isn't installed" >&2; exit 2; }
  name="$name.age"
  pg pg_dump $(target) --format=custom --compress=6 --no-owner --no-privileges \
    | age -r "$BACKUP_AGE_RECIPIENT" > "$tmp"
else
  pg pg_dump $(target) --format=custom --compress=6 --no-owner --no-privileges > "$tmp"
fi

[ -s "$tmp" ] || { echo "backup is empty" >&2; rm -f "$tmp"; exit 1; }
mv "$tmp" "$BACKUP_DIR/$name"
( cd "$BACKUP_DIR" && sha256sum "$name" > "$name.sha256" )
sum=$(cut -d' ' -f1 "$BACKUP_DIR/$name.sha256")
size=$(wc -c < "$BACKUP_DIR/$name" | tr -d ' ')

pruned=0
if [ "$RETENTION_DAYS" -gt 0 ]; then
  while IFS= read -r old; do
    rm -f "$old" "$old.sha256"
    pruned=$((pruned + 1))
  done < <(find "$BACKUP_DIR" -maxdepth 1 -name 'fluidbuddha-*.dump*' ! -name '*.sha256' -mtime +"$RETENTION_DAYS")
fi

secs=$(( $(date +%s) - start ))
printf '{"at":"%s","file":"%s","bytes":%s,"sha256":"%s","revision":"%s","seconds":%s,"pruned":%s}\n' \
  "$stamp" "$name" "$size" "$sum" "$revision" "$secs" "$pruned" >> "$BACKUP_DIR/backup-log.jsonl"
echo "backup ok: $BACKUP_DIR/$name ($size bytes, schema $revision, ${secs}s, pruned $pruned)"
