#!/usr/bin/env bash
set -euo pipefail

# Some Vast hosts create or rewrite this injected file with permissive
# ownership or mode after the container starts. OpenSSH then rejects every
# otherwise valid account key. Keep correcting it during the startup window.
echo "qwen38-onstart: starting SSH permission repair"
nohup bash -c '
  for _ in $(seq 1 120); do
    if [[ -e /root/.ssh/authorized_keys ]]; then
      chown root:root /root /root/.ssh /root/.ssh/authorized_keys
      chmod 0700 /root
      chmod 0700 /root/.ssh
      chmod 0600 /root/.ssh/authorized_keys
    fi
    sleep 1
  done
  echo "qwen38-onstart: SSH permission repair complete"
' >/tmp/qwen38-ssh-permission-repair.log 2>&1 </dev/null &

install -d -m 0755 /workspace/qwen38
