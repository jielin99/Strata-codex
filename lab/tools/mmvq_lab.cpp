// mmvq_lab: the engine's decode GEMV (strata::kernels::native_mmvq) on the IQ3_XXS model's dense shapes and types,
// with a working set larger than the GPU's caches.
//   mmvq_lab [working-set MiB=1024] [ms per case=300] [filter=all]
// Each case rotates through enough copies of its weight matrix to cover the working set, so every call reads its
// weights from memory, not from a cache. One line per case: type, n_in x n_out (the GGUF's ne0 x ne1), columns,
// microseconds per call, weight GB/s (GB = 1e9 bytes) and a checksum of the last output (the bytes are synthetic,
// so the checksum only shows the call produced finite numbers). The engine's STRATA_MMVQ_* switches apply as usual.
// Built against the engine's kernels (see lab/plans for the command line); it changes no engine file.
#include "strata/kernels/native_mmvq.hpp"
#include <sycl/sycl.hpp>
#include <dpct/dpct.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

struct Case { const char* tensor; const char* type_name; int type, n_in, n_out; };

// From the model's tensor list (lab/results/01-decode-bound/tensors.tsv): every (shape, type) pair a dense
// projection of the IQ3_XXS model uses.  ggml types: Q4_K 12, Q5_K 13, Q6_K 14, IQ4_NL 20, IQ3_S 21, IQ4_XS 23, Q2_0 42.
static const Case kCases[] = {
    {"attn_qkv", "IQ4_XS", 23, 2560, 10240}, {"attn_qkv", "Q4_K", 12, 2560, 10240},
    {"attn_qkv", "Q5_K", 13, 2560, 10240},   {"attn_qkv", "Q6_K", 14, 2560, 10240},
    {"attn_gate", "IQ3_S", 21, 2560, 6144},  {"attn_gate", "IQ4_XS", 23, 2560, 6144},
    {"attn_gate", "Q4_K", 12, 2560, 6144},   {"attn_gate", "Q5_K", 13, 2560, 6144},
    {"attn_gate", "Q6_K", 14, 2560, 6144},
    {"ssm_out", "IQ3_S", 21, 6144, 2560},    {"ssm_out", "IQ4_XS", 23, 6144, 2560},
    {"ssm_out", "Q4_K", 12, 6144, 2560},     {"ssm_out", "Q5_K", 13, 6144, 2560},
    {"ssm_out", "Q6_K", 14, 6144, 2560},
    {"attn_q", "IQ3_S", 21, 2560, 12288},    {"attn_q", "IQ4_XS", 23, 2560, 12288},
    {"attn_q", "Q4_K", 12, 2560, 12288},     {"attn_q", "Q6_K", 14, 2560, 12288},
    {"shexp_gate_up", "IQ3_S", 21, 2560, 640}, {"shexp_gate_up", "IQ4_XS", 23, 2560, 640},
    {"shexp_gate_up", "Q4_K", 12, 2560, 640},  {"shexp_gate_up", "Q5_K", 13, 2560, 640},
    {"shexp_gate_up", "Q6_K", 14, 2560, 640},
    {"shexp_down", "IQ4_NL", 20, 640, 2560}, {"shexp_down", "Q2_0", 42, 640, 2560},
    {"output", "Q5_K", 13, 2560, 248320},
};

int main(int argc, char** argv) {
    const size_t ws_mib = argc > 1 ? (size_t) std::atoll(argv[1]) : 1024;
    const double ms_per_case = argc > 2 ? std::atof(argv[2]) : 300.0;
    const std::string filter = argc > 3 ? argv[3] : "all";
    sycl::queue* s = &dpct::get_in_order_queue();
    const sycl::device dev = s->get_device();
    std::printf("device: %s\n", dev.get_info<sycl::info::device::name>().c_str());
    std::printf("driver: %s\n", dev.get_info<sycl::info::device::driver_version>().c_str());
    std::printf("working set: %zu MiB, %.0f ms per case\n", ws_mib, ms_per_case);
    for (const char* k : {"STRATA_MMVQ_SG", "STRATA_MMVQ_PF", "STRATA_MMVQ_WIDE_RPW", "STRATA_MMVQ_A2", "STRATA_MMVQ_WIDE_K",
                          "STRATA_MMVQ_WIDE_32", "STRATA_MMVQ_WAVE", "STRATA_MMVQ_RPW"})
        if (const char* v = std::getenv(k)) std::printf("env %s=%s\n", k, v);
    std::printf("tensor\ttype\tn_in\tn_out\tcols\tcopies\tus\tGB/s\tchecksum\n");
    for (const Case& c : kCases) {
        if (filter != "all" && filter != c.tensor && filter != c.type_name) continue;
        const size_t wbytes = strata::kernels::native_mmvq_weight_bytes(c.type, c.n_in, c.n_out);
        const size_t copies = std::max<size_t>(2, ((ws_mib << 20) + wbytes - 1) / wbytes);
        std::vector<uint8_t> hw(wbytes);
        std::vector<void*> w(copies, nullptr);
        bool ok = true;
        for (size_t k = 0; k < copies && ok; ++k) {
            // synthetic bytes; the & 0x3b keeps every fp16 scale finite (as mmvq_sg_bench does)
            for (size_t i = 0; i < wbytes; ++i) hw[i] = (uint8_t) (((i + 977 * k) * 2654435761u) >> 13) & 0x3b;
            w[k] = sycl::malloc_device(wbytes, *s);
            if (w[k] == nullptr) { ok = false; break; }
            s->memcpy(w[k], hw.data(), wbytes).wait();
        }
        if (!ok) {
            std::printf("%s\t%s\t%d\t%d\t-\t%zu\tallocation failed\n", c.tensor, c.type_name, c.n_in, c.n_out, copies);
            for (void* p : w) if (p) sycl::free(p, *s);
            continue;
        }
        for (int nc = 1; nc <= 6; ++nc) {
            std::vector<float> hx((size_t) nc * c.n_in);
            for (size_t i = 0; i < hx.size(); ++i) hx[i] = (float) ((i * 7919) % 1000) / 500.f - 1.f;
            float* x = sycl::malloc_device<float>(hx.size(), *s);
            void* xq = sycl::malloc_device(strata::kernels::native_q8_1_bytes(c.n_in, nc), *s);
            float* y = sycl::malloc_device<float>((size_t) nc * c.n_out, *s);
            s->memcpy(x, hx.data(), hx.size() * 4).wait();
            strata::kernels::native_quantize_q8_1(x, xq, c.n_in, nc, s);
            size_t k = 0;
            auto run = [&] { strata::kernels::native_mmvq(c.type, w[k], xq, y, c.n_in, c.n_out, nc, s); k = (k + 1) % copies; };
            for (size_t i = 0; i < copies; ++i) run();   // warm-up: every copy once (JIT, first touch)
            s->wait();
            long calls = 0;
            const auto t0 = std::chrono::steady_clock::now();
            double el = 0;
            do {
                for (size_t i = 0; i < copies; ++i) run();
                s->wait();
                calls += (long) copies;
                el = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
            } while (el < ms_per_case);
            const double us = el * 1e3 / (double) calls;
            std::vector<float> hy((size_t) nc * c.n_out);
            s->memcpy(hy.data(), y, hy.size() * 4).wait();
            double cs = 0;
            for (float v : hy) cs += std::isfinite(v) ? std::fabs((double) v) : 1e30;
            std::printf("%s\t%s\t%d\t%d\t%d\t%zu\t%.1f\t%.1f\t%.6e\n", c.tensor, c.type_name, c.n_in, c.n_out, nc, copies, us,
                        (double) wbytes / us / 1e3, cs);
            std::fflush(stdout);
            sycl::free(x, *s); sycl::free(xq, *s); sycl::free(y, *s);
        }
        for (void* p : w) sycl::free(p, *s);
    }
    return 0;
}
