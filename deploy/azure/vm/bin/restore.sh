#!/bin/bash
# Restores (docs/deployment/azure-runbook.md, "Restore"). Run as root, via `fluidbuddha restore ...`:
#
#   restore.sh list                     backups on this VM and in Blob storage
#   restore.sh drill [dump]             restore a dump into a scratch database, compare row counts, drop it
#   restore.sh dump <dump> --yes        replace the live database with a dump
#   restore.sh pitr-drill "<time>"      point-in-time recovery into a scratch container (proves the base
#                                       backups and WAL work; production is untouched)
#   restore.sh pitr "<time>" --yes      point-in-time recovery of the live database
#
# <dump> is a file in backups/dumps, a blob name (dumps/...), or "latest".
# <time> is a timestamp with its zone, for example "2026-11-23 14:05:00+05:30".
set -euo pipefail
# shellcheck source=lib.sh
. "$(dirname "$(readlink -f "$0")")/lib.sh"

BK=$FB_HOME/backups
PSQL=(compose exec -T postgres psql -U fluidbuddha -v ON_ERROR_STOP=1 -tA)

YES=0
args=()
for a in "$@"; do
  if [ "$a" = --yes ]; then YES=1; else args+=("$a"); fi
done
set -- "${args[@]}"

confirm() {
  [ "$YES" = 1 ] && return 0
  [ -t 0 ] || die "add --yes to confirm (there is no terminal to ask on)"
  local ok
  read -r -p "$1 Type RESTORE to go on: " ok
  [ "$ok" = RESTORE ] || die "stopped"
}

verify() { # checksum, when there is one
  local f=$1
  if [ -f "$f.sha256" ]; then
    (cd "$(dirname "$f")" && sha256sum -c --quiet "$(basename "$f").sha256") || die "checksum mismatch: $f"
  fi
}

resolve_dump() { # <file | blob name | latest>: prints a local path, downloading if needed
  local want=$1 blob file
  if [ "$want" = latest ]; then
    file=$(find "$BK/dumps" -maxdepth 1 -name '*.dump' -printf '%T@ %p\n' | sort -n | tail -n 1 | cut -d' ' -f2-)
    if [ -n "$file" ]; then echo "$file"; return; fi
    az_login
    blob=$(blob_list dumps/ | grep '\.dump$' | tail -n 1 || true)
    [ -n "$blob" ] || die "no dumps here or in Blob storage"
  elif [ -f "$want" ]; then
    echo "$want"
    return
  else
    blob=dumps/$(basename "$want")
  fi
  file=$BK/dumps/$(basename "$blob")
  if [ ! -f "$file" ]; then
    az_login
    blob_get "$blob" "$file"
    blob_get "$blob.sha256" "$file.sha256" || log "no checksum for $blob"
  fi
  echo "$file"
}

counts() { # <psql runner...> -- prints "table rows" for every table in the public schema
  local t
  for t in $("$@" -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"); do
    printf '%-40s %s\n' "$t" "$("$@" -c "SELECT count(*) FROM public.\"$t\"")"
  done
}

list() {
  echo "On this VM:"
  find "$BK/dumps" "$BK/base" -maxdepth 1 -type f ! -name '*.sha256' -printf '  %TF %TH:%TM  %10s  %f\n' | sort
  echo "  WAL waiting for upload: $(find "$BK/wal" -name '*.gz' | wc -l)"
  az_login
  echo "In Blob storage ($STORAGE_ACCOUNT/$BACKUP_CONTAINER), newest last:"
  blob_list dumps/ | grep '\.dump$' | tail -n 10 | sed 's/^/  /' || true
  blob_list base/ | tail -n 10 | sed 's/^/  /' || true
  echo "  WAL segments: $(blob_list wal/ | wc -l)"
}

drill() {
  local file pg
  file=$(resolve_dump "${1:-latest}")
  verify "$file"
  pg=$(compose ps -q postgres)
  [ -n "$pg" ] || die "postgres isn't running"
  log "drill: restoring $(basename "$file") into the scratch database fluidbuddha_drill"
  docker cp "$file" "$pg:/tmp/drill.dump"
  if ! compose exec -T postgres sh -c 'dropdb -U fluidbuddha --if-exists fluidbuddha_drill &&
      createdb -U fluidbuddha fluidbuddha_drill &&
      pg_restore -U fluidbuddha -d fluidbuddha_drill --no-owner --exit-on-error /tmp/drill.dump'; then
    compose exec -T postgres sh -c 'rm -f /tmp/drill.dump; dropdb -U fluidbuddha --if-exists fluidbuddha_drill'
    die "the dump didn't restore cleanly"
  fi
  printf '%-40s %s\n' "table" "rows (restored / live now)"
  join <(counts "${PSQL[@]}" -d fluidbuddha_drill | sort) <(counts "${PSQL[@]}" -d fluidbuddha | sort) |
    awk '{ printf "%-40s %s / %s\n", $1, $2, $3 }'
  compose exec -T postgres sh -c 'rm -f /tmp/drill.dump; dropdb -U fluidbuddha fluidbuddha_drill'
  mark last-restore-drill
  log "drill passed: $(basename "$file") restores cleanly (scratch database dropped)"
}

restore_dump() {
  local file pg
  file=$(resolve_dump "${1:?which dump? (a file, a blob name or latest)}")
  verify "$file"
  confirm "This replaces the live database with $(basename "$file")."
  pg=$(compose ps -q postgres)
  [ -n "$pg" ] || die "postgres isn't running"
  compose stop backend
  docker cp "$file" "$pg:/tmp/restore.dump"
  if ! compose exec -T postgres sh -c 'dropdb -U fluidbuddha --if-exists fluidbuddha_restore &&
      createdb -U fluidbuddha fluidbuddha_restore &&
      pg_restore -U fluidbuddha -d fluidbuddha_restore --no-owner --exit-on-error /tmp/restore.dump'; then
    compose start backend
    die "pg_restore failed; the live database is unchanged"
  fi
  # Swap only once the restore succeeded, and keep the old database until someone drops it.
  "${PSQL[@]}" -d postgres \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'fluidbuddha' AND pid <> pg_backend_pid()" \
    -c "DROP DATABASE IF EXISTS fluidbuddha_before_restore" \
    -c "ALTER DATABASE fluidbuddha RENAME TO fluidbuddha_before_restore" \
    -c "ALTER DATABASE fluidbuddha_restore RENAME TO fluidbuddha" > /dev/null
  compose exec -T postgres rm -f /tmp/restore.dump
  compose up -d
  log "restored $(basename "$file"). The previous database is kept as fluidbuddha_before_restore."
  log "Drop it once you're happy: fluidbuddha psql -c 'DROP DATABASE fluidbuddha_before_restore'"
}

# --- point-in-time recovery -------------------------------------------------------------------

pick_base() { # <target epoch>: the newest base backup in Blob storage taken before it
  local name ts best=""
  for name in $(blob_list base/ | grep '\.tar\.gz$' || true); do
    ts=$(basename "$name" .tar.gz)
    ts=${ts#base-} # 20261123T021500Z
    ts=$(date -u -d "${ts:0:4}-${ts:4:2}-${ts:6:2} ${ts:9:2}:${ts:11:2}:${ts:13:2}" +%s)
    if [ "$ts" -lt "$1" ]; then best=$name; fi
  done
  echo "$best"
}

prepare() { # <data dir> <target time> <target epoch>: base backup + WAL + recovery settings
  local dir=$1 blob file dl
  az_login
  blob=$(pick_base "$3")
  [ -n "$blob" ] || die "no base backup before $2 (base backups are kept 15 days)"
  file=$BK/base/$(basename "$blob")
  [ -f "$file" ] || blob_get "$blob" "$file"
  log "base backup: $(basename "$blob")"

  # Every archived WAL segment, from this VM and from Blob storage.
  find "$BK/restore-wal" -mindepth 1 -delete
  cp -n "$BK"/wal-uploaded/*.gz "$BK"/wal/*.gz "$BK/restore-wal/" 2> /dev/null || true
  dl=$(mktemp -d "$BK/wal-download.XXXXXX")
  az storage blob download-batch --auth-mode login --account-name "$STORAGE_ACCOUNT" \
    --source "$BACKUP_CONTAINER" --pattern 'wal/*' --destination "$dl" \
    --no-progress --only-show-errors --output none
  cp -n "$dl"/wal/*.gz "$BK/restore-wal/" 2> /dev/null || true
  rm -rf "$dl"
  chown -R 999:999 "$BK/restore-wal"
  log "WAL segments ready: $(find "$BK/restore-wal" -name '*.gz' | wc -l)"

  rm -rf "$dir"
  install -d -m 0700 -o 999 -g 999 "$dir"
  tar -xzf "$file" -C "$dir"
  chown -R 999:999 "$dir"
  cat >> "$dir/postgresql.auto.conf" << EOF
restore_command = 'test -f /restore-wal/%f.gz && gunzip -c /restore-wal/%f.gz > %p'
recovery_target_time = '$2'
recovery_target_action = 'promote'
EOF
  touch "$dir/recovery.signal"
}

wait_recovered() { # <container>: until recovery has ended (an hour at most)
  local i
  for i in $(seq 1 720); do
    [ "$(docker inspect -f '{{.State.Running}}' "$1" 2> /dev/null)" = true ] || return 1
    if [ "$(docker exec "$1" psql -U fluidbuddha -d postgres -tAc 'SELECT pg_is_in_recovery()' 2> /dev/null)" = f ]; then
      return 0
    fi
    [ $((i % 12)) -ne 0 ] || log "recovering ($((i / 12)) min)"
    sleep 5
  done
  return 1
}

target_epoch() {
  date -d "$1" +%s 2> /dev/null || die "can't read the time '$1' (try \"2026-11-23 14:05:00+05:30\")"
}

pitr_drill() {
  local target=${1:?which time?} epoch dir=$FB_HOME/data/pitr-drill name=fluidbuddha-pitr-drill
  epoch=$(target_epoch "$target")
  prepare "$dir" "$target" "$epoch"
  docker rm -f "$name" > /dev/null 2>&1 || true
  docker run -d --name "$name" --shm-size 256m \
    -v "$dir:/var/lib/postgresql/data" -v "$BK/restore-wal:/restore-wal:ro" \
    pgvector/pgvector:pg16 postgres -c archive_mode=off > /dev/null
  if ! wait_recovered "$name"; then
    docker logs --tail 40 "$name" || true
    docker rm -f "$name" > /dev/null
    die "recovery to $target didn't finish (log above)"
  fi
  log "recovered a scratch copy to $target. Rows per table:"
  counts docker exec "$name" psql -U fluidbuddha -d fluidbuddha -v ON_ERROR_STOP=1 -tA | sed 's/^/  /'
  docker rm -f "$name" > /dev/null
  rm -rf "$dir"
  find "$BK/restore-wal" -mindepth 1 -delete
  mark last-pitr-drill
  log "point-in-time drill passed (scratch copy removed)"
}

pitr() {
  local target=${1:?which time?} epoch stamp new pg
  epoch=$(target_epoch "$target")
  confirm "This rewinds the live database to $target. Changes after that are lost (today's data folder is kept)."
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  new=$FB_HOME/data/postgres.pitr-$stamp
  prepare "$new" "$target" "$epoch"
  compose stop backend postgres
  mv "$FB_HOME/data/postgres" "$FB_HOME/data/postgres.before-pitr-$stamp"
  mv "$new" "$FB_HOME/data/postgres"
  compose up -d postgres
  pg=$(compose ps -q postgres)
  wait_recovered "$pg" || die "recovery didn't finish; the data from before is in data/postgres.before-pitr-$stamp"
  "${PSQL[@]}" -d postgres -c "ALTER SYSTEM RESET restore_command" -c "ALTER SYSTEM RESET recovery_target_time" \
    -c "ALTER SYSTEM RESET recovery_target_action" -c "SELECT pg_reload_conf()" > /dev/null
  compose up -d
  find "$BK/restore-wal" -mindepth 1 -delete
  log "recovered to $target. A fresh base backup starts the new timeline:"
  "$(dirname "$(readlink -f "$0")")/backup.sh" base
  log "The data from before is in data/postgres.before-pitr-$stamp; delete it once you're happy."
}

case "${1:-}" in
  list) list ;;
  drill) drill "${2:-latest}" ;;
  dump) restore_dump "${2:-}" ;;
  pitr-drill) pitr_drill "${2:-}" ;;
  pitr) pitr "${2:-}" ;;
  *) sed -n '2,13p' "$0" >&2; exit 2 ;;
esac
