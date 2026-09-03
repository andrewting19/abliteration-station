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

exec /usr/sbin/sshd -D -e
