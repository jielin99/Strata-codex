# 05：MoE 和 hc 读的环境变量测量

本轮只记录结果，不做分析或原因推断。原始记录保留在手册指定的 `05-moe-hc-env` 原始目录，以下文件引用均相对于该目录。

## 执行环境

- 开始记录：2026-10-16T01:27:49.141809+08:00（`env.txt:1`）。
- 引擎 HEAD：`7629f0b294bcaef91b971ac768a377f7a85518cd`（`env.txt:2`）；开始前跟踪文件无改动（`env.txt:7`）。
- 程序：32892416 字节，修改时间 2026-10-16T00:24:02.160723+08:00（`env.txt:3`、`env.txt:4`）。
- SHA256：`28ac70667e3929c2828a1e5d4b9cc971883c70b253a544d8586cdb8f35156a88`（`env.txt:5`），为第 04 轮编译的程序。
- 用户已确认插电、最佳性能、期间不使用电脑（`env.txt:6`）。
- 开机统计起点：Statistics since 2026/10/15 2:32:52（`env.txt:11`）。
- 交流电电源模式覆盖项：ActiveOverlayAcPowerScheme    REG_SZ    ded574b5-45a0-4f42-8737-46345c09c238（`env.txt:42`）。
- GPU 与驱动：Intel(R) Arc(TM) 140T GPU (32GB) 32.0.101.8826（`env.txt:48`）。
- 本轮未重启；注册表覆盖项对应「最佳性能」。电源模式查询命令不受支持，使用手册指定的注册表后备方法。

## 分段设置

所有段设置 `STRATA_VERIFY_DEBUG=1`、`STRATA_DECODE_TIMING=1`。每段先删除手册列出的变量及所有待测开关、`STRATA_MMVQ_Q6_SWAR`，再设置本段变量。

| 段 | 附加环境变量 |
|---|---|
| 1-base | 无 |
| 2-split | `STRATA_EXPERT_SPLIT=1` |
| 3-lanes16 | `STRATA_GU_LANES=16`、`STRATA_DOWN_LANES=16` |
| 4-base | 无 |
| 5-lanes4 | `STRATA_GU_LANES=4`、`STRATA_DOWN_LANES=4` |
| 6-hcdirect | `STRATA_GR_DOWN_SLICED=0` |
| 7-hcnorm | `STRATA_GR_NORM_SPLIT=0` |
| 8-base | 无 |

每段启动服务、预热、执行三个短问题各三次，结束服务进程树，待引擎全部退出后等待 60 秒，再保存日志增量。不跑 4K。

## 按窗口列数记录 GPU 时间

表中为 GPU 时间中位数，单位 ms；括号内为匹配窗口数，每格附原始汇总表行号。窗口包含预热期间的匹配记录，未按正式请求过滤。

| T | 1-base | 2-split | 3-lanes16 | 4-base | 5-lanes4 | 6-hcdirect | 7-hcnorm | 8-base |
|---|---|---|---|---|---|---|---|---|
| 1 | 166.6 (56)；`by-t.tsv:2` | 187.0 (56)；`by-t.tsv:7` | 165.8 (59)；`by-t.tsv:12` | 165.6 (57)；`by-t.tsv:17` | 166.4 (50)；`by-t.tsv:22` | 179.0 (51)；`by-t.tsv:27` | 170.3 (53)；`by-t.tsv:32` | 165.7 (57)；`by-t.tsv:37` |
| 2 | 209.8 (68)；`by-t.tsv:3` | 244.6 (67)；`by-t.tsv:8` | 211.5 (57)；`by-t.tsv:13` | 208.2 (65)；`by-t.tsv:18` | 208.9 (60)；`by-t.tsv:23` | 224.3 (72)；`by-t.tsv:28` | 213.8 (66)；`by-t.tsv:33` | 209.2 (60)；`by-t.tsv:38` |
| 3 | 266.1 (65)；`by-t.tsv:4` | 312.8 (42)；`by-t.tsv:9` | 266.0 (53)；`by-t.tsv:14` | 263.8 (45)；`by-t.tsv:19` | 266.9 (54)；`by-t.tsv:24` | 283.7 (50)；`by-t.tsv:29` | 270.2 (60)；`by-t.tsv:34` | 266.5 (64)；`by-t.tsv:39` |
| 4 | 285.7 (260)；`by-t.tsv:5` | 341.9 (268)；`by-t.tsv:10` | 287.1 (260)；`by-t.tsv:15` | 284.6 (260)；`by-t.tsv:20` | 284.5 (266)；`by-t.tsv:25` | 307.1 (259)；`by-t.tsv:30` | 288.2 (251)；`by-t.tsv:35` | 284.2 (260)；`by-t.tsv:40` |
| 6 | 555.4 (75)；`by-t.tsv:6` | 628.7 (74)；`by-t.tsv:11` | 555.8 (74)；`by-t.tsv:16` | 550.3 (74)；`by-t.tsv:21` | 552.8 (74)；`by-t.tsv:26` | 581.0 (74)；`by-t.tsv:31` | 553.7 (74)；`by-t.tsv:36` | 553.7 (74)；`by-t.tsv:41` |

vdbg_windows: 4064 windows from 8 log(s) -> windows.tsv, by-t.tsv（`vdbg.txt:1`）。逐窗口原始行号见 `windows.tsv` 的 `segment` 和 `line` 列，对应 `<段>/engine.log`。

## 草稿接受数 / 提供数

仅累计正式请求。生成 tok/s 和首 token 时间保存在 `timing.tsv`，不据此作结论。

| 段 | 草稿接受数之和 | 草稿提供数之和 | 缺失接受数 / 提供数字段的请求数 | 原始来源 |
|---|---|---|---|---|
| 1-base | 475 | 941 | 0 / 0 | `timing.tsv:2`–`timing.tsv:10` |
| 2-split | 496 | 911 | 0 / 0 | `timing.tsv:11`–`timing.tsv:19` |
| 3-lanes16 | 505 | 899 | 0 / 0 | `timing.tsv:20`–`timing.tsv:28` |
| 4-base | 503 | 891 | 0 / 0 | `timing.tsv:29`–`timing.tsv:37` |
| 5-lanes4 | 496 | 922 | 0 / 0 | `timing.tsv:38`–`timing.tsv:46` |
| 6-hcdirect | 498 | 906 | 0 / 0 | `timing.tsv:47`–`timing.tsv:55` |
| 7-hcnorm | 495 | 895 | 0 / 0 | `timing.tsv:56`–`timing.tsv:64` |
| 8-base | 492 | 925 | 0 / 0 | `timing.tsv:65`–`timing.tsv:73` |

每个数字的原始 `bench.json` 行号列在 `timing.tsv`，各段求和结果也记录在原始 `collection-check.json` 的 `draft_totals`。

## 错误关键词匹配与执行记录

按手册对全部段及重试目录的引擎日志扫描 `error`、`failed`、`mismatch` 以及非零 `nonfinite=`，匹配 40 行（`collection-check.json:6`；逐段扫描行数记录在该文件的 `log_scan`）。以下逐行记录匹配内容。

- `1-base/engine.log:34`：`strata verify: captured the 6-token window (upload no error, sync no error)`
- `1-base/engine.log:283`：`strata verify: captured the 3-token window (upload no error, sync no error)`
- `1-base/engine.log:408`：`strata verify: captured the 1-token window (upload no error, sync no error)`
- `1-base/engine.log:471`：`strata verify: captured the 2-token window (upload no error, sync no error)`
- `1-base/engine.log:658`：`strata verify: captured the 4-token window (upload no error, sync no error)`
- `2-split/engine.log:34`：`strata verify: captured the 6-token window (upload no error, sync no error)`
- `2-split/engine.log:283`：`strata verify: captured the 3-token window (upload no error, sync no error)`
- `2-split/engine.log:408`：`strata verify: captured the 1-token window (upload no error, sync no error)`
- `2-split/engine.log:533`：`strata verify: captured the 2-token window (upload no error, sync no error)`
- `2-split/engine.log:658`：`strata verify: captured the 4-token window (upload no error, sync no error)`
- `3-lanes16/engine.log:34`：`strata verify: captured the 6-token window (upload no error, sync no error)`
- `3-lanes16/engine.log:283`：`strata verify: captured the 3-token window (upload no error, sync no error)`
- `3-lanes16/engine.log:408`：`strata verify: captured the 1-token window (upload no error, sync no error)`
- `3-lanes16/engine.log:533`：`strata verify: captured the 2-token window (upload no error, sync no error)`
- `3-lanes16/engine.log:658`：`strata verify: captured the 4-token window (upload no error, sync no error)`
- `4-base/engine.log:34`：`strata verify: captured the 6-token window (upload no error, sync no error)`
- `4-base/engine.log:283`：`strata verify: captured the 3-token window (upload no error, sync no error)`
- `4-base/engine.log:408`：`strata verify: captured the 1-token window (upload no error, sync no error)`
- `4-base/engine.log:533`：`strata verify: captured the 2-token window (upload no error, sync no error)`
- `4-base/engine.log:658`：`strata verify: captured the 4-token window (upload no error, sync no error)`
- `5-lanes4/engine.log:34`：`strata verify: captured the 6-token window (upload no error, sync no error)`
- `5-lanes4/engine.log:283`：`strata verify: captured the 3-token window (upload no error, sync no error)`
- `5-lanes4/engine.log:408`：`strata verify: captured the 1-token window (upload no error, sync no error)`
- `5-lanes4/engine.log:533`：`strata verify: captured the 2-token window (upload no error, sync no error)`
- `5-lanes4/engine.log:658`：`strata verify: captured the 4-token window (upload no error, sync no error)`
- `6-hcdirect/engine.log:34`：`strata verify: captured the 6-token window (upload no error, sync no error)`
- `6-hcdirect/engine.log:283`：`strata verify: captured the 3-token window (upload no error, sync no error)`
- `6-hcdirect/engine.log:408`：`strata verify: captured the 1-token window (upload no error, sync no error)`
- `6-hcdirect/engine.log:533`：`strata verify: captured the 2-token window (upload no error, sync no error)`
- `6-hcdirect/engine.log:658`：`strata verify: captured the 4-token window (upload no error, sync no error)`
- `7-hcnorm/engine.log:34`：`strata verify: captured the 6-token window (upload no error, sync no error)`
- `7-hcnorm/engine.log:283`：`strata verify: captured the 3-token window (upload no error, sync no error)`
- `7-hcnorm/engine.log:408`：`strata verify: captured the 1-token window (upload no error, sync no error)`
- `7-hcnorm/engine.log:533`：`strata verify: captured the 2-token window (upload no error, sync no error)`
- `7-hcnorm/engine.log:658`：`strata verify: captured the 4-token window (upload no error, sync no error)`
- `8-base/engine.log:34`：`strata verify: captured the 6-token window (upload no error, sync no error)`
- `8-base/engine.log:283`：`strata verify: captured the 3-token window (upload no error, sync no error)`
- `8-base/engine.log:408`：`strata verify: captured the 1-token window (upload no error, sync no error)`
- `8-base/engine.log:533`：`strata verify: captured the 2-token window (upload no error, sync no error)`
- `8-base/engine.log:658`：`strata verify: captured the 4-token window (upload no error, sync no error)`

| 段 | 开始 | 结束 | 状态 | 正式请求数 | 含预热的请求失败数 | 新增崩溃文件数 | 来源 |
|---|---|---|---|---|---|---|---|
| 1-base | 2026-10-16 01:27:52 | 2026-10-16 01:32:55 | completed | 9 | 0 | 0 | `1-base/metadata.json:3`、`1-base/metadata.json:12`、`1-base/metadata.json:10`、`1-base/metadata.json:13`；计数见 `collection-check.json` 对应段 |
| 2-split | 2026-10-16 01:32:58 | 2026-10-16 01:38:25 | completed | 9 | 0 | 0 | `2-split/metadata.json:3`、`2-split/metadata.json:13`、`2-split/metadata.json:11`、`2-split/metadata.json:14`；计数见 `collection-check.json` 对应段 |
| 3-lanes16 | 2026-10-16 01:38:27 | 2026-10-16 01:43:27 | completed | 9 | 0 | 0 | `3-lanes16/metadata.json:3`、`3-lanes16/metadata.json:14`、`3-lanes16/metadata.json:12`、`3-lanes16/metadata.json:15`；计数见 `collection-check.json` 对应段 |
| 4-base | 2026-10-16 01:43:30 | 2026-10-16 01:48:25 | completed | 9 | 0 | 0 | `4-base/metadata.json:3`、`4-base/metadata.json:12`、`4-base/metadata.json:10`、`4-base/metadata.json:13`；计数见 `collection-check.json` 对应段 |
| 5-lanes4 | 2026-10-16 01:48:28 | 2026-10-16 01:53:29 | completed | 9 | 0 | 0 | `5-lanes4/metadata.json:3`、`5-lanes4/metadata.json:14`、`5-lanes4/metadata.json:12`、`5-lanes4/metadata.json:15`；计数见 `collection-check.json` 对应段 |
| 6-hcdirect | 2026-10-16 01:53:31 | 2026-10-16 01:58:40 | completed | 9 | 0 | 0 | `6-hcdirect/metadata.json:3`、`6-hcdirect/metadata.json:13`、`6-hcdirect/metadata.json:11`、`6-hcdirect/metadata.json:14`；计数见 `collection-check.json` 对应段 |
| 7-hcnorm | 2026-10-16 01:58:43 | 2026-10-16 02:03:42 | completed | 9 | 0 | 0 | `7-hcnorm/metadata.json:3`、`7-hcnorm/metadata.json:13`、`7-hcnorm/metadata.json:11`、`7-hcnorm/metadata.json:14`；计数见 `collection-check.json` 对应段 |
| 8-base | 2026-10-16 02:03:44 | 2026-10-16 02:08:41 | completed | 9 | 0 | 0 | `8-base/metadata.json:3`、`8-base/metadata.json:12`、`8-base/metadata.json:10`、`8-base/metadata.json:13`；计数见 `collection-check.json` 对应段 |

共 72 个正式请求，失败 0，新增崩溃文件 0，重试目录 0，致命错误记录存在：False（`collection-check.json:2`、`collection-check.json:3`、`collection-check.json:4`、`collection-check.json:7`、`collection-check.json:8`）。

## 方法和结束状态

驱动复制自 03 原始目录所用脚本：将分段改为本轮八段，扩充变量清理列表，各段统一启用 DEBUG 和 TIMING，增加开始与结束的引擎版本、程序元数据及配置哈希核对。服务启动、预热、短请求、进程树清理、等待和日志截取流程沿用。未偏离手册的实验步骤。

未做回答一致性核对：新版手册明确取消此项；`bench.json` 不含回答文本。本轮未修改引擎代码、未重新编译、未修改配置。

结束引擎 HEAD：`7629f0b294bcaef91b971ac768a377f7a85518cd`（`checks.json:3`）；exe SHA256：`28ac70667e3929c2828a1e5d4b9cc971883c70b253a544d8586cdb8f35156a88`（`checks.json:7`）。配置与程序均未变化，跟踪文件状态为空（`checks.json:9`、`checks.json:10`、`checks.json:11`）。

公开数据：`windows.tsv` 是逐窗口数字与原始日志行号；`by-t.tsv` 是分段和全体按 T 汇总；`vdbg.txt` 是解析工具计数；`timing.tsv` 是逐请求计时、草稿计数和原始行号。其余日志和响应只保留在原始目录。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
