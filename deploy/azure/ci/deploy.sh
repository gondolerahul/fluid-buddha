#!/bin/bash
# Runs a release on the VM through Azure Run Command (the Release workflow's deploy job).
#   deploy/azure/ci/deploy.sh <resource group> <vm> <sha>
# The VM fetches the release bundle from the registry if it doesn't have it, then runs that release's
# own deploy script (vm/fluidbuddha-deploy), which rolls back by itself if the new release fails.
set -euo pipefail
rg=$1
vm=$2
sha=$3
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "::error::not a commit SHA: $sha"; exit 2; }

# Runs as root on the VM. Plain sh: Run Command doesn't promise bash for the outer script.
read -r -d '' remote << 'EOF' || true
#!/bin/sh
set -eu
SHA=__SHA__
. /etc/fluidbuddha/host.env
REL=/opt/fluidbuddha/releases/$SHA
if [ ! -x "$REL/vm/fluidbuddha-deploy" ]; then
  az login --identity --allow-no-subscriptions --output none --only-show-errors
  az acr login --name "$ACR_NAME" --output none --only-show-errors
  IMG=$ACR_LOGIN_SERVER/fluidbuddha/release:$SHA
  docker pull --quiet "$IMG" > /dev/null
  TMP=$(mktemp -d /opt/fluidbuddha/releases/.fetch.XXXXXX)
  CID=$(docker create "$IMG" /bin/true)
  docker cp "$CID:/bundle/." "$TMP/"
  docker rm "$CID" > /dev/null
  rm -rf "$REL"
  mv "$TMP" "$REL"
fi
LOG=/var/log/fluidbuddha/deploy-$(date +%Y%m%d-%H%M%S)-$SHA.log
RC=0
"$REL/vm/fluidbuddha-deploy" "$SHA" > "$LOG" 2>&1 || RC=$?
tail -n 30 "$LOG"
echo "FB_DEPLOY_EXIT=$RC log=$LOG"
EOF
remote=${remote//__SHA__/$sha}

echo "Deploying $sha on $vm ($rg). Run Command shows the last lines; the full log stays on the VM."
out=$(az vm run-command invoke --resource-group "$rg" --name "$vm" --command-id RunShellScript \
  --scripts "$remote" --query "value[0].message" -o tsv)
echo "$out"
if ! grep -q '^FB_DEPLOY_EXIT=0 ' <<< "$out"; then
  echo "::error::The deploy failed on the VM (see the log above). A failed release rolls back to the previous one by itself."
  exit 1
fi
