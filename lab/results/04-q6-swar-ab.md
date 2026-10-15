# 04：Q6 SWAR 端到端 A/B

本轮只记录结果，不做分析或原因推断。原始记录保留在手册指定的 `04-q6-swar-ab` 原始目录，以下原始文件引用均相对于该目录。

## 执行环境

- 开始记录：2026-10-16T00:16:48.018285+08:00（`environment.json:2`）。
- 旧引擎 HEAD：`29825274e3de26b35101d73be2d793315453a6ac`（`environment.json:3`）；开始前已检查跟踪文件无改动。
- 旧程序：32693760 字节，修改时间 2026-10-14T14:56:46.468059+08:00，SHA256 `7b40f6b5062f83d98a4144f6c63e1d5f0a9eaa7401dd8ade357d20616b3853b0`（`environment.json:5`、`environment.json:6`、`environment.json:7`）。
- 已收到插电、最佳性能、运行期间不使用电脑的确认（`environment.json:9`）。
- 开机统计起点：Statistics since 2026/10/15 2:32:52（`env.txt:4`）。
- 交流电电源模式覆盖项：ActiveOverlayAcPowerScheme    REG_SZ    ded574b5-45a0-4f42-8737-46345c09c238（`env.txt:35`）。
- GPU 和驱动：Intel(R) Arc(TM) 140T GPU (32GB) 32.0.101.8826（`env.txt:41`）。
- 本轮未重启；覆盖项 GUID 对应「最佳性能」。电源模式查询命令不受支持，使用手册指定的注册表后备方法。

## 更新和编译

引擎快进到 `7629f0b294bcaef91b971ac768a377f7a85518cd`，差异只有 `sycl/src/kernels/cuda/native_mmvq.dp.cpp`。执行 `<repo>/sycl/tools/build_windows.bat`，退出码 0，耗时 340.333 秒（`build.json`、`build.txt:1`–`build.txt:8`）。 原始行：`build.json:3`、`build.json:4`、`build.json:11`、`build.json:12`。
新程序：32892416 字节，修改时间 2026-10-16T00:24:02.160723+08:00，SHA256 `28ac70667e3929c2828a1e5d4b9cc971883c70b253a544d8586cdb8f35156a88`（`build.json` 的 `new_exe` 字段；公开副本见 `build.txt`）。 原始行：`build.json:15`、`build.json:16`、`build.json:17`。

## 七段测量

O 为旧程序；A 为新程序且开关从环境删除；B 为新程序且 `STRATA_MMVQ_Q6_SWAR=1`。每段先清理手册列出的环境变量，预热后跑三个短问题各三次，不跑 4K。

| 段 | q1 tok/s 中位数 | q2 | q3 | 全部 tok/s 中位数 | tok/s 最小–最大 | 首 token 秒中位数 | 秒最小–最大 | 数字来源 |
|---|---|---|---|---|---|---|---|---|
| 0-O | 9.9 | 7.7 | 7.4 | 7.7 | 7.0–10.1 | 4.398 | 4.124–4.863 | `timing.tsv:2`–`timing.tsv:10` |
| 1-A | 10.0 | 7.1 | 7.1 | 7.2 | 6.2–10.1 | 4.433 | 4.134–5.780 | `timing.tsv:11`–`timing.tsv:19` |
| 2-B | 10.3 | 7.4 | 7.7 | 7.7 | 7.2–10.8 | 3.020 | 2.774–3.342 | `timing.tsv:20`–`timing.tsv:28` |
| 3-B | 10.4 | 7.2 | 7.3 | 7.8 | 7.0–10.7 | 3.088 | 2.827–3.396 | `timing.tsv:29`–`timing.tsv:37` |
| 4-A | 9.8 | 6.9 | 6.7 | 7.1 | 6.7–10.0 | 4.468 | 4.195–5.111 | `timing.tsv:38`–`timing.tsv:46` |
| 5-A | 10.0 | 6.8 | 6.6 | 6.9 | 6.4–10.5 | 4.458 | 4.155–4.938 | `timing.tsv:47`–`timing.tsv:55` |
| 6-B | 10.3 | 7.1 | 7.1 | 7.2 | 6.5–10.6 | 3.071 | 2.809–3.371 | `timing.tsv:56`–`timing.tsv:64` |

每个数字的原始 `bench.json` 行号列在 `timing.tsv`；表内统计由对应九行计算，计算结果同时保存在原始目录的 `summary.json`。

## A/B 合并

| 组 | 问题 | 生成 tok/s 中位数 | 首 token 秒中位数 | 原始来源 |
|---|---|---|---|---|
| A | q1 | 10.0 | 4.938 | 1-A/bench.json, 4-A/bench.json, 5-A/bench.json；逐项行号见 `timing.tsv` |
| A | q2 | 6.9 | 4.184 | 1-A/bench.json, 4-A/bench.json, 5-A/bench.json；逐项行号见 `timing.tsv` |
| A | q3 | 6.9 | 4.452 | 1-A/bench.json, 4-A/bench.json, 5-A/bench.json；逐项行号见 `timing.tsv` |
| B | q1 | 10.3 | 3.354 | 2-B/bench.json, 3-B/bench.json, 6-B/bench.json；逐项行号见 `timing.tsv` |
| B | q2 | 7.2 | 2.816 | 2-B/bench.json, 3-B/bench.json, 6-B/bench.json；逐项行号见 `timing.tsv` |
| B | q3 | 7.3 | 3.071 | 2-B/bench.json, 3-B/bench.json, 6-B/bench.json；逐项行号见 `timing.tsv` |

## 回答核对

按手册的无文本分支记录：`bench.json` 没有回答文本，`answers.tsv` 全部写「无文本」。九组中全部相同零组、有差异零组、无法核对九组；有差异零组不代表回答一致（`answers-check.txt:2`–`answers-check.txt:11`）。新旧程序及开关两侧的回答一致性未验证，原因是指定的 `bench.json` 不含文本。

`bench.json` 顶层字段：chat, prompts, agent, clients, skipped, failures。请求字段：ok, err, ttft_s, total_s, prompt_tokens, reused_tokens, read_tokens, generated_tokens, prompt_tps, prompt_tps_source, decode_tps, decode_tps_source, prompt_ms, decode_ms, drafts_offered, drafts_accepted, run, prompt（`0-O/bench.json` 第一条请求对象）。

## 执行记录和结束状态

- 0-O：2026-10-16 00:16:51 至 2026-10-16 00:21:37，状态 completed，正式请求 9，含预热的请求失败 0，新增崩溃文件 0（`0-O/metadata.json`）。 原始行：`0-O/metadata.json:3`、`0-O/metadata.json:9`、`0-O/metadata.json:7`、`0-O/metadata.json:10`；请求数和崩溃文件计数见 `collection-check.json` 对应段。
- 1-A：2026-10-16 00:27:27 至 2026-10-16 00:32:25，状态 completed，正式请求 9，含预热的请求失败 0，新增崩溃文件 0（`1-A/metadata.json`）。 原始行：`1-A/metadata.json:3`、`1-A/metadata.json:9`、`1-A/metadata.json:7`、`1-A/metadata.json:10`；请求数和崩溃文件计数见 `collection-check.json` 对应段。
- 2-B：2026-10-16 00:32:27 至 2026-10-16 00:37:01，状态 completed，正式请求 9，含预热的请求失败 0，新增崩溃文件 0（`2-B/metadata.json`）。 原始行：`2-B/metadata.json:3`、`2-B/metadata.json:11`、`2-B/metadata.json:9`、`2-B/metadata.json:12`；请求数和崩溃文件计数见 `collection-check.json` 对应段。
- 3-B：2026-10-16 00:37:03 至 2026-10-16 00:41:39，状态 completed，正式请求 9，含预热的请求失败 0，新增崩溃文件 0（`3-B/metadata.json`）。 原始行：`3-B/metadata.json:3`、`3-B/metadata.json:11`、`3-B/metadata.json:9`、`3-B/metadata.json:12`；请求数和崩溃文件计数见 `collection-check.json` 对应段。
- 4-A：2026-10-16 00:41:41 至 2026-10-16 00:46:39，状态 completed，正式请求 9，含预热的请求失败 0，新增崩溃文件 0（`4-A/metadata.json`）。 原始行：`4-A/metadata.json:3`、`4-A/metadata.json:9`、`4-A/metadata.json:7`、`4-A/metadata.json:10`；请求数和崩溃文件计数见 `collection-check.json` 对应段。
- 5-A：2026-10-16 00:46:41 至 2026-10-16 00:51:39，状态 completed，正式请求 9，含预热的请求失败 0，新增崩溃文件 0（`5-A/metadata.json`）。 原始行：`5-A/metadata.json:3`、`5-A/metadata.json:9`、`5-A/metadata.json:7`、`5-A/metadata.json:10`；请求数和崩溃文件计数见 `collection-check.json` 对应段。
- 6-B：2026-10-16 00:51:42 至 2026-10-16 00:56:18，状态 completed，正式请求 9，含预热的请求失败 0，新增崩溃文件 0（`6-B/metadata.json`）。 原始行：`6-B/metadata.json:3`、`6-B/metadata.json:11`、`6-B/metadata.json:9`、`6-B/metadata.json:12`；请求数和崩溃文件计数见 `collection-check.json` 对应段。

共 63 个正式请求，失败 0，新增崩溃文件 0，重试目录 0，致命错误记录存在：False（`collection-check.json`）。未观察到卡住。 原始行：`collection-check.json:2`、`collection-check.json:3`、`collection-check.json:4`、`collection-check.json:5`、`collection-check.json:6`。

驱动以 03 使用的脚本为底子：增加旧程序备份、快进更新和编译步骤，将分段顺序改为 O/A/B/B/A/A/B，新增 SWAR 环境变量清理与 B 段设置，其余启动、预热、请求、进程树清理、等待及日志截取流程沿用。环境的 Git 和 exe 元数据保存在 `environment.json`，系统查询保存在 `env.txt`；这是记录文件布局的偏离，数据均已记录。未修改配置。

结束引擎 HEAD：`7629f0b294bcaef91b971ac768a377f7a85518cd`（`checks.json:3`）。最终 exe SHA256：`28ac70667e3929c2828a1e5d4b9cc971883c70b253a544d8586cdb8f35156a88`（`checks.json:7`）。配置哈希未变、跟踪文件状态为空（`checks.json:9`、`checks.json:10`）。保留新程序，开关默认关闭。

公开数据：`timing.tsv` 是逐请求数字及原始行号；`answers.tsv` 是无文本记录及来源；`answers-check.txt` 是各组核对状态；`build.txt` 是脱敏的构建命令、耗时、差异和程序元数据。完整日志与响应仅保留在原始目录。

自查：按 lab/README.md 的关键字列表扫描，未发现命中
