# 04 的分析：MoE 专家和 hc 读的代码（开发机，读代码，2026-10-16）

引擎 commit `29825274`，只看 SYCL。文件缩写：V = `sycl/src/core/verify.cpp`，IQ = `sycl/src/kernels/cuda/iq_kernels.dp.cpp`，
GR = `sycl/src/kernels/cuda/fused_gr.dp.cpp`。证据等级：✅ 已验证、⚠️ 推断、⬜ 未验证。
时间数字来自 `analysis/01` 第 3 节（PROFILE 段，平均 T≈3.2；PROFILE 本身会插入时间戳内核，所以偏大）。

## 1. 结论
1. ✅ **hc 读的是 BF16，q8 路径在 SYCL 上不存在。** `STRATA_HC_Q8` 默认关（`sycl/src/core/native_dense.cpp:34`），而且 SYCL 的
   `fused_gr_read_multi` 直接返回 false（GR:1883，注释 "the Q8_0 reads (S23 STRATA_HC_Q8) are not built"）。
   - 每次 hc 读约 13.3 MB（down 6.55 MB + up 6.55 MB + 小向量），每层 2 次，每个窗口 96 次，约 1.27 GB；路由 BF16 每层 2.62 MB，合计约 0.13 GB。
   - ⚠️ 按 PROFILE 的时间折算：hc-read0 32.4 ms / 0.64 GB ≈ 20 GB/s；hc-read1+router 48.5 ms / 0.76 GB ≈ 16 GB/s。只有读带宽的 22–28%。
   - 每次 hc 读是 4 个内核（GR:1757-1873），其中 norm 和 reduce 只有十几个工作组，⚠️ 推断主要花在启动和延迟上。
2. ✅ **IQ2_XXS 和 IQ2_XS 的 gate/up 没有多 token 版本。** `Multi<TY>::has` 只对 18（IQ3_XXS）、21（IQ3_S）、22（IQ2_S）、20（IQ4_NL）、
   42（Q2_0）为真（IQ:1587-1730）。这两种类型时，一个专家被窗口里 k 个 token 选中，同一行权重要解码 k 次（IQ:1786-1812 的 `row_entries`）。
   模型里 IQ2_XXS 9 层、IQ2_XS 10 层，共 19/48 层的 gate/up（`results/01-decode-bound/tensors.tsv`）。
3. ✅ **同一专家被 3 个 token 选中时，其他类型也要解码两遍**：`row_entries` 先走 4 个一组，再走 2 个一组，最后单个（IQ:1793-1811），3 = 2 + 1。
4. ⚠️ MoE（VRAM hits）约 120 ms/窗口，按专家字节折算约 7–23 GB/s（`analysis/01`）。每层 MoE 是 gate/up、swiglu+量化、down、combine 4 个内核，
   gate/up 默认每行 8 条 lane（`STRATA_GU_LANES` / `STRATA_DOWN_LANES` 可改为 4/16/32，IQ:4100-4109，只需环境变量）。
   02 已看到这些内核在 140T 编译目标上有寄存器溢出。⬜ 每个窗口每层实际有几个不同专家、每种类型的速率，都还没测。

## 2. 可能的方向（都还没测，按「能否不改代码先测」排列）
| 方向 | 改动 | 是否逐位相同 | 先要测什么 |
|---|---|---|---|
| MoE 每行 lane 数 | 只改环境变量 | ⚠️ 推断不是（求和顺序变了） | MoE 内核在 140T 上按类型、token 数、lane 数的速率 |
| IQ2_XXS / IQ2_XS 的多 token 版本 | 改引擎 | 可以做成相同（其他类型的 Multi 就是这样写的，⬜ 要核对） | 同上，看这两种类型多 token 时慢多少 |
| hc 读的内核 | 改引擎 | 可以做成相同 | hc 读在 140T 上按 T 的速率 |
| hc 改用 q8 | 改引擎（SYCL 没有） | 不相同，会改变数值 | 要你先决定能否接受 |

## 3. 下一步
写一个 MoE 内核的测量工具（和 `mmvq_lab` 同样的做法，调用引擎的 `native_expert_grouped`），在 140T 上测每种类型、每组 1–4 个 token、
不同 lane 数的速率；hc 读同样测 T=1–4。数据回来以后，再决定改哪一处。
