#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

python3 -m compileall -q src scripts tests
PYTHONPATH=src python3 -m unittest discover -s tests -v

while IFS= read -r script; do
  bash -n "$script"
done < <(find scripts -type f -name '*.sh' -o -type f -name 'qwen-vast' -o -type f -name 'qwen-cloud' -o -type f -name 'pi-qwen-cloud' -o -type f -name 'inference-key')

node --check scripts/idle-proxy.mjs
python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/qwen-cloud-wheel . >/dev/null

if rg -n --hidden \
  --glob '!scripts/release-check.sh' \
  --glob '!**/__pycache__/**' \
  --glob '!*.pyc' \
  '(100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|andrewting|@gmail\.com|root@kevin|GPUHub|gpuhub|TensorDock|tensordock)' .; then
  echo "The public-data scan found a blocked value." >&2
  exit 1
fi

if find . -type f \( -name '*.gguf' -o -name '*.tar' -o -name '*.tar.zst' \
  -o -name 'tailscaled.state' -o -name '*.key' -o -name '*.token' \) | grep -q .; then
  echo "The artifact scan found a blocked file." >&2
  exit 1
fi

echo "RELEASE_CHECK_OK"
