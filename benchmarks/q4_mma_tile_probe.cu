#include "ggml-cuda/common.cuh"
#include <dlfcn.h>

// Separate names prevent replacement of the normal attention templates.
#define QWEN_EXPERIMENTAL_Q4_TILE
#define flash_attn_ext_f16 qwen_experimental_q4_mma_kernel
#define ggml_cuda_flash_attn_ext_mma_f16_case qwen_experimental_q4_mma_case
#include "ggml-cuda/fattn-mma-f16.cuh"
template void qwen_experimental_q4_mma_case<256,256,8,8>(ggml_backend_cuda_context &,ggml_tensor *);

extern "C" void qwen_q4_mma_tile_probe(ggml_backend_cuda_context * ctx, ggml_tensor * dst) {
    GGML_ASSERT(dst->src[0]->ne[0] == 256);
    GGML_ASSERT(dst->src[1]->ne[0] == 256 && dst->src[2]->ne[0] == 256);
    GGML_ASSERT(dst->src[1]->type == GGML_TYPE_Q4_0 && dst->src[2]->type == GGML_TYPE_Q4_0);
    GGML_ASSERT(dst->src[0]->ne[1] >= 3 && dst->src[0]->ne[1] <= 8);
    qwen_experimental_q4_mma_case<256,256,8,8>(*ctx,dst);
}

void ggml_cuda_flash_attn_ext(ggml_backend_cuda_context & ctx, ggml_tensor * dst) {
    const auto * q=dst->src[0];
    const auto * k=dst->src[1];
    const auto * v=dst->src[2];
    float max_bias=0,softcap=0;
    memcpy(&max_bias,reinterpret_cast<const float *>(dst->op_params)+1,sizeof(float));
    memcpy(&softcap,reinterpret_cast<const float *>(dst->op_params)+2,sizeof(float));
    if (ggml_cuda_info().devices[ctx.device].cc == GGML_CUDA_CC_BLACKWELL &&
        q->ne[0]==256 && k->ne[0]==256 && v->ne[0]==256 &&
        q->ne[1]>=3 && q->ne[1]<=8 && q->ne[3]==1 &&
        k->type==GGML_TYPE_Q4_0 && v->type==GGML_TYPE_Q4_0 &&
        k->ne[2]>0 && q->ne[2]/k->ne[2]==6 && q->ne[2]%k->ne[2]==0 &&
        k->ne[1]%FATTN_KQ_STRIDE==0 && dst->src[3] && max_bias==0 && softcap==0) {
        qwen_q4_mma_tile_probe(&ctx,dst);
        return;
    }
    using Original=void (*)(ggml_backend_cuda_context &,ggml_tensor *);
    static auto original=reinterpret_cast<Original>(dlsym(RTLD_NEXT,
        "_Z24ggml_cuda_flash_attn_extR25ggml_backend_cuda_contextP11ggml_tensor"));
    GGML_ASSERT(original);
    original(ctx,dst);
}
