# 08：hc 读 down 内核开关 `STRATA_GR_DOWN_V2=1`（变体选择 + 分内核计时 + 端到端 A/B + 逐位核对）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\08-gr-down\`（下文叫「原始目录」）。
- 结论写到 `lab/results/08-gr-down.md`；可公开的数据文件放在 `lab/results/08-gr-down/`（下文叫「数据目录」）。

**前提**：`plans/07` 已经执行完，引擎在 `43ce0300`，日常配置 `strata-iq3_xxs.json` 的 `env` 里有 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`、`STRATA_GR_UP_EPI`。不是的话停下来报告。

**目的**：开发机的判断见 `lab/analysis/07-gr-up.md`（候选的来源）和 `lab/analysis/08-prep.md`（这一份的依据）。
07 之后 hc 读里最大的是 down（加 reduce），它在 140T 编译目标上有 1.2–1.6 KB 的寄存器溢出。功能分支新提交 `0408d916` 加了开关
`STRATA_GR_DOWN_V2=1`（同样的运算和顺序，寄存器用得少，开发机上逐位相同），以及只在它打开时生效的 `STRATA_GR_DOWN_ROWS=64|128`（一片的行分给更多工作组）。
这一份先在 140T 上从三个变体里选出最快的，再做端到端 A/B，条件满足时加进日常配置；同时把 hc 读拆到每个内核计时，最后用一个长请求跑一次 PROFILE，
得到提示词窗口混入较少的、近似的分阶段时间（这两项都只用来给以后定目标，`analysis/08-prep.md` 第 3、4 节）。

**例外**（README 共通规则的例外，仅限本手册写的步骤）：更新引擎 checkout 并重新编译 `build-sycl-win`；编译 `build-lab-gr8`；
第 5 节在条件满足时改一次 `strata-iq3_xxs.json`（先备份）。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次（确认后中间不再问）：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑；共享 GPU 内存上限仍是 75%。
4. 在原始目录的 `env.txt` 记录（查法同 `plans/01` 第 0 节第 4 步）：日期时间、开机以来的时间、电源模式、GPU 驱动版本、可用物理内存、
   `git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `43ce0300…`）、`git -C D:\dev\Strata-intel-npu status --short --untracked-files=no`（预期为空）、
   `build-sycl-win\strata.exe` 的大小、修改时间和 SHA256（预期 33,016,320 字节，SHA256 以 `55ee540c` 开头）。不符就停下来报告。

## 1. 更新引擎并编译
1. 把 `build-sycl-win\strata.exe` 复制到原始目录，命名为 `strata-43ce0300.exe`（回退用，不提交）。
2. 更新（只允许快进）：
   ```
   git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git local-v0.1.43.1-intel-npu
   git -C D:\dev\Strata-intel-npu merge --ff-only FETCH_HEAD
   git -C D:\dev\Strata-intel-npu rev-parse HEAD
   git -C D:\dev\Strata-intel-npu diff --stat 43ce0300 HEAD
   ```
   HEAD 应为 `0408d916…`，`diff --stat` 应只有 `sycl/src/kernels/cuda/fused_gr.dp.cpp` 一个文件。不是的话停下来报告。
3. 编译：`D:\dev\Strata-intel-npu\sycl\tools\build_windows.bat`。以退出码为 0 为准，记下耗时、新 exe 的大小、修改时间和 SHA256。
   编译失败就把报错原文（去掉路径里的用户名）写进结论，把 `strata-43ce0300.exe` 复制回 `build-sycl-win\strata.exe`，停止。
4. 确认 `build-sycl-win\gr_bench.exe` 存在且修改时间晚于这次编译开始。不是的话在结论里写明，第 2、3 节跳过，第 4、5 节不做。

## 2. 工具编译（`build-lab-gr8` 已存在时，先停下来问用户，不要覆盖）
```
set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
set "E=D:\dev\Strata-intel-npu"
set "B=D:\dev\Strata-intel-npu\build-lab-gr8"
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
`gr_events.py` 应打印 `launch sites recorded`。以退出码为 0、exe 存在为准；每条命令的耗时、exe 的大小和 SHA256 记进原始目录的 `build.txt`。
失败就把报错原文写进结论，跳过用它的那一步，继续。

## 3. 内核测速、选变体、逐位核对（`strata.exe` 不运行时）
环境变量（这一节都用这一组，四个变体只差最后几个变量）：
```
set ONEAPI_DEVICE_SELECTOR=level_zero:gpu
set STRATA_GR_V3=
set STRATA_GR_DOWN_SLICED=
set STRATA_GR_DOWN_DIRECT=
set STRATA_GR_NORM_SPLIT=
set STRATA_HC_SPLIT=
set STRATA_GR_UP_EPI=1
cd /d D:\dev\strata-lab\08-gr-down
```

| 变体 | 再设的变量 |
|---|---|
| `base` | `set STRATA_GR_DOWN_V2=` 和 `set STRATA_GR_DOWN_ROWS=`（都不设） |
| `v2` | `set STRATA_GR_DOWN_V2=1`，`set STRATA_GR_DOWN_ROWS=` |
| `r128` | `set STRATA_GR_DOWN_V2=1`，`set STRATA_GR_DOWN_ROWS=128` |
| `r64` | `set STRATA_GR_DOWN_V2=1`，`set STRATA_GR_DOWN_ROWS=64` |

1. **逐位核对**：先 `type nul > gap-exit.txt`。每个变体跑一次 `%B%\gr_apply_parity.exe > gap-<变体>.txt`，每次之后 `echo <变体>-exit %ERRORLEVEL% >> gap-exit.txt`；
   然后 `fc gap-base.txt gap-<变体>.txt > gap-fc-<变体>.txt`、`echo fc-<变体> %ERRORLEVEL% >> gap-exit.txt`（`v2`、`r128`、`r64` 各一次），
   最后 `find /c /v "" gap-base.txt gap-v2.txt gap-r128.txt gap-r64.txt >> gap-exit.txt`。
   一个变体通过 = 它和 `base` 的程序退出码都是 0、两个文件都是 33 行、`fc` 退出码为 0、`gap-fc-<变体>.txt` 里是「找不到差异」。
2. **`gr_bench` 交替跑 3 轮**，每轮按 `base`、`v2`、`r128`、`r64` 的顺序各跑一次：`%E%\build-sycl-win\gr_bench.exe > gr-<轮>-<变体>.txt`（轮 = 1、2、3，共 12 个文件）。
3. **选变体**（照下面的规则算，不要自己判断）：
   - 每个变体、每个 token 数取 3 轮的中位数 t1…t6（微秒）。加权时间 W = 0.12·t1 + 0.14·t2 + 0.12·t3 + 0.62·t4（生成窗口里各 T 的占比，`analysis/03-window-t.md`）。
   - 候选只从 `v2`、`r128`、`r64` 里选。一个变体是候选 = 它通过第 3.1 节，而且对每个 token 数 1…6，`base` 三轮和它三轮的 6 个 `checksum` 全部相同。
   - 候选里选 W 最小的一个。没有候选，或者选出的 W 不比 `base` 的 W 小 2% 以上（W ≥ 0.98 × base 的 W），就算「没有变体胜出」。
   - 「没有变体胜出」时：照做第 3.4 节，跳过第 4、5 节，再做第 5b 节，然后整理数据、写结论。
   - 在 `choice.txt` 写下：四个变体的 t1…t6 和 W、每个变体是否为候选、选中的变体（或「没有变体胜出」）。
4. **分内核计时**：`base` 和选中的变体各跑一次 `%B%\gr_events_bench.exe > ev-<变体>.txt`（没有变体胜出时，四个都跑）。
   每行的 `kernels` 列应为 4（norm、down、reduce、up）；不是 4 就在结论里写明。
   每次正常约 1 分钟；超过 5 分钟没结束就结束这个进程，在结论里写明，继续。

## 4. 端到端分段（6 段，交替；第 3.3 节没有变体胜出就不做）
驱动脚本以 `plans/07` 用过的为底子，复制到原始目录再改，改了什么写进结论。

**每段用的配置副本**：把 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录，原文件这一节不动：
- `cfg-a.json`：原样。
- `cfg-b.json`：同 `cfg-a.json`，只在 `env` 里再加 `"STRATA_GR_DOWN_V2": "1"`；选中的是 `r128` 或 `r64` 时，再加 `"STRATA_GR_DOWN_ROWS": "128"`（或 `"64"`）。

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
1. 先从环境里删除 `plans/03` 第 1 节列出的变量，再删除 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`、`STRATA_GR_UP_EPI`、`STRATA_GR_DOWN_V2`、`STRATA_GR_DOWN_ROWS`
   和第 3 节列出的其余变量，然后设 `STRATA_DECODE_TIMING=1`。
2. 记下引擎日志长度；按配置副本启动服务，等就绪；`s.warm_up()`。
3. **贪心请求**（同 `plans/06` 第 3.1 节：`g1`、`g2`，temperature 0，max_tokens 256，回答 JSON 存到 `<原始目录>\<段>\`，哈希的算法相同），
   再 `s.run_chat()`（9 个请求，不跑 4K）。保存 `bench.json`。
4. 结束进程树，等到 `strata.exe` 全部退出后再等 60 秒；截取 `engine.log`。

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。
引擎日志里出现 `error`、`failed`、`mismatch`、`device lost`、`nonfinite=` 后面不是 0 的行，去掉 `no error` 这种误中后，把行（去掉路径和文本）写进结论。

## 5. 日常配置加选中的变体（条件满足时）
条件（四条都满足）：
1. 第 3.3 节选出了变体（它已满足逐位核对和校验和两条）。
2. 6 段都完成（没有跳过的段），每段 9 个测速请求都成功。
3. 6 段的 `g1` 哈希全部相同，`g2` 哈希也全部相同。
4. 三对相邻段（`1-A`/`2-B`、`3-B`/`4-A`、`5-A`/`6-B`）里，每一对都是 B 段的 ms/token（9 个请求的生成总毫秒 ÷ 生成总 token）比 A 段小。

- 满足：先把 `strata-iq3_xxs.json` 复制到原始目录（`strata-iq3_xxs.before-08.json`，不提交），再只在它的 `env` 里加 `cfg-b.json` 比 `cfg-a.json` 多出的那一项或两项，其他不动；
  用 JSON 解析器读一遍；在 `config-change.json` 里记下改前改后的 `env`（只有键名和值）。结论里写「已加」。
- 不满足：不改，结论里写明哪一条没满足（数字照写）。

## 5b. 分阶段计时（最后一段，只看比例，不参与任何决定）
第 5 节做完后（不论改没改配置）跑这一段 `7-P`，第 3.3 节没有变体胜出也照跑：
1. 配置：把（第 5 节之后的）`strata-iq3_xxs.json` 复制为原始目录的 `cfg-p.json`，原样。
2. 环境：同第 4 节每段的第 1 步，再设 `STRATA_VERIFY_PROFILE=1`。**不要设 `STRATA_VERIFY_DEBUG`。**
3. 启动服务，`s.warm_up()`，然后只发一个贪心请求 `g3`（请求体同 `plans/06` 第 3.1 节，`max_tokens` 改为 1024）：
   `写一篇约一千字的文章，介绍混合专家模型（MoE）的原理、优点、缺点和典型应用。`
4. 结束进程树、等 60 秒、截取 `engine.log`。启动失败或请求失败就记下来，不重试，继续第 6 节。
5. 记录：`engine.log` 里这个请求的 `strata decode timing` 行和紧跟的 `strata decode GPU stages` 行（原文，加行号），
   以及回答的 `completion_tokens`、`finish_reason`（回答本身不提交）。

## 6. 放进数据目录的内容（提交前逐个打开确认只有数字和引擎状态）
1. `timing.tsv`、`decode.tsv`、`greedy.tsv`、`greedy-check.txt`、`startup.tsv`：格式同 `results/07-gr-up/`；`greedy-check.txt` 另写一句和 07 的哈希（`g1` `553ac32f017ae0be`、`g2` `1c1c19249884638f`）是否相同。
2. `gap.txt`：四个 `gap-<变体>.txt` 的第一行（设备名）和行数、`gap-exit.txt` 的内容、三个 `gap-fc-<变体>.txt` 有无差异。
3. `gr-<轮>-<变体>.txt`（12 个，原样）、`choice.txt`、`ev-<变体>.txt`（原样）。
4. `build.txt`：第 1、2 节的编译记录（命令、耗时、`diff --stat`、exe 的大小和 SHA256，路径换成占位符）。
5. `config-change.json`（第 5 节改了才有）。
6. `profile.txt`：第 5b 节记录的两行原文、`completion_tokens`、`finish_reason`；失败时写失败的原文。

## 7. 结论 `lab/results/08-gr-down.md`
按 README 的「结论文件的格式」写。额外包括：
1. `choice.txt` 原样贴出；`ev-<变体>.txt` 原样贴出。
2. 每组（A、B）合并：总生成毫秒 ÷ 总生成 token（ms/token）、q1/q2/q3 各自的生成 tok/s 中位数、首 token 时间中位数、草稿接受数之和 / 提供数之和；
   每段各自的 ms/token；从 `decode.tsv` 取每个请求的 `ms/window`、`draft` 和 `tokens/window`，给出每组的中位数。
3. `gap.txt` 的结果；`greedy-check.txt` 的摘要；第 5 节改没改配置。
4. 第 4 节要求记录的错误行（没有就写「没有」）；`profile.txt` 原样贴出。
5. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/08-gr-down.md` 和 `lab/results/08-gr-down/`，推送。

预计耗时：⚠️ 约 1 小时 10 分（重编引擎约 5 分钟（07 是 320 秒）；工具编译约 5 分钟；内核测速约 10 分钟；6 段每段约 5 分钟；第 5b 节约 5 分钟）。
