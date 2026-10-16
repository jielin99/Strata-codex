# 09：MoE gate/up 共享内存码本测量

执行时间：2026-10-17T04:28:22.014915+08:00（`environment.json:2`）。Windows，Arc 140T。用户确认插电、最佳性能、实验期间不使用电脑、共享 GPU 内存上限 75%。

- 起始引擎 `0408d9163cdc305a22f09dd48692122018b58fa7`（`environment.json:3`），执行引擎 `d35f55e49ea390f7121f1d1b4a21c682184e8183`（`engine-build.json:6`）。
- 起始 exe：33101312 字节，修改时间 2026-10-17T01:00:35.896331+08:00，SHA256 `9dca0dc14910fa9e2b4eb233e68466ac44d4c7c997b8c7169b2d3631a0f22eec`（`environment.json:6`、`environment.json:7`、`environment.json:8`）。
- 执行 exe：33721856 字节，修改时间 2026-10-17T04:30:43.466328+08:00，SHA256 `1a1e28c4b05b739da3b07f4710df283dc1053588bdd2f9bf0732c7a2396c4d03`（`engine-build.json:9`、`engine-build.json:10`、`engine-build.json:11`）。
- 电源模式：最佳性能（`environment.json:13`）。可用物理内存 60751851520 字节（`environment.json:11`）。
- GPU：Intel(R) Arc(TM) 140T GPU (32GB)，驱动 `32.0.101.8826`（`environment.json:14`）。
- 开机时间：2026/10/16 16:15:08（`environment.json:12`）；本轮未发起重启。

引擎构建退出码 0，耗时 335.348 秒（`engine-build.json:5`、`engine-build.json:4`）。命令、工具构建耗时、文件大小及哈希见 `09-moe-grid/build.txt`，每项附原始行号。

## 内核判定

`choice.txt` 原样如下。完整性及双校验和来源：六个原始 `mp-*.tsv` 全部数据行和 `mp-exit.txt`；组跨步核对来源：`ngp-off.txt:58: native_grouped_parity: 0 failures`；`ngp-on.txt:58: native_grouped_parity: 0 failures`。

```text
off t1..t4_us=510.900000, 863.300000, 1233.400000, 1501.900000 W_us=1261.356000
on t1..t4_us=507.200000, 867.500000, 1222.200000, 1495.200000 W_us=1256.002000
W(on)/W(off)=0.9957553616901176
integrity=True; errors=[]
keys=154; key_sets_equal=True
checksum_differences=0; gu_checksum_differences=0
native_grouped_parity=True
winner=False
T3 window reference (not used for selection):
state	mem	phase	median_us_per_layer
off	dram	all	1233.4
off	dram	gu	821.6
off	dram	down	395.9
off	cached	all	1125.6
off	cached	gu	751.4
off	cached	down	379.8
on	dram	all	1222.2
on	dram	gu	814.4
on	dram	down	407.3
on	cached	all	1066.3
on	cached	gu	717.2
on	cached	down	382.8
Per-file integrity:
file	rows	all_rows	exit
mp-1-off.tsv	462	154	0
mp-1-on.tsv	462	154	0
mp-2-on.tsv	462	154	0
mp-2-off.tsv	462	154	0
mp-3-off.tsv	462	154	0
mp-3-on.tsv	462	154	0
```

| case | mem | phase | us/layer | 原始来源 |
| --- | --- | --- | --- | --- |
| T1 | dram | all | 517.4 | mp-1-off.tsv:7 |
| T2 | dram | all | 863.3 | mp-1-off.tsv:73 |
| T3 | dram | all | 1245.4 | mp-1-off.tsv:139 |
| T3 | dram | gu | 821.6 | mp-1-off.tsv:140 |
| T3 | dram | down | 395.3 | mp-1-off.tsv:141 |
| T3 | cached | all | 1125.6 | mp-1-off.tsv:172 |
| T3 | cached | gu | 771.9 | mp-1-off.tsv:173 |
| T3 | cached | down | 393.5 | mp-1-off.tsv:174 |
| T4 | dram | all | 1501.9 | mp-1-off.tsv:205 |
| T1 | dram | all | 497.8 | mp-1-on.tsv:8 |
| T2 | dram | all | 1324.4 | mp-1-on.tsv:74 |
| T3 | dram | all | 1222.2 | mp-1-on.tsv:140 |
| T3 | dram | gu | 814.4 | mp-1-on.tsv:141 |
| T3 | dram | down | 402.8 | mp-1-on.tsv:142 |
| T3 | cached | all | 1103.4 | mp-1-on.tsv:173 |
| T3 | cached | gu | 717.2 | mp-1-on.tsv:174 |
| T3 | cached | down | 384.3 | mp-1-on.tsv:175 |
| T4 | dram | all | 1495.2 | mp-1-on.tsv:206 |
| T1 | dram | all | 492.9 | mp-2-off.tsv:7 |
| T2 | dram | all | 869.5 | mp-2-off.tsv:73 |
| T3 | dram | all | 1218.6 | mp-2-off.tsv:139 |
| T3 | dram | gu | 811.3 | mp-2-off.tsv:140 |
| T3 | dram | down | 395.9 | mp-2-off.tsv:141 |
| T3 | cached | all | 1133.9 | mp-2-off.tsv:172 |
| T3 | cached | gu | 751.4 | mp-2-off.tsv:173 |
| T3 | cached | down | 378.8 | mp-2-off.tsv:174 |
| T4 | dram | all | 1481.0 | mp-2-off.tsv:205 |
| T1 | dram | all | 507.2 | mp-2-on.tsv:8 |
| T2 | dram | all | 841.5 | mp-2-on.tsv:74 |
| T3 | dram | all | 1223.3 | mp-2-on.tsv:140 |
| T3 | dram | gu | 796.5 | mp-2-on.tsv:141 |
| T3 | dram | down | 407.3 | mp-2-on.tsv:142 |
| T3 | cached | all | 1053.6 | mp-2-on.tsv:173 |
| T3 | cached | gu | 713.7 | mp-2-on.tsv:174 |
| T3 | cached | down | 377.5 | mp-2-on.tsv:175 |
| T4 | dram | all | 1486.8 | mp-2-on.tsv:206 |
| T1 | dram | all | 510.9 | mp-3-off.tsv:7 |
| T2 | dram | all | 842.8 | mp-3-off.tsv:73 |
| T3 | dram | all | 1233.4 | mp-3-off.tsv:139 |
| T3 | dram | gu | 855.0 | mp-3-off.tsv:140 |
| T3 | dram | down | 420.9 | mp-3-off.tsv:141 |
| T3 | cached | all | 1115.5 | mp-3-off.tsv:172 |
| T3 | cached | gu | 723.3 | mp-3-off.tsv:173 |
| T3 | cached | down | 379.8 | mp-3-off.tsv:174 |
| T4 | dram | all | 1580.7 | mp-3-off.tsv:205 |
| T1 | dram | all | 534.3 | mp-3-on.tsv:8 |
| T2 | dram | all | 867.5 | mp-3-on.tsv:74 |
| T3 | dram | all | 1191.5 | mp-3-on.tsv:140 |
| T3 | dram | gu | 844.8 | mp-3-on.tsv:141 |
| T3 | dram | down | 414.9 | mp-3-on.tsv:142 |
| T3 | cached | all | 1066.3 | mp-3-on.tsv:173 |
| T3 | cached | gu | 718.8 | mp-3-on.tsv:174 |
| T3 | cached | down | 382.8 | mp-3-on.tsv:175 |
| T4 | dram | all | 1536.3 | mp-3-on.tsv:206 |

## 端到端与日常配置

第 3.3 节不胜出。按计划，第 4 节端到端 A/B、第 5 节配置修改未做。日常配置未改。

## 执行记录、偏离和失败

- 仅快进更新引擎并构建计划指定的 SYCL 后端；工具编译到新目录 build-lab-moe9。未修改引擎源码，未安装或下载依赖。
- 已准备以 08 为底子的端到端驱动，调整目录、开关清理及配置准入条件，移除额外 PROFILE 段；内核阶段不胜出，驱动未执行。
- 未做其他模型、其他硬件、CUDA 或 HIP 验证。未发起额外测试。

没有重试段。
构建及内核测量没有失败或超时；退出码见 build.txt、mp-exit.txt。

引擎错误行（排除 no error 等误中）：

端到端未运行，无该项日志。

原始日志、执行脚本及回退用 exe 留在原始目录，未提交。本轮未生成端到端回答或配置备份。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
