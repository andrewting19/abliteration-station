#!/usr/bin/env bash
set -euo pipefail

ROOT=${QWEN38_ROOT:-/workspace/qwen38}
BASE_URL=${QWEN38_BASE_URL:-http://127.0.0.1:17070}
KEY_FILE=${QWEN38_KEY_FILE:-$ROOT/api_key}
SLOT_ID=${QWEN38_SLOT_ID:-0}
ACTION=${1:-}
FILENAME=${2:-pi-session.slot}

[[ "$SLOT_ID" =~ ^[0-9]+$ ]] || { echo "Slot ID must be numeric." >&2; exit 2; }
[[ "$FILENAME" =~ ^[A-Za-z0-9._-]+$ ]] || {
  echo "The checkpoint filename contains unsafe characters." >&2
  exit 2
}
[[ -s "$KEY_FILE" ]] || { echo "The inference key is missing." >&2; exit 1; }

request() {
  curl -fsS --max-time "${QWEN38_SLOT_TIMEOUT_SECONDS:-900}" \
    -H "Authorization: Bearer $(<"$KEY_FILE")" \
    -H "Content-Type: application/json" \
    --data "{\"filename\":\"$FILENAME\"}" \
    "$BASE_URL/slots/$SLOT_ID?action=$1"
}

case "$ACTION" in
  save)
    started=$(date +%s)
    response=$(request save)
    path="$ROOT/slot-cache/$FILENAME"
    sidecar="$path.ckpt"
    [[ -s "$path" ]] || { echo "The server did not create $path." >&2; exit 1; }
    [[ -s "$sidecar" ]] || { echo "The server did not create $sidecar." >&2; exit 1; }
    jq -n \
      --argjson response "$response" \
      --arg filename "$FILENAME" \
      --arg sha256 "$(sha256sum "$path" | cut -d' ' -f1)" \
      --arg checkpoint_sha256 "$(sha256sum "$sidecar" | cut -d' ' -f1)" \
      --argjson bytes "$(stat -c %s "$path")" \
      --argjson checkpoint_bytes "$(stat -c %s "$sidecar")" \
      --argjson elapsed_seconds "$(( $(date +%s) - started ))" \
      '{action:"save",filename:$filename,sha256:$sha256,checkpoint_sha256:$checkpoint_sha256,bytes:$bytes,checkpoint_bytes:$checkpoint_bytes,elapsed_seconds:$elapsed_seconds,response:$response}'
    ;;
  restore)
    started=$(date +%s)
    path="$ROOT/slot-cache/$FILENAME"
    [[ -s "$path" && -s "$path.ckpt" ]] || {
      echo "The slot file or checkpoint sidecar is missing." >&2
      exit 1
    }
    response=$(request restore)
    jq -n \
      --argjson response "$response" \
      --arg filename "$FILENAME" \
      --argjson elapsed_seconds "$(( $(date +%s) - started ))" \
      '{action:"restore",filename:$filename,elapsed_seconds:$elapsed_seconds,response:$response}'
    ;;
  *)
    echo "Usage: $0 {save|restore} [SAFE_FILENAME]" >&2
    exit 2
    ;;
esac
