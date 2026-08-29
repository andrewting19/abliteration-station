#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run this command as root." >&2; exit 1; }
systemctl disable --now abliteration-station-proxy.service 2>/dev/null || true
rm -f /etc/systemd/system/abliteration-station-proxy.service \
  /usr/local/bin/abliteration-station /usr/local/bin/pi-abliteration-station \
  /usr/local/bin/abliteration-station-configure \
  /usr/local/lib/abliteration-station/idle-proxy.mjs \
  /root/.pi/agent/extensions/abliteration-station-status.ts
systemctl daemon-reload
echo "Removed programs and the service."
echo "Provider instances, /etc/abliteration-station, /root/.config/abliteration-station, and /var/lib/abliteration-station were preserved."
echo "Stop or destroy any rented GPU separately before deleting retained state."
