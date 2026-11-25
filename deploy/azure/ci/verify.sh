#!/bin/bash
# Public checks after a release (the Release workflow): HTTPS on every name, readiness, the widget
# loader, the www redirect and the TURN relay. Waits up to 5 minutes per URL, because certificates
# are issued on the first deploy.
#   deploy/azure/ci/verify.sh <site URL> <console URL> <API URL>
set -euo pipefail
site=$1
console=$2
api=$3
failures=0

check() { # <url> [expected status]
  local url=$1 want=${2:-200} code=000 i
  for i in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url" || true)
    if [ "$code" = "$want" ]; then
      echo "ok    $code  $url"
      return 0
    fi
    [ "$i" -eq 30 ] || sleep 10
  done
  echo "::error::$url answered $code, expected $want"
  failures=$((failures + 1))
}

check "$site/"
check "https://www.${site#https://}/" 301
check "$console/login"
check "$api/readyz"
check "$api/widget/loader.js"
curl -s --max-time 15 "$api/readyz" | jq . || true

if python3 "$(dirname "$0")/stun_check.py" "${api#https://}" 3478; then :; else
  echo "::error::The TURN relay didn't answer on UDP 3478: voice handoff won't connect."
  failures=$((failures + 1))
fi

[ "$failures" -eq 0 ] || exit 1
