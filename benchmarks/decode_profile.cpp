// Compile with headers from the exact deployed engine revision.
#include "llama.h"
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <time.h>
#include <unistd.h>

struct counters {
    std::atomic<uint64_t> calls{0}, units{0}, elapsed{0}, cpu{0}, failures{0};
};
static counters decode_stats[3][10], get_stats[3][2], set_stats[3][2];
static counters read_stats[3][3][10];
static counters sync_stats[3][10];
static thread_local int last_batch[3] = {};
static const char * reads[] = {"layer_input", "nextn", "logits"};
static const char * roles[] = {"target", "draft", "other"};
static const char * batches[] = {"0", "1", "2", "3", "4", "5", "6", "7", "8", ">8"};

static uint64_t clock_ns(clockid_t clock) {
    timespec value;
    clock_gettime(clock, &value);
    return uint64_t(value.tv_sec) * 1000000000ULL + uint64_t(value.tv_nsec);
}
static int role(const llama_context * context) {
    if (!context) return 2;
    const auto * model = llama_get_model(context);
    char architecture[64] = {};
    if (!model || llama_model_meta_val_str(model, "general.architecture", architecture, sizeof(architecture)) < 0) return 2;
    if (!std::strcmp(architecture, "dflash") || !std::strcmp(architecture, "dspark")) return 1;
    return !std::strncmp(architecture, "qwen", 4) ? 0 : 2;
}
static void add(counters & value, uint64_t start, uint64_t cpu_start, uint64_t units, bool failed = false) {
    value.cpu.fetch_add(clock_ns(CLOCK_THREAD_CPUTIME_ID) - cpu_start, std::memory_order_relaxed);
    value.elapsed.fetch_add(clock_ns(CLOCK_MONOTONIC) - start, std::memory_order_relaxed);
    value.units.fetch_add(units, std::memory_order_relaxed);
    value.calls.fetch_add(1, std::memory_order_relaxed);
    value.failures.fetch_add(failed, std::memory_order_relaxed);
}

extern "C" void qwen_profile_sync(llama_context * context, uint64_t elapsed, uint64_t cpu, bool in_sampler) {
    if (in_sampler) return;
    const int r = role(context);
    auto & value = sync_stats[r][last_batch[r]];
    value.calls.fetch_add(1, std::memory_order_relaxed);
    value.elapsed.fetch_add(elapsed, std::memory_order_relaxed);
    value.cpu.fetch_add(cpu, std::memory_order_relaxed);
}

extern "C" int32_t llama_decode(llama_context * context, llama_batch batch) {
    using function = int32_t (*)(llama_context *, llama_batch);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "llama_decode"));
    if (!original) std::abort();
    const int category = batch.n_tokens > 8 ? 9 : (batch.n_tokens > 0 ? batch.n_tokens : 0);
    const int model_role = role(context);
    last_batch[model_role] = category;
    auto & value = decode_stats[model_role][category];
    const auto start = clock_ns(CLOCK_MONOTONIC), cpu_start = clock_ns(CLOCK_THREAD_CPUTIME_ID);
    const auto result = original(context, batch);
    add(value, start, cpu_start, batch.n_tokens > 0 ? batch.n_tokens : 0, result != 0);
    return result;
}

float * llama_get_embeddings_layer_inp(llama_context * context, uint32_t layer) {
    using function = float * (*)(llama_context *, uint32_t);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "_Z30llama_get_embeddings_layer_inpP13llama_contextj"));
    if (!original) std::abort();
    const int r = role(context);
    const auto start = clock_ns(CLOCK_MONOTONIC), cpu_start = clock_ns(CLOCK_THREAD_CPUTIME_ID);
    auto * result = original(context, layer);
    add(read_stats[r][0][last_batch[r]], start, cpu_start, 0);
    return result;
}

float * llama_get_embeddings_nextn(llama_context * context) {
    using function = float * (*)(llama_context *);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "_Z26llama_get_embeddings_nextnP13llama_context"));
    if (!original) std::abort();
    const int r = role(context);
    const auto start = clock_ns(CLOCK_MONOTONIC), cpu_start = clock_ns(CLOCK_THREAD_CPUTIME_ID);
    auto * result = original(context);
    add(read_stats[r][1][last_batch[r]], start, cpu_start, 0);
    return result;
}

extern "C" float * llama_get_logits_ith(llama_context * context, int32_t index) {
    using function = float * (*)(llama_context *, int32_t);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "llama_get_logits_ith"));
    if (!original) std::abort();
    const int r = role(context);
    const auto start = clock_ns(CLOCK_MONOTONIC), cpu_start = clock_ns(CLOCK_THREAD_CPUTIME_ID);
    auto * result = original(context, index);
    add(read_stats[r][2][last_batch[r]], start, cpu_start, 0);
    return result;
}

extern "C" size_t llama_state_seq_get_data_ext(llama_context * context, uint8_t * dst, size_t size, llama_seq_id seq, llama_state_seq_flags flags) {
    using function = size_t (*)(llama_context *, uint8_t *, size_t, llama_seq_id, llama_state_seq_flags);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "llama_state_seq_get_data_ext"));
    if (!original) std::abort();
    auto & value = get_stats[role(context)][(flags & LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY) != 0];
    const auto start = clock_ns(CLOCK_MONOTONIC), cpu_start = clock_ns(CLOCK_THREAD_CPUTIME_ID);
    const auto result = original(context, dst, size, seq, flags);
    add(value, start, cpu_start, result);
    return result;
}

extern "C" size_t llama_state_seq_set_data_ext(llama_context * context, const uint8_t * src, size_t size, llama_seq_id seq, llama_state_seq_flags flags) {
    using function = size_t (*)(llama_context *, const uint8_t *, size_t, llama_seq_id, llama_state_seq_flags);
    static const auto original = reinterpret_cast<function>(dlsym(RTLD_NEXT, "llama_state_seq_set_data_ext"));
    if (!original) std::abort();
    auto & value = set_stats[role(context)][(flags & LLAMA_STATE_SEQ_FLAGS_PARTIAL_ONLY) != 0];
    const auto start = clock_ns(CLOCK_MONOTONIC), cpu_start = clock_ns(CLOCK_THREAD_CPUTIME_ID);
    const auto result = original(context, src, size, seq, flags);
    add(value, start, cpu_start, result);
    return result;
}

__attribute__((destructor)) static void report_decode() {
    for (int r = 0; r < 3; ++r) {
        for (int b = 0; b < 10; ++b) {
            const auto & value = sync_stats[r][b];
            if (!value.calls.load()) continue;
            std::fprintf(stderr, "QWEN_SYNC_PROFILE {\"kind\":\"sync\",\"pid\":%d,\"role\":\"%s\",\"batch\":\"%s\",\"calls\":%llu,\"elapsed_ms\":%.6f,\"cpu_ms\":%.6f}\n",
                int(getpid()), roles[r], batches[b], (unsigned long long)value.calls.load(),
                value.elapsed.load()/1000000.0, value.cpu.load()/1000000.0);
        }
        for (int operation = 0; operation < 3; ++operation) {
            for (int b = 0; b < 10; ++b) {
                const auto & value = read_stats[r][operation][b];
                if (!value.calls.load()) continue;
                std::fprintf(stderr, "QWEN_READ_PROFILE {\"kind\":\"readback\",\"pid\":%d,\"role\":\"%s\",\"operation\":\"%s\",\"batch\":\"%s\",\"calls\":%llu,\"elapsed_ms\":%.6f,\"cpu_ms\":%.6f}\n",
                    int(getpid()), roles[r], reads[operation], batches[b], (unsigned long long)value.calls.load(),
                    value.elapsed.load()/1000000.0, value.cpu.load()/1000000.0);
            }
        }
        for (int b = 0; b < 10; ++b) {
            const auto & value = decode_stats[r][b];
            if (!value.calls.load()) continue;
            std::fprintf(stderr, "QWEN_DECODE_PROFILE {\"kind\":\"decode\",\"pid\":%d,\"role\":\"%s\",\"batch\":\"%s\",\"calls\":%llu,\"tokens\":%llu,\"elapsed_ms\":%.6f,\"cpu_ms\":%.6f,\"failures\":%llu}\n",
                int(getpid()), roles[r], batches[b], (unsigned long long)value.calls.load(), (unsigned long long)value.units.load(),
                value.elapsed.load()/1000000.0, value.cpu.load()/1000000.0, (unsigned long long)value.failures.load());
        }
        for (int partial = 0; partial < 2; ++partial) {
            for (int operation = 0; operation < 2; ++operation) {
                const auto & value = operation ? set_stats[r][partial] : get_stats[r][partial];
                if (!value.calls.load()) continue;
                std::fprintf(stderr, "QWEN_STATE_PROFILE {\"kind\":\"state\",\"pid\":%d,\"role\":\"%s\",\"operation\":\"%s\",\"partial\":%d,\"calls\":%llu,\"bytes\":%llu,\"elapsed_ms\":%.6f,\"cpu_ms\":%.6f}\n",
                    int(getpid()), roles[r], operation ? "set" : "get", partial, (unsigned long long)value.calls.load(),
                    (unsigned long long)value.units.load(), value.elapsed.load()/1000000.0, value.cpu.load()/1000000.0);
            }
        }
    }
}
