# Future experiment backlog

These experiments are ideas, not accepted results. Do not run paid experiments
without a manifest, baseline, price cap, and cleanup rule.

## Priority 0: establish the honest baseline

### E000 - Sanitized real Pi corpus

Create private captures for complete Pi turns at 32K, 64K, 100K, 130K, 200K,
and 245K. Include tool calls, tool results, novel output, and repeated code.
Store hashes and metadata in reports. Never commit the request bodies.

### E001 - Baseline variance

Run five samples of each workload on the current host. Measure prompt TPS,
token-weighted decode TPS, time to first token, total turn time, DFlash
acceptance, and task success. This establishes the noise floor.

### E002 - Full cost ledger

Measure wake, setup, active inference, idle, stopped storage, failed rental,
and interruption cost. Report dollars per successful Pi turn and per work hour.

## Priority 1: likely large cost or speed wins

### E100 - High-quality Vast bid hosts

Compare on-demand with interruptible bid hosts. Test the literal $0.20 range and
the likely value range near $0.30 to $0.34. Prefer modern CPUs and PCIe above
45 GB/s. Measure interruption rate and long-context recovery cost. Keep
on-demand fallback. Do not promote a host below the quality and 80 TPS gates.

The intended future product mode is `economy`:

1. Select a high-PCIe bid host with a total price cap near $0.34/hour.
2. Prefer the $0.30 to $0.34 value range over an unqualified $0.20 host.
3. Run the fixed 120K workload and require at least 80 token-weighted decode
   TPS plus all normal quality gates.
4. If no bid host passes, start a qualified on-demand host automatically.
5. Detect a provider interruption separately from a model, network, or Pi
   error and show the state clearly in the Pi TUI.
6. Preserve the Pi session locally, restart or replace the instance, restore
   the private route, and retry only when the request is safe to repeat.
7. Bound retry count, elapsed time, and total rental cost. Never create two
   paid instances for one recovery.
8. Prefer economy mode for short or recoverable work. Allow users to select
   reliable on-demand mode before important continuous 100K-plus sessions.
9. Measure the cost of lost prefill, lost decode, and repeated tool work after
   every interruption. Include those losses in dollars per successful turn.

Promotion requires a complete interrupted-turn test at more than 100K context,
not only a successful uninterrupted benchmark.

### E101 - Host value frontier

Sweep RTX 4090 and RTX 5090 offers across CPU generation, PCIe bandwidth, RAM,
disk, location, and price. The new source claims about 100 TPS on one 4090 for
the same Q3 model. Verify it on our full Pi workload. Select by successful-turn
cost, not GPU name or DLPerf.

### E102 - LoopSpec-style adaptive reuse

Reproduce prompt and N-gram reuse for repeated code, DFlash2 for novel output,
and an adaptive verification gate. Measure exact-copy and novel-agentic classes
separately. The source reports 64 to 229 TPS on exact-copy work at 255K. Require
target verification for every accepted token and no quality regression.

### E103 - Prefix and session cache reuse

Measure stable Pi prefixes, incremental tool results, slot checkpoints, prompt
cache persistence after idle stop, and cache restore after host restart. Record
cache hit rate, bytes restored, saved prefill time, and stale-cache failures.

### E104 - Adaptive idle policy

Compare fixed 10-minute idle stop with a policy based on recent turn frequency,
session context size, expected prefill cost, and bid/on-demand rate. Optimize
expected dollars plus waiting time. Keep a hard maximum idle cost.

### E105 - Lazy Pi prompt and tool loading

Measure the token and prefill cost of system prompts, extension instructions,
tool schemas, and project files. Load rarely used tools only when required.
Quality-gate tool discovery and first-use correctness.

## Priority 2: inference-engine work

### E200 - DFlash acceptance instrumentation

Expose drafted tokens, accepted tokens, verification steps, acceptance length,
and time spent in target, draft, sampling, and KV work. Correlate acceptance
with workload class and context length.

### E201 - DFlash block-size sweep

Recheck `n_max` values 4 through 8 on current code. Historical tests selected
6; 4 and 7 were slower. Engine changes can move the optimum. Use complete Pi
turns and fixed quality gates.

### E202 - Q3-aligned drafter

Test the source author's planned Q3-aligned DFlash drafter against the current
Q4_0 draft. Measure acceptance, memory, decode, and distribution preservation.

### E203 - LoopSpec versus pure DFlash

Compare pure DFlash, prompt/N-gram reuse, adaptive combined mode, and target-only
decode. Break results down by exact-copy, patch reproduction, and novel output.

### E204 - llama.cpp versus SGLang and vLLM

Test current llama.cpp/DFlash against current SGLang and vLLM DFlash support on
one identical host. Measure single-user long-context behavior. Do not use batch
throughput as the primary score.

### E205 - CPU-native build matrix

Compare portable SM120a, CPU-native builds, link-time optimization, CUDA graph
settings, thread count, poll values, batch, and microbatch. Pair each binary
with its exact source tree and build manifest.

### E206 - KV cache formats

Compare Q4_0, Q5, Q6, Q8, and higher-precision KV formats. Measure 250K
retrieval, reasoning quality, memory, prefill, and decode. Do not assume KV
quantization is quality-neutral.

### E207 - Parallelism

Measure one, two, and three simultaneous Pi requests. Record per-request TTFT,
decode, total throughput, memory, and fairness. Single-user latency remains the
primary metric.

## Priority 3: model and quant choices

### E300 - Unsloth Dynamic V3 quant ladder

Compare the released 1-bit through 6-bit ladder using the same quality suite.
The current UD-Q3_K_XL is the baseline. A smaller quant is acceptable only if
it matches the declared quality tolerance. Do not replace Q3 only to improve a
speed screenshot.

### E301 - Q4 quality ceiling

Measure whether a Dynamic V3 Q4 target gives a useful quality gain for coding
and defensive-security tasks without losing the desired cost and speed. Report
memory pressure and DFlash compatibility.

### E302 - Unleashed V2

Evaluate the announced future model against the current target on long-context
retrieval, tool use, coding, security research, refusals, and looping.

### E303 - Qwen3.8-Flash-Next abliterated profile

Wait for a suitable abliterated release. Compare its quality and active-parameter
efficiency with dense 27B. Test native QSA long-context behavior, MTP, DFlash,
and tool use independently.

### E304 - Flash-Next CPU MoE offload

Reproduce the reported Q4, 250K, `-cmoe` profile on a 4090 or 5090 host with at
least 120 GB RAM. The prior report measured about 364 prompt TPS and 21 decode
TPS. Treat it as a quality/cost profile, not a speed replacement.

### E305 - Flash-Next SSD expert streaming

After a compatible abliterated model exists, reproduce the reported full-Q4
expert cache on Apple Silicon. Measure cache hit rate, SSD bandwidth, resident
memory, long-context stability, and quality. Do not accept the reported 40 TPS
until reproduced.

## Priority 4: provider and lifecycle economics

### E400 - Bid interruption recovery

Inject provider stops during prefill, decode, and tool waits. Verify clear Pi
errors, automatic wake, no duplicate rental, and bounded retries. Measure lost
work and recovery time at 100K and 200K.

### E401 - Destroy versus retain

Compare retained-storage cost and 47-second wake with destroy-and-rebuild cost,
download time, and host quality uncertainty. Compute the break-even idle gap.

### E402 - Build and model distribution

Compare public downloads, regional object storage, provider-side copy, a private
container image, and local relay. Measure cold bootstrap time, transfer cost,
integrity, and operational friction.

### E403 - Provider comparison

Revisit Vast, GPUHub, SaladCloud, TensorDock, and mature emergency providers.
Use identical model, context, private route, Pi workload, and cost accounting.

### E404 - Reservation economics

Compare on-demand, bid, and prepaid reservation at observed weekly use. Include
the loss of flexibility and the fact that stopping can release the GPU.

## Known rejected or constrained ideas

- Temperature 0: rejected because it reproduced a semantic planning loop.
- DFlash plus unconditional N-gram and `p_min=0.75`: caused a large real-work
  slowdown in the historical production profile.
- Private-route-first wake: increased cold start from about 47 to 64 seconds.
- Favorable microbenchmarks: never sufficient for promotion.
- Q2 replacement: outside the current accepted quality profile unless a future
  quality study explicitly changes that decision.
