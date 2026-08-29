# Experiment results

## 2026-08-29: RTX 5090 cost and speed sweep

The production profile stayed at Qwen3.8 Q3, 262,144 context, temperature 1,
native medium thinking, and Q4_0 DFlash2.

### Accepted production host

- Vast instance class: on-demand RTX 5090
- CPU: AMD EPYC 7R32
- PCIe bandwidth: 26.3 GB/s
- Total price: $0.4567/hour with 150 GB storage
- Cold prompt: 225,136 tokens at 1,038 prompt TPS
- Long-context decode: 1,637 tokens at 83.1 TPS
- Gate context: 239,310 prompt tokens
- Tool loop: correct `read_file` call and correct final use of the tool result
- Private Pi route: passed after promotion

After the fixture correction, the same host passed the intended gate with
117,046 prompt tokens and 1,447 output tokens at 119.0 decode TPS. Its cold
111K warm-up ran at 1,546 prompt TPS. The integrated tool-loop gate also
passed.

This host passed the 80 TPS minimum. Cold bootstrap was slow. The provider
needed about eight minutes to load the base image. The 12 GiB target download
averaged about 20 MiB/s.

### Bid-host result

An RTX 5090 bid host with an AMD EPYC 9B14 and 54.1 GB/s PCIe cost
$0.3383/hour at the tested bid. Three 239K decode samples were 88.0, 89.0,
and 83.9 TPS. Its cold prompt result was 1,131 TPS. The tool loop and a
30-second retained-instance restart passed.

The first $0.20 GPU bid was preempted during setup. A later stop during a
direct benchmark was probably the local ten-minute idle controller, not a
provider preemption. Direct benchmark commands did not register activity with
the proxy. The performance gate now inhibits idle stop for the test duration.

### Rejected host and selector finding

One rented host advertised enough capability through the broad search but had
`cuda_max_good` 13.0. It could not start the CUDA 13.2 image. A server-side
`cuda_vers>=13.2` query then hid valid hosts, so that query is not reliable for
this workflow. The selector now uses the broad `cuda_vers>=13` query and checks
the returned `cuda_max_good >= 13.2` value locally before rental.

### Measurement correction

The fixture documented as 120K was 239,310 tokens. The old generator used
13,250 synthetic functions. The generator now uses 6,600 functions for an
approximately 120K gate. The 239K results above remain useful as a near-limit
gate, but they must not be labeled 120K.

### DFlash sweep status

The first sweep attempt was invalid because idle stop ended the direct run.
The corrected sweep used the lifecycle inhibit and the 117K gate. Its decode
results were:

- `n_max=4`: 109.0 TPS
- `n_max=5`: 112.7 TPS
- `n_max=6`: 119.0 TPS
- `n_max=7`: 116.5 TPS
- `n_max=8`: 114.1 TPS

Keep `n_max=6`. It was the fastest value in this bounded sweep.
