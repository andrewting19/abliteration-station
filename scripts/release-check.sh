#!/usr/bin/env bash
set -euo pipefail

root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

python3 -m compileall -q src scripts tests
PYTHONPATH=src python3 -m unittest discover -s tests -v

while IFS= read -r script; do
  bash -n "$script"
done < <(find scripts -type f -name '*.sh' -o -type f -name 'qwen-vast' -o -type f -name 'abliteration-station' -o -type f -name 'pi-abliteration-station' -o -type f -name 'inference-key' -o -type f -name 'lifecycle-progress' -o -type f -name 'deferred-performance-gate')

if command -v shellcheck >/dev/null 2>&1; then
  find scripts -type f \( -name '*.sh' -o -name 'qwen-vast' \
    -o -name 'abliteration-station' -o -name 'pi-abliteration-station' \
    -o -name 'inference-key' -o -name 'lifecycle-progress' \
    -o -name 'deferred-performance-gate' \) \
    -exec shellcheck --severity=warning {} +
elif [[ ${REQUIRE_SHELLCHECK:-0} == 1 ]]; then
  echo "ShellCheck is required but not installed." >&2
  exit 1
fi

node --check scripts/idle-proxy.mjs
bash -n benchmarks/run_retained_probe.sh
bash -n benchmarks/prepare_q8_draft.sh
bash -n benchmarks/check_image_host_keys.sh
npm pack --dry-run --json >/tmp/abliteration-station-npm-pack.json
python3 - <<'PY'
import json
from pathlib import Path

pack = json.loads(Path("/tmp/abliteration-station-npm-pack.json").read_text())[0]
names = {entry["path"] for entry in pack["files"]}
required = {
    "package.json",
    "extensions/abliteration-station.ts",
    "scripts/install.sh",
    "scripts/idle-proxy.mjs",
    "scripts/lifecycle-progress",
    "scripts/deferred-performance-gate",
    "config/example.json",
    "patches/llama-slot-checkpoints.patch",
}
missing = sorted(required - names)
if missing:
    raise SystemExit(f"Pi package is missing required files: {missing}")
PY
python3 -m pip wheel --no-deps --no-build-isolation --wheel-dir /tmp/abliteration-station-wheel . >/dev/null

if rg -n --hidden \
  --glob '!scripts/release-check.sh' \
  --glob '!.git/**' \
  --glob '!**/__pycache__/**' \
  --glob '!*.pyc' \
  '(100\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|@gmail\.com|root@kevin)' .; then
  echo "The public-data scan found a blocked value." >&2
  exit 1
fi

if git ls-files -co --exclude-standard | grep -E \
  '(^|/)(tailscaled[.]state|[^/]+[.](gguf|tar|tar[.]zst|key|token))$' | grep -q .; then
  echo "The artifact scan found a blocked file." >&2
  exit 1
fi

echo "RELEASE_CHECK_OK"
