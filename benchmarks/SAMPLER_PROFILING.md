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
- CPU-time fields use the calling thread's CPU clock. Compare them with
  elapsed time to distinguish CPU work from waits or descheduling.
- Full-sampler fields intercept `common_sampler_sample` and subtract its
  `llama_synchronize` calls. Grammar and chain measurements are subsets of
  this total, not additional time. Other server and model work is not covered.
- The measurements do not cover tokenization, model GPU execution, or all
  server bookkeeping. Low measured time rejects the hypothesis that this
  part explains most of the missing throughput.
- Check that output hashes, token counts, and tool-call completion agree with
  the uninstrumented control. Report profiling overhead separately.
- Do not use an instrumented throughput result to promote a runtime.

`tests/test_sampler_profile.py` runs a Linux interposition test. It verifies
call preservation, null-sampler forwarding, category counts, and timing output.
The test does not establish correctness or performance on a real GPU workload.

The C++ symbol signature is tied to the inspected engine revision. Verify the
exported symbols and the forwarding test before using the probe with a different
runtime. It fails closed if an original function cannot be resolved.

## Decode and state-copy probe

Compile `decode_profile.cpp` with the sampler probe and headers from the exact
deployed revision. It forwards batch structs and state-buffer arguments without
reading or changing their contents. The Linux test needs `LLAMA_PROFILE_INCLUDE`
set to a directory containing those engine and GGML headers.

Reports separate target and draft calls, small batches by token count, and large
batches above eight tokens. Large batches include prefill. Small batches are
not automatically proof of verification or replay; compare with server counters
and call sites. State byte counts are serialized bytes returned by the API, not
a direct PCIe traffic measurement. Timings are inclusive API intervals.

Set `QWEN38_REQUIRE_DECODE_PROFILE=1` for this probe. The runner then requires
target, draft, and sampler records from the actual profiling process ID.

Synchronization records measure waits for work submitted before the call.
CUDA stream waits can busy-spin: high calling-thread CPU time does not prove
CPU arithmetic is the bottleneck. Decode call-return time is not completed GPU
time. Readback intervals can include synchronization. Do not add nested API
intervals or include prefill records in generation totals.
