# Blackwell IQ matrix-kernel candidate

This is an experiment, not an accepted runtime.

1. Download artifact `iq-mmq-candidate` from Actions run 33967291510 after it
   succeeds. Check BUILD_INFO, source tree, compiler, and SHA256SUMS.
2. Use one isolated RTX 5090 worker under the configured rental cap. Set its
   cleanup deadline before starting tests. Do not change the production route.
3. Test the baseline and candidate libraries with the same test executable and
   dependencies. Verify which CUDA library the process loads. Do not replace a
   library mapped by a running process.
4. For each library, run the existing numerical backend test, with console
   output saved and the process exit code checked:

   ```sh
   test-backend-ops test -b CUDA0 -o MUL_MAT \
     -p 'type_a=iq(2_xxs|2_xs|2_s|3_xxs|3_s|4_xs|4_nl),' --output console
   python3 benchmarks/check_iq_backend_log.py backend.log
   ```

   The log check requires passed cases for all seven changed formats at batches
   1, 4, 5, 6, 7, and 8. Exit zero alone is insufficient: the upstream executable
   can skip a missing backend or run no matching cases. The pinned numerical
   tolerance for these types is 5e-4 NMSE. Do not increase it to pass a candidate.
5. Run uninstrumented paired replays of the private 196,442- and 201,715-token
   Pi requests. Keep weights, draft, sampling, context, and server flags fixed.
   Record prefill, cached tokens, decode duration, generated token count, draft
   acceptance, finish reason, tool-call validity, and output hashes. Different
   floating-point kernels can change output; do not treat speed alone as quality
   evidence. Inspect any divergence before promotion.
6. Require the real long-output performance gate, then test the live Pi path.
   Backend microbenchmarks do not satisfy sustained agentic TPS or lifecycle
   requirements. Keep all unmet gates open and remove the test deployment.

Build history: run 33961758359 compiled the baseline CUDA library but failed
when linking the test executable: the CPU runner had no `libcuda.so.1` driver.
Commit 3f5a13c adds a link-only SONAME alias to the toolkit driver stub. The
stub is not packaged and is not added to the runtime search path. Replacement
run 33962877786 must still pass before its output can be used.

Run 33962877786 passed compilation but failed numerical GPU tests. Diagnostic
lookup fixes then passed 130/130 cases with zero memory-checker errors. Run
33967291510 builds both libraries with those fixes. Repeat the gates on these
full artifacts; the diagnostic override result alone does not accept them.
