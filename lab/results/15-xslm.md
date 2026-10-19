# 15：140T 的 XSLM 与共享专家队列测量

执行时间：2026-10-20T00:27:13.989184+08:00（`env.txt:2`）。用户已确认插电、最佳性能、测量期间不使用电脑，共享 GPU 内存上限 75%。本轮未发起重启。

- 更新前 HEAD：`d7123fe1c71aecfcfa148921cf3dfc309c17b160`，已跟踪文件干净（`env.txt:3`、`env.txt:4`）。
- 更新后 HEAD：`76b68817f0f44894d025b2388fa5df1a3321f883`（`build.txt:5`）。
- 新 exe：37317632 字节，修改时间 2026-10-20T00:29:42.213907+08:00，SHA256 `2fd326aa7140d143e76dd7705ffc0ca6f538ef053d077fcad3010f4cd95d047e`（`build.txt:11`）。
- GPU：Intel(R) Arc(TM) 140T GPU (32GB)，驱动 32.0.101.8826（`env.txt:15`、`env.txt:16`）。
- 电源模式：最佳性能（`env.txt:18`）。
- 开机以来 36289.671 秒，可用物理内存 59598516224 字节（`env.txt:12`、`env.txt:13`）。

原始来源均为本轮原始目录下的相对文件名和行号。构建命令、耗时、退出码、exe 校验值见 [build.txt](15-xslm/build.txt)，各行标出原始行号。

`xslm-choice.txt` 前 15 行（原始 `xslm-choice.txt:1–15`）：

```text
problems: 0
choice: none  (the setting of the smallest median W, if below 0.95 x W(base) and below base's W in each round; none with any problem); best 16 0.9903 x base, every round below base: True; D5, D6 x base 0.9906, 1.1141 (at most 1.03)
bitwise: 12 dumps the same bytes True (sha256 731ba759d1c313cd, 32782848 bytes each); checksums the same in every run; 1-8 columns (mm8-*) the same True

W = 0.12 D1 + 0.14 D2 + 0.12 D3 + 0.62 D4 (ms; D_T = tensors x us summed over the 26 cases):
  base: median W 68.207  (1.0000 x base)  rounds 68.207 70.410 67.630
  4   : median W 131.442  (1.9271 x base)  rounds 136.255 131.442 131.325
  8   : median W 83.142  (1.2190 x base)  rounds 83.142 82.926 84.020
  16  : median W 67.543  (0.9903 x base)  rounds 66.869 68.919 67.543

median D_T by type (ms), T = 1..6 (recorded only):
  Q4_K   base:   5.849   8.324  10.443  12.277  13.999  15.368
  Q4_K   4   :   6.221  11.058  20.337  24.930  24.603  46.688
  Q4_K   8   :   5.880   8.633  12.754  14.909  15.840  25.515
  Q4_K   16  :   5.888   8.232   9.914  11.240  12.553  17.436
```

`e2e-choice.txt` 原样内容（原始 `e2e-choice.txt:1–27`）：

```text
problems: 0
add: none  (the switch of the group resolved faster than A by the most: its mean ms/token below A's by more than the larger range of the two groups; at most one; none with any problem)
segments: 1-A 2-C 3-C 4-A 5-A 6-C (10-D0 / 11-D1 left out)
greedy: g1 553ac32f017ae0be  g2 1c1c19249884638f
windows and avg T per request the same in every segment: False (recorded only)
  request 1: windows 34 34 34 34 34 34
  request 2: windows 52 49 52 52 52 52
  request 3: windows 50 50 51 49 50 48
  request 4: windows 34 34 34 34 33 34
  request 5: windows 53 56 53 54 55 53
  request 6: windows 52 52 52 53 53 53
  request 7: windows 34 34 34 34 34 33
  request 8: windows 51 51 51 51 51 51
  request 9: windows 51 51 49 51 51 50

segment  ms/token  verify ms/window  draft ms/window  tokens/window  windows
  1-A     103.861       203.43          23.82         2.189      411
  2-C     105.600       206.92          24.13         2.189      411
  3-C     105.580       207.41          24.15         2.194      410
  4-A     107.675       210.49          24.54         2.184      412
  5-A     107.255       209.26          24.29         2.179      413
  6-C     110.167       217.62          25.21         2.206      408

group means; range = (max - min) / mean over the group's 3 segments
  A: ms/token 106.264 (range 0.0359)  verify ms/window 207.72 (range 0.0340)
  C: ms/token 107.116 (range 0.0428)  verify ms/window 210.65 (range 0.0508)
  C vs A: ms/token +0.0080 against the noise 0.0428 -> faster and resolved: False; verify ms/window +0.0141 (noise 0.0508, recorded only)
```

`final-check.txt` 原样内容（原始 `final-check.txt:1–3`）：

```text
problems: 0
write: none  (e2e-choice.txt's switch, when 11-D1 (with it) ran clean and gave 10-D0's greedy and bench answers; none with any problem)
10-D0: ms/token 105.372, windows 408, all resident False, greedy 553ac32f017ae0be 1c1c19249884638f = 13/14 A (device plan path)
```

## 端到端

| 段 | 状态 | 测速请求数 / 成功数 | 来源 |
|---|---|---|---|
| 1-A | completed | 9 / 9 | `1-A/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 2-C | completed | 9 / 9 | `2-C/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 3-C | completed | 9 / 9 | `3-C/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 4-A | completed | 9 / 9 | `4-A/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 5-A | completed | 9 / 9 | `5-A/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 6-C | completed | 9 / 9 | `6-C/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 10-D0 | completed | 9 / 9 | `10-D0/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |

| 组 | 总生成毫秒 / 总 token | ms/token | 草稿接受 / 提供 |
|---|---|---|---|
| A | 286911.6 / 2700 | 106.264 | 1470 / 2747 |
| C | 289211.9 / 2700 | 107.116 | 1478 / 2759 |
| D0 | 94834.8 / 900 | 105.372 | 494 / 917 |

组汇总来源：`timing.tsv` 的对应段和请求，各字段标出原始 bench.json 行号。

| 组 | 问题 | 生成 tok/s 中位数 | 首 token 秒中位数 |
|---|---|---|---|
| A | q1 | 11.900 | 2.826 |
| A | q2 | 8.400 | 2.366 |
| A | q3 | 8.700 | 2.574 |
| C | q1 | 12.000 | 2.781 |
| C | q2 | 8.400 | 2.332 |
| C | q3 | 8.900 | 2.551 |
| D0 | q1 | 12.000 | 2.453 |
| D0 | q2 | 8.400 | 2.063 |
| D0 | q3 | 8.900 | 2.291 |

问题中位数来源：`timing.tsv` 对应组及 question 的原始字段。

| 段 | ms/token | 窗口数 | 平均 T | 草稿接受 / 提供 |
|---|---|---|---|---|
| 1-A | 103.861 | 411 | 3.2290 | 491 / 916 |
| 2-C | 105.600 | 411 | 3.2470 | 491 / 923 |
| 3-C | 105.580 | 410 | 3.2375 | 492 / 917 |
| 4-A | 107.675 | 412 | 3.2363 | 490 / 921 |
| 5-A | 107.255 | 413 | 3.2048 | 489 / 910 |
| 6-C | 110.167 | 408 | 3.2522 | 495 / 919 |
| 10-D0 | 105.372 | 408 | 3.2477 | 494 / 917 |

段来源：`timing.tsv` 的原始 bench.json 字段；窗口数和平均 T 来自 `decode.tsv` 中与 chat 请求边界匹配的行。平均 T 用各请求窗口数加权，原始日志的每请求 T 已取两位小数。

| 组 | ms/window 中位数 | draft 中位数 | tokens/window 中位数 |
|---|---|---|---|
| A | 230.960 | 24.040 | 1.960 |
| C | 239.150 | 24.930 | 2.000 |
| D0 | 229.910 | 24.150 | 2.000 |

窗口中位数来源：`decode.tsv` 的测速请求行，与各段 `request-boundaries.json` 的 chat 字节范围逐一匹配；每行保留原始 engine.log 行号。补充 `decode-requests.tsv`，逐请求指明对应的 decode 行，区分预热、贪心和测速请求。



每请求 verify 毫秒见 `decode-requests.tsv` 的 verify 列；每段按窗口数加权的 verify、草稿毫秒及窗口数见上面的判定原文。测速回答 SHA256 前 16 位和 token 数见 `bench-text.tsv`，保留原始字段行号。

| 段 | 常驻专家数 | missing from VRAM | 来源 |
|---|---|---|---|
| 1-A | 24576 | 未出现对应计数行 | `1-A/engine.log:17` |
| 2-C | 24576 | 未出现对应计数行 | `2-C/engine.log:17` |
| 3-C | 24576 | 未出现对应计数行 | `3-C/engine.log:17` |
| 4-A | 24576 | 未出现对应计数行 | `4-A/engine.log:17` |
| 5-A | 24576 | 未出现对应计数行 | `5-A/engine.log:17` |
| 6-C | 24576 | 未出现对应计数行 | `6-C/engine.log:17` |
| 10-D0 | 24514 | 62 | `10-D0/engine.log:17`, `10-D0/engine.log:24` |

第 3 节：修改前已备份日常配置，仅在 env 增加 `STRATA_GR_RED_BATCH=1`、`STRATA_GR_UP_TREE=1`，其他字节保留，JSON 与预期对象比较通过。前后 env 见 `config-change.json`。

第 7 节：write 为 none，未再修改日常配置。

B 组未做：内核判定为 `choice: none`，按手册只跑 A、C 六段。`11-D1` 未做：端到端判定为 `add: none`，按手册只跑 `10-D0`。

第 5、6 节要求记录的引擎错误行：没有。

执行状态（来源为各段 metadata.json）：

- 1-A：completed，失败请求计数 0（`1-A/metadata.json:10`、`1-A/metadata.json:13`）。
- 2-C：completed，失败请求计数 0（`2-C/metadata.json:10`、`2-C/metadata.json:13`）。
- 3-C：completed，失败请求计数 0（`3-C/metadata.json:10`、`3-C/metadata.json:13`）。
- 4-A：completed，失败请求计数 0（`4-A/metadata.json:10`、`4-A/metadata.json:13`）。
- 5-A：completed，失败请求计数 0（`5-A/metadata.json:10`、`5-A/metadata.json:13`）。
- 6-C：completed，失败请求计数 0（`6-C/metadata.json:10`、`6-C/metadata.json:13`）。
- 10-D0：completed，失败请求计数 0（`10-D0/metadata.json:10`、`10-D0/metadata.json:13`）。

重试目录：无。

引擎及工具构建均成功；16 次内核运行全部正常退出，未出现超时。七段端到端均正常完成，未记录失败、卡住或崩溃。依据为 `build.txt`、`mm-exit.txt` 和上述各段状态来源。

驱动以第 14 轮为底子，复制并适配在原始目录保存：改用 fixed15；测速 chat 包装记录返回 text 的 UTF-8 SHA256 和 completion_tokens；请求边界提取增加 verify；检查 4-token 与日常 6-token 启动路径；不发 logprobs 请求。保留固定提示词、每段九次测速、进程树清理、退出后等待 60 秒和最多三次尝试。

偏离：使用已初始化 oneAPI 的 CMD 内的顺序驱动代替手工逐行输入；内核参数、开关、运行顺序及 900 秒超时上限按手册。远程访问使用已配置的 Git SSH 别名，目标仓库相同。

数据目录中的两次端到端判定已重跑，输出与原始目录逐字节相同。只构建、运行手册指定 SYCL 后端；未修改引擎源码，未构建 CUDA、HIP。未做原因分析。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
