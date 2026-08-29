#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ENV=${QWEN38_RUNTIME_ENV:-/workspace/qwen38/runtime.env}
REPLAY=${QWEN38_REPLAY:-/tmp/replay_captured_pi.py}
WARM_CAPTURE=${QWEN38_WARM_CAPTURE:-/tmp/001-chat-completions.json}
GATE_CAPTURE=${QWEN38_GATE_CAPTURE:-/tmp/002-chat-completions.json}
KEY_FILE=${QWEN38_KEY_FILE:-/workspace/qwen38/api_key}
RESULTS=${QWEN38_SWEEP_RESULTS:-/tmp/dflash-sweep.jsonl}
BASELINE=$(sed -n 's/^QWEN38_DRAFT_N_MAX=//p' "$RUNTIME_ENV")

[[ "$BASELINE" =~ ^[0-9]+$ ]] || {
  echo "The baseline DFlash value is invalid." >&2
  exit 1
}

set_n_max() {
  local value=$1
  sed -i "s/^QWEN38_DRAFT_N_MAX=.*/QWEN38_DRAFT_N_MAX=$value/" "$RUNTIME_ENV"
  supervisorctl restart qwen38-cloud >/dev/null
  for _ in $(seq 1 180); do
    if curl -fsS --max-time 2 \
      -H "Authorization: Bearer $(cat "$KEY_FILE")" \
      http://127.0.0.1:17070/health >/dev/null 2>&1; then
      return
    fi
    sleep 2
  done
  echo "The server did not become healthy for n_max=$value." >&2
  return 1
}

restore() {
  set_n_max "$BASELINE" || true
}
trap restore EXIT

: >"$RESULTS"
for value in "$@"; do
  [[ "$value" =~ ^[0-9]+$ ]] || {
    echo "Each n_max value must be an integer." >&2
    exit 1
  }
  set_n_max "$value"
  warm=$(python3 "$REPLAY" "$WARM_CAPTURE" \
    --base-url http://127.0.0.1:17070 --api-key-file "$KEY_FILE" --max-tokens 512)
  gate=$(python3 "$REPLAY" "$GATE_CAPTURE" \
    --base-url http://127.0.0.1:17070 --api-key-file "$KEY_FILE" --max-tokens 2048)
  jq -nc --argjson n_max "$value" --argjson warm "$warm" --argjson gate "$gate" \
    '{n_max:$n_max,warm:$warm,gate:$gate}' | tee -a "$RESULTS"
done
