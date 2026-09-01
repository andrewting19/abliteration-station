#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/portable-manifest.env"

case "$QWEN38_ROOT" in
  /workspace/qwen38) ;;
  *) echo "Refusing unexpected QWEN38_ROOT: $QWEN38_ROOT" >&2; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive
dpkg --force-confold --configure -a
apt-get update
apt-get -o Dpkg::Options::="--force-confold" install -y --no-install-recommends \
  aria2 build-essential ca-certificates cmake curl git jq libcurl4-openssl-dev \
  libssl-dev ninja-build openssl pkg-config python3 python3-pip \
  supervisor zstd

if ! command -v tailscaled >/dev/null 2>&1; then
  curl -fsSL --retry 5 https://tailscale.com/install.sh -o /tmp/install-tailscale.sh
  bash /tmp/install-tailscale.sh
fi

mkdir -p "$QWEN38_ROOT/models" "$QWEN38_ROOT/slot-cache" "$QWEN38_ROOT/tailscale"

LLAMA_DIR="$QWEN38_ROOT/llama.cpp-master-dflash"
BUILD_NAME=build-cuda13-master
BUILD_CACHE_NAME=$QWEN38_BUILD_CACHE_FILE
BUILD_PROFILE=portable-sm120a
BUILD_NATIVE=OFF
BUILD_DIR="$LLAMA_DIR/$BUILD_NAME"
BUILD_CACHE="$SCRIPT_DIR/$BUILD_CACHE_NAME"
BUILD_CACHE_SHA="$BUILD_CACHE.sha256"

build_matches_source() {
  local binary=$1
  [[ -x "$binary" ]] || return 1
  [[ -r "$BUILD_DIR/.qwen38-build-profile" ]] || return 1
  [[ $(<"$BUILD_DIR/.qwen38-build-profile") == "$BUILD_PROFILE" ]] || return 1
  [[ -r "$BUILD_DIR/.qwen38-source-tree" ]] || return 1
  [[ $(<"$BUILD_DIR/.qwen38-source-tree") == "$QWEN38_LLAMA_EXPECTED_TREE" ]] || return 1
  "$binary" --version >/dev/null 2>&1
}

if [[ ${CUDA_VERSION:-} == 13.2* && ! -s "$BUILD_CACHE" ]]; then
  if aria2c \
    --allow-overwrite=true \
    --auto-file-renaming=false \
    --console-log-level=warn \
    --file-allocation=none \
    --max-connection-per-server=8 \
    --min-split-size=8M \
    --split=8 \
    --dir "$SCRIPT_DIR" \
    --out "$BUILD_CACHE_NAME" \
    "$QWEN38_ARTIFACT_BASE_URL/$BUILD_CACHE_NAME" &&
     echo "$QWEN38_BUILD_CACHE_SHA256  $BUILD_CACHE" | sha256sum -c -; then
    printf '%s  %s\n' "$QWEN38_BUILD_CACHE_SHA256" "$BUILD_CACHE_NAME" >"$BUILD_CACHE_SHA"
  else
    echo "The portable runtime download failed. Building from the pinned source." >&2
    rm -f "$BUILD_CACHE" "$BUILD_CACHE_SHA"
  fi
fi

if [[ -s "$BUILD_CACHE" && -s "$BUILD_CACHE_SHA" && ! -x "$BUILD_DIR/bin/llama-server" ]]; then
  mkdir -p "$LLAMA_DIR"
  (cd "$SCRIPT_DIR" && sha256sum -c "$(basename -- "$BUILD_CACHE_SHA")")
  tar --zstd -xf "$BUILD_CACHE" -C "$LLAMA_DIR"
fi

if [[ -x "$BUILD_DIR/bin/llama-server" ]] && ! build_matches_source "$BUILD_DIR/bin/llama-server"; then
  rejected_dir="${BUILD_DIR}.rejected-$(date -u +%Y%m%dT%H%M%SZ)"
  echo "Rejecting a build cache that does not match the verified source: $rejected_dir" >&2
  mv "$BUILD_DIR" "$rejected_dir"
fi

if build_matches_source "$BUILD_DIR/bin/llama-server" &&
   [[ -x "$BUILD_DIR/bin/llama-quantize" ]]; then
  echo "Using the verified cached RTX 5090 build."
else
  if [[ -e "$LLAMA_DIR" ]]; then
    rejected_source="${LLAMA_DIR}.rejected-$(date -u +%Y%m%dT%H%M%SZ)"
    mv "$LLAMA_DIR" "$rejected_source"
  fi
  git clone --filter=blob:none --no-checkout \
    https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR"
  git -C "$LLAMA_DIR" checkout --detach "$QWEN38_LLAMA_BASE_COMMIT"
  git -C "$LLAMA_DIR" fetch origin "$QWEN38_DFLASH_COMMIT"
  git -C "$LLAMA_DIR" \
    -c user.name=qwen38-bootstrap \
    -c user.email=qwen38-bootstrap@localhost \
    cherry-pick FETCH_HEAD
  CURRENT_TREE=$(git -C "$LLAMA_DIR" rev-parse 'HEAD^{tree}')
  if [[ "$CURRENT_TREE" != "$QWEN38_LLAMA_EXPECTED_TREE" ]]; then
    echo "Unexpected llama.cpp tree after build preparation: $CURRENT_TREE" >&2
    exit 1
  fi
  cmake -S "$LLAMA_DIR" -B "$BUILD_DIR" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_ARCHITECTURES=120a \
    -DGGML_CUDA=ON \
    -DGGML_CUDA_FA=ON \
    -DGGML_CUDA_GRAPHS=ON \
    -DGGML_NATIVE="$BUILD_NATIVE" \
    -DLLAMA_BUILD_SERVER=ON
  cmake --build "$BUILD_DIR" --target llama-server llama-quantize -j "$(nproc)"
  printf '%s\n' "$BUILD_PROFILE" > "$BUILD_DIR/.qwen38-build-profile"
  printf '%s\n' "$QWEN38_LLAMA_EXPECTED_TREE" > "$BUILD_DIR/.qwen38-source-tree"
fi

build_matches_source "$BUILD_DIR/bin/llama-server" || {
  echo "The built server revision does not match the verified source." >&2
  exit 1
}

download_url_file() {
  local url=$1
  local expected_sha=$2
  local destination=$3
  local partial="${destination}.part"

  if [[ -f "$destination" ]] && echo "$expected_sha  $destination" | sha256sum -c - >/dev/null 2>&1; then
    return 0
  fi

  aria2c \
    --allow-overwrite=true \
    --auto-file-renaming=false \
    --console-log-level=warn \
    --continue=true \
    --file-allocation=none \
    --max-connection-per-server=16 \
    --min-split-size=16M \
    --split=16 \
    --summary-interval=10 \
    --dir "$(dirname -- "$partial")" \
    --out "$(basename -- "$partial")" \
    "$url"
  echo "$expected_sha  $partial" | sha256sum -c -
  mv "$partial" "$destination"
}

download_hf_file() {
  local repo=$1
  local revision=$2
  local file=$3
  local expected_sha=$4
  local destination=$5
  download_url_file \
    "https://huggingface.co/${repo}/resolve/${revision}/${file}?download=true" \
    "$expected_sha" "$destination"
}

TARGET_PATH="$QWEN38_ROOT/models/$QWEN38_TARGET_FILE"
DRAFT_BF16_PATH="$QWEN38_ROOT/models/$QWEN38_DRAFT_BF16_FILE"
DRAFT_Q4_PATH="$QWEN38_ROOT/models/$QWEN38_DRAFT_Q4_FILE"

draft_artifact_pid=""
if [[ ! -f "$DRAFT_Q4_PATH" ]] ||
   ! echo "$QWEN38_DRAFT_Q4_SHA256  $DRAFT_Q4_PATH" | sha256sum -c - >/dev/null 2>&1; then
  download_url_file \
    "$QWEN38_ARTIFACT_BASE_URL/$QWEN38_DRAFT_Q4_FILE" \
    "$QWEN38_DRAFT_Q4_SHA256" "$DRAFT_Q4_PATH" &
  draft_artifact_pid=$!
fi

download_hf_file \
  "$QWEN38_TARGET_REPO" "$QWEN38_TARGET_REVISION" "$QWEN38_TARGET_FILE" "$QWEN38_TARGET_SHA256" "$TARGET_PATH"

if [[ -n "$draft_artifact_pid" ]]; then
  if ! wait "$draft_artifact_pid"; then
    echo "The portable Q4 draft download failed. Using the BF16 fallback." >&2
    rm -f "${DRAFT_Q4_PATH}.part" "$DRAFT_Q4_PATH"
  fi
fi

if [[ -f "$DRAFT_Q4_PATH" ]] &&
   echo "$QWEN38_DRAFT_Q4_SHA256  $DRAFT_Q4_PATH" | sha256sum -c - >/dev/null 2>&1; then
  echo "Using the verified copied Q4_0 draft model."
else
  download_hf_file \
    "$QWEN38_DRAFT_REPO" "$QWEN38_DRAFT_REVISION" "$QWEN38_DRAFT_BF16_FILE" "$QWEN38_DRAFT_BF16_SHA256" "$DRAFT_BF16_PATH"
  "$BUILD_DIR/bin/llama-quantize" "$DRAFT_BF16_PATH" "$DRAFT_Q4_PATH" Q4_0 "$(nproc)"
  echo "$QWEN38_DRAFT_Q4_SHA256  $DRAFT_Q4_PATH" | sha256sum -c -
fi

for required in \
  "$SCRIPT_DIR/run-qwen38-cloud.sh" \
  "$SCRIPT_DIR/run-tailscaled.sh" \
  "$SCRIPT_DIR/qwen38-cloud.conf" \
  "$SCRIPT_DIR/tailscaled-qwen.conf" \
  "$SCRIPT_DIR/runtime.env"; do
  [[ -s "$required" ]] || { echo "Missing deployment asset: $required" >&2; exit 1; }
done

install -d -m 0755 /opt/supervisor-scripts /var/log/portal
install -m 0755 "$SCRIPT_DIR/run-qwen38-cloud.sh" /opt/supervisor-scripts/run-qwen38-cloud.sh
install -m 0755 "$SCRIPT_DIR/run-tailscaled.sh" /opt/supervisor-scripts/run-tailscaled.sh
install -m 0644 "$SCRIPT_DIR/qwen38-cloud.conf" /etc/supervisor/conf.d/qwen38-cloud.conf
install -m 0644 "$SCRIPT_DIR/tailscaled-qwen.conf" /etc/supervisor/conf.d/tailscaled-qwen.conf
install -m 0600 "$SCRIPT_DIR/runtime.env" "$QWEN38_ROOT/runtime.env"
sed -i "s/^QWEN38_BUILD_DIR=.*/QWEN38_BUILD_DIR=$BUILD_NAME/" "$QWEN38_ROOT/runtime.env"

if [[ ! -s "$QWEN38_ROOT/api_key" ]]; then
  umask 077
  openssl rand -hex 32 > "$QWEN38_ROOT/api_key"
fi

if ! supervisorctl status >/dev/null 2>&1; then
  supervisord -c /etc/supervisor/supervisord.conf
  sleep 1
fi

supervisorctl reread
supervisorctl update
supervisorctl restart tailscaled-qwen || true
supervisorctl restart qwen38-cloud

for _ in $(seq 1 120); do
  if curl -fsS --max-time 2 \
    -H "Authorization: Bearer $(<"$QWEN38_ROOT/api_key")" \
    http://127.0.0.1:17070/health >/dev/null; then
    echo "Qwen3.8 service is healthy."
    supervisorctl status qwen38-cloud tailscaled-qwen
    exit 0
  fi
  sleep 2
done

supervisorctl status qwen38-cloud tailscaled-qwen || true
tail -n 100 /var/log/portal/qwen38-cloud.err.log >&2 || true
exit 1
