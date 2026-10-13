# Intel 核显 / NPU 第一轮诊断

实验分支：`local-v0.1.43.1-intel-npu`。
基础：上游正式 tag `v0.1.43.1`，commit `a0116b2782a5b82622358c04a06496485d12b2d6`。

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

## 接下来依据硬件报告进行

先验证 Windows 的 Intel GPU 构建与核显内存规划，再跑真实 Strata 基线。
NPU 并行实验另行评估计算图、量化兼容、调度及同步开销，保留显式关闭入口。
上游 Windows SYCL PR #2079、核显同步 PR #2110、内存/启动 PR #2114 与安装 PR #2115
仅作为候选实现来源，尚未迁入本分支。

此包使用标准 PowerShell 和 Python；未验证 Windows ML 或 Foundry Local。
