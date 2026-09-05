#include <cuda_runtime.h>
#include <cstdio>

__global__ void signs(unsigned * out) {
    unsigned s = threadIdx.x;
    out[2*s] = __vcmpne4(((s & 0x03) << 7) | ((s & 0x0C) << 21), 0);
    out[2*s+1] = __vcmpne4(((s & 0x30) << 3) | ((s & 0xC0) << 17), 0);
}

int main() {
    unsigned * out;
    if (cudaMallocManaged(&out, 512*sizeof(unsigned)) != cudaSuccess) return 2;
    signs<<<1,256>>>(out);
    if (cudaDeviceSynchronize() != cudaSuccess) return 3;
    int failures = 0;
    for (unsigned s=0; s<256; ++s) {
        for (unsigned half=0; half<2; ++half) {
            unsigned expected=0;
            for (unsigned j=0; j<4; ++j) {
                if (s & (1u << (4*half+j))) expected |= 255u << (8*j);
            }
            if (out[2*s+half] != expected) {
                if (failures < 8) std::printf("sign=%u half=%u actual=%08x expected=%08x\n",s,half,out[2*s+half],expected);
                ++failures;
            }
        }
    }
    std::printf("sign_cases=512 failures=%d\n",failures);
    cudaFree(out);
    return failures ? 1 : 0;
}
