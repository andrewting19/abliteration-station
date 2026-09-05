#!/usr/bin/env python3
"""Compare exported CPU dot products with scalar dequantized dot products."""
import ctypes as c
import json
import math
import sys

base = c.CDLL(sys.argv[1] + "/libggml-base.so.0", mode=c.RTLD_GLOBAL)
cpu = c.CDLL(sys.argv[1] + "/libggml-cpu.so.0", mode=c.RTLD_GLOBAL)
cpu.ggml_cpu_init()
base.ggml_quantize_chunk.argtypes = [c.c_int, c.c_void_p, c.c_void_p, c.c_int64, c.c_int64, c.c_int64, c.c_void_p]
base.ggml_quantize_chunk.restype = c.c_size_t
for kind, enum in (("iq2_s", 22), ("iq3_s", 21)):
    for n in (256, 4096):
        x = (c.c_float * n)(*(math.sin(i * .37) for i in range(n)))
        y = (c.c_float * n)(*(math.cos(i * .19) for i in range(n)))
        importance = (c.c_float * n)(*([1] * n))
        qx, qy = c.create_string_buffer(n * 8), c.create_string_buffer(n * 8)
        base.ggml_quantize_chunk(enum, x, qx, 0, 1, n, importance)
        base.quantize_row_q8_K_ref.argtypes = [c.c_void_p, c.c_void_p, c.c_int64]
        base.quantize_row_q8_K_ref(y, qy, n)
        dx, dy = (c.c_float * n)(), (c.c_float * n)()
        for symbol, src, dst in (("dequantize_row_" + kind, qx, dx), ("dequantize_row_q8_K", qy, dy)):
            fn = getattr(base, symbol)
            fn.argtypes = [c.c_void_p, c.c_void_p, c.c_int64]
            fn(src, dst, n)
        expected = math.fsum(a * b for a, b in zip(dx, dy))
        for suffix in ("", "_generic"):
            fn = getattr(cpu, "ggml_vec_dot_" + kind + "_q8_K" + suffix)
            fn.argtypes = [c.c_int, c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_size_t, c.c_int]
            result = c.c_float()
            fn(n, c.byref(result), 0, qx, 0, qy, 0, 1)
            print(json.dumps({"type": kind, "n": n, "implementation": suffix or "native", "scalar": expected, "dot": result.value, "absolute_error": abs(expected-result.value)}))
