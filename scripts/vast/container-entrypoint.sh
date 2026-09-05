#!/usr/bin/env bash
set -euo pipefail

prepare_host_key() {
  local directory=$1
  install -d -m 0700 "$directory"
  local key="$directory/ssh_host_ed25519_key"
  if [[ ! -s "$key" ]]; then
    ssh-keygen -q -t ed25519 -N '' -f "$key"
  fi
  chmod 0600 "$key"
  printf '%s\n' "$key"
}

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

# Keys belong to the container, outside the portable model workspace. Never
# copy one worker's SSH identity with its model/KV data to a new worker.
SSH_HOST_KEY_ARGS=()
key_directory=/var/lib/abliteration-station/ssh-host-keys
if [[ -s "$key_directory/ssh_host_ed25519_key" || \
      ! -s /workspace/qwen38/runtime.env || \
      ! -s /etc/ssh/ssh_host_ed25519_key ]]; then
  SSH_HOST_KEY_ARGS=(-h "$(prepare_host_key "$key_directory")")
fi
# Legacy retained containers keep their existing key until replacement.

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

exec /usr/sbin/sshd -D -e "${SSH_HOST_KEY_ARGS[@]}"
