# 05：MoE 和 hc 读的现成开关，按窗口列数比较 GPU 时间（不改引擎）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\05-moe-hc-env\`（下文叫「原始目录」）。
- 结论写到 `lab/results/05-moe-hc-env.md`；可公开的数据文件放在 `lab/results/05-moe-hc-env/`（下文叫「数据目录」）。

**前提**：`plans/04` 已经执行完（引擎在 `7629f0b2`，`build-sycl-win\strata.exe` 是 04 编译出来的）。没有执行完就停下来报告。

**目的**：`lab/analysis/04-moe-hc-code.md` 找到了几个只用环境变量就能切换的 MoE 和 hc 读的写法。这一份在笔记本上测：
每种写法下，每种窗口列数（T）的 GPU 时间比默认快还是慢，回答是否和默认相同。
计时用 `plans/03` 的方法（`STRATA_VERIFY_DEBUG=1`，每个窗口一行 T 和 GPU 时间）。这个开关本身会让运行变慢，但每段都开，所以段与段之间可以比较。
生成 tok/s 在这一份里**不作为结论**，只记录。

不改引擎代码，不改 `strata-iq3_xxs.json`，不重新编译。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑。确认后中间不再问。
4. 在原始目录的 `env.txt` 记录（查法和 `plans/01` 第 0 节第 4 步相同）：日期时间、开机以来的时间、电源模式、GPU 驱动版本、
   `git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `7629f0b2…`）、`build-sycl-win\strata.exe` 的大小、修改时间和 SHA256
   （预期和 `results/04-q6-swar-ab.md` 里记录的新 exe 相同）。不符就停下来报告。

## 1. 分段运行（8 段）
驱动脚本以 `plans/03` 用过的为底子，复制到原始目录再改。每段的做法和 `plans/03` 第 1 节相同：先从环境里删除 `plans/03` 第 1 节列出的变量，
再删除下表「环境变量」一列出现过的所有变量和 `STRATA_MMVQ_Q6_SWAR`，然后设置 `STRATA_VERIFY_DEBUG=1`、`STRATA_DECODE_TIMING=1`，再加上下表这一段的变量。

| 顺序 | 段 | 环境变量（在 DEBUG 和 TIMING 之外） | 改的是什么 |
|---|---|---|---|
| 1 | `1-base` | 无 | 默认 |
| 2 | `2-split` | `STRATA_EXPERT_SPLIT=1` | MoE 改用多 token 的 split 内核（IQ2_XXS/IQ2_XS 也复用解码） |
| 3 | `3-lanes16` | `STRATA_GU_LANES=16`、`STRATA_DOWN_LANES=16` | MoE 每行 16 条 lane（默认 8） |
| 4 | `4-base` | 无 | 默认 |
| 5 | `5-lanes4` | `STRATA_GU_LANES=4`、`STRATA_DOWN_LANES=4` | MoE 每行 4 条 lane |
| 6 | `6-hcdirect` | `STRATA_GR_DOWN_SLICED=0` | hc 读的 down 改用 direct 内核 |
| 7 | `7-hcnorm` | `STRATA_GR_NORM_SPLIT=0` | hc 读的 norm 每个 token 一个工作组 |
| 8 | `8-base` | 无 | 默认 |

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。
某一段的引擎日志里出现 `error`、`failed`、`mismatch` 或 `nonfinite=` 后面不是 0 的行，把这些行（去掉路径和文本）写进结论。

## 2. 整理
1. 窗口表：
   ```
   set PYTHONUTF8=1
   cd /d D:\dev\strata-lab\05-moe-hc-env
   D:\dev\Strata-intel-npu\.venv\Scripts\python.exe D:\dev\Strata-lab140t\lab\tools\vdbg_windows.py windows.tsv by-t.tsv 1-base=1-base\engine.log 2-split=2-split\engine.log 3-lanes16=3-lanes16\engine.log 4-base=4-base\engine.log 5-lanes4=5-lanes4\engine.log 6-hcdirect=6-hcdirect\engine.log 7-hcnorm=7-hcnorm\engine.log 8-base=8-base\engine.log > vdbg.txt
   ```
2. `timing.tsv`：8 段每个请求一行，列和 `results/01-decode-bound/timing.tsv` 相同，每个数字标出 bench.json 的行号。
3. `answers.tsv` 和 `answers-check.txt`：做法和 `plans/04` 第 4 节相同（回答文本的 SHA256 前 16 位；文本本身不提交）。
   `answers-check.txt` 里，对每个（请求序号、问题编号）列出：3 个 base 段之间是否相同；其他每段和 `1-base` 是否相同。

## 3. 放进数据目录的内容
`windows.tsv`、`by-t.tsv`、`vdbg.txt`、`timing.tsv`、`answers.tsv`、`answers-check.txt`。提交前逐个打开确认只有数字、哈希和引擎状态。

## 4. 结论 `lab/results/05-moe-hc-env.md`
按 README 的「结论文件的格式」写。额外包括：
1. 按 T 的 GPU 中位数表：行是 T=1、2、3、4（以及出现的 6），列是 8 个段，数字取 `by-t.tsv` 各段的 `gpu_median_ms`，括号里写窗口数。
2. `answers-check.txt` 的摘要：base 之间是否一致；每个其他段有几个请求的回答和 `1-base` 不同。
3. 第 1 节要求记录的错误行（没有就写「没有」）。
4. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/05-moe-hc-env.md` 和 `lab/results/05-moe-hc-env/`，推送。

预计耗时：⚠️ 约 45 分钟（8 段，每段约 5 分钟，按 03 的耗时推）。
