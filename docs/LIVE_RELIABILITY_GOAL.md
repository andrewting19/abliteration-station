# Live Pi reliability and speed goal

## Five-dollar continuation, 2026-09-05

The user added funds and authorized at most five additional dollars before
reassessment. Starting account funds were 9.377988496900272 USD. Kevin's
spend_guard.py counts total account drawdown, including retained storage, and
stops labelled test rentals at 4.75 USD drawdown with a 0.25 USD margin. The
label prefix is qwen-goal5-20260905-. Production instances are not owned by
this guard. No automatic top-up was enabled.

On test instance 49994797, the real 201715-token request measured 66.19 TPS
with the fixed baseline (1004 output tokens), 41.99 TPS with the four-column
fused tile (1464 output tokens), and 38.70 TPS with direct-Q4 vector attention
at eight query columns (2937 output tokens). Responses differ, so these are not
equal-output comparisons. All finished with tool calls. Both candidates are
rejected as speed improvements. The vector candidate passed 18 numerical cases
and a zero-error memory check before replay. Summaries are saved directly on
Kevin under benchmarks/private/q4-mma-results in service state. Drawdown was
about 0.60 USD at the last check; all full-goal gates remain in force.

## Resolved funding interruption (2026-09-05 16:20 UTC)

Vast then reported balance -0.037874 USD, credit zero, and credit-only billing.
Test instance 49977258 changed to exited/stopped before the smaller-tile replay
connected. The cleanup service had not run, and the production proxy had no
matching stop event. The controller summary is empty and is not a valid result.
The user subsequently added funds with the five-dollar continuation limit above.
This is a historical interruption, not the current blocker. No performance or
full-lifecycle completion is claimed.

## Isolated live Pi lifecycle check

Follow-up results: a second wake restored about 186K cache tokens and completed
the read tool and final answer, but first token took 64.408 seconds. The third
attempt failed after a stale provider-state shortcut in the test helper; that
shortcut was removed. Its retry failed because Vast could not return the
retained GPU within 45 seconds. The queued start was cancelled. There are not
three consecutive passing cycles, and neither successful wake met 45 seconds.

The ten-minute idle check first refused to stop because restarting the isolated
proxy killed its child SSH tunnel. Required cache-save protection worked; this
was a test-route fault, not proof of a production Tailscale failure. Restoring
the tunnel allowed the automatic save of 185974 tokens and stop, but the delay
means the clean idle-timing gate remains open. Current budget drawdown was
0.91888 USD; the test instance is stopped and retains its bounded cleanup timer.

A private session branch from the historical 201715-token boundary uses the
actual Pi package with a read-only fixture guard. Its first request was 185643
tokens after the reduced tool set and test prompt, and completed a read tool
call plus the correct fixture heading. This is a functional test, not a speed
acceptance workload. The original session and production route were unchanged.

The first wake attempt failed because the isolated systemd proxy lacked the
root HOME environment. After correcting the test service, a Pi prompt resumed
the stopped test instance, restored 185744 cached tokens, and completed its
tool call and final response. First token took 55.454 seconds; the functional
cycle passed, but the 45-second target failed. A stale ready phase was also
observed; commit 679f8d4 fixes its reporting and passes 19 proxy tests. The fix
is deployed only to the isolated proxy, whose idle clock survived restart.
The real ten-minute idle-stop check is in progress; three cycles are not yet
verified. All lifecycle test state is under the private pi-lifecycle-49994797
directory on Kevin.

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

## Full-library and real-request results

Later fused tensor-core prototype: after isolating its symbols and using the
shared CUDA runtime, it passed 22 numerical cases and completed the real 201K
request at 57.02 TPS (2037 output tokens). The same-host baseline measured
67.67 TPS (1004 output tokens). This prototype is not an accepted speed fix.
An earlier library-resource-handle failure produced no valid speed result.

The smaller query-tile variant passed one targeted 200K numerical case, but
its real replay result was not collected before the bounded cleanup removed
instance 49972446 at 15:52 UTC. Treat its speed as unknown. Deletion was verified.
The baseline and first prototype summaries remain on Kevin under
`benchmarks/private/q4-mma-results`. Future replays must write their summary
directly to the controller, and must not start if insufficient cleanup time
remains. The goal is still incomplete; no inference candidate was promoted.

Full build 33967291510 passed. On isolated instance 49964346, both libraries
passed 130/130 numerical tests. At 196,442 context tokens, fixed baseline decoded
3,076 tokens at 52.04 TPS; the dispatch candidate decoded 808 at 53.80 TPS. At
201,715 context tokens, baseline decoded 1,004 at 66.33 TPS and candidate decoded
1,603 at 71.28 TPS. All finished with tool calls. Outputs differ, so these are
not equal-output speed comparisons. The candidate is not accepted as an 80 TPS
solution. Baseline cold prefill was 1,270 to 1,273 TPS. Candidate's second test
reused 196,438 cache tokens; do not compare its prefill time with a cold run.

A bounded Nsight Systems trace of the baseline 201K request preserved its
output hashes. Profiling changed decode from 66.33 to 62.39 TPS; do not use
profiled throughput for acceptance. The final 15 seconds of GPU kernel activity
fall within the reported 16.08-second decode phase. Summed kernel durations were
5.00 seconds for vector matrix products, 4.16 seconds for Q4 dequantization, and
2.78 seconds for attention. Summed durations are not necessarily wall time if
kernels overlap. The SQLite trace is saved privately on Kevin as
`benchmarks/private/iq-mmq-results/real-201715-trace.sqlite` in service state.

The target attention kernels have head width 256. Q4 cache support is already
compiled by default; enabling FA_ALL_QUANTS alone is not the proposed fix.
The current selector uses direct quantized vector attention only for batches
up to two tokens on this GPU, then selects FP16 matrix attention. Test direct
Q4 vector attention for the seven-token verification batch as a separate
candidate. Numerical and real-request gates remain required. Production is
unchanged.

## Rejected attention and cache experiments, 2026-09-05

Direct Q4 vector attention for Blackwell head-width 256 and query batches 3-8
passed 12 numerical cases at cache lengths 1024 and 16384, then six cases at
200704. The four initial batch-32/64 tests did not cover the changed path and
were not used as acceptance. The real 201715-token replay decoded 2597 tokens
at 31.03 TPS, substantially below the 66.33 TPS fixed baseline. This candidate
is rejected. The patch is retained only as a rejected experiment, not installed.

Q8 target K/V cache at the full 262144 capacity started successfully. A prefill
sample used 27980 MiB VRAM. This is a sample, not a proven peak or a full-capacity
stress test. The 201715-token request decoded 2267 tokens at 60.35 TPS and
finished with an edit tool call. It did not improve this workload. The target
weights and draft precision were unchanged; output differences prevent an
equal-output comparison. Q4 cache remains the production setting.

Results and the GPU trace are saved privately on Kevin. Test instance 49964346
was deleted after result-file checks, and absence was verified. Production was
not changed. Further work must address the measured GPU costs without assuming
that removing one conversion kernel makes the replacement attention path faster.
The 80 TPS, fresh-start, and full live Pi cycle requirements remain incomplete.

## Conversion-only paired replay, checked 2026-09-06 00:35 UTC

Instance 50001402 completed the 201715-token captured request with the fixed
baseline at 73.9658 decode TPS and the conversion-only candidate at 76.8695 TPS.
Both produced 1004 tokens, finished with an edit tool call, and matched content
and reasoning hashes. This is one pair, not a repeatable speed result. The old
summary did not hash tool arguments, so full output equality is not proven.
The replay helper now records a private-text-free hash of ordered tool names
and exact arguments. Future paired comparisons must check that hash too.

Baseline prefill took 135.854 seconds. Candidate reused 201711 tokens and had
request TTFT of 0.730 seconds. This excludes provisioning, startup, and cache
transfer; it does not prove the retained-wake or fresh-instance TTFT gate.
The conversion kernel passed bitwise checks and numerical attention tests,
but no inference change is promoted from this single measurement.

The cleanup timer removed instance 50001402; its absence was verified through
the provider API. All four original retained instances are stopped. The
production proxy is active with no active request or pending wake. Budget
drawdown is $2.0428 of the user's additional $5 allowance. The guard remains
enabled. The next speed test needs repeated warm baseline/candidate runs with
full output fingerprints on the same host. All full-goal gates remain open.

### Repeat test started, 2026-09-06 00:39 UTC

Test instance 50014017 (machine 145373) was rented at $0.508333/hour after
exact-offer revalidation. The provider reports the base image is still loading.
The one-hour `abliteration-test-50014017-expire.timer` is active on Kevin.
The account spending guard is active; drawdown before rental was $2.0501.
Only this test instance is intended to run. Production routing is unchanged.
The bounded readiness/bootstrap command is in tool session 17437. Inspect this
handle and provider state before retrying; do not create a duplicate instance.
Use the updated replay helper in private/q4-mma-results for complete tool
fingerprints. No replay has started on this instance yet.

The next check confirmed the same live readiness process, with provider image
layers still progressing. Contract start was Unix 1788655028.2870266. Loading
already exceeded 180 seconds before SSH readiness, so this attempt cannot meet
the fresh-instance TTFT target. Keep this delay in the result. The complete
local release check passed: 104 tests, two environment-specific skips, and
RELEASE_CHECK_OK. These tests do not replace real Pi acceptance cycles.

### Repeat results and cleanup, 2026-09-06 02:58 UTC

The 201715-token baseline cold request completed at 62.7979 decode TPS and
1289.38 prefill TPS (156.443 seconds prefill). Each replay produced 1004 output
tokens. Three restored-cache baseline runs measured 67.9954, 67.8686, and
67.8690 TPS. Three conversion-candidate runs measured 64.5399, 69.0867, and
69.1929 TPS. All seven runs matched content, reasoning, and ordered tool name
and argument hashes. Each warm run restored 201711 prompt tokens.

The candidate's initial run after restart was slower. Its two later runs show
only a small gain, not the 80 TPS outcome. No inference candidate is promoted.
The earlier cold-baseline versus warm-candidate pair is not a sufficient
measurement of a speed gain. Warm cache restore took approximately 1.7-2.0
seconds here; this is not full stop/wake TTFT.

The provider now confirms instance 50014017 is absent after scheduled cleanup.
The intended return to the released library was not executed before cleanup;
there is no test server left to restore. Private result files are retained on
Kevin under q4-mma-results. Current spending drawdown is $3.5786 of the $5
allowance. Production proxy has no active request or pending wake. Full Pi
stop/wake cycles and all performance requirements remain unproven.

### Final budgeted lifecycle test setup, 2026-09-06 03:02 UTC

Rented instance 50023706 on machine 144282 at $0.440333/hour after exact-offer
revalidation. The 45-minute abliteration-test-50023706-expire timer is active;
the account guard remains the earlier stop condition. Do not create another
instance while this one exists. Provider state is loading, with no SSH port.
Bounded readiness and official bootstrap process: tool session 45233.

Isolated state is on Kevin at benchmarks/private/pi-lifecycle-50023706. The
session fork uses the same historical 201715-token request boundary. Original
Pi history is unchanged. The private proxy is on port 17076, in transient unit
pi-lifecycle-50023706-proxy with a 40-minute runtime cap. Health is good, with
zero requests and no route. No inference request has been sent yet.

The test-only ensure adapter now starts its SSH tunnel in a separate systemd
unit instead of the proxy process group. This addresses the prior test setup
fault where proxy restart killed the cache-save route. Shell syntax passes;
live tunnel restart behavior still needs verification. This change does not
alter production Tailscale or production routing. The fixture tool guard is
benchmarks/private/pi_read_guard.ts and permits only test-project reads.

At 03:05 UTC the same provider instance remains loading with no SSH port.
The readiness command is confirmed live in session 45233. The private Pi RPC
process is live in session 61951. Its get_state response confirms provider
abliteration-station, URL http://127.0.0.1:17076/v1, qwen38-cloud, context 262144,
medium thinking, no active inference, and 362 historical messages. No prompt
has been sent. All three test units/guards checked active. Drawdown at 03:03
UTC was $3.5998. Continue the existing handles, not a duplicate deployment.

### Provider startup failure, 2026-09-06 03:10 UTC

Readiness session 45233 exited with status 1 and `Readiness deadline reached`.
Provider state remained loading with no SSH port throughout the bounded check.
The daemon-log request returned no useful content. Saved the final filtered
provider state in private/pi-lifecycle-50023706/provider-failure.json, then
destroyed only instance 50023706. A fresh instance listing confirms absence.
Stopped pi-lifecycle-50023706-proxy and closed Pi RPC session 61951 with EOF.
No model or inference request ran. The isolated fixture and session copy remain
on Kevin. Production was not modified. Drawdown at 03:10 UTC was $3.6263;
the account guard remains active. This failed provider startup is not a speed
measurement or a successful lifecycle cycle. Do not resume the terminal tool
handles or try to start this destroyed instance.

## Retained autostart discovery and live Pi test, 2026-09-06

After one offer disappeared before create, instance 50024630 was acquired at
$0.428333/hour. Its 45-minute cleanup timer remains active. The official
bootstrap completed on the test instance. Production route was not changed.
Private Pi RPC session 4822 uses private/pi-lifecycle-50024630; no inference
candidate was installed. This is the released target, draft, and CUDA runtime.

The initial 185637-token Pi fixture turn completed a real read tool and final
answer. It took 156.10 seconds to first token, including 14.50 seconds of local
route preparation; prefill was 1332.42 TPS. These short outputs are not sustained
decode acceptance. Cache save preserved 185805 tokens. A full confirmed
stop/wake/request cycle succeeded at 55.023-second TTFT, reusing 185749 tokens.

The container PID 1 was `bash /.launch`. It calls /root/onstart.sh before SSH,
but that hook was empty. Installing an ENTRYPOINT helper alone did not activate
it in this base-image/SSH path. Added retained-onstart.sh and bootstrap wiring
for the empty default hook and the exact prior package hook. Custom hooks and
symlinks are preserved. The existing package SSH permission repair is retained
in vast-onstart.sh, which calls the new helper when installed.

On the test worker the next confirmed stop/wake/Pi turn took 37.822 seconds to
first token and reused 185914 cache tokens. Supervisor showed model uptime of
24 seconds when the SSH check arrived. This supports earlier startup, but only
one post-change cycle has met the 45-second target.

The following wake failed because Vast reported resources unavailable. It
returned 503 after 48.68 seconds. A further real Pi cancellation test aborted
while an actual provider wake was pending: active_requests became zero, metric
status was 499/cancelled with no inference tokens, and Pi reported aborted.
The shared wake continued, then failed its provider deadline. At 03:41 UTC the
instance was exited/intended stopped, with no request, wake, or route left.
The three consecutive successful cycles requirement is NOT met. Idle-stop
timing and sustained 80 TPS remain open.

Also corrected source UI wording: a missing route does not prove the GPU is
stopped, and an HTTP response does not mean the first model token has arrived.
Unit checks cover ready-route wording. The release check passed 106 tests with
two environment-specific skips before the final connection wording adjustment.
The source changes are not yet installed into production or publicly released.
Private metrics and the 186104-token saved-cache metadata remain on Kevin.

### Scope correction and canonical rental retry

The preceding test used a manual `--ssh` base-image rental. The normal
qwen-vast rent command instead uses the pinned model image with `--args ""`,
which activates its own ENTRYPOINT. Therefore the 37.822-second measurement
and the empty onstart-hook fix apply to the legacy SSH/base-image path, not
proof of an improvement to the default production rental path. Do not promote
that measurement as default-path acceptance. No such production update was made.

Instance 50024630 stayed unavailable. It was destroyed and absence verified;
the private proxy and Pi RPC session 4822 were closed. Its temporary worker
cache was removed with the rental. The original Pi history and all original
production instances/caches were not changed. Test metrics and source session
copies remain private on Kevin.

Added a validated QWEN38_INSTANCE_LABEL option (default unchanged) so the normal
rental command can create budget-guarded test instances. Used that source command
to rent instance 50027040, offer 41974058 on machine 141223, at $0.521667/hour.
Provider readback verifies the production image digest ending 3f1e16490a and
image_runtype=args. The 45-minute cleanup timer is active. Official installed
qwen-vast deploy is running with private-route activation disabled. Check its
live tool handle before retrying; no Pi request has started on this instance.
Measured drawdown before rental was $3.9433 of the user's $5 allowance. The
account guard remains authoritative and may end this trial before cleanup.

Canonical deploy tool session: 87939 (confirmed live while provider image layers
download). The test-label validation and existing provider tests pass, 29/29.
The original production bootstrap/deploy/onstart files matched their prior
source hashes at readback. They were not overwritten. Do not claim the new
legacy-hook or UI source changes are installed in production.
