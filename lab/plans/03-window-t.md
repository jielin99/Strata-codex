# 03：引擎里每个 verify 窗口的列数和 GPU 时间（不改引擎）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\03-window-t\`（下文叫「原始目录」）。
- 结论写到 `lab/results/03-window-t.md`；可公开的数据文件放在 `lab/results/03-window-t/`（下文叫「数据目录」）。

**目的**：02 在 140T 上发现，Q6_K 的稠密 GEMV 在 5 列和 6 列时速度掉到约 5 GB/s（`lab/analysis/02-kernel-code.md` 第 5 节）。
这一份用引擎现成的开关 `STRATA_VERIFY_DEBUG=1` 测两件事：
1. 生成时，各种列数（T = 1–6）的 verify 窗口各占多少。
2. 每种 T 的窗口在 GPU 上花多少时间，引擎里是否也出现 5、6 列的大跌。

开了这个开关后，引擎每个窗口打印一行
`verify dbg: T=<T> window: since previous window <ms> ms, staging <ms> ms, gpu <ms> ms`（`sycl/src/core/verify.cpp:2318-2322`）。
这个开关**会改变运行**：图里每层多两个小拷贝，每个窗口结束后还要多做几次同步读取并打印几十行。所以这些段的生成 tok/s 不能和正常段比，
只用它们的 T 分布和 gpu 时间。生成 tok/s 看不开开关的段。

只测，不改引擎代码，不改 `strata-iq3_xxs.json`，不重新编译 `strata.exe`。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑。确认后中间不再问。
4. 在原始目录的 `env.txt` 记录（查法和 `plans/01` 第 0 节第 4 步相同）：
   - 日期时间、开机以来的时间。
   - `git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `29825274…`，不一致就停下来报告）。
   - `build-sycl-win\strata.exe` 的大小、修改时间和 SHA256（预期和 `plans/01` 时相同：32,693,760 字节，SHA256 以 `7b40f6b5` 开头；不同就停下来报告）。
   - 电源模式（以设置里的电源模式为准，不能用电源计划的名字代替）。
   - GPU 驱动版本。

## 1. 分段运行（交替跑 4 段）
驱动脚本以 `plans/01` 第 3 节用过的驱动脚本（在 `D:\dev\strata-lab\01-decode-bound\` 下）为底子，复制到原始目录再改，改了什么写进结论。

| 顺序 | 段 | 环境变量 |
|---|---|---|
| 1 | `1-N` | 不加开关 |
| 2 | `2-D` | `STRATA_VERIFY_DEBUG=1`、`STRATA_DECODE_TIMING=1` |
| 3 | `3-D` | 同 2-D |
| 4 | `4-N` | 同 1-N |

每段的做法和 `plans/01` 第 3 节完全相同：
1. 先从环境里**删除**这些变量：`STRATA_VERIFY_DEBUG`、`STRATA_DECODE_TIMING`、`STRATA_PREFILL_TIMING`、`STRATA_VERIFY_PROFILE`、`STRATA_VERIFY_EAGER`、
   `STRATA_SH_STREAM`、`STRATA_PREFILL_SYNC`、`STRATA_PF_STEP_SYNC`、`SYCL_UR_USE_LEVEL_ZERO_V2`、`UR_L0_USE_COPY_ENGINE`、`SYCL_UR_TRACE`，再按上表设置。
2. 记下 `strata-iq3_xxs.log` 当前的字节长度。
3. `sb.start_server(<配置>, 8080, None, <原始目录>\<段>\server.log)`，再 `sb.wait_ready(..., 1800)`。
4. 执行 `s.warm_up()`，然后 `s.run_chat()`（3 个短问题各 3 次，共 9 个请求）。**不跑 4K。**
5. 把 `s.out` 存成 `<原始目录>\<段>\bench.json`。
6. 结束服务进程树，等到 `strata.exe` 全部退出后再等 60 秒；把引擎日志从第 2 步的位置到末尾，复制成 `<原始目录>\<段>\engine.log`。

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。
D 段的 `engine.log` 会比 01 大很多（每个窗口几十行），这是正常的。

## 2. 整理
1. 窗口表（只读 `verify dbg: T=` 开头的那一种行，其他行不管）：
   ```
   set PYTHONUTF8=1
   cd /d D:\dev\strata-lab\03-window-t
   D:\dev\Strata-intel-npu\.venv\Scripts\python.exe D:\dev\Strata-lab140t\lab\tools\vdbg_windows.py windows.tsv by-t.tsv 2-D=2-D\engine.log 3-D=3-D\engine.log > vdbg.txt
   ```
   `vdbg.txt` 里会写出一共读到多少个窗口。是 0 的话，说明开关没生效，写进结论，不要自己改开关重跑。
2. `timing.tsv`：4 段每个请求一行，列和 `results/01-decode-bound/timing.tsv` 相同（段、请求序号、问题编号、生成 token 数、生成 tok/s、首 token 时间、
   草稿接受数/提供数，每个数字标出 bench.json 的行号）。
3. `<段>-decode.txt`：2-D 和 3-D 两段 engine.log 里所有以 `strata decode` 开头的行，原文，每行前面加上它在 engine.log 里的行号。

## 3. 放进数据目录的内容
`windows.tsv`、`by-t.tsv`、`vdbg.txt`、`timing.tsv`、`2-D-decode.txt`、`3-D-decode.txt`。这些文件里只应有数字和引擎状态，提交前逐个打开确认。
`engine.log` 里 `verify dbg` 的其他行（专家编号、权重、token 编号等）**不提交**，留在原始目录。

## 4. 结论 `lab/results/03-window-t.md`
按 README 的「结论文件的格式」写。额外包括：
1. `by-t.tsv` 里 `all` 的那几行，原样做成表：T、窗口数、占比、gpu 中位数 / 最小 / 最大。
2. 4 段的总表：每段 q1/q2/q3 的生成 tok/s 中位数，9 个请求的生成 tok/s 中位数和最小–最大。
3. 2-D、3-D 两段：`vdbg.txt` 读到的窗口数，和 `strata decode timing` 行里的 windows 数之和（逐行相加），两个数各是多少。
4. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/03-window-t.md` 和 `lab/results/03-window-t/`，推送。

预计耗时：⚠️ 约 30–40 分钟（4 段，每段约 1.5 分钟加载加 9 个请求；D 段每个窗口多打印几十行，会更慢一些）。这是按 01 的耗时推的。
