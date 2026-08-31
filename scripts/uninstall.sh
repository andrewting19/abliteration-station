#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run this command as root." >&2; exit 1; }
systemctl disable --now abliteration-station-proxy.service 2>/dev/null || true
if [[ -x /opt/abliteration-station/remove-pi-provider.py ]]; then
  PI_CODING_AGENT_DIR=${PI_CODING_AGENT_DIR:-/root/.pi/agent} \
    /opt/abliteration-station/remove-pi-provider.py
fi
if [[ -L /root/bin/pi-qwen38-cloud ]] && \
   [[ $(readlink -f /root/bin/pi-qwen38-cloud) == /usr/local/bin/pi-abliteration-station ]]; then
  rm -f /root/bin/pi-qwen38-cloud
fi
rm -f /etc/systemd/system/abliteration-station-proxy.service \
  /usr/local/bin/abliteration-station /usr/local/bin/pi-abliteration-station \
  /usr/local/bin/abliteration-station-audit \
  /usr/local/bin/abliteration-station-configure \
  /root/.pi/agent/extensions/abliteration-station-status.ts
rm -rf /usr/local/lib/abliteration-station /opt/abliteration-station
systemctl daemon-reload
echo "Removed Abliteration Station programs, Pi registration, code, and service."
echo "Provider instances, /etc/abliteration-station, /root/.config/abliteration-station, and /var/lib/abliteration-station were preserved."
echo "Stop or destroy any rented GPU separately before deleting retained state."
