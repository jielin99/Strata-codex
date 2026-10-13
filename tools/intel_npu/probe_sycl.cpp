// probe_sycl.cpp: what the SYCL runtime reports for each device, as JSON on stdout.
//
// Read-only. It answers the questions the native Windows engine (PR #2079) gates on - ext_intel_free_memory and
// ext_oneapi_graph - plus what the engine's kernels need (fp16, fp64, a sub-group size of 32: sycl/CMakeLists.txt
// builds with -fsycl-default-sub-group-size=32) and whether the device's memory is the host's (host_unified_memory,
// how PR #2110/#2114 tell an integrated GPU). One tiny kernel per GPU checks that a 32-wide sub-group really runs.
// No large allocation: whether the expert cache's one big allocation fits is the engine's own test.
//
// Build (Windows, after oneAPI setvars.bat):  icx -fsycl /O2 /EHsc probe_sycl.cpp /Feprobe_sycl.exe
// Build (Linux):                              icpx -fsycl -O2 probe_sycl.cpp -o probe_sycl
// Exit code: 0 when at least one Level Zero GPU is found, 2 otherwise.
#include <sycl/sycl.hpp>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <string>
#include <vector>

namespace {

std::string quoted(const std::string& s) {
    std::string out = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { out += '\\'; out += (char) c; }
        else if (c < 0x20) { char b[8]; std::snprintf(b, sizeof b, "\\u%04x", c); out += b; }
        else out += (char) c;
    }
    return out + "\"";
}

const char* backend_name(sycl::backend b) {
    switch (b) {
    case sycl::backend::ext_oneapi_level_zero: return "level_zero";
    case sycl::backend::opencl: return "opencl";
    default: return "other";
    }
}

std::string env_or_null(const char* name) {
    const char* v = std::getenv(name);
    return v ? quoted(v) : "null";
}

// One field: "name": value, or "name": null plus the error text when the query throws.
struct Obj {
    std::string body;
    void raw(const char* k, const std::string& v) { body += (body.empty() ? "" : ",") + quoted(k) + ":" + v; }
    template <class F> void get(const char* k, F f) {
        try { raw(k, f()); }
        catch (const std::exception& e) { raw(k, "null"); raw((std::string(k) + "_error").c_str(), quoted(e.what())); }
    }
    std::string str() const { return "{" + body + "}"; }
};

std::string b(bool v) { return v ? "true" : "false"; }
std::string u(uint64_t v) { return std::to_string(v); }

// 64 work-items in sub-groups of 32: each sub-group's sum of its ids must arrive in every lane.
std::string sub_group_32_check(const sycl::device& d) {
    sycl::queue q(d);
    std::vector<int> out(64, -1);
    {
        sycl::buffer<int> buf(out.data(), sycl::range<1>(64));
        q.submit([&](sycl::handler& h) {
            sycl::accessor a(buf, h, sycl::write_only);
            h.parallel_for(sycl::nd_range<1>(64, 64), [=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
                auto sg = it.get_sub_group();
                a[it.get_global_id(0)] = sycl::reduce_over_group(sg, (int) sg.get_local_id()[0], sycl::plus<int>()) +
                                         1000 * (int) sg.get_local_range()[0];
            });
        });
    }
    const int want = 31 * 32 / 2 + 1000 * 32;   // lanes 0..31 summed, and the sub-group's size
    for (int v : out)
        if (v != want) return quoted("wrong result " + std::to_string(v) + ", expected " + std::to_string(want));
    return quoted("ok");
}

std::string device_json(unsigned index, const sycl::device& d) {
    Obj o;
    o.raw("index", u(index));
    o.get("name", [&] { return quoted(d.get_info<sycl::info::device::name>()); });
    o.raw("backend", quoted(backend_name(d.get_backend())));
    o.raw("is_gpu", b(d.is_gpu()));
    o.get("vendor_id", [&] { return u(d.get_info<sycl::info::device::vendor_id>()); });
    o.get("driver_version", [&] { return quoted(d.get_info<sycl::info::device::driver_version>()); });
    o.get("version", [&] { return quoted(d.get_info<sycl::info::device::version>()); });
    o.get("pci_device_id", [&] {
        if (!d.has(sycl::aspect::ext_intel_device_id)) return std::string("null");
        char hex[16];
        std::snprintf(hex, sizeof hex, "%04x", (unsigned) d.get_info<sycl::ext::intel::info::device::device_id>());
        return quoted(hex);
    });
    o.get("host_unified_memory", [&] { return b(d.get_info<sycl::info::device::host_unified_memory>()); });
    o.get("global_mem_size", [&] { return u(d.get_info<sycl::info::device::global_mem_size>()); });
    o.get("max_mem_alloc_size", [&] { return u(d.get_info<sycl::info::device::max_mem_alloc_size>()); });
    o.get("max_compute_units", [&] { return u(d.get_info<sycl::info::device::max_compute_units>()); });
    o.get("max_work_group_size", [&] { return u(d.get_info<sycl::info::device::max_work_group_size>()); });
    o.get("local_mem_size", [&] { return u(d.get_info<sycl::info::device::local_mem_size>()); });
    o.get("sub_group_sizes", [&] {
        std::string s = "[";
        for (size_t v : d.get_info<sycl::info::device::sub_group_sizes>()) s += (s.size() > 1 ? "," : "") + u(v);
        return s + "]";
    });
    // the two the native Windows engine refuses to start without (PR #2079)
    o.raw("ext_intel_free_memory", b(d.has(sycl::aspect::ext_intel_free_memory)));
    o.get("free_memory", [&] {
        if (!d.has(sycl::aspect::ext_intel_free_memory)) return std::string("null");
        return u(d.get_info<sycl::ext::intel::info::device::free_memory>());
    });
    o.raw("ext_oneapi_graph", b(d.has(sycl::aspect::ext_oneapi_graph)));
    o.raw("fp16", b(d.has(sycl::aspect::fp16)));
    o.raw("fp64", b(d.has(sycl::aspect::fp64)));
    o.raw("usm_device_allocations", b(d.has(sycl::aspect::usm_device_allocations)));
    o.raw("usm_host_allocations", b(d.has(sycl::aspect::usm_host_allocations)));
    o.raw("usm_shared_allocations", b(d.has(sycl::aspect::usm_shared_allocations)));
    if (d.is_gpu()) o.get("sub_group_32_kernel", [&] { return sub_group_32_check(d); });
    return o.str();
}

}  // namespace

int main() {
    // Read before the first SYCL call: the runtime can set ZES_ENABLE_SYSMAN itself while it starts (seen in the
    // oneAPI 2025.3.2 image: env -u ZES_ENABLE_SYSMAN, and it read back as "1" after the device list).
    const std::string env_selector = env_or_null("ONEAPI_DEVICE_SELECTOR");
    const std::string env_sysman = env_or_null("ZES_ENABLE_SYSMAN");
    const std::string env_relaxed = env_or_null("UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS");
    std::string devices;
    bool level_zero_gpu = false;
    std::string error = "null";
    try {
        const auto all = sycl::device::get_devices();
        for (unsigned i = 0; i < all.size(); ++i) {
            devices += (devices.empty() ? "" : ",\n    ") + device_json(i, all[i]);
            if (all[i].is_gpu() && all[i].get_backend() == sycl::backend::ext_oneapi_level_zero) level_zero_gpu = true;
        }
    } catch (const std::exception& e) {
        error = quoted(e.what());
    }
    std::printf("{\n  \"scope\": \"SYCL device capabilities and one tiny sub-group kernel; not Strata inference\",\n");
    std::printf("  \"env\": {\"ONEAPI_DEVICE_SELECTOR\": %s, \"ZES_ENABLE_SYSMAN\": %s, "
                "\"UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS\": %s},\n",
                env_selector.c_str(), env_sysman.c_str(), env_relaxed.c_str());
    std::printf("  \"error\": %s,\n  \"devices\": [\n    %s\n  ]\n}\n", error.c_str(), devices.c_str());
    return level_zero_gpu ? 0 : 2;
}
