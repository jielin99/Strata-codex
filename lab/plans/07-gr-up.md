# 07：hc 读 up 内核开关 `STRATA_GR_UP_EPI=1`（端到端 A/B + 内核测速 + 逐位核对），日常配置加 `STRATA_Q2_SWAR=1`

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\07-gr-up\`（下文叫「原始目录」）。
- 结论写到 `lab/results/07-gr-up.md`；可公开的数据文件放在 `lab/results/07-gr-up/`（下文叫「数据目录」）。

**前提**：`plans/06` 已经执行完，引擎在 `870dee5e`，日常配置 `strata-iq3_xxs.json` 的 `env` 里已有 `STRATA_MMVQ_Q6_SWAR`。不是的话停下来报告。

**目的**：开发机的判断见 `lab/analysis/06-decide.md`。这一份做两件事：
1. 日常配置加 `STRATA_Q2_SWAR=1`（06 测得生成快约 3.5%，回答不变）。
2. 测功能分支新提交 `43ce0300` 的开关 `STRATA_GR_UP_EPI=1`：hc 读的 up 内核把每行的收尾挪到行循环之后做（开发机 UHD 730 上 hc 读快 46–64%，输出逐位相同）。
   条件满足时把它也加进日常配置。

**例外**（README 共通规则的例外，仅限本手册写的步骤）：更新引擎 checkout 并重新编译 `build-sycl-win`；编译 `build-lab-gr`；
第 1 节和第 5 节各改一次 `strata-iq3_xxs.json`（第 1 节改之前先备份）。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次（确认后中间不再问）：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑；共享 GPU 内存上限仍是 75%。
4. 在原始目录的 `env.txt` 记录（查法同 `plans/01` 第 0 节第 4 步）：日期时间、开机以来的时间、电源模式、GPU 驱动版本、可用物理内存、
   `git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `870dee5e…`）、`git -C D:\dev\Strata-intel-npu status --short --untracked-files=no`（预期为空）、
   `build-sycl-win\strata.exe` 的大小、修改时间和 SHA256（预期 32,999,424 字节，SHA256 以 `64d6f4aa` 开头）。不符就停下来报告。

## 1. 日常配置加 `STRATA_Q2_SWAR=1`
1. 把 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录，命名为 `strata-iq3_xxs.before-07.json`（回退用，不提交）。
2. 只在原文件的 `env` 里加一项 `"STRATA_Q2_SWAR": "1"`，其他不动。用 JSON 解析器读一遍确认格式正确。
3. 在原始目录的 `config-change.json` 记下：改前改后 `env` 的键列表（只要键名和值，不要路径）。

## 2. 更新引擎并编译
1. 把 `build-sycl-win\strata.exe` 复制到原始目录，命名为 `strata-870dee5e.exe`（回退用，不提交）。
2. 更新（只允许快进）：
   ```
   git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git local-v0.1.43.1-intel-npu
   git -C D:\dev\Strata-intel-npu merge --ff-only FETCH_HEAD
   git -C D:\dev\Strata-intel-npu rev-parse HEAD
   git -C D:\dev\Strata-intel-npu diff --stat 870dee5e HEAD
   ```
   HEAD 应为 `43ce0300…`，`diff --stat` 应只有 `sycl/src/kernels/cuda/fused_gr.dp.cpp` 一个文件。不是的话停下来报告。
3. 编译：`D:\dev\Strata-intel-npu\sycl\tools\build_windows.bat`。以退出码为 0 为准，记下耗时、新 exe 的大小、修改时间和 SHA256。
   编译失败就把报错原文（去掉路径里的用户名）写进结论，把 `strata-870dee5e.exe` 复制回 `build-sycl-win\strata.exe`，停止。
4. 确认 `build-sycl-win\gr_bench.exe` 存在且修改时间晚于这次编译开始。不是的话在结论里写明，跳过 3.4。

## 3. 内核测速和逐位核对（`strata.exe` 不运行时）
1. 编译两个工具（`build-lab-gr` 已存在时，先停下来问用户，不要覆盖）：
   ```
   set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
   call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
   set "E=D:\dev\Strata-intel-npu"
   set "B=D:\dev\Strata-intel-npu\build-lab-gr"
   set "L=D:\dev\Strata-lab140t\lab\tools"
   mkdir %B%
   set "CF=-fsycl -fsycl-default-sub-group-size=32 -fsycl-device-code-split=per_kernel /c /O2 /EHsc /std:c++20 /fp:precise /DNDEBUG -Wno-deprecated-declarations -Wno-unused-parameter -Wno-unused-variable"
   set "CI=/I%E%\sycl\include /I%E%\include /I%E%\third_party\ggml /I%E%\sycl\src\kernels\cuda"
   icx %CF% %CI% %L%\gr_apply_parity.cpp /Fo%B%\gr_apply_parity.obj
   icx %CF% %CI% %L%\gr_split.cpp /Fo%B%\gr_split.obj
   icx %CF% %CI% %E%\sycl\src\kernels\cuda\fused_gr.dp.cpp /Fo%B%\fused_gr.obj
   set "LF=-fsycl -fsycl-device-code-split=per_kernel -Xsycl-target-backend=spir64 "-cl-fp32-correctly-rounded-divide-sqrt -ze-opt-greater-than-4GB-buffer-required""
   icx %LF% %B%\gr_apply_parity.obj %B%\fused_gr.obj -o %B%\gr_apply_parity.exe
   icx %LF% %B%\gr_split.obj %B%\fused_gr.obj -o %B%\gr_split.exe
   ```
   以退出码为 0、exe 存在为准；每条命令的耗时、exe 的大小和 SHA256 记进原始目录的 `build.txt`。失败就把报错原文写进结论，跳过用它的那一步，继续。
2. 环境变量（这一节都用这一组）：
   ```
   set ONEAPI_DEVICE_SELECTOR=level_zero:gpu
   set STRATA_GR_UP_EPI=
   set STRATA_GR_V3=
   set STRATA_GR_DOWN_SLICED=
   set STRATA_GR_DOWN_DIRECT=
   set STRATA_GR_NORM_SPLIT=
   set STRATA_HC_SPLIT=
   cd /d D:\dev\strata-lab\07-gr-up
   ```
3. 逐位核对（开关不设、设为 1 各一次）：
   ```
   %B%\gr_apply_parity.exe > gap-off.txt
   echo off-exit %ERRORLEVEL% > gap-exit.txt
   set STRATA_GR_UP_EPI=1
   %B%\gr_apply_parity.exe > gap-on.txt
   echo on-exit %ERRORLEVEL% >> gap-exit.txt
   set STRATA_GR_UP_EPI=
   fc gap-off.txt gap-on.txt > gap-fc.txt
   echo fc-exit %ERRORLEVEL% >> gap-exit.txt
   find /c /v "" gap-off.txt gap-on.txt >> gap-exit.txt
   ```
   通过的标准（四条都要）：两次程序退出码都是 0；两个文件各 33 行（设备名 1 行 + 32 种情况）；`fc` 的退出码是 0（`fc` 的退出码 0 = 相同，1 = 不同，2 = 比较出错）；
   `gap-fc.txt` 里是「找不到差异」。不通过就记下是哪一条、差异的行数，照样继续第 4 节（第 5 节的条件不会满足）。
4. `gr_bench` 交替跑 6 次：
   ```
   %E%\build-sycl-win\gr_bench.exe > gr-1-off.txt
   set STRATA_GR_UP_EPI=1
   %E%\build-sycl-win\gr_bench.exe > gr-2-on.txt
   set STRATA_GR_UP_EPI=
   %E%\build-sycl-win\gr_bench.exe > gr-3-off.txt
   set STRATA_GR_UP_EPI=1
   %E%\build-sycl-win\gr_bench.exe > gr-4-on.txt
   set STRATA_GR_UP_EPI=
   %E%\build-sycl-win\gr_bench.exe > gr-5-off.txt
   set STRATA_GR_UP_EPI=1
   %E%\build-sycl-win\gr_bench.exe > gr-6-on.txt
   set STRATA_GR_UP_EPI=
   ```
   开关不设和设为 1 时，同一 token 数的 `checksum` 应相同（开发机 UHD 730 上相同，而且和 06 在 140T 上的相同）。
5. `gr_split`（hc 读里 norm、down、up 各花多少时间）各跑一次：
   ```
   %B%\gr_split.exe > split-off.txt
   set STRATA_GR_UP_EPI=1
   %B%\gr_split.exe > split-on.txt
   set STRATA_GR_UP_EPI=
   ```
   每次正常约 1 分钟；超过 5 分钟没结束就结束这个进程，在结论里写明，继续第 4 节（`gr_split` 只用来看分布，不影响第 5 节）。

## 4. 端到端分段（6 段，交替）
驱动脚本以 `plans/06` 用过的为底子，复制到原始目录再改，改了什么写进结论。

**每段用的配置副本**：把（第 1 节改过的）`D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录，原文件这一节不动：
- `cfg-a.json`：原样（`--expert-cache auto`，`env` 里有 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`）。
- `cfg-b.json`：同 `cfg-a.json`，只在 `env` 里再加 `"STRATA_GR_UP_EPI": "1"`。

配置的 `env` 会覆盖进程的环境变量（`serve/server.py:2631-2632`），所以开关只写在配置副本里。

| 顺序 | 段 | 配置 | 做什么 |
|---|---|---|---|
| 1 | `1-A` | `cfg-a` | 贪心 + 9 个请求 |
| 2 | `2-B` | `cfg-b` | 同上 |
| 3 | `3-B` | `cfg-b` | 同上 |
| 4 | `4-A` | `cfg-a` | 同上 |
| 5 | `5-A` | `cfg-a` | 同上 |
| 6 | `6-B` | `cfg-b` | 同上 |

- **任何一段都不要设 `STRATA_VERIFY_DEBUG`**（全常驻时会出错，见 `analysis/06-retro.md` 第 4 节）。

每段：
1. 先从环境里删除 `plans/03` 第 1 节列出的变量，再删除 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR` 和第 3.2 节列出的变量，然后设 `STRATA_DECODE_TIMING=1`。
2. 记下引擎日志长度；按配置副本启动服务，等就绪；`s.warm_up()`。
3. **贪心请求**（同 `plans/06` 第 3.1 节：`g1`、`g2`，temperature 0，max_tokens 256，回答 JSON 存到 `<原始目录>\<段>\`，哈希的算法相同），
   再 `s.run_chat()`（9 个请求，不跑 4K）。保存 `bench.json`。
4. 结束进程树，等到 `strata.exe` 全部退出后再等 60 秒；截取 `engine.log`。

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。
引擎日志里出现 `error`、`failed`、`mismatch`、`device lost`、`nonfinite=` 后面不是 0 的行，去掉 `no error` 这种误中后，把行（去掉路径和文本）写进结论。

## 5. 日常配置加 `STRATA_GR_UP_EPI=1`（条件满足时）
条件（四条都满足）：
1. 第 3.3 节的逐位核对通过（四条标准都满足）。
2. 6 段的 `g1` 哈希全部相同，`g2` 哈希也全部相同。
3. 三对相邻段（`1-A`/`2-B`、`3-B`/`4-A`、`5-A`/`6-B`）里，每一对都是 B 段的 ms/token（9 个请求的生成总毫秒 ÷ 生成总 token）比 A 段小。
4. 第 3.4 节 6 个 `gr_bench` 文件里，同一 token 数的 `checksum` 全部相同（第 3.4 节没跑就算不满足）。

- 满足：只在 `strata-iq3_xxs.json` 的 `env` 里再加一项 `"STRATA_GR_UP_EPI": "1"`，其他不动；用 JSON 解析器读一遍；在 `config-change.json` 里补记。结论里写「已加」。
- 不满足：不改，结论里写明哪一条没满足（数字照写）。

## 6. 放进数据目录的内容（提交前逐个打开确认只有数字和引擎状态）
1. `timing.tsv`：6 段每个请求一行，列和 `results/06-decide/timing.tsv` 相同，每个数字标出 `bench.json` 的行号。
2. `decode.tsv`：每段 `engine.log` 里以 `strata decode timing` 开头的行，原文，前面加段名和行号。
3. `greedy.tsv`、`greedy-check.txt`：格式同 `results/06-decide/`；`greedy-check.txt` 另写一句和 06 的哈希（`g1` `553ac32f017ae0be`、`g2` `1c1c19249884638f`）是否相同。
4. `startup.tsv`：每段 `engine.log` 里这几行的原文（加行号，路径换占位符）：`expert cache auto:`、`expert cache … slots`、
   `… mirrored in pinned host memory …`、`token graph hit path:`。
5. `gap.txt`：`gap-off.txt`、`gap-on.txt` 的第一行（设备名）和行数，`gap-exit.txt` 的内容，`gap-fc.txt` 有无差异。
6. `gr-<n>-<off|on>.txt`（6 个，`gr_bench` 的输出原样）、`split-off.txt`、`split-on.txt`（原样）。
7. `build.txt`：第 2、3 节的编译记录（命令、耗时、`diff --stat`、exe 的大小和 SHA256，路径换成占位符）。
8. `config-change.json`：第 1、5 节改了什么（只有键名和值）。

## 7. 结论 `lab/results/07-gr-up.md`
按 README 的「结论文件的格式」写。额外包括：
1. 每组（A、B）合并：总生成毫秒 ÷ 总生成 token（ms/token）、q1/q2/q3 各自的生成 tok/s 中位数、首 token 时间中位数、草稿接受数之和 / 提供数之和；
   每段各自的 ms/token；从 `decode.tsv` 取每个请求的 `ms/window`、`draft` 和 `tokens/window`，给出每组的中位数。
2. `gr_bench`：每个 token 数，off 3 次和 on 3 次的时间中位数；6 个文件里同一 token 数的校验和是否全部相同，是否和 `results/06-decide/gr-1.txt` 的相同。
3. `split-off.txt`、`split-on.txt` 原样贴出。
4. `gap.txt` 的结果；`greedy-check.txt` 的摘要；第 1、5 节改没改配置。
5. 第 4 节要求记录的错误行（没有就写「没有」）。
6. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/07-gr-up.md` 和 `lab/results/07-gr-up/`，推送。

预计耗时：⚠️ 约 1 小时（重编引擎约 5 分钟（06 是 303 秒）；工具编译加内核测速约 10 分钟；6 段每段约 5 分钟）。
