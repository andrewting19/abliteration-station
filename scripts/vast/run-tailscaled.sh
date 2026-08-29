#!/usr/bin/env bash
set -euo pipefail

mkdir -p /workspace/qwen38/tailscale /var/run/tailscale

exec /usr/sbin/tailscaled \
  --tun=userspace-networking \
  --state=/workspace/qwen38/tailscale/tailscaled.state \
  --socket=/var/run/tailscale/tailscaled.sock
