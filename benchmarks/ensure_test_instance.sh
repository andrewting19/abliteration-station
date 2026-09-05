#!/usr/bin/env bash
# Retained-instance-only adapter for isolated Pi acceptance. Never rents.
set -euo pipefail
root=${ABLITERATION_STATION_TEST_ROOT:?Test root required}
instance=$(cat "$root/instance-id")
[[ "$instance" =~ ^[0-9]+$ ]] || exit 2
vast=/usr/local/lib/abliteration-station/vast
guard=/var/lib/abliteration-station/benchmarks/private/qwen-goal-five-dollar-state.json
jq -e '.stopped == false' "$guard" >/dev/null
state=$("$vast/.vast-venv/bin/vastai" show instance "$instance" --raw)
jq -e '.dph_total <= 0.53 and (.label | startswith("qwen-goal5-20260905-"))' <<< "$state" >/dev/null
# Provider status can lag a just-completed stop request. Set the desired state
# explicitly, then use the readiness wait rather than trusting the first read.
"$vast/.vast-venv/bin/vastai" start instance "$instance" --raw >&2
ABLITERATION_STATION_PROGRESS_COMMAND=/bin/true "$vast/qwen-vast" resume "$instance" >&2
state=$("$vast/.vast-venv/bin/vastai" show instance "$instance" --raw)
host=$(jq -er '.public_ipaddr' <<< "$state")
port=$(jq -er '.ports["22/tcp"][0].HostPort' <<< "$state")
ssh -S "$root/tunnel.sock" -O exit "root@$host" >/dev/null 2>&1 || true
ssh -M -S "$root/tunnel.sock" -fN -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=10 -o ServerAliveCountMax=2 -o StrictHostKeyChecking=accept-new \
  -o "HostKeyAlias=vast-instance-$instance" -i /root/.ssh/abliteration-station-vast \
  -p "$port" -L 127.0.0.1:17075:127.0.0.1:17070 "root@$host"
