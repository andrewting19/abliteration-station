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

Commit `617544324899a6c4694c59c7360105f64c905205` passed items 1 through 6.
The real request returned `PACKAGE_OK`. The bounded cancellation request was
recorded as cancelled after 3.34 seconds. Item 7 must pass before the v0.2.0
tag is released.

## Release boundary

Version 0.2 does not claim support for other providers, GPUs, operating systems,
model variants, or multiple concurrent long-context slots.
