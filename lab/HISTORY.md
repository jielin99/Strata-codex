# 履历

## 目标与计划（2026-10-15）

- **目标**：在 Windows 11 + Arc 140T 笔记本上，让 Strata **生成更快**，手段不限。
  - 最初的设想是让 CPU、核显、NPU 一起参与推理（`docs/INTEL_NPU_HANDOFF.md` 第 5–9 行）。现在只在能提升生成速度时才这样做。
  - 读提示词变快、生成变慢的方案不要。
- **现状**：到目前只完成了「疏通」，即引擎在 Windows 核显上跑通、跑稳，偶发卡住也找到了位置。详见 `results/history-2026-10-14-15.md`。
- **第 1 阶段**（`plans/01`）：测出生成速度卡在哪里。需要三样数据：每个窗口要读多少字节、实测的读带宽上限、各部分的耗时。
  其中第 01 份手册只采集数据，内核覆盖表和字节数的计算在开发机上做。
- **第 2 阶段**：按「该部分占生成时间的比例 × 能省下的比例」排序选方向。候选有：稠密 GEMV 内核、MTP 草稿、投机参数、启动和同步开销、少读字节、NPU/CPU 分担（按净收益判断，排在最后）。
- **关闭或搁置**：卡住（结案观察）、v2 适配器（已否决）、CPU_SHARE、STEPPED。

## 履历

| 日期 | 手册 | 结论 | 一句话 |
|---|---|---|---|
| 2026-10-14 | 手工传递（第 1 轮测速） | `results/history-2026-10-14-15.md` | CPU 空转时生成慢约 12%；之前看到的「开计时更快」是机器状态漂移 |
| 2026-10-15 | 手工传递（第 2 轮 /Zi） | 同上 | 设备代码的调试信息超过 4 GB，链接失败 |
| 2026-10-15 | 手工传递（第 3 轮 MAP） | 同上 | 卡住定位到 `prefill.cpp:3859` 的 memcpy（旧适配器） |
| 2026-10-15 | 手工传递（第 4 轮适配器） | 同上 | 164 个请求 0 次卡住；v2 读入 +15%、生成 −7%，用户否决 |
| 2026-10-15 | `plans/00-cleanup.md` | `results/00-cleanup.md` | worktree 已建；待清理对象在执行前已不存在（dmp 备份保留，未做哈希比对）；引擎 HEAD 和远端一致（29825274）；笔记本推送可行。结论里的「电源模式：平衡」是电源计划，不是设置里的电源模式（手册的查法错了，已在 01 和 README 改正） |
| 2026-10-15 | `plans/01-decode-bound.md` | `results/01-decode-bound.md`，分析 `analysis/01-decode-bound.md` | 54 个请求 0 失败；读带宽 72 / 62 GB/s；verify 只用到带宽的约 20–40%（推断瓶颈在内核）；草稿约占 10%；1 小时内漂移 9–15% |
| 2026-10-15 | （开发机，未用笔记本） | `analysis/02-kernel-code.md` | 读代码 + 140T 编译目标的 ISA + UHD 730 实测：稠密 GEMV 卡在指令数；Q6_K 的 sub_sat 换成逐位等价写法，指令 −45–53%，UHD 上 +13–73%；MoE 默认内核有寄存器溢出 |
| 2026-10-15 | `plans/02-mmvq-q6k.md` | `results/02-mmvq-q6k.md`，分析 `analysis/02-kernel-code.md` 第 5 节 | 140T 上去掉 sub_sat 全部更快（1 列 +19–28%，3 列 +87–132%），校验值相同；Q6_K 有列数断崖（现状 5 列、去掉 sub_sat 后 6 列掉到约 5 GB/s），其他类型没有 |
| 2026-10-15 | `plans/03-window-t.md` | `results/03-window-t.md`，分析 `analysis/03-window-t.md` | 生成窗口只有 T=1–4（T=4 占 61%）；T=6 是读短提示词的窗口，GPU 541 ms，Q6_K 的大跌在引擎里也出现；Q6_K 去掉 sub_sat 对生成约 +3.5%（不是 6–8%），对读短提示词影响大 |
| 2026-10-16 | `plans/04-q6-swar-ab.md` | `results/04-q6-swar-ab.md`，判断 `analysis/04-q6-swar-ab.md` | 引擎开关 `STRATA_MMVQ_Q6_SWAR=1`（功能分支 `7629f0b2`）：生成每 token 130.6 → 123.1 ms（约 +6% tok/s），首 token 4.46 → 3.07 s；63 请求 0 失败；回答一致性因无文本、且采样每次不同而未能核对 |
| 2026-10-16 | （开发机，读代码 + Codex 外审） | `analysis/04-moe-hc-code.md` | hc 读走 BF16（SYCL 无 q8 路径）；默认 MoE 路径对 IQ2_XXS/IQ2_XS 不做多 token 复用，已有 `STRATA_EXPERT_SPLIT=1` 路径覆盖；05 测现成开关 |
| 2026-10-16 | `plans/05-moe-hc-env.md` | `results/05-moe-hc-env.md`，判断 `analysis/05-moe-hc-env.md` | 5 个 MoE/hc 现成开关没有一个比默认快：`STRATA_EXPERT_SPLIT=1` 加权 +18.8%、`STRATA_GR_DOWN_SLICED=0` +7.6%、`STRATA_GR_NORM_SPLIT=0` +1.5%、lane 4/16 无差；默认三段差 ≤0.3%；72 请求 0 失败 |
| 2026-10-16 | （开发机，复盘 + Codex 外审） | `analysis/06-retro.md` | 复盘：没先读 `docs/A770_SPEED_SPEC.md` 等已有调查、按好试而非时间占比选目标、每轮只带一个测量问题；⚠️ MoE 约占窗口 45%、每列约 +27 ms；第一个候选 `STRATA_Q2_SWAR=1`（功能分支 `870dee5e`）：UHD 730 上 48 层输出逐字节相同、MoE 窗口约 −12%，140T 编译目标主循环指令 4,711 → 1,843 |
| 2026-10-16 | `plans/06-decide.md` | `results/06-decide.md`，判断 `analysis/06-decide.md` | `STRATA_Q2_SWAR=1`：每 token 122.3 → 118.2 ms（约 +3.5% tok/s），三对相邻段都更快，140T 上 MoE 窗口 −11～−13%；`--mtp-q4 all` 慢 5.3%（草稿每窗口 +16 ms），不用；贪心回答 10 段哈希全同，日常配置已开 SWAR；D 组因手册判断条件写错没测（共享显存 75% 实际已生效，日常已是全常驻）；开发机发现 hc 读的 up 内核占约 75%，收尾移出行循环后 UHD 730 上 hc 读 −46～−64%（引擎的链接选项）、逐位相同 |
| 2026-10-16 | `plans/07-gr-up.md` | `results/07-gr-up.md`，判断 `analysis/07-gr-up.md` | `STRATA_GR_UP_EPI=1`：每 token 120.7 → 114.5 ms（约 +5.4% tok/s），三对相邻段都更快；140T 上 hc 读 −8～−15%，每窗口约省 8.5 ms，和端到端一致；逐位核对、`gr_bench` 校验和、贪心哈希全同（也和 06 同）；日常配置已开 Q2 SWAR 和 GR_UP_EPI；140T 上 up 原本只占 hc 读的约 40%（UHD 730 上 75%），现在 down + reduce 占 55–60% |
