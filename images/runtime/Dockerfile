FROM nvidia/cuda:13.2.0-runtime-ubuntu24.04@sha256:3b8afffc99c6ca801e6bf31a426400432cc8ba9dea77bd27ccf8cd67f06424eb AS cuda-runtime

FROM nvidia/cuda:13.2.0-base-ubuntu24.04@sha256:b66239c62d5aa5481cb8151c7ff410e0d8d3d4a75cb4c90e66e89639ded490f4

ARG RUNTIME_URL=https://github.com/andrewting19/abliteration-station/releases/download/bootstrap-artifacts-v1/llama-build-cuda13-sm120a-dflash-fused-kvpatch.tar.zst
ARG RUNTIME_SHA256=a306552e059c812dc9a0991b19be400e98b6f7c6174a8ad5921a91a837247955

ENV DEBIAN_FRONTEND=noninteractive

COPY --from=cuda-runtime /usr/local/cuda-13.2/targets/x86_64-linux/lib/libcublas.so.13.3.0.5 /usr/local/cuda-13.2/targets/x86_64-linux/lib/
COPY --from=cuda-runtime /usr/local/cuda-13.2/targets/x86_64-linux/lib/libcublasLt.so.13.3.0.5 /usr/local/cuda-13.2/targets/x86_64-linux/lib/
COPY --from=cuda-runtime /usr/local/cuda-13.2/targets/x86_64-linux/lib/libcudart.so.13.2.51 /usr/local/cuda-13.2/targets/x86_64-linux/lib/

RUN cd /usr/local/cuda-13.2/targets/x86_64-linux/lib \
    && ln -s libcublas.so.13.3.0.5 libcublas.so.13 \
    && ln -s libcublasLt.so.13.3.0.5 libcublasLt.so.13 \
    && ln -s libcudart.so.13.2.51 libcudart.so.13 \
    && ldconfig

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      aria2 ca-certificates curl jq openssh-server openssl python3 supervisor zstd \
    && curl -fsSL https://tailscale.com/install.sh -o /tmp/install-tailscale.sh \
    && bash /tmp/install-tailscale.sh \
    && rm -rf /var/lib/apt/lists/* /tmp/install-tailscale.sh \
    && install -d -m 0755 /run/sshd /opt/abliteration-station/cache /workspace/qwen38/models \
    && ssh-keygen -A

RUN aria2c --allow-overwrite=true --auto-file-renaming=false --file-allocation=none \
      --max-connection-per-server=8 --min-split-size=8M --split=8 \
      --dir /opt/abliteration-station/cache --out runtime.tar.zst "$RUNTIME_URL" \
    && echo "$RUNTIME_SHA256  /opt/abliteration-station/cache/runtime.tar.zst" | sha256sum -c - \
    && printf '%s  %s\n' "$RUNTIME_SHA256" runtime.tar.zst \
      > /opt/abliteration-station/cache/runtime.tar.zst.sha256

COPY images/runtime/entrypoint.sh /usr/local/bin/abliteration-station-container-entrypoint
RUN chmod 0755 /usr/local/bin/abliteration-station-container-entrypoint

EXPOSE 22
ENTRYPOINT ["/usr/local/bin/abliteration-station-container-entrypoint"]
