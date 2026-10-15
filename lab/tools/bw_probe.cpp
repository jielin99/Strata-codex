// bw_probe: how fast can the GPU read memory allocated the way the engine allocates it?
//   bw_probe [MiB=2048] [iters=20] [kinds=device,host]
// Fills each buffer with a non-zero pattern by a kernel (no zero pages, no constant data), then times a read-only
// kernel that streams the whole buffer in 16-byte loads and folds it into one word per work-item (written out, so it
// cannot be optimized away).  Prints one line per iteration and a summary (median/min/max GB/s, GB = 1e9 bytes).
// Standalone (no engine code):  icx -fsycl -O2 bw_probe.cpp -o bw_probe.exe   /   icpx -fsycl -O2 ...
#include <sycl/sycl.hpp>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

static double run_one(sycl::queue& q, const sycl::uint4* buf, size_t n16, uint32_t* out, size_t items, size_t wg) {
    const auto t0 = std::chrono::steady_clock::now();
    q.parallel_for(sycl::nd_range<1>(items, wg), [=](sycl::nd_item<1> it) {
        const size_t gid = it.get_global_id(0), stride = it.get_global_range(0);
        uint32_t acc = 0;
        for (size_t i = gid; i < n16; i += stride) {
            const sycl::uint4 v = buf[i];
            acc ^= v.x() + v.y() * 3u + v.z() * 5u + v.w() * 7u;
        }
        out[gid] = acc;
    }).wait();
    return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}

int main(int argc, char** argv) {
    const size_t mib = argc > 1 ? (size_t) std::atoll(argv[1]) : 2048;
    const int iters = argc > 2 ? std::atoi(argv[2]) : 20;
    const std::string kinds = argc > 3 ? argv[3] : "device,host";
    sycl::queue q{sycl::gpu_selector_v};
    const sycl::device dev = q.get_device();
    std::printf("device: %s\n", dev.get_info<sycl::info::device::name>().c_str());
    std::printf("driver: %s\n", dev.get_info<sycl::info::device::driver_version>().c_str());
    std::printf("buffer: %zu MiB, iterations: %d\n", mib, iters);
    const size_t bytes = mib << 20, n16 = bytes / 16;
    const size_t wg = 256;
    const size_t items = (size_t) dev.get_info<sycl::info::device::max_compute_units>() * wg * 16;
    uint32_t* out = sycl::malloc_device<uint32_t>(items, q);
    size_t pos = 0;
    while (pos <= kinds.size()) {
        size_t end = kinds.find(',', pos);
        if (end == std::string::npos) end = kinds.size();
        const std::string kind = kinds.substr(pos, end - pos);
        pos = end + 1;
        if (kind.empty()) continue;
        void* p = nullptr;
        if (kind == "device") p = sycl::malloc_device(bytes, q);
        else if (kind == "host") p = sycl::malloc_host(bytes, q);
        else if (kind == "shared") p = sycl::malloc_shared(bytes, q);
        else { std::printf("%s: unknown kind (device, host, shared)\n", kind.c_str()); continue; }
        if (p == nullptr) { std::printf("%s: allocation of %zu MiB failed\n", kind.c_str(), mib); continue; }
        sycl::uint4* buf = (sycl::uint4*) p;
        q.parallel_for(sycl::range<1>(n16), [=](sycl::id<1> i) {
            const uint32_t k = (uint32_t) i[0] * 2654435761u;
            buf[i] = sycl::uint4(k ^ 0x9E3779B9u, k + 0x7F4A7C15u, k * 3u + 1u, ~k);
        }).wait();
        run_one(q, buf, n16, out, items, wg);   // warm-up
        std::vector<double> gbs;
        for (int i = 0; i < iters; ++i) {
            const double s = run_one(q, buf, n16, out, items, wg);
            gbs.push_back((double) bytes / s / 1e9);
            std::printf("%s iter %d: %.2f GB/s\n", kind.c_str(), i, gbs.back());
        }
        uint32_t check = 0;
        q.memcpy(&check, out, sizeof(check)).wait();
        std::vector<double> s = gbs;
        std::sort(s.begin(), s.end());
        std::printf("summary %s: median %.2f GB/s, min %.2f, max %.2f (n=%d, check %08x)\n", kind.c_str(),
                    s[s.size() / 2], s.front(), s.back(), (int) s.size(), check);
        sycl::free(p, q);
    }
    sycl::free(out, q);
    return 0;
}
