# Sampler timing probe

Use only on an isolated Linux worker. The probe calls the original exported
`llama_sampler_apply` function exactly once and accumulates elapsed time for
grammar and chain samplers. It does not read or change candidate data.

Build on a compatible Linux controller:

```sh
g++ -O2 -std=c++17 -shared -fPIC benchmarks/sampler_profile.cpp -ldl -o sampler_profile.so
```

Copy the library to the isolated worker. Stop its normal model service before
starting the diagnostic process. Set `QWEN38_SAMPLER_PROFILE_LIBRARY` to the
absolute library path when running the normal launcher. The launcher applies
`LD_PRELOAD` only to the inference server, not to shell utilities.

Run one verified historical request with unchanged settings. End the server
gracefully after the response completes. Read the `QWEN_SAMPLER_PROFILE` record
from stderr. The record contains call counts and elapsed milliseconds, not
prompt or response text. A forced kill can lose this final record.

Interpretation:

- Grammar time includes active validation and cheap inactive-lazy checks.
- Chain time includes the work of nested sampler components. Do not add
  nested measurements as if they were independent time intervals.
- The measurements do not cover tokenization, model GPU execution, or all
  server bookkeeping. Low measured time rejects the hypothesis that this
  part explains most of the missing throughput.
- Check that output hashes, token counts, and tool-call completion agree with
  the uninstrumented control. Report profiling overhead separately.
- Do not use an instrumented throughput result to promote a runtime.

`tests/test_sampler_profile.py` runs a Linux interposition test. It verifies
call preservation, null-sampler forwarding, category counts, and timing output.
The test does not establish correctness or performance on a real GPU workload.
