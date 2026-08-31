#!/usr/bin/env bash
set -euo pipefail

QWEN_VAST_DIR=${QWEN38_VAST_DIR:-/usr/local/lib/abliteration-station/vast}
VASTAI="$QWEN_VAST_DIR/.vast-venv/bin/vastai"
QWEN_VAST="$QWEN_VAST_DIR/qwen-vast"
INSTANCE_FILE=${QWEN38_INSTANCE_FILE:-/var/lib/abliteration-station/vast-instance-id}
LIFECYCLE_PROXY_URL=${QWEN38_LIFECYCLE_PROXY_URL:-http://127.0.0.1:17072}
CONFIG_FILE=${ABLITERATION_STATION_CONFIG:-/etc/abliteration-station/config.json}
MODEL_URL=${QWEN38_MODEL_URL:-$(jq -r '.providers.vast.upstream' "$CONFIG_FILE")}
PRICE_CAP=${QWEN38_MAX_DPH:-0.53}
LOCK_FILE=${QWEN38_ENSURE_LOCK:-/run/lock/qwen38-vast-ensure.lock}
API_KEY_COMMAND=${QWEN38_API_KEY_COMMAND:-$QWEN_VAST_DIR/inference-key}

die() {
  echo "Abliteration Station start failed: $*" >&2
  exit 1
}

for required in "$VASTAI" "$QWEN_VAST" "$API_KEY_COMMAND"; do
  [[ -x "$required" ]] || die "required executable is missing: $required"
done
[[ "$PRICE_CAP" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "QWEN38_MAX_DPH must be numeric"

ensure_lock_timeout_seconds=${QWEN38_ENSURE_LOCK_TIMEOUT_SECONDS:-7200}
exec 9>"$LOCK_FILE"
echo "Checking the private Qwen server..." >&2
flock -w "$ensure_lock_timeout_seconds" 9 ||
  die "another start operation did not finish within ${ensure_lock_timeout_seconds} seconds"

curl -fsS -X POST "$LIFECYCLE_PROXY_URL/lifecycle/inhibit?seconds=7200" >/dev/null ||
  die "the local Qwen idle controller is not available"
release_inhibit() {
  curl -fsS -X POST "$LIFECYCLE_PROXY_URL/lifecycle/release" >/dev/null 2>&1 || true
}
trap release_inhibit EXIT

api_key=$($API_KEY_COMMAND)

model_is_ready() {
  local response
  response=$(curl -fsS --connect-timeout 2 --max-time 5 \
    -H "Authorization: Bearer $api_key" "$MODEL_URL/v1/models" 2>/dev/null) || return 1
  jq -e '
    any(.data[]?;
      .id == "qwen38-cloud" and
      .meta.n_ctx == 262144 and
      (.meta.ftype | startswith("Q3_K")))
  ' >/dev/null <<<"$response"
}

chat_is_ready() {
  local response
  response=$(curl -fsS --max-time 180 \
    -H "Authorization: Bearer $api_key" \
    -H "Content-Type: application/json" \
    "$MODEL_URL/v1/chat/completions" \
    -d '{"model":"qwen38-cloud","messages":[{"role":"user","content":"Reply with OK."}],"max_tokens":64,"temperature":1,"stream":false,"chat_template_kwargs":{"enable_thinking":true,"reasoning_effort":"medium"}}' \
    2>/dev/null) || return 1
  jq -e '
    (.usage.prompt_tokens // 0) > 0 and
    (.usage.completion_tokens // 0) > 0 and
    ((.choices[0].message.content // "") | length) +
      ((.choices[0].message.reasoning_content // "") | length) > 0
  ' >/dev/null <<<"$response"
}

if model_is_ready; then
  echo "The private Qwen server is ready." >&2
  exit 0
fi

old_instance_id=""
if [[ -r "$INSTANCE_FILE" ]]; then
  old_instance_id=$(tr -d '[:space:]' <"$INSTANCE_FILE")
  [[ "$old_instance_id" =~ ^[0-9]+$ ]] || old_instance_id=""
fi

resume_existing() {
  local instance_id=$1
  local instance_json actual_status start_result
  instance_json=$($VASTAI show instance "$instance_id" --raw 2>/dev/null) || return 1
  jq -e --argjson instance_id "$instance_id" '
    .error != true and ((.id // .contract_id) == $instance_id)
  ' >/dev/null 2>&1 <<<"$instance_json" || return 1
  actual_status=$(jq -r '.actual_status // empty' <<<"$instance_json")

  case "$actual_status" in
    running|loading) ;;
    *)
      echo "Starting retained Vast instance $instance_id..." >&2
      start_result=$($VASTAI start instance "$instance_id" --raw 2>&1) || return 1
      printf '%s\n' "$start_result" >&2
      jq -e '.error == true' >/dev/null 2>&1 <<<"$start_result" && return 1
      ;;
  esac

  "$QWEN_VAST" resume "$instance_id" >&2 || return 1
  for _ in $(seq 1 90); do
    model_is_ready && chat_is_ready && return 0
    sleep 2
  done
  return 1
}

if [[ -n "$old_instance_id" ]]; then
  if resume_existing "$old_instance_id"; then
    echo "Retained Qwen instance $old_instance_id is ready." >&2
    exit 0
  fi
  echo "The retained instance could not pass the Q3/262K chat gate. A fresh host is required." >&2
  $VASTAI stop instance "$old_instance_id" --raw >/dev/null 2>&1 || true
fi

rollback_new_instance() {
  local failed_instance_id=$1
  echo "Stopping and removing failed fresh instance $failed_instance_id." >&2
  $VASTAI stop instance "$failed_instance_id" --raw >/dev/null 2>&1 || true
  $VASTAI destroy instance "$failed_instance_id" --yes --raw >/dev/null 2>&1 || true
  if [[ -n "$old_instance_id" ]]; then
    printf '%s\n' "$old_instance_id" | install -m 0644 /dev/stdin "$INSTANCE_FILE"
  else
    rm -f "$INSTANCE_FILE"
  fi
}

excluded_offer_ids=""
for rental_attempt in 1 2 3; do
  echo "Rental attempt $rental_attempt of 3: selecting one verified RTX 5090 below \$$PRICE_CAP per hour..." >&2
  if ! created=$(QWEN38_EXCLUDE_OFFER_IDS="$excluded_offer_ids" \
      "$QWEN_VAST" rent-best on-demand "$PRICE_CAP" --rent); then
    echo "No usable offer was secured on attempt $rental_attempt." >&2
    continue
  fi
  new_instance_id=$(jq -r '.new_contract // empty' <<<"$created")
  offer_id=$(jq -r '.offer_id // empty' <<<"$created")
  if [[ ! "$new_instance_id" =~ ^[0-9]+$ || ! "$offer_id" =~ ^[0-9]+$ ]]; then
    echo "Vast did not return a valid instance and offer ID." >&2
    continue
  fi
  if [[ -n "$excluded_offer_ids" ]]; then
    excluded_offer_ids+=",$offer_id"
  else
    excluded_offer_ids=$offer_id
  fi

  printf '%s\n' "$new_instance_id" | install -m 0644 /dev/stdin "$INSTANCE_FILE"
  echo "Deploying Qwen3.8 Q3 and DFlash on Vast instance $new_instance_id..." >&2
  if ! "$QWEN_VAST" deploy "$new_instance_id" >&2; then
    rollback_new_instance "$new_instance_id"
    continue
  fi

  echo "Running the 120K real-Pi decode gate on Vast instance $new_instance_id..." >&2
  if ! "$QWEN_VAST" performance-gate "$new_instance_id" >&2; then
    echo "Vast instance $new_instance_id did not sustain 80 decode TPS." >&2
    rollback_new_instance "$new_instance_id"
    continue
  fi

  if [[ -n "$old_instance_id" ]]; then
    route_args=("$new_instance_id" "$old_instance_id")
  else
    route_args=("$new_instance_id")
  fi
  if ! "$QWEN_VAST" activate-route "${route_args[@]}" >&2; then
    rollback_new_instance "$new_instance_id"
    continue
  fi

  for _ in $(seq 1 90); do
    if model_is_ready && chat_is_ready; then
      echo "Fresh Qwen instance $new_instance_id passed the Q3/262K chat gate." >&2
      if [[ -n "$old_instance_id" ]]; then
        echo "Removing replaced instance $old_instance_id to stop its storage charge." >&2
        $VASTAI destroy instance "$old_instance_id" --yes --raw >/dev/null 2>&1 ||
          echo "Warning: replaced instance $old_instance_id still needs manual removal." >&2
      fi
      exit 0
    fi
    sleep 2
  done

  rollback_new_instance "$new_instance_id"
done

die "three fresh RTX 5090 rentals failed the private Q3/262K chat gate"
