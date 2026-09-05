// Diagnostic preload for an isolated Linux worker. Does not change sampling.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <dlfcn.h>
#include <time.h>

struct llama_sampler;
struct llama_token_data_array;
struct common_sampler;
struct llama_context;
extern "C" const char * llama_sampler_name(const llama_sampler *);

static std::atomic<uint64_t> grammar_ns{0}, grammar_calls{0}, chain_ns{0}, chain_calls{0};
static std::atomic<uint64_t> grammar_cpu_ns{0}, chain_cpu_ns{0};
static std::atomic<uint64_t> sample_ns{0}, sample_cpu_ns{0}, sample_calls{0}, sample_sync_ns{0};
static thread_local unsigned sample_depth = 0;
static thread_local uint64_t sync_ns = 0, sync_cpu_ns = 0;

static uint64_t now_ns(clockid_t clock = CLOCK_MONOTONIC) {
    timespec value;
    clock_gettime(clock, &value);
    return uint64_t(value.tv_sec) * 1000000000ULL + uint64_t(value.tv_nsec);
}

extern "C" void llama_synchronize(llama_context * context) {
    using function = void (*)(llama_context *);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "llama_synchronize"));
    if (!original) std::abort();
    if (!sample_depth) { original(context); return; }
    const auto start = now_ns();
    const auto cpu_start = now_ns(CLOCK_THREAD_CPUTIME_ID);
    original(context);
    sync_cpu_ns += now_ns(CLOCK_THREAD_CPUTIME_ID) - cpu_start;
    sync_ns += now_ns() - start;
}

int32_t common_sampler_sample(common_sampler * sampler, llama_context * context, int index, bool grammar_first) {
    using function = int32_t (*)(common_sampler *, llama_context *, int, bool);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "_Z21common_sampler_sampleP14common_samplerP13llama_contextib"));
    if (!original) std::abort();
    const auto start = now_ns();
    const auto cpu_start = now_ns(CLOCK_THREAD_CPUTIME_ID);
    const auto sync_start = sync_ns;
    const auto sync_cpu_start = sync_cpu_ns;
    ++sample_depth;
    const auto token = original(sampler, context, index, grammar_first);
    --sample_depth;
    const auto cpu_used = now_ns(CLOCK_THREAD_CPUTIME_ID) - cpu_start;
    const auto used = now_ns() - start;
    const auto waited = sync_ns - sync_start;
    const auto cpu_waited = sync_cpu_ns - sync_cpu_start;
    sample_ns.fetch_add(used > waited ? used - waited : 0, std::memory_order_relaxed);
    sample_cpu_ns.fetch_add(cpu_used > cpu_waited ? cpu_used - cpu_waited : 0, std::memory_order_relaxed);
    sample_sync_ns.fetch_add(waited, std::memory_order_relaxed);
    sample_calls.fetch_add(1, std::memory_order_relaxed);
    return token;
}

extern "C" void llama_sampler_apply(llama_sampler * sampler, llama_token_data_array * candidates) {
    using function = void (*)(llama_sampler *, llama_token_data_array *);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "llama_sampler_apply"));
    if (!original) {
        std::fputs("Sampler profiler could not resolve the original function\n", stderr);
        std::abort();
    }
    const char * name = sampler ? llama_sampler_name(sampler) : nullptr;
    const bool grammar = name && std::strcmp(name, "grammar") == 0;
    const bool chain = name && std::strcmp(name, "chain") == 0;
    if (!grammar && !chain) {
        original(sampler, candidates);
        return;
    }
    const auto start = now_ns();
    const auto cpu_start = now_ns(CLOCK_THREAD_CPUTIME_ID);
    original(sampler, candidates);
    const auto cpu_elapsed = now_ns(CLOCK_THREAD_CPUTIME_ID) - cpu_start;
    const auto elapsed = now_ns() - start;
    (grammar ? grammar_ns : chain_ns).fetch_add(elapsed, std::memory_order_relaxed);
    (grammar ? grammar_calls : chain_calls).fetch_add(1, std::memory_order_relaxed);
    (grammar ? grammar_cpu_ns : chain_cpu_ns).fetch_add(cpu_elapsed, std::memory_order_relaxed);
}

__attribute__((destructor)) static void report() {
    std::fprintf(stderr, "QWEN_SAMPLER_PROFILE {\"grammar_calls\":%llu,\"grammar_ms\":%.6f,\"chain_calls\":%llu,\"chain_ms\":%.6f,\"grammar_cpu_ms\":%.6f,\"chain_cpu_ms\":%.6f,\"sample_calls\":%llu,\"sample_ms_excluding_sync\":%.6f,\"sample_cpu_ms_excluding_sync\":%.6f,\"sample_sync_ms\":%.6f}\n",
        static_cast<unsigned long long>(grammar_calls.load()), grammar_ns.load() / 1000000.0,
        static_cast<unsigned long long>(chain_calls.load()), chain_ns.load() / 1000000.0,
        grammar_cpu_ns.load() / 1000000.0, chain_cpu_ns.load() / 1000000.0,
        static_cast<unsigned long long>(sample_calls.load()), sample_ns.load() / 1000000.0,
        sample_cpu_ns.load() / 1000000.0, sample_sync_ns.load() / 1000000.0);
}
