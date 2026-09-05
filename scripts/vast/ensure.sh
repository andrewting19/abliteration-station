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
PROGRESS_COMMAND=${ABLITERATION_STATION_PROGRESS_COMMAND:-/usr/local/bin/abliteration-station-progress}
DEFERRED_GATE_COMMAND=${ABLITERATION_STATION_DEFERRED_GATE_COMMAND:-/usr/local/bin/abliteration-station-deferred-gate}
USE_PROVIDER_COPY=${QWEN38_USE_PROVIDER_COPY:-0}
ALLOW_CUDA_13_0_FALLBACK=${QWEN38_ALLOW_CUDA_13_0_FALLBACK:-1}
FRESH_RENTAL_ATTEMPTS=${QWEN38_FRESH_RENTAL_ATTEMPTS:-3}
OFFER_ACQUIRE_ATTEMPTS=${QWEN38_OFFER_ACQUIRE_ATTEMPTS:-5}
FAILED_HOSTS_FILE=${QWEN38_FAILED_HOSTS_FILE:-/var/lib/abliteration-station/failed-bootstrap-offers.tsv}
FAILED_HOST_TTL=${QWEN38_FAILED_HOST_TTL_SECONDS:-1800}

die() {
  if [[ -x "$PROGRESS_COMMAND" ]]; then
    "$PROGRESS_COMMAND" failed "$*" 0 >/dev/null || true
  fi
  echo "Abliteration Station start failed: $*" >&2
  exit 1
}

for required in "$VASTAI" "$QWEN_VAST" "$API_KEY_COMMAND" "$PROGRESS_COMMAND" "$DEFERRED_GATE_COMMAND"; do
  [[ -x "$required" ]] || die "required executable is missing: $required"
done
[[ "$PRICE_CAP" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "QWEN38_MAX_DPH must be numeric"

ensure_lock_timeout_seconds=${QWEN38_ENSURE_LOCK_TIMEOUT_SECONDS:-7200}
exec 9>"$LOCK_FILE"
echo "Checking the private Qwen server..." >&2
"$PROGRESS_COMMAND" checking "Checking the private Qwen route" 10
flock -w "$ensure_lock_timeout_seconds" 9 ||
  die "another start operation did not finish within ${ensure_lock_timeout_seconds} seconds"

curl -fsS -X POST "$LIFECYCLE_PROXY_URL/lifecycle/inhibit?seconds=7200" >/dev/null ||
  die "the local Qwen idle controller is not available"
release_inhibit() {
  curl -fsS -X POST "$LIFECYCLE_PROXY_URL/lifecycle/release" >/dev/null 2>&1 || true
}
trap release_inhibit EXIT

failed_offers_file=$(mktemp /run/abliteration-station/failed-offers.XXXXXX)
cleanup() {
  rm -f "$failed_offers_file"
  release_inhibit
}
trap cleanup EXIT

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
  "$PROGRESS_COMMAND" ready "Qwen is ready" 0
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

  if ! jq -e --argjson cap "$PRICE_CAP" '
      .dph_total as $price |
      ($price | type) == "number" and $price >= 0 and $price <= $cap
    ' >/dev/null <<<"$instance_json"; then
    echo "The retained instance price is unknown or exceeds the current hourly cap; it will not be resumed." >&2
    "$PROGRESS_COMMAND" retained_price_rejected "Retained GPU price exceeds the cap or is unknown; selecting a replacement" 30 "$instance_id"
    return 1
  fi

  case "$actual_status" in
    running|loading) ;;
    *)
      echo "Starting retained Vast instance $instance_id..." >&2
      "$PROGRESS_COMMAND" retained_start "Requesting the retained Vast GPU" 55 "$instance_id"
      start_result=$($VASTAI start instance "$instance_id" --raw 2>&1) || return 1
      printf '%s\n' "$start_result" >&2
      jq -e '.error == true' >/dev/null 2>&1 <<<"$start_result" && return 1
      if grep -qi 'resources are currently unavailable' <<<"$start_result"; then
        "$PROGRESS_COMMAND" retained_wait "Waiting briefly for the retained GPU; Vast queued the request" 45 "$instance_id"
      else
        "$PROGRESS_COMMAND" retained_boot "Starting Qwen on the retained GPU" 55 "$instance_id"
      fi
      ;;
  esac

  "$QWEN_VAST" resume "$instance_id" >&2 || return 1
  for _ in $(seq 1 90); do
    # A generation probe replaces the user's slot. The exact retained runtime
    # is checked by resume; let the user's request verify generation.
    model_is_ready && return 0
    sleep 2
  done
  return 1
}

if [[ -n "$old_instance_id" ]]; then
  if resume_existing "$old_instance_id"; then
    "$PROGRESS_COMMAND" ready "Qwen is ready on the retained GPU" 0 "$old_instance_id"
    echo "Retained Qwen instance $old_instance_id is ready." >&2
    exit 0
  fi
  echo "The retained instance could not pass the Q3/262K chat gate. A fresh host is required." >&2
  "$PROGRESS_COMMAND" replacement_select "The retained GPU is unavailable; selecting a replacement" 30
  $VASTAI stop instance "$old_instance_id" --raw >/dev/null 2>&1 || true
fi

rollback_new_instance() {
  local failed_instance_id=$1
  # Keep a bounded rejection across Pi retries, not just this shell process.
  if [[ "${offer_id:-}" =~ ^[0-9]+$ ]]; then
    printf '%s\t%s\n' "$(date +%s)" "$offer_id" >>"$FAILED_HOSTS_FILE"
  fi
  echo "Stopping and removing failed fresh instance $failed_instance_id." >&2
  $VASTAI stop instance "$failed_instance_id" --raw >/dev/null 2>&1 || true
  $VASTAI destroy instance "$failed_instance_id" --yes --raw >/dev/null 2>&1 || true
  if [[ -n "$old_instance_id" && "$USE_PROVIDER_COPY" == 1 ]]; then
    printf '%s\n' "$old_instance_id" | install -m 0644 /dev/stdin "$INSTANCE_FILE"
  else
    rm -f "$INSTANCE_FILE"
  fi
}

[[ "$FRESH_RENTAL_ATTEMPTS" =~ ^[1-3]$ ]] ||
  die "QWEN38_FRESH_RENTAL_ATTEMPTS must be 1, 2, or 3"
[[ "$OFFER_ACQUIRE_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] ||
  die "QWEN38_OFFER_ACQUIRE_ATTEMPTS must be a positive integer"

excluded_offer_ids=""
if [[ -r "$FAILED_HOSTS_FILE" ]]; then
  [[ "$FAILED_HOST_TTL" =~ ^[1-9][0-9]*$ ]] || die "Failed-host TTL must be a positive integer"
  excluded_offer_ids=$(awk -v now="$(date +%s)" -v ttl="$FAILED_HOST_TTL" \
    '$1 ~ /^[0-9]+$/ && $2 ~ /^[0-9]+$/ && now-$1 < ttl {print $2}' \
    "$FAILED_HOSTS_FILE" | sort -nu | paste -sd, -)
  if [[ -n "$excluded_offer_ids" ]]; then
    tr ',' '\n' <<<"$excluded_offer_ids" >>"$failed_offers_file"
  fi
fi
secured_any_instance=0
for rental_attempt in $(seq 1 "$FRESH_RENTAL_ATTEMPTS"); do
  "$PROGRESS_COMMAND" replacement_select "Selecting replacement RTX 5090, attempt $rental_attempt of $FRESH_RENTAL_ATTEMPTS" 30
  echo "Rental attempt $rental_attempt of $FRESH_RENTAL_ATTEMPTS: selecting one verified RTX 5090 below \$$PRICE_CAP per hour..." >&2
  if ! created=$(QWEN38_EXCLUDE_OFFER_IDS="$excluded_offer_ids" \
      QWEN38_FAILED_OFFERS_FILE="$failed_offers_file" \
      QWEN38_CUDA_MIN=13.2 QWEN38_RENT_BEST_ATTEMPTS="$OFFER_ACQUIRE_ATTEMPTS" \
      "$QWEN_VAST" rent-best on-demand "$PRICE_CAP" --rent); then
    excluded_offer_ids=$(sort -nu "$failed_offers_file" | paste -sd, -)
    if [[ "$ALLOW_CUDA_13_0_FALLBACK" == 1 ]]; then
      echo "No CUDA 13.2 offer was secured. Trying a matching CUDA 13.0 host." >&2
      "$PROGRESS_COMMAND" replacement_select "No CUDA 13.2 GPU is available; trying CUDA 13.0" 25
      if ! created=$(QWEN38_EXCLUDE_OFFER_IDS="$excluded_offer_ids" \
          QWEN38_FAILED_OFFERS_FILE="$failed_offers_file" \
          QWEN38_CUDA_MIN=13.0 QWEN38_RENT_BEST_ATTEMPTS=10 \
          "$QWEN_VAST" rent-best on-demand "$PRICE_CAP" --rent); then
        excluded_offer_ids=$(sort -nu "$failed_offers_file" | paste -sd, -)
        echo "No usable offer was secured on attempt $rental_attempt." >&2
        continue
      fi
    else
      echo "No fast CUDA 13.2 offer was secured. The CUDA 13.0 fallback is disabled." >&2
      continue
    fi
  fi
  new_instance_id=$(jq -r '.new_contract // empty' <<<"$created")
  offer_id=$(jq -r '.offer_id // empty' <<<"$created")
  if [[ ! "$new_instance_id" =~ ^[0-9]+$ || ! "$offer_id" =~ ^[0-9]+$ ]]; then
    echo "Vast did not return a valid instance and offer ID." >&2
    continue
  fi
  secured_any_instance=1
  if [[ -n "$excluded_offer_ids" ]]; then
    excluded_offer_ids+=",$offer_id"
  else
    excluded_offer_ids=$offer_id
  fi

  printf '%s\n' "$new_instance_id" | install -m 0644 /dev/stdin "$INSTANCE_FILE"
  copied_workspace=0
  if [[ -n "$old_instance_id" && "$USE_PROVIDER_COPY" == 1 ]]; then
    echo "Copying the verified Qwen workspace from $old_instance_id to $new_instance_id..." >&2
    "$PROGRESS_COMMAND" workspace_copy "Copying the verified model workspace inside Vast" 240 "$new_instance_id"
    if "$QWEN_VAST" copy "$old_instance_id" "$new_instance_id" >&2 &&
       "$QWEN_VAST" activate-copy "$new_instance_id" "$old_instance_id" >&2; then
      copied_workspace=1
    else
      echo "The provider-side workspace copy failed. Using the public bootstrap fallback." >&2
    fi
  fi
  if (( copied_workspace == 0 )); then
    echo "Deploying Qwen3.8 Q3 and DFlash on Vast instance $new_instance_id..." >&2
    "$PROGRESS_COMMAND" public_bootstrap \
      "Starting the pinned Qwen image; an uncached first pull can take longer" 90 "$new_instance_id"
    deploy_env=()
    if [[ -z "$old_instance_id" ]]; then
      deploy_env+=(QWEN38_ACTIVATE_TAILSCALE_STATE=1)
    fi
    if ! env "${deploy_env[@]}" "$QWEN_VAST" deploy "$new_instance_id" >&2; then
      rollback_new_instance "$new_instance_id"
      continue
    fi
  fi

  if [[ -n "$old_instance_id" ]]; then
    route_args=("$new_instance_id" "$old_instance_id")
  else
    route_args=("$new_instance_id")
  fi
  "$PROGRESS_COMMAND" private_route "Restoring the private Tailscale route" 45 "$new_instance_id"
  route_env=()
  if [[ -z "$old_instance_id" && "$copied_workspace" == 0 ]]; then
    route_env+=(QWEN38_PRIVATE_ROUTE_PRELOADED=1)
  fi
  if ! env "${route_env[@]}" "$QWEN_VAST" activate-route "${route_args[@]}" >&2; then
    rollback_new_instance "$new_instance_id"
    continue
  fi

  for _ in $(seq 1 90); do
    if model_is_ready && chat_is_ready; then
      echo "Fresh Qwen instance $new_instance_id passed the Q3/262K chat gate." >&2
      "$PROGRESS_COMMAND" ready "Qwen is ready on the replacement GPU" 0 "$new_instance_id"
      install -d -m 0700 /var/lib/abliteration-station/performance-gates
      nohup "$DEFERRED_GATE_COMMAND" "$new_instance_id" \
        >"/var/lib/abliteration-station/performance-gates/runner-$new_instance_id.log" 2>&1 </dev/null &
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

if (( secured_any_instance == 0 )); then
  die "No compatible RTX 5090 could be rented within the hourly cap of $PRICE_CAP. No model test ran."
fi
die "$FRESH_RENTAL_ATTEMPTS fresh RTX 5090 rental attempts failed during bootstrap or model checks"
