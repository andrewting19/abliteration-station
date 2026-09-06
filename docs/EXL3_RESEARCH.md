# EXL3 lead from Tono_Ken3

Reviewed 2026-09-06 UTC. Research only; no backend or model change deployed.

Source: https://x.com/Tono_Ken3/status/2096231786347118837
Attached table: https://pbs.twimg.com/media/HRdOci4aEAAdOtl.png?name=orig
Backend: https://github.com/turboderp-org/exllamav3

The post claims a Huihui Qwen3.8-27B EXL3 6.5-bpw version uses 24 GB versus
52 GB and retains 98%+ accuracy. That metric is not defined in the post.
The visible table uses 20 MMLU questions and eight agent checks per row.
Its seconds/correct column is NOT decode TPS. The table does not establish
quality parity on cybersecurity or sustained inference at 100K-262K context.
The wording mixes an unquantized winner with a quantized size claim; do not
assume every table row is the 6.5-bpw quant.

EXL3 is a different format and ExLlamaV3 is a different engine, not a GGUF flag.
The official README lists speculative decoding, 2-8 bit cache quantization,
and an OpenAI-compatible service through TabbyAPI. Version 1.4.7 release notes
include a recurrent-slot leak fix. These features justify an evaluation, not
a speed or correctness claim for our exact target/draft pair.

For a controlled evaluation:

1. Start from the same full-precision Unleashed checkpoint when possible.
   Do not attribute a simultaneous switch to Huihui to an engine improvement.
2. Compare at a similar memory budget first. The cited 24-GB weight footprint
   is larger than our 13.223-GB GGUF and leaves less room on a 32-GB 5090 for
   the draft, cache, and runtime buffers. Full 262144 capacity must be tested.
3. Verify exact model architecture, native medium thinking, tool parsing,
   DFlash2 compatibility, cancellation, and checkpoint persistence separately.
4. Replay copied real 100K-201K Pi requests; measure actual emitted tokens,
   completed tool calls, cold/warm TTFT, GPU memory, and quality. Do not use
   requested token counts or this tweet's seconds/correct as decode throughput.
5. Treat Huihui as a separate quality comparison after the engine comparison.

No EXL3 conversion or GPU experiment was started from this post. Keep the
current lifecycle test and the user's additional $5 spending limit intact.
