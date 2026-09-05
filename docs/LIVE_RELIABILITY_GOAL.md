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
