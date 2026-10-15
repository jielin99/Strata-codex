# 04：引擎开关 `STRATA_MMVQ_Q6_SWAR=1` 的端到端 A/B（生成 tok/s、首 token 时间）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\04-q6-swar-ab\`（下文叫「原始目录」）。
- 结论写到 `lab/results/04-q6-swar-ab.md`；可公开的数据文件放在 `lab/results/04-q6-swar-ab/`（下文叫「数据目录」）。

**目的**：功能分支 `local-v0.1.43.1-intel-npu` 新增了提交 `7629f0b2`：Q6_K 的 wide 内核在开关 `STRATA_MMVQ_Q6_SWAR=1` 时不用逐字节的 `sub_sat`，
6–8 列拆成 4 列加其余。开关默认关闭，关闭时走原来的代码；打开时输出应和关闭时逐位相同（`lab/analysis/03-window-t.md` 第 4 节）。
这一份在笔记本上：
1. 把引擎更新到 `7629f0b2` 并重新编译。
2. 交替跑开关关闭（A）和打开（B），比较生成 tok/s 和首 token 时间。
3. 核对：新程序关闭开关时和旧程序回答相同，打开开关时和关闭时回答相同。

**例外**：这一份要更新引擎 checkout 并重新编译 `build-sycl-win`（README 共通规则的例外，仅限本手册写的步骤）。不改 `strata-iq3_xxs.json`。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑。确认后中间不再问。
4. 在原始目录的 `env.txt` 记录（查法和 `plans/01` 第 0 节第 4 步相同）：日期时间、开机以来的时间、电源模式、GPU 驱动版本、
   `git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `29825274…`）、`git -C D:\dev\Strata-intel-npu status --short --untracked-files=no`（预期为空）、
   `build-sycl-win\strata.exe` 的大小、修改时间和 SHA256（预期 32,693,760 字节，SHA256 以 `7b40f6b5` 开头）。
   HEAD、状态或 exe 和预期不符，就停下来报告。

## 1. 旧程序的一段（O）
1. 把 `build-sycl-win\strata.exe` 复制到原始目录，命名为 `strata-29825274.exe`（回退用，不提交）。
2. 跑一段 `0-O`，做法见第 3 节，环境变量同 A。

## 2. 更新引擎并编译
1. 更新到功能分支的新提交（只允许快进）：
   ```
   git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git local-v0.1.43.1-intel-npu
   git -C D:\dev\Strata-intel-npu merge --ff-only FETCH_HEAD
   git -C D:\dev\Strata-intel-npu rev-parse HEAD
   ```
   HEAD 应为 `7629f0b2…`。不是的话停下来报告。
   再记录 `git -C D:\dev\Strata-intel-npu diff --stat 29825274 HEAD`（预期只有 `sycl/src/kernels/cuda/native_mmvq.dp.cpp` 一个文件）。
2. 编译（和现有 exe 相同的构建脚本和目录）：
   ```
   D:\dev\Strata-intel-npu\sycl\tools\build_windows.bat
   ```
   以退出码为 0 为准，记下耗时、新 exe 的大小、修改时间和 SHA256。编译失败就把报错原文写进结论，把 `strata-29825274.exe` 复制回
   `build-sycl-win\strata.exe`，停止。

## 3. 分段运行
做法和 `plans/01` 第 3 节相同（驱动脚本以 `plans/03` 用过的为底子）：每段先删除 `plans/03` 第 1 节列出的变量和 `STRATA_MMVQ_Q6_SWAR`，再按下表设置；
记下引擎日志长度；启动服务；`s.warm_up()`；`s.run_chat()`（9 个请求，不跑 4K）；保存 `bench.json`；结束进程树，等 60 秒；截取 `engine.log`。

| 顺序 | 段 | 程序 | 环境变量 |
|---|---|---|---|
| 0 | `0-O` | 旧（第 1 节，编译前） | 不加开关 |
| 1 | `1-A` | 新 | 不加开关 |
| 2 | `2-B` | 新 | `STRATA_MMVQ_Q6_SWAR=1` |
| 3 | `3-B` | 新 | 同 2-B |
| 4 | `4-A` | 新 | 同 1-A |
| 5 | `5-A` | 新 | 同 1-A |
| 6 | `6-B` | 新 | 同 2-B |

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。

## 4. 整理
1. `timing.tsv`：7 段每个请求一行，列和 `results/01-decode-bound/timing.tsv` 相同，每个数字标出 bench.json 的行号。
2. `answers.tsv`：每段每个请求一行：段、请求序号、问题编号、回答文本的 SHA256 前 16 位（`bench.json` 里有回答文本时；没有就写「无文本」，并在结论里说明 bench.json 里有哪些字段）。
   **回答文本本身不提交。**
3. `answers-check.txt`：对每个（请求序号、问题编号），列出 7 段的哈希是否全部相同；不同的列出是哪几段不同。

## 5. 放进数据目录的内容
`timing.tsv`、`answers.tsv`、`answers-check.txt`，和第 2 节的编译记录（命令、耗时、`diff --stat` 输出、新旧 exe 的大小与 SHA256，路径换成占位符）`build.txt`。

## 6. 结论 `lab/results/04-q6-swar-ab.md`
按 README 的「结论文件的格式」写。额外包括：
1. 7 段的总表：每段 q1/q2/q3 的生成 tok/s 中位数，9 个请求的生成 tok/s 中位数和最小–最大；首 token 时间的中位数和最小–最大。
2. A 段合并（1-A、4-A、5-A）和 B 段合并（2-B、3-B、6-B）：每个问题的生成 tok/s 中位数、首 token 时间中位数。
3. `answers-check.txt` 的摘要：多少组全部相同，多少组有不同。
4. **不做分析，不写原因推断**，分析由开发机来做。
5. 结束时的状态：引擎 HEAD 和 `build-sycl-win\strata.exe` 的 SHA256（预期是新的；开关默认关闭，不需要回退）。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/04-q6-swar-ab.md` 和 `lab/results/04-q6-swar-ab/`，推送。

预计耗时：⚠️ 约 45–60 分钟（7 段，每段约 5 分钟，按 03 的耗时推；另加编译，只重编一个文件和链接，⚠️ 时间未知）。
