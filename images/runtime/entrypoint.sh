#!/usr/bin/env bash
set -euo pipefail

install -d -m 0700 /root/.ssh
if [[ -n "${PUBLIC_KEY:-}" ]]; then
  printf '%s\n' "$PUBLIC_KEY" >>/root/.ssh/authorized_keys
fi
if [[ -e /root/.ssh/authorized_keys ]]; then
  sort -u /root/.ssh/authorized_keys -o /root/.ssh/authorized_keys
  chmod 0600 /root/.ssh/authorized_keys
fi

exec /usr/sbin/sshd -D -e

