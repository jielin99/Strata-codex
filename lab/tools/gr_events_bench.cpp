// gr_events_bench: each kernel's own execution time in one fused GR read (strata::kernels::fused_gr_read_multi, the
// hc read), from the events that lab/tools/gr_events.py makes the read record (compile its copy of fused_gr.dp.cpp
// in place of the engine's; see lab/plans for the command lines).
//   gr_events_bench [iterations=300]
// Lines: T, the read's span on the GPU (first kernel's start to last kernel's end), then each kernel's mean execution
// time in submission order (the default read: norm, down, reduce, up), and what the span has beyond their sum (the
// gaps between kernels on the GPU), and how many of the iterations were left out of those means because an event's
// timestamps were not in order or not plausible (end before start, or a span over 1 s). Microseconds. Shapes are the model's (n_embd 2560, hc 4, hc_lr 320), synthetic
// BF16 weights, the plain read (no apply). The engine's STRATA_GR_* switches apply as usual.
#include "strata/kernels/fused_gr.hpp"
#include <sycl/sycl.hpp>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace strata::kernels {
extern sycl::event g_lab_ev[16];
extern int g_lab_nev;
void gpu_stamp(unsigned long long*, int, void*) {}   // the engine's profile stamps; never called here
}  // namespace strata::kernels

int main(int argc, char** argv) {
    using namespace strata::kernels;
    const int iters = argc > 1 && std::atoi(argv[1]) > 0 ? std::atoi(argv[1]) : 300;
    sycl::queue q{sycl::gpu_selector_v,
                  sycl::property_list{sycl::property::queue::in_order(), sycl::property::queue::enable_profiling()}};
    sycl::queue* s = &q;
    std::printf("device: %s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    for (const char* k : {"STRATA_GR_UP_EPI", "STRATA_GR_DOWN_V2", "STRATA_GR_DOWN_ROWS", "STRATA_GR_DOWN_SLICED",
                          "STRATA_GR_NORM_SPLIT", "STRATA_GR_V3", "STRATA_GR_RED_BATCH", "STRATA_GR_UP_TREE"})
        if (const char* v = std::getenv(k)) std::printf("env %s=%s\n", k, v);
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
    FusedGrArgs a[TM];
    for (int t = 0; t < TM; ++t) {
        float* o = out + (size_t) t * (LR + HC + HC + N);
        a[t].R = d_R + (size_t) t * D; a[t].w_norm = d_n; a[t].w_down = d_wd; a[t].w_up = d_wu; a[t].w_inject = d_wi;
        a[t].lo = o; a[t].rs = o + LR; a[t].inject_out = o + LR + HC; a[t].mixed = o + LR + 2 * HC;
    }
    auto t_ns = [](const sycl::event& e, bool end) {
        return end ? e.get_profiling_info<sycl::info::event_profiling::command_end>()
                   : e.get_profiling_info<sycl::info::event_profiling::command_start>();
    };
    std::printf("T\tspan_us\tkernels\tk0_us\tk1_us\tk2_us\tk3_us\tk4_us\tgaps_us\tbad\n");
    for (int T = 1; T <= 6; ++T) {
        for (int i = 0; i < 50; ++i) fused_gr_read_multi(a, T, xn, s);
        s->wait();
        double span = 0, k[16] = {};
        int nk = -1, good = 0, bad = 0;
        for (int i = 0; i < iters; ++i) {
            g_lab_nev = 0;
            fused_gr_read_multi(a, T, xn, s);
            s->wait();
            if (nk < 0) nk = g_lab_nev;
            if (g_lab_nev != nk || nk == 0) { std::printf("%d\tkernel count changed (%d, %d)\n", T, nk, g_lab_nev); return 1; }
            // an iteration counts only when every timestamp is in order and the span is under 1 s (one bad timestamp
            // in 300 once made a span of 6e13 us)
            const uint64_t s0 = t_ns(g_lab_ev[0], false), e1 = t_ns(g_lab_ev[nk - 1], true);
            bool ok = e1 >= s0 && e1 - s0 < 1000000000ull;
            for (int j = 0; j < nk; ++j) ok = ok && t_ns(g_lab_ev[j], true) >= t_ns(g_lab_ev[j], false);
            if (!ok) { ++bad; continue; }
            for (int j = 0; j < nk; ++j) k[j] += (t_ns(g_lab_ev[j], true) - t_ns(g_lab_ev[j], false)) * 1e-3;
            span += (e1 - s0) * 1e-3;
            ++good;
        }
        if (good == 0) { std::printf("%d\tno iteration with plausible timestamps\n", T); return 1; }
        double sum = 0;
        std::printf("%d\t%.1f\t%d", T, span / good, nk);
        for (int j = 0; j < 5; ++j) {
            if (j < nk) { std::printf("\t%.1f", k[j] / good); sum += k[j] / good; }
            else std::printf("\t-");
        }
        for (int j = 5; j < nk; ++j) sum += k[j] / good;
        std::printf("\t%.1f\t%d\n", span / good - sum, bad);
    }
    return 0;
}
