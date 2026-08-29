# Research source inventory

Claims in social posts are experiment inputs, not verified results. Preserve
the source URL and reproduce the result before changing production.

## Current model and LoopSpec

- [Unleashed, LoopSpec, BenchLoop, and BenchHub](https://x.com/outsource_/status/2093706271350231313)
  - Reports UD-Q3_K_XL at 13.2 GB, 250K retrieval, and a 64 to 229 TPS
    exact-copy LoopSpec result at 255K.
  - Proposes prompt/N-gram reuse, DFlash2 for novel output, an adaptive gate,
    quant quality tests, long retrieval, draft acceptance, tool correctness,
    and real agent measurements.
  - Status: model is our current target; LoopSpec and benchmark claims are not
    reproduced in this repository.

## Flash-Next

- [CPU MoE offload profile](https://x.com/analogalok/status/2092697021790708148)
  - Reported 250K Q4 profile with about 364 prompt TPS and 21 decode TPS on one
    RTX 4090 with 110 GB host RAM.
- [SSD expert streaming](https://x.com/EyalToledano/status/2093429897188299113)
  - Reported 37 GB resident memory and about 40 decode TPS on an M4 Max while
    streaming about 60% of experts.
  - Linked implementation: [oMLX pull request 3260](https://github.com/jundot/omlx/pull/3260).
- [Official Qwen3.8-Flash-Next repository](https://github.com/QwenLM/Qwen3.8-Flash-Next)
  - Primary architecture and model source.

## DFlash

- [DFlash2 model and documentation](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2)
- [NVIDIA Model Optimizer DFlash recipe](https://github.com/NVIDIA/Model-Optimizer/blob/main/examples/speculative_decoding/doc/dflash.md)

## Earlier user-supplied sources retained for future triage

These links influenced earlier model, quant, runtime, or provider discussion.
Their exact claims must be recovered and classified before the related
experiment runs:

- https://x.com/zhijianliu_/status/2089836737132650504
- https://x.com/RoundtableSpace/status/2089876248176759205
- https://x.com/0x0SojalSec/status/2090396448437547070
- https://x.com/0x0SojalSec/status/2090184191682199954
- https://x.com/analogalok/status/2090797011100717267
- https://x.com/0xkydo/status/2090894947335750142
- https://x.com/trevorwood222/status/2090778670088732933
- https://x.com/kimmonismus/status/2092593917543780735

## Internal historical evidence

The experiment backlog also uses prior measured evidence from the original
deployment: host CPU and PCIe comparisons, DFlash `n_max` sweeps, temperature
loop behavior, 120K replays, real Pi tool turns, cancellation, cold wake, and
idle stop. New experiments must copy the evidence into sanitized result files
instead of depending on old machine-specific notes.
