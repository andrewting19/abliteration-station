# Validation

## Local release gates

`scripts/release-check.sh` verifies these items without paid compute:

- Python unit tests;
- concurrent proxy wake and clear wake-failure behavior;
- Pi wrapper hold and release order;
- Python, Node.js, and shell syntax;
- package build;
- ShellCheck in CI;
- clean Ubuntu install and uninstall in a container;
- full-history Gitleaks scanning in CI;
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

The corrected reference gate passed real Pi tool use, cancellation, idle stop,
and a 117,046-token workload. It reached 119.0 decode tokens per second. A
239,310-token near-limit run reached 83.1 decode tokens per second. The
retained-instance path has reached the model in about 30 to 47 seconds when
Vast can return the same GPU. Results vary by host.

## Release boundary

Version 0.1 does not claim support for other providers, GPUs, operating systems,
model variants, or multiple concurrent long-context slots.
