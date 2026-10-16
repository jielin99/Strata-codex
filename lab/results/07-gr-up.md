# 07：hc 读 up 内核 A/B、逐位核对与配置

执行日期：2026-10-16T14:41:40.363914+08:00（`environment.json:2`）。Arc 140T，Windows。用户确认插电、最佳性能、实验期间不使用电脑；共享 GPU 内存上限仍为 75%。

- 起始引擎 `870dee5e70ecd004b9468a9e50fa05b33e18629d`（`environment.json:3`）；执行引擎 `43ce03004cc7f3c0a87146f89ba9e9f2923a5d24`（`engine-build.json:6`）。
- 起始 exe：32999424 字节；修改时间 2026-10-16T03:40:26.450143+08:00；SHA256 `64d6f4aa27ff3d8fb1749cd69817b69a2d1e36a96d3e1dc23e7a11a7c04445bc`（`environment.json:6`、`environment.json:7`、`environment.json:8`）。
- 新 exe：33016320 字节；修改时间 2026-10-16T14:43:49.390212+08:00；SHA256 `55ee540cbf599e4900aaacc00eb17d788b5376bcd8324553020108c14daf307d`（`engine-build.json:9`、`engine-build.json:10`、`engine-build.json:11`）。
- 电源模式：最佳性能；可用物理内存 58432303104 字节（`environment.json:13`、`environment.json:11`）。
- GPU：Intel(R) Arc(TM) 140T GPU (32GB)；驱动版本 `32.0.101.8826`（`environment.json:14`）。
- 开机时间记录：2026/10/16 3:30:33（`environment.json:12`）；本轮未发起重启。

引擎构建退出码 0，耗时 320.516 秒（`engine-build.json:5`、`engine-build.json:4`）；只构建手册指定的 SYCL 后端和两个测量工具。

## 端到端测量

只统计每段 9 个短请求，预热及贪心请求不纳入。ms/token = 总生成毫秒 ÷ 总生成 token。逐请求数字及原始 bench.json 行号见 `07-gr-up/timing.tsv`。

| 组 | 请求数 | ms/token | 草稿接受/提供 |
| --- | --- | --- | --- |
| A | 27 | 120.738 | 1478/2782 |
| B | 27 | 114.541 | 1488/2702 |

| 组 | 问题 | 生成 tok/s 中位数 | 首 token 秒 中位数 |
| --- | --- | --- | --- |
| A | q1 | 10.700 | 3.282 |
| A | q2 | 7.300 | 2.747 |
| A | q3 | 7.400 | 2.972 |
| B | q1 | 11.100 | 3.177 |
| B | q2 | 7.900 | 2.669 |
| B | q3 | 7.900 | 2.879 |

| 组 | ms/window 中位数 | draft ms 中位数 | tokens/window 中位数 |
| --- | --- | --- | --- |
| A | 259.070 | 26.100 | 2.000 |
| B | 251.040 | 25.370 | 2.040 |

decode 来源：`07-gr-up/decode.tsv` 各段最后 9 行；已与请求前后的日志字节位置核对。

| 段 | ms/token | 来源 |
| --- | --- | --- |
| 1-A | 120.730 | 1-A/bench.json；逐项行号见 timing.tsv |
| 2-B | 113.121 | 2-B/bench.json；逐项行号见 timing.tsv |
| 3-B | 115.389 | 3-B/bench.json；逐项行号见 timing.tsv |
| 4-A | 121.597 | 4-A/bench.json；逐项行号见 timing.tsv |
| 5-A | 119.885 | 5-A/bench.json；逐项行号见 timing.tsv |
| 6-B | 115.112 | 6-B/bench.json；逐项行号见 timing.tsv |

| A 段 | B 段 | B 比 A 小 |
| --- | --- | --- |
| 1-A | 2-B | True |
| 4-A | 3-B | True |
| 5-A | 6-B | True |

## GR 内核测量

与 06 的比较来源：`lab/results/06-decide/gr-1.txt:1` 至 `:6`。

| tokens | off us 中位数 | on us 中位数 | 六次校验和相同 | 与 06 相同 | 原始来源 |
| --- | --- | --- | --- | --- | --- |
| 1 | 472.1 | 416.8 | True | True | gr-1-off.txt:1, gr-2-on.txt:1, gr-3-off.txt:1, gr-4-on.txt:1, gr-5-off.txt:1, gr-6-on.txt:1 |
| 2 | 532.6 | 461.8 | True | True | gr-1-off.txt:2, gr-2-on.txt:2, gr-3-off.txt:2, gr-4-on.txt:2, gr-5-off.txt:2, gr-6-on.txt:2 |
| 3 | 604.8 | 515.9 | True | True | gr-1-off.txt:3, gr-2-on.txt:3, gr-3-off.txt:3, gr-4-on.txt:3, gr-5-off.txt:3, gr-6-on.txt:3 |
| 4 | 665.2 | 584.7 | True | True | gr-1-off.txt:4, gr-2-on.txt:4, gr-3-off.txt:4, gr-4-on.txt:4, gr-5-off.txt:4, gr-6-on.txt:4 |
| 5 | 712.0 | 629.7 | True | True | gr-1-off.txt:5, gr-2-on.txt:5, gr-3-off.txt:5, gr-4-on.txt:5, gr-5-off.txt:5, gr-6-on.txt:5 |
| 6 | 759.6 | 698.6 | True | True | gr-1-off.txt:6, gr-2-on.txt:6, gr-3-off.txt:6, gr-4-on.txt:6, gr-5-off.txt:6, gr-6-on.txt:6 |

### 分项时间

split-off.txt（原始文件同名；行号依次对应）

```text
device: Intel(R) Arc(TM) 140T GPU (32GB)
T	total_us	norm_us	down_us	up_us
1	473.0	27.6	263.6	181.7
2	550.4	28.4	299.0	223.0
3	639.6	34.0	338.3	267.3
4	693.2	41.0	357.8	294.4
5	726.4	41.1	372.4	312.9
6	795.8	46.3	402.4	347.1
```

split-on.txt（原始文件同名；行号依次对应）

```text
device: Intel(R) Arc(TM) 140T GPU (32GB)
T	total_us	norm_us	down_us	up_us
1	450.3	23.7	284.3	142.4
2	467.6	29.0	285.9	152.7
3	519.7	32.1	313.9	173.7
4	597.1	35.5	353.7	207.9
5	665.5	43.1	377.3	245.1
6	705.2	43.7	393.3	268.2
```

## 核对及日常配置

核对记录来源：`gap-off.txt:1`、`gap-on.txt:1`、`gap-exit.txt:1` 至 `:5`、`gap-fc.txt:2`；贪心原始行号见 `07-gr-up/greedy.tsv`。

gap-off.txt:1: device: Intel(R) Arc(TM) 140T GPU (32GB); lines 33
gap-on.txt:1: device: Intel(R) Arc(TM) 140T GPU (32GB); lines 33
off-exit 0
on-exit 0
fc-exit 0
gap-off.txt lines 33
gap-on.txt lines 33
gap-fc.txt: no differences
All four parity criteria passed: True

g1: all equal
553ac32f017ae0be: 1-A, 2-B, 3-B, 4-A, 5-A, 6-B
g2: all equal
1c1c19249884638f: 1-A, 2-B, 3-B, 4-A, 5-A, 6-B
Comparison with 06: g1 True, g2 True

第 1 节：已备份原配置并加入 `STRATA_Q2_SWAR=1`。
第 5 节：已加 `STRATA_GR_UP_EPI=1`。
条件及前后 env：`07-gr-up/config-change.json`。

## 执行记录、偏离和失败

- 驱动以 06 为底子，替换为 A/B 六段；清除 GR 相关变量，SWAR 与 GR 开关均由配置副本提供；保留预热、g1/g2、9 请求、日志字节位置记录、进程树清理、退出后等待 60 秒及最多三次重试。
- 未改引擎源码；未安装或下载依赖。未做其他后端或硬件的验证。

| 段 | 状态 | 来源 |
| --- | --- | --- |
| 1-A | completed | 1-A/metadata.json:1 |
| 2-B | completed | 2-B/metadata.json:1 |
| 3-B | completed | 3-B/metadata.json:1 |
| 4-A | completed | 4-A/metadata.json:1 |
| 5-A | completed | 5-A/metadata.json:1 |
| 6-B | completed | 6-B/metadata.json:1 |

没有重试段。

引擎错误行（排除 no error 等误中）：

没有。

原始 JSON、日志、配置备份和 exe 留在原始目录；数据目录只保存测量数字和引擎状态。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
