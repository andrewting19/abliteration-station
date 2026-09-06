# Kaggle TPU lead

Reviewed 2026-09-06 UTC. Research only; no Kaggle account, deployment, or upload.

Original author: https://x.com/_ARahim_/status/2095577678837604644
User-supplied repost: https://x.com/Oluwaphilemon1/status/2096410154086301839
Source code: https://github.com/ARahim3/kaggle-tpu-lab
Rollback change: https://github.com/vllm-project/tpu-inference/pull/3178

The project exists and contains a serving script, notebook, launcher, and MTP
rollback patch. This establishes an implementation, not independently verified
throughput. Its published single-stream self-test uses a short story prompt,
192 output tokens, temperature zero, and ignore_eos. It does not establish
130 TPS on a real 100K-262K agentic prompt. It uses completion_tokens from
reported usage when available, but falls back to counting nonempty stream
events; that fallback is not a valid token count under speculative streaming.

The README separately reports 105K prefill in about 10 seconds and 225K prefill
in about 28 seconds. These are useful unreplicated claims. Eight TPU v5e chips
are not equivalent to one 5090. The recipe uses full BF16 stock Qwen, not our
Unleashed checkpoint. Its MTP drafter is not our DFlash2 drafter.

Important limits from the author: approximately 6-22 minutes startup with
prepared assets, prefix caching disabled in the pinned TPU runtime, one session
at a time, nine-hour sessions, and roughly 20 free TPU hours per week. Confirm
actual account quota, availability, and permitted use with Kaggle before use.
The default tunnel is a public, API-key-protected Cloudflare endpoint, not our
private Tailscale route. Do not send private Pi transcripts to this setup
without reviewing and securing the data path.

The eight-stream throughput table is internally inconsistent: 540 aggregate
TPS and 107 TPS for each of eight simultaneous streams do not describe the same
uniform steady-state interval. Request or reproduce raw measurements rather
than repeating that row as verified evidence.

Potential test: verify the source and rollback patch; run a nonprivate long
prompt with actual token counts; then test our exact checkpoint, temperature
one, native medium thinking, real tool calls, cancellation, and cache reuse.
Treat greedy 12/12 prompt agreement as a narrow correctness test, not proof for
all temperature-one workloads. Keep the existing Vast budget limit intact.
