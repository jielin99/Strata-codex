# Intel 核显 / NPU 第一轮诊断

实验分支：`local-v0.1.43.1-intel-npu`。
基础：上游正式 tag `v0.1.43.1`，commit `a0116b2782a5b82622358c04a06496485d12b2d6`。

Ubuntu 开发机继续开发请先阅读[实验引继文档](../../docs/INTEL_NPU_HANDOFF.md)。

## 在 Windows 11 笔记本运行

1. 解压整个诊断包到可写目录，如 `D:\AI\Strata-Intel-Diagnostics`。
2. 双击 `DIAGNOSE.bat`，普通用户即可；等待窗口提示完成。
3. 把生成的 `reports` 中本次时间目录里的全部报告返回给 Codex，包含硬件信息、OpenVINO 结果和错误记录。

脚本读取 CPU、内存、Windows 版本、GPU/NPU 驱动和工具链是否存在。
没有采集电脑名、用户名、序列号或网络地址；运行时错误文字可能包含本机文件路径，分享前可查看。
GPU 的共享内存容量不能用 Win32_VideoController 的 AdapterRAM 可靠表示，因此没有把该字段当作可用显存。

若 Python 环境已经有 OpenVINO 和 NumPy，会分别指定枚举到的 CPU/GPU/NPU，
执行一个固定 64×64 的矩阵乘法，并验证执行设备和数值结果。没有使用 AUTO/HETERO 回退。
首次调用可能触发驱动编译；诊断子进程超过 120 秒会被停止，超时记录保存在报告中。
工具不会安装软件、下载模型或修改系统设置。
BAT 的 ExecutionPolicy Bypass 只作用于本次 PowerShell 进程，没有更改持久策略。

如果缺少 Python / OpenVINO，先返回已有报告。缺少依赖不表示硬件不支持 NPU。
已有特定 Python 环境时，在 CMD 中运行：

```cmd
powershell.exe -NoProfile -ExecutionPolicy Bypass -File collect_windows.ps1 -PythonExe "D:\AI\your-env\Scripts\python.exe"
```

## 结果范围

- `npu_enumerated=true`：OpenVINO 发现 NPU。
- `npu_smoke_passed=true`：合成矩阵图在报告的 NPU 上执行，且通过宽容差数值比较。
- 编译和首次推理时间只用于排查启动问题，不作为 Strata 性能指标。
- 本工具尚未接入 Strata 推理，不证明真实模型、MoE 专家、量化格式或多设备协作成功。

## SYCL 能力检查（需要 oneAPI 与 VS 2022 C++ 生成工具）

`PROBE_SYCL.bat` 用 `icx` 编译 `probe_sycl.cpp`，再分三种环境各跑一次：

| 报告 | 环境变量 |
| --- | --- |
| `default.json` | 不加 |
| `sysman.json` | `ZES_ENABLE_SYSMAN=1`（PR #2079 的安装流程会设置） |
| `relaxed.json` | 再加 `UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS=1`（`strata-sycl-native.sh` 会设置） |

每个设备记录：名称、后端、PCI 设备 ID、`host_unified_memory`、总内存、单次分配上限、
sub-group 宽度，原生 Windows 引擎启动时要求的 `ext_intel_free_memory` 与 `ext_oneapi_graph`，
以及引擎内核要用的 fp16/fp64。每块 GPU 跑一个 32 宽 sub-group 的小内核，核对结果。
不做大块内存分配，专家缓存能否一次分配成功由引擎自己检验。

报告在 `reports\sycl-<日期>-<时间>`，同时保存 `icx --version`、`sycl-ls` 和编译输出。
找不到 `icx` 时脚本会调用 oneAPI 的 `setvars.bat`；VS 生成工具在默认位置时自动设置 `VS2022INSTALLDIR`。

## 接下来依据硬件报告进行

先验证 Windows 的 Intel GPU 构建与核显内存规划，再跑真实 Strata 基线。
NPU 并行实验另行评估计算图、量化兼容、调度及同步开销，保留显式关闭入口。
上游 PR #2114、#2110、#2079 已迁入本分支（保留原作者，`cherry-pick -x`）；
Linux 安装用的 PR #2115 未迁入。

此包使用标准 PowerShell 和 Python；未验证 Windows ML 或 Foundry Local。
