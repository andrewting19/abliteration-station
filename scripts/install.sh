#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run this installer as root." >&2; exit 1; }
source_dir=${1:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}
install_root=${ABLITERATION_STATION_INSTALL_ROOT:-/opt/abliteration-station}
vast_root=${ABLITERATION_STATION_VAST_ROOT:-/usr/local/lib/abliteration-station/vast}

for command in python3 node curl jq ssh scp systemctl flock openssl tailscale; do
  command -v "$command" >/dev/null || { echo "Missing required command: $command" >&2; exit 1; }
done

pi_path=${PI_ABLITERATION_STATION_BIN:-$(command -v pi || true)}
if [[ -z "$pi_path" ]]; then
  for candidate in /root/.nvm/versions/node/*/bin/pi; do
    [[ -x "$candidate" ]] && pi_path=$candidate
  done
fi
[[ -n "$pi_path" && -x "$pi_path" ]] || {
  echo "Pi is not installed. Set PI_ABLITERATION_STATION_BIN to its executable." >&2
  exit 1
}

install -d -m 0755 "$install_root/src" "$install_root/benchmarks" "$vast_root" /etc/abliteration-station \
  /root/.config/abliteration-station /root/.config/vastai \
  /usr/local/lib/abliteration-station /var/lib/abliteration-station/benchmarks \
  /var/lib/abliteration-station/metrics /run/abliteration-station
cp -a "$source_dir/src/." "$install_root/src/"
cp -a "$source_dir/benchmarks/." "$install_root/benchmarks/"
cp -a "$source_dir/scripts/vast/." "$vast_root/"
cp -a "$source_dir/scripts/vast/benchmarks/." /var/lib/abliteration-station/benchmarks/
install -m 0755 "$source_dir/scripts/vast/replay_captured_pi.py" \
  /var/lib/abliteration-station/benchmarks/replay_captured_pi.py
install -m 0755 "$source_dir/scripts/vast/tool_loop_gate.py" \
  /var/lib/abliteration-station/benchmarks/tool_loop_gate.py
install -m 0755 "$source_dir/scripts/abliteration-station" /usr/local/bin/abliteration-station
install -m 0755 "$source_dir/scripts/pi-abliteration-station" /usr/local/bin/pi-abliteration-station
install -m 0755 "$source_dir/scripts/audit.sh" /usr/local/bin/abliteration-station-audit
install -m 0755 "$source_dir/scripts/configure.sh" /usr/local/bin/abliteration-station-configure
install -m 0755 "$source_dir/scripts/uninstall.sh" "$install_root/uninstall.sh"
install -m 0755 "$source_dir/scripts/install-pi-provider.py" "$install_root/install-pi-provider.py"
install -m 0755 "$source_dir/scripts/remove-pi-provider.py" "$install_root/remove-pi-provider.py"
install -m 0755 "$vast_root/ensure.sh" "$vast_root/ensure"
install -m 0755 "$source_dir/scripts/idle-proxy.mjs" /usr/local/lib/abliteration-station/idle-proxy.mjs
install -m 0644 "$source_dir/scripts/abliteration-station-proxy.service" \
  /etc/systemd/system/abliteration-station-proxy.service

if [[ ! -s /etc/abliteration-station/config.json ]]; then
  install -m 0600 "$source_dir/config/example.json" /etc/abliteration-station/config.json
fi

# Version 0.2 registers the provider from its Pi package. Remove the old copied
# extension and models.json entry so Pi does not load two copies.
rm -f /root/.pi/agent/extensions/abliteration-station-status.ts \
  /root/.pi/agent/extensions/qwen-cloud-wake-status.ts
PI_CODING_AGENT_DIR=${PI_CODING_AGENT_DIR:-/root/.pi/agent} \
  "$install_root/remove-pi-provider.py"

systemctl daemon-reload
echo "Installed Abliteration Station."
echo "Next: sudo abliteration-station-configure"
