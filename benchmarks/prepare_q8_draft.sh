#!/usr/bin/env bash
# Run only on an isolated test worker. Does not change the running profile.
set -euo pipefail
source /tmp/qwen38-portable/portable-manifest.env
root=/workspace/qwen38
input="$root/models/$QWEN38_DRAFT_BF16_FILE"
output="$root/models/Qwen3.8-27B-DFlash2-Q8_0.gguf"
base=${QWEN38_HF_BASE:-https://huggingface.co}
if ! test -s "$input" || ! echo "$QWEN38_DRAFT_BF16_SHA256  $input" | sha256sum -c - >/dev/null 2>&1; then
  timeout 240 aria2c --allow-overwrite=true --auto-file-renaming=false \
    --file-allocation=none --max-connection-per-server=8 --split=8 --min-split-size=8M \
    --connect-timeout=10 --timeout=30 --max-tries=2 --retry-wait=2 \
    --summary-interval=20 --console-log-level=warn --dir "$root/models" \
    --out "$QWEN38_DRAFT_BF16_FILE" \
    "$base/$QWEN38_DRAFT_REPO/resolve/$QWEN38_DRAFT_REVISION/$QWEN38_DRAFT_BF16_FILE?download=true"
fi
echo "$QWEN38_DRAFT_BF16_SHA256  $input" | sha256sum -c -
bin="$root/llama.cpp-kvpatch/build/bin"
LD_LIBRARY_PATH="$bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  "$bin/llama-quantize" "$input" "$output" Q8_0 8
sha256sum "$output"
