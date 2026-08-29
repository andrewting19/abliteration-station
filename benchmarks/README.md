# Abliteration Station benchmarks

This directory defines the measurement contract for cost and speed work. It
does not contain private Pi transcripts or paid benchmark results.

## Rules

1. Keep the model quality profile fixed unless the experiment explicitly tests
   quality: Q3 target, temperature 1.0, native medium thinking, and 262,144
   tokens of context.
2. Compare the same workload, prompt tokens, output budget, seed, and sampling
   settings.
3. Report cold start, time to first token, prefill, decode, total turn time, and
   cost separately.
4. Separate exact-copy or prefix-reuse tests from novel coding generation.
5. Report token-weighted decode speed across the complete Pi turn. Do not use
   only the fastest short branch.
6. Reject a candidate if any required quality, tool, retrieval, cancellation,
   or privacy gate fails.
7. Run at least three measured repetitions after one warm-up. Report median,
   p10, and p90.
8. Store only sanitized or synthetic requests in Git. Keep real Pi captures in
   the operator's private benchmark directory.

## Workload classes

- `novel-agentic`: normal coding or defensive-security work with tool calls.
- `exact-copy`: repeated code or patch reproduction. This measures reuse
  systems such as LoopSpec and must not be reported as normal decode speed.
- `long-retrieval`: needle retrieval and instruction following at 64K to 250K.
- `prefill-only`: fixed small output used to isolate prompt processing.
- `decode-only`: warm prompt with a large output budget.
- `lifecycle-cold`: stopped provider through first response token.
- `quality`: deterministic code, tool, retrieval, refusal, and loop checks.

## Commands

Run one manifest against an already running OpenAI-compatible server:

```sh
python3 benchmarks/measure_openai.py \
  benchmarks/manifests/smoke.json \
  --base-url http://127.0.0.1:17072 \
  --api-key-file /root/.config/abliteration-station/inference_api_key \
  --output private-results/smoke.jsonl
```

Build a comparison report:

```sh
python3 benchmarks/analyze_results.py private-results/*.jsonl
```

Both tools use only the Python standard library. The measurement output follows
`schema/result.schema.json`.

Summarize real privacy-safe Pi measurements:

```sh
python3 benchmarks/summarize_proxy_metrics.py \
  /var/lib/abliteration-station/metrics/requests.jsonl \
  --hourly-rate 0.40
```

## Private result layout

Use a directory outside Git, or use `private-results/`, which is ignored:

```text
private-results/
  baseline/
  experiment-id/
  sanitized-real-pi/
```

Each experiment must retain its manifest, runtime arguments, source revision,
model hashes, host facts, raw JSONL results, and generated summary.
