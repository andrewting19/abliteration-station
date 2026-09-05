#!/usr/bin/env bash
# CPU-only image check. Test containers have no network and no user credentials.
set -euo pipefail
image=${1:?An immutable image reference is required}
[[ "$image" != -* && "$image" == *@sha256:* ]] || exit 2
first=""
second=""
cleanup() {
  for container in "$first" "$second"; do
    if [[ "$container" =~ ^[0-9a-f]{64}$ ]]; then
      docker rm -f "$container" >/dev/null 2>&1 || true
    fi
  done
}
trap cleanup EXIT
key=/var/lib/abliteration-station/ssh-host-keys/ssh_host_ed25519_key
wait_key() {
  for attempt in $(seq 1 50); do
    docker exec "$1" test -s "$key.pub" >/dev/null 2>&1 && return 0
    sleep 0.2
  done
  docker logs "$1" >&2
  return 1
}
fingerprint() {
  docker exec "$1" ssh-keygen -lf "$key.pub" | awk '{print $2}'
}
first=$(docker run -d --network none "$image")
second=$(docker run -d --network none "$image")
wait_key "$first"
wait_key "$second"
original=$(fingerprint "$first")
[[ -n "$original" && "$original" != "$(fingerprint "$second")" ]]
[[ "$(docker exec "$first" stat -c %a "$key")" == 600 ]]
docker exec "$first" test ! -e /etc/ssh/ssh_host_ed25519_key
docker exec "$first" test ! -e /etc/ssh/ssh_host_rsa_key
docker exec "$first" test ! -e /etc/ssh/ssh_host_ecdsa_key
docker restart "$first" >/dev/null
wait_key "$first"
[[ "$original" == "$(fingerprint "$first")" ]]
echo '{"unique_fresh_keys":true,"retained_key_stable":true,"private_key_mode":"600"}'
