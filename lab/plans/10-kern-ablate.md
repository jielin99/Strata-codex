# 10：140T 上 MoE 和稠密 GEMV 内核的拆分计时（`kern_ablate`，不改引擎）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\10-kern-ablate\`（下文叫「原始目录」）。
- 结论写到 `lab/results/10-kern-ablate.md`；可公开的数据文件放在 `lab/results/10-kern-ablate/`（下文叫「数据目录」）。

**前提**：`plans/09` 已经执行完，引擎在 `d35f55e4`，`build-sycl-win\strata.exe` 是 33,721,856 字节、SHA256 以 `1a1e28c4` 开头，
日常配置 `strata-iq3_xxs.json` 的 `env` 里有 `STRATA_MMVQ_Q6_SWAR`、`STRATA_Q2_SWAR`、`STRATA_GR_UP_EPI`、`STRATA_GR_DOWN_V2`（没有 `STRATA_GU_GRID_SLM`）。
不是的话停下来报告。

**目的**：09 说明开发机核显上的快慢不能推到 140T（`analysis/09-moe-grid.md`）。这一份在 140T 上把三个最重的内核拆开计时，找出时间花在哪一步，
再决定下一轮改什么（依据 `analysis/10-prep.md`）。工具 `lab/tools/kern_ablate.cpp` 把引擎的内核按固定形状复制一份（`base`，MoE 只保留单 entry 路径，
算式和顺序与引擎相同，要求和引擎输出逐位相同），再做几份各去掉一步的诊断版本，以及两个候选写法（要求和 `base` 逐位相同）：
- MoE 专家 gate/up 的单 entry 路径（IQ3_S、IQ2_XXS，25 个专家）：`nogrid`（不查码本）、`nosign`（不做符号）、`noact`（不读激活）、`now`（不读权重）、
  候选 `slm`（码本放共享内存）。
- 稠密 Q4_K 宽内核（2560 → 10240，1–4 列）：`noones`（不算激活和的 dp4a）、`noact`、`now`。
- 稠密 Q6_K 宽内核（SWAR，2560 → 10240，1–4 列）：`noact`、`now`，候选 `pf2`、`pf4`（权重提前 2 / 4 步读）。

这一轮不改引擎、不改日常配置、不跑服务。

**例外**（README 共通规则的例外，仅限本手册写的步骤）：编译 `build-lab-ka10`。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 已有 `strata.exe` 在运行时，停下来问用户（测量时 GPU 上不能有别的负载）。
3. 请用户确认一次（确认后中间不再问）：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑。
4. 建原始目录（`mkdir D:\dev\strata-lab\10-kern-ablate`；已存在时停下来问用户）。在原始目录的 `env.txt` 记录（查法同 `plans/01` 第 0 节第 4 步）：
   日期时间、开机以来的时间、电源模式、GPU 驱动版本、可用物理内存、`git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `d35f55e4…`）、
   `git -C D:\dev\Strata-intel-npu status --short --untracked-files=no`（预期为空）、`build-sycl-win\strata.exe` 的大小和 SHA256
   （预期 33,721,856 字节，SHA256 以 `1a1e28c4` 开头）。不符就停下来报告。

## 1. 工具编译（`build-lab-ka10` 已存在时，先停下来问用户，不要覆盖）
```
set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
set "E=D:\dev\Strata-intel-npu"
set "B=D:\dev\Strata-intel-npu\build-lab-ka10"
set "L=D:\dev\Strata-lab140t\lab\tools"
mkdir %B%
set "CF=-fsycl -fsycl-default-sub-group-size=32 -fsycl-device-code-split=per_kernel /c /O2 /EHsc /std:c++20 /fp:precise /DNDEBUG -Wno-deprecated-declarations -Wno-unused-parameter -Wno-unused-variable"
set "CI=/I%E%\sycl\include /I%E%\include /I%E%\third_party\ggml /I%E%\sycl\src\kernels\cuda"
icx %CF% %CI% %L%\kern_ablate.cpp /Fo%B%\kern_ablate.obj
icx %CF% %CI% %E%\sycl\src\kernels\cuda\iq_kernels.dp.cpp /Fo%B%\iq_kernels.obj
icx %CF% %CI% %E%\sycl\src\kernels\cuda\native_mmvq.dp.cpp /Fo%B%\native_mmvq.obj
set "LF=-fsycl -fsycl-device-code-split=per_kernel -Xsycl-target-backend=spir64 "-cl-fp32-correctly-rounded-divide-sqrt -ze-opt-greater-than-4GB-buffer-required""
icx %LF% %B%\kern_ablate.obj %B%\iq_kernels.obj %B%\native_mmvq.obj -o %B%\kern_ablate.exe
```
以退出码为 0、exe 存在为准；每条命令的耗时、exe 的大小和 SHA256 记进原始目录的 `build.txt`。失败就把报错原文写进结论，停止。

## 2. 测量（同一组环境变量，跑 2 次）
```
set ONEAPI_DEVICE_SELECTOR=level_zero:gpu
set STRATA_MMVQ_Q6_SWAR=1
set STRATA_Q2_SWAR=1
set STRATA_MMVQ_A2=
set STRATA_MMVQ_PF=
set STRATA_MMVQ_WIDE_RPW=
set STRATA_MMVQ_WIDE_K=
set STRATA_MMVQ_SG=
set STRATA_MMVQ_WIDE=
set STRATA_MMVQ_WIDE_MIN=
set STRATA_MMVQ_WIDE_MAXC=
set STRATA_MMVQ_WAVE=
set STRATA_MMVQ_RPW=
set STRATA_Q6_PACKED=
set STRATA_EXPERT_LANES=
set STRATA_GU_LANES=
set STRATA_EXPERT_SPLIT=
set STRATA_OLD_IQ_MMVQ=
set STRATA_GU_GRID_SLM=
set STRATA_GROUPED_V1=
set STRATA_IQ_STAGE_GRID=
cd /d D:\dev\strata-lab\10-kern-ablate
type nul > ka-exit.txt
%B%\kern_ablate.exe 5 100 > ka-1.tsv 2> ka-1.err
echo ka-1 %ERRORLEVEL% >> ka-exit.txt
%B%\kern_ablate.exe 5 100 > ka-2.tsv 2> ka-2.err
echo ka-2 %ERRORLEVEL% >> ka-exit.txt
```
每次正常约 2–5 分钟（第一次运行要编译内核，会慢一些）；超过 15 分钟没结束就结束这个进程，在结论里写明，继续下一次。

## 3. 核对（用 `D:\dev\Strata-intel-npu\.venv\Scripts\python.exe`，先 `set PYTHONUTF8=1`；照规则算，不要自己判断）
对 `ka-1.tsv`、`ka-2.tsv` 各自：
1. 退出码 0；设备行含 `140T`；有一行 `rounds 5, launches 100` 和一行 `env STRATA_MMVQ_Q6_SWAR=1`，没有 `note:` 行；
   表头 `part type variant n us spread GB/s same checksum` 之后正好 58 行数据、每行 9 列，（`part`、`type`、`variant`、`n`）没有重复，
   而且正好是这 58 个键：`moe` 的 `IQ3_S`、`IQ2_XXS` 各 `engine base nogrid nosign noact now slm`（`n` = 25）；`q4k` 的 `Q4_K` 在 `n` = 1–4 各
   `engine base noones noact now`；`q6k` 的 `Q6_K` 在 `n` = 1–4 各 `engine base noact now pf2 pf4`。`us` 是正的有限数。
2. `same` 列：`variant` 为 `base` 的 10 行、`slm` 的 2 行、`pf2` / `pf4` 的 8 行都应为 `1`；其余行是 `-`。不是的话照记，不要重跑。
3. 两次之间：每个（`part`、`type`、`variant`、`n`）的 `checksum` 应相同（输入是固定的）；`us` 的相对差（第 2 次 ÷ 第 1 次 − 1）记下来。

把结果写进 `check.txt`：两份文件各自的 1、2 两条是否成立（不成立的行原样列出），第 3 条 `checksum` 不同的个数，
`us` 相对差里绝对值最大的一个（带正负号）和对应的行。

## 4. 放进数据目录的内容（提交前逐个打开确认：只有数字、设备和驱动信息、开关名、核对结论，以及路径换成占位符的编译命令）
1. `ka-1.tsv`、`ka-2.tsv`（原样）、`ka-exit.txt`、两个 `.err` 的大小（字节数，非 0 的把内容去掉路径后附上）、`check.txt`。
2. `build.txt`：第 1 节的编译记录（命令、耗时、exe 的大小和 SHA256，路径换成占位符）。

## 5. 结论 `lab/results/10-kern-ablate.md`
按 README 的「结论文件的格式」写。额外包括：
1. `check.txt` 原样贴出。
2. 一张表：每个（`part`、`type`、`n`），各 `variant` 的 `us`（两次的平均）。
3. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/10-kern-ablate.md` 和 `lab/results/10-kern-ablate/`，推送。

预计耗时：⚠️ 约 20 分钟（工具编译约 2 分钟（09 的同类编译约 113 秒）；两次测量各约 2–5 分钟）。
