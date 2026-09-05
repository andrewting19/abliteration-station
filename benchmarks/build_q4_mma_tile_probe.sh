#!/usr/bin/env bash
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$project/scripts/vast/portable-manifest.env"
task_dir=$(mktemp -d /tmp/q4-mma-tile.XXXXXX)
output="$project/dist/q4-mma-tile-probe"
[[ ! -e "$output" ]] || exit 1
install -d "$output"
git clone --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp.git "$task_dir/source"
git -C "$task_dir/source" checkout --detach "$QWEN38_LLAMA_BASE_COMMIT"
git -C "$task_dir/source" apply "$project/patches/experimental-q4-mma-tile.patch"
nvcc -O3 -lineinfo --use_fast_math --extended-lambda -std=c++17 \
  -arch=sm_120a -DGGML_CUDA_USE_GRAPHS --cudart shared \
  -Xcompiler -fPIC,-fvisibility=hidden,-fvisibility-inlines-hidden -shared \
  -I"$task_dir/source/ggml/include" -I"$task_dir/source/ggml/src" \
  -I"$project/benchmarks" "$project/benchmarks/q4_mma_tile_probe.cu" \
  -o "$output/q4-mma-tile-probe.so"
{
  printf 'base_commit=%s\ncompile_only=true\n' "$QWEN38_LLAMA_BASE_COMMIT"
  nvcc --version
  sha256sum "$project/patches/experimental-q4-mma-tile.patch" \
    "$project/benchmarks/qwen-q4-tile.cuh" "$output/q4-mma-tile-probe.so"
} > "$output/BUILD_INFO.txt"
