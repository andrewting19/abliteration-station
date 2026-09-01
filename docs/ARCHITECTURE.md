# Architecture

The Pi-facing distribution is an official Pi package. The durable lifecycle
process remains a root-owned companion service. See [PI_PACKAGE.md](PI_PACKAGE.md).

## Request path

```text
Pi
  -> local OpenAI-compatible proxy on 127.0.0.1
  -> serialized lifecycle controller
  -> retained or fresh Vast RTX 5090
  -> private Tailscale TCP route
  -> llama.cpp model server on the remote loopback interface
```

Pi does not manage a cloud account. The provider driver owns rent, resume, stop,
and discovery operations. The controller owns model validation. The proxy owns
request forwarding, request counts, wake serialization, and idle stop.

## Start states

1. A healthy route exists. The proxy forwards the request.
2. A retained instance exists. The controller starts it and restores services.
3. A retained instance cannot reclaim its GPU within the provider scheduling
   window. The controller rents a replacement and first asks Vast to copy the
   verified workspace directly from the stopped instance. It uses public
   downloads and a rebuild only if that copy fails.
4. No retained workspace exists. The controller rents, builds, benchmarks, and
   accepts one qualified host.

The local health endpoint reports each wake phase, its start time, and a
bounded phase estimate. The Pi package shows this state while it keeps the
prompt queued. An estimate is not reported as a deadline. Pi says when an
estimate is exceeded and the provider is still working.

A file lock prevents duplicate rentals across processes. A shared Promise in
the Node.js proxy prevents duplicate wake operations for concurrent requests.

## Acceptance gates

For the included profile, every route must report these configured values:

- model ID `qwen38-cloud`;
- context size 262,144;
- target quantization that starts with `Q3_K`;
- non-empty output from a native medium-thinking chat request.

A fresh host enters the private route after the model and chat gates pass. The
first queued user request does not wait for a synthetic benchmark. After the
route is idle, a deferred worker runs the 120K replay and tool gate and records
the result. This gate supplies host-selection evidence without adding minutes
to first-token latency.

Vast's stopped-instance copy path is disabled by default because the provider
copy service was not reliable in production. Set `QWEN38_USE_PROVIDER_COPY=1`
only for a bounded transfer test. Public artifact bootstrap remains the default
until the transfer path has a successful acceptance record.

## Idle stop

The proxy records active requests and response activity. It does not stop the
provider during a request. After ten idle minutes, it sends a stop request to
Vast and removes the active route. The next inference request starts the route
again and then continues automatically.

## Provider contract

A provider implements `doctor`, `ensure`, `stop`, and `status`. Its
`module:Class` adapter is selected by configuration. `ensure` returns an
endpoint and a non-secret machine identity. `stop` must stop paid compute
without deleting retained model data. See [EXTENDING.md](EXTENDING.md).
