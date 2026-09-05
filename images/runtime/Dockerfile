FROM ubuntu:24.04 AS model-sharder

ARG LLAMA_COMMIT=7339054744f109c4cd89b75689dbb8a2c154d60e
ARG TARGET_URL=https://huggingface.co/outsourc-e/Qwen3.8-27B-Unleashed-GGUF/resolve/67a999218fd7002f11bf82bc81d6289beea60841/Qwen3.8-27B-Unleashed-UD-Q3_K_XL.gguf?download=true
ARG TARGET_SHA256=b4c9721ab6ed1b7d1d1863b8f43e2fbce6a88dab39ea4333d2e74a7ad69580fe
ARG DRAFT_URL=https://github.com/andrewting19/abliteration-station/releases/download/bootstrap-artifacts-v1/Qwen3.8-27B-DFlash2-Q4_0.gguf
ARG DRAFT_SHA256=3db1e714ed60a0765f117353f4747f9c83d0f2b74da6c1049e0890af22ad6e3a

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      aria2 ca-certificates cmake g++ git make \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp.git /src \
    && git -C /src checkout "$LLAMA_COMMIT" \
    && cmake -S /src -B /src/build \
      -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_SERVER=OFF \
      -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
    && cmake --build /src/build --target llama-gguf-split -j 4

RUN install -d -m 0755 /model \
    && aria2c --allow-overwrite=true --auto-file-renaming=false \
      --file-allocation=none --max-connection-per-server=16 \
      --min-split-size=8M --split=16 --dir /tmp --out target.gguf "$TARGET_URL" \
    && echo "$TARGET_SHA256  /tmp/target.gguf" | sha256sum -c - \
    && /src/build/bin/llama-gguf-split --split-max-size 4G \
      /tmp/target.gguf /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL \
    && rm -f /tmp/target.gguf \
    && aria2c --allow-overwrite=true --auto-file-renaming=false \
      --file-allocation=none --max-connection-per-server=8 \
      --min-split-size=8M --split=8 --dir /model \
      --out Qwen3.8-27B-DFlash2-Q4_0.gguf "$DRAFT_URL" \
    && echo "$DRAFT_SHA256  /model/Qwen3.8-27B-DFlash2-Q4_0.gguf" | sha256sum -c - \
    && echo '47168c5c8c810f9d090aec8ece58fe4e131bf760efdac6092136fb2cd966a5c3  /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL-00001-of-00004.gguf' | sha256sum -c - \
    && echo '509386c0207602f5ece755ac58dd08f92ab0ebab4346141567654a1875bbb9ca  /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL-00002-of-00004.gguf' | sha256sum -c - \
    && echo 'e7f43aa1a076e7a82c2d6fbe7853d2fdbf33d31804997e3a5faf9865dc5e48ee  /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL-00003-of-00004.gguf' | sha256sum -c - \
    && echo 'df6747171bd6bcdd4446af80a258fcd3bd23c02e4ca445ff4ac6ab71e9ad9f17  /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL-00004-of-00004.gguf' | sha256sum -c -

FROM nvidia/cuda:13.2.0-runtime-ubuntu24.04@sha256:3b8afffc99c6ca801e6bf31a426400432cc8ba9dea77bd27ccf8cd67f06424eb AS cuda-runtime

FROM nvidia/cuda:13.2.0-base-ubuntu24.04@sha256:b66239c62d5aa5481cb8151c7ff410e0d8d3d4a75cb4c90e66e89639ded490f4

ARG RUNTIME_URL=https://github.com/andrewting19/abliteration-station/releases/download/bootstrap-artifacts-v1/llama-build-cuda13-sm120a-dflash-fused-kvpatch.tar.zst
ARG RUNTIME_SHA256=a306552e059c812dc9a0991b19be400e98b6f7c6174a8ad5921a91a837247955

ENV DEBIAN_FRONTEND=noninteractive

COPY --from=cuda-runtime /usr/local/cuda-13.2/targets/x86_64-linux/lib/libcublas.so.13.3.0.5 /usr/local/cuda-13.2/targets/x86_64-linux/lib/
COPY --from=cuda-runtime /usr/local/cuda-13.2/targets/x86_64-linux/lib/libcublasLt.so.13.3.0.5 /usr/local/cuda-13.2/targets/x86_64-linux/lib/
RUN cd /usr/local/cuda-13.2/targets/x86_64-linux/lib \
    && ln -sf libcublas.so.13.3.0.5 libcublas.so.13 \
    && ln -sf libcublasLt.so.13.3.0.5 libcublasLt.so.13 \
    && ldconfig

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      aria2 ca-certificates curl jq libgomp1 openssh-server openssl python3 supervisor zstd \
    && curl -fsSL https://tailscale.com/install.sh -o /tmp/install-tailscale.sh \
    && bash /tmp/install-tailscale.sh \
    && rm -rf /var/lib/apt/lists/* /tmp/install-tailscale.sh \
    && install -d -m 0755 /run/sshd /opt/abliteration-station/cache /workspace/qwen38/models \
    && rm -f /etc/ssh/ssh_host_rsa_key /etc/ssh/ssh_host_rsa_key.pub \
      /etc/ssh/ssh_host_ecdsa_key /etc/ssh/ssh_host_ecdsa_key.pub \
      /etc/ssh/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key.pub

RUN aria2c --allow-overwrite=true --auto-file-renaming=false --file-allocation=none \
      --max-connection-per-server=8 --min-split-size=8M --split=8 \
      --dir /opt/abliteration-station/cache --out runtime.tar.zst "$RUNTIME_URL" \
    && echo "$RUNTIME_SHA256  /opt/abliteration-station/cache/runtime.tar.zst" | sha256sum -c - \
    && printf '%s  %s\n' "$RUNTIME_SHA256" runtime.tar.zst \
      > /opt/abliteration-station/cache/runtime.tar.zst.sha256

RUN install -d -m 0755 /opt/abliteration-station/cache/models
COPY --from=model-sharder /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL-00001-of-00004.gguf /opt/abliteration-station/cache/models/
COPY --from=model-sharder /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL-00002-of-00004.gguf /opt/abliteration-station/cache/models/
COPY --from=model-sharder /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL-00003-of-00004.gguf /opt/abliteration-station/cache/models/
COPY --from=model-sharder /model/Qwen3.8-27B-Unleashed-UD-Q3_K_XL-00004-of-00004.gguf /opt/abliteration-station/cache/models/
COPY --from=model-sharder /model/Qwen3.8-27B-DFlash2-Q4_0.gguf /opt/abliteration-station/cache/

COPY scripts/vast/container-entrypoint.sh /usr/local/bin/abliteration-station-container-entrypoint
RUN chmod 0755 /usr/local/bin/abliteration-station-container-entrypoint

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/abliteration-station-container-entrypoint"]
