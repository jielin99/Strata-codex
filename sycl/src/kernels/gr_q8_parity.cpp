// sycl/src/kernels/gr_q8_parity.cpp - SYCL port: checks the STRATA_HC_Q8 read (fused_gr_read_multi with Q8_0 down /
// up projections) for 1-8 tokens, with and without the pending write, with the inject rows as BF16 (the layers'
// reads), as a Q8_0 copy (STRATA_HC_Q8_INJECT=1) or absent (the final mixer's read), at the model's shapes:
//   same:  Q8_0 blocks whose scale is a power of two, so every weight is BF16-exact: the BF16 read and the Q8_0 read
//          take the same weights and differ only in their summation order;
//   ref:   ordinary Q8_0 blocks against a double-precision transcription of the read on the dequantized weights.
// Prints the largest error of every output (mixed, inject, rs, lo, the written R) relative to that output's largest
// magnitude; exit 1 above the bound.
#include "strata/kernels/fused_gr.hpp"
#include <sycl/sycl.hpp>
#include <dpct/dpct.hpp>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

namespace {
constexpr int N = 2560, HC = 4, D = N * HC, LR = 320, TM = strata::kernels::kFusedGrMaxT;
constexpr double kBound = 1e-4;   // float sums over 10,240 / 320 terms in another order: ~1e-6 expected

uint32_t g_r = 12345;
float rnd() { g_r = g_r * 1664525u + 1013904223u; return ((g_r >> 8) & 0xffff) / 65536.0f - 0.5f; }
float bf16f(uint16_t b) { const uint32_t u = (uint32_t) b << 16; float f; std::memcpy(&f, &u, 4); return f; }
uint16_t bf16b(float f) { uint32_t u; std::memcpy(&u, &f, 4); return (uint16_t) (u >> 16); }   // exact values only

// rows x cols Q8_0 (blocks along cols) and its dequantized values; pow2: block scales 2^-12..2^-9 (BF16-exact values)
void make_q8(int rows, int cols, bool pow2, std::vector<uint8_t>& q8, std::vector<float>& deq) {
    q8.assign((size_t) rows * cols / 32 * 34, 0);
    deq.assign((size_t) rows * cols, 0.0f);
    for (size_t b = 0; b < (size_t) rows * cols / 32; ++b) {
        const float d = pow2 ? std::ldexp(1.0f, -9 - (int) (g_r % 4)) : (0.4f + std::fabs(rnd())) * 4e-4f;
        rnd();
        const sycl::half h = (sycl::half) d;
        const float dh = (float) h;
        std::memcpy(q8.data() + b * 34, &h, 2);
        for (int j = 0; j < 32; ++j) {
            const int q = (int) std::lround(rnd() * 254.0f);   // -127..127
            q8[b * 34 + 2 + j] = (uint8_t) (int8_t) q;
            deq[b * 32 + j] = dh * (float) q;
        }
    }
}

struct Out { std::vector<float> mixed, inject, rs, lo, R; };

// the read in double: R' = R + gw bo (pending write), per-stream RMS, xn = R' w_norm rs, lo = silu(down xn / HC),
// inject = inject_rows xn, mixed = mean over streams of xn * sigmoid(up lo)
void reference(const std::vector<float>& R, const std::vector<float>& wn, const std::vector<float>& wd,
               const std::vector<float>& wu, const std::vector<float>& wi, bool apply, const std::vector<float>& bo,
               const std::vector<float>& ip, float eps, Out& o) {
    std::vector<double> r(D), xn(D);
    for (int i = 0; i < D; ++i) {
        const int c = i / N;
        const double gw = apply ? 2.0 / (1.0 + std::exp(-(double) ip[c] / HC)) : 0.0;
        r[i] = (double) R[i] + (apply ? (double) bo[i - c * N] * gw : 0.0);
    }
    o.rs.assign(HC, 0.0f);
    for (int c = 0; c < HC; ++c) {
        double ss = 0;
        for (int d = 0; d < N; ++d) ss += r[c * N + d] * r[c * N + d];
        const double rs = 1.0 / std::sqrt(ss / N + eps);
        o.rs[c] = (float) rs;
        for (int d = 0; d < N; ++d) xn[c * N + d] = r[c * N + d] * wn[c * N + d] * rs;
    }
    std::vector<double> lo(LR);
    for (int k = 0; k < LR; ++k) {
        double a = 0;
        for (int i = 0; i < D; ++i) a += (double) wd[(size_t) k * D + i] * xn[i];
        const double x = a / HC;
        lo[k] = x / (1.0 + std::exp(-x));
    }
    o.lo.assign(lo.begin(), lo.end());
    o.inject.assign(HC, 0.0f);
    for (int c = 0; c < HC; ++c) {
        double a = 0;
        for (int i = 0; i < D; ++i) a += (double) wi[(size_t) c * D + i] * xn[i];
        o.inject[c] = (float) a;
    }
    o.mixed.assign(N, 0.0f);
    for (int d = 0; d < N; ++d) {
        double m = 0;
        for (int c = 0; c < HC; ++c) {
            const int i = c * N + d;
            double g = 0;
            for (int k = 0; k < LR; ++k) g += (double) wu[(size_t) i * LR + k] * lo[k];
            m += xn[i] / (1.0 + std::exp(-g));
        }
        o.mixed[d] = (float) (m / HC);
    }
    o.R.assign(D, 0.0f);
    for (int i = 0; i < D; ++i) o.R[i] = (float) r[i];
}

double rel_err(const std::vector<float>& want, const std::vector<float>& got) {
    double mag = 0, err = 0;
    for (size_t i = 0; i < want.size(); ++i) {
        mag = std::max(mag, std::fabs((double) want[i]));
        err = std::max(err, std::fabs((double) want[i] - (double) got[i]));
        if (!std::isfinite(got[i])) return INFINITY;
    }
    return mag > 0 ? err / mag : err;
}
}  // namespace

int main() {
    using namespace strata::kernels;
    sycl::queue* s = &dpct::get_in_order_queue();
    auto dev = [&](const void* h, size_t b) { void* p = sycl::malloc_device(b, *s); s->memcpy(p, h, b).wait(); return p; };
    int fails = 0;
    for (const bool pow2 : {true, false}) {
        std::vector<uint8_t> qd, qu;
        std::vector<float> fd, fu;
        make_q8(LR, D, pow2, qd, fd);
        make_q8(D, LR, pow2, qu, fu);
        std::vector<uint8_t> qi;
        std::vector<float> fiq;   // the inject rows' Q8_0 values; the BF16 copy below is them truncated (exact when pow2)
        make_q8(HC, D, pow2, qi, fiq);
        std::vector<float> fib(fiq.size()), wn(D), R((size_t) TM * D), bo((size_t) TM * N), ip((size_t) TM * HC);
        std::vector<uint16_t> bd(fd.size()), bu(fu.size()), bi(fiq.size());
        for (size_t i = 0; i < fiq.size(); ++i) { bi[i] = bf16b(fiq[i]); fib[i] = bf16f(bi[i]); }
        for (size_t i = 0; i < bd.size(); ++i) bd[i] = bf16b(fd[i]);   // exact only when pow2 (the `same` check)
        for (size_t i = 0; i < bu.size(); ++i) bu[i] = bf16b(fu[i]);
        for (auto& v : wn) v = 1.0f + 0.1f * rnd();
        for (auto& v : R) v = rnd();
        for (auto& v : bo) v = rnd();
        for (auto& v : ip) v = rnd();
        auto split = [](const std::vector<uint8_t>& blk) {   // the SYCL loader's layout: int8 values, then fp16 scales
            const size_t nb = blk.size() / 34;
            std::vector<uint8_t> o(blk.size());
            for (size_t b = 0; b < nb; ++b) {
                std::memcpy(o.data() + b * 32, blk.data() + b * 34 + 2, 32);
                std::memcpy(o.data() + nb * 32 + b * 2, blk.data() + b * 34, 2);
            }
            return o;
        };
        const std::vector<uint8_t> sd = split(qd), su = split(qu), si = split(qi);
        auto* d_qd = (uint8_t*) dev(sd.data(), sd.size());
        auto* d_qu = (uint8_t*) dev(su.data(), su.size());
        auto* d_qi = (uint8_t*) dev(si.data(), si.size());
        auto* d_bd = (uint16_t*) dev(bd.data(), bd.size() * 2);
        auto* d_bu = (uint16_t*) dev(bu.data(), bu.size() * 2);
        auto* d_bi = (uint16_t*) dev(bi.data(), bi.size() * 2);
        auto* d_wn = (float*) dev(wn.data(), wn.size() * 4);
        auto* d_bo = (float*) dev(bo.data(), bo.size() * 4);
        auto* d_ip = (float*) dev(ip.data(), ip.size() * 4);
        float* d_R = sycl::malloc_device<float>((size_t) TM * D, *s);
        float* xn = sycl::malloc_device<float>((size_t) TM * D, *s);
        constexpr int OW = LR + HC + HC + N;   // lo, rs, inject, mixed
        float* out = sycl::malloc_device<float>((size_t) TM * OW, *s);
        for (const int inj : {0, 1, 2}) {   // the inject rows: BF16, Q8_0 copy, absent
        for (const bool apply : {false, true}) {
            for (int T = 1; T <= TM; ++T) {
                // run: q8 = false the BF16 read, true the Q8_0 read; returns rs, inject, mixed and R per token
                auto run = [&](bool q8, std::vector<Out>& res) {
                    s->memcpy(d_R, R.data(), R.size() * 4).wait();
                    s->memset(out, 0, (size_t) TM * OW * 4).wait();
                    FusedGrArgs a[TM];
                    for (int t = 0; t < T; ++t) {
                        float* o = out + (size_t) t * OW;
                        a[t].R = d_R + (size_t) t * D; a[t].R_out = d_R + (size_t) t * D; a[t].apply = apply;
                        a[t].bo_prev = d_bo + (size_t) t * N; a[t].inj_prev = d_ip + (size_t) t * HC;
                        a[t].w_norm = d_wn; a[t].w_down = d_bd; a[t].w_up = d_bu; a[t].w_inject = inj < 2 ? d_bi : nullptr;
                        a[t].q8_down = q8 ? d_qd : nullptr; a[t].q8_up = q8 ? d_qu : nullptr;
                        a[t].q8_inject = q8 && inj == 1 ? d_qi : nullptr;
                        a[t].eps = 1e-6f;
                        a[t].lo = o; a[t].rs = o + LR; a[t].inject_out = o + LR + HC; a[t].mixed = o + LR + 2 * HC;
                    }
                    fused_gr_read_multi(a, T, xn, s);
                    s->wait();
                    std::vector<float> h((size_t) TM * OW), hr((size_t) TM * D);
                    s->memcpy(h.data(), out, h.size() * 4).wait();
                    s->memcpy(hr.data(), d_R, hr.size() * 4).wait();
                    res.assign(T, Out{});
                    for (int t = 0; t < T; ++t) {
                        const float* o = h.data() + (size_t) t * OW;
                        res[t].rs.assign(o + LR, o + LR + HC);
                        res[t].inject.assign(o + LR + HC, o + LR + 2 * HC);
                        res[t].mixed.assign(o + LR + 2 * HC, o + OW);
                        res[t].lo.assign(o, o + LR);
                        res[t].R.assign(hr.begin() + (size_t) t * D, hr.begin() + (size_t) (t + 1) * D);
                    }
                };
                std::vector<Out> q8, want;
                run(true, q8);
                if (pow2) {
                    run(false, want);
                } else {
                    want.resize(T);
                    for (int t = 0; t < T; ++t) {
                        const std::vector<float> Rt(R.begin() + (size_t) t * D, R.begin() + (size_t) (t + 1) * D);
                        const std::vector<float> bt(bo.begin() + (size_t) t * N, bo.begin() + (size_t) (t + 1) * N);
                        const std::vector<float> it(ip.begin() + (size_t) t * HC, ip.begin() + (size_t) (t + 1) * HC);
                        reference(Rt, wn, fd, fu, inj == 1 ? fiq : fib, apply, bt, it, 1e-6f, want[t]);
                    }
                }
                double em = 0, ei = 0, er = 0, el = 0, eR = 0;
                for (int t = 0; t < T; ++t) {
                    em = std::max(em, rel_err(want[t].mixed, q8[t].mixed));
                    if (inj < 2) ei = std::max(ei, rel_err(want[t].inject, q8[t].inject));
                    er = std::max(er, rel_err(want[t].rs, q8[t].rs));
                    el = std::max(el, rel_err(want[t].lo, q8[t].lo));
                    if (apply) eR = std::max(eR, rel_err(want[t].R, q8[t].R));
                }
                const bool ok = em <= kBound && ei <= kBound && er <= kBound && el <= kBound && eR <= kBound;
                fails += ok ? 0 : 1;
                std::printf("%s %s inj=%s T=%d: mixed %.2e inject %.2e rs %.2e lo %.2e R %.2e %s\n", pow2 ? "same" : "ref ",
                            apply ? "apply" : "plain", inj == 0 ? "bf16" : inj == 1 ? "q8" : "none", T, em, ei, er, el,
                            eR, ok ? "ok" : "FAIL");
            }
        }
        }
        for (void* p : {(void*) d_qd, (void*) d_qu, (void*) d_qi, (void*) d_bd, (void*) d_bu, (void*) d_bi, (void*) d_wn, (void*) d_bo,
                        (void*) d_ip, (void*) d_R, (void*) xn, (void*) out})
            sycl::free(p, *s);
    }
    std::printf("gr_q8_parity: %d failures\n", fails);
    return fails ? 1 : 0;
}
