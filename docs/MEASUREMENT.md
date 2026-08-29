# Measurement contract

The optimization objective is not maximum tokens per second. It is the lowest
cost and shortest useful Pi turn with no accepted quality regression.

## Primary scorecard

Each candidate must report:

| Area | Required measurements |
|---|---|
| Quality | task success, valid tool calls, patch tests, long-context retrieval, loop rate, refusal boundary, and human review for real work |
| User latency | cold wake, time to first token, prefill, decode, tool round trips, and total turn time |
| Throughput | prompt TPS, token-weighted decode TPS, output tokens, draft acceptance, and cache-reuse hit rate |
| Cost | compute rate, storage rate, charged lifetime, cost per successful turn, and cost per million useful output tokens |
| Reliability | wake success, preemption rate, cancellation time, timeout rate, and recovery time |
| Resources | GPU memory, host memory, GPU utilization, power, PCIe traffic, disk reads, and network transfer |

## Real Pi telemetry

The local proxy writes privacy-safe request metrics to
`/var/lib/abliteration-station/metrics/requests.jsonl`. It records endpoint,
wake requirement, wake time, upstream header time, first response byte, total
time, status, response bytes, cancellation, usage, and server timing fields.
It does not store request bodies, response text, headers, tool arguments, file
contents, or API keys. The file is root-only and is never part of the public
repository.

## Quality is a hard gate

A candidate is quality-preserving only if all required tests pass and its real
Pi task success is not worse than the baseline beyond the declared tolerance.
Speed does not compensate for these failures:

- malformed or missing tool calls;
- incorrect code or failed tests;
- loss of a required long-context fact;
- a new refusal on an allowed task;
- deterministic planning or command loops;
- truncated output or context failure;
- loss of native medium thinking;
- changed sampling distribution that is not the experiment under test.

Use temperature 1.0 for production comparisons. Temperature 0 is a known
quality regression for this workload and is not an optimization candidate.

## Workload matrix

Measure all important candidates at these prompt bands:

- 2K: short control.
- 32K: early project work.
- 64K: common agent session.
- 100K to 130K: normal long Pi work.
- 180K to 220K: late session.
- 245K to 250K: lifecycle and compaction boundary.

At each band, include:

- novel coding generation;
- read-only and write tool branches;
- defensive-security analysis;
- exact-copy or patch reproduction;
- needle retrieval;
- one intentionally long output.

Exact-copy results must remain in the `exact-copy` workload class. A 229 TPS
copy-reuse result cannot be reported as 229 TPS normal agentic decode.

## Repetition and statistics

Run one warm-up and at least three measured samples. For noisy host or sampling
comparisons, use five or more samples. Report:

- median, p10, and p90 latency;
- token-weighted decode TPS;
- median cost per successful turn;
- complete failure and quality-failure counts;
- the fastest and slowest host facts.

Use paired prompts and seeds where the inference method permits this. For
sampling runs, compare aggregate task success and full-turn distributions, not
answer identity.

## Cost accounting

Track these values separately:

- advertised GPU rate;
- total rate with storage;
- paid cold-start and setup time;
- paid idle time;
- stopped-instance storage cost;
- failed-host and interrupted-turn cost;
- bytes downloaded and setup time for a fresh host.

The primary cost metric is dollars per successful real Pi turn. A secondary
metric is dollars per million useful output tokens. Both must include wake,
prefill, decode, and tool-loop time.

## Baseline

The accepted historical baseline is the exact Qwen3.8-27B Unleashed
UD-Q3_K_XL target, Q4_0 DFlash2, Q4_0 KV caches, DFlash `n_max=6`, one 262,144
slot, temperature 1.0, and native medium thinking.

Historical full-turn and long-context results range by host and sampled path.
The 120,844-token acceptance gate reached 84.62 decode TPS. A strong desktop
CPU host reached approximately 98 token-weighted TPS on a copied full Pi turn.
Use new paired measurements instead of treating either value as universal.

## Promotion rule

Promote a candidate only when:

1. Every hard quality and safety gate passes.
2. It improves total successful-turn cost, total turn latency, or both.
3. It passes real Pi tool work at more than 100K tokens.
4. It passes cancellation, cold wake, and idle stop.
5. It has a documented rollback path.
6. Its result is reproduced on a second run or host when host hardware is part
   of the claim.
