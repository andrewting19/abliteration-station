# Validation

## Local release gates

`scripts/release-check.sh` verifies these items without paid compute:

- Python unit tests;
- concurrent proxy wake and clear wake-failure behavior;
- Pi wrapper hold and release order;
- Python, Node.js, and shell syntax;
- package build;
- scans for private addresses, credentials, personal host names, and artifacts.

## Paid hardware gate

The first fresh host must pass these checks before the controller records it:

1. The exact Q3 model and Q4 draft files match pinned SHA-256 values.
2. The llama.cpp source tree matches the pinned tree hash.
3. The endpoint reports Q3 and 262,144 tokens of context.
4. A native medium-thinking chat request returns content.
5. A synthetic long-context replay sustains at least 80 decode tokens per
   second.

## Reference acceptance result

The original deployment passed real Pi tool use, cancellation, idle stop, and
a 120,844-token workload. It reached 84.62 decode tokens per second for a
2,048-token output. The retained-instance path reached the model in about 47
seconds. Results vary by host.

## Release boundary

Version 0.1 does not claim support for other providers, GPUs, operating systems,
model variants, or multiple concurrent long-context slots.
