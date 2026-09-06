#!/usr/bin/env bash
# Abliteration Station: start retained services before SSH readiness.
set -euo pipefail
[[ -s /workspace/qwen38/runtime.env && -s /etc/supervisor/conf.d/qwen38-cloud.conf ]] || exit 0
if ! supervisorctl pid >/dev/null 2>&1; then
  supervisord -c /etc/supervisor/supervisord.conf
fi
if ! supervisorctl status qwen38-cloud | grep -Eq 'RUNNING|STARTING'; then
  supervisorctl start qwen38-cloud
fi
if [[ -s /workspace/qwen38/tailscale/tailscaled.state ]] &&
   ! supervisorctl status tailscaled-qwen | grep -Eq 'RUNNING|STARTING'; then
  supervisorctl start tailscaled-qwen
fi
