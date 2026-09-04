# Qwen cache and long-context acceptance

This file records the gates for the current cache-persistence work. A checked
item requires current command or runtime evidence.

- [x] Keep the production Pi route separate from the test GPU.
- [x] Pin the Q3 target, Q4_0 DFlash draft, 262,144 context, temperature 1.0,
  and native medium thinking.
- [x] Save a real Pi cache with more than 140,000 prompt tokens.
- [x] Transfer it through private SSH with root-only local storage.
- [x] Verify the archive SHA-256 and both member SHA-256 values before import.
- [x] Reject unsafe filenames, parent traversal, and unexpected archive paths.
- [x] Match the active executable, loaded workspace libraries, process
  arguments, target model, and draft model before restore.
- [x] Restore on a replacement RTX 5090 and prove an exact prompt-prefix hit.
- [x] Restore after a llama-server restart and a Vast stop/start cycle.
- [x] Use full prefill safely when the prompt prefix does not match.
- [x] Pass a live cancellation test without leaving the slot busy.
- [ ] Pass the installed Kevin idle-stop, cache-save, wake, import, and restore
  path from one open Pi session.
- [x] Complete the copied real Pi quality gate with an unrestricted output
  allowance and record task success, not only valid tool syntax.
- [x] Reproduce the accepted performance result with enough output tokens for
  a stable comparison.
- [x] Run the release security scan and prove that no private request, cache,
  key, address, or host identity is tracked.
- [ ] Document the installed rollback command and test it.

The fused-runtime candidate also passed these additional gates:

- [x] Prove the speed gain against target-only and old-DFlash controls on the
  same weak-CPU host.
- [x] Publish a checksum-verified portable CUDA runtime artifact.
- [x] Complete a clean official deployment from that artifact.
- [x] Pass the copied 117K Pi gate above 80 TPS and pass the tool loop.
- [x] Save and restore a nonempty 117K cache after a server restart.
- [x] Prove a more than 100K cache hit after restore.
- [x] Test a higher-precision Q8 draft and reject it when it does not beat Q4.

The speed target is an optimization objective. Quality, safe fallback, and
correct cache identity are hard gates. A short response is not sufficient
evidence for a decode-speed promotion.

## Fresh-instance time to first token

The pinned-image path passed the fresh-instance gate on 2026-09-03:

- [x] Start with no live or usable retained Vast instance.
- [x] Rent a fresh RTX 5090 and activate the private Tailscale route.
- [x] Keep Qwen3.8-27B Unleashed Q3_K_XL, Q4_0 DFlash, 262,144 context,
  temperature 1.0, and native medium thinking.
- [x] Send a captured real Pi request with 145,211 prompt tokens and no KV
  cache reuse.
- [x] Stream the first token in less than 180 seconds.
- [x] Pass the response quality check and the release test suite.

The measured result was 177.15 seconds to the first token, 1,492 prompt TPS,
and 74.4 decode TPS. The selected Vast machine already had the pinned runtime
image in its host image cache. This result does not claim that the first image
pull on an arbitrary host finishes in less than three minutes.

## Retained-instance warm start

- [x] Keep the KV checkpoint on the retained provider disk instead of copying
  it through Kevin.
- [x] Save more than 145,000 tokens before the idle stop.
- [x] Restore 145,207 cached tokens after two independent stop/start cycles.
- [x] Start model loading and Tailscale before SSH becomes available.
- [x] Avoid duplicate model gates and runtime hashing for the same retained
  instance.
- [x] Produce the same output SHA-256 as the cold-prefill control.
- [x] Measure first-token latency below 30 seconds twice: 21.36 and 20.20
  seconds.
- [x] Keep decode performance above 75 TPS: 77.56 and 77.49 TPS.

The warm result applies to a retained stopped instance with its provider disk.
It does not apply after Vast destroys the instance or moves the request to a
different host.
