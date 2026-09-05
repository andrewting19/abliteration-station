#!/usr/bin/env bash
# Run on the Linux controller against an already stopped, isolated test instance.
# Does not rent, stop, destroy, or change the production route.
set -euo pipefail
instance_id=${1:?Instance ID is required}
cap=${2:?Hourly cap is required}
work_directory=${3:?Private cache-gate directory is required}
capture=${4:?Private captured request is required}
helpers=${5:?Directory containing the Python gate helpers is required}
[[ "$instance_id" =~ ^[0-9]+$ && "$cap" =~ ^[0-9]+([.][0-9]+)?$ ]] || exit 2
[[ "$work_directory" == /* && -d "$work_directory" && -s "$capture" ]] || exit 2
vast_dir=${QWEN38_VAST_DIR:-/usr/local/lib/abliteration-station/vast}
vastai="$vast_dir/.vast-venv/bin/vastai"
config=${ABLITERATION_STATION_CONFIG:-/etc/abliteration-station/config.json}
key_file=$(jq -r '.inference_key_file' "$config")
lifecycle_key=$(jq -r '.providers.vast.lifecycle_token_file' "$config")
ssh_key=${QWEN38_SSH_KEY:-/root/.ssh/abliteration-station-vast}
port=${GATE_LOCAL_PORT:-17074}
[[ "$port" =~ ^[0-9]+$ ]] || exit 2
export ABLITERATION_STATION_PROGRESS_COMMAND=/bin/true
export PYTHONPATH=${PYTHONPATH:-/opt/abliteration-station/src}
started=$(date +%s%N)
state=$("$vastai" show instance "$instance_id" --raw)
jq -e --argjson cap "$cap" '
  .actual_status == "exited" and .intended_status == "stopped" and
  (.dph_total | type) == "number" and .dph_total <= $cap
' >/dev/null <<<"$state" || { echo "Test instance must be stopped and within the price cap." >&2; exit 1; }
"$vastai" start instance "$instance_id" --raw >&2
"$vast_dir/qwen-vast" resume "$instance_id" >&2
state=$("$vastai" show instance "$instance_id" --raw)
host=$(jq -r '.public_ipaddr // empty' <<<"$state")
ssh_port=$(jq -r '.ports["22/tcp"][0].HostPort // empty' <<<"$state")
[[ -n "$host" && "$ssh_port" =~ ^[0-9]+$ ]] || exit 1
control="$work_directory/ssh.sock"
ssh -S "$control" -O exit "root@$host" >/dev/null 2>&1 || true
ssh -M -S "$control" -fN -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 \
  -o StrictHostKeyChecking=accept-new -o "HostKeyAlias=vast-instance-$instance_id" -i "$ssh_key" -p "$ssh_port" \
  -L "127.0.0.1:$port:127.0.0.1:17070" "root@$host"
python3 "$helpers/live_cache_restore_gate.py" --provider-local \
  --instance-id "$instance_id" --upstream "http://127.0.0.1:$port" \
  --work-directory "$work_directory" --inference-key-file "$key_file" \
  --lifecycle-token-file "$lifecycle_key" --cache-command "$vast_dir/qwen-vast" >&2
wake_seconds=$(awk -v start="$started" -v end="$(date +%s%N)" 'BEGIN { printf "%.9f", (end-start)/1000000000 }')
python3 "$helpers/replay_captured_pi.py" "$capture" --stream \
  --base-url "http://127.0.0.1:$port" --api-key-file "$key_file" \
  --max-tokens 4096 --seed 424242 --minimum-cached-tokens 200000 |
  jq --argjson wake "$wake_seconds" '. + {
    wake_seconds: $wake,
    end_to_end_first_token_seconds: ($wake + .first_token_seconds),
    scope: "isolated controller cache and provider resume path; not a live Pi TUI wake"
  }'
