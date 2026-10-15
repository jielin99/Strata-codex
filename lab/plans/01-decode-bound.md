# 01：测出生成速度卡在哪里（第 1 阶段，数据采集）

先读 `lab/README.md`，遵守共通规则、提交范围和推送步骤。全部用 CMD。
- 原始记录写到 `D:\dev\strata-lab\01-decode-bound\`（下文叫「原始目录」）。
- 结论写到 `lab/results/01-decode-bound.md`；可公开的数据文件放在 `lab/results/01-decode-bound/`（下文叫「数据目录」）。

**目的**：给开发机提供三样东西：每个生成窗口要读多少字节（需要张量清单和运行时文件）、这台机器实测的读带宽上限、生成阶段各部分的耗时。
这一份只采集数据，不做分析。不改引擎代码，不改 `strata-iq3_xxs.json`。

## 0. 开始前
1. 确认 `D:\dev\Strata-lab140t` 在 `lab/140t` 上，并已同步到最新（按 README 推送步骤的第 2 步）。
2. 8080 被占用或已有 `strata.exe` 在运行时，停下来问用户。
3. 请用户确认一次：插着电源、电源模式「最佳性能」、跑的过程中不使用电脑。确认后中间不再问。
4. 在原始目录记录：
   - 日期时间、开机以来的时间（`net statistics workstation` 的「统计数据开始于」一行）。
   - `git -C D:\dev\Strata-intel-npu rev-parse HEAD`。
   - `build-sycl-win\strata.exe` 的大小、修改时间和 SHA256。
   - 电源：Windows 11 有两层，**以第二层为准**。
     - 电源计划：`powercfg /getactivescheme`。现代待机的笔记本通常只有「平衡」，**不代表**设置里的电源模式。
     - 电源模式（设置 → 系统 → 电源和电池 → 电源模式）：`powercfg /getactiveoverlayscheme`；命令不存在时改用
       `reg query HKLM\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes /v ActiveOverlayAcPowerScheme`。
       对照：`ded574b5-45a0-4f42-8737-46345c09c238` = 最佳性能，`961cc777-2547-4f9d-8174-7d86181b8a7a` = 最佳能效，
       全零或没有这个值 = 平衡。查不出来就写「未能读取」，**不要**用电源计划的名字代替。
   - 可用物理内存。
   - GPU 驱动版本（PowerShell：`Get-CimInstance Win32_VideoController | Select Name,DriverVersion`）。

## 1. 配置和模型文件清单
1. 读 `D:\dev\Strata-intel-npu\strata-iq3_xxs.json`。把它的 `args`、`env` 等字段写成脱敏后的副本 `数据目录\config.json`：
   - 所有绝对路径换成占位符：模型所在目录写 `<model-dir>`，仓库目录写 `<repo>`，其他目录写 `<path-N>`。
   - `--api-key` 的值删掉。
   - 占位符和真实路径的对照只写在原始目录里。
2. 对 `args` 里每个指向已存在文件或目录的参数，在 `数据目录\files.tsv` 里记录：参数名、占位符、类型（文件或目录）、文件名、大小。
   - 是目录的话，列出里面的文件（相对路径和大小），最多 500 项，超过的只写总数和总大小。
3. 张量清单：对参数里引用的所有 `.gguf` 文件（全部分片，还有 MTP 用的 gguf，如果有的话）运行
   ```
   D:\dev\Strata-intel-npu\.venv\Scripts\python.exe D:\dev\Strata-lab140t\lab\tools\gguf_tensors.py <数据目录>\tensors.tsv <每个 gguf 文件或所在目录>
   ```
   会生成 `tensors.tsv` 和 `tensors.meta.json`。如果 `tensors.tsv` 超过 200 KB，就按 gguf 文件拆成 `tensors-<序号>.tsv`，每个都不超过 200 KB。
4. 运行时的小索引文件：在第 2 步列出的目录里，把不超过 200 KB 的 `.txt` 和 `.json` 文件（例如 MTP 目录下的 `dense.txt`）复制到 `数据目录\rt\`，保持相对路径。
   复制前逐个打开检查，里面有绝对路径的就换成占位符，并在结论里注明。

## 2. 读带宽探针
1. 编译（新目录，在 `.gitignore` 的 `build*/` 范围内）：
   ```
   set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
   call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
   mkdir D:\dev\Strata-intel-npu\build-lab-tools
   icx -fsycl /O2 /EHsc -Wno-deprecated-declarations D:\dev\Strata-lab140t\lab\tools\bw_probe.cpp -o D:\dev\Strata-intel-npu\build-lab-tools\bw_probe.exe
   ```
   编译失败就把报错原文写进结论，跳过这一节，继续第 3 节。
2. 运行两次：第 3 节开始前一次，第 3 节结束后一次。两次都要在 `strata.exe` 没有运行时进行。
   - 环境变量设成和配置文件一样：`ONEAPI_DEVICE_SELECTOR=level_zero:gpu`、`UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1`。
   ```
   D:\dev\Strata-intel-npu\build-lab-tools\bw_probe.exe 2048 20 device,host
   ```
   输出原样保存到原始目录的 `bw-before.txt` 和 `bw-after.txt`，再复制一份到数据目录（输出里只有设备名、驱动版本和数字）。

## 3. 生成阶段的分段计时（3 种开关，交替跑 6 段）
驱动脚本以 `D:\dev\strata-lab\adapter-20261015-1013\drive.py` 为底子改，放进原始目录，改了什么写进结论。

| 顺序 | 段 | 环境变量 |
|---|---|---|
| 1 | `1-N` | 不加计时开关 |
| 2 | `2-T` | `STRATA_DECODE_TIMING=1` |
| 3 | `3-P` | `STRATA_DECODE_TIMING=1`、`STRATA_VERIFY_PROFILE=1` |
| 4 | `4-P` | 同 3-P |
| 5 | `5-T` | 同 2-T |
| 6 | `6-N` | 同 1-N |

每段：
1. 先从环境里**删除**这些变量：`STRATA_DECODE_TIMING`、`STRATA_PREFILL_TIMING`、`STRATA_VERIFY_PROFILE`、`STRATA_VERIFY_EAGER`、`STRATA_SH_STREAM`、`STRATA_PREFILL_SYNC`、`STRATA_PF_STEP_SYNC`、`SYCL_UR_USE_LEVEL_ZERO_V2`、`UR_L0_USE_COPY_ENGINE`、`SYCL_UR_TRACE`，再按上表设置。
2. 记下 `strata-iq3_xxs.log` 当前的字节长度。
3. `sb.start_server(<配置>, 8080, None, <原始目录>\<段>\server.log)`，再 `sb.wait_ready(..., 1800)`。
4. 执行 `s.warm_up()`，然后 `s.run_chat()`（3 个短问题各 3 次，共 9 个请求）。**不跑 4K。**
5. 把 `s.out` 存成 `<原始目录>\<段>\bench.json`。
6. 结束服务进程树，等到 `strata.exe` 全部退出后再等 60 秒；把引擎日志从第 2 步的位置到末尾，复制成 `<原始目录>\<段>\engine.log`。

卡住或失败的处理：记下来，继续下一段；同一段失败 3 次就跳过这一段。新出现的 dmp 复制到原始目录。

## 4. 放进数据目录的内容（都是数字和引擎状态，提交前逐行检查）
1. `timing.tsv`：每段每个请求一行。列：段、请求序号、问题编号、生成 token 数、生成 tok/s、首 token 时间、草稿接受数/提供数（bench.json 里有的就填，没有就留空）。
2. `<段>-decode.txt`：这一段 engine.log 里所有以 `strata decode` 开头的行，原文，每行前面加上它在 engine.log 里的行号。
3. `startup.txt`：从 `1-N` 和 `3-P` 两段的 engine.log 里，取引擎启动到第一个请求之间，所有以 `strata verify`、`strata mtp`、`strata generate`、`strata expert`、`strata cache`、`strata kv` 开头的行，同样加行号。
   - 逐行检查：带路径的行，把路径换成占位符。
   - 这些行里应该会有 `the N-token window graph has K nodes`、`window up to N tokens` 这类内容，开发机要用它们判断走的是哪种图。
4. `bw-before.txt`、`bw-after.txt`。

## 5. 结论 `lab/results/01-decode-bound.md`
按 README 的「结论文件的格式」写。额外包括：
1. 6 段的总表：每段 q1/q2/q3 的生成 tok/s 中位数，9 个请求的生成 tok/s 中位数和最小–最大。
2. 第 2 节两次探针的 device / host 中位数。
3. 数据目录里每个文件的一句话说明。
4. **不做分析，不写原因推断**，分析由开发机来做。

然后按 README 做提交前自查（关键字扫描要覆盖数据目录的每个文件），提交 `lab/results/01-decode-bound.md` 和 `lab/results/01-decode-bound/`，推送。

预计耗时：⚠️ 约 1 小时（6 段，每段约 1.5 分钟加载加 9 个请求），加上编译和清单整理的时间。
