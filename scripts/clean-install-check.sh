#!/usr/bin/env bash
set -euo pipefail

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required for the clean-install check." >&2
  exit 1
}

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
docker run --rm -i -v "$root:/src:ro" ubuntu:24.04 bash -s <<'CONTAINER'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 nodejs curl jq openssh-client openssl util-linux >/dev/null
install -d -m 0755 /test-bin
for command in systemctl tailscale pi; do
  printf '#!/usr/bin/env bash\nexit 0\n' >"/test-bin/$command"
  chmod 0755 "/test-bin/$command"
done
export PATH="/test-bin:$PATH"

/src/scripts/install.sh /src
test -x /usr/local/bin/abliteration-station
test -x /usr/local/bin/pi-abliteration-station
test -x /usr/local/bin/abliteration-station-audit
test -x /opt/abliteration-station/remove-pi-provider.py
test -x /usr/local/lib/abliteration-station/vast/qwen-vast
test -s /etc/abliteration-station/config.json
test ! -e /root/.pi/agent/extensions/abliteration-station-status.ts

/src/scripts/uninstall.sh
test ! -e /usr/local/bin/abliteration-station
test ! -e /usr/local/bin/pi-abliteration-station
test ! -e /usr/local/bin/abliteration-station-audit
test ! -e /usr/local/lib/abliteration-station
test ! -e /opt/abliteration-station
test -s /etc/abliteration-station/config.json
echo CLEAN_INSTALL_CHECK_OK
CONTAINER
