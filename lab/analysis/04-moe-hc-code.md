# 04 的分析：MoE 专家和 hc 读的代码（开发机，读代码，2026-10-16，已按 Codex 外审修订）

引擎 commit `29825274`，只看 SYCL。文件缩写：V = `sycl/src/core/verify.cpp`，IQ = `sycl/src/kernels/cuda/iq_kernels.dp.cpp`，
GR = `sycl/src/kernels/cuda/fused_gr.dp.cpp`。证据等级：✅ 已验证、⚠️ 推断、⬜ 未验证。
时间数字来自 `analysis/01` 第 3 节（PROFILE 段，平均 T≈3.2）。PROFILE 本身会插入时间戳内核，所以偏大；而且这些段里混有 PLE、残差、路由等别的工作（`analysis/01` 第 3 节末尾）。

## 1. 结论
1. ✅ **hc 读的是 BF16 权重。** `STRATA_HC_Q8` 默认关（`sycl/src/core/native_dense.cpp:34`）；SYCL 的 `fused_gr_read_multi` 只跑 BF16 内核
   （权重读取在 GR:546-550、643-656），没有 Q8_0 的读法（GR:1882 的注释 "the Q8_0 reads (S23 STRATA_HC_Q8) are not built"）。
   - 每次 hc 读约 13.2 MB（down 6.55 MB + up 6.55 MB + 小向量）。主体 48 层、每层 2 次，单组窗口共 96 次，约 1.27 GB；
     另有输出头前的一次（V:1590-1604），窗口拆成两组时次数还会增加（V:823、835）。路由 BF16 每层 2.62 MB，合计约 0.13 GB。
   - ⚠️ 按「权重字节 ÷ PROFILE 时间」折算：hc-read0 0.64 GB ÷ 32.4 ms ≈ 20 GB/s；hc-read1+router 0.76 GB ÷ 48.5 ms ≈ 16 GB/s，
     约为读带宽 72.3 GB/s 的 22–27%。这只说明「有效权重吞吐低」，分不出计算、缓存、并行度和启动各占多少。
   - 默认路径（sliced）每次 hc 读 4 个内核：norm、down、reduce、up（GR:1762-1765、1793-1807、1867-1873）。
     其中 up 内核有 160 个工作组（GR:601-602），每个工作组都把同一份 320 维的部分和重新相加、做除法和 SiLU（GR:624-632），是重复计算，⬜ 占比没测。
   - 已有的可测变体：`STRATA_GR_NORM_SPLIT=0`、`STRATA_GR_DOWN_SLICED=0`、`STRATA_GR_DOWN_DIRECT=0`（GR:376-378、582-598），
     以及 `STRATA_GR_V3=1`（两个内核，求和顺序不同，不逐位相同，GR:1627 附近）。
2. ✅ **默认路径没有给 IQ2_XXS 和 IQ2_XS 的 gate/up 做多 token 复用。**
   - 默认走 `native_gu_kernel` → `row_entries`（V:1438-1442 → IQ:5130-5134 → IQ:4182-4185 → IQ:4111-4120 → IQ:1842-1853）。
   - `Multi<TY>::has` 只对 18（IQ3_XXS）、21（IQ3_S）、22（IQ2_S）、20（IQ4_NL）、42（Q2_0）为真（IQ:1587-1752）。
     16（IQ2_XXS）和 17（IQ2_XS）没有，一个专家被窗口里 k 个 token 选中时，同一行权重解码 k 次（IQ:1786-1812）。
   - 模型里 IQ2_XXS 9 层、IQ2_XS 10 层，共 19/48 层的 gate/up（`results/01-decode-bound/tensors.tsv`）。
   - **引擎里已经有另一条路径**：`STRATA_EXPERT_SPLIT=1`（IQ:2823、4184-4193）改用 `native_gu_multi_kernel`。它对 16、17 也有专门实现
     （`Split<16>` IQ:872、`Split<17>` IQ:926），解码放在 token 循环外，还有 3 个 token 的专门分支。这条路径每行 32 条 lane，和默认的 8 条不同，
     ⚠️ 推断不逐位相同，⬜ 没有核对。
3. ✅ **默认路径中，同一专家被 3 个 token 选中时，有 Multi 的类型也要解码两遍**：`row_entries` 先 4 个一组、再 2 个一组、最后单个（IQ:1793-1811），
   3 = 2 + 1；没有 Multi 的 16、17 是 1 + 1 + 1。
4. ✅ **MoE 的计时口径**：PROFILE 的「VRAM hits」段只包住一次 `native_expert_grouped`（V:1460-1462 两个时间戳之间），默认是 3 个内核：
   gate/up、SwiGLU+q8_1（融合）、down（IQ:5130-5139、5182-5197、5229-5235；`STRATA_GROUPED_V1` 才把中间拆成两个）。
   输入量化（V:1402-1407）和 combine（V:1502-1515，属于「copy+combine」段）不在这段里。
   - ⚠️ 这段约 120 ms/窗口，按专家字节折算约 7–23 GB/s（`analysis/01`）。重复解码的次数不等于从内存读的次数（第二遍很可能命中缓存）。
   - ✅ 激活没有跨输出行复用：gate/up 每个输出行都为每个 token 重新读一遍 q8_1 激活（IQ:1768-1777），down 也是（IQ:1995-2022）。
   - ✅ `STRATA_GU_LANES` / `STRATA_DOWN_LANES`（4/8/16/32，IQ:4100-4109）只要环境变量就能改，但会改变累加的分配和归约顺序（IQ:803-817、1763-1781），
     **不保证逐位相同**；值在第一次调用后缓存，不同配置要分进程跑。
   - 02 在容器编译器、140T 编译目标上看到这些内核有寄存器溢出（`analysis/02` 第 2.4 节）。这不是笔记本驱动的实测。
5. 启动次数：单组窗口、默认配置下，每层光 hc 读和一次专家调用就有 2×4 + 3 = 11 次启动，48 层共 528 次，还没算路由、量化、combine。
   默认的专家内核、SwiGLU 和 hc up 都带 `use_root_sync` 属性（IQ:4116-4120、4140-4144、5183-5193，GR:1864-1873）。
   ⬜ 这些只说明值得测启动成本，不能说明它占主要时间。

## 2. 可能的方向（都还没测）
| 方向 | 改动 | 是否逐位相同 | 先要测什么 |
|---|---|---|---|
| `STRATA_EXPERT_SPLIT=1`（已有路径，覆盖 IQ2_XXS/IQ2_XS 的多 token） | 只改环境变量 | ⚠️ 推断不是（lane 数不同），⬜ 要核对 | MoE 内核按类型、组大小的速率；输出差异 |
| MoE 每行 lane 数 | 只改环境变量 | 不保证 | 同上 |
| 默认路径给 16、17 补 Multi | 改引擎 | 目标是逐位相同，待实现和验证 | 先看上两项的数据 |
| hc 读的已有变体（`STRATA_GR_*`） | 只改环境变量 | `GR_V3` 不是；其他 ⬜ 要核对 | hc 读在 140T 上按 T 的速率 |
| hc up 内核去掉重复计算 | 改引擎 | 目标是逐位相同 | 同上 |
| hc 改用 q8 | 改引擎（SYCL 没有） | 不相同，会改变数值 | 要你先决定能否接受 |

## 3. 下一步
写 MoE 和 hc 读的测量工具，调用引擎的 `native_expert_grouped` 和 hc 读函数。测项要包括：
- 按模型真实的 48 层权重、超过缓存的工作集轮换（参考 `sycl/src/kernels/native_grouped_parity.cpp:305-353、404-437` 的跨层权重、图回放和混合分组的做法）。
- 窗口 T=1–4，不同专家数、每个专家的 token 数分布（混合组大小），gate/up 和 down 分开计时。
- 默认、`STRATA_EXPERT_SPLIT=1`、不同 lane 数、`STRATA_GR_*` 变体，每种配置单独一个进程，输出逐字节比较。
- ⬜ 窗口里每层实际有几个不同专家，这个工具测不到，要从引擎里取（之后另定）。

## 外审处理记录（Codex，一轮，2026-10-16）
- 必修 2 条都采纳：已有的 `STRATA_EXPERT_SPLIT` 路径；「VRAM hits」段的口径（3 个内核，combine 另计）。
- 建议 4 条都采纳：折算只表示有效吞吐；激活不复用和测量工具的测项；hc up 的重复计算和已有开关；lane 不保证逐位相同、启动次数和 `use_root_sync`。
- 措辞都已改：hc 不走 q8 的证据改为引用权重读取；「96 次」「4 个内核」「3 = 2 + 1」「逐位相同」加限定；速率写成字节 ÷ 时间。
- 只剩措辞类问题，按规范不再审第二轮。
