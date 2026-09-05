#include "ggml-cuda/vecdotq.cuh"
#include "ggml-quants.h"
#include <cmath>
#include <cstdio>

__global__ void dot(const void * x, const block_q8_1 * y, float * out, int kind) {
    int i = threadIdx.x;
    if (i < 8) out[i] = kind == 22 ? vec_dot_iq2_s_q8_1(x,y,0,2*i) : vec_dot_iq3_s_q8_1(x,y,0,2*i);
}

int main() {
    float x[256], y[256], dx[256], importance[256];
    void * qx; block_q8_1 * qy; float * out;
    if (cudaMallocManaged(&qx, 2048) != cudaSuccess || cudaMallocManaged(&qy, 8*sizeof(block_q8_1)) != cudaSuccess || cudaMallocManaged(&out, 8*sizeof(float)) != cudaSuccess) return 2;
    for (int i=0;i<256;++i) { x[i]=std::sin(i*.37); y[i]=std::cos(i*.19); importance[i]=1; }
    quantize_row_q8_1_ref(y,qy,256);
    int failures=0;
    for (int kind : {21,22}) {
        ggml_quantize_chunk((ggml_type)kind,x,qx,0,1,256,importance);
        if (kind==22) dequantize_row_iq2_s((block_iq2_s*)qx,dx,256);
        else dequantize_row_iq3_s((block_iq3_s*)qx,dx,256);
        dot<<<1,32>>>(qx,qy,out,kind);
        if (cudaDeviceSynchronize()!=cudaSuccess) return 3;
        double expected=0, actual=0;
        for (int i=0;i<256;++i) expected += dx[i]*__low2float(qy[i/32].ds)*qy[i/32].qs[i%32];
        for (int i=0;i<8;++i) actual += out[i];
        std::printf("type=%d scalar=%.9f cuda=%.9f error=%.9f\n",kind,expected,actual,std::abs(expected-actual));
        failures += std::abs(expected-actual)>0.001;
    }
    cudaFree(qx); cudaFree(qy); cudaFree(out);
    return failures ? 1 : 0;
}
