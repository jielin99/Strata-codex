// sycl/src/kernels/gr_bench.cpp - SYCL port: time fused_gr_read_multi (norm + down + up) for 1-6 tokens on random
// weights at the Coder's shapes; prints a checksum of every output so two builds/switches can be compared bitwise.
// `gr_bench q8`: the same weights' down / up as Q8_0 (ggml's reference rounding, in the SYCL loader's split layout:
// the int8 values, then the fp16 scales) through the STRATA_HC_Q8 read. `dram` (with or without q8): 16 copies of
// the weights, each call the next one, so every read comes from memory as in the engine (96 different reads a window)
// rather than from the last-level cache the single copy stays in.
#include "strata/kernels/fused_gr.hpp"
#include <sycl/sycl.hpp>
#include <dpct/dpct.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
int main(int argc, char** argv) {
    using namespace strata::kernels;
    bool q8 = false, dram = false;
    for (int i = 1; i < argc; ++i) {
        q8 = q8 || std::strcmp(argv[i], "q8") == 0;
        dram = dram || std::strcmp(argv[i], "dram") == 0;
    }
    const int NC = dram ? 16 : 1;
    sycl::queue* s = &dpct::get_in_order_queue();
    constexpr int N = 2560, HC = 4, D = N * HC, LR = 320, TM = kFusedGrMaxT;
    auto bf16 = [](float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t) (u >> 16); };
    std::vector<uint16_t> wd((size_t) LR * D), wu((size_t) D * LR), wi((size_t) HC * D);
    uint32_t r = 12345;
    auto rnd = [&] { r = r * 1664525u + 1013904223u; return ((r >> 8) & 0xffff) / 65536.0f - 0.5f; };
    for (auto& v : wd) v = bf16(rnd() * 0.05f);
    for (auto& v : wu) v = bf16(rnd() * 0.05f);
    for (auto& v : wi) v = bf16(rnd() * 0.05f);
    std::vector<float> hR((size_t) TM * D), hn(D);
    for (auto& v : hR) v = rnd();
    for (auto& v : hn) v = 1.0f + 0.1f * rnd();
    auto dev = [&](const void* h, size_t b) { void* p = sycl::malloc_device(b, *s); s->memcpy(p, h, b).wait(); return p; };
    auto* d_wd = (uint16_t*) dev(wd.data(), wd.size() * 2);
    auto* d_wu = (uint16_t*) dev(wu.data(), wu.size() * 2);
    auto* d_wi = (uint16_t*) dev(wi.data(), wi.size() * 2);
    auto* d_R = (float*) dev(hR.data(), hR.size() * 4);
    auto* d_n = (float*) dev(hn.data(), hn.size() * 4);
    float* xn = sycl::malloc_device<float>((size_t) TM * D, *s);
    float* out = sycl::malloc_device<float>((size_t) TM * (LR + HC + HC + N), *s);
    uint8_t *d_qd = nullptr, *d_qu = nullptr;
    size_t wbytes = (wd.size() + wu.size() + wi.size()) * 2;
    if (q8) {   // Q8_0 of the BF16 values in the split layout; the outputs zeroed once (as gr_q8_parity does)
        auto q8_0 = [&](const std::vector<uint16_t>& w) {
            std::vector<uint8_t> o(w.size() / 32 * 34);
            for (size_t b = 0; b < w.size() / 32; ++b) {
                float x[32], amax = 0.0f;
                for (int j = 0; j < 32; ++j) {
                    const uint32_t u = (uint32_t) w[b * 32 + j] << 16;
                    std::memcpy(&x[j], &u, 4);
                    amax = std::max(amax, std::fabs(x[j]));
                }
                const float d = amax / 127.0f, id = d != 0.0f ? 1.0f / d : 0.0f;
                const sycl::half h = (sycl::half) d;
                std::memcpy(o.data() + w.size() + b * 2, &h, 2);
                for (int j = 0; j < 32; ++j) o[b * 32 + j] = (uint8_t) (int8_t) std::lround(x[j] * id);
            }
            return o;
        };
        const std::vector<uint8_t> qd = q8_0(wd), qu = q8_0(wu);
        d_qd = (uint8_t*) dev(qd.data(), qd.size());
        d_qu = (uint8_t*) dev(qu.data(), qu.size());
        wbytes = qd.size() + qu.size() + wi.size() * 2;
        s->memset(out, 0, (size_t) TM * (LR + HC + HC + N) * 4).wait();
    }
    std::vector<FusedGrArgs> sets((size_t) NC * TM);   // copy j's arguments at [j * TM, j * TM + TM)
    for (int j = 0; j < NC; ++j) {
        auto copy = [&](const void* p, size_t b) {
            if (j == 0 || p == nullptr) return (void*) p;
            void* c = sycl::malloc_device(b, *s);
            s->memcpy(c, p, b).wait();
            return c;
        };
        const auto* cwd = (const uint16_t*) copy(d_wd, wd.size() * 2);
        const auto* cwu = (const uint16_t*) copy(d_wu, wu.size() * 2);
        const auto* cwi = (const uint16_t*) copy(d_wi, wi.size() * 2);
        const auto* cqd = (const uint8_t*) copy(d_qd, wd.size() / 32 * 34);
        const auto* cqu = (const uint8_t*) copy(d_qu, wu.size() / 32 * 34);
        for (int t = 0; t < TM; ++t) {
            FusedGrArgs& x = sets[(size_t) j * TM + t];
            float* o = out + (size_t) t * (LR + HC + HC + N);
            x.R = d_R + (size_t) t * D; x.w_norm = d_n; x.w_down = cwd; x.w_up = cwu; x.w_inject = cwi;
            x.lo = o; x.rs = o + LR; x.inject_out = o + LR + HC; x.mixed = o + LR + 2 * HC;
            x.q8_down = cqd; x.q8_up = cqu;
        }
    }
    auto a = [&](int i) { return sets.data() + (size_t) (i % NC) * TM; };
    for (int T = 1; T <= 6; ++T) {
        const auto w0 = std::chrono::steady_clock::now();
        while (std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - w0).count() < 150) {
            for (int i = 0; i < 20; ++i) fused_gr_read_multi(a(i), T, xn, s);
            s->wait();
        }
        const int it = 500;
        const auto t0 = std::chrono::steady_clock::now();
        for (int i = 0; i < it; ++i) fused_gr_read_multi(a(i), T, xn, s);
        s->wait();
        const double us = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count() / it;
        std::vector<float> h((size_t) T * (LR + HC + HC + N));
        s->memcpy(h.data(), out, h.size() * 4).wait();
        uint64_t cs = 1469598103934665603ull;
        double sum = 0;
        for (float v : h) { uint32_t u; std::memcpy(&u, &v, 4); cs = (cs ^ u) * 1099511628211ull; sum += v; }
        std::printf("fused GR read%s%s, %d tokens: %7.1f us (%.0f GB/s of weights)  checksum %016llx  sum %.9e\n",
                    q8 ? " (Q8_0)" : "", dram ? " (16 copies)" : "", T, us, wbytes / us / 1e3, (unsigned long long) cs,
                    sum);
    }
    return 0;
}
