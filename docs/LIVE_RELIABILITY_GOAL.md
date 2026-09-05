# Live Pi reliability and speed goal

Started 2026-09-05 UTC. Status: active, not accepted.

## Acceptance

- Complete the real Pi request with valid stream termination and tool use.
- Verify three consecutive stop, wake, and real-context request cycles.
- Target at least 80 sustained decode tokens/s at 100K or more context tokens.
- Target retained local-cache first token below 45 seconds.
- Target fresh-instance first token below 180 seconds. Count provider setup,
  failed attempts, and prefill. Do not exclude failed cold starts.
- Keep the configured rental cap, preserve useful cache, and avoid extra running
  deployments. Do not interrupt active user inference for a benchmark.

## Initial evidence

The live request could not resume its retained GPU. Vast reported unavailable
resources. The 45-second retained deadline expired. The offer search then
returned offers that were absent from the next search. The first request
returned 503. Pi retried.

The first replacement stalled during image loading and was removed after the
existing 180-second no-progress limit. A new Pi retry selected the same offer.
The second replacement reached running state after more than five minutes.
This cold start fails the 180-second target. No decode measurement is available
yet. The replacement costs approximately $0.4283/hour, below the $0.53 cap.

The saved checkpoint had 36 tokens, consistent with a short readiness probe.
This does not establish that an actual long-context checkpoint was overwritten.

## Changes under verification

- Revalidate a selected offer on its observed machine, then check its exact ID
  and price locally. Live checks found that Vast's `id` search filter returned
  no results for an offer returned by the machine filter. The initial ID-filter
  change was corrected before release. The corrected rental succeeded.
- Retain failed bootstrap offer IDs for 30 minutes across Pi retry processes.
- Report rental failure separately from model-test failure.
- Preserve current failure details in the proxy error; ignore stale errors.
- Remove the generating readiness probe from retained wake.
- Skip remote runtime work when cache metadata has no portable artifact and
  belongs to another instance.
- Measure first actual stream token separately from first response byte, and
  record the finish reason without storing response content.

63 tests and the release checks pass. Shell and Python changes are installed
on the controller. The proxy was restarted during zero active inference
requests. Its runtime directory now survives a service restart; the live route
remained intact. End-to-end acceptance remains pending.

## Live results at 04:49 UTC

- First successful request: 187,851 input tokens, 1,246 output tokens.
- Cold prefill: 138.59 seconds, 1,355.47 tokens/s.
- Decode for that request: 59.99 tokens/s.
- The real Pi transcript shows completed tool calls and non-error tool results.
- Seventeen completed requests produced 14,839 output tokens at 63.23
  token-weighted decode tokens/s. Context ranged from 187,851 to 208,143.
- Recent cached requests reached the first actual token in about 3.0 to 3.3
  seconds and reported a tool-calls finish reason.
- A real 200,016-token checkpoint saved successfully: 3,849,190,144 bytes,
  with 1,349.56 ms reported save time. This is a provider-local checkpoint.
- A separate test offer below the price cap was unavailable on recheck. No
  second test instance was created. The user's active work was not interrupted
  for inference experiments.

## Remaining gates

The 80 tokens/s sustained real-context target is not met. The fresh first-token
target is not met. Three stop/wake/request cycles have not run. Use a separate
qualified test host, or wait until user work is idle, before comparative tests.
Keep target quantization, temperature, thinking, and tool constraints unchanged.
The server reports that grammar disables target backend sampling. This is a
candidate bottleneck, not a measured attribution of all missing throughput.

## Isolated follow-up test

An isolated RTX 5090 with a Ryzen 9700X was secured at $0.4806/hour. It uses
the same pinned image and is not connected to the production route. A 45-minute
cleanup timer limits its lifetime. Bootstrap is still in progress; no speed
result is accepted yet.

An explicit, disabled-by-default one-request capture is available through
`ABLITERATION_STATION_CAPTURE_NEXT_FILE`. It creates a 0600 file, does not
overwrite existing captures, and stops capture above 32 MiB. Captures contain
private request bodies. Keep them outside the repository and remove them after
the experiment. Normal metrics contain no request body.

The proxy now preserves idle age across restarts. Retained startup also checks
the current price against the cap before asking Vast to resume compute. The
machine-specific rental, capture, idle-age, and price changes pass 67 tests and
the release checks.

The initial capture was matched to the wrong nearby metrics record. Its file
timestamp identifies the 208,587-token request, whose production response was
52 tokens. It is not a sustained decode workload. The capture can now require
a minimum completed output count and writes a matching private metrics sidecar.

## Completed isolated checks, 2026-09-05

- The captured 208,587-token request cold-prefilled in 166.82 seconds at
  1,250.35 tokens/s. Its 46-token result is excluded from speed acceptance.
- Three stopped-instance resume and provider-local cache probes reached their
  first token in 30.64, 38.59, and 21.36 seconds. Each reused 208,583 tokens and
  processed only four prompt tokens. Each returned a tool call with the same
  reasoning hash. These are isolated controller/provider probes, not three
  live Pi TUI wakes.
- A proxy cancellation probe closed the client after its first actual token.
  The proxy recorded cancellation; the server became idle 0.59 seconds later.
- Historical request prefixes were reconstructed using exact tool-call IDs,
  excluding the reference assistant answer. Replayed token counts matched the
  production counts exactly. The 201,715-token case produced 2,728 output tokens
  at 63.17 TPS. The 196,442-token case produced 3,076 output tokens at 53.53 TPS.
  Both ended with tool calls. The faster-CPU host is not promoted as an 80 TPS
  improvement.
- The test instance was destroyed, and absence was verified before closing
  its cleanup timer. No test GPU remains rented.

## Production completion and idle stop

The user's Pi turn ended normally at 05:16:06 UTC. Its final context was about
51K after compaction. The normal idle controller saved 51,545 tokens and
stopped the retained instance about 610 seconds after the last activity. The
route was cleared and the provider reported exited/stopped. This is an actual
production idle-stop check, not an artificially shortened timer.

The 80 TPS real-context gate and fresh-instance first-token gate remain open.
The three isolated wake probes do not establish three complete live Pi TUI
wake cycles. Further speed experiments must retain the real request corpus,
sampling settings, target quantization, and tool constraints.

The completed changes pass 72 tests and the release checks. Cancelled HTTP 200
streams are excluded from successful-turn throughput. Summary output reports
successful-output cost separately. The no-route idle path no longer repeatedly
invokes a stop command that cannot succeed.

## Paired draft and prefill tests

Another isolated contract on the same physical test host used the same pinned
target, runtime, context, temperature, thinking, and tool constraints.

| Real request | Variant | Output tokens | Decode TPS | Prompt time |
|---|---|---:|---:|---:|
| 196,442 tokens | Q4 draft control | 3,076 | 53.19 | 151.93 s |
| 196,442 tokens | Q8 draft | 3,076 | 52.60 | 152.90 s |
| 201,715 tokens | Q8 draft, cached prefix | 1,658 | 67.89 | 6.64 s |
| 201,715 tokens | Q4 draft, same cached-prefix count | 1,527 | 77.27 | 7.22 s |
| 196,442 tokens | Q4, prefill microbatch 4096 | 2,803 | 53.00 | 147.41 s |

The 196K Q4 and Q8 runs produced identical content and reasoning hashes. All
runs ended with tool calls. Q8 is not promoted. The larger prefill microbatch
saved about 4.5 seconds but used about 3.8 GB more VRAM and did not improve
decode. It is not promoted. Production remains Q4 draft and 8192/2048 batches.
The test contract was deleted; absence was verified. Test cleanup should use
an absolute UTC deadline: the relative timer's displayed wall deadline drifted
on the controller VM. The original wall-clock deadline was enforced instead.

## SSH findings

A fresh contract reused a previous container's address and port. Global
address-based known-host entries caused SSH failure. The adapter now uses a
stable `HostKeyAlias` based on the verified instance ID while keeping strict
host-key checks. The corrected transport deployed successfully.

The image build also generated shared SSH host keys. Source changes remove
build-time keys and generate fresh-container keys outside the portable model
workspace. Tests verify different new keys and stable retained keys. Legacy
retained containers preserve their existing trust until replacement. This
image change was initially source-only. Candidate builds now pass fresh-key
uniqueness and retained-key tests. The production default image is not yet
changed; do not claim that legacy retained workers have new keys.

## Next performance investigation

Measure sampler and grammar CPU cost on the real long-request corpus before
another tuning sweep. The inspected `llama_grammar_apply_impl` decodes candidate
vocabulary pieces on each active grammar application. Reusing decoded pieces
or exact-state validity masks is a hypothesis, not a proven bottleneck or speed
gain. Any cache must preserve UTF-8, grammar stacks, end-of-generation behavior,
and cloned-sampler semantics exactly. Keep the 80 TPS and lifecycle gates open.

## Candidate image and layer reuse verification

Candidate `sha256:29c7977540116efe813ce79c9f82290a87922213130658f7a5bdc0d9d1461789`
passed image build and CPU-only container tests in Actions run 33953229627.
Two fresh containers had different host keys; restarting one preserved its
key. A Vast test worker also presented a new key, not the legacy shared key.

Layer-header inspection found different file and directory timestamps for
unchanged model data in successive builds. All five large model/draft layers
changed, requiring 14,151,118,052 additional bytes if the old layers were cached.
Fixed `SOURCE_DATE_EPOCH` plus image-export timestamp rewriting was applied.
Two independent normalized builds reused all five large layers; changed large
layer bytes were zero. This does not remove model downloads on a fully uncached
host. Candidate builds use separate tags and did not overwrite production tags.

## Real sampler profile: CPU-sampler hypothesis rejected for this case

The verified 196,442-token request produced 3,076 tokens at 53.22 decode TPS.
Content and reasoning hashes matched the uninstrumented control. Decode took
57,773.681 ms. The diagnostic probe reported:

- Full sampler, excluding synchronization: 593.029 ms elapsed, 591.920 ms CPU.
- Grammar: 2.872 ms elapsed, 2.761 ms CPU across 683 calls.
- Sampler chain: 252.302 ms elapsed, 251.119 ms CPU across 3,077 calls.
- Synchronization inside the sampler: 3.524 ms elapsed.

Grammar and chain measurements are subsets of the full sampler. The full
sampler is about one percent of decode time. Removing this cost cannot yield
80 TPS. Do not implement grammar caching as the main speed fix based on the
earlier hypothesis. Other server work is outside this measurement.

An initial probe attempt failed before inference because its launcher path was
wrong; that attempt is not evidence. The path was corrected and the actual
diagnostic process was verified running. The second long-case profile was not
started because insufficient time remained before cleanup. The test instance
was deleted by its deadline cleanup; absence was verified.

Next, measure target versus draft decode calls and recurrent-state replay or
copy work. Inspect small speculative-batch CUDA dispatch before choosing a
kernel change. Keep target weights, sampling, and verification semantics fixed
for the first measurements. The 80 TPS and full live Pi wake gates remain open.

## Target verification profile and next kernel test (2026-09-05)

The full forwarding probe replayed the same 196,442-token request. It produced
3,076 tokens at 53.41 TPS, with matching content and reasoning hashes and a
`tool_calls` finish. The private evidence file on Kevin is
`benchmarks/private/sampler-profile/sync-196442.log` under the service state
directory. The test worker was deleted after collection.

Of 57,571 ms decode time, 1,312 target batch-seven synchronization calls used
51,007 ms (about 89%). The sampler excluding synchronization used 548 ms.
Draft next-token readback used 2,730 ms. API decode calls are asynchronous;
their return times alone do not measure completed GPU work. CUDA stream waits
can use CPU time while they wait. This result does not show a CPU arithmetic
bottleneck. State-copy records did not show a generation replay storm.

The next candidate changes only Blackwell IQ-format dispatch for batches five
through eight from the vector kernel to the existing matrix kernel. The target
file contains mostly IQ-format weights despite its Q3_K_XL label. Batch-seven
verification is therefore a relevant case. Single-token dispatch, target
weights, draft weights, sampling, and verification rules remain unchanged.

Actions run 33961758359 builds paired baseline and candidate CUDA libraries
from the exact deployed source with the same compiler. This is a CPU-only
build; no GPU is rented while it compiles. No speed gain is established yet.
Before installation, require numerical backend tests with nonzero case counts,
then uninstrumented A/B runs on the copied 196K and 201K Pi requests. Keep the
production runtime unchanged until correctness and performance pass. The full
live Pi lifecycle gates remain incomplete.

The first compiler run failed at test-executable linking, not during a GPU
test. The CPU-only runner could not resolve `libcuda.so.1`. Commit 3f5a13c adds
a build-only driver-stub search path. Replacement run 33962877786 is active;
no candidate has passed numerical or real-request performance gates yet.
Local release checks passed 85 tests with two Linux-only skips. Both skipped
probe tests passed separately on Kevin with the exact engine headers.

## GPU numerical investigation (2026-09-05)

Run 33962877786 passed. Downloaded library hashes and source trees matched the
build record. Large image pulls on test instances 49956315 and 49958258 did
not reach SSH; the second reported retries for three roughly 4 GB model layers.
Both instances were deleted and their absence verified. These attempts do not
pass the cold-start gate. A partial layer read from the Mac succeeded, which
does not establish that the worker network path was healthy.

Test instance 49959229 uses a CUDA base image, costs $0.48056/hour, and has a
cleanup timer for 12:59:56 UTC. SSH and an RTX 5090 with driver 595.84 were
verified. It is separate from the production route.

Both paired libraries fail the existing CUDA matrix test for IQ2_S and IQ3_S.
The CPU-only test passes 28 cases; CUDA GET_ROWS passes eight cases. An
independent full-matrix test confirms the discrepancy against scalar arithmetic:
CPU NMSE is about 0.00005, while CUDA NMSE is 0.36 to 0.51. Disabling CUDA graphs
and PDL does not change this result. No tolerance was loosened.

Smaller diagnostics pass: CPU dot products agree with scalar dequantized dot
products within 0.000002 absolute error, all 512 sign-mask cases pass, and a
direct CUDA dot-product check passes with and without fast math. These narrow
checks do not excuse the full-matrix failures. Initial diagnostic helper errors
were corrected before collecting those results. Production remains unchanged.
The full-matrix input, activation conversion, and dispatch paths need further
investigation before either candidate can be accepted or benchmarked on Pi.

## Bounded lookup extraction fix

Input readback matched the original buffers. Compute Sanitizer found invalid
global reads in IQ2_S table access at vecdotq.cuh:1140. Replacing the local
byte-pointer index reads with unsigned shifts and masks fixed the independent
vector-matrix test. Its CUDA NMSE became approximately 0.00006, below the
unchanged 0.0005 threshold. Its memory check reported zero errors.

With only the vector fix, the broader test passed 124/130 cases. The six
remaining failures used the matrix kernel, which had the same lookup pattern.
Applying equivalent extraction there produced 130/130 passing cases and zero
Compute Sanitizer errors. Evidence is on Kevin under
`benchmarks/private/iq-mmq-results/both-fixed-sanitizer.log` in service state.
These tests used diagnostic shared-library overrides, not a released runtime.
The exact compiler root cause is not yet established; do not claim all local
byte-pointer reads are unsafe or that production was shown to have this fault.

Commit 8b7eeb2 saves the patch and starts full paired build 33967291510. Both
outputs include the lookup fix; only the candidate changes the IQ verification
batch dispatch. This separates correctness work from the proposed speed change.
The full rebuilt artifacts must repeat numerical checks before real Pi replay.
Test instance 49959229 was deleted after logs were copied. Its absence was
verified. Production remains unchanged, and all agentic speed gates remain open.
