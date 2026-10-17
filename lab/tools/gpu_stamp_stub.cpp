// gpu_stamp_stub: the engine's profile stamp (verify_kernels.dp.cpp), which fused_gr.dp.cpp references, as an empty
// function, so sycl/src/kernels/gr_bench.cpp links against fused_gr.dp.cpp alone (as gr_apply_parity.cpp does).
// gr_bench never turns the profile on, so the stamp is never called.
namespace strata::kernels { void gpu_stamp(unsigned long long*, int, void*) {} }
