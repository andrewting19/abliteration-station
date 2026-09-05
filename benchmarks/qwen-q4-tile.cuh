#pragma once

// Experimental synchronous Q4-to-shared-memory loader. Not a production path.
// Include after the engine common and attention swizzle headers.
template<int stride_tile, bool swz, int nwarps, int tile_rows, bool oob_check, bool sparse>
static __device__ __forceinline__ void qwen_load_q4_tile(
        const void * source, half2 * tile, int half2_columns, int row_bytes,
        int first_row, int valid_rows, const int32_t * indices, int column_offset) {
    constexpr int warp = 32;
    for (int linear=threadIdx.y*warp+threadIdx.x;
         linear<tile_rows*half2_columns; linear+=nwarps*warp) {
        const int row=linear/half2_columns;
        const int col=linear%half2_columns;
        int source_row=first_row+row;
        bool valid=!oob_check || row<valid_rows;
        if constexpr (sparse) {
            source_row=row<valid_rows ? indices[first_row+row] : -1;
            valid=source_row>=0;
        }
        half2 values=__float2half2_rn(0.0f);
        if (valid) {
            const int element=column_offset+2*col;
            const auto * blocks=reinterpret_cast<const block_q4_0 *>(
                reinterpret_cast<const char *>(source)+int64_t(source_row)*row_bytes);
            const auto & block=blocks[element/32];
            const int within=element%32;
            const int shift=within>=16 ? 4 : 0;
            const int first=(block.qs[within%16]>>shift)&15;
            const int second=(block.qs[(within+1)%16]>>shift)&15;
            values=__hmul2(__half2half2(block.d),__floats2half2_rn(float(first-8),float(second-8)));
        }
        if constexpr (swz) {
            *reinterpret_cast<half2 *>(reinterpret_cast<char *>(tile)+
                ggml_cuda_fattn_smem_swizzle::bytes_rc<stride_tile>(row,col))=values;
        } else {
            tile[row*stride_tile+col]=values;
        }
    }
}
