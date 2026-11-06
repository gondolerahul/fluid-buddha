#!/usr/bin/env bash
# Load image tarballs made by bin/export-images.sh (air-gapped installs).
#   bin/import-images.sh [images-dir]
set -euo pipefail
cd "$(dirname "$0")/.."
DIR=${1:-images}
( cd "$DIR" && sha256sum -c SHA256SUMS )
for t in "$DIR"/*.tar; do docker load -i "$t"; done
if [ -f "$DIR/VERSION" ]; then
  v=$(cut -d= -f2 "$DIR/VERSION")
  if grep -q '^FB_VERSION=' .env 2>/dev/null; then sed -i "s|^FB_VERSION=.*|FB_VERSION=$v|" .env; else echo "FB_VERSION=$v" >> .env; fi
  echo "images loaded: FB_VERSION=$v"
fi
