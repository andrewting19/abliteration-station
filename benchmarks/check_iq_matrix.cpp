#include "ggml.h"
#include "ggml-backend.h"
#include "ggml-alloc.h"
#include <vector>
#include <cmath>
#include <cstdio>

int main() {
    ggml_backend_load_all();
    int failures=0;
    for (const char * name : {"CPU", "CUDA0"}) {
        auto backend=ggml_backend_init_by_name(name,nullptr);
        if (!backend) return 2;
        for (auto type : {GGML_TYPE_IQ2_S,GGML_TYPE_IQ3_S}) {
            constexpr int k=256,m=16,n=7;
            auto ctx=ggml_init({16*1024*1024,nullptr,true});
            auto a=ggml_new_tensor_2d(ctx,type,k,m);
            auto b=ggml_new_tensor_2d(ctx,GGML_TYPE_F32,k,n);
            auto result=ggml_mul_mat(ctx,a,b);
            auto graph=ggml_new_graph(ctx);
            ggml_build_forward_expand(graph,result);
            auto buffer=ggml_backend_alloc_ctx_tensors(ctx,backend);
            if (!buffer) return 3;
            std::vector<float> x(k*m),y(k*n),dx(k*m),importance(k,1),out(m*n);
            for (int i=0;i<k*m;++i) x[i]=std::sin(i*.37);
            for (int i=0;i<k*n;++i) y[i]=std::cos(i*.19);
            std::vector<unsigned char> q(ggml_nbytes(a));
            ggml_quantize_chunk(type,x.data(),q.data(),0,m,k,importance.data());
            ggml_get_type_traits(type)->to_float(q.data(),dx.data(),k*m);
            ggml_backend_tensor_set(a,q.data(),0,q.size());
            ggml_backend_tensor_set(b,y.data(),0,y.size()*sizeof(float));
            if (ggml_backend_graph_compute(backend,graph)!=GGML_STATUS_SUCCESS) return 4;
            ggml_backend_tensor_get(result,out.data(),0,out.size()*sizeof(float));
            double error=0, energy=0;
            for (int col=0;col<n;++col) for (int row=0;row<m;++row) {
                double expected=0;
                for(int j=0;j<k;++j) expected+=double(dx[row*k+j])*y[col*k+j];
                double diff=expected-out[col*m+row]; error+=diff*diff; energy+=expected*expected;
            }
            double nmse=error/energy;
            std::printf("backend=%s type=%s nmse=%.9g\n",name,ggml_type_name(type),nmse);
            failures+=nmse>5e-4;
            ggml_backend_buffer_free(buffer); ggml_free(ctx);
        }
        ggml_backend_free(backend);
    }
    return failures?1:0;
}
