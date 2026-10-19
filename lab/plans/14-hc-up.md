# 14：hc 读的 up / reduce 改写（`STRATA_GR_UP_TREE`、`STRATA_GR_RED_BATCH`）+ SLM2 加进日常配置

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\14-hc-up\`（下文叫「原始目录」）。
- 结论写到 `lab/results/14-hc-up.md`；可公开的数据文件放在 `lab/results/14-hc-up/`（下文叫「数据目录」）。

**前提**：`plans/13` 已经执行完，引擎在 `8b563925`，`build-sycl-win\strata.exe` 是 35,016,192 字节、SHA256 以 `f95fba18` 开头；
日常配置 `strata-iq3_xxs.json` 的 `env` 里有 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`、`STRATA_GR_UP_EPI`、`STRATA_GR_DOWN_V2`，
没有 `STRATA_GU_GRID_SLM`、`STRATA_GU_GRID_SLM2`、`STRATA_HC_Q8`、`STRATA_VERIFY_ALL_RESIDENT`、`STRATA_GR_RED_BATCH`、`STRATA_GR_UP_TREE`；
`args` 里有 `--expert-cache auto`。不是的话停下来报告。

**目的**：开发机的依据见 `lab/analysis/14-prep.md`。
- 用户已同意（2026-10-19）把 `STRATA_GU_GRID_SLM2=2` 加进日常配置：第 3 节先做这件事，之后的测量都在新的日常配置上。
- hc 读（每个窗口各层 96 次）在 140T 上，up 内核占一半，速率只有 down 的约 64%（08 的按内核计时）。功能分支新提交 `d7123fe1` 加了两个默认关闭的开关：
  - `STRATA_GR_RED_BATCH=1`：down 之后的 reduce 成批读取部分和；
  - `STRATA_GR_UP_TREE=1`：up 的每行点积改由 4 个线程按原来的加法树计算（要和 `STRATA_GR_UP_EPI=1` 一起开）。
  - 开发机核显上两个都实测逐位相同（`gr_apply_parity` 32 种情形、`gr_bench` 校验和）。GPU 编译器可能换加法顺序，所以第 4 节在 140T 上再核对一次。
- 第 4 节在 140T 上按内核计时，按规则判定是否做端到端；第 5 节端到端；第 6 节在 140T 上也逐位相同、端到端条件都满足时，把两个开关加进日常配置。

**例外**（README 共通规则的例外，仅限本手册写的步骤）：更新引擎 checkout 并重新编译 `build-sycl-win`；编译 `build-lab-hcup`；
第 3 节改一次 `strata-iq3_xxs.json`（先备份）；第 6 节在条件满足时再改一次（先备份）。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次（确认后中间不再问）：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑；共享 GPU 内存上限仍是 75%。
4. 建原始目录（`mkdir D:\dev\strata-lab\14-hc-up`；已存在时停下来问用户）。在原始目录的 `env.txt` 记录（查法同 `plans/01` 第 0 节第 4 步）：
   日期时间、开机以来的时间、电源模式、GPU 驱动版本、可用物理内存、`git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `8b563925…`）、
   `git -C D:\dev\Strata-intel-npu status --short --untracked-files=no`（预期为空）、`build-sycl-win\strata.exe` 的大小、修改时间和 SHA256
   （预期 35,016,192 字节，SHA256 以 `f95fba18` 开头）。不符就停下来报告。
5. **运行任何 exe 之前，先在同一个 CMD 里初始化 oneAPI**（12 里没初始化时，工具全部以 `0xC0000135` 退出）：
   ```
   set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
   call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
   ```
   第 2、4 节的命令都在这个 CMD 里输入。

## 1. 更新引擎并编译
1. 把 `build-sycl-win\strata.exe` 复制到原始目录，命名为 `strata-8b563925.exe`（回退用，不提交）。
2. 更新（只允许快进）：
   ```
   git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git local-v0.1.43.1-intel-npu
   git -C D:\dev\Strata-intel-npu merge --ff-only FETCH_HEAD
   git -C D:\dev\Strata-intel-npu rev-parse HEAD
   git -C D:\dev\Strata-intel-npu diff --stat 8b563925 HEAD
   ```
   HEAD 应为 `d7123fe1…`；`diff --stat` 应只有 `sycl/src/kernels/cuda/fused_gr.dp.cpp` 一个文件。不是的话停下来报告。
3. 编译：`D:\dev\Strata-intel-npu\sycl\tools\build_windows.bat`。以退出码为 0 为准，记下耗时、新 exe 的大小、修改时间和 SHA256。
   编译失败就把报错原文（去掉路径里的用户名）写进结论，把 `strata-8b563925.exe` 复制回 `build-sycl-win\strata.exe`，停止。
4. 确认 `build-sycl-win\gr_bench.exe` 和 `build-sycl-win\gr_q8_parity.exe` 都存在，修改时间都晚于这次编译开始。不是的话在结论里写明，第 4、5 节不做。

## 2. 工具编译（`build-lab-hcup` 已存在时，先停下来问用户，不要覆盖）
```
set "E=D:\dev\Strata-intel-npu"
set "B=D:\dev\Strata-intel-npu\build-lab-hcup"
set "L=D:\dev\Strata-lab140t\lab\tools"
mkdir %B%
set PYTHONUTF8=1
%E%\.venv\Scripts\python.exe %L%\gr_events.py %E%\sycl\src\kernels\cuda\fused_gr.dp.cpp %B%\fused_gr_events.cpp
set "CF=-fsycl -fsycl-default-sub-group-size=32 -fsycl-device-code-split=per_kernel /c /O2 /EHsc /std:c++20 /fp:precise /DNDEBUG -Wno-deprecated-declarations -Wno-unused-parameter -Wno-unused-variable"
set "CI=/I%E%\sycl\include /I%E%\include /I%E%\third_party\ggml /I%E%\sycl\src\kernels\cuda"
icx %CF% %CI% %L%\gr_apply_parity.cpp /Fo%B%\gr_apply_parity.obj
icx %CF% %CI% %L%\gr_events_bench.cpp /Fo%B%\gr_events_bench.obj
icx %CF% %CI% %E%\sycl\src\kernels\cuda\fused_gr.dp.cpp /Fo%B%\fused_gr.obj
icx %CF% %CI% %B%\fused_gr_events.cpp /Fo%B%\fused_gr_events.obj
set "LF=-fsycl -fsycl-device-code-split=per_kernel -Xsycl-target-backend=spir64 "-cl-fp32-correctly-rounded-divide-sqrt -ze-opt-greater-than-4GB-buffer-required""
icx %LF% %B%\gr_apply_parity.obj %B%\fused_gr.obj -o %B%\gr_apply_parity.exe
icx %LF% %B%\gr_events_bench.obj %B%\fused_gr_events.obj -o %B%\gr_events_bench.exe
```
`gr_events.py` 应打印 `launch sites recorded`。以每条命令退出码为 0、exe 存在为准；每条命令的耗时、exe 的大小和 SHA256 记进原始目录的 `build.txt`。
失败就把报错原文写进结论，第 4、5 节不做（第 3 节照做）。

## 3. 日常配置加 `STRATA_GU_GRID_SLM2=2`（用户已同意，2026-10-19）
先把 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录（`strata-iq3_xxs.before-14.json`，不提交），再只在它的 `env` 里加 `"STRATA_GU_GRID_SLM2": "2"`，其他不动；
用 JSON 解析器读一遍；在 `config-change.json` 里记下改前改后的 `env`（只有键名和值）。

## 4. 内核对比、核对（`strata.exe` 不运行时）
环境变量（这一节都用这一组，只开日常配置里影响 hc 读的两个开关；各次运行只差 `STRATA_GR_RED_BATCH`、`STRATA_GR_UP_TREE`）：
```
set ONEAPI_DEVICE_SELECTOR=level_zero:gpu
set STRATA_GR_UP_EPI=1
set STRATA_GR_DOWN_V2=1
set "STRATA_MMVQ_Q6_SWAR="
set "STRATA_Q2_SWAR="
set "STRATA_GR_DOWN_ROWS="
set "STRATA_GR_DOWN_SLICED="
set "STRATA_GR_NORM_SPLIT="
set "STRATA_GR_V3="
set "STRATA_HC_Q8="
set "STRATA_GU_GRID_SLM="
set "STRATA_GU_GRID_SLM2="
set "STRATA_DECODE_TIMING="
set "STRATA_GR_RED_BATCH="
set "STRATA_GR_UP_TREE="
cd /d D:\dev\strata-lab\14-hc-up
set STRATA_ > env-strata.txt
type env-strata.txt
```
`env-strata.txt` 应该正好两行：`STRATA_GR_DOWN_V2=1`、`STRATA_GR_UP_EPI=1`。多出来的变量逐个 `set "名字="` 删掉，再重做这一步，直到正好两行。

下面「rb」是只设 `STRATA_GR_RED_BATCH=1`，「tree」是只设 `STRATA_GR_UP_TREE=1`，「both」是两个都设，「base」是两个都不设。
每条命令前按需要 `set "STRATA_GR_RED_BATCH=1"` / `set "STRATA_GR_RED_BATCH="`、`set "STRATA_GR_UP_TREE=1"` / `set "STRATA_GR_UP_TREE="`。逐行输入，不要改动：

1. **逐位核对和容差核对**：
   ```
   type nul > ev-exit.txt
   set "STRATA_GR_RED_BATCH="
   set "STRATA_GR_UP_TREE="
   %B%\gr_apply_parity.exe > gap-base.txt
   echo gap-base %ERRORLEVEL% >> ev-exit.txt
   %E%\build-sycl-win\gr_bench.exe > gb-base.txt
   echo gb-base %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH=1"
   %B%\gr_apply_parity.exe > gap-rb.txt
   echo gap-rb %ERRORLEVEL% >> ev-exit.txt
   %E%\build-sycl-win\gr_bench.exe > gb-rb.txt
   echo gb-rb %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_UP_TREE=1"
   %B%\gr_apply_parity.exe > gap-tree.txt
   echo gap-tree %ERRORLEVEL% >> ev-exit.txt
   %E%\build-sycl-win\gr_bench.exe > gb-both.txt
   echo gb-both %ERRORLEVEL% >> ev-exit.txt
   %E%\build-sycl-win\gr_q8_parity.exe > gq-both.txt 2>&1
   echo gq-both %ERRORLEVEL% >> ev-exit.txt
   ```
   之后**不要再清空 `ev-exit.txt`**。`gap-tree.txt` 是两个开关都开时的结果（文件名沿用 tree）。
2. **按内核计时，跑 3 轮**，每轮 4 种设置各一次，顺序轮换。逐行输入：
   ```
   set "STRATA_GR_RED_BATCH="
   set "STRATA_GR_UP_TREE="
   %B%\gr_events_bench.exe 300 > gev-1-base.txt 2> gev-1-base.err
   echo gev-1-base %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH=1"
   %B%\gr_events_bench.exe 300 > gev-1-rb.txt 2> gev-1-rb.err
   echo gev-1-rb %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH="
   set "STRATA_GR_UP_TREE=1"
   %B%\gr_events_bench.exe 300 > gev-1-tree.txt 2> gev-1-tree.err
   echo gev-1-tree %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH=1"
   %B%\gr_events_bench.exe 300 > gev-1-both.txt 2> gev-1-both.err
   echo gev-1-both %ERRORLEVEL% >> ev-exit.txt

   set "STRATA_GR_UP_TREE="
   %B%\gr_events_bench.exe 300 > gev-2-rb.txt 2> gev-2-rb.err
   echo gev-2-rb %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH="
   set "STRATA_GR_UP_TREE=1"
   %B%\gr_events_bench.exe 300 > gev-2-tree.txt 2> gev-2-tree.err
   echo gev-2-tree %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH=1"
   %B%\gr_events_bench.exe 300 > gev-2-both.txt 2> gev-2-both.err
   echo gev-2-both %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH="
   set "STRATA_GR_UP_TREE="
   %B%\gr_events_bench.exe 300 > gev-2-base.txt 2> gev-2-base.err
   echo gev-2-base %ERRORLEVEL% >> ev-exit.txt

   set "STRATA_GR_UP_TREE=1"
   %B%\gr_events_bench.exe 300 > gev-3-tree.txt 2> gev-3-tree.err
   echo gev-3-tree %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH=1"
   %B%\gr_events_bench.exe 300 > gev-3-both.txt 2> gev-3-both.err
   echo gev-3-both %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH="
   set "STRATA_GR_UP_TREE="
   %B%\gr_events_bench.exe 300 > gev-3-base.txt 2> gev-3-base.err
   echo gev-3-base %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH=1"
   %B%\gr_events_bench.exe 300 > gev-3-rb.txt 2> gev-3-rb.err
   echo gev-3-rb %ERRORLEVEL% >> ev-exit.txt
   set "STRATA_GR_RED_BATCH="
   ```
   开发机核显上第 4 节整组约 50 秒；任何一次超过 5 分钟没结束就结束这个进程，在结论里写明，继续下一条。
3. **判定**（用 `%E%\.venv\Scripts\python.exe`，先 `set PYTHONUTF8=1`；照脚本的输出记，不要自己判断）：
   ```
   %E%\.venv\Scripts\python.exe %L%\hcup_choice.py D:\dev\strata-lab\14-hc-up 140T
   ```
   脚本写出原始目录的 `hcup-choice.txt` 并打印。下面每一条不成立都记为一个问题：
   - `ev-exit.txt` 正好 19 行（3 个 `gap`、3 个 `gb`、1 个 `gq`、12 个 `gev`）、名字不重复、全部是 0；12 个 `.err` 都是空的；`env-strata.txt` 正好上面两行。
   - `gap-base.txt` 和 `gap-rb.txt` 完全相同（成批 reduce 逐位相同）；三个 `gap` 文件都是设备行加 32 种情形（带 / 不带待写入 × 有 / 无 inject × T=1–8）各一行。
   - `gb-base.txt`、`gb-rb.txt` 的校验和等于默认读法的已知值；`gq-both.txt` 是 96 种情形各一行 ok（误差是有限数且不超过 1e-4）加 `gr_q8_parity: 0 failures`。
   - 12 个 `gev` 文件：设备行含 `140T`；`env` 行和设置一致；6 行数据，每行 4 个内核，数是正的有限数；
     最后一列 `bad`（300 次里因为时间戳不合理被剔除的次数）不超过 30。
   - 两个开关都开时是否逐位相同（`gap-tree.txt` 和 `gap-base.txt` 完全相同、`gb-both.txt` 的校验和等于已知值）记为一行 `bitwise both: True` 或 `False`，**不算问题**，第 6 节要用。
   - **时间**：每种设置、每个 token 数取 3 轮中位数；用整次读的时间（span）算加权时间 W = 0.12·s1 + 0.14·s2 + 0.12·s3 + 0.62·s4。
   - **选择**：没有问题、而且 W(both) < 0.90 × W(base)，为 `choice: e2e`；否则为 `choice: none`。
   - `choice: none` 时第 5 节不做，整理数据、写结论。

## 5. 端到端分段（6 段，交替；第 4 节 `choice: e2e` 时做）
驱动脚本以 13 用过的为底子（`sycl\serve\server_intel.py`、固定测速提示词、启动日志的核对），复制到原始目录再改，改了什么写进结论。和 13 不同的地方：
- `s.nonce = "fixed14"`；只有 A、B 两组，6 段；不发 logprobs 请求。

**每段用的配置副本**：把第 3 节改好的 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录，原文件这一节不动：
- `cfg-a.json`：只在 `env` 里加 `"STRATA_VERIFY_ALL_RESIDENT": "0"`（两组走同一条路径的理由同 13，见 `analysis/13-prep.md` 第 5 节）。
- `cfg-b.json`：同 `cfg-a.json`，`env` 里再加 `"STRATA_GR_RED_BATCH": "1"`、`"STRATA_GR_UP_TREE": "1"`。

| 顺序 | 段 | 配置 |
|---|---|---|
| 1 | `1-A` | `cfg-a` |
| 2 | `2-B` | `cfg-b` |
| 3 | `3-B` | `cfg-b` |
| 4 | `4-A` | `cfg-a` |
| 5 | `5-A` | `cfg-a` |
| 6 | `6-B` | `cfg-b` |

- **任何一段都不要设 `STRATA_VERIFY_DEBUG`**。

每段：
1. 先从环境里删除 `plans/03` 第 1 节列出的变量，再删除第 4 节列出的全部 `STRATA_` 变量（包括 `STRATA_GR_UP_EPI`、`STRATA_GR_DOWN_V2`），然后设 `STRATA_DECODE_TIMING=1`。
2. 记下引擎日志长度；按配置副本启动服务（`server_intel.py`，同 13），等就绪；`s.nonce = "fixed14"`；`s.warm_up()`。
3. **贪心请求**（同 `plans/06` 第 3.1 节：`g1`、`g2`），再 `s.run_chat()`（9 个请求，不跑 4K）。保存 `bench.json`。
4. 结束进程树，等到 `strata.exe` 全部退出后再等 60 秒；截取 `engine.log`。
5. 启动日志的 `strata verify: window up to …` 那一行**不能**带 `(100% VRAM resident: zero-doorbell graph)`；带了就停下来报告。

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。
引擎日志里出现 `error`、`failed`、`mismatch`、`device lost`、`nonfinite=` 后面不是 0 的行，去掉 `no error` 这种误中后，把行（去掉路径和文本）写进结论。

## 6. 日常配置加 `STRATA_GR_RED_BATCH=1`、`STRATA_GR_UP_TREE=1`（条件满足时）
条件（七条都满足）：
1. 第 4 节 `choice: e2e`，而且 `bitwise both: True`（140T 上两个开关都开时逐位相同）。
2. 6 段都完成（没有跳过的段），每段 9 个测速请求都成功。
3. 6 段的 `g1` 哈希全部相同，`g2` 哈希也全部相同。
4. 6 段里，9 个测速请求各自的生成 token 数在 6 段之间都相同。
5. 三对相邻段（`1-A`/`2-B`、`3-B`/`4-A`、`5-A`/`6-B`）里，每一对都是 B 段的 ms/token 比 A 段小。
6. 6 段的 `strata verify: window up to` 那一行都没有 `100% VRAM resident`（常驻和不常驻的专家数照记，不作为条件：13 里两组都有 25–31 个不常驻，开发机判断不影响比较）。
7. 第 5 节要求记录的错误行一条也没有（去掉 `no error` 这种误中之后）。

- 满足：先把 `strata-iq3_xxs.json` 复制到原始目录（`strata-iq3_xxs.before-14b.json`，不提交），再只在它的 `env` 里加 `"STRATA_GR_RED_BATCH": "1"`、`"STRATA_GR_UP_TREE": "1"`，其他不动
  （不加 `STRATA_VERIFY_ALL_RESIDENT`）；用 JSON 解析器读一遍；在 `config-change.json` 里再记下这次改前改后的 `env`。结论里写「已加」。
- 不满足：不改，结论里写明哪一条没满足（数字照写）。

## 7. 放进数据目录的内容（提交前逐个打开确认：只有数字、设备和驱动信息、开关名、核对结论、模型对固定提示词的回答 token，以及路径换成占位符的编译命令）
1. `gap-*.txt`、`gb-*.txt`、`gq-both.txt`、12 个 `gev-*.txt`、`ev-exit.txt`、`env-strata.txt`、`hcup-choice.txt`。`.err` 都是空的话不提交，非空的去掉路径后附上。
2. `timing.tsv`、`decode.tsv`、`decode-requests.tsv`、`greedy.tsv`、`greedy-check.txt`、`startup.tsv`：格式同 `results/13-hc-q8/`（第 5 节没做就没有）。
   `greedy-check.txt` 列出 6 段的 g1、g2 哈希是否全部相同，另写一句和 13 的 A 组（`g1` `553ac32f017ae0be`、`g2` `1c1c19249884638f`）是否相同。
3. `build.txt`、`config-change.json`（第 3 节的改动，第 6 节改了的话也记在里面）。

## 8. 结论 `lab/results/14-hc-up.md`
按 README 的「结论文件的格式」写。额外包括：
1. `hcup-choice.txt` 原样贴出。
2. 第 3 节改了配置（`config-change.json` 的摘要）。
3. 第 5 节做了的话：每组（A、B）合并的 ms/token、q1/q2/q3 各自的生成 tok/s 中位数、首 token 时间中位数、草稿接受数之和 / 提供数之和；
   每段各自的 ms/token、窗口数、平均 T、草稿接受数 / 提供数；从 `decode.tsv` 取每个请求的 `ms/window`、`draft` 和 `tokens/window`，给出每组的中位数；
   每段常驻的专家数和 `missing from VRAM` 的个数；`greedy-check.txt` 的摘要；第 6 节七条逐条是否满足（数字照写）、改没改配置。
4. 第 5 节要求记录的错误行（没有就写「没有」）。
5. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/14-hc-up.md` 和 `lab/results/14-hc-up/`，推送。

预计耗时：⚠️ 约 50 分钟（重编引擎约 5 分钟；工具编译约 3 分钟；第 4 节约 2 分钟（开发机 50 秒）；6 段每段约 5–6 分钟（13 的同样流程））。
