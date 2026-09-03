#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$SCRIPT_DIR/portable-manifest.env"

case "$QWEN38_ROOT" in
  /workspace/qwen38) ;;
  *) echo "Refusing unexpected QWEN38_ROOT: $QWEN38_ROOT" >&2; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive
required_commands=(aria2c curl jq openssl python3 supervisord tailscaled zstd)
missing_commands=()
for required_command in "${required_commands[@]}"; do
  command -v "$required_command" >/dev/null 2>&1 || missing_commands+=("$required_command")
done
if (( ${#missing_commands[@]} > 0 )); then
  dpkg --force-confold --configure -a
  apt-get update
  apt-get -o Dpkg::Options::="--force-confold" install -y --no-install-recommends \
    aria2 build-essential ca-certificates cmake curl git jq libcurl4-openssl-dev \
    libssl-dev ninja-build openssl pkg-config python3 python3-pip \
    supervisor zstd
fi

if ! command -v tailscaled >/dev/null 2>&1; then
  curl -fsSL --retry 5 https://tailscale.com/install.sh -o /tmp/install-tailscale.sh
  bash /tmp/install-tailscale.sh
fi

mkdir -p "$QWEN38_ROOT/models" "$QWEN38_ROOT/slot-cache" "$QWEN38_ROOT/tailscale"

LLAMA_DIR="$QWEN38_ROOT/llama.cpp-kvpatch"
BUILD_NAME=build
BUILD_CACHE_NAME=$QWEN38_BUILD_CACHE_FILE
BUILD_PROFILE=portable-sm120a
BUILD_NATIVE=OFF
BUILD_DIR="$LLAMA_DIR/$BUILD_NAME"
BUILD_CACHE="$SCRIPT_DIR/$BUILD_CACHE_NAME"
BUILD_CACHE_SHA="$BUILD_CACHE.sha256"

PREBUILT_CACHE_DIR=${QWEN38_PREBUILT_CACHE_DIR:-/opt/abliteration-station/cache}
if [[ ! -s "$BUILD_CACHE" && -s "$PREBUILT_CACHE_DIR/runtime.tar.zst" ]]; then
  echo "$QWEN38_BUILD_CACHE_SHA256  $PREBUILT_CACHE_DIR/runtime.tar.zst" | sha256sum -c -
  cp "$PREBUILT_CACHE_DIR/runtime.tar.zst" "$BUILD_CACHE"
  printf '%s  %s\n' "$QWEN38_BUILD_CACHE_SHA256" "$BUILD_CACHE_NAME" >"$BUILD_CACHE_SHA"
fi

build_matches_source() {
  local binary=$1
  local binary_dir validation_output
  [[ -x "$binary" ]] || return 1
  [[ -r "$BUILD_DIR/.qwen38-build-profile" ]] || return 1
  [[ $(<"$BUILD_DIR/.qwen38-build-profile") == "$BUILD_PROFILE" ]] || return 1
  [[ -r "$BUILD_DIR/.qwen38-source-tree" ]] || return 1
  [[ $(<"$BUILD_DIR/.qwen38-source-tree") == "$QWEN38_LLAMA_EXPECTED_TREE" ]] || return 1
  binary_dir=$(dirname -- "$binary")
  if ! validation_output=$(LD_LIBRARY_PATH="$binary_dir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
      "$binary" --version 2>&1); then
    printf 'Cached runtime validation failed: %s\n' "$validation_output" >&2
    return 1
  fi
}

if [[ -s "$BUILD_CACHE" ]] &&
   ! echo "$QWEN38_BUILD_CACHE_SHA256  $BUILD_CACHE" | sha256sum -c - >/dev/null 2>&1; then
  echo "Removing a runtime artifact that does not match the current manifest." >&2
  rm -f -- "$BUILD_CACHE" "$BUILD_CACHE_SHA"
fi

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

if [[ -s "$BUILD_CACHE" ]]; then
  echo "$QWEN38_BUILD_CACHE_SHA256  $BUILD_CACHE" | sha256sum -c -
  printf '%s  %s\n' "$QWEN38_BUILD_CACHE_SHA256" "$BUILD_CACHE_NAME" >"$BUILD_CACHE_SHA"
fi

if [[ -s "$BUILD_CACHE" && -s "$BUILD_CACHE_SHA" && ! -x "$BUILD_DIR/bin/llama-server" ]]; then
  mkdir -p "$LLAMA_DIR"
  (cd "$SCRIPT_DIR" && sha256sum -c "$(basename -- "$BUILD_CACHE_SHA")")
  tar --zstd -xf "$BUILD_CACHE" -C "$LLAMA_DIR"
  printf '%s\n' "$BUILD_PROFILE" > "$BUILD_DIR/.qwen38-build-profile"
  printf '%s\n' "$QWEN38_LLAMA_EXPECTED_TREE" > "$BUILD_DIR/.qwen38-source-tree"
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
  if [[ -n "$QWEN38_DFLASH_COMMIT" && "$QWEN38_DFLASH_COMMIT" != "$QWEN38_LLAMA_BASE_COMMIT" ]]; then
    git -C "$LLAMA_DIR" fetch origin "$QWEN38_DFLASH_COMMIT"
    git -C "$LLAMA_DIR" \
      -c user.name=qwen38-bootstrap \
      -c user.email=qwen38-bootstrap@localhost \
      cherry-pick FETCH_HEAD
  fi
  echo "$QWEN38_RUNTIME_PATCH_SHA256  $SCRIPT_DIR/$QWEN38_RUNTIME_PATCH_FILE" | sha256sum -c -
  git -C "$LLAMA_DIR" apply "$SCRIPT_DIR/$QWEN38_RUNTIME_PATCH_FILE"
  git -C "$LLAMA_DIR" add tools/server/server-context.cpp
  CURRENT_TREE=$(git -C "$LLAMA_DIR" write-tree)
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
    -DLLAMA_BUILD_UI=OFF \
    -DLLAMA_USE_PREBUILT_UI=OFF \
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
  local expected_bytes=$4
  local partial="${destination}.part"
  local attempt pid size last_size=-1 stalled=0 complete_stable=0

  if [[ -f "$destination" ]] && echo "$expected_sha  $destination" | sha256sum -c - >/dev/null 2>&1; then
    return 0
  fi

  for attempt in 1 2 3 4 5; do
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
      "$url" &
    pid=$!
    last_size=-1
    stalled=0
    complete_stable=0
    while kill -0 "$pid" 2>/dev/null; do
      sleep 5
      size=$(stat -c %s "$partial" 2>/dev/null || echo 0)
      if [[ "$size" == "$last_size" ]]; then
        stalled=$((stalled + 5))
      else
        stalled=0
        last_size=$size
      fi
      if [[ "$size" == "$expected_bytes" ]]; then
        complete_stable=$((complete_stable + 5))
        if (( complete_stable >= 10 )) &&
           echo "$expected_sha  $partial" | sha256sum -c - >/dev/null 2>&1; then
          kill "$pid" 2>/dev/null || true
          wait "$pid" 2>/dev/null || true
          rm -f "${partial}.aria2"
          mv "$partial" "$destination"
          return 0
        fi
      else
        complete_stable=0
      fi
      if (( stalled >= 120 )); then
        echo "The download stopped making progress; retrying ($attempt/5)." >&2
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        break
      fi
    done
    wait "$pid" 2>/dev/null || true
    if [[ -f "$partial" ]] &&
       [[ $(stat -c %s "$partial") == "$expected_bytes" ]] &&
       echo "$expected_sha  $partial" | sha256sum -c - >/dev/null 2>&1; then
      rm -f "${partial}.aria2"
      mv "$partial" "$destination"
      return 0
    fi
  done
  echo "The verified download did not complete after five attempts." >&2
  return 1
}

download_hf_file() {
  local repo=$1
  local revision=$2
  local file=$3
  local expected_sha=$4
  local destination=$5
  local expected_bytes=$6
  local primary_url="https://huggingface.co/${repo}/resolve/${revision}/${file}?download=true"
  local download_url=$primary_url
  if ! curl -fsSIL --connect-timeout 5 --max-time 10 "$primary_url" >/dev/null 2>&1; then
    download_url="https://hf-mirror.com/${repo}/resolve/${revision}/${file}"
    echo "The Hugging Face route is unavailable. Using the checksum-verified mirror." >&2
  fi
  download_url_file \
    "$download_url" \
    "$expected_sha" "$destination" "$expected_bytes"
}

TARGET_PATH="$QWEN38_ROOT/models/$QWEN38_TARGET_FILE"
DRAFT_BF16_PATH="$QWEN38_ROOT/models/$QWEN38_DRAFT_BF16_FILE"
DRAFT_Q4_PATH="$QWEN38_ROOT/models/$QWEN38_DRAFT_Q4_FILE"
SELECTED_MODEL_FILE=$QWEN38_TARGET_FILE

embedded_model_dir="$PREBUILT_CACHE_DIR/models"
embedded_model_files=(
  "$QWEN38_TARGET_SHARD_1"
  "$QWEN38_TARGET_SHARD_2"
  "$QWEN38_TARGET_SHARD_3"
  "$QWEN38_TARGET_SHARD_4"
)
embedded_model_hashes=(
  "$QWEN38_TARGET_SHARD_1_SHA256"
  "$QWEN38_TARGET_SHARD_2_SHA256"
  "$QWEN38_TARGET_SHARD_3_SHA256"
  "$QWEN38_TARGET_SHARD_4_SHA256"
)
embedded_model_ready=1
for index in "${!embedded_model_files[@]}"; do
  source_path="$embedded_model_dir/${embedded_model_files[$index]}"
  [[ -s "$source_path" ]] || { embedded_model_ready=0; break; }
  if [[ "${QWEN38_TRUST_PINNED_IMAGE:-0}" != 1 ]]; then
    echo "${embedded_model_hashes[$index]}  $source_path" | sha256sum -c -
  fi
done
if [[ "$embedded_model_ready" == 1 ]]; then
  for filename in "${embedded_model_files[@]}"; do
    cp --reflink=auto "$embedded_model_dir/$filename" "$QWEN38_ROOT/models/$filename"
  done
  SELECTED_MODEL_FILE=$QWEN38_TARGET_SHARD_1
  echo "Using the checksum-verified embedded Qwen target shards."
fi

if [[ ! -s "$DRAFT_Q4_PATH" && -s "$PREBUILT_CACHE_DIR/$QWEN38_DRAFT_Q4_FILE" ]]; then
  if [[ "${QWEN38_TRUST_PINNED_IMAGE:-0}" != 1 ]]; then
    echo "$QWEN38_DRAFT_Q4_SHA256  $PREBUILT_CACHE_DIR/$QWEN38_DRAFT_Q4_FILE" | sha256sum -c -
  fi
  cp --reflink=auto "$PREBUILT_CACHE_DIR/$QWEN38_DRAFT_Q4_FILE" "$DRAFT_Q4_PATH"
fi

draft_artifact_pid=""
if [[ ! -f "$DRAFT_Q4_PATH" ]] ||
   ! echo "$QWEN38_DRAFT_Q4_SHA256  $DRAFT_Q4_PATH" | sha256sum -c - >/dev/null 2>&1; then
  download_url_file \
    "$QWEN38_ARTIFACT_BASE_URL/$QWEN38_DRAFT_Q4_FILE" \
    "$QWEN38_DRAFT_Q4_SHA256" "$DRAFT_Q4_PATH" "$QWEN38_DRAFT_Q4_BYTES" &
  draft_artifact_pid=$!
fi

if [[ "$embedded_model_ready" != 1 ]]; then
  download_hf_file \
    "$QWEN38_TARGET_REPO" "$QWEN38_TARGET_REVISION" "$QWEN38_TARGET_FILE" "$QWEN38_TARGET_SHA256" "$TARGET_PATH" "$QWEN38_TARGET_BYTES"
fi

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
    "$QWEN38_DRAFT_REPO" "$QWEN38_DRAFT_REVISION" "$QWEN38_DRAFT_BF16_FILE" "$QWEN38_DRAFT_BF16_SHA256" "$DRAFT_BF16_PATH" "$QWEN38_DRAFT_BF16_BYTES"
  "$BUILD_DIR/bin/llama-quantize" "$DRAFT_BF16_PATH" "$DRAFT_Q4_PATH" Q4_0 "$(nproc)"
  echo "$QWEN38_DRAFT_Q4_SHA256  $DRAFT_Q4_PATH" | sha256sum -c -
fi

for required in \
  "$SCRIPT_DIR/run-qwen38-cloud.sh" \
  "$SCRIPT_DIR/slot-cache-control.sh" \
  "$SCRIPT_DIR/run-tailscaled.sh" \
  "$SCRIPT_DIR/qwen38-cloud.conf" \
  "$SCRIPT_DIR/tailscaled-qwen.conf" \
  "$SCRIPT_DIR/runtime.env"; do
  [[ -s "$required" ]] || { echo "Missing deployment asset: $required" >&2; exit 1; }
done

install -d -m 0755 /opt/supervisor-scripts /var/log/portal
install -m 0755 "$SCRIPT_DIR/run-qwen38-cloud.sh" /opt/supervisor-scripts/run-qwen38-cloud.sh
install -m 0755 "$SCRIPT_DIR/slot-cache-control.sh" /usr/local/bin/qwen38-slot-cache
install -m 0755 "$SCRIPT_DIR/run-tailscaled.sh" /opt/supervisor-scripts/run-tailscaled.sh
install -m 0644 "$SCRIPT_DIR/qwen38-cloud.conf" /etc/supervisor/conf.d/qwen38-cloud.conf
install -m 0644 "$SCRIPT_DIR/tailscaled-qwen.conf" /etc/supervisor/conf.d/tailscaled-qwen.conf
install -m 0600 "$SCRIPT_DIR/runtime.env" "$QWEN38_ROOT/runtime.env"
sed -i "s/^QWEN38_BUILD_DIR=.*/QWEN38_BUILD_DIR=$BUILD_NAME/" "$QWEN38_ROOT/runtime.env"
sed -i "s/^QWEN38_MODEL_FILE=.*/QWEN38_MODEL_FILE=$SELECTED_MODEL_FILE/" "$QWEN38_ROOT/runtime.env"

if [[ ! -s "$QWEN38_ROOT/api_key" ]]; then
  umask 077
  openssl rand -hex 32 > "$QWEN38_ROOT/api_key"
fi

if ! supervisorctl pid >/dev/null 2>&1; then
  supervisord -c /etc/supervisor/supervisord.conf
  sleep 1
fi

supervisorctl reread
supervisorctl update
tailscale_start_pid=""
if [[ -s "$QWEN38_ROOT/tailscale/tailscaled.state" ]]; then
  supervisorctl start tailscaled-qwen >/tmp/qwen38-tailscale-start.log 2>&1 &
  tailscale_start_pid=$!
fi
supervisorctl restart qwen38-cloud
if [[ -n "$tailscale_start_pid" ]]; then
  wait "$tailscale_start_pid"
fi

for _ in $(seq 1 120); do
  if curl -fsS --max-time 2 \
    -H "Authorization: Bearer $(<"$QWEN38_ROOT/api_key")" \
    http://127.0.0.1:17070/health >/dev/null; then
    echo "Qwen3.8 service is healthy."
    supervisorctl status qwen38-cloud
    exit 0
  fi
  sleep 2
done

supervisorctl status qwen38-cloud || true
tail -n 100 /var/log/portal/qwen38-cloud.err.log >&2 || true
exit 1
