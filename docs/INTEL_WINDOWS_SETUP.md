# Windows 11 Intel 核显：安装、编译、启动手顺

实验分支 `local-v0.1.43.1-intel-npu`。本文是在笔记本上从零开始的完整操作顺序；
背景、取证和决策记录见[实验引继文档](INTEL_NPU_HANDOFF.md)。

每一步标注了验证状态：

- ✅ 已在目标笔记本上实际跑通（2026-10-14）
- ⚠️ 只在 Ubuntu 开发机上验证过，或者是根据代码推断
- ⬜ 还没有人跑过

## 目标机器

| 项目 | 内容 |
| --- | --- |
| 机型 | ThinkPad T14，Core Ultra 9 285H，内存 64 GB（2 × 32 GB，6400 MT/s） |
| 核显 | Arc 140T（PCI `8086:7d51`），驱动 32.0.101.8826 |
| NPU | Intel AI Boost，驱动 32.0.100.4778 |
| 系统 | Windows 11 专业版 Build 26300 |

其他 Intel 核显或驱动版本没有试过。

## 0. 准备

- C 盘至少留 20 GB 给工具，模型另算（IQ3_XXS 约 76 GB，Coder IQ1_M 约 58 GB）。
- 开发目录统一放在 `D:\dev`。
- 下面的命令都在 **CMD** 里执行，不要用 PowerShell。PowerShell 不认 `cd /d`，
  而且 Windows PowerShell 5 的 `>` 重定向会把日志写成 UTF-16。
  在 PowerShell 窗口里输入 `cmd` 回车，就切到 CMD 了。

## 1. 安装工具（只需一次）

装的顺序要对：**先装 VS 生成工具，再装 oneAPI**，否则 oneAPI 可能识别不到 VS。

### 1.1 Visual Studio 2022 生成工具（C++） ✅

用管理员身份打开 CMD：

```bat
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--passive --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

也可以从微软官网下载 “Build Tools for Visual Studio 2022”，在图形界面里勾选「使用 C++ 的桌面开发」。
`build_windows.bat` 会检查 `Microsoft.VisualStudio.Component.VC.Tools.x86.x64` 这个组件。
笔记本上装好的版本是 17.14.41，MSVC 14.44.35207。

确认装上了：

```bat
"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -all -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
```

应输出 `C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools`。

### 1.2 Intel oneAPI：DPC++/C++ 编译器和 oneMKL ✅

版本要求 2025.3 或更新。笔记本上装的是 2026.1.1，装在默认位置 `C:\Program Files (x86)\Intel\oneAPI`。二选一：

- **独立安装包**：在 Intel 的[独立工具页](https://www.intel.com/content/www/us/en/docs/oneapi-toolkit/installation-guide-windows/latest/install-standalone-tools.html)只下载两个，
  Compilers 下的 **Intel® oneAPI DPC++/C++ Compiler** 和 Libraries 下的 **Intel® oneAPI Math Kernel Library (oneMKL)**。
  系统选 Windows，两个尽量选同一个版本号，点 “Continue as a Guest” 下载后运行，安装位置保持默认。
- **winget 装完整工具包**，体积更大：`winget install --id Intel.OneAPI.Toolkit -e`

不要用 pip 装 oneAPI：pip 上只有运行时，没有编译器。oneTBB 不用单独装，编译器安装包会一起装上（笔记本上已确认）。

### 1.3 CMake、Ninja、Git ✅

```bat
winget install --id Kitware.CMake -e
winget install --id Ninja-build.Ninja -e
winget install --id Git.Git -e
```

CMake 要求 ≥ 3.24。笔记本上的版本：CMake 4.4.4、Ninja 1.13.2、Git 2.52.0。

### 1.4 Python ✅

要 Python 3.10 以上的 64 位版本。没有的话，`START-HERE.bat` 第一次运行时会为当前用户装 Python 3.12。

### 1.5 记住 VS 的路径 ✅

笔记本上 `setvars.bat` 自己找不到装在标准位置的 BuildTools（原因没查明），要手动指定。存成用户环境变量，以后每个新窗口就不用再设：

```bat
setx VS2022INSTALLDIR "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
```

`setx` 只对之后新开的窗口生效。

## 2. 每次开新窗口先做 ✅

编译和启动都要用到 oneAPI 的环境，**每个新开的 CMD 窗口都先执行**：

```bat
set "VS2022INSTALLDIR=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
call "C:\Program Files (x86)\Intel\oneAPI\setvars.bat" intel64 vs2022
```

正常时会输出 `Visual Studio version 17.14.41 environment configured.` 和 `:: oneAPI environment initialized ::`，
**不应该**出现 “Visual Studio was not found”。

第一次装完后检查一遍：

```bat
icx --version
sycl-ls
cmake --version
ninja --version
git --version
where cl
```

最要紧的是 `sycl-ls` 要有这一行：

```text
[level_zero:gpu][level_zero:0] Intel(R) oneAPI Unified Runtime over Level-Zero, Intel(R) Arc(TM) 140T GPU (32GB) ...
```

`where cl` 要能找到 `...\BuildTools\VC\Tools\MSVC\<版本>\bin\Hostx64\x64\cl.exe`。

## 3. 取代码 ✅

```bat
if not exist D:\dev mkdir D:\dev
git clone -b local-v0.1.43.1-intel-npu https://github.com/jielin99/Strata-codex.git D:\dev\Strata-intel-npu
```

如果出现 `Connection was reset` 或 `RPC failed; curl 28`，那是网络问题（仓库是公开的），重试就行。
还不行可以浅克隆（加 `--depth 1 --single-branch`），或者让开发机做一个 `git bundle` 拷过来。

以后更新代码：

```bat
cd /d D:\dev\Strata-intel-npu
git pull
```

## 4. SYCL 能力检查（可选，约 1 分钟） ✅

用来确认驱动和运行时没问题，换驱动或 oneAPI 之后建议重跑一次：

```bat
cd /d D:\dev\Strata-intel-npu\tools\intel_npu
PROBE_SYCL.bat
```

报告写在 `tools\intel_npu\reports\sycl-<日期>-<时间>\`。在 Arc 140T 上，Level Zero 那一项的结果应该是：

| 字段 | 期望值 |
| --- | --- |
| `ext_oneapi_limited_graph` | `true`（完整的 `ext_oneapi_graph` 是 `false`，正常） |
| `graph_record_replay` | `"ok"` |
| `sub_group_32_kernel` | `"ok"` |
| `fp16` / `fp64` | `true` / `true` |
| `max_mem_alloc_size` | 默认 4 GiB；`relaxed.json` 里是 33.58 GiB |

## 5. 编译引擎 ✅

在已经执行过第 2 步的窗口里：

```bat
cd /d D:\dev\Strata-intel-npu
sycl\tools\build_windows.bat > build-win.log 2>&1
build-sycl-win\strata.exe --list-devices
```

- 第一次完整编译 211 个目标，按日志时间戳估算约 10 分钟；以后只重编改过的文件。
- 编译时窗口没有输出是正常的，所有输出都在 `build-win.log` 里。
- 日志里会有一万多条 `warning:`，是自动转换代码（dpct）的常见警告，不用管。
  判断成败只看两点：搜不到 `error:`，最后一行是 `Linking CXX executable ...`。
  可以用 `findstr /c:"error:" build-win.log` 检查，没有输出就是没有错误。
- `--list-devices` 里 Level Zero 那一项要有 `"limited_graph_supported":true`。
  没有这个字段，说明 exe 还是旧的，先 `git pull` 再重新编译。
  列表里还会有一项 `"driver":"opencl"`，是同一块核显的 OpenCL 入口，可以忽略。

## 6. 确认模型文件 ⚠️

Strata 只支持 ISTA-DASLab 发布的 GSQ-RCO 版本（Q2_0、IQ2_XS、IQ3_XXS、IQ3_S，以及 Coder 的 IQ1_M），
还有 Unsloth 的 UD-Q4_K_XL 和 UD-IQ4_XS。**Unsloth 的 `UD-IQ3_XXS` 不能用**（`setup.py` 的 `SUPPORTED_GGUFS`）。

```bat
dir /b "<模型目录>\*.gguf"
```

- 文件名里有 `UD-IQ3_XXS` 的不能用。
- 分片 `...-00001-of-0000N.gguf` 到 `...-0000N-of-0000N.gguf` 必须全部齐全。

按 64 GB 内存估算（PR #2115 的核显内存规则：shard 1 + 20 GiB，来自作者在 Linux 上的实测，Windows 上未验证）：

| 模型 | 下载大小 | 核显需要内存 | 64 GB 机器 |
| --- | --- | --- | --- |
| Coder IQ1_M | 58.4 GB | 约 47.6 GiB | 放得下，最稳妥 |
| Q2_0 | 66.4 GB | 约 55.0 GiB | 放得下 |
| IQ2_XS | 68.0 GB | 约 56.5 GiB | 放得下 |
| IQ3_XXS | 75.8 GB | 约 63.8 GiB | **超出**，只适合试跑（作者实测只剩 3–4 GiB，没跑好） |

实测（2026-10-14，ThinkPad T14 / Arc 140T / 63.5 GiB）：IQ3_XXS 32K 能跑，内存峰值约 57 GB，但要按第 7 步末尾改配置。

## 7. 安装并第一次启动 ⚠️

2026-10-14 用 IQ3_XXS、32K 跑通，但 setup 生成的配置要手改（见本节末尾）。

启动前关掉占内存的程序，打开任务管理器的「性能」页看内存。然后在执行过第 2 步的窗口里：

```bat
cd /d D:\dev\Strata-intel-npu
START-HERE.bat --backend sycl --family qwen --model IQ3_XXS --gguf-dir "<模型目录>" --context 32768 --data-dir D:\dev\Strata-data
```

| 参数 | 作用 |
| --- | --- |
| `--backend sycl` | 走 Intel SYCL 引擎（PR #2079 的原生 Windows 路径） |
| `--family` / `--model` | 换别的模型时一起改，比如 Coder 用 `--family coder --model IQ1_M` |
| `--gguf-dir` | 直接用已经下载好的模型文件，不会重新下载模型 |
| `--context 32768` | 实测用的上下文。不写的话，setup 会按核显报告的 33.6 GB“显存”把上下文默认设成 131072。上下文对内存影响小（int8 KV），大头是约 40 GiB 的专家 |
| `--data-dir` | 配置和小文件放这里。setup 还会下载 Python 包和 llama.cpp 源码 |

预期会这样（推断）：

- 第一次运行会在仓库里创建 `.venv`，并安装 Python 包。
- 第一次启动引擎要现场编译内核（JIT），可能需要几分钟。
- 启动成功后会打开浏览器聊天页，API 在 `http://127.0.0.1:8080`。

出问题时：

- 内存接近 100%，系统明显变卡：在 CMD 窗口按 `Ctrl+C` 停止。
- 报错退出：保留窗口的全部输出，再看仓库根目录下的引擎日志 `strata-<模型>.log`（`setup.py` 配置里的 `log` 字段）。

已知限制：

- 核显在这里会被当成一块有 33.6 GB 显存的独显来配置。#2115 那套核显专用配置（`--stream-experts`、不用 KV 流式等）没有迁入，
  所以内存占用和速度不能直接跟 #2110 作者在 Linux 上的数字（Coder IQ1_M 约 11.5–17.4 tok/s）对比。
- 专家缓存按驱动报告的 33.58 GiB 规划，这个数是 Windows 给核显的共享内存预算，不是实时空闲量。
  其他程序占用大量内存时可能会超额。
- 不要用 `--host 0.0.0.0` 把服务暴露到局域网，除非同时设了 `--api-key`。

**setup 生成的配置要改一处，另一处不要动**（实测，2026-10-14）。打开仓库根目录的 `strata-iq3_xxs.json`：

| 项 | setup 写的 | 改成 | 原因 |
| --- | --- | --- | --- |
| `"--prefill"` | `"4096"` | `"512"` | 4096 时提示词缓冲区放不下，引擎崩溃（`sycl9.dll` 0xc0000005）或内存 100% 后 `DEVICE_LOST` |
| `"env"` 里的 `STRATA_VERIFY_NO_HOST` | `"1"` | 不要动 | 改成 `"0"`（让 CPU 从 SSD 算放不下的专家）能省内存，但输出全是 `!!!!` |

不要靠调大 `--vram-reserve-mib` 省内存：核显上它只把专家从缓存挪到镜像，总量不变。
`--prefill 1024`、`2048` 没有试过。

实测速度（同一会话热运行 4 次）：生成 4.7–7.2 tok/s，提示词 7.1–27.5 tok/s，内存峰值约 57 GB。

## 8. 以后启动 ⬜

安装成功后，setup 会在仓库根目录写一个 `run-<模型名小写>.bat`（例如 `run-iq3_xxs.bat`）。
以后启动时先执行第 2 步，再运行它即可；也可以再次运行 `START-HERE.bat`。

## 9. 更新代码后

```bat
cd /d D:\dev\Strata-intel-npu
git pull
sycl\tools\build_windows.bat > build-win.log 2>&1
build-sycl-win\strata.exe --list-devices
```

setup 只在 `strata.exe` 不存在时才会编译（`ensure_windows_engine`），不会发现 exe 已经过时。
所以**拉取新代码后要自己重新编译**。

## 10. 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| `setvars.bat` 提示 “Visual Studio was not found” | 先 `set "VS2022INSTALLDIR=..."` 再执行 `setvars`，或者用 1.5 的 `setx` 永久设置 |
| `where cl` 找不到 | 同上；或者 VS 没装 C++ 组件，用 1.1 的 `vswhere` 命令检查 |
| PowerShell 报 `找不到接受实际参数...的位置形式参数` | 在 PowerShell 里用了 CMD 的 `cd /d`。先输入 `cmd` 切过去 |
| `git clone` 报 `Connection was reset` | 网络问题，重试，或者见第 3 步 |
| 编译输出满屏 warning | 正常，只看有没有 `error:` |
| 引擎报 `command graphs are unavailable (ext_oneapi_graph)` | exe 是旧的。新版本的提示是 `ext_oneapi_limited_graph`。`git pull` 后重新编译 |
| 引擎报 `ExpertCache: cudaMalloc(...) failed` | 可能没设 `UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1`。新版本 setup 生成的配置里已经带上了 |
| `PROBE_SYCL.bat` 说找不到 `icx` 或 `cl` | 先执行第 2 步 |
| 输出全是 `!!!!!` | `STRATA_VERIFY_NO_HOST` 被改成了 `0`。改回 `1`，见第 7 步末尾 |
| 启动时引擎退出，日志最后是 `do not fit ... trying a 3072-token chunk` | 提示词缓冲区放不下。`--prefill` 改成 `512` |
| 运行测试 exe 时反复提示“程序被阻止” | Windows 智能应用控制拦截未签名程序。关闭后才能运行。注意：旧版 Windows 关闭后不能再打开（除非重装），新版本是否仍然如此未确认 |

## 验证状态汇总（2026-10-14）

- **已在笔记本上跑通**：第 1–5 步。工具安装和检查；SYCL 能力检查第二版（受限图、录制重放、sub-group 32 都正常）；
  引擎完整编译 211/211、0 个错误；改动后增量编译通过；`--list-devices` 显示 `limited_graph_supported:true`。
- **只在开发机上验证过**：setup 相关的测试（`tools/test_setup_sycl.py` 36 项通过）。
- **已在笔记本上跑通（手改配置后）**：第 7 步，IQ3_XXS 32K 加载、4 次推理输出正常，速度和内存见第 7 步末尾。
- **还没验证**：setup 不手改配置就能用；第 8 步的 `run-*.bat` 重启；长时间稳定性；首字延迟；`--prefill` 512 以外的取值；
  其他模型。NPU 还没有接入 Strata，本文不涉及 NPU。
