# Shared by the FluidBuddha VM scripts. Sourced, not run.
# shellcheck shell=bash

FB_HOME=${FB_HOME:-/opt/fluidbuddha}
FB_STATE=${FB_STATE:-/var/lib/fluidbuddha}
# Names and addresses written at provisioning (infra/cloud-init.yaml).
# shellcheck source=/dev/null
. /etc/fluidbuddha/host.env

log() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# The live release's folder (releases/<sha>), or nothing before the first deploy.
current_release() {
  if [ -L "$FB_HOME/current" ]; then readlink -f "$FB_HOME/current"; fi
}

# docker compose for one release folder, with the files the deploy renders.
compose_in() {
  local dir=$1
  shift
  docker compose --project-name fluidbuddha --env-file "$FB_HOME/.env" -f "$dir/docker-compose.yml" "$@"
}

# docker compose for the live release.
compose() {
  local dir
  dir=$(current_release)
  [ -n "$dir" ] || die "no release is live yet"
  compose_in "$dir" "$@"
}

# Azure, signed in as the VM's managed identity (no keys on disk).
az_login() {
  az login --identity --allow-no-subscriptions --output none --only-show-errors
}

blob_put() { # <file> <blob name>
  az storage blob upload --auth-mode login --account-name "$STORAGE_ACCOUNT" \
    --container-name "$BACKUP_CONTAINER" --file "$1" --name "$2" --overwrite true \
    --no-progress --only-show-errors --output none
}

blob_get() { # <blob name> <file>
  az storage blob download --auth-mode login --account-name "$STORAGE_ACCOUNT" \
    --container-name "$BACKUP_CONTAINER" --name "$1" --file "$2" \
    --no-progress --only-show-errors --output none
}

blob_list() { # <prefix>: blob names, oldest first
  az storage blob list --auth-mode login --account-name "$STORAGE_ACCOUNT" \
    --container-name "$BACKUP_CONTAINER" --prefix "$1" --num-results "*" \
    --query "sort_by([], &properties.lastModified)[].name" -o tsv --only-show-errors
}

# Record that something succeeded just now (the watchdog reads these).
mark() { date +%s > "$FB_STATE/$1"; }

# Minutes since mark <name>, or a very large number if it never happened.
minutes_since() {
  if [ -f "$FB_STATE/$1" ]; then
    echo $((($(date +%s) - $(cat "$FB_STATE/$1")) / 60))
  else
    echo 999999
  fi
}
