# 12：MoE gate/up 开关 `STRATA_GU_GRID_SLM2`（140T 上比较关 / 1 / 2 + 逐位核对 + 端到端 A/B）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\12-moe-slm2\`（下文叫「原始目录」）。
- 结论写到 `lab/results/12-moe-slm2.md`；可公开的数据文件放在 `lab/results/12-moe-slm2/`（下文叫「数据目录」）。

**前提**：`plans/11` 已经执行完，引擎在 `d35f55e4`，`build-sycl-win\strata.exe` 是 33,721,856 字节、SHA256 以 `1a1e28c4` 开头；
日常配置 `strata-iq3_xxs.json` 的 `env` 里有 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`、`STRATA_GR_UP_EPI`、`STRATA_GR_DOWN_V2`，没有 `STRATA_GU_GRID_SLM` 和 `STRATA_GU_GRID_SLM2`。
不是的话停下来报告。

**目的**：开发机的依据见 `lab/analysis/12-prep.md`。MoE 约占 GPU 各阶段合计的 40%（`analysis/08-gr-down.md` 第 2 节），其中 gate/up 是最大的一段。
功能分支新提交 `a3b39b06` 加了开关 `STRATA_GU_GRID_SLM2`（默认关）：IQ2_XXS、IQ2_XS、IQ3_XXS、IQ3_S 层的专家 gate/up 把码本放进共享内存。
- `=1`：单个 entry 的计算路径读共享内存里的码本。IQ2_XXS、IQ2_XS 没有多个 entry 一起算的路径，所有 entry 都走这条；
  IQ3_XXS、IQ3_S 是按 4 个、2 个分批以后剩下的单个 entry 走这条，分批的部分不变。
- `=2`：在 `=1` 之外，IQ3_XXS、IQ3_S 按 4 个、2 个一起算的部分也读共享内存里的码本。
开发机上两种设置的最终输出和量化前的 gate/up 都和关时逐位相同。这一份先在 140T 上用 `moe_probe` 比较关、1、2，并核对 140T 上同样逐位相同；
按第 3 节的规则选出一个设置（加权快 2% 以上）后再做端到端 A/B，条件满足时加进日常配置。

**例外**（README 共通规则的例外，仅限本手册写的步骤）：更新引擎 checkout 并重新编译 `build-sycl-win`；编译 `build-lab-moe12`；
第 5 节在条件满足时改一次 `strata-iq3_xxs.json`（先备份）。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次（确认后中间不再问）：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑；共享 GPU 内存上限仍是 75%。
4. 建原始目录（`mkdir D:\dev\strata-lab\12-moe-slm2`；已存在时停下来问用户）。在原始目录的 `env.txt` 记录（查法同 `plans/01` 第 0 节第 4 步）：
   日期时间、开机以来的时间、电源模式、GPU 驱动版本、可用物理内存、`git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `d35f55e4…`）、
   `git -C D:\dev\Strata-intel-npu status --short --untracked-files=no`（预期为空）、`build-sycl-win\strata.exe` 的大小、修改时间和 SHA256
   （预期 33,721,856 字节，SHA256 以 `1a1e28c4` 开头）。不符就停下来报告。

## 1. 更新引擎并编译
1. 把 `build-sycl-win\strata.exe` 复制到原始目录，命名为 `strata-d35f55e4.exe`（回退用，不提交）。
2. 更新（只允许快进）：
   ```
   git -C D:\dev\Strata-intel-npu fetch git@github.com:jielin99/Strata-codex.git local-v0.1.43.1-intel-npu
   git -C D:\dev\Strata-intel-npu merge --ff-only FETCH_HEAD
   git -C D:\dev\Strata-intel-npu rev-parse HEAD
   git -C D:\dev\Strata-intel-npu diff --stat d35f55e4 HEAD
   ```
   HEAD 应为 `a3b39b06…`，`diff --stat` 应只有 `sycl/src/kernels/cuda/iq_kernels.dp.cpp` 一个文件。不是的话停下来报告。
3. 编译：`D:\dev\Strata-intel-npu\sycl\tools\build_windows.bat`。以退出码为 0 为准，记下耗时、新 exe 的大小、修改时间和 SHA256。
   编译失败就把报错原文（去掉路径里的用户名）写进结论，把 `strata-d35f55e4.exe` 复制回 `build-sycl-win\strata.exe`，停止。
4. 确认 `build-sycl-win\native_grouped_parity.exe` 存在且修改时间晚于这次编译开始。不是的话在结论里写明，**第 3 节第 3 步整个跳过**
   （不要运行旧的 exe，也不写 `ngp` 的退出码）；判定脚本会因为缺这几项记为问题，结果是 `choice: none`。

## 2. 工具编译（`build-lab-moe12` 已存在时，先停下来问用户，不要覆盖）
```
set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
set "E=D:\dev\Strata-intel-npu"
set "B=D:\dev\Strata-intel-npu\build-lab-moe12"
set "L=D:\dev\Strata-lab140t\lab\tools"
mkdir %B%
set "CF=-fsycl -fsycl-default-sub-group-size=32 -fsycl-device-code-split=per_kernel /c /O2 /EHsc /std:c++20 /fp:precise /DNDEBUG -Wno-deprecated-declarations -Wno-unused-parameter -Wno-unused-variable"
set "CI=/I%E%\sycl\include /I%E%\include /I%E%\third_party\ggml /I%E%\sycl\src\kernels\cuda"
icx %CF% %CI% %L%\moe_probe.cpp /Fo%B%\moe_probe.obj
icx %CF% %CI% %E%\sycl\src\kernels\cuda\iq_kernels.dp.cpp /Fo%B%\iq_kernels.obj
icx %CF% %CI% %E%\sycl\src\kernels\cuda\native_mmvq.dp.cpp /Fo%B%\native_mmvq.obj
set "LF=-fsycl -fsycl-device-code-split=per_kernel -Xsycl-target-backend=spir64 "-cl-fp32-correctly-rounded-divide-sqrt -ze-opt-greater-than-4GB-buffer-required""
icx %LF% %B%\moe_probe.obj %B%\iq_kernels.obj %B%\native_mmvq.obj -o %B%\moe_probe.exe
```
以每条命令退出码为 0、exe 存在为准；每条命令的耗时、exe 的大小和 SHA256 记进原始目录的 `build.txt`。
失败就把报错原文写进结论，第 3 节跳过，第 4、5 节不做。

## 3. 内核对比、逐位核对（`strata.exe` 不运行时）
环境变量（这一节都用这一组，三种设置只差 `STRATA_GU_GRID_SLM2`）：
```
set ONEAPI_DEVICE_SELECTOR=level_zero:gpu
set STRATA_Q2_SWAR=1
set "STRATA_GU_LANES="
set "STRATA_DOWN_LANES="
set "STRATA_EXPERT_SPLIT="
set "STRATA_OLD_IQ_MMVQ="
set "STRATA_GROUPED_V1="
set "STRATA_IQ_STAGE_GRID="
set "STRATA_GU_GRID_SLM="
set "STRATA_GU_GRID_SLM2="
cd /d D:\dev\strata-lab\12-moe-slm2
set STRATA_ > env-strata.txt
type env-strata.txt
```
`env-strata.txt` 应该正好一行 `STRATA_Q2_SWAR=1`（`set STRATA_` 列出所有以 `STRATA_` 开头的变量）。多出来的变量逐个 `set "名字="` 删掉，再重做这一步，直到正好一行。

1. **预热**（每种设置第一次运行要编译它的内核；输出不分析，只记退出码）。逐行输入：
   ```
   type nul > mp-exit.txt
   set "STRATA_GU_GRID_SLM2="
   %B%\moe_probe.exe 50 1 > warm-off.txt 2>&1
   echo warm-off %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2=1"
   %B%\moe_probe.exe 50 1 > warm-1.txt 2>&1
   echo warm-1 %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2=2"
   %B%\moe_probe.exe 50 1 > warm-2.txt 2>&1
   echo warm-2 %ERRORLEVEL% >> mp-exit.txt
   ```
   之后**不要再清空 `mp-exit.txt`**。
2. **`moe_probe` 跑 3 轮**，每轮三种设置各一次，顺序轮换（第 1 轮 关、1、2；第 2 轮 1、2、关；第 3 轮 2、关、1）。逐行输入，不要改动：
   ```
   set "STRATA_GU_GRID_SLM2="
   %B%\moe_probe.exe 200 4 > mp-1-off.tsv 2> mp-1-off.err
   echo mp-1-off %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2=1"
   %B%\moe_probe.exe 200 4 > mp-1-1.tsv 2> mp-1-1.err
   echo mp-1-1 %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2=2"
   %B%\moe_probe.exe 200 4 > mp-1-2.tsv 2> mp-1-2.err
   echo mp-1-2 %ERRORLEVEL% >> mp-exit.txt

   set "STRATA_GU_GRID_SLM2=1"
   %B%\moe_probe.exe 200 4 > mp-2-1.tsv 2> mp-2-1.err
   echo mp-2-1 %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2=2"
   %B%\moe_probe.exe 200 4 > mp-2-2.tsv 2> mp-2-2.err
   echo mp-2-2 %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2="
   %B%\moe_probe.exe 200 4 > mp-2-off.tsv 2> mp-2-off.err
   echo mp-2-off %ERRORLEVEL% >> mp-exit.txt

   set "STRATA_GU_GRID_SLM2=2"
   %B%\moe_probe.exe 200 4 > mp-3-2.tsv 2> mp-3-2.err
   echo mp-3-2 %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2="
   %B%\moe_probe.exe 200 4 > mp-3-off.tsv 2> mp-3-off.err
   echo mp-3-off %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2=1"
   %B%\moe_probe.exe 200 4 > mp-3-1.tsv 2> mp-3-1.err
   echo mp-3-1 %ERRORLEVEL% >> mp-exit.txt
   ```
   11 里 140T 上每次约 108 秒；超过 10 分钟没结束就结束这个进程，在结论里写明，继续下一条。两次之间不用等待。
   每个文件开头是设备名、驱动、`200 ms per case`、`env` 行（都有 `env STRATA_Q2_SWAR=1`；1、2 的文件多一行 `env STRATA_GU_GRID_SLM2=1` 或 `=2`）和专家占用的显存，
   然后是表头 `case scope layers groups entries mem phase us_per_layer GB/s iters checksum gu_checksum` 和数据行。
3. **引擎自带的组跨步核对**（它比较新的启动方式和逐组启动，两边用同一个开关状态，所以三种设置各跑一次）。第 1 节第 4 步不通过时整步跳过。逐行输入：
   ```
   set "STRATA_GU_GRID_SLM2="
   %E%\build-sycl-win\native_grouped_parity.exe > ngp-off.txt 2>&1
   echo ngp-off %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2=1"
   %E%\build-sycl-win\native_grouped_parity.exe > ngp-1.txt 2>&1
   echo ngp-1 %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2=2"
   %E%\build-sycl-win\native_grouped_parity.exe > ngp-2.txt 2>&1
   echo ngp-2 %ERRORLEVEL% >> mp-exit.txt
   set "STRATA_GU_GRID_SLM2="
   ```
4. **判定**（用 `D:\dev\Strata-intel-npu\.venv\Scripts\python.exe`，先 `set PYTHONUTF8=1`；照脚本的输出记，不要自己判断）：
   ```
   %E%\.venv\Scripts\python.exe %L%\moe_choice.py D:\dev\strata-lab\12-moe-slm2 140T
   ```
   脚本写出原始目录的 `choice.txt` 和 `medians.tsv`，并打印 `choice.txt`。下面每一条不成立都记为一个问题：
   - `mp-exit.txt` 正好 15 行（3 个预热、9 个 `moe_probe`、3 个 `ngp`）、名字不重复、全部是 0；9 个 `.err` 都是空的；`env-strata.txt` 正好一行 `STRATA_Q2_SWAR=1`；
     3 个 `ngp-*.txt` 的最后一行都是 `native_grouped_parity: 0 failures`。
   - 9 个 `.tsv` 表头之前的行和上面写的一致（设备行含 `140T`），驱动行相同；每份 462 行、键不重复且和工具固定输出的 462 个键（7 种情形 × 11 个范围 × 2 种布局 × 3 个阶段）一致、时间是正的有限数、`iters` ≥ 1，
     `phase` 为 `all` 的 154 行带两个 16 位十六进制校验和。
   - 9 份的 `checksum` 和 `gu_checksum` 逐键全部相同。
   - **时间**：`case` 为 `T1`…`T4`、`scope` 为 `window`、`mem` 为 `dram`、`phase` 为 `all` 的 `us_per_layer`，每种设置取 3 轮的中位数 t1…t4，
     加权时间 W = 0.12·t1 + 0.14·t2 + 0.12·t3 + 0.62·t4（生成窗口里各 T 的占比，`analysis/03-window-t.md`，和 09 相同）。
   - **选择**：没有问题时，在 W 小于 0.98 × W(关) 的设置（1、2）里选 W 较小的一个；都不满足或有问题时为 `none`。
     `choice.txt` 第一行是 `problems: <个数>`（有问题时逐条列在它下面），接着一行是 `choice: 1`、`choice: 2` 或 `choice: none`。
   - `choice: none` 时第 4、5 节不做，整理数据、写结论。

## 4. 端到端分段（6 段，交替；第 3 节 `choice: none` 时不做）
驱动脚本以 `plans/08` 用过的为底子，复制到原始目录再改，改了什么写进结论。

**每段用的配置副本**：把 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json` 复制到原始目录，原文件这一节不动：
- `cfg-a.json`：原样。
- `cfg-b.json`：同 `cfg-a.json`，只在 `env` 里再加 `"STRATA_GU_GRID_SLM2": "<choice 的值>"`（`"1"` 或 `"2"`）。

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
1. 先从环境里删除 `plans/03` 第 1 节列出的变量，再删除 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`、`STRATA_GR_UP_EPI`、`STRATA_GR_DOWN_V2`、`STRATA_GR_DOWN_ROWS`、
   `STRATA_GU_GRID_SLM`、`STRATA_GU_GRID_SLM2` 和第 3 节列出的其余变量，然后设 `STRATA_DECODE_TIMING=1`。
2. 记下引擎日志长度；按配置副本启动服务，等就绪；`s.warm_up()`。
3. **贪心请求**（同 `plans/06` 第 3.1 节：`g1`、`g2`，temperature 0，max_tokens 256，回答 JSON 存到 `<原始目录>\<段>\`，哈希的算法相同），
   再 `s.run_chat()`（9 个请求，不跑 4K）。保存 `bench.json`。
4. 结束进程树，等到 `strata.exe` 全部退出后再等 60 秒；截取 `engine.log`。

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。
引擎日志里出现 `error`、`failed`、`mismatch`、`device lost`、`nonfinite=` 后面不是 0 的行，去掉 `no error` 这种误中后，把行（去掉路径和文本）写进结论。

## 5. 日常配置加开关（条件满足时）
条件（五条都满足）：
1. 第 3 节 `choice` 是 1 或 2（它已满足完整性、校验和与组跨步核对）。
2. 6 段都完成（没有跳过的段），每段 9 个测速请求都成功。
3. 6 段的 `g1` 哈希全部相同，`g2` 哈希也全部相同。
4. 三对相邻段（`1-A`/`2-B`、`3-B`/`4-A`、`5-A`/`6-B`）里，每一对都是 B 段的 ms/token（9 个请求的生成总毫秒 ÷ 生成总 token）比 A 段小。
5. 第 4 节要求记录的错误行一条也没有（去掉 `no error` 这种误中之后）。

- 满足：先把 `strata-iq3_xxs.json` 复制到原始目录（`strata-iq3_xxs.before-12.json`，不提交），再只在它的 `env` 里加 `"STRATA_GU_GRID_SLM2": "<choice 的值>"`，其他不动；
  用 JSON 解析器读一遍；在 `config-change.json` 里记下改前改后的 `env`（只有键名和值）。结论里写「已加」。
- 不满足：不改，结论里写明哪一条没满足（数字照写）。

## 6. 放进数据目录的内容（提交前逐个打开确认：只有数字、设备和驱动信息、开关名、核对结论，以及路径换成占位符的编译命令）
1. `timing.tsv`、`decode.tsv`、`greedy.tsv`、`greedy-check.txt`、`startup.tsv`：格式同 `results/08-gr-down/`；
   `greedy-check.txt` 另写一句和 08 的哈希（`g1` `553ac32f017ae0be`、`g2` `1c1c19249884638f`）是否相同。第 4 节没做就没有这几个文件。
2. 9 个 `mp-*.tsv`（原样）、`mp-exit.txt`、`env-strata.txt`、`choice.txt`、`medians.tsv`，3 个 `ngp-*.txt` 的最后 3 行。
   预热输出不提交。`.err` 都是空的话不提交，非空的去掉路径后附上。
3. `build.txt`：第 1、2 节的编译记录（命令、耗时、`diff --stat`、exe 的大小和 SHA256，路径换成占位符）。
4. `config-change.json`（第 5 节改了才有）。

## 7. 结论 `lab/results/12-moe-slm2.md`
按 README 的「结论文件的格式」写。额外包括：
1. `choice.txt` 原样贴出。
2. 第 4 节做了的话：每组（A、B）合并：总生成毫秒 ÷ 总生成 token（ms/token）、q1/q2/q3 各自的生成 tok/s 中位数、首 token 时间中位数、
   草稿接受数之和 / 提供数之和；每段各自的 ms/token；从 `decode.tsv` 取每个请求的 `ms/window`、`draft` 和 `tokens/window`，给出每组的中位数。
3. `greedy-check.txt` 的摘要；第 5 节改没改配置。
4. 第 4 节要求记录的错误行（没有就写「没有」）。
5. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/12-moe-slm2.md` 和 `lab/results/12-moe-slm2/`，推送。

预计耗时：⚠️ 约 1 小时 10 分钟（重编引擎约 5 分钟（08 是 301 秒）；工具编译约 2 分钟；预热约 2 分钟；9 次 `moe_probe` 约 17 分钟（11 里每次约 108 秒）；
`ngp` 3 次（⬜ 140T 上的耗时没记录过）；6 段每段约 5 分钟）。
