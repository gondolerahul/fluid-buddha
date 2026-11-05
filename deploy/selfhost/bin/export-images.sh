#!/usr/bin/env bash
# Air-gapped installs (README.md → Air-gapped): on a machine with internet,
# build every image and save them as tarballs to carry across.
#
#   FB_VERSION=2026.11.1 bin/export-images.sh      # → images/*.tar + SHA256SUMS
#
# The build bakes in API_DOMAIN (the console calls it), so use the target's
# .env (or set API_DOMAIN / CONSOLE_DOMAIN) when building.
set -euo pipefail
cd "$(dirname "$0")/.."
export FB_VERSION=${FB_VERSION:-$(date -u +%Y.%m.%d)}
[ -f .env ] || { echo "copy the target install's .env here first (the console image needs its API_DOMAIN)"; exit 1; }
docker compose build
mkdir -p images
for svc in web backend console; do
  docker save "fluidbuddha/$svc:$FB_VERSION" -o "images/fluidbuddha-$svc-$FB_VERSION.tar"
done
for img in pgvector/pgvector:pg16 redis:7-alpine coturn/coturn:4.6; do
  docker pull "$img"
  docker save "$img" -o "images/$(echo "$img" | tr '/:' '__').tar"
done
( cd images && sha256sum ./*.tar > SHA256SUMS )
echo "FB_VERSION=$FB_VERSION" > images/VERSION
echo "images/ is ready: copy it with deploy/selfhost to the target, then run bin/install.sh there."
