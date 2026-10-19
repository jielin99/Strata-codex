# 14：140T 上 hc up / reduce 核对

执行时间：2026-10-19T17:12:03.098023+08:00（`env.txt:2`）。用户已确认插电、最佳性能、测量期间不使用电脑，共享 GPU 内存上限 75%。本轮未发起重启（`env.txt:11`）。

- 更新前 HEAD：`8b5639257ebad17d673a6b96a68b6962cfb3d33e`，已跟踪文件干净（`env.txt:3`、`env.txt:4`）。
- 更新后 HEAD：`d7123fe1c71aecfcfa148921cf3dfc309c17b160`（`build.txt:5`）。
- 新 exe：35180544 字节，修改时间 2026-10-19T17:14:09.474580+08:00，SHA256 `2ee3648c42dcb87b3eba852e25f2180c2add92fc80df3e7af39bc1fae548297d`（`build.txt:11`）。
- GPU：Intel(R) Arc(TM) 140T GPU (32GB)，驱动 32.0.101.8826（`env.txt:15`、`env.txt:16`）。
- 电源模式：最佳性能（`env.txt:18`）。
- 开机以来 10177.078 秒，可用物理内存 59603812352 字节（`env.txt:12`、`env.txt:13`）。

原始来源均为本轮原始目录下的相对文件名和行号。

## 构建与内核判定

引擎仅快进更新并构建手册指定 SYCL 后端。命令、耗时、退出码及文件校验值见 [build.txt](14-hc-up/build.txt)，各行标出原始行号。工具命令逐条检查退出码，运行前在同一 CMD 初始化 oneAPI。

`hcup-choice.txt` 原样内容（原始 `hcup-choice.txt:1–49`）：

```text
problems: 0
choice: e2e  (e2e: W(both) < 0.9 x W(base); none with any problem)
bitwise: gr_apply_parity base = rb True; base = both True (0 of 32 cases differ); gr_bench base and rb = the default read's checksums; both differs at T []
bitwise both: True

median us (3 rounds): span / norm down reduce up, T = 1..6
  base T1:   287.7 /   15.9  105.4   32.4  129.0
  base T2:   305.1 /   19.5  108.0   30.3  145.6
  base T3:   348.8 /   22.5  114.0   31.6  172.2
  base T4:   389.4 /   25.8  119.6   39.3  199.7
  base T5:   431.9 /   29.4  126.1   40.2  231.9
  base T6:   473.6 /   34.8  132.9   40.4  259.5
  rb   T1:   268.7 /   15.5   99.3   19.9  130.0
  rb   T2:   288.0 /   17.2  104.3   19.9  142.2
  rb   T3:   317.1 /   20.9  108.2   20.7  162.8
  rb   T4:   364.9 /   24.8  117.9   27.5  187.6
  rb   T5:   406.1 /   28.0  124.1   27.2  220.3
  rb   T6:   438.8 /   31.8  125.9   27.7  247.8
  tree T1:   242.2 /   14.8  102.2   29.5   91.6
  tree T2:   306.3 /   19.3  105.0   32.1  142.8
  tree T3:   329.0 /   25.0  112.4   34.2  154.4
  tree T4:   361.8 /   28.4  119.8   42.9  167.5
  tree T5:   391.2 /   32.6  128.4   45.0  185.0
  tree T6:   401.7 /   36.2  128.2   43.0  192.3
  both T1:   238.2 /   14.6  105.3   20.2   92.7
  both T2:   297.5 /   17.8  106.7   21.6  145.0
  both T3:   311.6 /   22.0  112.7   21.9  150.1
  both T4:   348.6 /   26.7  120.0   30.4  167.5
  both T5:   377.9 /   31.9  128.6   29.9  186.0
  both T6:   395.3 /   35.0  132.4   30.8  191.4

W = 0.12 s1 + 0.14 s2 + 0.12 s3 + 0.62 s4 (median span in us):
  base: W 360.5  (1.0000 x base)
  rb: W 336.9  (0.9344 x base)
  tree: W 335.7  (0.9313 x base)
  both: W 323.8  (0.8980 x base)
per-round W (recorded only):
  round 1 base: W 360.5
  round 1 rb: W 341.6
  round 1 tree: W 337.2
  round 1 both: W 352.7
  round 2 rb: W 335.9
  round 2 tree: W 441.8
  round 2 both: W 316.6
  round 2 base: W 401.6
  round 3 tree: W 334.1
  round 3 both: W 324.7
  round 3 base: W 354.3
  round 3 rb: W 335.5
```

内核数据来自数据目录中同名原始文件，各自保留原始行号。判定逐项读取 19 个退出码、12 个计时文件和核对输出。

## 日常配置

第 3 节已备份日常配置，仅在 env 新增 `STRATA_GU_GRID_SLM2=2`，保留其他字段和原有文本；JSON 解析并与预期对象比较通过。改前、改后 env 见 `config-change.json`（原始同名文件）。

## 端到端

| 段 | 状态 | 测速请求数 / 成功数 | 来源 |
|---|---|---|---|
| 1-A | completed | 9 / 9 | `1-A/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 2-B | completed | 9 / 9 | `2-B/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 3-B | completed | 9 / 9 | `3-B/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 4-A | completed | 9 / 9 | `4-A/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 5-A | completed | 9 / 9 | `5-A/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |
| 6-B | completed | 9 / 9 | `6-B/metadata.json:10`；本段 bench.json requests 逐项计数，字段行号见 timing.tsv |

| 组 | 总生成毫秒 / 总 token | ms/token | 草稿接受 / 提供 |
|---|---|---|---|
| A | 277099.5 / 2700 | 102.629 | 1516 / 2635 |
| B | 275485.8 / 2700 | 102.032 | 1498 / 2680 |

组汇总来源：`timing.tsv` 的对应段和请求，各字段标出原始 bench.json 行号。

| 组 | 问题 | 生成 tok/s 中位数 | 首 token 秒中位数 |
|---|---|---|---|
| A | q1 | 12.500 | 2.418 |
| A | q2 | 8.600 | 2.073 |
| A | q3 | 8.900 | 2.283 |
| B | q1 | 12.500 | 2.362 |
| B | q2 | 8.500 | 2.049 |
| B | q3 | 9.100 | 2.218 |

问题中位数来源：`timing.tsv` 对应组及 question 的原始字段。

| 段 | ms/token | 窗口数 | 平均 T | 草稿接受 / 提供 |
|---|---|---|---|---|
| 1-A | 106.201 | 408 | 3.1984 | 497 / 897 |
| 2-B | 98.358 | 397 | 3.2168 | 506 / 880 |
| 3-B | 103.050 | 411 | 3.2060 | 497 / 906 |
| 4-A | 97.477 | 387 | 3.1888 | 526 / 847 |
| 5-A | 104.210 | 410 | 3.1755 | 493 / 891 |
| 6-B | 104.687 | 409 | 3.1866 | 495 / 894 |

段来源：`timing.tsv` 的原始 bench.json 字段；窗口数和平均 T 来自 `decode.tsv` 中与 chat 请求边界匹配的行。平均 T 用各请求窗口数加权，原始日志的每请求 T 已取两位小数。

| 组 | ms/window 中位数 | draft 中位数 | tokens/window 中位数 |
|---|---|---|---|
| A | 227.060 | 23.900 | 2.080 |
| B | 224.930 | 23.830 | 2.000 |

窗口中位数来源：`decode.tsv` 的测速请求行，与各段 `request-boundaries.json` 的 chat 字节范围逐一匹配；每行保留原始 engine.log 行号。补充 `decode-requests.tsv`，逐请求指明对应的 decode 行，区分预热、贪心和测速请求。


本轮六段贪心哈希及与第 13 轮 A 组的比较（原始响应字段行号见 `greedy.tsv`）：

```text
1-A g1 553ac32f017ae0be
2-B g1 553ac32f017ae0be
3-B g1 553ac32f017ae0be
4-A g1 553ac32f017ae0be
5-A g1 553ac32f017ae0be
6-B g1 553ac32f017ae0be
g1 all six equal: True; same as 13 A: True
1-A g2 1c1c19249884638f
2-B g2 1c1c19249884638f
3-B g2 1c1c19249884638f
4-A g2 1c1c19249884638f
5-A g2 1c1c19249884638f
6-B g2 1c1c19249884638f
g2 all six equal: True; same as 13 A: True
```

## 第 6 节条件

| 条件 | 是否满足 |
|---|---|
| 1. 内核 choice=e2e 且 bitwise both=True | True |
| 2. 六段完成，各九次测速成功 | True |
| 3. 六段 g1/g2 哈希分别一致 | True |
| 4. 九个请求生成 token 数在六段间分别一致 | True |
| 5. 三对相邻段 B 的 ms/token 均小于 A | False |
| 6. 六段均无全部常驻路径 | True |
| 7. 指定引擎错误行为空 | True |

条件依据：`timing.tsv`、`greedy.tsv`、`startup.tsv` 均标出原始文件行号；内核判定见上。
三对 B 更快：[True, False, False]（`decision.json:11`）。

| 段 | 常驻专家数 | missing from VRAM | 来源 |
|---|---|---|---|
| 1-A | 24563 | 13 | startup.tsv 对应段原始行号 |
| 2-B | 24506 | 70 | startup.tsv 对应段原始行号 |
| 3-B | 24503 | 73 | startup.tsv 对应段原始行号 |
| 4-A | 24490 | 86 | startup.tsv 对应段原始行号 |
| 5-A | 24505 | 71 | startup.tsv 对应段原始行号 |
| 6-B | 24490 | 86 | startup.tsv 对应段原始行号 |

两个开关未加进日常配置；未满足条件编号：5。

第 5 节要求记录的引擎错误行：没有。

1-A：completed，请求失败计数 0（`1-A/metadata.json:10`、`1-A/metadata.json:13`）。
2-B：completed，请求失败计数 0（`2-B/metadata.json:10`、`2-B/metadata.json:13`）。
3-B：completed，请求失败计数 0（`3-B/metadata.json:10`、`3-B/metadata.json:13`）。
4-A：completed，请求失败计数 0（`4-A/metadata.json:10`、`4-A/metadata.json:13`）。
5-A：completed，请求失败计数 0（`5-A/metadata.json:10`、`5-A/metadata.json:13`）。
6-B：completed，请求失败计数 0（`6-B/metadata.json:10`、`6-B/metadata.json:13`）。

重试目录：无。

驱动以第 13 轮为底子，固定 nonce=fixed14；只用六段 A/B，不发 logprobs 请求。配置副本共同设置 STRATA_VERIFY_ALL_RESIDENT=0，B 副本另开两个待测开关；保留贪心提示词、请求边界、进程树清理、退出后等待及最多三次重试。

## 执行记录

采用驱动在已初始化 oneAPI 的 CMD 内自动顺序执行，替代手工逐行输入；参数、开关及运行顺序按手册，内核各进程超时上限为 300 秒。编译与内核测量没有失败、超时或崩溃。

只构建及运行手册指定 SYCL 后端；未修改引擎源码，未构建 CUDA、HIP。未做原因分析。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
