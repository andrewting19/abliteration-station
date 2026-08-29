#!/usr/bin/env bash
set -euo pipefail

ROOT=/workspace/qwen38
API_KEY_FILE="$ROOT/api_key"

if [[ -r "$ROOT/runtime.env" ]]; then
  # This file is root-only and contains non-secret runtime tuning values.
  source "$ROOT/runtime.env"
fi

MODEL_FILE="${QWEN38_MODEL_FILE:-Qwen3.8-27B-Unleashed-UD-Q3_K_XL.gguf}"
MODEL="$ROOT/models/$MODEL_FILE"
CONTEXT_SIZE="${QWEN38_CONTEXT_SIZE:-262144}"
PARALLEL="${QWEN38_PARALLEL:-1}"
BUILD_DIR="${QWEN38_BUILD_DIR:-build}"
LLAMA_DIR="${QWEN38_LLAMA_DIR:-$ROOT/llama.cpp}"
SERVER="$LLAMA_DIR/$BUILD_DIR/bin/llama-server"
DRAFT_QUANT="${QWEN38_DRAFT_QUANT:-Q8_0}"
DRAFT="$ROOT/models/Qwen3.8-27B-DFlash2-${DRAFT_QUANT}.gguf"
DRAFT_N_MAX="${QWEN38_DRAFT_N_MAX:-6}"
DRAFT_P_MIN="${QWEN38_DRAFT_P_MIN:-}"
SPEC_TYPE="${QWEN38_SPEC_TYPE:-draft-dflash}"
NGRAM_N="${QWEN38_NGRAM_N:-}"
NGRAM_M="${QWEN38_NGRAM_M:-}"
CACHE_TYPE_K="${QWEN38_CACHE_TYPE_K:-q4_0}"
CACHE_TYPE_V="${QWEN38_CACHE_TYPE_V:-q4_0}"
DRAFT_CACHE_TYPE_K="${QWEN38_DRAFT_CACHE_TYPE_K:-q4_0}"
DRAFT_CACHE_TYPE_V="${QWEN38_DRAFT_CACHE_TYPE_V:-q4_0}"
POLL="${QWEN38_POLL:-50}"
PRIO="${QWEN38_PRIO:-0}"
NO_HOST="${QWEN38_NO_HOST:-0}"
export GGML_CUDA_GRAPH_OPT="${QWEN38_CUDA_GRAPH_OPT:-0}"
AUTO_THREADS=$(nproc)
if (( AUTO_THREADS > 16 )); then
  AUTO_THREADS=16
fi
THREADS="${QWEN38_THREADS:-$AUTO_THREADS}"
PREWARM="${QWEN38_PREWARM:-1}"
TEMPERATURE="${QWEN38_TEMPERATURE:-1.0}"
CHAT_TEMPLATE="${QWEN38_CHAT_TEMPLATE:-}"

EXTRA_ARGS=()
SPEC_ARGS=()
if [[ "$NO_HOST" == "1" ]]; then
  EXTRA_ARGS+=(--no-host)
fi
if [[ -n "$CHAT_TEMPLATE" ]]; then
  EXTRA_ARGS+=(--chat-template "$CHAT_TEMPLATE")
fi
if [[ -n "$DRAFT_P_MIN" ]]; then
  SPEC_ARGS+=(--spec-draft-p-min "$DRAFT_P_MIN")
fi
if [[ -n "$NGRAM_N" || -n "$NGRAM_M" ]]; then
  if [[ -z "$NGRAM_N" || -z "$NGRAM_M" ]]; then
    echo "QWEN38_NGRAM_N and QWEN38_NGRAM_M must be set together" >&2
    exit 1
  fi
  SPEC_ARGS+=(--spec-ngram-simple-size-n "$NGRAM_N")
  SPEC_ARGS+=(--spec-ngram-simple-size-m "$NGRAM_M")
fi

for path in "$SERVER" "$MODEL" "$DRAFT" "$API_KEY_FILE"; do
  if [[ ! -s "$path" ]]; then
    echo "Required file is missing or empty: $path" >&2
    exit 1
  fi
done

if [[ "$PREWARM" == "1" ]]; then
  # Sequential reads avoid very slow random mmap page faults on some Vast
  # overlay disks. Both files fit in host RAM on the selected 5090 offers.
  dd if="$MODEL" of=/dev/null bs=64M status=none
  dd if="$DRAFT" of=/dev/null bs=64M status=none
fi

mkdir -p "$ROOT/slot-cache"

exec "$SERVER" \
  --model "$MODEL" \
  --spec-draft-model "$DRAFT" \
  --spec-type "$SPEC_TYPE" \
  --spec-draft-ngl all \
  --spec-draft-type-k "$DRAFT_CACHE_TYPE_K" \
  --spec-draft-type-v "$DRAFT_CACHE_TYPE_V" \
  --spec-draft-n-max "$DRAFT_N_MAX" \
  "${SPEC_ARGS[@]}" \
  --alias qwen38-cloud \
  --api-key-file "$API_KEY_FILE" \
  --host 127.0.0.1 \
  --port 17070 \
  --ctx-size "$CONTEXT_SIZE" \
  --parallel "$PARALLEL" \
  --batch-size 2048 \
  --ubatch-size 512 \
  --cache-type-k "$CACHE_TYPE_K" \
  --cache-type-v "$CACHE_TYPE_V" \
  --flash-attn on \
  --gpu-layers all \
  --fit off \
  --threads "$THREADS" \
  --threads-batch "$THREADS" \
  --poll "$POLL" \
  --poll-draft 1 \
  --prio "$PRIO" \
  --prio-draft "$PRIO" \
  --ctx-checkpoints 4 \
  --slot-save-path "$ROOT/slot-cache" \
  --cache-ram 0 \
  --cache-prompt \
  --cache-reuse 0 \
  --no-context-shift \
  --jinja \
  --reasoning-format deepseek \
  --reasoning on \
  --reasoning-effort medium \
  --temperature "$TEMPERATURE" \
  --top-p 0.95 \
  --top-k 20 \
  --min-p 0.0 \
  --repeat-penalty 1.0 \
  --metrics \
  --no-webui \
  --timeout 7200 \
  "${EXTRA_ARGS[@]}"
