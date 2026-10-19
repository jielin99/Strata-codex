// moe_probe: where the engine's grouped expert kernels (strata::kernels::native_expert_grouped) spend their time on
// this GPU, for the IQ3_XXS model's 48 layers (each layer's own gate/up and down types, 2560 x 640 experts, synthetic
// weights; the same layer table and window sizes as lab/tools/moe_lab.cpp).
//   moe_probe [ms per case=300] [max T=4]
// Every case runs the scope's layers back to back, one host wait per window (the time includes the submissions and
// that wait), and is timed three ways:
//   all   the whole call: gate/up, SwiGLU + q8_1, down
//   gu    the gate/up phase: gate/up + SwiGLU + q8_1  (native_expert_set_mode(0, 1))
//   down  down only                                   (native_expert_set_mode(0, 2))
// (the phases run alone, so `all` need not be `gu` + `down`), and with two weight layouts:
//   dram    every group of a layer on its own expert (distinct bytes, as the engine reads them)
//   cached  every group of a layer on expert 0 (one pointer: later groups can hit the caches; whether they do is
//           not measured)
// Cases: `T` windows of 1..max T tokens (moe_lab's group sizes; the entries go round the tokens, so each token has
// 10), and `G10xE` = 10 groups of E = 1, 2, 4 entries each (the same weight bytes, E times the dot products).
// GB/s = G x the phase's bytes of one expert / time, also for `cached`: an equivalent weight rate for comparing
// runs, not the DRAM traffic (codebooks, activations, outputs and repeated reads are not counted).
// iters = windows timed. checksum = the call's outputs; gu_checksum = the gate and up values before SwiGLU and
// q8_1 (the scratch layout native_expert_grouped uses: gate at 0, up at the 256-byte-rounded cap_entries x n_ff
// floats), both from the last full call of the `all` line. Use the numbers to compare runs, not as the engine's time.
// Built against the engine's kernels (see lab/plans for the command line); it changes no engine file.
#include "strata/kernels/iq_kernels.hpp"
#include <sycl/sycl.hpp>
#include <dpct/dpct.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <random>
#include <string>
#include <utility>
#include <vector>

namespace k = strata::kernels;

// gate/up type : down type of blk.0 .. blk.47 (as moe_lab)
static const int kLayers[48][2] = {
    {17, 20}, {16, 42}, {17, 20}, {16, 42}, {17, 20}, {17, 42}, {16, 42}, {16, 42}, {21, 42}, {17, 42}, {17, 42}, {16, 42},
    {22, 42}, {16, 42}, {17, 42}, {22, 42}, {16, 42}, {22, 42}, {21, 42}, {17, 42}, {21, 42}, {22, 42}, {21, 42}, {21, 42},
    {21, 42}, {17, 42}, {22, 42}, {16, 42}, {21, 20}, {22, 20}, {21, 20}, {16, 20}, {21, 20}, {21, 42}, {21, 20}, {18, 20},
    {18, 42}, {21, 20}, {22, 20}, {17, 20}, {22, 42}, {18, 42}, {22, 20}, {21, 20}, {18, 20}, {18, 42}, {22, 20}, {18, 20},
};
constexpr int64_t kH = 2560, kFF = 640;
constexpr int kTopK = 10, kMaxT = 4, kMaxE = 4, kGroupsE = 10;

static std::vector<int> groups_of(int T) {   // moe_lab's: entries per distinct expert of a T-token window
    std::vector<int> c;
    switch (T) {
        case 1: c.assign(10, 1); break;
        case 2: c = {2, 2, 2}; c.resize(17, 1); break;
        case 3: c = {3, 2, 2, 2}; c.resize(25, 1); break;
        default: c = {4, 3, 3, 2, 2, 2}; c.resize(30, 1); break;
    }
    return c;
}

static int block_values(int t) { return t == 20 ? 32 : t == 42 ? 64 : 256; }

struct Rng {
    uint64_t s;
    uint64_t next() { s ^= s >> 12; s ^= s << 25; s ^= s >> 27; return s * 2685821657736338717ull; }
};

static void random_rows(int t, int64_t rows, int64_t n, Rng& r, std::vector<uint8_t>& out) {   // as moe_lab
    const size_t rb = k::iq_row_bytes(t, n), bs = k::iq_row_bytes(t, block_values(t));
    const size_t o0 = out.size();
    out.resize(o0 + (size_t) rows * rb);
    for (size_t o = o0; o < out.size(); o += 8) {
        const uint64_t v = r.next();
        std::memcpy(&out[o], &v, std::min<size_t>(8, out.size() - o));
    }
    for (size_t o = o0; o < out.size(); o += bs) {
        const uint64_t v = r.next();
        const uint16_t h = (uint16_t) (((v & 3) == 0 ? 0x8000 : 0) | ((2 + (v >> 2) % 7) << 10) | ((v >> 8) & 1023));
        std::memcpy(&out[o], &h, 2);
    }
}

struct Layer {
    k::NativeExpertLayout L;
    std::vector<void*> blobs;
    unsigned long long* dptr = nullptr;
    int32_t *dstart = nullptr, *dn = nullptr, *ddst = nullptr, *dtok = nullptr;
    void* scr = nullptr;
    float* out = nullptr;
};

int main(int argc, char** argv) {
    const double ms_per_case = argc > 1 ? std::atof(argv[1]) : 300.0;
    const int max_t = argc > 2 ? std::max(1, std::min(kMaxT, std::atoi(argv[2]))) : kMaxT;
    sycl::queue* s = &dpct::get_in_order_queue();
    const sycl::device dev = s->get_device();
    std::printf("device: %s\n", dev.get_info<sycl::info::device::name>().c_str());
    std::printf("driver: %s\n", dev.get_info<sycl::info::device::driver_version>().c_str());
    std::printf("%.0f ms per case\n", ms_per_case);
    for (const char* e : {"STRATA_Q2_SWAR", "STRATA_GU_LANES", "STRATA_DOWN_LANES", "STRATA_EXPERT_SPLIT", "STRATA_OLD_IQ_MMVQ",
                          "STRATA_GROUPED_V1", "STRATA_IQ_STAGE_GRID", "STRATA_GU_GRID_SLM", "STRATA_GU_GRID_SLM2"})
        if (const char* v = std::getenv(e)) std::printf("env %s=%s\n", e, v);

    const int gmax = std::max((int) groups_of(max_t).size(), kGroupsE);
    const int cap = std::max(kTopK * max_t, kGroupsE * kMaxE);
    Rng rng{0x9E3779B97F4A7C15ull};
    std::vector<Layer> layers(48);
    double blob_mb = 0;
    for (int l = 0; l < 48; ++l) {
        Layer& y = layers[(size_t) l];
        y.L = k::native_expert_layout(kLayers[l][0], kLayers[l][1], kH, kFF);
        if (!k::native_expert_supported(kLayers[l][0], kLayers[l][1], kH, kFF)) {
            std::fprintf(stderr, "moe_probe: layer %d types %d/%d not supported\n", l, kLayers[l][0], kLayers[l][1]);
            return 1;
        }
        for (int g = 0; g < gmax; ++g) {
            std::vector<uint8_t> b;
            random_rows(kLayers[l][0], 2 * kFF, kH, rng, b);
            random_rows(kLayers[l][1], kH, kFF, rng, b);
            if (b.size() != y.L.bytes) { std::fprintf(stderr, "moe_probe: blob %zu != %zu bytes\n", b.size(), y.L.bytes); return 1; }
            void* d = sycl::malloc_device(b.size(), *s);
            if (d == nullptr) { std::fprintf(stderr, "moe_probe: out of device memory\n"); return 1; }
            s->memcpy(d, b.data(), b.size()).wait();
            y.blobs.push_back(d);
            blob_mb += (double) b.size() / 1e6;
        }
        y.dptr = sycl::malloc_device<unsigned long long>((size_t) cap, *s);
        y.dstart = sycl::malloc_device<int32_t>((size_t) cap + 1, *s);
        y.dn = sycl::malloc_device<int32_t>(1, *s);
        y.ddst = sycl::malloc_device<int32_t>((size_t) cap, *s);
        y.dtok = sycl::malloc_device<int32_t>((size_t) cap, *s);
        y.scr = sycl::malloc_device(k::native_expert_scratch_bytes(cap, kFF), *s);
        y.out = sycl::malloc_device<float>((size_t) cap * kH, *s);
    }
    std::printf("experts in device memory: %.0f MB (48 layers x %d)\n", blob_mb, gmax);

    const int ntok = std::max(kMaxT, kMaxE);
    std::vector<float> x((size_t) ntok * kH);
    {
        std::mt19937 mt(12345);
        std::normal_distribution<float> nd(0.f, 1.f);
        for (auto& v : x) v = nd(mt);
    }
    float* dx = sycl::malloc_device<float>(x.size(), *s);
    void* dxq = sycl::malloc_device((size_t) ntok * (kH / 32) * 36, *s);
    s->memcpy(dx, x.data(), x.size() * 4).wait();
    k::quantize_q8_1_rows(dx, ntok, kH, dxq, s);
    s->wait_and_throw();

    // the cases: name, the launch's group rows and entry capacity, entries per group (a group's entries are distinct
    // tokens). T windows are sized as the engine sizes them (10 per token for both); G10xE has exactly its 10 group
    // rows, so E changes only the work per group
    struct Case { std::string name; int64_t capg, cape; int ntok; std::vector<int> cnt; };
    std::vector<Case> cases;
    for (int T = 1; T <= max_t; ++T) cases.push_back({"T" + std::to_string(T), kTopK * T, kTopK * T, T, groups_of(T)});
    for (int E : {1, 2, 4})
        cases.push_back({"G10x" + std::to_string(E), kGroupsE, kGroupsE * E, E, std::vector<int>(kGroupsE, E)});

    std::map<std::pair<int, int>, std::vector<int>> pairs;
    for (int l = 0; l < 48; ++l) pairs[{kLayers[l][0], kLayers[l][1]}].push_back(l);
    std::vector<std::pair<std::pair<int, int>, std::vector<int>>> scopes;
    {
        std::vector<int> all;
        for (int l = 0; l < 48; ++l) all.push_back(l);
        scopes.push_back({{-1, -1}, all});
    }
    for (auto& [pr, ls] : pairs) scopes.push_back({pr, ls});

    std::printf("case\tscope\tlayers\tgroups\tentries\tmem\tphase\tus_per_layer\tGB/s\titers\tchecksum\tgu_checksum\n");
    for (const auto& [cname, capg, cape, ntok_c, cnt] : cases) {
        const int G = (int) cnt.size();
        std::vector<int32_t> start(1, 0), tok, dst;
        for (int c : cnt) {
            for (int i = 0; i < c; ++i) tok.push_back((int32_t) (tok.size() % (size_t) ntok_c));   // round the tokens
            start.push_back(start.back() + c);
        }
        const int E = start.back();
        for (int e = 0; e < E; ++e) dst.push_back(e);
        for (int same = 0; same < 2; ++same) {
            for (Layer& y : layers) {
                std::vector<unsigned long long> p;
                for (int g = 0; g < G; ++g) p.push_back((unsigned long long) y.blobs[(size_t) (same ? 0 : g)]);
                s->memcpy(y.dptr, p.data(), p.size() * 8);
                s->memcpy(y.dstart, start.data(), start.size() * 4);
                s->memcpy(y.dn, &G, 4);
                s->memcpy(y.ddst, dst.data(), dst.size() * 4);
                s->memcpy(y.dtok, tok.data(), tok.size() * 4);
                s->wait_and_throw();
            }
            for (auto& [pr, ls] : scopes) {
                for (int phase = 0; phase < 3; ++phase) {
                    auto window = [&] {
                        for (int l : ls) {
                            Layer& y = layers[(size_t) l];
                            k::native_expert_grouped(y.L, y.dptr, y.dstart, y.dn, y.ddst, y.dtok, capg, cape, dxq, y.scr,
                                                     y.out, s);
                        }
                    };
                    k::native_expert_set_mode(0, 0);
                    window();   // the down phase reads the q8_1 image this full call leaves in the scratch
                    k::native_expert_set_mode(0, phase);
                    for (int i = 0; i < 3; ++i) window();
                    s->wait_and_throw();
                    int n = 0;
                    const auto t0 = std::chrono::steady_clock::now();
                    double ms = 0;
                    do {
                        window();
                        s->wait_and_throw();
                        ++n;
                        ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
                    } while (ms < ms_per_case);
                    k::native_expert_set_mode(0, 0);
                    const double per_window = ms / n;
                    double bytes = 0;
                    for (int l : ls) {
                        const auto& L = layers[(size_t) l].L;
                        const double gu = (double) L.down_off, dn = (double) (L.bytes - L.down_off);
                        bytes += (double) G * (phase == 0 ? gu + dn : phase == 1 ? gu : dn);
                    }
                    uint64_t h = 1469598103934665603ull, hg = 1469598103934665603ull;
                    bool finite = true;
                    auto fold = [&](uint64_t& acc, const std::vector<float>& v) {
                        for (float f : v) {
                            uint32_t u;
                            std::memcpy(&u, &f, 4);
                            acc = (acc ^ u) * 1099511628211ull;
                            finite = finite && std::isfinite(f);
                        }
                    };
                    if (phase == 0) {   // the last full call above (phase 0 was timed)
                        std::vector<float> o((size_t) E * kH), gu((size_t) E * kFF);
                        const size_t fa = ((size_t) cape * (size_t) kFF * sizeof(float) + 255) & ~(size_t) 255;
                        for (int l : ls) {
                            s->memcpy(o.data(), layers[(size_t) l].out, o.size() * 4).wait();
                            fold(h, o);
                            s->memcpy(gu.data(), layers[(size_t) l].scr, gu.size() * 4).wait();   // gate
                            fold(hg, gu);
                            s->memcpy(gu.data(), (const uint8_t*) layers[(size_t) l].scr + fa, gu.size() * 4).wait();   // up
                            fold(hg, gu);
                        }
                    }
                    char scope[32];
                    if (pr.first < 0) std::snprintf(scope, sizeof scope, "window");
                    else std::snprintf(scope, sizeof scope, "%d/%d", pr.first, pr.second);
                    char sum[40] = "-", gsum[24] = "-";
                    if (phase == 0) {
                        std::snprintf(sum, sizeof sum, "%016llx%s", (unsigned long long) h, finite ? "" : " NONFINITE");
                        std::snprintf(gsum, sizeof gsum, "%016llx", (unsigned long long) hg);
                    }
                    std::printf("%s\t%s\t%zu\t%d\t%d\t%s\t%s\t%.1f\t%.1f\t%d\t%s\t%s\n", cname.c_str(), scope, ls.size(), G, E,
                                same ? "cached" : "dram", phase == 0 ? "all" : phase == 1 ? "gu" : "down",
                                1e3 * per_window / (double) ls.size(), bytes / (per_window * 1e6), n, sum, gsum);
                    std::fflush(stdout);
                }
            }
        }
    }
    return 0;
}
