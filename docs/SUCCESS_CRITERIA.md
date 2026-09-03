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
