// moe_lab: the engine's grouped expert kernels (strata::kernels::native_expert_grouped) for one verify window of
// T tokens over the IQ3_XXS model's 48 layers, with each layer's own gate/up and down types
// (lab/results/01-decode-bound/tensors.tsv), 2560 x 640 experts and synthetic weights.
//   moe_lab [ms per case=1000] [max T=4]
// Window width T: every layer routes 10*T entries (10 experts per token) over the groups of kGroups[T] (one group =
// one distinct expert; a group's entries are different tokens). How many distinct experts a real window has per layer
// is not known (the engine does not report it); the sizes below are a fixed guess that also runs the 4-, 2- and
// 1-entry paths of the kernels. Every layer has its own experts in device memory, so one window reads 48 layers'
// worth of distinct weights, as the engine does.
// Lines: one per T for the whole window (48 calls back to back, one wait), then one per (gate/up, down) type pair
// with only that pair's layers: microseconds per layer and the experts' GB/s (GB = 1e9 bytes, the distinct experts'
// bytes / time). Use the numbers to compare two runs (a switch on and off), not as the engine's time: the engine
// quantizes the activations and plans the groups in kernels of its own, and replays the window as a graph.
// MOE_LAB_DUMP=<file>: every layer's output of the last whole-window run of every T (float32), for comparing two runs
// (for example STRATA_Q2_SWAR unset and =1) byte for byte. The checksum only shows the outputs were finite.
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
#include <utility>
#include <vector>

namespace k = strata::kernels;

// gate/up type : down type of blk.0 .. blk.47 (ggml types: IQ2_XXS 16, IQ2_XS 17, IQ3_XXS 18, IQ4_NL 20, IQ3_S 21,
// IQ2_S 22, Q2_0 42)
static const int kLayers[48][2] = {
    {17, 20}, {16, 42}, {17, 20}, {16, 42}, {17, 20}, {17, 42}, {16, 42}, {16, 42}, {21, 42}, {17, 42}, {17, 42}, {16, 42},
    {22, 42}, {16, 42}, {17, 42}, {22, 42}, {16, 42}, {22, 42}, {21, 42}, {17, 42}, {21, 42}, {22, 42}, {21, 42}, {21, 42},
    {21, 42}, {17, 42}, {22, 42}, {16, 42}, {21, 20}, {22, 20}, {21, 20}, {16, 20}, {21, 20}, {21, 42}, {21, 20}, {18, 20},
    {18, 42}, {21, 20}, {22, 20}, {17, 20}, {22, 42}, {18, 42}, {22, 20}, {21, 20}, {18, 20}, {18, 42}, {22, 20}, {18, 20},
};
constexpr int64_t kH = 2560, kFF = 640;
constexpr int kTopK = 10, kMaxT = 4;

// group sizes (entries per distinct expert) of a T-token window: 10*T entries in all
static std::vector<int> groups_of(int T) {
    std::vector<int> c;
    switch (T) {
        case 1: c.assign(10, 1); break;                                   // 10 experts
        case 2: c = {2, 2, 2}; c.resize(17, 1); break;                    // 17 experts
        case 3: c = {3, 2, 2, 2}; c.resize(25, 1); break;                 // 25 experts
        default: c = {4, 3, 3, 2, 2, 2}; c.resize(30, 1); break;          // 30 experts
    }
    return c;
}

static int block_values(int t) { return t == 20 ? 32 : t == 42 ? 64 : 256; }

struct Rng {   // xorshift64*: the same bytes on every run
    uint64_t s;
    uint64_t next() { s ^= s >> 12; s ^= s << 25; s ^= s >> 27; return s * 2685821657736338717ull; }
};

// `rows` rows of `n` values of format t: random bytes, then a finite fp16 scale (2^-13 .. 2^-6) at every block start
static void random_rows(int t, int64_t rows, int64_t n, Rng& r, std::vector<uint8_t>& out) {
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
    std::vector<void*> blobs;   // kMaxT's group count, the first G used for a smaller T
    unsigned long long* dptr = nullptr;
    int32_t *dstart = nullptr, *dn = nullptr, *ddst = nullptr, *dtok = nullptr;
    void* scr = nullptr;
    float* out = nullptr;
};

int main(int argc, char** argv) {
    const double ms_per_case = argc > 1 ? std::atof(argv[1]) : 1000.0;
    const int max_t = argc > 2 ? std::max(1, std::min(kMaxT, std::atoi(argv[2]))) : kMaxT;
    sycl::queue* s = &dpct::get_in_order_queue();
    const sycl::device dev = s->get_device();
    std::printf("device: %s\n", dev.get_info<sycl::info::device::name>().c_str());
    std::printf("driver: %s\n", dev.get_info<sycl::info::device::driver_version>().c_str());
    std::printf("%.0f ms per case\n", ms_per_case);
    for (const char* e : {"STRATA_Q2_SWAR", "STRATA_GU_LANES", "STRATA_DOWN_LANES", "STRATA_EXPERT_SPLIT", "STRATA_OLD_IQ_MMVQ",
                          "STRATA_GROUPED_V1", "STRATA_IQ_STAGE_GRID"})
        if (const char* v = std::getenv(e)) std::printf("env %s=%s\n", e, v);
    FILE* dump = std::getenv("MOE_LAB_DUMP") ? std::fopen(std::getenv("MOE_LAB_DUMP"), "wb") : nullptr;
    if (std::getenv("MOE_LAB_DUMP") && dump == nullptr) { std::fprintf(stderr, "moe_lab: cannot open MOE_LAB_DUMP\n"); return 1; }

    const int gmax = (int) groups_of(max_t).size(), cap = kTopK * max_t;
    Rng rng{0x9E3779B97F4A7C15ull};
    std::vector<Layer> layers(48);
    double blob_mb = 0;
    for (int l = 0; l < 48; ++l) {
        Layer& y = layers[(size_t) l];
        y.L = k::native_expert_layout(kLayers[l][0], kLayers[l][1], kH, kFF);
        if (!k::native_expert_supported(kLayers[l][0], kLayers[l][1], kH, kFF)) {
            std::fprintf(stderr, "moe_lab: layer %d types %d/%d not supported\n", l, kLayers[l][0], kLayers[l][1]);
            return 1;
        }
        for (int g = 0; g < gmax; ++g) {
            std::vector<uint8_t> b;
            random_rows(kLayers[l][0], 2 * kFF, kH, rng, b);   // gate rows | up rows
            random_rows(kLayers[l][1], kH, kFF, rng, b);       // down rows
            if (b.size() != y.L.bytes) { std::fprintf(stderr, "moe_lab: blob %zu != %zu bytes\n", b.size(), y.L.bytes); return 1; }
            void* d = sycl::malloc_device(b.size(), *s);
            if (d == nullptr) { std::fprintf(stderr, "moe_lab: out of device memory\n"); return 1; }
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

    // the activations: kMaxT tokens, quantized once (q8_1, kH/32 blocks per token)
    std::vector<float> x((size_t) kMaxT * kH);
    {
        std::mt19937 mt(12345);
        std::normal_distribution<float> nd(0.f, 1.f);
        for (auto& v : x) v = nd(mt);
    }
    float* dx = sycl::malloc_device<float>(x.size(), *s);
    void* dxq = sycl::malloc_device((size_t) kMaxT * (kH / 32) * 36, *s);
    s->memcpy(dx, x.data(), x.size() * 4).wait();
    k::quantize_q8_1_rows(dx, kMaxT, kH, dxq, s);
    s->wait();

    std::printf("T\tscope\tlayers\tgroups\tentries\tms_per_window\tus_per_layer\tGB/s\tchecksum\n");
    for (int T = 1; T <= max_t; ++T) {
        const std::vector<int> cnt = groups_of(T);
        const int G = (int) cnt.size();
        std::vector<int32_t> start(1, 0), tok, dst;
        for (int c : cnt) {
            for (int i = 0; i < c; ++i) tok.push_back((int32_t) ((start.size() + (size_t) i) % (size_t) T));   // c distinct tokens
            start.push_back(start.back() + c);
        }
        const int E = start.back();
        for (int e = 0; e < E; ++e) dst.push_back(e);
        for (Layer& y : layers) {
            std::vector<unsigned long long> p;
            for (int g = 0; g < G; ++g) p.push_back((unsigned long long) y.blobs[(size_t) g]);
            s->memcpy(y.dptr, p.data(), p.size() * 8);
            s->memcpy(y.dstart, start.data(), start.size() * 4);
            s->memcpy(y.dn, &G, 4);
            s->memcpy(y.ddst, dst.data(), dst.size() * 4);
            s->memcpy(y.dtok, tok.data(), tok.size() * 4);
            s->wait();
        }
        // scope -1: the whole window; then each type pair's layers alone
        std::map<std::pair<int, int>, std::vector<int>> pairs;
        for (int l = 0; l < 48; ++l) pairs[{kLayers[l][0], kLayers[l][1]}].push_back(l);
        std::vector<std::pair<std::pair<int, int>, std::vector<int>>> scopes;
        {
            std::vector<int> all;
            for (int l = 0; l < 48; ++l) all.push_back(l);
            scopes.push_back({{-1, -1}, all});
        }
        for (auto& [pr, ls] : pairs) scopes.push_back({pr, ls});
        for (auto& [pr, ls] : scopes) {
            auto window = [&] {
                for (int l : ls) {
                    Layer& y = layers[(size_t) l];
                    k::native_expert_grouped(y.L, y.dptr, y.dstart, y.dn, y.ddst, y.dtok, (int64_t) kTopK * T,
                                             (int64_t) kTopK * T, dxq, y.scr, y.out, s);
                }
            };
            for (int i = 0; i < 3; ++i) window();
            s->wait();
            int n = 0;
            const auto t0 = std::chrono::steady_clock::now();
            double ms = 0;
            do {
                window();
                s->wait();
                ++n;
                ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
            } while (ms < ms_per_case);
            const double per_window = ms / n;
            double bytes = 0;
            for (int l : ls) bytes += (double) G * (double) layers[(size_t) l].L.bytes;
            uint64_t h = 1469598103934665603ull;
            bool finite = true;
            std::vector<float> o((size_t) E * kH);
            for (int l : ls) {
                s->memcpy(o.data(), layers[(size_t) l].out, o.size() * 4).wait();
                for (float v : o) {
                    uint32_t u;
                    std::memcpy(&u, &v, 4);
                    h = (h ^ u) * 1099511628211ull;
                    finite = finite && std::isfinite(v);
                }
                if (dump != nullptr && pr.first < 0) std::fwrite(o.data(), 4, o.size(), dump);
            }
            char scope[32];
            if (pr.first < 0) std::snprintf(scope, sizeof scope, "window");
            else std::snprintf(scope, sizeof scope, "%d/%d", pr.first, pr.second);
            std::printf("%d\t%s\t%zu\t%d\t%d\t%.3f\t%.1f\t%.1f\t%016llx%s\n", T, scope, ls.size(), G, E, per_window,
                        1e3 * per_window / (double) ls.size(), bytes / (per_window * 1e6), (unsigned long long) h,
                        finite ? "" : " NONFINITE");
            std::fflush(stdout);
        }
    }
    if (dump != nullptr) std::fclose(dump);
    return 0;
}
