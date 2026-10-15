# 06：Q2_0 开关、`--mtp-q4 all`、全常驻，一轮做决定（端到端 A/B + 内核测速 + 回答一致性）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\06-decide\`（下文叫「原始目录」）。
- 结论写到 `lab/results/06-decide.md`；可公开的数据文件放在 `lab/results/06-decide/`（下文叫「数据目录」）。

**前提**：`plans/05` 已经执行完，引擎在 `7629f0b2`。不是的话停下来报告。

**目的**：开发机的复盘和方案见 `lab/analysis/06-retro.md`。这一份在同一轮里比较 3 个候选，并核对回答是否不变：
- B：功能分支新提交 `870dee5e` 的开关 `STRATA_Q2_SWAR=1`（Q2_0 专家 down 不用软件模拟的字节置换，开发机上输出逐字节相同）。
- C：`--mtp-q4 all`（草稿层的投影和草稿头用 4 位副本，引擎已有的参数）。
- D：全部专家放进设备内存（要先把核显共享显存上限调高）。

**例外**（README 共通规则的例外，仅限本手册写的步骤）：更新引擎 checkout 并重新编译 `build-sycl-win`；编译 `build-lab-moe`；
第 4 节在条件满足时改一次 `strata-iq3_xxs.json`（先备份）。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次（确认后中间不再问）：
   - 插着电源、电源模式「最佳性能」、跑的过程中不使用电脑。
   - **已在 Intel Graphics Software 里把共享 GPU 内存上限（Shared GPU Memory Override）调到 75%，并重启过**。用户说没有这个选项或没调，就照常执行，D 组全部跳过，在结论里写明。
4. 在原始目录的 `env.txt` 记录（查法同 `plans/01` 第 0 节第 4 步）：日期时间、开机以来的时间、电源模式、GPU 驱动版本、可用物理内存、
   `git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `7629f0b2…`）、`git -C D:\dev\Strata-intel-npu status --short --untracked-files=no`（预期为空）、
   `build-sycl-win\strata.exe` 的大小、修改时间和 SHA256（预期 32,892,416 字节，SHA256 以 `28ac7066` 开头）。不符就停下来报告。

## 1. 更新引擎并编译
1. 把 `build-sycl-win\strata.exe` 复制到原始目录，命名为 `strata-7629f0b2.exe`（回退用，不提交）。
2. 更新（只允许快进）：
   ```
   git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git local-v0.1.43.1-intel-npu
   git -C D:\dev\Strata-intel-npu merge --ff-only FETCH_HEAD
   git -C D:\dev\Strata-intel-npu rev-parse HEAD
   git -C D:\dev\Strata-intel-npu diff --stat 7629f0b2 HEAD
   ```
   HEAD 应为 `870dee5e…`，`diff --stat` 应只有 `sycl/src/kernels/cuda/iq_kernels.dp.cpp` 一个文件。不是的话停下来报告。
3. 编译：`D:\dev\Strata-intel-npu\sycl\tools\build_windows.bat`。以退出码为 0 为准，记下耗时、新 exe 的大小、修改时间和 SHA256。
   编译失败就把报错原文（去掉路径里的用户名）写进结论，把 `strata-7629f0b2.exe` 复制回 `build-sycl-win\strata.exe`，停止。
4. 列出 `build-sycl-win` 里 `gr_bench.exe`、`iq_multi_parity.exe` 是否存在及修改时间。缺哪个就在结论里写明，跳过第 2 节里用它的那一步。

## 2. 内核测速（`strata.exe` 不运行时）
1. 编译 `moe_lab`（选项和 `plans/02` 第 1 节相同）。`build-lab-moe` 已存在时，先停下来问用户，不要覆盖。
   ```
   set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
   call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
   set "E=D:\dev\Strata-intel-npu"
   set "B=D:\dev\Strata-intel-npu\build-lab-moe"
   set "L=D:\dev\Strata-lab140t\lab\tools"
   mkdir %B%
   set "CF=-fsycl -fsycl-default-sub-group-size=32 -fsycl-device-code-split=per_kernel /c /O2 /EHsc /std:c++20 /fp:precise /DNDEBUG -Wno-deprecated-declarations -Wno-unused-parameter -Wno-unused-variable"
   set "CI=/I%E%\sycl\include /I%E%\include /I%E%\third_party\ggml /I%E%\sycl\src\kernels\cuda"
   icx %CF% %CI% %L%\moe_lab.cpp /Fo%B%\moe_lab.obj
   icx %CF% %CI% %E%\sycl\src\kernels\cuda\iq_kernels.dp.cpp /Fo%B%\iq_kernels.obj
   icx %CF% %CI% %E%\sycl\src\kernels\cuda\native_mmvq.dp.cpp /Fo%B%\native_mmvq.obj
   set "LF=-fsycl -fsycl-device-code-split=per_kernel -Xsycl-target-backend=spir64 "-cl-fp32-correctly-rounded-divide-sqrt -ze-opt-greater-than-4GB-buffer-required""
   icx %LF% %B%\moe_lab.obj %B%\iq_kernels.obj %B%\native_mmvq.obj -o %B%\moe_lab.exe
   ```
   以退出码为 0、exe 存在为准；每条命令的耗时、exe 的大小和 SHA256 记进原始目录的 `build.txt`。失败就把报错原文写进结论，跳过 2.3，继续。
2. 环境变量（这一节都用这一组）：
   ```
   set ONEAPI_DEVICE_SELECTOR=level_zero:gpu
   set UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
   set STRATA_Q2_SWAR=
   set STRATA_GU_LANES=
   set STRATA_DOWN_LANES=
   set STRATA_EXPERT_SPLIT=
   set STRATA_OLD_IQ_MMVQ=
   set STRATA_GROUPED_V1=
   set STRATA_IQ_STAGE_GRID=
   cd /d D:\dev\strata-lab\06-decide
   ```
3. `moe_lab`：交替跑 6 次，每次约 1–2 分钟（输出里有每个 T 的整窗口和每种类型组合的时间）。
   ```
   set MOE_LAB_DUMP=dump-off.bin
   %B%\moe_lab.exe 1000 4 > moe-1-off.tsv
   set STRATA_Q2_SWAR=1
   set MOE_LAB_DUMP=dump-on.bin
   %B%\moe_lab.exe 1000 4 > moe-2-on.tsv
   set MOE_LAB_DUMP=
   set STRATA_Q2_SWAR=
   %B%\moe_lab.exe 1000 4 > moe-3-off.tsv
   set STRATA_Q2_SWAR=1
   %B%\moe_lab.exe 1000 4 > moe-4-on.tsv
   set STRATA_Q2_SWAR=
   %B%\moe_lab.exe 1000 4 > moe-5-off.tsv
   set STRATA_Q2_SWAR=1
   %B%\moe_lab.exe 1000 4 > moe-6-on.tsv
   set STRATA_Q2_SWAR=
   fc /b dump-off.bin dump-on.bin > dump-fc.txt
   ```
   `dump-fc.txt` 里应是「找不到差异」（FC: no differences encountered）。有差异就记下差异的行数（`find /c /v "" dump-fc.txt`），不要把内容写进结论。
   `.bin` 文件不提交。
4. `iq_multi_parity`（开关不设、设为 1 各一次）：
   ```
   %E%\build-sycl-win\iq_multi_parity.exe > parity-off.txt 2>&1
   set STRATA_Q2_SWAR=1
   %E%\build-sycl-win\iq_multi_parity.exe > parity-on.txt 2>&1
   set STRATA_Q2_SWAR=
   fc parity-off.txt parity-on.txt > parity-fc.txt
   ```
   记录两个文件最后一行（`iq_multi_parity: N failures`），以及 `parity-fc.txt` 是否有差异。
5. `gr_bench`（hc 读的基线，后续改 hc 用）跑 3 次：`%E%\build-sycl-win\gr_bench.exe > gr-<n>.txt`（n = 1、2、3）。

## 3. 端到端分段（13 段，交替）
驱动脚本以 `plans/05` 用过的为底子，复制到原始目录再改，改了什么写进结论。

**每段用的配置副本**：把 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录，只改 `args`，原文件这一节不动：
- `cfg-17520.json`：`--expert-cache` 后面的值改成 `17520`（和现在常驻的专家数相同）。
- `cfg-mtpq4.json`：同 `cfg-17520.json`，再在 `args` 末尾加 `"--mtp-q4", "all"`。
- `cfg-auto.json`：原样（`--expert-cache auto`）。

| 顺序 | 段 | 配置 | 环境变量（在 `STRATA_DECODE_TIMING=1` 之外） | 做什么 |
|---|---|---|---|---|
| 1 | `1-A` | `cfg-17520` | `STRATA_MMVQ_Q6_SWAR=1` | 贪心 + 9 个请求 |
| 2 | `2-B` | `cfg-17520` | `STRATA_MMVQ_Q6_SWAR=1`、`STRATA_Q2_SWAR=1` | 同上 |
| 3 | `3-C` | `cfg-mtpq4` | `STRATA_MMVQ_Q6_SWAR=1` | 同上 |
| 4 | `4-D` | `cfg-auto` | `STRATA_MMVQ_Q6_SWAR=1` | 同上 |
| 5 | `5-D` | 同 4 | 同 4 | 同上 |
| 6 | `6-C` | 同 3 | 同 3 | 同上 |
| 7 | `7-B` | 同 2 | 同 2 | 同上 |
| 8 | `8-A` | 同 1 | 同 1 | 同上 |
| 9 | `9-A` | 同 1 | 同 1 | 同上 |
| 10 | `10-B` | 同 2 | 同 2 | 同上 |
| 11 | `11-C` | 同 3 | 同 3 | 同上 |
| 12 | `12-D` | 同 4 | 同 4 | 同上 |
| 13 | `13-A0` | `cfg-17520` | 无（不开 SWAR） | **只做贪心**，不跑 9 个请求 |

- 共享显存上限没调（第 0 节第 3 步），或者 `4-D` 的启动日志里 GPU 名后面仍是 `(32GB)`：跳过所有 D 段，其余照常。
- **任何一段都不要设 `STRATA_VERIFY_DEBUG`**（全常驻时会出错，见 `analysis/06-retro.md` 第 4 节）。

每段：
1. 先从环境里删除 `plans/03` 第 1 节列出的变量，再删除 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`，然后设 `STRATA_DECODE_TIMING=1` 和上表这一段的变量。
2. 记下引擎日志长度；按配置副本启动服务，等就绪；`s.warm_up()`。
3. **贪心请求**（3.1），再 `s.run_chat()`（9 个请求，不跑 4K；`13-A0` 不跑）。保存 `bench.json`。
4. 结束进程树，等到 `strata.exe` 全部退出后再等 60 秒；截取 `engine.log`。

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。
引擎日志里出现 `error`、`failed`、`mismatch`、`device lost`、`nonfinite=` 后面不是 0 的行，去掉 `no error` 这种误中后，把行（去掉路径和文本）写进结论。

### 3.1 贪心请求（回答一致性）
对 `http://127.0.0.1:8080/v1/chat/completions` 发 2 个请求，请求头和驱动脚本里的会话发请求时相同。请求体：
```
{"model": "<配置里的 model_name>", "messages": [{"role": "user", "content": "<提示词>"}], "temperature": 0, "max_tokens": 256, "stream": false}
```
- `g1`：`用三句话解释什么是混合专家模型（MoE）。`
- `g2`：`Write a Python function fib(n) that returns the n-th Fibonacci number iteratively, with a docstring.`

每个回答的完整 JSON 存到 `<原始目录>\<段>\greedy-g1.json`、`greedy-g2.json`（**不提交**）。
算哈希：把 `choices[0].message` 里的 `reasoning_content`（没有这个字段就当空字符串）、一行 `---`、`content` 按 UTF-8 连起来，取 SHA256 的前 16 位。

## 4. 日常配置打开 SWAR（用户 2026-10-16 已同意）
条件：`13-A0` 和 A 段（`1-A`、`8-A`、`9-A`）的 `g1`、`g2` 哈希全部相同，而且三个 A 段之间也相同。
- 满足：把 `strata-iq3_xxs.json` 复制到原始目录（`strata-iq3_xxs.before-06.json`），然后只在它的 `env` 里加一项 `"STRATA_MMVQ_Q6_SWAR": "1"`，其他不动。结论里写「已加」。
- 不满足：不改，结论里写明哪个哈希不同。

`STRATA_Q2_SWAR`、`--mtp-q4` 这一份**不**加进日常配置，由开发机判断后再定。

## 5. 放进数据目录的内容（提交前逐个打开确认只有数字和引擎状态）
1. `timing.tsv`：12 段（不含 `13-A0`）每个请求一行，列和 `results/01-decode-bound/timing.tsv` 相同，每个数字标出 `bench.json` 的行号。
2. `decode.tsv`：每段 `engine.log` 里以 `strata decode timing` 开头的行，原文，前面加段名和行号。
3. `greedy.tsv`：每段每个提示词一行：段、提示词（g1/g2）、哈希前 16 位、`completion_tokens`、`finish_reason`、`usage` 里有的缓存命中 token 数（没有就留空）。
4. `greedy-check.txt`：对 g1、g2 各列出所有段的哈希是否相同；不同的写出是哪些段。
5. `startup.tsv`：每段 `engine.log` 里这几行的原文（加行号，路径换占位符）：`strata generate: GPU 0:`、`expert cache auto:`、`expert cache … slots`、
   `… mirrored in pinned host memory …`、`token graph hit path:`、`strata mtp: --mtp-q4:`。
6. `moe-<n>-<off|on>.tsv`（6 个，`moe_lab` 的输出原样）、`dump-check.txt`（`dump-fc.txt` 的结论一句话和差异行数）。
7. `parity.txt`：`parity-off.txt`、`parity-on.txt` 的最后一行，和 `parity-fc.txt` 有无差异。
8. `gr-1.txt`、`gr-2.txt`、`gr-3.txt`（`gr_bench` 的输出原样）。
9. `build.txt`：第 1、2 节的编译记录（命令、耗时、`diff --stat`、exe 的大小和 SHA256，路径换成占位符）。

## 6. 结论 `lab/results/06-decide.md`
按 README 的「结论文件的格式」写。额外包括：
1. 每组（A、B、C、D）合并：总生成 token ÷ 总生成时间（ms/token）、q1/q2/q3 各自的生成 tok/s 中位数、首 token 时间中位数、草稿接受数之和 / 提供数之和；
   从 `decode.tsv` 取每个请求的 `ms/window`、`draft` 和 `tokens/window`，给出每组的中位数。
2. `moe_lab`：每个 T 的 `window` 行，off 3 次和 on 3 次的 `ms_per_window` 中位数；每种类型组合 T=4 的 `us_per_layer` 中位数（off / on）。
3. `dump-check.txt`、`parity.txt` 的结果；`gr_bench` 3 次每个 token 数的时间中位数。
4. `greedy-check.txt` 的摘要；第 4 节改没改配置。
5. D 段：`startup.tsv` 里 GPU 名后面的容量、缓存槽数、镜像专家数。
6. 第 3 节要求记录的错误行（没有就写「没有」）。
7. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/06-decide.md` 和 `lab/results/06-decide/`，推送。

预计耗时：⚠️ 约 2 小时（重编引擎 ⚠️ 时间未知，`iq_kernels.dp.cpp` 要重编；`moe_lab` 编译加运行约 20 分钟；13 段每段约 5 分钟）。
