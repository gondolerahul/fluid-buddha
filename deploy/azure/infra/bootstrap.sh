#!/bin/bash
# First boot of a FluidBuddha VM, run by cloud-init (cloud-init.yaml). Safe to run again.
# Adds what deploys need beyond Ubuntu's packages, and the folders they use. The release itself
# (compose file, scripts, timers) comes with each deploy: vm/fluidbuddha-deploy.
set -euo pipefail
log() { echo "[fluidbuddha-bootstrap] $*"; }
# shellcheck source=/dev/null
. /etc/fluidbuddha/host.env

# 1. Swap. Postgres, two Next.js servers and the voice agent share 8 GiB. Swap keeps a spike from
#    waking the out-of-memory killer. Basv2 VMs have no temporary disk, so it lives on the OS disk.
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
sysctl --system >/dev/null

# 2. Azure CLI, from Microsoft's repository. The VM's managed identity reads Key Vault, pulls from
#    the registry and uploads backups with it.
if ! command -v az >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor --yes -o /etc/apt/keyrings/microsoft.gpg
  chmod a+r /etc/apt/keyrings/microsoft.gpg
  cat > /etc/apt/sources.list.d/azure-cli.sources <<EOF
Types: deb
URIs: https://packages.microsoft.com/repos/azure-cli/
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: main
Architectures: $(dpkg --print-architecture)
Signed-by: /etc/apt/keyrings/microsoft.gpg
EOF
  apt-get update -q
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q azure-cli
fi

# 3. Containers must not reach the instance metadata service: its tokens open Key Vault, the
#    registry and the backups. The host keeps access (deploys and backups use it).
cat > /usr/local/sbin/fluidbuddha-firewall <<'EOF'
#!/bin/sh
iptables -C DOCKER-USER -d 169.254.169.254 -j DROP 2>/dev/null \
  || iptables -I DOCKER-USER -d 169.254.169.254 -j DROP
EOF
chmod 0755 /usr/local/sbin/fluidbuddha-firewall
cat > /etc/systemd/system/fluidbuddha-firewall.service <<'EOF'
[Unit]
Description=FluidBuddha: keep containers away from the instance metadata service
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/fluidbuddha-firewall

[Install]
WantedBy=docker.service
EOF

# 4. Folders. Postgres runs as uid 999 in its container: it owns its data and the WAL archive.
install -d -m 0755 /opt/fluidbuddha /opt/fluidbuddha/releases /opt/fluidbuddha/data \
  /opt/fluidbuddha/data/caddy /opt/fluidbuddha/data/caddy-config /var/log/fluidbuddha
install -d -m 0700 /opt/fluidbuddha/secrets /var/lib/fluidbuddha
install -d -m 0700 -o 999 -g 999 /opt/fluidbuddha/data/postgres
install -d -m 0750 /opt/fluidbuddha/backups /opt/fluidbuddha/backups/dumps \
  /opt/fluidbuddha/backups/base /opt/fluidbuddha/backups/wal-uploaded
install -d -m 0750 -o 999 -g 999 /opt/fluidbuddha/backups/wal /opt/fluidbuddha/backups/restore-wal

# 5. Services.
systemctl daemon-reload
systemctl enable --now docker.service
systemctl enable --now fluidbuddha-firewall.service
usermod -aG docker "$ADMIN_USER"

date -Is > /var/lib/fluidbuddha/bootstrap-done
log "done: $(docker --version); $(docker compose version); azure-cli $(az version --query '"azure-cli"' -o tsv)"
