#!/bin/bash
# The watchdog (fluidbuddha-watchdog.timer, every 15 minutes). Emails ALERT_EMAIL when something
# needs a person: disk, memory, backups, WAL uploads, WAL archiving, containers. One email per
# problem every 6 hours while it lasts, and one when it clears. It mails through the app's own email
# settings (Microsoft Graph, or SMTP), so it works while the backend is down.
set -euo pipefail
# shellcheck source=lib.sh
. "$(dirname "$(readlink -f "$0")")/lib.sh"

[ -f "$FB_HOME/backend.env" ] || exit 0 # nothing is deployed yet
set -a
# shellcheck source=/dev/null
. "$FB_HOME/backend.env"
# shellcheck source=/dev/null
. "$FB_HOME/ops.env"
set +a

ALERTS=$FB_STATE/alerts
REPEAT_SECONDS=$((6 * 3600))
mkdir -p "$ALERTS"

send_mail() { # <subject> <body>
  local to=${ALERT_EMAIL:-} from token netrc
  [ -n "$to" ] || { log "no ALERT_EMAIL, not sent: $1"; return 1; }
  from=$(sed -E 's/^.*<([^>]+)>.*$/\1/' <<< "${SMTP_FROM:-}")
  if [ "${EMAIL_TRANSPORT:-smtp}" = graph ]; then
    [ -n "${GRAPH_CLIENT_SECRET:-}" ] || { log "Graph isn't set up, not sent: $1"; return 1; }
    token=$(printf '%s' "$GRAPH_CLIENT_SECRET" | curl -fsS --max-time 20 \
      "https://login.microsoftonline.com/$GRAPH_TENANT_ID/oauth2/v2.0/token" \
      --data-urlencode grant_type=client_credentials --data-urlencode "client_id=$GRAPH_CLIENT_ID" \
      --data-urlencode "client_secret@-" --data-urlencode "scope=https://graph.microsoft.com/.default" |
      jq -r .access_token)
    jq -n --arg s "$1" --arg b "$2" --arg to "$to" '{message: {subject: $s,
        body: {contentType: "Text", content: $b}, toRecipients: [{emailAddress: {address: $to}}]},
        saveToSentItems: false}' |
      curl -fsS --max-time 20 "https://graph.microsoft.com/v1.0/users/$from/sendMail" \
        -H @<(printf 'Authorization: Bearer %s\n' "$token") -H "Content-Type: application/json" \
        --data-binary @- > /dev/null
  elif [ -n "${SMTP_HOST:-}" ]; then
    netrc=$(mktemp)
    printf 'machine %s login %s password %s\n' "$SMTP_HOST" "${SMTP_USERNAME:-}" "${SMTP_PASSWORD:-}" > "$netrc"
    printf 'From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n%s\r\n' "$SMTP_FROM" "$to" "$1" "$2" |
      curl -fsS --max-time 30 --url "smtp://$SMTP_HOST:${SMTP_PORT:-587}" --ssl-reqd \
        --netrc-file "$netrc" --mail-from "$from" --mail-rcpt "$to" -T - || { rm -f "$netrc"; return 1; }
    rm -f "$netrc"
  else
    log "no email transport, not sent: $1"
    return 1
  fi
}

problems=() # "key|message"
add() { problems+=("$1|$2"); }

# Grace period after the first deploy: the first nightly backup comes the night after.
deployed_minutes=$(minutes_since first-deploy)

disk=$(df --output=pcent / | tail -n 1 | tr -dc '0-9')
[ "$disk" -lt 80 ] || add disk "The OS disk is ${disk}% full."

memory=$(awk '/^MemAvailable:/ { print int($2 / 1024) }' /proc/meminfo)
[ "$memory" -ge 300 ] || add memory "Only ${memory} MiB of memory is available."

if [ "$deployed_minutes" -gt $((26 * 60)) ]; then
  [ "$(minutes_since last-dump)" -lt $((26 * 60)) ] ||
    add dump "No nightly dump has reached Blob storage for over 26 hours (journalctl -u fluidbuddha-backup)."
  [ "$(minutes_since last-base)" -lt $((26 * 60)) ] ||
    add base "No base backup has reached Blob storage for over 26 hours (journalctl -u fluidbuddha-backup)."
fi
if [ "$deployed_minutes" -gt 60 ]; then
  [ "$(minutes_since last-wal)" -lt 60 ] ||
    add wal-upload "WAL hasn't been uploaded for over an hour (journalctl -u fluidbuddha-wal-upload)."
fi
stuck=$(find "$FB_HOME/backups/wal" -name '*.gz' -mmin +60 | wc -l)
[ "$stuck" -eq 0 ] || add wal-stuck "$stuck archived WAL file(s) have waited over an hour for upload."

if [ -n "$(compose ps -q postgres 2> /dev/null)" ]; then
  failing=$(compose exec -T postgres psql -U fluidbuddha -d fluidbuddha -tAc \
    "SELECT coalesce(last_failed_time > coalesce(last_archived_time, 'epoch'), false) FROM pg_stat_archiver" 2> /dev/null || echo unknown)
  [ "$failing" = f ] || add archiving "Postgres can't archive WAL (pg_stat_archiver says '$failing'). Point-in-time recovery is at risk."
fi

expected="backend console coturn edge postgres redis website"
running=$(compose ps --services --status running 2> /dev/null | sort | xargs || true)
[ "$running" = "$expected" ] || add containers "Containers running: '${running:-none}', expected: '$expected'."
unhealthy=$(docker ps --filter label=com.docker.compose.project=fluidbuddha --filter health=unhealthy --format '{{.Names}}' | xargs || true)
[ -z "$unhealthy" ] || add unhealthy "Unhealthy containers: $unhealthy."

now=$(date +%s)
release=$(basename "$(current_release)")
declare -A active=()
for p in "${problems[@]}"; do
  key=${p%%|*}
  msg=${p#*|}
  active[$key]=1
  log "problem: $msg"
  last=0
  [ ! -f "$ALERTS/$key" ] || last=$(cat "$ALERTS/$key")
  if [ $((now - last)) -ge "$REPEAT_SECONDS" ]; then
    if send_mail "[FluidBuddha $FB_ENV] $msg" "$msg

VM: $(hostname), release $release
What to do: docs/deployment/azure-runbook.md"; then
      echo "$now" > "$ALERTS/$key"
    fi
  fi
done

for f in "$ALERTS"/*; do
  [ -e "$f" ] || continue
  key=$(basename "$f")
  [ -z "${active[$key]:-}" ] || continue
  if send_mail "[FluidBuddha $FB_ENV] Resolved: $key" "The '$key' problem has cleared on $(hostname)."; then
    rm -f "$f"
  fi
done

[ ${#problems[@]} -gt 0 ] || log "all checks passed"
