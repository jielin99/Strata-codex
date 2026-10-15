# 03：verify 窗口列数与 GPU 时间

本轮只记录测量数据，不做原因分析。原始记录保留在手册指定的 `03-window-t` 原始目录，下文原始文件引用均相对于该目录。

## 执行环境

- 记录时间：2026-10-15T23:13:21.286519+08:00（`env.txt:1`）。
- 引擎 HEAD：`29825274e3de26b35101d73be2d793315453a6ac`（`env.txt:2`）。
- 程序 `build-sycl-win/strata.exe`：32693760 字节，修改时间 2026-10-14T14:56:46.468059+08:00（`env.txt:3`、`env.txt:4`）。
- SHA256：`7b40f6b5062f83d98a4144f6c63e1d5f0a9eaa7401dd8ade357d20616b3853b0`（`env.txt:5`），与 01 记录相同。
- GPU 与驱动：Intel(R) Arc(TM) 140T GPU (32GB) 32.0.101.8826（`env.txt:52`）。
- 用户已确认插电、最佳性能、运行中不使用电脑（`env.txt:6`）。注册表交流电覆盖方案为 `ded574b5-45a0-4f42-8737-46345c09c238`，对应最佳性能（`env.txt:45`）；电源模式查询命令不受支持，按手册使用注册表后备方法。
- 统计数据开始于 2026/10/15 2:32:52（`env.txt:12`）。本轮未重启。

## 窗口分布与 GPU 时间

下表原样记录 `by-t.tsv` 中 `all` 各行的前六项统计；完整表还包括 staging 和 since-previous 中位数。窗口包含预热期间产生的匹配行，未按正式请求过滤。

| T | 窗口数 | 占比 | GPU 中位数 ms | GPU 最小 ms | GPU 最大 ms | 来源 |
|---|---|---|---|---|---|---|
| 1 | 103 | 0.103 | 163.1 | 151.3 | 197.4 | `by-t.tsv:12` |
| 2 | 122 | 0.122 | 204.8 | 194.7 | 225.7 | `by-t.tsv:13` |
| 3 | 105 | 0.105 | 261.0 | 245.2 | 340.5 | `by-t.tsv:14` |
| 4 | 525 | 0.523 | 278.6 | 258.5 | 354.9 | `by-t.tsv:15` |
| 6 | 148 | 0.148 | 541.2 | 503.3 | 623.0 | `by-t.tsv:16` |

vdbg_windows: 1003 windows from 2 log(s) -> windows.tsv, by-t.tsv（`vdbg.txt:1`）。

本轮未观察到 T=5 的窗口，未测得该列数的 GPU 时间（`by-t.tsv` 的全部分组行，逐窗口记录见 `windows.tsv`）。

## 四段生成速度

N 段不加计时或调试开关；D 段设置 `STRATA_VERIFY_DEBUG=1`、`STRATA_DECODE_TIMING=1`。D 段会增加拷贝、同步和打印，生成速度不能与 N 段比较；正常生成速度只看 N 段。

| 段 | q1 中位数 tok/s | q2 中位数 tok/s | q3 中位数 tok/s | 全部请求中位数 tok/s | 最小–最大 tok/s | 原始来源 |
|---|---|---|---|---|---|---|
| 1-N | 10.2 | 7.1 | 7.1 | 7.3 | 7.0–10.3 | `1-N/bench.json` 行 15, 35, 55, 75, 95, 115, 135, 155, 175 |
| 2-D | 10.4 | 7.0 | 7.2 | 7.6 | 6.5–10.6 | `2-D/bench.json` 行 15, 35, 55, 75, 95, 115, 135, 155, 175 |
| 3-D | 10.2 | 7.2 | 7.0 | 7.2 | 6.4–10.3 | `3-D/bench.json` 行 15, 35, 55, 75, 95, 115, 135, 155, 175 |
| 4-N | 10.0 | 6.7 | 7.4 | 7.4 | 6.5–10.3 | `4-N/bench.json` 行 15, 35, 55, 75, 95, 115, 135, 155, 175 |

逐请求数字和字段行号见 `timing.tsv`。请求序号按执行顺序，问题编号为基准工具索引加一；中位数只统计成功且有生成速度的正式请求。

## 窗口数核对

| 段 | vdbg 窗口数 | decode timing windows 逐行之和 | decode 原始来源 |
|---|---|---|---|
| 2-D | 495 | 414 | `2-D/engine.log` 行 1031, 1157, 1283, 1657, 4201, 7490, 11398, 13942, 17602, 20952, 23496, 27094, 30754 |
| 3-D | 508 | 427 | `3-D/engine.log` 行 1031, 1157, 1283, 1657, 4263, 8110, 11584, 14252, 17726, 21386, 23992, 27528, 31560 |

vdbg 窗口数按 `windows.tsv` 的 segment 字段计数；总数见 `vdbg.txt:1`。两种计数均包括本段预热。decode 求和只读取 `strata decode timing:` 行中的 windows 字段。

两段的两种窗口计数均不相等，以上按实际输出记录。

## 执行记录与偏离

驱动从 01 的 `drive.py` 复制到原始目录后修改：更换输出目录，顺序改为 N、D、D、N；清理变量列表增加 `STRATA_VERIFY_DEBUG`，D 段设置上述两个开关；取消带宽探针调用；增加每段最多三次的失败重试及结束时文件校验。复用原驱动的就绪等待、请求超时、预热、九个短请求、进程树清理、退出后等待及追加日志截取。原驱动副本为 `drive-01-original.py`。

每段就绪等待与单请求超时上限沿用 01；只结束本次启动的服务进程树，确认引擎退出后等待规定的 60 秒，再截取追加日志。

| 段 | 开始 | 结束 | 状态 | 原始来源 |
|---|---|---|---|---|
| 1-N | 2026-10-15 23:13:26 | 2026-10-15 23:18:14 | completed | `1-N/metadata.json:3`；`1-N/metadata.json:9`；`1-N/metadata.json:7` |
| 2-D | 2026-10-15 23:18:17 | 2026-10-15 23:23:05 | completed | `2-D/metadata.json:3`；`2-D/metadata.json:12`；`2-D/metadata.json:10` |
| 3-D | 2026-10-15 23:23:08 | 2026-10-15 23:27:59 | completed | `3-D/metadata.json:3`；`3-D/metadata.json:12`；`3-D/metadata.json:10` |
| 4-N | 2026-10-15 23:28:02 | 2026-10-15 23:32:52 | completed | `4-N/metadata.json:3`；`4-N/metadata.json:9`；`4-N/metadata.json:7` |

| 段 | 正式请求数 | 失败请求数（含预热） | 新增崩溃转储数 | 来源 |
|---|---|---|---|---|
| 1-N | 9 | 0 | 0 | `collection-check.json:8` 所在对象的 requests、failures、new_dumps 字段 |
| 2-D | 9 | 0 | 0 | `collection-check.json:15` 所在对象的 requests、failures、new_dumps 字段 |
| 3-D | 9 | 0 | 0 | `collection-check.json:22` 所在对象的 requests、failures、new_dumps 字段 |
| 4-N | 9 | 0 | 0 | `collection-check.json:29` 所在对象的 requests、failures、new_dumps 字段 |

失败重试次数为 0（`collection-check.json:44`）；未产生驱动致命错误记录（`collection-check.json:45`）。
配置及引擎程序 SHA256 均未变化（`checks.json:3`、`checks.json:4`）；引擎工作区状态为空（`git-status-before.txt`、`git-status-after.txt`）。

未做：4K 长提示、重新编译、引擎或配置修改、原因分析，均不在本轮范围内。

## 数据文件

- `windows.tsv`：每个匹配窗口的段、原始 engine.log 行号、T 与三个时间。
- `by-t.tsv`：按段及全体窗口汇总的分布与时间统计。
- `vdbg.txt`：提取工具报告的总窗口数。
- `timing.tsv`：四段逐请求数字，沿用 01 的列并附各字段的 bench.json 行号。
- `2-D-decode.txt`、`3-D-decode.txt`：全部 `strata decode` 行，前缀为本段 engine.log 行号。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
