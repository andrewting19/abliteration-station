#include "ggml-cuda/convert.cuh"
#include <dlfcn.h>
#include <cstdio>
#include <vector>

int main(int argc,char ** argv) {
    if (argc!=2) return 2;
    void * library=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
    using Get=to_fp16_cuda_t (*)(ggml_type);
    auto original=reinterpret_cast<Get>(dlsym(library,"_Z21ggml_get_to_fp16_cuda9ggml_type"));
    auto candidate=reinterpret_cast<Get>(dlsym(RTLD_DEFAULT,"_Z21ggml_get_to_fp16_cuda9ggml_type"));
    if (!original || !candidate || original==candidate) return 3;
    for (int64_t count : {int64_t(32),int64_t(256),int64_t(8192),int64_t(200704)*256*4}) {
        const size_t bytes=count/32*sizeof(block_q4_0);
        block_q4_0 * input; half * a; half * b;
        if (cudaMallocManaged(&input,bytes)!=cudaSuccess || cudaMalloc(&a,count*2)!=cudaSuccess || cudaMalloc(&b,count*2)!=cudaSuccess) return 4;
        for (int64_t i=0;i<count/32;++i) {
            input[i].d=__float2half(float(int(i%257)-128)/64);
            for(int j=0;j<16;++j) input[i].qs[j]=uint8_t(i*37+j*19);
        }
        cudaEvent_t begin,end; cudaEventCreate(&begin); cudaEventCreate(&end);
        float times[2];
        for(int version=0;version<2;++version) {
            auto fn=(version?candidate:original)(GGML_TYPE_Q4_0);
            half * dst=version?b:a;
            fn(input,dst,count,nullptr); cudaDeviceSynchronize();
            cudaEventRecord(begin);
            for(int rep=0;rep<20;++rep) fn(input,dst,count,nullptr);
            cudaEventRecord(end); cudaEventSynchronize(end);
            cudaEventElapsedTime(&times[version],begin,end);
        }
        std::vector<unsigned short> ha(count),hb(count);
        cudaMemcpy(ha.data(),a,count*2,cudaMemcpyDeviceToHost);
        cudaMemcpy(hb.data(),b,count*2,cudaMemcpyDeviceToHost);
        if(cudaGetLastError()!=cudaSuccess) return 5;
        size_t different=0;
        for(int64_t i=0;i<count;++i) different+=ha[i]!=hb[i];
        std::printf("values=%lld differing_half_bits=%zu baseline_ms=%.6f candidate_ms=%.6f\n",(long long)count,different,times[0]/20,times[1]/20);
        if(different) return 1;
        cudaEventDestroy(begin); cudaEventDestroy(end); cudaFree(input); cudaFree(a); cudaFree(b);
    }
}
