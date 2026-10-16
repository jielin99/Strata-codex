// gr_apply_parity: one fused GR read (strata::kernels::fused_gr_read_multi, the hc read) per case from the same
// inputs, printing a hash of every output, so two runs (for example STRATA_GR_UP_EPI unset and =1) can be compared
// bit for bit with `fc`. The engine's gr_bench prints checksums too, but only of the plain read (no previous-half
// write folded in, never in place); here the cases are what verify.cpp passes:
//   apply 0/1   - fold the previous half's write (bo_prev, inj_prev) into R, written back in place (R_out == R)
//   inject 0/1  - with the inject rows (a block's read) or without (the final mixer)
//   T 1..kFusedGrMaxT tokens
// Shapes are the model's (n_embd 2560, hc 4, hc_lr 320); weights and inputs are synthetic, BF16 as in the GGUF.
// Lines: "apply A inject I T n  outputs <hash of lo, rs, inject_out, mixed>  R <hash of R after the read>".
// Built against the engine's fused_gr.dp.cpp (see lab/plans for the command line); it changes no engine file.
#include "strata/kernels/fused_gr.hpp"
#include <sycl/sycl.hpp>
#include <dpct/dpct.hpp>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>

// the engine's profile stamps live in verify_kernels.dp.cpp; this tool never passes a stamp buffer
namespace strata::kernels { void gpu_stamp(unsigned long long*, int, void*) {} }

int main() {
    using namespace strata::kernels;
    sycl::queue* s = &dpct::get_in_order_queue();
    std::printf("device: %s\n", s->get_device().get_info<sycl::info::device::name>().c_str());
    constexpr int N = 2560, HC = 4, D = N * HC, LR = 320, TM = kFusedGrMaxT;
    auto bf16 = [](float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t) (u >> 16); };
    std::vector<uint16_t> wd((size_t) LR * D), wu((size_t) D * LR), wi((size_t) HC * D);
    uint32_t r = 777;
    auto rnd = [&] { r = r * 1664525u + 1013904223u; return ((r >> 8) & 0xffff) / 65536.0f - 0.5f; };
    for (auto& v : wd) v = bf16(rnd() * 0.05f);
    for (auto& v : wu) v = bf16(rnd() * 0.05f);
    for (auto& v : wi) v = bf16(rnd() * 0.05f);
    std::vector<float> hR((size_t) TM * D), hn(D), hbo((size_t) TM * N), hip((size_t) TM * HC);
    for (auto& v : hR) v = rnd() * 4.0f;
    for (auto& v : hn) v = 1.0f + 0.1f * rnd();
    for (auto& v : hbo) v = rnd();
    for (auto& v : hip) v = rnd() * 3.0f;
    auto dev = [&](const void* h, size_t b) { void* p = sycl::malloc_device(b, *s); s->memcpy(p, h, b).wait(); return p; };
    auto* d_wd = (uint16_t*) dev(wd.data(), wd.size() * 2);
    auto* d_wu = (uint16_t*) dev(wu.data(), wu.size() * 2);
    auto* d_wi = (uint16_t*) dev(wi.data(), wi.size() * 2);
    auto* d_R = (float*) dev(hR.data(), hR.size() * 4);
    auto* d_n = (float*) dev(hn.data(), hn.size() * 4);
    auto* d_bo = (float*) dev(hbo.data(), hbo.size() * 4);
    auto* d_ip = (float*) dev(hip.data(), hip.size() * 4);
    float* xn = sycl::malloc_device<float>((size_t) TM * D, *s);
    const size_t per = LR + HC + HC + N;
    float* out = sycl::malloc_device<float>((size_t) TM * per, *s);
    for (int mode = 0; mode < 4; ++mode) {   // bit 0: apply (in place), bit 1: inject rows
        for (int T = 1; T <= TM; ++T) {
            s->memcpy(d_R, hR.data(), hR.size() * 4).wait();
            s->memset(out, 0, (size_t) TM * per * 4).wait();
            FusedGrArgs a[TM];
            for (int t = 0; t < T; ++t) {
                float* o = out + (size_t) t * per;
                a[t].R = d_R + (size_t) t * D;
                a[t].R_out = (mode & 1) ? d_R + (size_t) t * D : nullptr;   // in place, as verify.cpp passes it
                a[t].apply = (mode & 1) != 0;
                a[t].bo_prev = d_bo + (size_t) t * N;
                a[t].inj_prev = d_ip + (size_t) t * HC;
                a[t].w_norm = d_n; a[t].w_down = d_wd; a[t].w_up = d_wu;
                a[t].w_inject = (mode & 2) ? d_wi : nullptr;
                a[t].lo = o; a[t].rs = o + LR; a[t].inject_out = o + LR + HC; a[t].mixed = o + LR + 2 * HC;
            }
            fused_gr_read_multi(a, T, xn, s);
            s->wait();
            std::vector<float> h((size_t) T * per), hr((size_t) T * D);
            s->memcpy(h.data(), out, h.size() * 4).wait();
            s->memcpy(hr.data(), d_R, hr.size() * 4).wait();
            uint64_t cs = 1469598103934665603ull, cr = cs;   // FNV-1a over the float bits
            for (float v : h) { uint32_t u; std::memcpy(&u, &v, 4); cs = (cs ^ u) * 1099511628211ull; }
            for (float v : hr) { uint32_t u; std::memcpy(&u, &v, 4); cr = (cr ^ u) * 1099511628211ull; }
            std::printf("apply %d inject %d T %d  outputs %016llx  R %016llx\n", mode & 1, (mode >> 1) & 1, T,
                        (unsigned long long) cs, (unsigned long long) cr);
        }
    }
    return 0;
}
