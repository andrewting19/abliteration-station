#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run this installer as root." >&2; exit 1; }
source_dir=${1:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}
install_root=${QWEN_CLOUD_INSTALL_ROOT:-/opt/qwen-cloud-lifecycle}
vast_root=${QWEN_CLOUD_VAST_ROOT:-/usr/local/lib/qwen-cloud/vast}

for command in python3 node curl jq ssh scp systemctl flock openssl tailscale pi; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 1; }
done

install -d -m 0755 "$install_root/src" "$vast_root" /etc/qwen-cloud \
  /root/.config/qwen-cloud /root/.config/vastai /root/.pi/agent/extensions \
  /usr/local/lib/qwen-cloud /var/lib/qwen-cloud/benchmarks /run/qwen-cloud
cp -a "$source_dir/src/." "$install_root/src/"
cp -a "$source_dir/scripts/vast/." "$vast_root/"
cp -a "$source_dir/scripts/vast/benchmarks/." /var/lib/qwen-cloud/benchmarks/
install -m 0755 "$source_dir/scripts/vast/replay_captured_pi.py" \
  /var/lib/qwen-cloud/benchmarks/replay_captured_pi.py
install -m 0755 "$source_dir/scripts/qwen-cloud" /usr/local/bin/qwen-cloud
install -m 0755 "$source_dir/scripts/pi-qwen-cloud" /usr/local/bin/pi-qwen-cloud
install -m 0755 "$source_dir/scripts/audit.sh" /usr/local/bin/qwen-cloud-audit
install -m 0755 "$source_dir/scripts/configure.sh" /usr/local/bin/qwen-cloud-configure
install -m 0755 "$source_dir/scripts/uninstall.sh" "$install_root/uninstall.sh"
install -m 0755 "$source_dir/scripts/install-pi-provider.py" "$install_root/install-pi-provider.py"
install -m 0755 "$vast_root/ensure.sh" "$vast_root/ensure"
install -m 0644 "$source_dir/scripts/pi-qwen-cloud-wake-status.ts" \
  /root/.pi/agent/extensions/qwen-cloud-wake-status.ts
install -m 0755 "$source_dir/scripts/idle-proxy.mjs" /usr/local/lib/qwen-cloud/idle-proxy.mjs
install -m 0644 "$source_dir/scripts/qwen-cloud-proxy.service" \
  /etc/systemd/system/qwen-cloud-proxy.service

if [[ ! -s /etc/qwen-cloud/config.json ]]; then
  install -m 0600 "$source_dir/config/example.json" /etc/qwen-cloud/config.json
fi

systemctl daemon-reload
echo "Installed Qwen Cloud Lifecycle."
echo "Next: sudo qwen-cloud-configure"
