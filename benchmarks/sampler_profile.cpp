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
extern "C" const char * llama_sampler_name(const llama_sampler *);

static std::atomic<uint64_t> grammar_ns{0}, grammar_calls{0}, chain_ns{0}, chain_calls{0};
static std::atomic<uint64_t> grammar_cpu_ns{0}, chain_cpu_ns{0};

static uint64_t now_ns(clockid_t clock = CLOCK_MONOTONIC) {
    timespec value;
    clock_gettime(clock, &value);
    return uint64_t(value.tv_sec) * 1000000000ULL + uint64_t(value.tv_nsec);
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
    std::fprintf(stderr, "QWEN_SAMPLER_PROFILE {\"grammar_calls\":%llu,\"grammar_ms\":%.6f,\"chain_calls\":%llu,\"chain_ms\":%.6f,\"grammar_cpu_ms\":%.6f,\"chain_cpu_ms\":%.6f}\n",
        static_cast<unsigned long long>(grammar_calls.load()), grammar_ns.load() / 1000000.0,
        static_cast<unsigned long long>(chain_calls.load()), chain_ns.load() / 1000000.0,
        grammar_cpu_ns.load() / 1000000.0, chain_cpu_ns.load() / 1000000.0);
}
