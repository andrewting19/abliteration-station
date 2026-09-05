#include "ggml-cuda/common.cuh"

// Separate names prevent replacement of the normal attention templates.
#define QWEN_EXPERIMENTAL_Q4_TILE
#define flash_attn_ext_f16 qwen_experimental_q4_mma_kernel
#define ggml_cuda_flash_attn_ext_mma_f16_case qwen_experimental_q4_mma_case
#include "ggml-cuda/fattn-mma-f16.cuh"

extern "C" void qwen_q4_mma_tile_probe(ggml_backend_cuda_context * ctx, ggml_tensor * dst) {
    GGML_ASSERT(dst->src[0]->ne[0] == 256);
    GGML_ASSERT(dst->src[1]->ne[0] == 256 && dst->src[2]->ne[0] == 256);
    GGML_ASSERT(dst->src[1]->type == GGML_TYPE_Q4_0 && dst->src[2]->type == GGML_TYPE_Q4_0);
    GGML_ASSERT(dst->src[0]->ne[1] >= 3 && dst->src[0]->ne[1] <= 8);
    qwen_experimental_q4_mma_case<256,256,8,8>(*ctx,dst);
}
