# 06：Q2_0、MTP Q4、全常驻和回答一致性

执行日期：2026-10-16T03:38:21.296797+08:00；Arc 140T，Windows。用户确认插电、电源模式最佳性能、测试期间不使用电脑；共享 GPU 内存上限已调为 75% 并重启。

- 起始引擎 `7629f0b294bcaef91b971ac768a377f7a85518cd`；执行引擎 `870dee5e70ecd004b9468a9e50fa05b33e18629d`（`environment.json:3`、`engine-build.json:5`）。
- 起始 exe：32892416 字节（`environment.json:6`）；修改时间 2026-10-16T00:24:02.160723+08:00（`environment.json:7`）；SHA256 `28ac70667e3929c2828a1e5d4b9cc971883c70b253a544d8586cdb8f35156a88`（`environment.json:8`）。
- 新 exe：32999424 字节（`engine-build.json:8`）；修改时间 2026-10-16T03:40:26.450143+08:00（`engine-build.json:9`）；SHA256 `64d6f4aa27ff3d8fb1749cd69817b69a2d1e36a96d3e1dc23e7a11a7c04445bc`（`engine-build.json:10`）。
- 注册表电源模式：最佳性能；可用物理内存 59503546368 字节（`environment.json:13`；`environment.json:11`）。
- GPU 驱动：Intel Arc 140T，`32.0.101.8826`（`environment.json:14`）。
- 开机时间记录：2026/10/16 3:30:33（`environment.json:12`；本轮未发起重启）。

## 端到端测量

只合并每段 9 个短请求；预热和贪心请求不计入下表。ms/token = 总生成毫秒 ÷ 总生成 token。每个数值来自 `timing.tsv`；逐请求原始行号见该表的 source 列。decode 中位数取对应的 9 个请求，已用请求前后的日志字节位置核对。

| 组 | 请求数 | ms/token | 草稿接受/提供 | 段 |
| --- | --- | --- | --- | --- |
| A | 27 | 122.290 | 1484/2708 | 1-A, 8-A, 9-A |
| B | 27 | 118.184 | 1502/2730 | 10-B, 2-B, 7-B |
| C | 27 | 128.813 | 1512/2492 | 11-C, 3-C, 6-C |
| D | 未测 | 未测 | 未测 | 未测 |

| 组 | 问题 | 生成 tok/s 中位数 | 首 token 秒 中位数 |
| --- | --- | --- | --- |
| A | q1 | 10.500 | 3.382 |
| A | q2 | 7.400 | 2.865 |
| A | q3 | 7.200 | 3.100 |
| B | q1 | 10.900 | 3.277 |
| B | q2 | 7.500 | 2.773 |
| B | q3 | 7.700 | 3.017 |
| C | q1 | 9.200 | 3.362 |
| C | q2 | 7.100 | 2.881 |
| C | q3 | 7.000 | 3.126 |

| 组 | ms/window 中位数 | draft ms 中位数 | tokens/window 中位数 |
| --- | --- | --- | --- |
| A | 267.430 | 25.650 | 1.960 |
| B | 259.530 | 25.790 | 2.000 |
| C | 279.310 | 41.990 | 2.040 |

来源：`decode.tsv` 对应段最后 9 行；原始行号见 line 列。

## 内核测量

| T | off ms/window 中位数 | on ms/window 中位数 | 原始来源 |
| --- | --- | --- | --- |
| 1 | 31.158 | 27.241 | moe-1-off.tsv:6, moe-2-on.tsv:7, moe-3-off.tsv:6, moe-4-on.tsv:7, moe-5-off.tsv:6, moe-6-on.tsv:7 |
| 2 | 51.983 | 46.341 | moe-1-off.tsv:17, moe-2-on.tsv:18, moe-3-off.tsv:17, moe-4-on.tsv:18, moe-5-off.tsv:17, moe-6-on.tsv:18 |
| 3 | 76.128 | 73.615 | moe-1-off.tsv:28, moe-2-on.tsv:29, moe-3-off.tsv:28, moe-4-on.tsv:29, moe-5-off.tsv:28, moe-6-on.tsv:29 |
| 4 | 95.695 | 83.927 | moe-1-off.tsv:39, moe-2-on.tsv:40, moe-3-off.tsv:39, moe-4-on.tsv:40, moe-5-off.tsv:39, moe-6-on.tsv:40 |

| gate-up/down 类型 | T=4 off us/layer 中位数 | T=4 on us/layer 中位数 | 原始来源 |
| --- | --- | --- | --- |
| 16/20 | 1725.2 | 1807.0 | moe-1-off.tsv:40, moe-2-on.tsv:41, moe-3-off.tsv:40, moe-4-on.tsv:41, moe-5-off.tsv:40, moe-6-on.tsv:41 |
| 16/42 | 1839.2 | 1455.3 | moe-1-off.tsv:41, moe-2-on.tsv:42, moe-3-off.tsv:41, moe-4-on.tsv:42, moe-5-off.tsv:41, moe-6-on.tsv:42 |
| 17/20 | 1789.4 | 1831.9 | moe-1-off.tsv:42, moe-2-on.tsv:43, moe-3-off.tsv:42, moe-4-on.tsv:43, moe-5-off.tsv:42, moe-6-on.tsv:43 |
| 17/42 | 1836.8 | 1445.6 | moe-1-off.tsv:43, moe-2-on.tsv:44, moe-3-off.tsv:43, moe-4-on.tsv:44, moe-5-off.tsv:43, moe-6-on.tsv:44 |
| 18/20 | 1936.8 | 1933.2 | moe-1-off.tsv:44, moe-2-on.tsv:45, moe-3-off.tsv:44, moe-4-on.tsv:45, moe-5-off.tsv:44, moe-6-on.tsv:45 |
| 18/42 | 2039.0 | 1620.6 | moe-1-off.tsv:45, moe-2-on.tsv:46, moe-3-off.tsv:45, moe-4-on.tsv:46, moe-5-off.tsv:45, moe-6-on.tsv:46 |
| 21/20 | 2122.3 | 2100.9 | moe-1-off.tsv:46, moe-2-on.tsv:47, moe-3-off.tsv:46, moe-4-on.tsv:47, moe-5-off.tsv:46, moe-6-on.tsv:47 |
| 21/42 | 2182.8 | 1778.4 | moe-1-off.tsv:47, moe-2-on.tsv:48, moe-3-off.tsv:47, moe-4-on.tsv:48, moe-5-off.tsv:47, moe-6-on.tsv:48 |
| 22/20 | 1786.7 | 1823.1 | moe-1-off.tsv:48, moe-2-on.tsv:49, moe-3-off.tsv:48, moe-4-on.tsv:49, moe-5-off.tsv:48, moe-6-on.tsv:49 |
| 22/42 | 1921.0 | 1488.1 | moe-1-off.tsv:49, moe-2-on.tsv:50, moe-3-off.tsv:49, moe-4-on.tsv:50, moe-5-off.tsv:49, moe-6-on.tsv:50 |

Byte-identical: True; differing comparison output lines: 0. Source: dump-fc.txt:2.（`dump-check.txt:1`）。

```text
parity-off.txt:74: iq_multi_parity: 0 failures
parity-on.txt:74: iq_multi_parity: 0 failures
parity-fc.txt:2: no differences
```

| GR tokens | us 中位数 | 原始来源 |
| --- | --- | --- |
| 1 | 491.9 | gr-1.txt:1, gr-2.txt:1, gr-3.txt:1 |
| 2 | 546.6 | gr-1.txt:2, gr-2.txt:2, gr-3.txt:2 |
| 3 | 613.9 | gr-1.txt:3, gr-2.txt:3, gr-3.txt:3 |
| 4 | 678.8 | gr-1.txt:4, gr-2.txt:4, gr-3.txt:4 |
| 5 | 713.1 | gr-1.txt:5, gr-2.txt:5, gr-3.txt:5 |
| 6 | 808.6 | gr-1.txt:6, gr-2.txt:6, gr-3.txt:6 |

## 回答一致性及配置

```text
g1: all equal
553ac32f017ae0be: 1-A, 2-B, 3-C, 6-C, 7-B, 8-A, 9-A, 10-B, 11-C, 13-A0
g2: all equal
1c1c19249884638f: 1-A, 2-B, 3-C, 6-C, 7-B, 8-A, 9-A, 10-B, 11-C, 13-A0
```

日常配置：已加 `STRATA_MMVQ_Q6_SWAR=1`；已先备份原配置。（`config-change.json:2`）。
`STRATA_Q2_SWAR` 和 MTP Q4 未加入日常配置。

## D 组启动记录

`4-D` 启动仍报告 32GB，因此按手册跳过 `4-D`、`5-D`、`12-D` 的测量（`4-D/engine.log:13`）。

| 段 | 原始行 | 引擎状态 |
| --- | --- | --- |
| 4-D | 13 | strata generate: GPU 0: Intel(R) Arc(TM) 140T GPU (32GB), compute capability 12.74 |
| 4-D | 16 | strata generate: expert cache auto: 41.57 GiB free, 1024 MiB reserved (+184 MiB for the draft head) -> 18392 slots |
| 4-D | 17 | strata generate: expert cache 24539 slots, 39.90 GiB of VRAM; policy is |
| 4-D | 24 | strata generate: 37 of 37 experts missing from VRAM (+ 0 in the prompt loan's slots) mirrored in pinned host memory (0.06 GiB, 0.0 s); the GPU reads them over PCIe |
| 4-D | 29 | strata generate: token graph hit path: 24539 resident experts, decided on the device |

## 执行记录和偏离

- 驱动基于 05；替换段顺序、清除 Q2 SWAR 等变量、增加配置副本、贪心请求及请求日志位置记录，移除 VERIFY_DEBUG；13-A0 只做预热和贪心。
- Git 同步使用现有 origin 的 SSH 主机别名，目标仓库和分支与手册相同。
- 构建仅执行手册指定的 SYCL 和 MoE 构建，未改引擎代码。编译命令、退出码、耗时和文件信息见 `build.txt`（原始 JSON 在原始目录）。

| 段 | 状态 | 来源 |
| --- | --- | --- |
| 1-A | completed | 1-A/metadata.json:1 |
| 2-B | completed | 2-B/metadata.json:1 |
| 3-C | completed | 3-C/metadata.json:1 |
| 4-D | skipped | 4-D/metadata.json:1 |
| 6-C | completed | 6-C/metadata.json:1 |
| 7-B | completed | 7-B/metadata.json:1 |
| 8-A | completed | 8-A/metadata.json:1 |
| 9-A | completed | 9-A/metadata.json:1 |
| 10-B | completed | 10-B/metadata.json:1 |
| 11-C | completed | 11-C/metadata.json:1 |
| 13-A0 | completed | 13-A0/metadata.json:1 |

5-D：未做，4-D 启动仍报告 32GB。来源：5-D-skipped.json:1。
12-D：未做，4-D 启动仍报告 32GB。来源：12-D-skipped.json:1。
没有重试段。

错误行（已排除 no error）：

没有。

原始回答、完整日志、二进制与转储均保留在原始目录。未做其他模型、其他后端或其他硬件的验证。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
