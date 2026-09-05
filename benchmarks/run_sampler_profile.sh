#!/usr/bin/env bash
# Run only on a fresh isolated worker. No tool calls from the response execute.
set -euo pipefail
capture=${1:?A captured request is required}
directory=/workspace/qwen38/benchmarks/sampler-profile
[[ -s "$capture" && -s "$directory/sampler_profile.so" ]] || exit 2
if [[ -s /workspace/qwen38/tailscale/tailscaled.state ]]; then
  echo "Refusing a profiling run on a worker with private routing state." >&2
  exit 2
fi
grep -q QWEN38_SAMPLER_PROFILE_LIBRARY /opt/supervisor-scripts/run-qwen38-cloud.sh
install -m 0644 "$directory/qwen38-profile.conf" /etc/supervisor/conf.d/qwen38-profile.conf
supervisorctl stop qwen38-cloud >/dev/null 2>&1 || true
supervisorctl reread >/dev/null
supervisorctl update >/dev/null
cleanup() { supervisorctl stop qwen38-profile >/dev/null 2>&1 || true; }
trap cleanup EXIT
previous_reports=$(grep -c 'QWEN_SAMPLER_PROFILE ' /var/log/portal/qwen38-profile.err.log 2>/dev/null || true)
previous_reports=${previous_reports:-0}
supervisorctl start qwen38-profile >/dev/null
ready=0
for attempt in $(seq 1 90); do
  if curl -fsS --max-time 2 -H "Authorization: Bearer $(</workspace/qwen38/api_key)" \
      http://127.0.0.1:17070/health >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || { echo "Profile model did not become ready." >&2; exit 1; }
profile_pid=$(supervisorctl pid qwen38-profile)
[[ "$profile_pid" =~ ^[1-9][0-9]*$ ]] || exit 1
python3 "$directory/replay_captured_pi.py" "$capture" --stream --max-tokens 4096 --seed 424242
supervisorctl stop qwen38-profile >/dev/null
current_reports=$(grep -c 'QWEN_SAMPLER_PROFILE ' /var/log/portal/qwen38-profile.err.log 2>/dev/null || true)
(( ${current_reports:-0} > previous_reports )) || { echo "The run did not produce a new sampler report." >&2; exit 1; }
grep -E '^QWEN_(SAMPLER|DECODE|STATE|READ|SYNC)_PROFILE ' /var/log/portal/qwen38-profile.err.log |
  sed 's/^[^ ]* //' |
  jq -cs --argjson pid "$profile_pid" --argjson require_decode "${QWEN38_REQUIRE_DECODE_PROFILE:-0}" '
    map(select(.pid == $pid)) |
    if any(.[]; .kind == "sampler") and
       ($require_decode == 0 or (any(.[]; .kind == "decode" and .role == "target") and any(.[]; .kind == "decode" and .role == "draft")))
    then .[] else error("Required reports are missing for this process") end'
