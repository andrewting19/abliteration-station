#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run this command as root." >&2; exit 1; }
systemctl disable --now qwen-cloud-proxy.service 2>/dev/null || true
rm -f /etc/systemd/system/qwen-cloud-proxy.service \
  /usr/local/bin/qwen-cloud /usr/local/bin/pi-qwen-cloud \
  /usr/local/bin/qwen-cloud-configure \
  /usr/local/lib/qwen-cloud/idle-proxy.mjs \
  /root/.pi/agent/extensions/qwen-cloud-wake-status.ts
systemctl daemon-reload
echo "Removed programs and the service."
echo "Provider instances, /etc/qwen-cloud, /root/.config/qwen-cloud, and /var/lib/qwen-cloud were preserved."
echo "Stop or destroy any rented GPU separately before deleting retained state."
