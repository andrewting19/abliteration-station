#include "ggml-cuda/convert.cuh"
#include <dlfcn.h>

__global__ void qwen_q4_contiguous_half2(const block_q4_0 * source, half2 * output, int64_t pairs) {
    const int64_t pair=int64_t(blockIdx.x)*blockDim.x+threadIdx.x;
    if (pair>=pairs) return;
    const int64_t element=2*pair;
    const block_q4_0 & block=source[element/32];
    const int within=element%32;
    const int shift=within>=16 ? 4 : 0;
    const float d=__half2float(block.d);
    const int lo=(block.qs[within%16]>>shift)&15;
    const int hi=(block.qs[(within+1)%16]>>shift)&15;
    output[pair]=__floats2half2_rn(d*float(lo-8),d*float(hi-8));
}

static void qwen_convert_q4(const void * source, half * output, int64_t count, cudaStream_t stream) {
    GGML_ASSERT(count%32==0);
    if (count==0) return;
    const int64_t pairs=count/2;
    qwen_q4_contiguous_half2<<<(pairs+255)/256,256,0,stream>>>(
        static_cast<const block_q4_0 *>(source),reinterpret_cast<half2 *>(output),pairs);
}

__attribute__((visibility("default"))) to_fp16_cuda_t ggml_get_to_fp16_cuda(ggml_type type) {
    if (type==GGML_TYPE_Q4_0) return qwen_convert_q4;
    using Original=to_fp16_cuda_t (*)(ggml_type);
    static auto original=reinterpret_cast<Original>(dlsym(RTLD_NEXT,"_Z21ggml_get_to_fp16_cuda9ggml_type"));
    GGML_ASSERT(original);
    return original(type);
}
