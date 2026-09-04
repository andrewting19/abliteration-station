#!/usr/bin/env bash
set -euo pipefail

install -d -m 0700 /root/.ssh
if [[ -n "${PUBLIC_KEY_B64:-}" ]]; then
  printf '%s' "$PUBLIC_KEY_B64" | base64 -d >>/root/.ssh/authorized_keys
fi
if [[ -n "${PUBLIC_KEY:-}" ]]; then
  printf '%s\n' "$PUBLIC_KEY" >>/root/.ssh/authorized_keys
fi
if [[ -e /root/.ssh/authorized_keys ]]; then
  sort -u /root/.ssh/authorized_keys -o /root/.ssh/authorized_keys
  chown root:root /root /root/.ssh /root/.ssh/authorized_keys
  chmod 0700 /root /root/.ssh
  chmod 0600 /root/.ssh/authorized_keys
fi

install -d -m 0755 /workspace/qwen38

# A retained container already has its validated service files and model data.
# Start model loading while Vast brings up SSH. A new container does not have
# these files yet and continues to the normal deployment path.
if [[ -s /workspace/qwen38/runtime.env && \
      -s /etc/supervisor/conf.d/qwen38-cloud.conf ]]; then
  supervisord -c /etc/supervisor/supervisord.conf
  if [[ -s /workspace/qwen38/tailscale/tailscaled.state ]]; then
    supervisorctl start tailscaled-qwen >/dev/null
  fi
fi

exec /usr/sbin/sshd -D -e
