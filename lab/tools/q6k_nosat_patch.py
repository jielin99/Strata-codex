"""q6k_nosat_patch: write a copy of native_mmvq.dp.cpp whose wide Q6_K kernel drops the per-byte saturating subtract.
    python q6k_nosat_patch.py <engine native_mmvq.dp.cpp> <output .dp.cpp>
Each byte the kernel subtracts 32 from is in 0..63 (4 low bits | 2 high bits), so v - 32 never saturates, and
((v | 0x80) - 0x20) ^ 0x80 per byte (no borrow between bytes, since v | 0x80 >= 0x20) is the same bits as the
sub_sat it replaces. Only native_mmvq_q6k_wide_kernel changes; the engine file is read, never written. The output
needs -I<engine>/sycl/src/kernels/cuda for its relative include."""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
start = s.index("void native_mmvq_q6k_wide_kernel(")
end = s.index("// SYCL port: the wide Q6_K kernel with its weight loads issued U steps ahead")
body = s[start:end]
old0 = ("vi0[p] = dpct::vectorized_binary<sycl::char4>((vl[p] & 0x0f0f0f0f) | ((vh[p] << 4) & 0x30303030), "
        "0x20202020, dpct::sub_sat());")
old1 = ("vi1[p] = dpct::vectorized_binary<sycl::char4>(((vl[p] >> 4) & 0x0f0f0f0f) | (((vh[p] >> 4) << 4) & 0x30303030), "
        "0x20202020, dpct::sub_sat());")
new0 = ("vi0[p] = (int) (((((uint32_t) vl[p] & 0x0f0f0f0fu) | (((uint32_t) vh[p] << 4) & 0x30303030u)) | 0x80808080u) "
        "- 0x20202020u) ^ 0x80808080u;")
new1 = ("vi1[p] = (int) (((((uint32_t) vl[p] >> 4 & 0x0f0f0f0fu) | ((((uint32_t) vh[p] >> 4) << 4) & 0x30303030u)) "
        "| 0x80808080u) - 0x20202020u) ^ 0x80808080u;")
if body.count(old0) != 1 or body.count(old1) != 1:
    sys.exit("q6k_nosat_patch: the wide Q6_K kernel is not the expected one (engine changed?)")
body = body.replace(old0, new0).replace(old1, new1)
open(dst, "w", encoding="utf-8", newline="\n").write(s[:start] + body + s[end:])
print("q6k_nosat_patch: wrote", dst)
