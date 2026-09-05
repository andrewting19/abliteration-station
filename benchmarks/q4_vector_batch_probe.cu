#include "ggml-cuda/common.cuh"
#include "ggml-cuda/fattn-vec.cuh"
#include <dlfcn.h>

// Test only: keep normal attention for all shapes outside the verified profile.
__attribute__((visibility("default"))) void ggml_cuda_flash_attn_ext(ggml_backend_cuda_context & ctx, ggml_tensor * dst) {
    const auto * q=dst->src[0];
    const auto * k=dst->src[1];
    const auto * v=dst->src[2];
    float bias=0,softcap=0;
    memcpy(&bias,reinterpret_cast<const float *>(dst->op_params)+1,sizeof(float));
    memcpy(&softcap,reinterpret_cast<const float *>(dst->op_params)+2,sizeof(float));
    if (ggml_cuda_info().devices[ctx.device].cc == GGML_CUDA_CC_BLACKWELL &&
        q->ne[0]==256 && k->ne[0]==256 && v->ne[0]==256 &&
        q->ne[1]>=3 && q->ne[1]<=8 && q->ne[3]==1 &&
        k->type==GGML_TYPE_Q4_0 && v->type==GGML_TYPE_Q4_0 &&
        k->ne[2]>0 && q->ne[2]==6*k->ne[2] &&
        k->ne[1]%FATTN_KQ_STRIDE==0 && dst->src[3] && bias==0 && softcap==0) {
        ggml_cuda_flash_attn_ext_vec_case_impl<256,8,GGML_TYPE_Q4_0,GGML_TYPE_Q4_0,false>(ctx,dst);
        return;
    }
    using Original=void (*)(ggml_backend_cuda_context &,ggml_tensor *);
    static auto original=reinterpret_cast<Original>(dlsym(RTLD_NEXT,
        "_Z24ggml_cuda_flash_attn_extR25ggml_backend_cuda_contextP11ggml_tensor"));
    GGML_ASSERT(original);
    original(ctx,dst);
}
