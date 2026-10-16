// gr_split: where the time of one fused GR read (strata::kernels::fused_gr_read_multi, the hc read) goes, on the
// engine's own kernels: the norm, the down projection (with its reduce), the up projection. fused_gr_read_multi
// calls gpu_stamp(buf, i0, stream) after the norm and gpu_stamp(buf, i0 + 1, stream) after the down projection (the
// engine's profile stamps); this tool defines gpu_stamp itself as an empty kernel on a profiling queue and reads the
// marks' start times, so nothing in the engine changes. The marks between the kernels add a little time of their
// own: compare two runs (a switch on and off), and take the engine's gr_bench for the read's total.
//   gr_split [iterations=300]
// Lines: T, then microseconds per read: total (first mark to last), norm, down + reduce, up.
// Shapes are the model's (n_embd 2560, hc 4, hc_lr 320), synthetic BF16 weights, the plain read (no apply).
#include "strata/kernels/fused_gr.hpp"
#include <sycl/sycl.hpp>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

static sycl::event g_mark[2];
static sycl::event mark(sycl::queue* q) { return q->single_task([] {}); }
namespace strata::kernels {
void gpu_stamp(unsigned long long*, int i, void* stream) { g_mark[i & 1] = mark(static_cast<sycl::queue*>(stream)); }
}  // namespace strata::kernels

int main(int argc, char** argv) {
    using namespace strata::kernels;
    const int iters = argc > 1 ? std::atoi(argv[1]) : 300;
    sycl::queue q{sycl::gpu_selector_v,
                  sycl::property_list{sycl::property::queue::in_order(), sycl::property::queue::enable_profiling()}};
    sycl::queue* s = &q;
    std::printf("device: %s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
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
    unsigned long long stamp_dummy[2] = {0, 0};   // only non-null, so the read calls gpu_stamp
    auto at = [](const sycl::event& e) { return e.get_profiling_info<sycl::info::event_profiling::command_start>(); };
    std::printf("T\ttotal_us\tnorm_us\tdown_us\tup_us\n");
    for (int T = 1; T <= 6; ++T) {
        for (int i = 0; i < 50; ++i) fused_gr_read_multi(a, T, xn, s, stamp_dummy, 0);
        s->wait();
        double tot = 0, nrm = 0, dwn = 0, up = 0;
        for (int i = 0; i < iters; ++i) {
            const sycl::event b0 = mark(s);
            fused_gr_read_multi(a, T, xn, s, stamp_dummy, 0);
            sycl::event b3 = mark(s);
            b3.wait();
            const uint64_t t0 = at(b0), t1 = at(g_mark[0]), t2 = at(g_mark[1]), t3 = at(b3);
            tot += (t3 - t0) * 1e-3; nrm += (t1 - t0) * 1e-3; dwn += (t2 - t1) * 1e-3; up += (t3 - t2) * 1e-3;
        }
        std::printf("%d\t%.1f\t%.1f\t%.1f\t%.1f\n", T, tot / iters, nrm / iters, dwn / iters, up / iters);
    }
    return 0;
}
