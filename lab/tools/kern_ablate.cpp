// kern_ablate: where the time goes inside three of the engine's decode kernels on this GPU. Each kernel is copied
// here, specialized to the shapes below (`base`: the engine's expressions in the engine's order), and timed next to
// copies with one step taken out, and next to two candidate rewrites.
//   kern_ablate [rounds=3] [launches per measurement=100]
// Parts (shapes of the IQ3_XXS model; synthetic weights):
//   moe  the expert gate/up kernel's single-entry path (native_gu_kernel<TY, 8> -> row_entries -> row_dot_lanes ->
//        vec_dot_iq3_s_q8_1 / vec_dot_iq2_xxs_q8_1) for IQ3_S (21) and IQ2_XXS (16): 25 experts x 1 entry (entry g
//        reads token g % 4), 1280 rows each (gate | up), 2560 wide; the group loop and entry batching are left out.
//   q4k  the wide Q4_K GEMV (native_mmvq_wide_kernel<WideQ4K, N>), 2560 -> 10240, N = 1..4 columns.
//   q6k  the wide Q6_K GEMV with aligned loads and the SWAR unpack (the STRATA_MMVQ_Q6_SWAR=1 kernel), 2560 -> 10240,
//        N = 1..4 columns.
// Variants:
//   base    the copy; `same` = 1 when its output is bitwise the engine call's for every weight copy (run the tool with
//           STRATA_MMVQ_Q6_SWAR=1 and no other STRATA_* dispatch switch, so the engine calls take the copied kernels)
//   nogrid  moe: each codebook value computed from its index (index x 0x01010101) instead of looked up
//   nosign  moe: the codebook values used without the sign step
//   noact   no activation loads: each activation quant word is a weight word already in registers xor a salt
//           (a kernel argument, one per column), each activation scale a salt float; the arithmetic stays, the columns
//           differ (so the compiler cannot merge them) and nothing new is held per lane
//   now     no weight loads: the raw weight fields (quants, scale bytes, fp16 scales) made in registers from the
//           block's address, the step and a salt, then decoded with the same expressions (the codebook lookups stay,
//           on indices made that way)
//   noones  q4k: without the dp4a with ones (the activation sums) and the min terms
//   slm     moe candidate: the codebook staged in local memory once per work-group; `same` = bitwise base
//   pf2/pf4 q6k candidate: each sub-group issues the weight loads of 2 / 4 steps before their dots; `same` = bitwise base
//   engine  the engine's own call (moe: native_expert_grouped's gate/up phase, which also runs SwiGLU + q8_1;
//           q4k/q6k: native_mmvq), timed from the end of a marker kernel before it to the start of one after it
// The ablated variants compute something else; their outputs are not compared (`same` = -).
// Time: the copies' kernel start to end from the queue's profiling events (the engine: marker to marker, so it
// includes the gaps between its kernels); each measurement submits the launches back to back with one wait at the
// end; the median over the launches of a round, then the median over the rounds (the variants' order rotates from
// round to round); `spread` = (max - min) / median of the rounds. GB/s = base's weight bytes per launch / time, for
// every variant: an equivalent rate for comparing them, not the DRAM traffic. The launches rotate over weight copies
// that together exceed the GPU's caches. Use the numbers to compare variants with `base`, not as the engine's time.
// Built against the engine's kernels (see lab/plans for the command line); it changes no engine file.
#include "strata/kernels/iq_kernels.hpp"
#include "strata/kernels/native_mmvq.hpp"
#include "strata/sycl_math.hpp"
#include <sycl/sycl.hpp>
#include <dpct/dpct.hpp>
#define GGML_COMMON_DECL_SYCL
#define GGML_COMMON_IMPL_SYCL
#include "ggml-common.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <random>
#include <string>
#include <vector>

namespace k = strata::kernels;

enum Var { BASE, NOGRID, NOSIGN, NOACT, NOW, NOONES, SLM, PF2, PF4 };
static const char* var_name(int v) {
    static const char* n[] = {"base", "nogrid", "nosign", "noact", "now", "noones", "slm", "pf2", "pf4"};
    return n[v];
}

// ------------------------------------------------------------ copies of iq_kernels.dp.cpp's helpers (STRATA_SWAR=1)
namespace cp {
inline int get_int_b2(const void* x, const int& i32) {
    const uint16_t* x16 = (const uint16_t*) x;
    int x32 = x16[2 * i32 + 0] << 0;
    x32 |= x16[2 * i32 + 1] << 16;
    return x32;
}
inline int get_int_b4(const void* x, const int& i32) { return ((const int*) x)[i32]; }
inline uint32_t unpack_ksigns(const uint8_t v) {
    const uint32_t p = sycl::popcount(v) & 1;
    const uint32_t s = v ^ p << 7;
    return s * 0x01010101;
}
inline int swar_ne4(unsigned x) {
    x = (x | (x >> 4)) & 0x0F0F0F0Fu;
    x = (x | (x >> 2)) & 0x03030303u;
    x = (x | (x >> 1)) & 0x01010101u;
    return (int) (x * 0xFFu);
}
// `noact` / `now`: values standing in for loaded ones, made from kernel arguments (the salts: runtime values the
// compiler cannot fold, the same in every lane, so they cost no per-lane registers) and values already in registers,
// with one or two integer operations each (unsigned arithmetic only)
struct Salt { uint32_t w[8]; float f[4]; };
inline uint32_t seed_of(const void* p, int i, int j, uint32_t salt) {   // differs by row (the address), step, lane
    return ((uint32_t) reinterpret_cast<uintptr_t>(p) + (uint32_t) i * 0x9E3779B1u + (uint32_t) j * 0x85EBCA77u) ^ salt;
}
inline sycl::half fake_half(uint32_t x) {   // finite: exponent 8 (2^-7 .. 2^-6), either sign
    return sycl::bit_cast<sycl::half>((uint16_t) (0x2000u | (x & 0x83FFu)));
}
inline int swar_sub4(unsigned a, unsigned s) { return (int) (((a & 0x7F7F7F7Fu) + (s & 0x01010101u)) ^ (a & 0x80808080u)); }
template <int LANES>
inline float lanes_sum(float v) {
#pragma unroll
    for (int o = LANES / 2; o > 0; o >>= 1)
        v += dpct::experimental::permute_sub_group_by_xor(0xffffffffu, sycl::ext::oneapi::this_work_item::get_sub_group(), v, o);
    return v;
}

// vec_dot_iq3_s_q8_1 with the variants; G: the codebook in local memory (SLM) or nullptr (iq3s_grid)
template <int A>
inline float dot21(const void* __restrict__ vbq, const block_q8_1* __restrict__ bq8_1, const int& kbx, const int& iqs,
                   const uint32_t* G, const Salt& sl) {
    const block_iq3_s* bq3 = (const block_iq3_s*) vbq + kbx;
    sycl::int2 qs_packed;
    int qh, signs_packed_32, sc;
    float dw;
    if constexpr (A == NOW) {
        const uint32_t x = seed_of(vbq, kbx, iqs, sl.w[0]);
        qs_packed = sycl::int2((int) x, (int) (x ^ sl.w[1]));
        qh = (int) ((x >> 7) & 0xFFu);
        signs_packed_32 = (int) (x ^ sl.w[2]);
        sc = (int) ((x >> 13) & 0xFFu);
        dw = sycl::vec<sycl::half, 1>(fake_half(x >> 3)).convert<float, sycl::rounding_mode::automatic>()[0];
    } else {
        qs_packed = sycl::int2(get_int_b2(bq3->qs, iqs + 0), get_int_b2(bq3->qs, iqs + 1));
        qh = bq3->qh[iqs / 2];
        signs_packed_32 = get_int_b2(bq3->signs, iqs / 2);
        sc = bq3->scales[iqs / 4];
        dw = sycl::vec<sycl::half, 1>(bq3->d).convert<float, sycl::rounding_mode::automatic>()[0];
    }
    const uint8_t* qs = (const uint8_t*) &qs_packed;
    const uint8_t* signs_packed_8 = (const uint8_t*) &signs_packed_32;
    int sumi = 0;
#pragma unroll
    for (int l0 = 0; l0 < 8; l0 += 2) {
        const int i0 = qs[l0 + 0] | ((qh << (8 - l0)) & 0x100), i1 = qs[l0 + 1] | ((qh << (7 - l0)) & 0x100);
        sycl::int2 grid_pos;
        if constexpr (A == NOGRID) grid_pos = sycl::int2((int) ((uint32_t) i0 * 0x01010101u), (int) ((uint32_t) i1 * 0x01010101u));
        else if constexpr (A == SLM) grid_pos = sycl::int2(G[i0], G[i1]);
        else grid_pos = sycl::int2(iq3s_grid[i0], iq3s_grid[i1]);
        int grid_l, grid_h;
        if constexpr (A == NOSIGN) {
            grid_l = grid_pos.x();
            grid_h = grid_pos.y();
        } else {
            const int signs0 = swar_ne4(((signs_packed_8[l0 / 2] & 0x03) << 7) | ((signs_packed_8[l0 / 2] & 0x0C) << 21));
            const int signs1 = swar_ne4(((signs_packed_8[l0 / 2] & 0x30) << 3) | ((signs_packed_8[l0 / 2] & 0xC0) << 17));
            grid_l = swar_sub4(grid_pos.x() ^ signs0, signs0);
            grid_h = swar_sub4(grid_pos.y() ^ signs1, signs1);
        }
        int u0, u1;
        if constexpr (A == NOACT) { u0 = grid_l ^ (int) sl.w[4]; u1 = grid_h ^ (int) sl.w[5]; }
        else { u0 = get_int_b4(bq8_1[iqs / 2].qs, l0 + 0); u1 = get_int_b4(bq8_1[iqs / 2].qs, l0 + 1); }
        sumi = strata::dp4a(grid_l, u0, sumi);
        sumi = strata::dp4a(grid_h, u1, sumi);
    }
    sumi *= 1 + 2 * ((sc >> ((iqs << 1) & 0x04)) & 0x0F);
    const float ds = A == NOACT ? sl.f[0] : (float) bq8_1[iqs / 2].ds[0];
    const float d = dw * ds;
    return d * sumi;
}

// vec_dot_iq2_xxs_q8_1 with the variants; G: the codebook in local memory or nullptr (iq2xxs_grid)
template <int A>
inline float dot16(const void* __restrict__ vbq, const block_q8_1* __restrict__ bq8_1, const int& kbx, const int& iqs,
                   const uint64_t* G, const Salt& sl) {
    const block_iq2_xxs* bq2 = (const block_iq2_xxs*) vbq + kbx;
    int q2;
    uint32_t aux32;
    float dw;
    if constexpr (A == NOW) {
        const uint32_t x = seed_of(vbq, kbx, iqs, sl.w[0]);
        q2 = (int) x;
        aux32 = x ^ sl.w[1];
        dw = sycl::vec<sycl::half, 1>(fake_half(x >> 3)).convert<float, sycl::rounding_mode::automatic>()[0];
    } else {
        q2 = get_int_b2(bq2->qs, iqs);
        aux32 = get_int_b2(bq2->qs, iqs + 1);
        dw = sycl::vec<sycl::half, 1>(bq2->d).convert<float, sycl::rounding_mode::automatic>()[0];
    }
    const uint8_t* aux8 = (const uint8_t*) &q2;
    int sumi = 0;
#pragma unroll
    for (int k0 = 0; k0 < 8; k0 += 2) {
        sycl::uint2 grid_pos;
        if constexpr (A == NOGRID) {
            const uint32_t v = (uint32_t) aux8[k0 / 2] * 0x01010101u;
            grid_pos = sycl::uint2(v, v ^ 0x5A5A5A5Au);
        } else if constexpr (A == SLM) {
            grid_pos = ((const sycl::uint2*) G)[aux8[k0 / 2]];
        } else {
            grid_pos = ((const sycl::uint2*) iq2xxs_grid)[aux8[k0 / 2]];
        }
        int grid0, grid1;
        if constexpr (A == NOSIGN) {
            grid0 = (int) grid_pos.x();
            grid1 = (int) grid_pos.y();
        } else {
            const uint32_t signs = unpack_ksigns(aux32 >> (7 * k0 / 2));
            const int signs0 = swar_ne4(signs & 0x08040201);
            grid0 = swar_sub4(grid_pos.x() ^ signs0, signs0);
            const int signs1 = swar_ne4(signs & 0x80402010);
            grid1 = swar_sub4(grid_pos.y() ^ signs1, signs1);
        }
        int u0, u1;
        if constexpr (A == NOACT) { u0 = grid0 ^ (int) sl.w[4]; u1 = grid1 ^ (int) sl.w[5]; }
        else { u0 = get_int_b4(bq8_1[iqs / 2].qs, k0 + 0); u1 = get_int_b4(bq8_1[iqs / 2].qs, k0 + 1); }
        sumi = strata::dp4a(grid0, u0, sumi);
        sumi = strata::dp4a(grid1, u1, sumi);
    }
    const int ls = aux32 >> 27 | 1;
    sumi = sumi * ls / 8;
    const float ds = A == NOACT ? sl.f[0] : (float) bq8_1[iqs / 2].ds[0];
    const float d = dw * ds;
    return d * sumi;
}

// native_gu_kernel<TY, 8> for groups of one entry (row_entries' single-entry loop, row_dot_lanes<TY, 8>)
template <int TY, int A>
void gu_single(const unsigned long long* __restrict__ grp_ptr, const block_q8_1* __restrict__ xq, size_t up_off,
               size_t gu_row, int n_ff, int n_embd, float* __restrict__ gate, float* __restrict__ up, const void* G,
               const Salt sl) {
    constexpr int LN = 8;
    auto it = sycl::ext::oneapi::this_work_item::get_nd_item<3>();
    const int rib = (int) it.get_local_id(2) / LN, sub = (int) it.get_local_id(2) % LN;
    const int row = (int) it.get_group(2) * (256 / LN) + rib;
    if (row >= 2 * n_ff) return;
    const bool is_up = row >= n_ff;
    const int r = is_up ? row - n_ff : row;
    const size_t off = (is_up ? up_off : 0) + (size_t) r * gu_row;
    const int nb = n_embd / 256, xb = n_embd / 32;
    const int g = (int) it.get_group(1);   // one group per block row, entry e = g, its token g % 4
    const uint8_t* wr = (const uint8_t*) grp_ptr[g] + off;
    const block_q8_1* x = xq + (size_t) (g % 4) * xb;
    float s = 0.0f;
    for (int kk = sub; kk < nb * 8; kk += LN) {
        const int kbx = kk / 8, iqs = 2 * (kk % 8);
        if constexpr (TY == 21) s += dot21<A>(wr, x + kbx * 8, kbx, iqs, (const uint32_t*) G, sl);
        else s += dot16<A>(wr, x + kbx * 8, kbx, iqs, (const uint64_t*) G, sl);
    }
    s = lanes_sum<LN>(s);
    if (sub == 0) (is_up ? up : gate)[(size_t) g * n_ff + r] = s;
}

// ------------------------------------------------------------ copies of native_mmvq.dp.cpp's wide kernels
struct Q81Block { sycl::half2 ds; int8_t qs[32]; };
struct Q4KBlock { sycl::half2 dm; uint8_t scales[12]; uint8_t qs[128]; };
struct Q6KBlock { uint8_t ql[128]; uint8_t qh[64]; int8_t scales[16]; sycl::half d; };
constexpr int QK = 256, Q8K = 32, WARPS = 4, WARP = 32;

inline sycl::int4 ld_q8_16(const Q81Block* b, int half) {
    const int* q = reinterpret_cast<const int*>(b->qs) + 4 * half;
    return sycl::int4(q[0], q[1], q[2], q[3]);
}
inline int dp4a4(const sycl::int4 a, const sycl::int4 b, int acc) {
    acc = strata::dp4a(a.x(), b.x(), acc); acc = strata::dp4a(a.y(), b.y(), acc);
    acc = strata::dp4a(a.z(), b.z(), acc); return strata::dp4a(a.w(), b.w(), acc);
}
inline void k4_scale_min(const uint8_t* sc, int j, float& s, float& m) {
    if (j < 4) { s = (float) (sc[j] & 63); m = (float) (sc[j + 4] & 63); }
    else { s = (float) ((sc[j + 4] & 0xF) | ((sc[j - 4] >> 6) << 4)); m = (float) ((sc[j + 4] >> 4) | ((sc[j] >> 6) << 4)); }
}
template <class SC>   // k4_scale_min with the scale bytes from sc(i)
inline void k4_scale_min_f(const SC& sc, int j, float& s, float& m) {
    if (j < 4) { s = (float) (sc(j) & 63); m = (float) (sc(j + 4) & 63); }
    else { s = (float) ((sc(j + 4) & 0xF) | ((sc(j - 4) >> 6) << 4)); m = (float) ((sc(j + 4) >> 4) | ((sc(j) >> 6) << 4)); }
}
struct Q4W { sycl::int4 lo, hi; float dl, dh, ml, mh; int sb, half; };
template <int A>
inline Q4W q4_load(const Q4KBlock* b, int g, const Salt& sl) {
    Q4W r; r.sb = 2 * (g >> 1); r.half = g & 1;
    sycl::int4 q;
    sycl::half2 dmh;
    uint32_t x = 0;
    if constexpr (A == NOW) {   // the fields in registers, decoded below with the engine's expressions
        x = seed_of(b, g, 0, sl.w[0]);
        q = sycl::int4((int) x, (int) (x ^ sl.w[1]), (int) (x ^ sl.w[2]), (int) (x ^ sl.w[3]));
        dmh = sycl::half2(fake_half(x >> 3), fake_half(x >> 9));
    } else {
        q = reinterpret_cast<const sycl::int4*>(b->qs)[g];
        dmh = b->dm;
    }
    r.lo = sycl::int4(q.x() & 0x0f0f0f0f, q.y() & 0x0f0f0f0f, q.z() & 0x0f0f0f0f, q.w() & 0x0f0f0f0f);
    r.hi = sycl::int4((q.x() >> 4) & 0x0f0f0f0f, (q.y() >> 4) & 0x0f0f0f0f, (q.z() >> 4) & 0x0f0f0f0f, (q.w() >> 4) & 0x0f0f0f0f);
    const sycl::float2 dm = dmh.convert<float, sycl::rounding_mode::automatic>();
    float s0, m0, s1, m1;
    if constexpr (A == NOW) {
        auto sc = [x](int i) { return (uint8_t) ((x ^ ((uint32_t) i * 0x9Du)) >> 3); };
        k4_scale_min_f(sc, r.sb, s0, m0); k4_scale_min_f(sc, r.sb + 1, s1, m1);
    } else {
        k4_scale_min(b->scales, r.sb, s0, m0); k4_scale_min(b->scales, r.sb + 1, s1, m1);
    }
    r.dl = dm.x() * s0; r.ml = dm.y() * m0; r.dh = dm.x() * s1; r.mh = dm.y() * m1;
    return r;
}
template <int A>   // WideQ4K::apply's arithmetic; the caller loads ua, uc, da, dc (or, `noact`, makes them)
inline float q4_apply(const Q4W& r, const sycl::int4 ua, const sycl::int4 uc, const float da, const float dc) {
    const sycl::int4 ones(0x01010101, 0x01010101, 0x01010101, 0x01010101);
    if constexpr (A == NOONES) return da * (r.dl * (float) dp4a4(r.lo, ua, 0)) + dc * (r.dh * (float) dp4a4(r.hi, uc, 0));
    return da * (r.dl * (float) dp4a4(r.lo, ua, 0) - r.ml * (float) dp4a4(ones, ua, 0)) +
           dc * (r.dh * (float) dp4a4(r.hi, uc, 0) - r.mh * (float) dp4a4(ones, uc, 0));
}
template <int NCOLS, int A>
void q4k_wide(const Q4KBlock* __restrict__ w, const Q81Block* __restrict__ x, float* __restrict__ y, int n_in, int n_out,
              const Salt sl) {
    auto item = sycl::ext::oneapi::this_work_item::get_nd_item<3>();
    const int lane = int(item.get_local_id(2)), warp = int(item.get_local_id(1));
    const int row = int(item.get_group(2)) * WARPS + warp;
    if (row >= n_out) return;
    const int blocks_per_row = n_in / QK, x_stride = n_in / Q8K;
    const int g = lane & 7, sub = lane >> 3;
    const Q4KBlock* wr = w + std::size_t(row) * blocks_per_row;
    float acc[NCOLS] = {};
    for (int kbx = sub; kbx < blocks_per_row; kbx += 4) {
        const Q4W wv = q4_load<A>(wr + kbx, g, sl);
#pragma unroll
        for (int j = 0; j < NCOLS; ++j) {
            if constexpr (A == NOACT) {   // per column: the weights xor a column's salt, the column's salt scale
                const uint32_t ka = sl.w[j], kc = sl.w[4 + j];
                const sycl::int4 ua(wv.hi.x() ^ (int) ka, wv.hi.y() ^ (int) ka, wv.hi.z() ^ (int) ka, wv.hi.w() ^ (int) ka);
                const sycl::int4 uc(wv.lo.x() ^ (int) kc, wv.lo.y() ^ (int) kc, wv.lo.z() ^ (int) kc, wv.lo.w() ^ (int) kc);
                acc[j] += q4_apply<A>(wv, ua, uc, sl.f[j], sl.f[3 - j]);
            } else {
                const Q81Block* xb = x + std::size_t(j) * x_stride + kbx * (QK / Q8K);
                const Q81Block* a = xb + wv.sb; const Q81Block* c = xb + wv.sb + 1;
                acc[j] += q4_apply<A>(wv, ld_q8_16(a, wv.half), ld_q8_16(c, wv.half), (float) a->ds[0], (float) c->ds[0]);
            }
        }
    }
    auto sg = item.get_sub_group();
#pragma unroll
    for (int j = 0; j < NCOLS; ++j) {
        float v = acc[j];
#pragma unroll
        for (int o = WARP / 2; o > 0; o >>= 1) v += sycl::permute_group_by_xor(sg, v, o);
        if (lane == 0) y[std::size_t(j) * n_out + row] = v;
    }
}

inline sycl::int4 load16_a2(const void* p) {
    const uintptr_t a = reinterpret_cast<uintptr_t>(p);
    const sycl::int4* q = reinterpret_cast<const sycl::int4*>(a & ~uintptr_t(15));
    const int kk = int(a >> 2) & 3;
    const bool half = (a & 2) != 0;
    const sycl::int4 lo = q[0], hi = (a & 15) ? q[1] : lo;
    const uint32_t d[8] = {(uint32_t) lo.x(), (uint32_t) lo.y(), (uint32_t) lo.z(), (uint32_t) lo.w(),
                           (uint32_t) hi.x(), (uint32_t) hi.y(), (uint32_t) hi.z(), (uint32_t) hi.w()};
    uint32_t w[5];
#pragma unroll
    for (int i = 0; i < 5; ++i) w[i] = kk == 0 ? d[i] : kk == 1 ? d[i + 1] : kk == 2 ? d[i + 2] : d[(i + 3) & 7];
    uint32_t o[4];
#pragma unroll
    for (int i = 0; i < 4; ++i) o[i] = half ? (w[i] >> 16) | (w[i + 1] << 16) : w[i];
    return sycl::int4((int) o[0], (int) o[1], (int) o[2], (int) o[3]);
}
inline void q6_unpack(const sycl::int4& ql, const sycl::int4& qh, int vh_shift, int* vi0, int* vi1) {   // SWAR
    const int vl[4] = {ql.x(), ql.y(), ql.z(), ql.w()};
    const int vh[4] = {qh.x() >> vh_shift, qh.y() >> vh_shift, qh.z() >> vh_shift, qh.w() >> vh_shift};
#pragma unroll
    for (int p = 0; p < 4; ++p) {
        vi0[p] = (int) (((((uint32_t) vl[p] & 0x0f0f0f0fu) | (((uint32_t) vh[p] << 4) & 0x30303030u)) | 0x80808080u) - 0x20202020u) ^ 0x80808080u;
        vi1[p] = (int) (((((uint32_t) vl[p] >> 4 & 0x0f0f0f0fu) | ((((uint32_t) vh[p] >> 4) << 4) & 0x30303030u)) | 0x80808080u) - 0x20202020u) ^ 0x80808080u;
    }
}
// native_mmvq_q6k_wide_kernel<NCOLS, 1, WARP, sizeof(Q6KBlock), true, true> (base / noact / now)
template <int NCOLS, int A>
void q6k_wide(const Q6KBlock* __restrict__ w, const Q81Block* __restrict__ x, float* __restrict__ y, int n_in, int n_out,
              const Salt sl) {
    auto item = sycl::ext::oneapi::this_work_item::get_nd_item<3>();
    const int lane = int(item.get_local_id(2)), warp = int(item.get_local_id(1));
    const int row0 = int(item.get_group(2)) * WARPS + warp;
    if (row0 >= n_out) return;
    const int blocks_per_row = n_in / QK, x_stride = n_in / Q8K;
    const int g = lane & 7, sub = lane >> 3;
    const int vh_shift = 2 * ((g & 3) >> 1);
    const int qh4_idx = 2 * (g >> 2) + (g & 1);
    const int scale_offset = 8 * (g >> 2) + (g & 3);
    const int bq8_offset = 4 * (g >> 2) + ((g & 3) >> 1);
    const int u_int4 = g & 1;
    float acc[NCOLS] = {};
    for (int kbx = sub; kbx < blocks_per_row; kbx += WARP / 8) {
        const int kby = kbx * (QK / Q8K);
        sycl::int4 ql4, qh4; float dsc0, dsc1;
        {
            const Q6KBlock* b = reinterpret_cast<const Q6KBlock*>(reinterpret_cast<const uint8_t*>(w) +
                (std::size_t(row0) * blocks_per_row + kbx) * sizeof(Q6KBlock));
            if constexpr (A == NOW) {   // the fields in registers, the engine's scale expressions
                const uint32_t xs = seed_of(b, g, 0, sl.w[0]);
                ql4 = sycl::int4((int) xs, (int) (xs ^ sl.w[1]), (int) (xs ^ sl.w[2]), (int) (xs ^ sl.w[3]));
                qh4 = sycl::int4((int) (xs ^ sl.w[4]), (int) (xs ^ sl.w[5]), (int) (xs ^ sl.w[6]), (int) (xs ^ sl.w[7]));
                const float d = fake_half(xs >> 3);
                dsc0 = d * (float) (int8_t) (xs >> 8); dsc1 = d * (float) (int8_t) (xs >> 16);
            } else {
                ql4 = load16_a2(b->ql + 16 * g);
                qh4 = load16_a2(b->qh + 16 * qh4_idx);
                const float d = b->d;
                dsc0 = d * (float) b->scales[scale_offset]; dsc1 = d * (float) b->scales[scale_offset + 4];
            }
        }
        sycl::int4 u0[NCOLS], u1[NCOLS];
        float ds0[NCOLS], ds1[NCOLS];
#pragma unroll
        for (int j = 0; j < NCOLS; ++j) {
            if constexpr (A == NOACT) {   // per column: the weights xor a column's salt, the column's salt scales
                const int k0 = (int) sl.w[j], k1 = (int) sl.w[4 + j];
                u0[j] = sycl::int4(qh4.x() ^ k0, qh4.y() ^ k0, qh4.z() ^ k0, qh4.w() ^ k0);
                u1[j] = sycl::int4(ql4.x() ^ k1, ql4.y() ^ k1, ql4.z() ^ k1, ql4.w() ^ k1);
                ds0[j] = sl.f[j]; ds1[j] = sl.f[3 - j];
            } else {
                const Q81Block* xb = x + std::size_t(j) * x_stride + kby + bq8_offset;
                const int* p0 = reinterpret_cast<const int*>(xb[0].qs) + 4 * u_int4;
                const int* p1 = reinterpret_cast<const int*>(xb[2].qs) + 4 * u_int4;
                u0[j] = sycl::int4(p0[0], p0[1], p0[2], p0[3]);
                u1[j] = sycl::int4(p1[0], p1[1], p1[2], p1[3]);
                ds0[j] = xb[0].ds[0]; ds1[j] = xb[2].ds[0];
            }
        }
        int vi0[4], vi1[4];
        q6_unpack(ql4, qh4, vh_shift, vi0, vi1);
#pragma unroll
        for (int j = 0; j < NCOLS; ++j) {
            int s0 = 0, s1 = 0;
            s0 = strata::dp4a(vi0[0], u0[j].x(), s0); s0 = strata::dp4a(vi0[1], u0[j].y(), s0);
            s0 = strata::dp4a(vi0[2], u0[j].z(), s0); s0 = strata::dp4a(vi0[3], u0[j].w(), s0);
            s1 = strata::dp4a(vi1[0], u1[j].x(), s1); s1 = strata::dp4a(vi1[1], u1[j].y(), s1);
            s1 = strata::dp4a(vi1[2], u1[j].z(), s1); s1 = strata::dp4a(vi1[3], u1[j].w(), s1);
            acc[j] += ds0[j] * dsc0 * (float) s0 + ds1[j] * dsc1 * (float) s1;
        }
    }
    auto sg = item.get_sub_group();
#pragma unroll
    for (int j = 0; j < NCOLS; ++j) {
        float v = acc[j];
#pragma unroll
        for (int o = WARP / 2; o > 0; o >>= 1) v += sycl::permute_group_by_xor(sg, v, o);
        if (lane == 0) y[std::size_t(j) * n_out + row0] = v;
    }
}
// candidate: q6k_wide's weight loads (ql, qh, scales) of U steps first, then their dots in the same order as base
// (the steps' kbx = sub, sub + 4, ...; the same expression per step), so the output is bitwise base's
template <int NCOLS, int U>
void q6k_pf(const Q6KBlock* __restrict__ w, const Q81Block* __restrict__ x, float* __restrict__ y, int n_in, int n_out) {
    auto item = sycl::ext::oneapi::this_work_item::get_nd_item<3>();
    const int lane = int(item.get_local_id(2)), warp = int(item.get_local_id(1));
    const int row0 = int(item.get_group(2)) * WARPS + warp;
    if (row0 >= n_out) return;
    const int blocks_per_row = n_in / QK, x_stride = n_in / Q8K;
    const int g = lane & 7, sub = lane >> 3;
    const int vh_shift = 2 * ((g & 3) >> 1);
    const int qh4_idx = 2 * (g >> 2) + (g & 1);
    const int scale_offset = 8 * (g >> 2) + (g & 3);
    const int bq8_offset = 4 * (g >> 2) + ((g & 3) >> 1);
    const int u_int4 = g & 1;
    const uint8_t* wrow = reinterpret_cast<const uint8_t*>(w) + std::size_t(row0) * blocks_per_row * sizeof(Q6KBlock);
    float acc[NCOLS] = {};
    for (int kb0 = 0; kb0 < blocks_per_row; kb0 += 4 * U) {
        sycl::int4 ql4[U], qh4[U]; float dsc0[U], dsc1[U]; bool ok[U];
#pragma unroll
        for (int u = 0; u < U; ++u) {
            const int kbx = kb0 + 4 * u + sub;
            ok[u] = kbx < blocks_per_row;
            const Q6KBlock* b = reinterpret_cast<const Q6KBlock*>(wrow + std::size_t(ok[u] ? kbx : 0) * sizeof(Q6KBlock));
            ql4[u] = load16_a2(b->ql + 16 * g);
            qh4[u] = load16_a2(b->qh + 16 * qh4_idx);
            const float d = b->d;
            dsc0[u] = d * (float) b->scales[scale_offset]; dsc1[u] = d * (float) b->scales[scale_offset + 4];
        }
#pragma unroll
        for (int u = 0; u < U; ++u) {
            if (!ok[u]) continue;
            const int kby = (kb0 + 4 * u + sub) * (QK / Q8K);
            sycl::int4 u0[NCOLS], u1[NCOLS];
            float ds0[NCOLS], ds1[NCOLS];
#pragma unroll
            for (int j = 0; j < NCOLS; ++j) {
                const Q81Block* xb = x + std::size_t(j) * x_stride + kby + bq8_offset;
                const int* p0 = reinterpret_cast<const int*>(xb[0].qs) + 4 * u_int4;
                const int* p1 = reinterpret_cast<const int*>(xb[2].qs) + 4 * u_int4;
                u0[j] = sycl::int4(p0[0], p0[1], p0[2], p0[3]);
                u1[j] = sycl::int4(p1[0], p1[1], p1[2], p1[3]);
                ds0[j] = xb[0].ds[0]; ds1[j] = xb[2].ds[0];
            }
            int vi0[4], vi1[4];
            q6_unpack(ql4[u], qh4[u], vh_shift, vi0, vi1);
#pragma unroll
            for (int j = 0; j < NCOLS; ++j) {
                int s0 = 0, s1 = 0;
                s0 = strata::dp4a(vi0[0], u0[j].x(), s0); s0 = strata::dp4a(vi0[1], u0[j].y(), s0);
                s0 = strata::dp4a(vi0[2], u0[j].z(), s0); s0 = strata::dp4a(vi0[3], u0[j].w(), s0);
                s1 = strata::dp4a(vi1[0], u1[j].x(), s1); s1 = strata::dp4a(vi1[1], u1[j].y(), s1);
                s1 = strata::dp4a(vi1[2], u1[j].z(), s1); s1 = strata::dp4a(vi1[3], u1[j].w(), s1);
                acc[j] += ds0[j] * dsc0[u] * (float) s0 + ds1[j] * dsc1[u] * (float) s1;
            }
        }
    }
    auto sg = item.get_sub_group();
#pragma unroll
    for (int j = 0; j < NCOLS; ++j) {
        float v = acc[j];
#pragma unroll
        for (int o = WARP / 2; o > 0; o >>= 1) v += sycl::permute_group_by_xor(sg, v, o);
        if (lane == 0) y[std::size_t(j) * n_out + row0] = v;
    }
}
}  // namespace cp

template <int TY, int A> class KGu;
template <int N, int A> class KQ4;
template <int N, int A> class KQ6;
template <int N, int U> class KQ6pf;
class KMark;

struct Rng {
    uint64_t s;
    uint64_t next() { s ^= s >> 12; s ^= s << 25; s ^= s >> 27; return s * 2685821657736338717ull; }
};
static uint16_t small_half(Rng& r) {   // a finite fp16 scale 2^-13 .. 2^-6, either sign
    const uint64_t v = r.next();
    return (uint16_t) (((v & 3) == 0 ? 0x8000 : 0) | ((2 + (v >> 2) % 7) << 10) | ((v >> 8) & 1023));
}
static void fill_random(std::vector<uint8_t>& b, Rng& r) {
    for (size_t o = 0; o < b.size(); o += 8) {
        const uint64_t v = r.next();
        std::memcpy(&b[o], &v, std::min<size_t>(8, b.size() - o));
    }
}
static uint64_t hash(const std::vector<float>& v) {
    uint64_t h = 1469598103934665603ull;
    for (float f : v) { uint32_t u; std::memcpy(&u, &f, 4); h = (h ^ u) * 1099511628211ull; }
    return h;
}
static double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    const size_t n = v.size();
    return n == 0 ? 0 : n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

int main(int argc, char** argv) {
    const int rounds = argc > 1 && std::atoi(argv[1]) > 0 ? std::atoi(argv[1]) : 3;
    const int launches = argc > 2 && std::atoi(argv[2]) > 0 ? std::atoi(argv[2]) : 100;
    sycl::queue q{sycl::gpu_selector_v, sycl::property_list{sycl::property::queue::in_order(), sycl::property::queue::enable_profiling()}};
    sycl::queue* s = &q;
    std::printf("device: %s\n", q.get_device().get_info<sycl::info::device::name>().c_str());
    std::printf("driver: %s\n", q.get_device().get_info<sycl::info::device::driver_version>().c_str());
    std::printf("rounds %d, launches %d\n", rounds, launches);
    for (const char* e : {"STRATA_MMVQ_Q6_SWAR", "STRATA_Q2_SWAR"})
        if (const char* v = std::getenv(e)) std::printf("env %s=%s\n", e, v);
    // switches that send an engine call to another kernel than the one copied here
    for (const char* e : {"STRATA_MMVQ_A2", "STRATA_MMVQ_PF", "STRATA_MMVQ_WIDE_RPW", "STRATA_MMVQ_WIDE_K", "STRATA_MMVQ_SG",
                          "STRATA_MMVQ_WIDE", "STRATA_MMVQ_WIDE_MIN", "STRATA_MMVQ_WIDE_MAXC", "STRATA_MMVQ_WAVE", "STRATA_MMVQ_RPW",
                          "STRATA_Q6_PACKED", "STRATA_GU_LANES", "STRATA_EXPERT_SPLIT", "STRATA_OLD_IQ_MMVQ", "STRATA_GU_GRID_SLM",
                          "STRATA_GROUPED_V1", "STRATA_IQ_STAGE_GRID", "STRATA_EXPERT_LANES"})
        if (const char* v = std::getenv(e)) {
            std::printf("env %s=%s\n", e, v);
            std::printf("note: %s is set: an engine call may not take the copied kernel\n", e);
        }
    const bool swar = std::getenv("STRATA_MMVQ_Q6_SWAR") && std::atoi(std::getenv("STRATA_MMVQ_Q6_SWAR")) != 0;
    if (!swar) std::printf("note: STRATA_MMVQ_Q6_SWAR is not 1: the engine's Q6_K call is not the kernel copied here\n");

    constexpr int H = 2560, FF = 640, NOUT = 10240, G = 25, NT = 4;
    constexpr size_t kWorkingSet = (size_t) 320 << 20;   // bytes of weights the launches rotate over
    Rng rng{0x9E3779B97F4A7C15ull};
    cp::Salt salt;   // runtime values for the `noact` / `now` stand-ins
    for (auto& v : salt.w) v = (uint32_t) rng.next();
    for (auto& v : salt.f) v = 0.01f + (float) (rng.next() % 1000) * 1e-5f;
    auto dev_bytes = [&](const std::vector<uint8_t>& h) { void* p = sycl::malloc_device(h.size(), q); q.memcpy(p, h.data(), h.size()).wait(); return p; };

    // activations: NT tokens, q8_1 (the engine's quantizer)
    std::vector<float> xh((size_t) NT * H);
    { std::mt19937 mt(12345); std::normal_distribution<float> nd(0.f, 1.f); for (auto& v : xh) v = nd(mt); }
    float* dx = sycl::malloc_device<float>(xh.size(), q);
    q.memcpy(dx, xh.data(), xh.size() * 4).wait();
    auto* dxq = (block_q8_1*) sycl::malloc_device((size_t) NT * (H / 32) * sizeof(block_q8_1), q);
    k::quantize_q8_1_rows(dx, NT, H, dxq, s);
    q.wait_and_throw();

    auto kt = [](const sycl::event& e) {
        return (e.get_profiling_info<sycl::info::event_profiling::command_end>() -
                e.get_profiling_info<sycl::info::event_profiling::command_start>()) * 1e-3;
    };
    auto marker = [&] { return q.single_task<KMark>([] {}); };
    // one measurement: `launches` launches of fn(copy index), submitted back to back (one wait at the end, so the GPU
    // does not idle between them) -> the median device us of one launch
    auto measure = [&](int copies, const std::function<sycl::event(int)>& fn, bool engine) {
        std::vector<double> t;
        for (int i = 0; i < 5; ++i) fn(i % copies);
        q.wait_and_throw();
        std::vector<sycl::event> ev;
        for (int i = 0; i < launches; ++i) {
            if (engine) {
                ev.push_back(marker());
                fn(i % copies);
                ev.push_back(marker());
            } else {
                ev.push_back(fn(i % copies));
            }
        }
        q.wait_and_throw();
        if (engine)
            for (size_t i = 0; i + 1 < ev.size(); i += 2)
                t.push_back((ev[i + 1].get_profiling_info<sycl::info::event_profiling::command_start>() -
                             ev[i].get_profiling_info<sycl::info::event_profiling::command_end>()) * 1e-3);
        else
            for (const auto& e : ev) t.push_back(kt(e));
        return median(t);
    };
    std::printf("part\ttype\tvariant\tn\tus\tspread\tGB/s\tsame\tchecksum\n");
    auto report = [&](const char* part, const char* type, const char* var, int n, const std::vector<double>& per_round,
                      double bytes, const char* same, uint64_t h) {
        const double m = median(per_round);
        const double sp = m > 0 ? (*std::max_element(per_round.begin(), per_round.end()) -
                                   *std::min_element(per_round.begin(), per_round.end())) / m * 100 : 0;
        std::printf("%s\t%s\t%s\t%d\t%.1f\t%.1f%%\t%.1f\t%s\t%016llx\n", part, type, var, n, m, sp, bytes / (m * 1e3), same,
                    (unsigned long long) h);
        std::fflush(stdout);
    };

    // ------------------------------------------------------------ moe
    for (const int TY : {21, 16}) {
        const k::NativeExpertLayout L = k::native_expert_layout(TY, 42, H, FF);
        const int copies = (int) std::max<size_t>(2, kWorkingSet / ((size_t) G * L.bytes));
        std::vector<void*> blobs;   // copies x G experts
        for (int c = 0; c < copies * G; ++c) {
            std::vector<uint8_t> b(L.bytes);
            fill_random(b, rng);
            const size_t bs = TY == 21 ? sizeof(block_iq3_s) : sizeof(block_iq2_xxs);
            for (size_t o = 0; o < L.down_off; o += bs) { const uint16_t h = small_half(rng); std::memcpy(&b[o], &h, 2); }
            for (size_t o = L.down_off; o < L.bytes; o += 18) { const uint16_t h = small_half(rng); std::memcpy(&b[o], &h, 2); }   // Q2_0 d
            blobs.push_back(dev_bytes(b));
        }
        std::vector<unsigned long long*> dptr(copies);
        for (int c = 0; c < copies; ++c) {
            std::vector<unsigned long long> p(G);
            for (int g = 0; g < G; ++g) p[g] = (unsigned long long) blobs[(size_t) c * G + g];
            dptr[c] = sycl::malloc_device<unsigned long long>(G, q);
            q.memcpy(dptr[c], p.data(), G * 8).wait();
        }
        // the engine's call: G groups of one entry (entry g -> token g % 4), the gate/up phase
        std::vector<int32_t> start(G + 1), dst(G), tok(G);
        for (int g = 0; g <= G; ++g) start[g] = g;
        for (int g = 0; g < G; ++g) { dst[g] = g; tok[g] = g % NT; }
        auto* dstart = sycl::malloc_device<int32_t>(G + 1, q);
        auto* dn = sycl::malloc_device<int32_t>(1, q);
        auto* ddst = sycl::malloc_device<int32_t>(G, q);
        auto* dtok = sycl::malloc_device<int32_t>(G, q);
        int gG = G;
        q.memcpy(dstart, start.data(), (G + 1) * 4); q.memcpy(dn, &gG, 4); q.memcpy(ddst, dst.data(), G * 4);
        q.memcpy(dtok, tok.data(), G * 4).wait();
        void* scr = sycl::malloc_device(k::native_expert_scratch_bytes(G, FF), q);
        float* eout = sycl::malloc_device<float>((size_t) G * H, q);
        const size_t fa = ((size_t) G * FF * sizeof(float) + 255) & ~(size_t) 255;
        float* gate = sycl::malloc_device<float>((size_t) G * FF, q);
        float* up = sycl::malloc_device<float>((size_t) G * FF, q);
        const double bytes = (double) G * (double) L.down_off;
        const char* tname = TY == 21 ? "IQ3_S" : "IQ2_XXS";
        const size_t up_off = L.up_off, gu_row = L.gu_row;
        auto engine = [&](int c) {
            k::native_expert_set_mode(0, 1);
            k::native_expert_grouped(L, dptr[c], dstart, dn, ddst, dtok, G, G, dxq, scr, eout, s);
            k::native_expert_set_mode(0, 0);
            return sycl::event();
        };
        auto launch = [&](int A, int c) -> sycl::event {
            const unsigned long long* gp = dptr[c];
            const block_q8_1* xq = dxq;
            float *gt = gate, *upp = up;
            const cp::Salt sl = salt;
            const sycl::nd_range<3> nr(sycl::range<3>(1, G, (size_t) (2 * FF / 32) * 256), sycl::range<3>(1, 1, 256));
#define KGU(TT, AA) if (TY == TT && A == AA) return q.submit([&](sycl::handler& h) { \
                if constexpr (AA == SLM) { \
                    using GT = std::conditional_t<TT == 16, uint64_t, uint32_t>; \
                    constexpr int GN = TT == 16 ? 256 : 512; \
                    sycl::local_accessor<GT, 1> sg(sycl::range<1>(GN), h); \
                    h.parallel_for<KGu<TT, AA>>(nr, [=](sycl::nd_item<3> it) [[sycl::reqd_sub_group_size(32)]] { \
                        for (int i = (int) it.get_local_id(2); i < GN; i += 256) { \
                            if constexpr (TT == 16) sg[i] = iq2xxs_grid[i]; else sg[i] = iq3s_grid[i]; } \
                        it.barrier(sycl::access::fence_space::local_space); \
                        cp::gu_single<TT, AA>(gp, xq, up_off, gu_row, FF, H, gt, upp, \
                                              (const void*) sg.template get_multi_ptr<sycl::access::decorated::no>().get(), sl); }); \
                } else { \
                    h.parallel_for<KGu<TT, AA>>(nr, [=](sycl::nd_item<3>) [[sycl::reqd_sub_group_size(32)]] { \
                        cp::gu_single<TT, AA>(gp, xq, up_off, gu_row, FF, H, gt, upp, nullptr, sl); }); \
                } });
            KGU(21, BASE) KGU(21, NOGRID) KGU(21, NOSIGN) KGU(21, NOACT) KGU(21, NOW) KGU(21, SLM)
            KGU(16, BASE) KGU(16, NOGRID) KGU(16, NOSIGN) KGU(16, NOACT) KGU(16, NOW) KGU(16, SLM)
#undef KGU
            return sycl::event();
        };
        // bitwise, for every weight copy: base's gate/up against the engine's, slm's against base's
        std::vector<float> eg((size_t) G * FF), eu((size_t) G * FF), bg(eg.size()), bu(eg.size()), sg_(eg.size()), su(eg.size());
        bool eq_base = true, eq_slm = true;
        for (int c = 0; c < copies; ++c) {
            engine(c); q.wait_and_throw();
            q.memcpy(eg.data(), scr, eg.size() * 4); q.memcpy(eu.data(), (uint8_t*) scr + fa, eu.size() * 4).wait();
            launch(BASE, c); q.wait_and_throw();
            q.memcpy(bg.data(), gate, bg.size() * 4); q.memcpy(bu.data(), up, bu.size() * 4).wait();
            launch(SLM, c); q.wait_and_throw();
            q.memcpy(sg_.data(), gate, sg_.size() * 4); q.memcpy(su.data(), up, su.size() * 4).wait();
            eq_base = eq_base && std::memcmp(bg.data(), eg.data(), bg.size() * 4) == 0 && std::memcmp(bu.data(), eu.data(), bu.size() * 4) == 0;
            eq_slm = eq_slm && std::memcmp(sg_.data(), bg.data(), bg.size() * 4) == 0 && std::memcmp(su.data(), bu.data(), bu.size() * 4) == 0;
        }
        const std::string same_base = eq_base ? "1" : "0", same_slm = eq_slm ? "1" : "0";
        engine(0); q.wait_and_throw();   // copy 0's outputs for the checksums below
        q.memcpy(eg.data(), scr, eg.size() * 4); q.memcpy(eu.data(), (uint8_t*) scr + fa, eu.size() * 4).wait();
        const std::vector<int> vars = {BASE, NOGRID, NOSIGN, NOACT, NOW, SLM};
        std::vector<std::vector<double>> per(vars.size() + 1);
        for (int r = 0; r < rounds; ++r)   // the engine and the variants, the order rotated by one each round
            for (size_t o = 0; o <= vars.size(); ++o) {
                const size_t v = (o + (size_t) r) % (vars.size() + 1);
                if (v == 0) per[0].push_back(measure(copies, engine, true));
                else per[v].push_back(measure(copies, [&](int c) { return launch(vars[v - 1], c); }, false));
            }
        std::vector<float> eall(eg); eall.insert(eall.end(), eu.begin(), eu.end());
        report("moe", tname, "engine", G, per[0], bytes, "-", hash(eall));
        for (size_t v = 0; v < vars.size(); ++v) {
            launch(vars[v], 0); q.wait_and_throw();
            q.memcpy(bg.data(), gate, bg.size() * 4); q.memcpy(bu.data(), up, bu.size() * 4).wait();
            std::vector<float> all(bg); all.insert(all.end(), bu.begin(), bu.end());
            const char* same = vars[v] == BASE ? same_base.c_str() : vars[v] == SLM ? same_slm.c_str() : "-";
            report("moe", tname, var_name(vars[v]), G, per[v + 1], bytes, same, hash(all));
        }
        for (void* b : blobs) sycl::free(b, q);
        for (auto* p : dptr) sycl::free(p, q);
        sycl::free(dstart, q); sycl::free(dn, q); sycl::free(ddst, q); sycl::free(dtok, q);
        sycl::free(scr, q); sycl::free(eout, q); sycl::free(gate, q); sycl::free(up, q);
    }

    // ------------------------------------------------------------ q4k, q6k
    for (const int TY : {12, 14}) {
        const size_t bsz = TY == 12 ? sizeof(cp::Q4KBlock) : sizeof(cp::Q6KBlock);
        const size_t mat = (size_t) NOUT * (H / 256) * bsz;
        const int copies = (int) std::max<size_t>(2, kWorkingSet / mat);
        std::vector<void*> w;
        for (int c = 0; c < copies; ++c) {
            std::vector<uint8_t> b(mat);
            fill_random(b, rng);
            for (size_t o = 0; o < mat; o += bsz) {
                const uint16_t h0 = small_half(rng), h1 = small_half(rng);
                if (TY == 12) { std::memcpy(&b[o], &h0, 2); std::memcpy(&b[o + 2], &h1, 2); }   // d, dmin
                else std::memcpy(&b[o + 208], &h0, 2);                                       // d
            }
            w.push_back(dev_bytes(b));
        }
        float* y = sycl::malloc_device<float>((size_t) NT * NOUT, q);
        const char* tname = TY == 12 ? "Q4_K" : "Q6_K";
        const char* part = TY == 12 ? "q4k" : "q6k";
        const std::vector<int> vars = TY == 12 ? std::vector<int>{BASE, NOONES, NOACT, NOW} : std::vector<int>{BASE, NOACT, NOW, PF2, PF4};
        for (int n = 1; n <= 4; ++n) {
            const auto* xq = (const cp::Q81Block*) dxq;
            const sycl::nd_range<3> nr(sycl::range<3>(1, 1, (size_t) (NOUT / cp::WARPS)) * sycl::range<3>(1, cp::WARPS, cp::WARP),
                                       sycl::range<3>(1, cp::WARPS, cp::WARP));
            auto launch = [&](int A, int c) -> sycl::event {
                const void* wp = w[c];
                float* yy = y;
                const cp::Salt sl = salt;
#define KQ4(NN, AA) if (TY == 12 && n == NN && A == AA) return q.parallel_for<KQ4<NN, AA>>(nr, [=](sycl::nd_item<3>) \
                    [[sycl::reqd_sub_group_size(32)]] { cp::q4k_wide<NN, AA>((const cp::Q4KBlock*) wp, xq, yy, H, NOUT, sl); });
#define KQ6(NN, AA) if (TY == 14 && n == NN && A == AA) return q.parallel_for<KQ6<NN, AA>>(nr, [=](sycl::nd_item<3>) \
                    [[sycl::reqd_sub_group_size(32)]] { cp::q6k_wide<NN, AA>((const cp::Q6KBlock*) wp, xq, yy, H, NOUT, sl); });
#define KQ6P(NN, AA, UU) if (TY == 14 && n == NN && A == AA) return q.parallel_for<KQ6pf<NN, UU>>(nr, [=](sycl::nd_item<3>) \
                    [[sycl::reqd_sub_group_size(32)]] { cp::q6k_pf<NN, UU>((const cp::Q6KBlock*) wp, xq, yy, H, NOUT); });
#define ALLN(M, ...) M(1, __VA_ARGS__) M(2, __VA_ARGS__) M(3, __VA_ARGS__) M(4, __VA_ARGS__)
                ALLN(KQ4, BASE) ALLN(KQ4, NOONES) ALLN(KQ4, NOACT) ALLN(KQ4, NOW)
                ALLN(KQ6, BASE) ALLN(KQ6, NOACT) ALLN(KQ6, NOW)
                ALLN(KQ6P, PF2, 2) ALLN(KQ6P, PF4, 4)
#undef ALLN
#undef KQ4
#undef KQ6
#undef KQ6P
                return sycl::event();
            };
            auto engine = [&](int c) { k::native_mmvq(TY, w[c], dxq, y, H, NOUT, n, s); return sycl::event(); };
            std::vector<float> ey((size_t) n * NOUT), by(ey.size()), b0(ey.size());
            // bitwise, for every weight copy: base against the engine, pf2 / pf4 against base
            std::vector<bool> eq(vars.size(), true);
            for (int c = 0; c < copies; ++c) {
                engine(c); q.wait_and_throw(); q.memcpy(ey.data(), y, ey.size() * 4).wait();
                for (size_t v = 0; v < vars.size(); ++v) {
                    if (vars[v] != BASE && vars[v] != PF2 && vars[v] != PF4) continue;
                    launch(vars[v], c); q.wait_and_throw(); q.memcpy(by.data(), y, by.size() * 4).wait();
                    if (vars[v] == BASE) { b0 = by; eq[v] = eq[v] && std::memcmp(by.data(), ey.data(), by.size() * 4) == 0; }
                    else eq[v] = eq[v] && std::memcmp(by.data(), b0.data(), by.size() * 4) == 0;
                }
            }
            std::vector<std::string> same(vars.size(), "-");
            for (size_t v = 0; v < vars.size(); ++v)
                if (vars[v] == BASE || vars[v] == PF2 || vars[v] == PF4) same[v] = eq[v] ? "1" : "0";
            engine(0); q.wait_and_throw(); q.memcpy(ey.data(), y, ey.size() * 4).wait();   // copy 0 for the checksums
            std::vector<std::vector<double>> per(vars.size() + 1);
            for (int r = 0; r < rounds; ++r)   // the order rotated by one each round
                for (size_t o = 0; o <= vars.size(); ++o) {
                    const size_t v = (o + (size_t) r) % (vars.size() + 1);
                    if (v == 0) per[0].push_back(measure(copies, engine, true));
                    else per[v].push_back(measure(copies, [&](int c) { return launch(vars[v - 1], c); }, false));
                }
            report(part, tname, "engine", n, per[0], (double) mat, "-", hash(ey));
            for (size_t v = 0; v < vars.size(); ++v) {
                launch(vars[v], 0); q.wait_and_throw(); q.memcpy(by.data(), y, by.size() * 4).wait();
                report(part, tname, var_name(vars[v]), n, per[v + 1], (double) mat, same[v].c_str(), hash(by));
            }
        }
        for (void* p : w) sycl::free(p, q);
        sycl::free(y, q);
    }
    return 0;
}
