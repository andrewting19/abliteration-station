#!/usr/bin/env bash
set -euo pipefail

config=${ABLITERATION_STATION_CONFIG:-/etc/abliteration-station/config.json}
cli=${ABLITERATION_STATION_CLI:-/usr/local/bin/abliteration-station}
proxy_url=${PI_ABLITERATION_STATION_URL:-http://127.0.0.1:17072}

jq -e '
  (.provider_order | type == "array" and length > 0) and
  (.providers | type == "object" and length > 0) and
  ([.provider_order[] as $name | .providers[$name] != null] | all) and
  (.model.id | type == "string" and length > 0) and
  (.model.context_size | type == "number" and . > 0)
' "$config" >/dev/null

mapfile -t secret_files < <(jq -r '
  [.inference_key_file, (.providers[] | .lifecycle_token_file?)] |
  map(select(type == "string" and length > 0)) | unique[]
' "$config")
for secret in "${secret_files[@]}"; do
  [[ -s "$secret" ]]
  [[ $(stat -c %a "$secret") == 600 ]]
  [[ $(stat -c %U "$secret") == root ]]
done

if jq -e '.providers.vast != null' "$config" >/dev/null && \
   [[ -s /root/.config/abliteration-station/tailscale_auth_key ]]; then
  [[ $(stat -c %a /root/.config/abliteration-station/tailscale_auth_key) == 600 ]]
  [[ $(stat -c %U /root/.config/abliteration-station/tailscale_auth_key) == root ]]
elif jq -e '.providers.vast != null' "$config" >/dev/null; then
  state=/var/lib/abliteration-station/vast-private/tailscaled.state
  [[ -s "$state" ]]
  [[ $(stat -c %a "$state") == 600 ]]
  [[ $(stat -c %U "$state") == root ]]
fi

systemctl is-enabled --quiet abliteration-station-proxy.service
systemctl is-active --quiet abliteration-station-proxy.service
ss -ltn | grep -q ':17072 '
[[ -x /usr/local/bin/pi-abliteration-station ]]
pi_dir=${PI_CODING_AGENT_DIR:-/root/.pi/agent}
package_manifest=$(find "$pi_dir/git" "$pi_dir/npm/node_modules" \
  -path '*/abliteration-station/package.json' -type f -print -quit 2>/dev/null || true)
[[ -n "$package_manifest" && -s "$package_manifest" ]]
jq -e '
  .name == "@andrewting19/abliteration-station" and
  (.pi.extensions | index("./extensions") != null)
' "$package_manifest" >/dev/null
[[ -s "$(dirname -- "$package_manifest")/extensions/abliteration-station.ts" ]]
[[ ! -e "$pi_dir/extensions/abliteration-station-status.ts" ]]
[[ ! -e "$pi_dir/extensions/qwen-cloud-wake-status.ts" ]]

doctor=$($cli --config "$config" doctor)
jq -e 'length > 0 and ([.[] == []] | all)' >/dev/null <<<"$doctor"
health=$(curl -fsS "$proxy_url/healthz")
jq -e '
  .active_requests >= 0 and
  .idle_limit_seconds >= 60 and
  (.wake_in_flight | type) == "boolean"
' >/dev/null <<<"$health"

echo "ABLITERATION_STATION_AUDIT_OK"
