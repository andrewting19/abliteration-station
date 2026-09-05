#!/usr/bin/env bash
# CPU build only, inside the pinned CUDA development container.
set -euo pipefail
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
source "$project/scripts/vast/portable-manifest.env"
command -v nvcc >/dev/null
source_dir=$(mktemp -d /tmp/qwen-iq-mmq.XXXXXX)
output="$project/dist/iq-mmq-candidate"
[[ ! -e "$output" ]] || { echo "Candidate output already exists." >&2; exit 1; }
install -d -m 0755 "$output/baseline" "$output/candidate" "$output/test-bin"
git clone --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp.git "$source_dir/source"
git -C "$source_dir/source" checkout --detach "$QWEN38_LLAMA_BASE_COMMIT"
echo "$QWEN38_RUNTIME_PATCH_SHA256  $project/patches/llama-slot-checkpoints.patch" | sha256sum -c -
git -C "$source_dir/source" apply "$project/patches/llama-slot-checkpoints.patch"
git -C "$source_dir/source" add tools/server/server-context.cpp
[[ "$(git -C "$source_dir/source" write-tree)" == "$QWEN38_LLAMA_EXPECTED_TREE" ]]
git -C "$source_dir/source" apply "$project/patches/experimental-iq-index-shifts.patch"
git -C "$source_dir/source" add ggml/src/ggml-cuda/vecdotq.cuh ggml/src/ggml-cuda/mmq-load-tiles.cuh
fixed_baseline_tree=$(git -C "$source_dir/source" write-tree)
build="$source_dir/build"
# Resolve the driver SONAME at link time on a runner without a GPU driver.
# This directory is not packaged or placed on the runtime library path.
driver_stubs="$source_dir/driver-link-stubs"
install -d "$driver_stubs"
test -f /usr/local/cuda/lib64/stubs/libcuda.so
ln -s /usr/local/cuda/lib64/stubs/libcuda.so "$driver_stubs/libcuda.so.1"
cmake -S "$source_dir/source" -B "$build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=120a \
  -DCMAKE_EXE_LINKER_FLAGS="-Wl,-rpath-link,$driver_stubs" \
  -DGGML_CUDA=ON -DGGML_CUDA_FA=ON -DGGML_CUDA_GRAPHS=ON \
  -DGGML_NATIVE=OFF -DBUILD_SHARED_LIBS=ON \
  -DLLAMA_BUILD_COMMON=ON -DLLAMA_BUILD_TESTS=ON \
  -DLLAMA_BUILD_TOOLS=OFF -DLLAMA_BUILD_EXAMPLES=OFF
cmake --build "$build" --target ggml-cuda test-backend-ops -j 2
cp -a "$build/bin/"libggml-cuda.so* "$output/baseline/"
cp -a "$build/bin/"*.so* "$output/test-bin/"
cp -a "$build/bin/test-backend-ops" "$output/test-bin/"
git -C "$source_dir/source" apply "$project/patches/experimental-iq-mmq.patch"
git -C "$source_dir/source" add ggml/src/ggml-cuda/mmvq.cu
candidate_tree=$(git -C "$source_dir/source" write-tree)
cmake --build "$build" --target ggml-cuda -j 2
cp -a "$build/bin/"libggml-cuda.so* "$output/candidate/"
cp "$source_dir/source/LICENSE" "$output/llama-LICENSE"
{
  printf 'base_commit=%s\nbaseline_tree=%s\ncandidate_tree=%s\n' \
    "$QWEN38_LLAMA_BASE_COMMIT" "$fixed_baseline_tree" "$candidate_tree"
  printf 'original_tree=%s\n' "$QWEN38_LLAMA_EXPECTED_TREE"
  printf 'architecture=120a\nparallel_compile_jobs=2\n'
  sha256sum "$project/patches/experimental-iq-mmq.patch"
  sha256sum "$project/patches/experimental-iq-index-shifts.patch"
  nvcc --version
} > "$output/BUILD_INFO.txt"
(cd "$output" && sha256sum baseline/libggml-cuda.so.* candidate/libggml-cuda.so.* > SHA256SUMS)
echo "CUDA candidate built. GPU correctness and real-request gates remain required."
