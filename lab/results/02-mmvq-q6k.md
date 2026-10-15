# 02：140T 稠密 GEMV 与 Q6_K 去掉 sub_sat 的测量记录

## 执行环境

- 实验开始：2026-10-15T22:11:31.155101+08:00（`state.json:3`）。引擎 HEAD：`29825274e3de26b35101d73be2d793315453a6ac`（`env.txt:2`）；`sycl` 状态为空（`env.txt:3`）。
- GPU：Intel(R) Arc(TM) 140T GPU (32GB)；驱动：32.0.101.8826（`env.txt:50`）。
- 插电、最佳性能、测试期间不使用电脑已由用户确认（`env.txt:4`）。注册表 ActiveOverlayAcPowerScheme 为 `ded574b5-45a0-4f42-8737-46345c09c238`，对应最佳性能（`env.txt:43`）；`powercfg /getactiveoverlayscheme` 不受支持，按手册使用注册表后备方法。
- 工作站统计开始时间：统计数据开始于 2026/10/15 2:32:52（`env.txt:10`）。本轮未执行重启；该时间为工作站统计开始时间。
- 原始记录位于手册指定的 `02-mmvq-q6k` 原始目录。下文原始文件引用均相对于该目录；公开副本见同名数据目录。

## 编译

编译、链接均成功。副本的 `numstat` 为 `2	2`（`build.txt:6`）。

| 步骤 | 耗时（秒） | 原始记录 |
|---|---|---|
| 生成 nosat 副本 | 0.073 | `state.json:9` |
| `<build>\mmvq_lab.obj` | 9.98 | `state.json:15` |
| `<build>\iq_kernels.obj` | 13.887 | `state.json:21` |
| `<build>\base\native_mmvq.obj` | 26.422 | `state.json:27` |
| `<build>\nosat\native_mmvq.obj` | 26.536 | `state.json:33` |
| `<build>\base\mmvq_lab.exe` | 45.288 | `state.json:39` |
| `<build>\nosat\mmvq_lab.exe` | 43.642 | `state.json:45` |

源码与可执行文件：大小、SHA256 也记录在数据目录的 `build.txt`。

| 文件 | 字节 | 修改时间 | SHA256 | 原始记录 |
|---|---|---|---|---|
| `<engine>\sycl\src\kernels\cuda\native_mmvq.dp.cpp` | 180774 | 2026-10-14T02:36:15.096842+08:00 | d8f4d847b16f06daa8bc015886257a073c4952f3da07927dc88e7c20c7def1f0 | `state.json:54`；`state.json:53` |
| `<build>\nosat\native_mmvq_nosat.dp.cpp` | 180794 | 2026-10-15T22:11:31.202302+08:00 | 7d4dd13b4153891bbacd00be511163e3cabd95fccf22140a874094d1024b6984 | `state.json:60`；`state.json:59` |
| `<build>\base\mmvq_lab.exe` | 20713472 | 2026-10-15T22:13:32.032845+08:00 | ea38a4afb4711d42a426cab1495bf00b41138a44b0a44fa69c8572ab1fe02258 | `state.json:68`；`state.json:67` |
| `<build>\nosat\mmvq_lab.exe` | 20711936 | 2026-10-15T22:14:15.919170+08:00 | 8f91d8ec2e212f8b8779ef98ecfade267300164b9ef882cd9fdde72e87be8242 | `state.json:74`；`state.json:73` |

## Q6_K

工作集为 1024 MiB，每种情况 300 ms（各 `.tsv:3`）。工具报告的 SYCL 设备驱动版本为 `1.15.37858`（各 `.tsv:2`）。下表使用 `compare.tsv` 的中位数；倍率为 nosat/base。

| 张量 | 列数 | base GB/s | nosat GB/s | nosat/base | 原始记录 |
|---|---|---|---|---|---|
| attn_qkv | 1 | 51.6 | 64.3 | 1.247 | `compare.tsv:20` |
| attn_qkv | 2 | 33.3 | 50.4 | 1.518 | `compare.tsv:21` |
| attn_qkv | 3 | 20.8 | 44.8 | 2.152 | `compare.tsv:22` |
| attn_qkv | 4 | 28.4 | 41.0 | 1.442 | `compare.tsv:23` |
| attn_qkv | 5 | 5.3 | 35.3 | 6.648 | `compare.tsv:24` |
| attn_qkv | 6 | 3.5 | 5.3 | 1.533 | `compare.tsv:25` |
| attn_gate | 1 | 45.6 | 57.6 | 1.263 | `compare.tsv:50` |
| attn_gate | 2 | 30.0 | 43.6 | 1.453 | `compare.tsv:51` |
| attn_gate | 3 | 17.8 | 39.2 | 2.207 | `compare.tsv:52` |
| attn_gate | 4 | 25.0 | 36.0 | 1.443 | `compare.tsv:53` |
| attn_gate | 5 | 4.9 | 30.2 | 6.073 | `compare.tsv:54` |
| attn_gate | 6 | 3.4 | 5.2 | 1.521 | `compare.tsv:55` |
| ssm_out | 1 | 46.9 | 58.1 | 1.238 | `compare.tsv:80` |
| ssm_out | 2 | 31.5 | 44.3 | 1.406 | `compare.tsv:81` |
| ssm_out | 3 | 19.1 | 39.5 | 2.067 | `compare.tsv:82` |
| ssm_out | 4 | 27.4 | 36.0 | 1.312 | `compare.tsv:83` |
| ssm_out | 5 | 6.4 | 31.4 | 4.917 | `compare.tsv:84` |
| ssm_out | 6 | 4.3 | 6.4 | 1.491 | `compare.tsv:85` |
| attn_q | 1 | 50.1 | 64.0 | 1.277 | `compare.tsv:104` |
| attn_q | 2 | 33.7 | 49.9 | 1.478 | `compare.tsv:105` |
| attn_q | 3 | 19.7 | 45.6 | 2.317 | `compare.tsv:106` |
| attn_q | 4 | 27.9 | 41.6 | 1.491 | `compare.tsv:107` |
| attn_q | 5 | 5.4 | 36.5 | 6.774 | `compare.tsv:108` |
| attn_q | 6 | 3.5 | 5.2 | 1.511 | `compare.tsv:109` |
| shexp_gate_up | 1 | 21.7 | 25.8 | 1.189 | `compare.tsv:134` |
| shexp_gate_up | 2 | 14.5 | 19.7 | 1.358 | `compare.tsv:135` |
| shexp_gate_up | 3 | 9.4 | 17.5 | 1.865 | `compare.tsv:136` |
| shexp_gate_up | 4 | 12.4 | 16.0 | 1.294 | `compare.tsv:137` |
| shexp_gate_up | 5 | 5.5 | 14.3 | 2.621 | `compare.tsv:138` |
| shexp_gate_up | 6 | 4.8 | 5.4 | 1.122 | `compare.tsv:139` |

## 其他类型

列出工具内定义的全部类型与形状组合的 base GB/s；工具中没有的组合未做。

| 类型 | 张量 | 列数 | base GB/s | 原始记录 |
|---|---|---|---|---|
| IQ4_XS | attn_qkv | 1 | 48.7 | `compare.tsv:2` |
| IQ4_XS | attn_qkv | 2 | 43.8 | `compare.tsv:3` |
| IQ4_XS | attn_qkv | 3 | 38.0 | `compare.tsv:4` |
| IQ4_XS | attn_qkv | 4 | 36.0 | `compare.tsv:5` |
| IQ4_XS | attn_qkv | 5 | 31.6 | `compare.tsv:6` |
| IQ4_XS | attn_qkv | 6 | 29.5 | `compare.tsv:7` |
| Q4_K | attn_qkv | 1 | 51.9 | `compare.tsv:8` |
| Q4_K | attn_qkv | 2 | 38.5 | `compare.tsv:9` |
| Q4_K | attn_qkv | 3 | 29.7 | `compare.tsv:10` |
| Q4_K | attn_qkv | 4 | 26.0 | `compare.tsv:11` |
| Q4_K | attn_qkv | 5 | 23.1 | `compare.tsv:12` |
| Q4_K | attn_qkv | 6 | 20.8 | `compare.tsv:13` |
| Q5_K | attn_qkv | 1 | 60.3 | `compare.tsv:14` |
| Q5_K | attn_qkv | 2 | 47.0 | `compare.tsv:15` |
| Q5_K | attn_qkv | 3 | 37.1 | `compare.tsv:16` |
| Q5_K | attn_qkv | 4 | 32.1 | `compare.tsv:17` |
| Q5_K | attn_qkv | 5 | 28.0 | `compare.tsv:18` |
| Q5_K | attn_qkv | 6 | 25.0 | `compare.tsv:19` |
| IQ3_S | attn_gate | 1 | 21.8 | `compare.tsv:26` |
| IQ3_S | attn_gate | 2 | 19.9 | `compare.tsv:27` |
| IQ3_S | attn_gate | 3 | 18.7 | `compare.tsv:28` |
| IQ3_S | attn_gate | 4 | 16.9 | `compare.tsv:29` |
| IQ3_S | attn_gate | 5 | 15.1 | `compare.tsv:30` |
| IQ3_S | attn_gate | 6 | 15.6 | `compare.tsv:31` |
| IQ4_XS | attn_gate | 1 | 43.7 | `compare.tsv:32` |
| IQ4_XS | attn_gate | 2 | 40.1 | `compare.tsv:33` |
| IQ4_XS | attn_gate | 3 | 35.9 | `compare.tsv:34` |
| IQ4_XS | attn_gate | 4 | 33.0 | `compare.tsv:35` |
| IQ4_XS | attn_gate | 5 | 29.7 | `compare.tsv:36` |
| IQ4_XS | attn_gate | 6 | 25.8 | `compare.tsv:37` |
| Q4_K | attn_gate | 1 | 48.5 | `compare.tsv:38` |
| Q4_K | attn_gate | 2 | 32.5 | `compare.tsv:39` |
| Q4_K | attn_gate | 3 | 27.2 | `compare.tsv:40` |
| Q4_K | attn_gate | 4 | 22.2 | `compare.tsv:41` |
| Q4_K | attn_gate | 5 | 20.9 | `compare.tsv:42` |
| Q4_K | attn_gate | 6 | 18.9 | `compare.tsv:43` |
| Q5_K | attn_gate | 1 | 55.6 | `compare.tsv:44` |
| Q5_K | attn_gate | 2 | 41.8 | `compare.tsv:45` |
| Q5_K | attn_gate | 3 | 33.3 | `compare.tsv:46` |
| Q5_K | attn_gate | 4 | 28.7 | `compare.tsv:47` |
| Q5_K | attn_gate | 5 | 26.1 | `compare.tsv:48` |
| Q5_K | attn_gate | 6 | 23.2 | `compare.tsv:49` |
| IQ3_S | ssm_out | 1 | 23.7 | `compare.tsv:56` |
| IQ3_S | ssm_out | 2 | 19.7 | `compare.tsv:57` |
| IQ3_S | ssm_out | 3 | 18.6 | `compare.tsv:58` |
| IQ3_S | ssm_out | 4 | 17.3 | `compare.tsv:59` |
| IQ3_S | ssm_out | 5 | 15.6 | `compare.tsv:60` |
| IQ3_S | ssm_out | 6 | 15.7 | `compare.tsv:61` |
| IQ4_XS | ssm_out | 1 | 45.7 | `compare.tsv:62` |
| IQ4_XS | ssm_out | 2 | 41.7 | `compare.tsv:63` |
| IQ4_XS | ssm_out | 3 | 38.4 | `compare.tsv:64` |
| IQ4_XS | ssm_out | 4 | 35.2 | `compare.tsv:65` |
| IQ4_XS | ssm_out | 5 | 32.5 | `compare.tsv:66` |
| IQ4_XS | ssm_out | 6 | 29.4 | `compare.tsv:67` |
| Q4_K | ssm_out | 1 | 52.8 | `compare.tsv:68` |
| Q4_K | ssm_out | 2 | 35.4 | `compare.tsv:69` |
| Q4_K | ssm_out | 3 | 28.4 | `compare.tsv:70` |
| Q4_K | ssm_out | 4 | 24.8 | `compare.tsv:71` |
| Q4_K | ssm_out | 5 | 22.4 | `compare.tsv:72` |
| Q4_K | ssm_out | 6 | 20.5 | `compare.tsv:73` |
| Q5_K | ssm_out | 1 | 57.5 | `compare.tsv:74` |
| Q5_K | ssm_out | 2 | 44.2 | `compare.tsv:75` |
| Q5_K | ssm_out | 3 | 35.4 | `compare.tsv:76` |
| Q5_K | ssm_out | 4 | 28.9 | `compare.tsv:77` |
| Q5_K | ssm_out | 5 | 27.1 | `compare.tsv:78` |
| Q5_K | ssm_out | 6 | 24.7 | `compare.tsv:79` |
| IQ3_S | attn_q | 1 | 25.6 | `compare.tsv:86` |
| IQ3_S | attn_q | 2 | 20.5 | `compare.tsv:87` |
| IQ3_S | attn_q | 3 | 19.4 | `compare.tsv:88` |
| IQ3_S | attn_q | 4 | 18.5 | `compare.tsv:89` |
| IQ3_S | attn_q | 5 | 16.3 | `compare.tsv:90` |
| IQ3_S | attn_q | 6 | 16.0 | `compare.tsv:91` |
| IQ4_XS | attn_q | 1 | 48.0 | `compare.tsv:92` |
| IQ4_XS | attn_q | 2 | 43.4 | `compare.tsv:93` |
| IQ4_XS | attn_q | 3 | 39.0 | `compare.tsv:94` |
| IQ4_XS | attn_q | 4 | 34.4 | `compare.tsv:95` |
| IQ4_XS | attn_q | 5 | 32.6 | `compare.tsv:96` |
| IQ4_XS | attn_q | 6 | 29.2 | `compare.tsv:97` |
| Q4_K | attn_q | 1 | 51.4 | `compare.tsv:98` |
| Q4_K | attn_q | 2 | 35.8 | `compare.tsv:99` |
| Q4_K | attn_q | 3 | 29.8 | `compare.tsv:100` |
| Q4_K | attn_q | 4 | 25.4 | `compare.tsv:101` |
| Q4_K | attn_q | 5 | 23.0 | `compare.tsv:102` |
| Q4_K | attn_q | 6 | 21.0 | `compare.tsv:103` |
| IQ3_S | shexp_gate_up | 1 | 14.9 | `compare.tsv:110` |
| IQ3_S | shexp_gate_up | 2 | 10.7 | `compare.tsv:111` |
| IQ3_S | shexp_gate_up | 3 | 10.4 | `compare.tsv:112` |
| IQ3_S | shexp_gate_up | 4 | 9.6 | `compare.tsv:113` |
| IQ3_S | shexp_gate_up | 5 | 8.5 | `compare.tsv:114` |
| IQ3_S | shexp_gate_up | 6 | 9.1 | `compare.tsv:115` |
| IQ4_XS | shexp_gate_up | 1 | 25.4 | `compare.tsv:116` |
| IQ4_XS | shexp_gate_up | 2 | 22.1 | `compare.tsv:117` |
| IQ4_XS | shexp_gate_up | 3 | 20.3 | `compare.tsv:118` |
| IQ4_XS | shexp_gate_up | 4 | 18.3 | `compare.tsv:119` |
| IQ4_XS | shexp_gate_up | 5 | 16.7 | `compare.tsv:120` |
| IQ4_XS | shexp_gate_up | 6 | 14.7 | `compare.tsv:121` |
| Q4_K | shexp_gate_up | 1 | 24.9 | `compare.tsv:122` |
| Q4_K | shexp_gate_up | 2 | 15.0 | `compare.tsv:123` |
| Q4_K | shexp_gate_up | 3 | 13.2 | `compare.tsv:124` |
| Q4_K | shexp_gate_up | 4 | 10.8 | `compare.tsv:125` |
| Q4_K | shexp_gate_up | 5 | 10.4 | `compare.tsv:126` |
| Q4_K | shexp_gate_up | 6 | 9.3 | `compare.tsv:127` |
| Q5_K | shexp_gate_up | 1 | 29.5 | `compare.tsv:128` |
| Q5_K | shexp_gate_up | 2 | 20.3 | `compare.tsv:129` |
| Q5_K | shexp_gate_up | 3 | 15.7 | `compare.tsv:130` |
| Q5_K | shexp_gate_up | 4 | 13.5 | `compare.tsv:131` |
| Q5_K | shexp_gate_up | 5 | 12.4 | `compare.tsv:132` |
| Q5_K | shexp_gate_up | 6 | 10.7 | `compare.tsv:133` |
| IQ4_NL | shexp_down | 1 | 21.1 | `compare.tsv:140` |
| IQ4_NL | shexp_down | 2 | 19.8 | `compare.tsv:141` |
| IQ4_NL | shexp_down | 3 | 18.9 | `compare.tsv:142` |
| IQ4_NL | shexp_down | 4 | 16.3 | `compare.tsv:143` |
| IQ4_NL | shexp_down | 5 | 15.3 | `compare.tsv:144` |
| IQ4_NL | shexp_down | 6 | 12.8 | `compare.tsv:145` |
| Q2_0 | shexp_down | 1 | 4.0 | `compare.tsv:146` |
| Q2_0 | shexp_down | 2 | 4.0 | `compare.tsv:147` |
| Q2_0 | shexp_down | 3 | 3.3 | `compare.tsv:148` |
| Q2_0 | shexp_down | 4 | 2.9 | `compare.tsv:149` |
| Q2_0 | shexp_down | 5 | 2.5 | `compare.tsv:150` |
| Q2_0 | shexp_down | 6 | 1.5 | `compare.tsv:151` |
| Q5_K | output | 1 | 65.6 | `compare.tsv:152` |
| Q5_K | output | 2 | 52.8 | `compare.tsv:153` |
| Q5_K | output | 3 | 41.3 | `compare.tsv:154` |
| Q5_K | output | 4 | 37.3 | `compare.tsv:155` |
| Q5_K | output | 5 | 34.0 | `compare.tsv:156` |
| Q5_K | output | 6 | 29.7 | `compare.tsv:157` |

## 校验值

`mmvq_compare: 156 rows, 0 label(s) missing a row, 0 row(s) with differing checksums -> compare.tsv`（`compare.txt:25`）。

没有 `DIFFER` 行。
该检查比较工具输出的汇总校验值；未做输出数组逐元素或逐字节比较。

## 运行时间

| 运行 | 开始（+08:00） | 结束（+08:00） | 退出码 | 原始记录 |
|---|---|---|---|---|
| base-1 | 2026-10-15T22:14:17.075921+08:00 | 2026-10-15T22:15:43.027739+08:00 | 0 | `state.json:81`；`state.json:83` |
| nosat-1 | 2026-10-15T22:15:43.028459+08:00 | 2026-10-15T22:17:00.652375+08:00 | 0 | `state.json:88`；`state.json:90` |
| nosat-2 | 2026-10-15T22:17:00.653233+08:00 | 2026-10-15T22:18:15.003872+08:00 | 0 | `state.json:95`；`state.json:97` |
| base-2 | 2026-10-15T22:18:15.004508+08:00 | 2026-10-15T22:19:31.628128+08:00 | 0 | `state.json:102`；`state.json:104` |
| nosat-q6-1 | 2026-10-15T22:19:31.628786+08:00 | 2026-10-15T22:19:46.214222+08:00 | 0 | `state.json:109`；`state.json:111` |
| base-q6-1 | 2026-10-15T22:19:46.214916+08:00 | 2026-10-15T22:20:02.605877+08:00 | 0 | `state.json:116`；`state.json:118` |
| base-q6-2 | 2026-10-15T22:20:02.606577+08:00 | 2026-10-15T22:20:18.822806+08:00 | 0 | `state.json:123`；`state.json:125` |
| nosat-q6-2 | 2026-10-15T22:20:18.823637+08:00 | 2026-10-15T22:20:33.234786+08:00 | 0 | `state.json:130`；`state.json:132` |

时间与退出码来自原始 `state.json` 的 `runs` 各项。

## 失败与偏离

八次运行均成功，标准错误文件均为空；未发生重试、超时或崩溃。

编译出现子组属性相关警告，完整原文留在本地原始 `build.txt`；各编译及链接命令退出码均为 0。

使用 CMD 初始化 oneAPI，再由临时 Python 驱动顺序调用 CMD 编译和运行，记录耗时与退出码；编译参数、测量参数和运行顺序遵循手册。环境预检查使用 PowerShell 读取进程、端口、Git 状态及驱动。未修改引擎源码，未启动 Strata 服务。

## 数据文件

`build.txt` 为命令、耗时、numstat、源码和程序大小与 SHA256 的脱敏副本。八个运行 `.tsv` 为各次原始数字输出；`compare.tsv` 为分组中位数与校验值比较；`compare.txt` 为设备信息及比较汇总。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
