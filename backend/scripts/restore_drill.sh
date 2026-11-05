#!/usr/bin/env bash
# Restore drill (M2-11, SOC 2 A1.3): prove a backup actually restores.
#
# Checks the copy's SHA-256, restores it into a fresh scratch database on the
# same server, checks the schema revision and that the core tables are there
# with rows, writes the result to <BACKUP_DIR>/drills/ as evidence, and drops
# the scratch database. Exits non-zero if anything fails. Run it at least
# quarterly (docs/compliance/business-continuity.md).
#
#   PG_CONTAINER=a2ui-cortex-db PGUSER=cortex PGDATABASE=cortex scripts/restore_drill.sh [backup-file]
#   DATABASE_URL=postgresql://user:pass@db.internal:5432/cortex scripts/restore_drill.sh
#
# With no file, the newest copy in BACKUP_DIR (default ./backups) is used.
# BACKUP_AGE_IDENTITY: the `age` key file for encrypted copies.
# KEEP_DRILL_DB=1 keeps the scratch database for a look around.
set -euo pipefail

BACKUP_DIR=${BACKUP_DIR:-./backups}
URL=${DATABASE_URL:-${CORTEX_DB_URL:-}}
URL=${URL/+asyncpg/}

pg() {
  if [ -n "${PG_CONTAINER:-}" ]; then
    docker exec -i -e PGPASSWORD="${PGPASSWORD:-}" "$PG_CONTAINER" "$@"
  else
    "$@"
  fi
}

# Connection arguments for database $1.
on() {
  if [ -n "${PG_CONTAINER:-}" ] || [ -z "$URL" ]; then
    echo "-U ${PGUSER:-postgres} -d $1"
  else
    echo "--dbname=${URL%/*}/$1"
  fi
}

file=${1:-$(ls -1t "$BACKUP_DIR"/fluidbuddha-*.dump "$BACKUP_DIR"/fluidbuddha-*.dump.age 2>/dev/null | head -1 || true)}
[ -n "$file" ] && [ -f "$file" ] || { echo "no backup found (looked in $BACKUP_DIR)" >&2; exit 1; }
stamp=$(date -u +%Y%m%dT%H%M%SZ)
scratch="fb_restore_drill_$(date -u +%Y%m%d%H%M%S)"
admin_db=${PGADMIN_DATABASE:-postgres}
start=$(date +%s)
result=failed
detail=""
mkdir -p "$BACKUP_DIR/drills"

finish() {
  # shellcheck disable=SC2046
  if [ "${KEEP_DRILL_DB:-0}" != "1" ]; then
    pg psql $(on "$admin_db") -qc "DROP DATABASE IF EXISTS $scratch" >/dev/null 2>&1 || true
  fi
  secs=$(( $(date +%s) - start ))
  printf '{"at":"%s","backup":"%s","result":"%s","seconds":%s,"detail":"%s"}\n' \
    "$stamp" "$(basename "$file")" "$result" "$secs" "$detail" > "$BACKUP_DIR/drills/drill-$stamp.json"
  echo "restore drill $result in ${secs}s — $detail"
  echo "record: $BACKUP_DIR/drills/drill-$stamp.json"
}
trap finish EXIT

# 1. The copy is what was written.
if [ -f "$file.sha256" ]; then
  ( cd "$(dirname "$file")" && sha256sum -c "$(basename "$file").sha256" >/dev/null ) \
    || { detail="checksum mismatch"; exit 1; }
else
  detail="no checksum file"; exit 1
fi

# 2. Restore into a scratch database.
# shellcheck disable=SC2046
pg psql $(on "$admin_db") -qc "CREATE DATABASE $scratch" >/dev/null
if [[ "$file" == *.age ]]; then
  [ -n "${BACKUP_AGE_IDENTITY:-}" ] || { detail="encrypted copy and no BACKUP_AGE_IDENTITY"; exit 1; }
  # shellcheck disable=SC2046
  age -d -i "$BACKUP_AGE_IDENTITY" "$file" | pg pg_restore $(on "$scratch") --no-owner --exit-on-error \
    || { detail="pg_restore failed"; exit 1; }
else
  # shellcheck disable=SC2046
  pg pg_restore $(on "$scratch") --no-owner --exit-on-error < "$file" || { detail="pg_restore failed"; exit 1; }
fi

# 3. It looks like FluidBuddha.
# shellcheck disable=SC2046
revision=$(pg psql $(on "$scratch") -Atc "SELECT version_num FROM alembic_version")
counts=""
for t in tenants users memberships tenant_websites audit_events conversation_turns; do
  # shellcheck disable=SC2046
  n=$(pg psql $(on "$scratch") -Atc "SELECT count(*) FROM $t") || { detail="table $t missing"; exit 1; }
  counts="$counts $t=$n"
done
# shellcheck disable=SC2046
tenants=$(pg psql $(on "$scratch") -Atc "SELECT count(*) FROM tenants")
[ "$tenants" -gt 0 ] || { detail="restored database has no accounts"; exit 1; }

result=passed
detail="schema $revision;$counts"
