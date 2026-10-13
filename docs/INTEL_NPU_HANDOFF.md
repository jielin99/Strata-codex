# Intel 核显 / NPU 实验引继

更新时间：2026-10-14（Asia/Tokyo）。本文件是 Ubuntu 开发机继续工作的入口。

## 目标与边界

用户希望在 Windows 11 笔记本上运行 Strata，并探索让 CPU、Intel 核显、NPU
参与同一次模型推理，以改善实际延迟、吞吐或功耗。独立小模型或矩阵计算仅用于前置验证，
不能替代 Strata 的 NPU 协作补丁。

用户描述硬件为「U9 285 + 64GB 内存，T14 笔记本」。**完整 CPU 后缀、核显型号、NPU 型号和驱动尚未收到真机报告。**
此前讨论的 285H / Arc 140T / 13 TOPS 是条件假设，不能当作已检测事实。
用户已确认目标系统为 Windows 11，并选择先在笔记本上运行便携诊断包。

Ubuntu 是补丁开发环境。它的 CPU/GPU/NPU、系统版本、工具链和模型文件均待检查；
在 Ubuntu 上编译或测试成功，不能证明 Windows 笔记本部署成功。

## 分支基线与已完成内容

| 项目 | 状态 |
| --- | --- |
| 实验分支 | `local-v0.1.43.1-intel-npu` |
| 上游基础 | 正式 tag `v0.1.43.1` |
| 上游提交 | `a0116b2782a5b82622358c04a06496485d12b2d6` |
| `7b43cb49` | 新增可选 Windows 硬件采集与 OpenVINO 设备检查 |
| `c248ccda` | 修正 CMD 入口下的 UTF-8 处理，完善异常定位 |
| 本分支推理引擎 | 与正式 tag 相同，尚未加入 Intel/NPU 引擎补丁 |
| 其他候选分支补丁 | 没有迁入 ModelScope、Responses 或离线安装器修改 |

本分支新增工具在 [`tools/intel_npu/`](../tools/intel_npu/README.md)：

- `DIAGNOSE.bat`：Windows 双击入口。
- `collect_windows.ps1`：采集硬件、驱动、工具链是否存在；尝试启动 Python 检查。
- `probe_openvino.py`：跨平台 OpenVINO 设备枚举及可选固定 64×64 FP32 MatMul。
- `README.md`：诊断操作与结果范围。
- `.gitignore`：排除工具的报告、虚拟环境和 Python 缓存。

工具不会安装依赖、下载权重或修改持久系统配置。PowerShell 包装器对子进程设置 120 秒超时；
直接调用 Python 脚本没有内部超时。没有设置 AUTO/HETERO，按枚举设备逐个编译；
`EXECUTION_DEVICES` 检查目前核对设备类别，尚未严格区分同类别下不同设备索引。
数值容差为 `rtol=0.01, atol=0.005`，只适合小图连通性检查，不是量化或模型质量标准。

## 验证证据与缺口

已经检查：Python 语法编译、Windows 自带 PowerShell 运行、CMD 的 BAT 入口、含空格目录、
缺少 OpenVINO 时产生 JSON 错误报告并记录退出码 2、诊断 ZIP 的 CRC 和逐文件字节一致性。

原开发环境的 CIM 查询受沙箱限制，当前 Python 没有 OpenVINO；报告明确保存了错误。
**没有完成目标笔记本硬件检测、真实 NPU 计算、真实 Strata GPU 推理或 CPU/GPU/NPU 协作。**
没有跑本分支的引擎编译、全套回归、真实工具调用、长上下文、长期稳定性或性能测试。

便携包名为 `Strata-v0.1.43.1-intel-npu-diagnostics.zip`，只含四个运行/说明文件，
没有源码全量、模型或依赖。包和本机原始日志未纳入 Git；源码足够重建。
当时交付包 SHA256：`69213e5b41799e9e12d39a47cfdfb5fdcc052617811bd66b57ac7a56d7f9612f`。
重新打包可能因时间戳或换行产生不同档案哈希，须重新核验包内内容。

`npu_smoke_passed=true` 只能表示小图在报告的 NPU 上执行并通过数值检查，
不能据此宣布 Strata 接入 NPU。缺少依赖、编译失败、未发现 NPU、超时也要分别记录。

## 上游代码及候选实现入口

首先阅读根目录 `AGENTS.md`、[`docs/AI_SETUP.md`](AI_SETUP.md)、
[`docs/INTEL.md`](INTEL.md)、[`docs/INTEL_ARC.md`](INTEL_ARC.md) 和 [`docs/DETAILS.md`](DETAILS.md)。
部分 Intel 文档仍含旧版本说明；以选定 tag 的代码和实际检测结果为准。

正式 tag 中 Intel 路线是 `sycl/` 下的 GPU 后端；安装流程仍以 Linux/Docker 为主。
Windows 原生安装、核显可用内存查询、核显同步与缓存规划需要另外评估。
当前没有 Windows ML / Foundry Local 接入，也没有 NPU 推理调度实现。

先前检索发现以下上游候选，**尚未迁入本分支**。接续时重新核对状态、提交和适用平台，
避免将滚动 main 的变化全部搬入正式 tag 基线：

| 候选 | 用途与限制 |
| --- | --- |
| [PR #2079](https://github.com/Niko1221/Strata/pull/2079) | 原生 Windows SYCL 构建/安装。作者报告以 Arc Pro B70 独显验证，不能直接推广到核显 |
| [PR #2110](https://github.com/Niko1221/Strata/pull/2110) | 核显 `STRATA_WINDOW_SYNC`。作者报告 285H/Arc 140T、Linux、额外本地修复下 Coder IQ1_M 约 11.5–17.4 tok/s；不是我们的验证 |
| [PR #2114](https://github.com/Niko1221/Strata/pull/2114) | 核显可用内存查询、禁止提示词缓存借用、原生 Linux 启动入口 |
| [PR #2115](https://github.com/Niko1221/Strata/pull/2115) | 核显检测、RAM 预算与安装配置；依赖 #2114，Linux 实测不能替代 Windows 适配 |

代码检查入口：`sycl/CMakeLists.txt`、`sycl/setup_intel.py`、
`sycl/include/dpct/device.hpp` 的 `get_memory_info`、`sycl/src/core/verify.cpp` 的
`STRATA_WINDOW_SYNC`、`sycl/src/program/generate.cpp` 的提示词缓存借用和专家规划。
不要把 `usm_host_allocations` 能力直接等同于“设备是核显”；设备身份和共享内存语义须分别核对。

NPU 资料以官方文档为准：

- [OpenVINO NPU 支持范围](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/npu-device.html)
- [OpenVINO GenAI on NPU](https://docs.openvino.ai/2026/openvino-workflow-generative/inference-with-genai/inference-with-genai-on-npu.html)
- [Windows ML 执行提供程序](https://learn.microsoft.com/en-us/windows/ai/new-windows-ml/supported-execution-providers)

13 TOPS 是特定精度的峰值，不能直接与 Strata 的 IQ 量化算力或生成速度相加。
设备间共享物理内存也不保证共享张量零开销。需要测量量化转换、图编译、提交、同步、
访存和实际计算；设备利用率上升不能单独作为收益证据。

## Ubuntu 开发机盘点与上游补丁审查（2026-10-13）

开发机实测（`lscpu`、`lspci -nn`、`free -g`、驱动绑定读 `/sys/bus/pci/devices/0000:00:02.0/driver`）：

| 项目 | 结果 |
| --- | --- |
| 系统 | Ubuntu 24.04.5，内核 7.0.0-38 |
| CPU / 内存 | i3-13100（8 线程）/ 15 GiB，磁盘剩余 335 GiB |
| 核显 | UHD Graphics 730 `8086:4692`，当前绑定 **i915**（xe 模块已加载但未接管） |
| NPU | **没有**。`00:08.0 [8086:464f]` 是 GNA，不是 NPU；无 `/dev/accel` |
| 工具链 | 无 oneAPI（`icpx`/`sycl-ls`）、无 `cmake`、无 OpenVINO、无 numpy；sudo 需密码 |

结论：这台机器内存低于模型最低 32 GB，**不能做第 4 步真实 Strata 基线，也不能做任何 NPU 实测**。
装 oneAPI 后最多能编译 SYCL 引擎、在 UHD 730 上跑小型 parity 测试。`probe_openvino.py` 在此机因缺 numpy
退出码 2，与“缺依赖时报错”的设计一致。

上游 PR 已以只读引用取到本地 `refs/upstream-pr/<号>`（未合并、未推送）。四个 PR 都基于 `7695859a`
（正式 tag 基线 `a0116b27` 之前 33 个提交），截至取回时都未合入上游 main。各自单独 cherry-pick 到本分支均无冲突；
按 2114→2110→2115→2079 顺序叠加时，2079 与 2115 在 `sycl/setup_intel.py` 冲突。

| PR | 对 Windows 11 核显目标的适用性 |
| --- | --- |
| #2079 | 引擎侧 Windows 移植（文件读取改 `ReadFile`、CMake 的 `/fp:precise` `/Qmkl`、Pinned arena、`GlobalMemoryStatusEx`）是必需基础。但 setup 只认 `INTEL_ARC` 表里的独显 ID，引擎在 Windows 上**缺 `ext_intel_free_memory` 即退出 2**，核显会被直接拒绝 |
| #2110 | 只改 `verify.cpp` 一处，用 `host_unified_memory` 判核显后默认 `STRATA_WINDOW_SYNC=1`。与平台无关，可直接复用 |
| #2114 | 核显空闲内存回退只在 `__linux__` 下读 `/proc/meminfo`，Windows 需另写同义实现；禁止提示词借用一段与平台无关 |
| #2115 | 全部基于 Linux sysfs 和 `setvars.sh`，Windows 不可直接用，只能参考其 RAM 预算规则 |

待笔记本报告确认的关键事实：Windows Level Zero 下核显是否提供 `ext_intel_free_memory` 和 `ext_oneapi_graph`。
现有诊断包只做 OpenVINO 枚举，没有采这两项。

## 笔记本诊断报告（2026-10-13 23:24 采集）

来源：用户提供的 `20261013-232354/` 报告目录（`hardware.json` 等五个文件，未纳入 Git）。`errors` 为空。

| 项目 | 报告内容 |
| --- | --- |
| CPU | Intel Core Ultra 9 285H，16 核 16 线程 |
| 内存 | 63.5 GiB（2 × 32 GiB，6400 MT/s），采集时空闲 53.3 GiB |
| 系统 | Windows 11 专业版，版本 10.0.26300（Build 26300） |
| 核显 | Intel Arc 140T GPU（名称显示 32GB），驱动 32.0.101.8826 |
| NPU | Intel AI Boost，驱动 32.0.100.4778（驱动日期 2026-04-28），状态 OK |
| 工具链 | 有 `python`/`py`；无 `sycl-ls`、`icx`、`cmake`、`ninja`、`cl`，无 oneAPI `setvars` |
| OpenVINO 检查（23:24） | 缺 numpy，Python 退出码 2，设备列表为空 |
| OpenVINO 复查（23:39） | 独立 venv：OpenVINO 2026.4.1、numpy 2.5.4。枚举到 CPU、GPU（`Arc 140T (iGPU)`）、NPU（`Intel AI Boost`） |

`smoke.json`（64×64 FP32 MatMul）：

| 设备 | 编译 | 首次推理 | 最大绝对误差 | 结果 |
| --- | --- | --- | --- | --- |
| CPU | 17.5 ms | 0.784 ms | 2.8e-08 | 通过 |
| GPU.0 | 1940.9 ms | 0.522 ms | 4.0e-05 | 通过 |
| NPU | 579.5 ms | 未执行 | — | 失败：`Unexpected execution device: ['N', 'P', 'U']` |

NPU 失败是 `probe_openvino.py` 的缺陷，不是设备问题：NPU 插件的 `EXECUTION_DEVICES` 返回字符串 `"NPU"`，
脚本逐字符遍历后误判。已修正为字符串先包成列表；回落到 CPU 或空列表仍判失败。

修正后笔记本重跑 `smoke2.json`（23:47，同一 venv）：

| 设备 | 编译 | 首次推理 | 最大绝对误差 | 执行设备 | 结果 |
| --- | --- | --- | --- | --- | --- |
| CPU | 13.9 ms | 0.420 ms | 2.8e-08 | CPU | 通过 |
| GPU | 64.5 ms | 0.563 ms | 4.0e-05 | GPU.0 | 通过 |
| NPU | 17.8 ms | 536.9 ms | 4.9e-05 | NPU | 通过 |

`npu_smoke_passed=true`：小图确实在 NPU 上执行且数值正确。这**只证明 NPU 可用**，不是 Strata 接入 NPU。
每个设备只测了一次首次推理，没有预热后的重复测量，这些毫秒数不能用作性能数据。
GPU/NPU 编译时间比第一次（1940.9 / 579.5 ms）短很多，推测是驱动或 OpenVINO 的编译缓存，未核实。
NPU 首次推理 537 ms 远高于 CPU/GPU，推测含首次提交开销；稳态开销需另行重复测量。

报告没有采 PCI 设备 ID。285H 的 Arc 140T 应为 `8086:7d51`（PR #2115 的表），这是推断，未从报告核实。
核显硬件与 PR #2110/#2114 作者的机器同型（285H/Arc 140T），但作者在 Linux 上测，Windows 驱动下的
SYCL 能力（`ext_intel_free_memory`、`ext_oneapi_graph`）仍未知。

按 PR #2115 的核显内存规则（shard 1 + 20 GiB）粗算 63.5 GiB：Coder IQ1_M 约 47.6、Q2_0 约 55.0、
IQ2_XS 约 56.5 GiB 可装下；IQ3_XXS 约 63.8 GiB 装不下。该规则来自作者 Linux 实测，Windows 上未验证。

## Ubuntu 接续步骤

1. 阅读本文件，检查当前改动和开发机硬件、驱动、oneAPI/OpenVINO 工具链，保留版本清单。
2. 接收用户笔记本的 `reports`，确认完整 CPU 后缀、GPU、NPU 和 Windows/驱动版本。
   等待报告期间可以检查、编译、设计接口；没有目标硬件时按“未实机验证”报告。
3. 审查上游候选补丁，选择最小可移植改动。Windows 支持、核显资源规划、NPU 后端分开提交，
   优先复用现有 SYCL 实现。不要直接合并上游 main，也不要绕过内存/执行设备保护来强行跑通。
4. 先建立真实 Strata GPU 基线：固定模型与文件哈希、上下文、提示词、生成长度和推测设置。
   短上下文起步，验证输出和连续多轮，再记录首字延迟、prefill/decode、峰值内存与异常。
5. NPU 首先跑设备检查，再使用来自实际模型的代表性专家/稠密计算验证数值及端到端开销。
   IQ 权重转换、动态路由和静态计算图兼容性要明确设计；合成 MatMul 不足以决定能否集成。
6. 在测量基础上选择一项 NPU 分工原型，例如提示词成批计算、专家并行或草稿计算。
   这些只是候选，不是已验证方案。新功能显式 opt-in，可关闭；失败路径不得伪报 NPU 成功。
7. 同机、同日、同配置对比开/关；分开记录冷编译和热运行，防止前缀缓存复用污染结果。
   如果增加同步后变慢，保留结果并调整任务粒度。性能变化和数值/质量变化分开报告。
8. 在 Windows 笔记本完成编译或部署验收，验证多轮、取消、恢复和长期稳定性。
   GPU/NPU 实机、模型输出、真实工具调用、协议 Mock 测试必须分开表述。

可在现有 OpenVINO 环境用同一 Python 检查脚本；先枚举，再执行：

```bash
mkdir -p logs/intel-npu
python tools/intel_npu/probe_openvino.py --output logs/intel-npu/devices.json
timeout 120s python tools/intel_npu/probe_openvino.py --smoke --output logs/intel-npu/smoke.json
```

缺少 NPU 时退出码 2 是诊断结果，不是通用 CPU 测试失败。无 OpenVINO 环境时先确认
Python、插件和驱动兼容，使用项目独立环境；不要根据这份交接盲目升级系统驱动或下载完整权重。

## 协作约定与建议分工

用户授权在 Ubuntu 开发机借助其他 agents 协作。可以把工作拆成：
Windows SYCL/核显补丁审查、NPU 算子与调度原型、数值与性能验收；约定文件归属，
避免多人同时改同一文件，最后由一个 agent 汇总集成和验证。
这些子任务尚未派发，没有其他 agent 已完成工作的证据。

始终用中文与用户交流。新工作继续基于本实验分支，保留上游正式 tag 历史。
上游仅用于读取；推送明确指定我们仓库的远端，避免向上游推送或创建上游 PR。
`main` 不加入本地功能补丁，已有发布 tag 不移动。硬件报告、权重、虚拟环境、
密钥和本机维护日志不提交到公开 Git。实验分支上传不代表正式发布或验证通过。

给接续 agent 的启动提示：

> 请阅读 docs/INTEL_NPU_HANDOFF.md 并继续 local-v0.1.43.1-intel-npu。
> 目标是在 Windows 11 Intel 笔记本上让 Strata 利用核显，并开发可选 NPU 协作路径。
> 先核对开发机和笔记本诊断报告，审查已有上游 Windows/核显候选补丁；允许分派其他 agents
> 协作。保留正式 tag 基线，按上述步骤完成真实基线、NPU 数值和开销测量后再集成。
> 不把诊断脚本或 Mock 结果当作真实模型成功，不向上游推送。
