#!/usr/bin/env bash
set -euo pipefail

config=${QWEN_CLOUD_CONFIG:-/etc/qwen-cloud/config.json}
cli=${QWEN_CLOUD_CLI:-/usr/local/bin/qwen-cloud}
proxy_url=${PI_QWEN_CLOUD_URL:-http://127.0.0.1:17072}

jq -e '
  .provider_order == ["vast"] and
  .model.id == "qwen38-cloud" and
  .model.context_size == 262144 and
  .model.quant_prefix == "Q3_K" and
  .model.temperature == 1.0 and
  .model.reasoning_effort == "medium" and
  .providers.vast.ensure_command == "/usr/local/lib/qwen-cloud/vast/ensure"
' "$config" >/dev/null

for secret in /root/.config/qwen-cloud/inference_api_key \
  /root/.config/qwen-cloud/tailscale_auth_key /root/.config/vastai/vast_api_key; do
  [[ -s "$secret" ]]
  [[ $(stat -c %a "$secret") == 600 ]]
  [[ $(stat -c %U "$secret") == root ]]
done

systemctl is-enabled --quiet qwen-cloud-proxy.service
systemctl is-active --quiet qwen-cloud-proxy.service
ss -ltn | grep -q ':17072 '
[[ -x /usr/local/bin/pi-qwen-cloud ]]
[[ -s /root/.pi/agent/extensions/qwen-cloud-wake-status.ts ]]
[[ -s /root/.pi/agent/models.json ]]
jq -e '.providers["qwen-cloud"].models | any(.id == "qwen38-cloud")' \
  /root/.pi/agent/models.json >/dev/null

doctor=$($cli --config "$config" doctor)
jq -e '.vast == [] and length == 1' >/dev/null <<<"$doctor"
health=$(curl -fsS "$proxy_url/healthz")
jq -e '
  .active_requests >= 0 and
  .idle_limit_seconds >= 60 and
  (.wake_in_flight | type) == "boolean"
' >/dev/null <<<"$health"

echo "QWEN_CLOUD_AUDIT_OK"
