# Experiment results

## 2026-09-02: Fused CUDA DFlash runtime

The host-CPU comparison below showed correlation, but it did not prove that
the draft model must run on the CPU. The launcher already used
`--spec-draft-ngl all`. A same-host control test isolated the runtime change.

The candidate updates llama.cpp to commit
`7339054744f109c4cd89b75689dbb8a2c154d60e`. This revision includes the
fused DFlash encoder-to-KV path and native DFlash2 work. The launcher also
uses target backend sampling. These changes keep more speculative-decoding
work inside the CUDA path.

On the same RTX 5090 with an AMD EPYC 7F72 and 26.2 GB/s PCIe, the copied
160,556-token Pi workload gave these token-weighted results:

| Runtime | Output tokens | Decode TPS | Result |
|---|---:|---:|---|
| Old target only | 1,062 | 49.0 | Control |
| Old DFlash Q4 | 841 | 49.3 | No useful speculative gain |
| Old DFlash Q4 plus backend sampling | 1,679 | 55.3 | Small gain |
| New fused DFlash Q4 plus backend sampling | 1,794 | 79.35 | Accept |

The new DFlash path was approximately 62% faster than the target-only
control. Thus, CPU model-name filtering is not required for the main speed
gain. PCIe, CPU, and storage still affect prefill, cache save, and startup.

The official clean deployment downloaded the 45 MB verified runtime asset,
started the exact Q3 target with the Q4 DFlash draft, and passed the copied
117,046-token Pi gate at 120.32 and 120.65 decode TPS in two runs. The tool
gate passed. After a server restart, a saved 117,109-token slot restored in
1.54 seconds. The next request reused 117,042 tokens and decoded at 103.03
TPS.

A Q8_0 DFlash draft used 21.8 GB of GPU memory. It reached 120.12 TPS on the
same 117K gate. This did not improve the Q4 result, so Q4 remains the default.

An actual Vast stop/start of the isolated host took 46 seconds to return SSH.
The official retained-instance resume then took 16 seconds to restart the
private services and load the model. The 117,109-token checkpoint restored in
1.88 seconds. The next request reused 117,042 tokens and reached 108.58 TPS.
The test instance was stopped after the gate.

One host returned a complete model file but did not terminate its aria2
transfer. The bootstrap now uses pinned byte sizes, detects a stable complete
file, verifies its SHA-256, and safely completes the download. It also retries
a transfer that makes no progress for 120 seconds.

## 2026-09-02: Portable 160K Pi cache and decode sweep

The test used a private copy of a real Pi request. The request had 160,556
prompt tokens. The production route stayed on a separate RTX 5090.

The slot save produced 3,129,178,216 bytes of server state. The local
root-only `tar+zstd` archive was 3,612,762,526 bytes. Its SHA-256 and the two
member hashes were verified before extraction on the replacement host.

The replacement RTX 5090 restored 161,047 tokens in 576 to 620 ms. A request
after restore reported 160,552 cached tokens and only four prompt-evaluation
tokens. A clean restart from the release runtime artifact gave the same active
runtime fingerprint as the source host. An actual Vast stop/start took 47.3
seconds from stopped state to model readiness. The next restore took 591 ms
and preserved the same 160,552-token prefix hit.

The full 2,048-token allowance run completed with valid `agent_result` and
`bash` tool calls. It produced 631 tokens at 55.87 decode TPS. Three repeated
1,024-token allowance samples at the production `n_max=6` setting produced
1,817 output tokens at 64.57 token-weighted decode TPS. All samples had a
160,552-token cache hit and valid tool calls.

The bounded DFlash and CPU-thread tests were:

| Variant | Output tokens | Token-weighted decode TPS | Decision |
|---|---:|---:|---|
| `n_max=6`, 16 threads | 1,817 | 64.57 | Baseline |
| `n_max=4`, 16 threads | 1,380 | 59.94 | Reject |
| `n_max=5`, 16 threads | 2,041 | 66.16 | Do not promote; small, noisy gain |
| `n_max=6`, `p_min=0.10` | 2,560 | 57.38 | Reject |
| `n_max=6`, 8 threads | 1,151 | 66.18 | Do not promote; sample too short |
| `n_max=6`, 4 threads | 1,066 | 56.06 | Reject |

The cancellation gate stopped a live stream after 3.0 seconds. The server
reported healthy state 7 ms later. No tested tuning replaced the production
`n_max=6`, 16-thread configuration.

The official candidate was then installed on Kevin. A portable import from
the isolated Threadripper host to the former EPYC production host took 394.3
seconds, including archive validation, transfer, import, and restore. The
next request reused 160,552 tokens. Three real Pi samples on the EPYC host
produced 1,405 tokens at 45.3 token-weighted TPS. The same route was moved to
the Threadripper 9970X host without changing the model or runtime. Three
samples there produced 945 tokens at 71.14 token-weighted TPS. Each sample
reused 160,552 tokens and ended with valid agent tool calls. This comparison
shows that host CPU selection has a large effect on DFlash performance.

Kevin has limited free disk. The installed configuration therefore uses the
`in-place-safe` archive replacement mode. The verified remote slot remains on
the running GPU during transfer. A failed transfer removes the incomplete
local archive and the controller refuses to stop the GPU. The default release
configuration continues to use atomic archive replacement on hosts with
enough disk.

## 2026-08-29: RTX 5090 cost and speed sweep

The production profile stayed at Qwen3.8 Q3, 262,144 context, temperature 1,
native medium thinking, and Q4_0 DFlash2.

### Accepted production host

- Vast instance class: on-demand RTX 5090
- CPU: AMD EPYC 7R32
- PCIe bandwidth: 26.3 GB/s
- Total price: $0.4567/hour with 150 GB storage
- Cold prompt: 225,136 tokens at 1,038 prompt TPS
- Long-context decode: 1,637 tokens at 83.1 TPS
- Gate context: 239,310 prompt tokens
- Tool loop: correct `read_file` call and correct final use of the tool result
- Private Pi route: passed after promotion

After the fixture correction, the same host passed the intended gate with
117,046 prompt tokens and 1,447 output tokens at 119.0 decode TPS. Its cold
111K warm-up ran at 1,546 prompt TPS. The integrated tool-loop gate also
passed.

This host passed the 80 TPS minimum. Cold bootstrap was slow. The provider
needed about eight minutes to load the base image. The 12 GiB target download
averaged about 20 MiB/s.

### Bid-host result

An RTX 5090 bid host with an AMD EPYC 9B14 and 54.1 GB/s PCIe cost
$0.3383/hour at the tested bid. Three 239K decode samples were 88.0, 89.0,
and 83.9 TPS. Its cold prompt result was 1,131 TPS. The tool loop and a
30-second retained-instance restart passed.

The first $0.20 GPU bid was preempted during setup. A later stop during a
direct benchmark was probably the local ten-minute idle controller, not a
provider preemption. Direct benchmark commands did not register activity with
the proxy. The performance gate now inhibits idle stop for the test duration.

### Rejected host and selector finding

One rented host advertised enough capability through the broad search but had
`cuda_max_good` 13.0. It could not start the CUDA 13.2 image. A server-side
`cuda_vers>=13.2` query then hid valid hosts, so that query is not reliable for
this workflow. The selector now uses the broad `cuda_vers>=13` query and checks
the returned `cuda_max_good >= 13.2` value locally before rental.

### Measurement correction

The fixture documented as 120K was 239,310 tokens. The old generator used
13,250 synthetic functions. The generator now uses 6,600 functions for an
approximately 120K gate. The 239K results above remain useful as a near-limit
gate, but they must not be labeled 120K.

### DFlash sweep status

The first sweep attempt was invalid because idle stop ended the direct run.
The corrected sweep used the lifecycle inhibit and the 117K gate. Its decode
results were:

- `n_max=4`: 109.0 TPS
- `n_max=5`: 112.7 TPS
- `n_max=6`: 119.0 TPS
- `n_max=7`: 116.5 TPS
- `n_max=8`: 114.1 TPS

Keep `n_max=6`. It was the fastest value in this bounded sweep.

## 2026-09-04: retained-instance warm start and provider-local KV cache

The test used one retained RTX 5090 instance and the captured real Pi request
with 145,211 prompt tokens. The output was limited to 64 tokens so that the
test measured startup latency. All variants produced the same output SHA-256
and passed the quality gate.

| Variant | First token | Cache reuse | Decode TPS |
|---|---:|---:|---:|
| Retained instance, cold prefill | 152.65 s | 0 | 80.89 |
| Provider-local KV restore, sequential startup | 51.10 s | 145,207 | 78.53 |
| Provider-local KV restore, entrypoint autostart, run 1 | 21.36 s | 145,207 | 77.56 |
| Provider-local KV restore, entrypoint autostart, run 2 | 20.20 s | 145,207 | 77.49 |

The provider-local checkpoint was 2,838,652,556 bytes. The latest server save
took 742 ms. The complete save and stop command took 6.3 seconds. The cache
does not pass through Kevin during a retained-instance wake. The container
entrypoint starts the model and Tailscale while Vast prepares SSH. The
controller also does not repeat model gates or a runtime hash after the Vast
adapter validates the same exact retained instance.

The controlled result shows that KV restore saves 101.55 seconds compared to
a cold prefill on the same retained instance. Entrypoint autostart then removes
about 30 seconds from the earlier sequential restore path. Replacement hosts
still require runtime identity validation and a portable cache transfer or a
cold prefill.
