#!/usr/bin/env bash
set -euo pipefail

config=${ABLITERATION_STATION_CONFIG:-/etc/abliteration-station/config.json}
cli=${ABLITERATION_STATION_CLI:-/usr/local/bin/abliteration-station}
proxy_url=${PI_ABLITERATION_STATION_URL:-http://127.0.0.1:17072}

jq -e '
  .provider_order == ["vast"] and
  .model.id == "qwen38-cloud" and
  .model.context_size == 262144 and
  .model.quant_prefix == "Q3_K" and
  .model.temperature == 1.0 and
  .model.reasoning_effort == "medium" and
  .providers.vast.ensure_command == "/usr/local/lib/abliteration-station/vast/ensure"
' "$config" >/dev/null

for secret in /root/.config/abliteration-station/inference_api_key \
  /root/.config/vastai/vast_api_key; do
  [[ -s "$secret" ]]
  [[ $(stat -c %a "$secret") == 600 ]]
  [[ $(stat -c %U "$secret") == root ]]
done

if [[ -s /root/.config/abliteration-station/tailscale_auth_key ]]; then
  [[ $(stat -c %a /root/.config/abliteration-station/tailscale_auth_key) == 600 ]]
  [[ $(stat -c %U /root/.config/abliteration-station/tailscale_auth_key) == root ]]
else
  state=/var/lib/abliteration-station/vast-private/tailscaled.state
  [[ -s "$state" ]]
  [[ $(stat -c %a "$state") == 600 ]]
  [[ $(stat -c %U "$state") == root ]]
fi

systemctl is-enabled --quiet abliteration-station-proxy.service
systemctl is-active --quiet abliteration-station-proxy.service
ss -ltn | grep -q ':17072 '
[[ -x /usr/local/bin/pi-abliteration-station ]]
[[ -s /root/.pi/agent/extensions/abliteration-station-status.ts ]]
[[ -s /root/.pi/agent/models.json ]]
jq -e '.providers["abliteration-station"].models | any(.id == "qwen38-cloud")' \
  /root/.pi/agent/models.json >/dev/null

doctor=$($cli --config "$config" doctor)
jq -e '.vast == [] and length == 1' >/dev/null <<<"$doctor"
health=$(curl -fsS "$proxy_url/healthz")
jq -e '
  .active_requests >= 0 and
  .idle_limit_seconds >= 60 and
  (.wake_in_flight | type) == "boolean"
' >/dev/null <<<"$health"

echo "ABLITERATION_STATION_AUDIT_OK"
