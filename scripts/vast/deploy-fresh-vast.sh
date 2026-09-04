#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 SSH_HOST SSH_PORT [SSH_KEY] [INSTANCE_ID]" >&2
  exit 2
}

[[ $# -ge 2 && $# -le 4 ]] || usage

SSH_HOST=$1
SSH_PORT=$2
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/portable-manifest.env"
SSH_KEY=${3:-$HOME/.ssh/abliteration-station-vast}
INSTANCE_ID=${4:-null}
PROGRESS_COMMAND=${ABLITERATION_STATION_PROGRESS_COMMAND:-/usr/local/bin/abliteration-station-progress}
REMOTE_STAGE=/tmp/qwen38-portable
PATCH_FILE="$SCRIPT_DIR/patches/llama-slot-checkpoints.patch"
if [[ ! -s "$PATCH_FILE" ]]; then
  PATCH_FILE="$SCRIPT_DIR/../../patches/llama-slot-checkpoints.patch"
fi
[[ -s "$PATCH_FILE" ]] || { echo "The verified llama.cpp patch is missing." >&2; exit 1; }

[[ "$SSH_PORT" =~ ^[0-9]+$ ]] || usage
[[ -s "$SSH_KEY" ]] || { echo "SSH key not found: $SSH_KEY" >&2; exit 1; }
[[ "$INSTANCE_ID" == null || "$INSTANCE_ID" =~ ^[0-9]+$ ]] || usage

progress() {
  [[ -x "$PROGRESS_COMMAND" ]] || return 0
  "$PROGRESS_COMMAND" "$1" "$2" "$3" "$INSTANCE_ID"
}

CONTROL_DIR=$(mktemp -d /run/abliteration-station/ssh.XXXXXX)
CONTROL_PATH="$CONTROL_DIR/control"
close_control_connection() {
  ssh -o ControlPath="$CONTROL_PATH" -O exit "root@$SSH_HOST" >/dev/null 2>&1 || true
  rmdir "$CONTROL_DIR" >/dev/null 2>&1 || true
}
trap close_control_connection EXIT

SSH=(ssh -o ControlMaster=auto -o ControlPersist=60 -o ControlPath="$CONTROL_PATH" -o StrictHostKeyChecking=accept-new \
  -i "$SSH_KEY" -p "$SSH_PORT" "root@$SSH_HOST")
SCP=(scp -o ControlMaster=auto -o ControlPersist=60 -o ControlPath="$CONTROL_PATH" -o StrictHostKeyChecking=accept-new \
  -i "$SSH_KEY" -P "$SSH_PORT")

"${SSH[@]}" "install -d -m 0755 '$REMOTE_STAGE' /workspace/qwen38"
progress runtime_assets "Sending the verified runtime assets" 45
"${SCP[@]}" \
  "$SCRIPT_DIR/bootstrap-fresh-vast.sh" \
  "$SCRIPT_DIR/portable-manifest.env" \
  "$PATCH_FILE" \
  "$SCRIPT_DIR/run-qwen38-cloud.sh" \
  "$SCRIPT_DIR/slot-cache-control.sh" \
  "$SCRIPT_DIR/run-tailscaled.sh" \
  "$SCRIPT_DIR/container-entrypoint.sh" \
  "$SCRIPT_DIR/qwen38-cloud.conf" \
  "$SCRIPT_DIR/tailscaled-qwen.conf" \
  "$SCRIPT_DIR/runtime.env" \
  "root@$SSH_HOST:$REMOTE_STAGE/"

BUILD_CACHE_NAME=$QWEN38_BUILD_CACHE_FILE
if [[ "${QWEN38_SEND_RUNTIME_CACHE:-0}" == 1 && \
      -s "$SCRIPT_DIR/cache/$BUILD_CACHE_NAME" && \
      -s "$SCRIPT_DIR/cache/$BUILD_CACHE_NAME.sha256" ]]; then
  "${SCP[@]}" \
    "$SCRIPT_DIR/cache/$BUILD_CACHE_NAME" \
    "$SCRIPT_DIR/cache/$BUILD_CACHE_NAME.sha256" \
    "root@$SSH_HOST:$REMOTE_STAGE/"
fi

# Copy the local model API key through the private SSH connection.
INFERENCE_KEY_FILE=${ABLITERATION_STATION_INFERENCE_KEY_FILE:-$HOME/.config/abliteration-station/inference_api_key}
[[ -s "$INFERENCE_KEY_FILE" ]] || {
  echo "Inference key not found: $INFERENCE_KEY_FILE" >&2
  exit 1
}
"${SCP[@]}" "$INFERENCE_KEY_FILE" "root@$SSH_HOST:/workspace/qwen38/api_key"
"${SSH[@]}" 'chmod 0600 /workspace/qwen38/api_key'

# Route activation is separate by default so a blue-green replacement does
# not start with the same Tailscale identity as the still-running source.
PRIVATE_STATE_FILE="${ABLITERATION_STATION_PRIVATE_STATE_DIR:-/var/lib/abliteration-station/vast-private}/tailscaled.state"
if [[ "${QWEN38_ACTIVATE_TAILSCALE_STATE:-0}" == "1" && \
      -s "$PRIVATE_STATE_FILE" ]]; then
  "${SSH[@]}" 'install -d -m 0700 /workspace/qwen38/tailscale'
  "${SCP[@]}" "$PRIVATE_STATE_FILE" \
    "root@$SSH_HOST:/workspace/qwen38/tailscale/tailscaled.state"
  "${SSH[@]}" 'chmod 0600 /workspace/qwen38/tailscale/tailscaled.state'
fi

progress runtime_prepare "Preparing the CUDA runtime and inference server" 120
"${SSH[@]}" "QWEN38_TRUST_PINNED_IMAGE='${QWEN38_TRUST_PINNED_IMAGE:-0}' bash '$REMOTE_STAGE/bootstrap-fresh-vast.sh'" 2>&1 | while IFS= read -r line; do
  printf '%s\n' "$line"
  case "$line" in
    *"Cloning into"*|*"Using the verified cached RTX 5090 build"*)
      progress runtime_prepare "Preparing the pinned llama.cpp runtime" 90 ;;
    *"Qwen3.8-27B-Unleashed-UD-Q3_K_XL.gguf.part"*)
      progress target_download "Downloading the 12 GB Qwen target" 180 ;;
    *"Qwen3.8-27B-DFlash2-BF16.gguf.part"*)
      progress draft_download "Downloading the 3.5 GB draft source" 60 ;;
    *"llama_quantize: quantizing"*)
      progress draft_quantize "Quantizing the draft model" 20 ;;
    *"qwen38-cloud: started"*|*"Qwen3.8 service is healthy"*)
      progress model_load "Loading Qwen and DFlash into the RTX 5090" 45 ;;
  esac
done

echo "Deployment completed on $SSH_HOST:$SSH_PORT"
