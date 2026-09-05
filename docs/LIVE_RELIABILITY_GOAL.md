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

- Revalidate a selected offer by exact ID rather than another broad search.
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
