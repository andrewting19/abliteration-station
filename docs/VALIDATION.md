# Validation

## Local release gates

`scripts/release-check.sh` verifies these items without paid compute:

- Python unit tests;
- concurrent proxy wake and clear wake-failure behavior;
- Pi wrapper hold and release order;
- Python, Node.js, and shell syntax;
- Python and Pi package contents;
- ShellCheck in CI;
- clean Ubuntu install and uninstall in a container;
- full-history Gitleaks scanning in CI;
- scans for private addresses, credentials, personal host names, and artifacts.

## Paid hardware gates

The first fresh host must pass these checks before the controller records its
route:

1. The exact Q3 model and Q4 draft files match pinned SHA-256 values.
2. The llama.cpp source tree matches the pinned tree hash.
3. The endpoint reports Q3 and 262,144 tokens of context.
4. A native medium-thinking chat request returns content.

After the first interactive request finishes and the route is idle, the
deferred acceptance worker runs these checks:

1. A synthetic 120K-context replay sustains at least 80 decode tokens per
   second.
2. A two-step tool loop returns the required tool call and final answer.

The deferred result records host-selection evidence. It does not delay the
first response and does not claim that every real Pi workload reaches 80 TPS.

## Reference acceptance result

The corrected reference gate passed real Pi tool use, cancellation, idle stop,
and a 117,046-token workload. It reached 119.0 decode tokens per second. A
239,310-token near-limit run reached 83.1 decode tokens per second. The
retained-instance path has reached the model in about 30 to 47 seconds when
Vast can return the same GPU. Results vary by host.

## Version 0.3 release candidate

Runtime commit `36a1bb11ea2e2addbad493b7d48af7c716ca6b20` completed a fresh
deployment on Vast instance `49596277`. The bootstrap used the verified cached
RTX 5090 runtime, verified the Q3 target and Q4 draft, reported a healthy
262,144-token endpoint, passed the native-thinking chat gate, and removed the
replaced instance. The model downloads were network-bound. The draft transfer
took approximately 18 minutes on this host, so version 0.3 does not promise a
fixed fresh-start time.

A real Pi turn at 146,287 input tokens completed with HTTP 200. It measured
1,289.9 prompt tokens per second and 75.0 decode tokens per second for 568
output tokens. The retained-GPU wake took 65.9 seconds, time to first response
byte was 103.7 seconds, and total request time was 194.7 seconds. This real
turn is workload evidence, not an 80-TPS guarantee. The 80-TPS requirement
applies to the fixed deferred acceptance workload.

## Pi package acceptance

For each release, test the package from its exact Git commit:

1. `pi install` clones and installs the commit without an npm audit failure.
2. `pi --list-models` reports `abliteration-station/qwen38-cloud` with 262,144
   tokens of context and thinking support.
3. Pi reports each package command once. No legacy copied extension or
   `models.json` provider remains.
4. `/abliteration-setup` installs the companion-service code from the same
   commit.
5. A normal `pi` request returns model output through the package provider.
6. Client cancellation reaches the proxy and is recorded as cancelled.
7. After paid compute stops, a prompt in an open Pi session starts the retained
   GPU and returns output without a Pi restart.

Commit `da334d48da973e1608d30213692da860b81f17c6` passed all seven items for
version 0.2.
The real request returned `PACKAGE_OK`. The bounded cancellation request was
recorded as cancelled after 3.34 seconds. The final retained wake used the same
open Pi process and the same Vast instance. Pi showed the queued prompt and
returned `FINAL_RETAINED_WAKE_OK`. The proxy measured 46.60 seconds to restore
the route and 52.49 seconds for the full request. The resumed short decode ran
at 216.22 tokens per second. The 117,046-token acceptance gate on this host ran
at 112.60 decode tokens per second.

## Release boundary

Version 0.3 does not claim support for other providers, GPUs, operating systems,
model variants, or multiple concurrent long-context slots.

## Portable cache candidate

The 2026-09-02 candidate restored a private 160K real-Pi prefix across a clean
runtime restart, a retained Vast stop/start, and a replacement RTX 5090. The
server reported 160,552 cached tokens and four prompt-evaluation tokens after
each accepted restore. Restore time was approximately 0.6 seconds. A live
cancellation released the server immediately.

The official candidate was installed on Kevin and restored the same 160,552
token prefix through the normal private proxy. A 2,048-token allowance ended
naturally after 555 tokens with valid `agent_result` and `bash` calls. Two
additional samples also ended with valid tool calls. On the selected
Threadripper host, the three samples reached 71.14 token-weighted decode TPS.

Version 0.4 includes this cache path. The installed Kevin idle-save and
wake-restore gate and the documented rollback test remain alpha limitations.
The local release and private-artifact security scans pass.

## Fused DFlash candidate

The portable candidate uses current llama.cpp commit
`7339054744f109c4cd89b75689dbb8a2c154d60e`, the project slot-checkpoint
patch, CUDA DFlash KV fusion, and backend sampling. A clean official deploy
from the public checksum-verified runtime artifact passed the 117,046-token
captured Pi gate at 120.32 TPS. A repeat reached 120.65 TPS. The integrated
tool loop passed.

The same weak-CPU test host reached 79.35 token-weighted TPS across 1,794
tokens at a 160,556-token cached prefix. Its target-only control was 49.0 TPS.
This is evidence that the main improvement comes from the fused speculative
path, not from a host CPU requirement.

A nonempty 117,109-token checkpoint restored after a clean server restart in
1.54 seconds. The next request reported 117,042 cached tokens and 103.03
decode TPS. The final restore-alignment build repeated the restored request at
134.6 decode TPS without a speculative-batch failure. The current release check
has 45 passing tests.

The same cache also survived an actual Vast stop/start. SSH returned in 46
seconds, the official resume path loaded the service in 16 seconds, and cache
restore took 1.88 seconds. The first request after restore reused 117,042
tokens and reached 108.58 TPS.
