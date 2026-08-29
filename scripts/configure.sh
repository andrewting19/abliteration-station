#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID:-$(id -u)} -eq 0 ]] || { echo "Run this command as root." >&2; exit 1; }
secret_dir=/root/.config/qwen-cloud
vast_secret_dir=/root/.config/vastai
vast_root=${QWEN_CLOUD_VAST_ROOT:-/usr/local/lib/qwen-cloud/vast}
install_root=${QWEN_CLOUD_INSTALL_ROOT:-/opt/qwen-cloud-lifecycle}
install -d -m 0700 "$secret_dir" "$vast_secret_dir" /root/.ssh

read_secret() {
  local variable_name=$1
  local prompt=$2
  local value=${!variable_name:-}
  if [[ -z "$value" ]]; then
    [[ -t 0 ]] || { echo "$variable_name is required in non-interactive mode." >&2; exit 1; }
    read -r -s -p "$prompt: " value
    echo
  fi
  [[ -n "$value" ]] || { echo "$variable_name cannot be empty." >&2; exit 1; }
  printf '%s\n' "$value"
}

read_secret VAST_API_KEY "Vast.ai API key" | install -m 0600 /dev/stdin "$vast_secret_dir/vast_api_key"
read_secret TAILSCALE_AUTH_KEY "Reusable Tailscale auth key" | \
  install -m 0600 /dev/stdin "$secret_dir/tailscale_auth_key"

if [[ ! -s "$secret_dir/inference_api_key" ]]; then
  openssl rand -hex 32 | install -m 0600 /dev/stdin "$secret_dir/inference_api_key"
fi
if [[ ! -s /root/.ssh/qwen-cloud-vast ]]; then
  ssh-keygen -q -t ed25519 -N '' -f /root/.ssh/qwen-cloud-vast
fi

PI_CODING_AGENT_DIR=${PI_CODING_AGENT_DIR:-/root/.pi/agent} \
  "$install_root/install-pi-provider.py"
"$vast_root/qwen-vast" help >/dev/null
python3 /var/lib/qwen-cloud/benchmarks/generate.py
systemctl enable --now qwen-cloud-proxy.service
echo "Configuration is complete."
echo "Start Pi with: pi-qwen-cloud"
