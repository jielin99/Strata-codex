# 08：hc 读 down 变体、端到端测量与分阶段计时

执行日期：2026-10-17T00:58:33.749326+08:00（`environment.json:2`）。Arc 140T，Windows。用户确认插电、最佳性能、实验期间不使用电脑；共享 GPU 内存上限仍为 75%。

- 起始引擎 `43ce03004cc7f3c0a87146f89ba9e9f2923a5d24`（`environment.json:3`）；执行引擎 `0408d9163cdc305a22f09dd48692122018b58fa7`（`engine-build.json:6`）。
- 起始 exe：33016320 字节，修改时间 2026-10-16T14:43:49.390212+08:00，SHA256 `55ee540cbf599e4900aaacc00eb17d788b5376bcd8324553020108c14daf307d`（`environment.json:6`、`environment.json:7`、`environment.json:8`）。
- 执行 exe：33101312 字节，修改时间 2026-10-17T01:00:35.896331+08:00，SHA256 `9dca0dc14910fa9e2b4eb233e68466ac44d4c7c997b8c7169b2d3631a0f22eec`（`engine-build.json:9`、`engine-build.json:10`、`engine-build.json:11`）。
- 电源模式：最佳性能；可用物理内存 58935496704 字节（`environment.json:13`、`environment.json:11`）。
- GPU：Intel(R) Arc(TM) 140T GPU (32GB)；驱动版本 `32.0.101.8826`（`environment.json:14`）。
- 开机时间记录：2026/10/16 16:15:08（`environment.json:12`）；本轮未发起重启。

引擎构建退出码 0，耗时 301.103 秒（`engine-build.json:5`、`engine-build.json:4`）。构建记录及工具命令见 `08-gr-down/build.txt`，各项附原始来源。

## 变体选择与分内核计时

下列 choice.txt 原样摘录；t1…t6 为三轮中位数，W 按手册公式计算。各数字来源为同名原始文件 `gr-<轮>-<变体>.txt:1` 至 `:6`；校验来源见 gap.txt。

```text
variant	t1_us	t2_us	t3_us	t4_us	t5_us	t6_us	W_us	parity	checksums	candidate
base	478.700	534.500	524.800	554.700	620.700	679.500	539.164	True	True	False
v2	286.900	312.500	377.900	417.300	458.400	489.700	382.252	True	True	True
r128	291.800	477.300	355.700	400.300	425.700	488.300	392.708	True	True	True
r64	289.600	311.900	359.100	546.500	449.000	469.900	460.340	True	True	True
selected: v2
```

ev-base.txt（原始文件同名；行号依次对应）：

```text
device: Intel(R) Arc(TM) 140T GPU (32GB)
env STRATA_GR_UP_EPI=1
T	span_us	kernels	k0_us	k1_us	k2_us	k3_us	k4_us	gaps_us
1	395.2	4	16.2	217.1	30.3	127.1	-	4.5
2	469.9	4	20.3	257.5	33.9	153.6	-	4.7
3	497.0	4	25.0	266.0	35.1	166.6	-	4.3
4	728.5	4	38.0	374.4	47.2	263.8	-	5.1
5	734.9	4	39.2	375.0	49.8	266.2	-	4.9
6	687.5	4	36.1	340.1	46.4	260.5	-	4.4
```

ev-v2.txt（原始文件同名；行号依次对应）：

```text
device: Intel(R) Arc(TM) 140T GPU (32GB)
env STRATA_GR_UP_EPI=1
env STRATA_GR_DOWN_V2=1
T	span_us	kernels	k0_us	k1_us	k2_us	k3_us	k4_us	gaps_us
1	456.9	4	19.6	181.9	32.2	217.8	-	5.5
2	469.0	4	25.1	176.1	32.8	229.7	-	5.4
3	344.9	4	22.2	112.7	30.9	174.8	-	4.4
4	382.1	4	26.4	117.8	37.2	195.8	-	5.0
5	441.8	4	29.7	128.9	40.1	238.6	-	4.5
6	478.2	4	34.0	135.3	38.8	265.7	-	4.4
```

## 端到端测量

只统计每段 9 个短请求；预热及贪心请求不纳入。ms/token = 总生成毫秒 ÷ 总生成 token。逐请求数字及原始 bench.json 行号见 `08-gr-down/timing.tsv`。

| 组 | 请求数 | ms/token | 草稿接受/提供 |
| --- | --- | --- | --- |
| A | 27 | 113.476 | 1489/2789 |
| B | 27 | 105.682 | 1474/2728 |

| 组 | 问题 | 生成 tok/s 中位数 | 首 token 秒 中位数 |
| --- | --- | --- | --- |
| A | q1 | 11.400 | 3.093 |
| A | q2 | 7.800 | 2.582 |
| A | q3 | 8.100 | 2.821 |
| B | q1 | 12.200 | 2.875 |
| B | q2 | 8.400 | 2.440 |
| B | q3 | 8.500 | 2.687 |

| 组 | ms/window 中位数 | draft ms 中位数 | tokens/window 中位数 |
| --- | --- | --- | --- |
| A | 246.370 | 25.330 | 2.040 |
| B | 230.160 | 24.120 | 2.000 |

decode 来源：`08-gr-down/decode.tsv` 各段最后 9 行；已与请求前后的日志字节位置核对。

| 段 | ms/token | 来源 |
| --- | --- | --- |
| 1-A | 108.451 | 1-A/bench.json；逐项行号见 timing.tsv |
| 2-B | 107.098 | 2-B/bench.json；逐项行号见 timing.tsv |
| 3-B | 104.523 | 3-B/bench.json；逐项行号见 timing.tsv |
| 4-A | 115.358 | 4-A/bench.json；逐项行号见 timing.tsv |
| 5-A | 116.620 | 5-A/bench.json；逐项行号见 timing.tsv |
| 6-B | 105.425 | 6-B/bench.json；逐项行号见 timing.tsv |

| A 段 | B 段 | B 比 A 小 |
| --- | --- | --- |
| 1-A | 2-B | True |
| 4-A | 3-B | True |
| 5-A | 6-B | True |

## 核对和配置

```text
gap-base.txt:1: device: Intel(R) Arc(TM) 140T GPU (32GB); lines 33
gap-v2.txt:1: device: Intel(R) Arc(TM) 140T GPU (32GB); lines 33
gap-r128.txt:1: device: Intel(R) Arc(TM) 140T GPU (32GB); lines 33
gap-r64.txt:1: device: Intel(R) Arc(TM) 140T GPU (32GB); lines 33
base-exit 0
v2-exit 0
r128-exit 0
r64-exit 0
fc-v2 0
fc-r128 0
fc-r64 0
gap-base.txt lines 33
gap-v2.txt lines 33
gap-r128.txt lines 33
gap-r64.txt lines 33
gap-fc-v2.txt: no differences; all parity criteria passed: True
gap-fc-r128.txt: no differences; all parity criteria passed: True
gap-fc-r64.txt: no differences; all parity criteria passed: True
```

```text
g1: all equal
553ac32f017ae0be: 1-A, 2-B, 3-B, 4-A, 5-A, 6-B

g2: all equal
1c1c19249884638f: 1-A, 2-B, 3-B, 4-A, 5-A, 6-B

Comparison with 07: g1 True, g2 True
```

第 5 节：已加。只在日常配置 env 新增所选变体的开关；已先备份并用 JSON 解析器验证，前后 env 见 `08-gr-down/config-change.json`。

## 长请求 PROFILE

```text
7-P/engine.log:51: strata decode timing: 544 windows, avg T 2.62, 1.88 tokens/window, 241.37 ms/window = verify 217.06 (GPU-reach wait 0.00 + per-layer host 0.00 [plan 0.00 actq 0.00 jobs 0.00 CPU 0.00] + stage 0.00) + commit/emit 0.12 + draft 24.19; per layer-window: CPU experts 0.00 (0.00 entries), VRAM hits 0.00, PCIe 0.00
7-P/engine.log:52: strata decode GPU stages (ms/window): GDN layers: hc-read0 11.35 q8+qkv/q-idx gemv 22.09 conv 0.02 ab 0.04 z 10.76 rec 4.74 out-proj 14.29 hc-read1+router 22.89 shared+quant 0.36 waitA 0.00 VRAM hits 64.25 waitB 0.00 PCIe grp 0.00 copy+combine 0.03 (gap) 0.00 head 11.14   hc0 norm 0.10   hc0 down 0.01   hc0 up 0.01 | QSA layers: hc-read0 2.98 q8+kv-idx 0.03 k/v+norm-rope 0.08 kv+idx append 0.05 q+q-idx 12.52 scores+topk 0.01 kv-resolve 0.00 attention 0.12 gate 0.01 out-proj 6.80 hc-read1+router 7.47 shared+quant 0.11 VRAM hits 19.79 waitB 0.00 copy+combine 0.01 (gap) 0.00 | total 212.08 ms/window over 545 windows
completion_tokens: 1024 (7-P/profile-summary.json:2)
finish_reason: length (7-P/profile-summary.json:3)
```

## 执行记录、偏离和失败

- 驱动从 07 复制；保留配置副本、预热、g1/g2、9 个请求、请求日志字节位置、进程树清理、退出后等待 60 秒及最多三次重试；增加 DOWN_V2/ROWS 清理、配置条件判断及 7-P 长请求。
- gap 文件行数由 Python 按行统计，替代 CMD 的 find 计数；fc 比较实际执行，三个比较均无差异。
- 引擎仅快进更新并构建手册指定 SYCL 后端；工具构建在新目录 build-lab-gr8，未修改引擎源码。未安装或下载依赖。未做其他后端、其他模型或其他硬件的验证。

| 段 | 状态 | 来源 |
| --- | --- | --- |
| 1-A | completed | 1-A/metadata.json:10 |
| 2-B | completed | 2-B/metadata.json:10 |
| 3-B | completed | 3-B/metadata.json:10 |
| 4-A | completed | 4-A/metadata.json:10 |
| 5-A | completed | 5-A/metadata.json:10 |
| 6-B | completed | 6-B/metadata.json:10 |
| 7-P | completed | 7-P/metadata.json:11 |

没有重试段。

引擎错误行（排除 no error 等误中）：

没有。

原始日志、回答 JSON、配置备份、exe 和崩溃转储留在原始目录；不提交。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
