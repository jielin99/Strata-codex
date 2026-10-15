# 02：在 140T 上测稠密 GEMV 内核，对比 Q6_K 去掉 sub_sat 前后（只测内核，不改引擎）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\02-mmvq-q6k\`（下文叫「原始目录」）。
- 结论写到 `lab/results/02-mmvq-q6k.md`；可公开的数据文件放在 `lab/results/02-mmvq-q6k/`（下文叫「数据目录」）。

**目的**：`lab/analysis/02-kernel-code.md` 在开发机上发现，Q6_K 的 wide 内核去掉逐字节的 `sub_sat` 后，指令减少约一半，
UHD 730 上快 13–73%。这一份在 140T 上确认两件事：
1. 去掉 `sub_sat` 后，140T 上实际快多少，输出是否完全相同。
2. 140T 上每种类型、每种列数（1–6）的稠密 GEMV 速率（给后面的分析用）。

**不改引擎代码**：去掉 `sub_sat` 的版本，由 `lab/tools/q6k_nosat_patch.py` 把引擎的 `native_mmvq.dp.cpp` **复制**一份再改，
引擎目录里的文件只读不写。测量工具编译到新的 `build-lab-mmvq` 目录。**不启动 `strata.exe`**。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 已有 `strata.exe` 在运行时，停下来问用户（它占着约 28 GiB 显存，也会干扰计时）。
3. 请用户确认一次：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑。确认后中间不再问。
4. 在原始目录的 `env.txt` 记录：
   - 日期时间、开机以来的时间（`net statistics workstation` 的「统计数据开始于」一行）。
   - `git -C D:\dev\Strata-intel-npu rev-parse HEAD`（预期 `29825274…`，不一致就停下来报告）。
   - `git -C D:\dev\Strata-intel-npu status --short sycl`（预期为空）。
   - 电源模式：查法和 `plans/01` 第 0 节第 4 步相同，**以设置里的电源模式为准**，不能用电源计划的名字代替。
   - GPU 驱动版本（PowerShell：`Get-CimInstance Win32_VideoController | Select Name,DriverVersion`）。

## 1. 编译两个版本的 mmvq_lab
在一个 CMD 窗口里依次执行。任何一步失败，就把报错原文（去掉路径里的用户名）写进结论，停止，不要自己改源码或参数后重试。

1. 准备环境和目录：
   ```
   set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
   call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
   set "E=D:\dev\Strata-intel-npu"
   set "B=D:\dev\Strata-intel-npu\build-lab-mmvq"
   set "L=D:\dev\Strata-lab140t\lab\tools"
   mkdir %B%\base %B%\nosat
   set PYTHONUTF8=1
   ```
   `build-lab-mmvq` 已存在时，先停下来问用户，不要覆盖。
2. 生成去掉 `sub_sat` 的副本，并检查只改了 2 行：
   ```
   %E%\.venv\Scripts\python.exe %L%\q6k_nosat_patch.py %E%\sycl\src\kernels\cuda\native_mmvq.dp.cpp %B%\nosat\native_mmvq_nosat.dp.cpp
   git diff --no-index --ignore-cr-at-eol --numstat %E%\sycl\src\kernels\cuda\native_mmvq.dp.cpp %B%\nosat\native_mmvq_nosat.dp.cpp
   ```
   第二条命令应当只输出一行，开头是 `2	2`（2 行增、2 行删）。不是的话停下来报告。
   再记录两个文件的 SHA256（`certutil -hashfile <文件> SHA256`）到原始目录的 `build.txt`。
3. 编译选项（和引擎 JIT 构建的 `sycl/CMakeLists.txt:65-91` 一致：`-fsycl`、32 宽子组、每个内核一个模块、Windows 上 `/fp:precise`）：
   ```
   set "CF=-fsycl -fsycl-default-sub-group-size=32 -fsycl-device-code-split=per_kernel /c /O2 /EHsc /std:c++20 /fp:precise /DNDEBUG -Wno-deprecated-declarations -Wno-unused-parameter -Wno-unused-variable"
   set "CI=/I%E%\sycl\include /I%E%\include /I%E%\third_party\ggml /I%E%\sycl\src\kernels\cuda"
   icx %CF% %CI% %L%\mmvq_lab.cpp /Fo%B%\mmvq_lab.obj
   icx %CF% %CI% %E%\sycl\src\kernels\cuda\iq_kernels.dp.cpp /Fo%B%\iq_kernels.obj
   icx %CF% %CI% %E%\sycl\src\kernels\cuda\native_mmvq.dp.cpp /Fo%B%\base\native_mmvq.obj
   icx %CF% %CI% %B%\nosat\native_mmvq_nosat.dp.cpp /Fo%B%\nosat\native_mmvq.obj
   ```
   `iq_kernels.dp.cpp` 很大，⚠️ 可能要编译几分钟到十几分钟。每条命令的耗时记进 `build.txt`。
4. 链接（和引擎 JIT 构建的链接选项一致）：
   ```
   set "LF=-fsycl -fsycl-device-code-split=per_kernel -Xsycl-target-backend=spir64 "-cl-fp32-correctly-rounded-divide-sqrt -ze-opt-greater-than-4GB-buffer-required""
   icx %LF% %B%\mmvq_lab.obj %B%\iq_kernels.obj %B%\base\native_mmvq.obj -o %B%\base\mmvq_lab.exe
   icx %LF% %B%\mmvq_lab.obj %B%\iq_kernels.obj %B%\nosat\native_mmvq.obj -o %B%\nosat\mmvq_lab.exe
   ```
   以退出码为 0、exe 存在为准。两个 exe 的大小和 SHA256 记进 `build.txt`。

## 2. 运行（交替，8 次）
1. 环境变量：
   ```
   set ONEAPI_DEVICE_SELECTOR=level_zero:gpu
   set UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1
   set STRATA_MMVQ_SG=
   set STRATA_MMVQ_PF=
   set STRATA_MMVQ_WIDE_RPW=
   set STRATA_MMVQ_A2=
   set STRATA_MMVQ_WIDE_K=
   set STRATA_MMVQ_WIDE_32=
   set STRATA_MMVQ_WAVE=
   set STRATA_MMVQ_RPW=
   set SYCL_PROGRAM_COMPILE_OPTIONS=
   ```
   （`set X=` 就是从环境里删除。）
2. 按下表顺序跑，每次的标准输出存成原始目录下的 `<名字>.tsv`，标准错误存成 `<名字>.err`，并记下开始和结束时间。
   参数是「工作集 MiB、每种情况的毫秒数、筛选」。

   | 顺序 | 名字 | 程序 | 参数 |
   |---|---|---|---|
   | 1 | `base-1` | `%B%\base\mmvq_lab.exe` | `1024 300 all` |
   | 2 | `nosat-1` | `%B%\nosat\mmvq_lab.exe` | `1024 300 all` |
   | 3 | `nosat-2` | `%B%\nosat\mmvq_lab.exe` | `1024 300 all` |
   | 4 | `base-2` | `%B%\base\mmvq_lab.exe` | `1024 300 all` |
   | 5 | `nosat-q6-1` | `%B%\nosat\mmvq_lab.exe` | `1024 300 Q6_K` |
   | 6 | `base-q6-1` | `%B%\base\mmvq_lab.exe` | `1024 300 Q6_K` |
   | 7 | `base-q6-2` | `%B%\base\mmvq_lab.exe` | `1024 300 Q6_K` |
   | 8 | `nosat-q6-2` | `%B%\nosat\mmvq_lab.exe` | `1024 300 Q6_K` |

   例：`%B%\base\mmvq_lab.exe 1024 300 all > D:\dev\strata-lab\02-mmvq-q6k\base-1.tsv 2> D:\dev\strata-lab\02-mmvq-q6k\base-1.err`

   - 第一次运行时驱动要即时编译内核，开头会停一段时间，这是正常的（工具在计时前已经把每份权重跑过一遍）。
   - 某一次出现 `allocation failed`、崩溃或卡住超过 15 分钟：记下来，结束这个进程，继续下一次。同一个名字失败 2 次就跳过。
   - `.err` 不是空的，把内容（去掉路径里的用户名）写进结论。
3. 汇总（按名字前缀分组，`base` 是基准）：
   ```
   cd /d D:\dev\strata-lab\02-mmvq-q6k
   %E%\.venv\Scripts\python.exe %L%\mmvq_compare.py compare.tsv base=base-1.tsv base=base-2.tsv base=base-q6-1.tsv base=base-q6-2.tsv nosat=nosat-1.tsv nosat=nosat-2.tsv nosat=nosat-q6-1.tsv nosat=nosat-q6-2.tsv > compare.txt
   ```
   `compare.txt` 会列出每个文件开头的设备名、驱动和工作集，最后一行是「多少行、缺多少、校验值不一致的有多少行」。

## 3. 放进数据目录的内容
1. 第 2 节的 8 个 `.tsv`、`compare.tsv`、`compare.txt`。这些文件里只应有设备名、驱动版本和数字，提交前逐个打开确认。
2. `build.txt` 的脱敏副本：只留编译命令（路径换成 `<engine>`、`<build>`、`<tools>`）、耗时、`numstat` 的输出、两份源码和两个 exe 的大小与 SHA256。

## 4. 结论 `lab/results/02-mmvq-q6k.md`
按 README 的「结论文件的格式」写。额外包括：
1. 编译是否成功，`numstat` 的输出，各步耗时。
2. Q6_K 的表：5 种张量 × 1–6 列，列出 `base` 和 `nosat` 的 GB/s（`compare.tsv` 的中位数）和倍率 `nosat/base`。
3. 其他类型（IQ4_XS、Q4_K、Q5_K、IQ3_S、IQ4_NL、Q2_0）的表：每种类型、每个张量 × 1–6 列的 `base` GB/s。
4. 校验值：`compare.txt` 最后一行的原文；有 `DIFFER` 的行全部列出。
5. 每次运行的开始和结束时间。
6. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/02-mmvq-q6k.md` 和 `lab/results/02-mmvq-q6k/`，推送。

预计耗时：⚠️ 编译约 10–20 分钟（主要是 `iq_kernels.dp.cpp`），运行约 15–25 分钟（全量 4 次，每次约 2–4 分钟；Q6_K 4 次，每次约 1 分钟；
另加第一次运行的即时编译）。这是按 UHD 730 上的耗时推的，没在 140T 上测过。
