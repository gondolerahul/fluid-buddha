#!/bin/bash
# Backups (docs/deployment/azure-runbook.md, "Backups"). The systemd timers run:
#   backup.sh nightly      02:15 IST: a logical dump and a base backup, both copied to Blob storage
#   backup.sh wal          every 15 minutes: upload the archived WAL (point-in-time recovery)
# and by hand, or from a deploy:
#   backup.sh dump [tag]   a logical dump now (each deploy takes one tagged "predeploy")
#   backup.sh base         a base backup now
#
# Local copies are kept LOCAL_DAYS (3) days. In Blob storage, lifecycle rules keep dumps 35 days and
# base backups and WAL 15 days (infra/modules/data.bicep); soft delete adds 14 days on top.
set -euo pipefail
# shellcheck source=lib.sh
. "$(dirname "$(readlink -f "$0")")/lib.sh"

LOCAL_DAYS=${LOCAL_DAYS:-3}
BK=$FB_HOME/backups

stamp() { date -u +%Y%m%dT%H%M%SZ; }

need_postgres() {
  [ -n "$(compose ps -q postgres 2>/dev/null)" ] || die "postgres isn't running"
}

lock() { # one run of each kind at a time
  exec 9> "/run/lock/fluidbuddha-backup-$1.lock"
  flock -n 9 || die "a '$1' backup is already running"
}

dump() {
  local tag=${1:-} name file
  name="fluidbuddha-$(stamp)${tag:+-$tag}.dump"
  file=$BK/dumps/$name
  need_postgres
  compose exec -T postgres pg_dump -U fluidbuddha -d fluidbuddha -Fc > "$file.part"
  mv "$file.part" "$file"
  (cd "$BK/dumps" && sha256sum "$name" > "$name.sha256")
  log "dump: $file ($(du -h "$file" | cut -f1))"
  if ! { az_login && blob_put "$file" "dumps/$name" && blob_put "$file.sha256" "dumps/$name.sha256"; }; then
    # A failed upload doesn't block a deploy: the local copy is there.
    [ "$tag" = predeploy ] || die "uploading $name failed; the local copy is $file"
    log "WARNING: uploading $name failed; the local copy is $file"
    return 0
  fi
  log "uploaded: dumps/$name"
  [ -n "$tag" ] || mark last-dump
}

base() {
  local name file
  name="base-$(stamp).tar.gz"
  file=$BK/base/$name
  need_postgres
  # The WAL comes from the archive (-X none). Stdout carries one gzipped tar with the manifest in it.
  compose exec -T postgres pg_basebackup -U fluidbuddha -D - -Ft -X none -z -c fast > "$file.part"
  mv "$file.part" "$file"
  log "base backup: $file ($(du -h "$file" | cut -f1))"
  az_login
  blob_put "$file" "base/$name"
  log "uploaded: base/$name"
  mark last-base
}

wal() {
  local f n=0
  shopt -s nullglob
  local files=("$BK"/wal/*.gz)   # not *.gz.part: Postgres is still writing those
  if [ ${#files[@]} -gt 0 ]; then
    az_login
    for f in "${files[@]}"; do
      blob_put "$f" "wal/$(basename "$f")"
      mv -f "$f" "$BK/wal-uploaded/"
      n=$((n + 1))
    done
  fi
  find "$BK/wal-uploaded" -type f -mtime +"$LOCAL_DAYS" -delete
  log "wal: uploaded $n file(s)"
  mark last-wal
}

prune() {
  find "$BK/dumps" "$BK/base" -type f -mtime +"$LOCAL_DAYS" -delete
  find "$BK/dumps" "$BK/base" -type f -name '*.part' -mmin +120 -delete
}

case "${1:-}" in
  nightly) lock nightly; dump; base; prune ;;
  dump) lock dump; dump "${2:-}"; prune ;;
  base) lock base; base; prune ;;
  wal) lock wal; wal ;;
  *) echo "usage: backup.sh nightly | dump [tag] | base | wal" >&2; exit 2 ;;
esac
