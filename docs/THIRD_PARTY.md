# Third-party components

This project does not redistribute model weights or llama.cpp binaries.

At deployment time it downloads these components from their source projects:

- `outsourc-e/Qwen3.8-27B-Unleashed-GGUF`
- `incoai/Qwen3.8-27B-DFlash2-GGUF`
- `ggml-org/llama.cpp`, with a pinned DFlash change
- Tailscale on the rented host
- Vast.ai CLI in a local virtual environment

The two model repositories declare Apache-2.0 licenses. llama.cpp uses the MIT
license. Tailscale and the Vast.ai CLI have their own licenses and terms. Check
the current upstream license and model terms before commercial use. The pinned
repository, file names, commits, trees, and SHA-256 values are in
`scripts/vast/portable-manifest.env`.
