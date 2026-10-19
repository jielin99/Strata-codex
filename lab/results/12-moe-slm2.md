# 12：140T 上 MoE gate/up 共享内存开关

执行时间：2026-10-19T09:17:01.555489+08:00（`env.txt:1`）。用户已确认插电、电源模式“最佳性能”、实验期间不使用电脑，共享 GPU 内存上限保持 75%。本轮未发起重启（`env.txt:5`、`env.txt:6`）。

- 更新前引擎及 exe：`d35f55e49ea390f7121f1d1b4a21c682184e8183`；`env.txt:4` 记录大小、修改时间和 SHA256。已跟踪文件无改动（`env.txt:3`）。
- 更新后引擎：`a3b39b0638bbe3fb1a655b4bc9b0d1f879f13aca`（`build.txt:5`）。
- 新 exe：34895872 字节，修改时间 2026-10-19T09:19:09.327548+08:00，SHA256 `52c3e8f52ffb05da93c16aa8237176b055e924f006d4f5b2891313eda4812923`（`build.txt:11`）。
- GPU：Intel(R) Arc(TM) 140T GPU (32GB)，Windows 驱动 32.0.101.8826（`env.txt:91`）；运行时驱动见 `mp-1-off.tsv:2`。
- 电源模式：最佳性能，读取到对应模式标识（`env.txt:71`）。
- 开机以来 102123.843 秒（`env.txt:7`）。
- 可用物理内存：57578132 KiB（`env.txt:82`）。

原始文件保留在本机原始目录。下文来源均为该目录下的相对文件名和行号。

## 构建与测量

引擎仅快进更新指定文件，完整构建退出码为零。实验工具逐条编译、链接；命令、耗时、退出码和 exe 校验信息见 [build.txt](12-moe-slm2/build.txt)，每行标注原始来源。

运行顺序、参数与手册一致；工具使用链接选项 `-ze-opt-greater-than-4GB-buffer-required`。预热和正式测量的退出码见 [mp-exit.txt](12-moe-slm2/mp-exit.txt)，环境见 [env-strata.txt](12-moe-slm2/env-strata.txt)。

## 判定

下方原样引用 `choice.txt`：

```text
problems: 0
choice: 2  (a setting with W < 0.98 x W(off), the smaller W of the two; none with any problem)
integrity: 15 exit codes, 9 stderr files, env-strata.txt, 3 ngp files
equal outputs across the 9 runs: 154 keys with checksum and gu_checksum, 0 differ

W = 0.12 t1 + 0.14 t2 + 0.12 t3 + 0.62 t4 (t = median us/layer of T1..T4, window, dram, all):
  off: t1..t4 554.6 909.4 1337.6 1682.8  W 1397.7
  1: t1..t4 512.8 870.2 1273.9 1567.2  W 1307.9
  2: t1..t4 512.8 867.3 1238.9 1556.9  W 1296.9
  W(1) / W(off) = 0.9357
  W(2) / W(off) = 0.9279
  round 1 off: W 1408.4
  round 1 1: W 1296.6
  round 1 2: W 1295.6
  round 2 1: W 1309.7
  round 2 2: W 1295.7
  round 2 off: W 1388.0
  round 3 2: W 1326.0
  round 3 off: W 1397.7
  round 3 1: W 1309.3

recorded only (median us/layer, off / 1 / 2):
  T3 dram all: 1337.6 / 1273.9 / 1238.9
  T3 dram gu: 900.6 / 825.4 / 825.4
  T3 dram down: 434.3 / 438.1 / 440.0
  T3 cached all: 1232.7 / 1161.7 / 1152.3
  T3 cached gu: 815.3 / 748.8 / 732.8
  T3 cached down: 421.6 / 415.4 / 419.8
  G10x2 dram all: 714.6 / 697.5 / 665.4
  G10x2 dram gu: 486.2 / 464.8 / 441.2
  G10x2 dram down: 226.1 / 227.9 / 223.3
  G10x2 cached all: 654.9 / 634.6 / 619.3
  G10x2 cached gu: 428.4 / 421.6 / 394.9
  G10x2 cached down: 218.3 / 222.3 / 220.5
```

组跨步核对原始来源：`ngp-1.txt:58`（末行，公开副本保留最后三行）；`ngp-2.txt:58`（末行，公开副本保留最后三行）；`ngp-off.txt:58`（末行，公开副本保留最后三行）。

## 偏离、失败与未做

本次引擎构建已更新组跨步核对工具，三种设置均按手册运行。

首次从未初始化 oneAPI 的新 CMD 启动，全部工具立即返回 `3221225781`（`0xC0000135`），没有生成测量行（`startup-failure/mp-exit.txt:1` 至 `startup-failure/mp-exit.txt:15`）。首次文件及退出码完整保留于原始目录的 `startup-failure/`，没有清空原记录。随后初始化 oneAPI 环境，重新执行完整预热、轮换测量与组跨步核对序列；正文判定引用重跑结果。此为执行偏离。

A/B 驱动首次在启动服务前发生 `SyntaxError: unterminated string literal`。将源码前缀截取改为匹配独立函数定义行后继续；该次没有创建测量段目录。失败脚本和说明保留在原始目录（`driver-import-failure.txt:1`）。

## 端到端 A/B

| 段 | 状态 | 成功测速请求 | 失败请求 | 来源 |
|---|---|---|---|---|
| 1-A | completed | 9 | 0 | `1-A/metadata.json:10`、`1-A/metadata.json:13`；成功数由本段 bench.json 的 requests 逐项计数，字段行号见 timing.tsv |
| 2-B | completed | 9 | 0 | `2-B/metadata.json:10`、`2-B/metadata.json:13`；成功数由本段 bench.json 的 requests 逐项计数，字段行号见 timing.tsv |
| 3-B | completed | 9 | 0 | `3-B/metadata.json:10`、`3-B/metadata.json:13`；成功数由本段 bench.json 的 requests 逐项计数，字段行号见 timing.tsv |
| 4-A | completed | 9 | 0 | `4-A/metadata.json:10`、`4-A/metadata.json:13`；成功数由本段 bench.json 的 requests 逐项计数，字段行号见 timing.tsv |
| 5-A | completed | 9 | 0 | `5-A/metadata.json:10`、`5-A/metadata.json:13`；成功数由本段 bench.json 的 requests 逐项计数，字段行号见 timing.tsv |
| 6-B | completed | 9 | 0 | `6-B/metadata.json:10`、`6-B/metadata.json:13`；成功数由本段 bench.json 的 requests 逐项计数，字段行号见 timing.tsv |

没有重试或跳过的测量段。

| 组 | 总生成 ms / 总 token | ms/token | 草稿接受 / 提供 | 来源 |
|---|---|---|---|---|
| A | 279402.3 / 2700 | 103.482 | 1530 / 2700 | timing.tsv 对应组各行的原始来源 |
| B | 280539.8 / 2700 | 103.904 | 1514 / 2707 | timing.tsv 对应组各行的原始来源 |

| 组 | 问题 | 生成 tok/s 中位数 | 首 token 秒中位数 | 来源 |
|---|---|---|---|---|
| A | q1 | 12.500 | 2.940 | timing.tsv 的 question=1 行 |
| A | q2 | 8.700 | 2.436 | timing.tsv 的 question=2 行 |
| A | q3 | 8.600 | 2.664 | timing.tsv 的 question=3 行 |
| B | q1 | 12.500 | 2.886 | timing.tsv 的 question=1 行 |
| B | q2 | 8.600 | 2.410 | timing.tsv 的 question=2 行 |
| B | q3 | 8.700 | 2.596 | timing.tsv 的 question=3 行 |

| 组 | ms/window 中位数 | draft 中位数 | tokens/window 中位数 |
|---|---|---|---|
| A | 228.550 | 23.880 | 2.000 |
| B | 223.020 | 23.650 | 1.960 |

decode 来源：`decode.tsv` 中与各段 `request-boundaries.json` 的 chat 请求字节范围匹配的行；每行标出原始 `engine.log` 行号。

| 段 | ms/token | 来源 |
|---|---|---|
| 1-A | 104.338 | 1-A/bench.json；逐项行号见 timing.tsv |
| 2-B | 104.783 | 2-B/bench.json；逐项行号见 timing.tsv |
| 3-B | 102.995 | 3-B/bench.json；逐项行号见 timing.tsv |
| 4-A | 103.571 | 4-A/bench.json；逐项行号见 timing.tsv |
| 5-A | 102.538 | 5-A/bench.json；逐项行号见 timing.tsv |
| 6-B | 103.933 | 6-B/bench.json；逐项行号见 timing.tsv |

贪心核对（原始来源见 `greedy.tsv`）：

```text
g1: all equal
559a75356eb39f09: 1-A, 2-B, 3-B, 4-A, 5-A, 6-B
Comparison with 08: False

g2: all equal
a6c46dc05f536ef5: 1-A, 2-B, 3-B, 4-A, 5-A, 6-B
Comparison with 08: False
```

第 5 节：未改。未满足的条件编号：4；逐项条件为 [True, True, True, False, True]。

相邻配对 B 比 A 的 ms/token 小：[False, True, False]（`decision.json`）。

引擎错误行（排除 no error 等误中）：没有（原始各段 `engine.log` 全文扫描）。

驱动以 08 为底子，沿用 07 的六段流程：改为本轮配置开关，清理进程中全部 STRATA_ 变量并按副本加载；不运行 PROFILE 段；增加本轮五项配置条件及错误行检查。保留贪心哈希算法、预热、九次短请求、请求日志字节边界、最多三次重试和退出后等待 60 秒。

本次只编译并运行 SYCL 后端；未编译 CUDA、HIP。没有改动引擎源码。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
