#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 SSH_HOST SSH_PORT [SSH_KEY]" >&2
  exit 2
}

[[ $# -ge 2 && $# -le 3 ]] || usage

SSH_HOST=$1
SSH_PORT=$2
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SSH_KEY=${3:-$HOME/.ssh/qwen-cloud-vast}
REMOTE_STAGE=/tmp/qwen38-portable

[[ "$SSH_PORT" =~ ^[0-9]+$ ]] || usage
[[ -s "$SSH_KEY" ]] || { echo "SSH key not found: $SSH_KEY" >&2; exit 1; }

SSH=(ssh -o ControlMaster=no -o ControlPath=none -o StrictHostKeyChecking=accept-new \
  -i "$SSH_KEY" -p "$SSH_PORT" "root@$SSH_HOST")
SCP=(scp -o ControlMaster=no -o ControlPath=none -o StrictHostKeyChecking=accept-new \
  -i "$SSH_KEY" -P "$SSH_PORT")

"${SSH[@]}" "install -d -m 0755 '$REMOTE_STAGE' /workspace/qwen38"
"${SCP[@]}" \
  "$SCRIPT_DIR/bootstrap-fresh-vast.sh" \
  "$SCRIPT_DIR/portable-manifest.env" \
  "$SCRIPT_DIR/run-qwen38-cloud.sh" \
  "$SCRIPT_DIR/run-tailscaled.sh" \
  "$SCRIPT_DIR/qwen38-cloud.conf" \
  "$SCRIPT_DIR/tailscaled-qwen.conf" \
  "$SCRIPT_DIR/runtime.env" \
  "root@$SSH_HOST:$REMOTE_STAGE/"

BUILD_CACHE_NAME=llama-build-cuda13-sm120a.tar.zst
if [[ -s "$SCRIPT_DIR/cache/$BUILD_CACHE_NAME" && \
      -s "$SCRIPT_DIR/cache/$BUILD_CACHE_NAME.sha256" ]]; then
  "${SCP[@]}" \
    "$SCRIPT_DIR/cache/$BUILD_CACHE_NAME" \
    "$SCRIPT_DIR/cache/$BUILD_CACHE_NAME.sha256" \
    "root@$SSH_HOST:$REMOTE_STAGE/"
fi

# Copy the local model API key through the private SSH connection.
INFERENCE_KEY_FILE=${QWEN_CLOUD_INFERENCE_KEY_FILE:-$HOME/.config/qwen-cloud/inference_api_key}
[[ -s "$INFERENCE_KEY_FILE" ]] || {
  echo "Inference key not found: $INFERENCE_KEY_FILE" >&2
  exit 1
}
"${SCP[@]}" "$INFERENCE_KEY_FILE" "root@$SSH_HOST:/workspace/qwen38/api_key"
"${SSH[@]}" 'chmod 0600 /workspace/qwen38/api_key'

# Route activation is separate by default so a blue-green replacement does
# not start with the same Tailscale identity as the still-running source.
if [[ "${QWEN38_ACTIVATE_TAILSCALE_STATE:-0}" == "1" && \
      -s "$SCRIPT_DIR/.secrets/tailscaled.state" ]]; then
  "${SSH[@]}" 'install -d -m 0700 /workspace/qwen38/tailscale'
  "${SCP[@]}" "$SCRIPT_DIR/.secrets/tailscaled.state" \
    "root@$SSH_HOST:/workspace/qwen38/tailscale/tailscaled.state"
  "${SSH[@]}" 'chmod 0600 /workspace/qwen38/tailscale/tailscaled.state'
fi

"${SSH[@]}" "bash '$REMOTE_STAGE/bootstrap-fresh-vast.sh'"

echo "Deployment completed on $SSH_HOST:$SSH_PORT"
