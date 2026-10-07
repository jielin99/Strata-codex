# v0.1.40.1 本地优化版

版本标识 `v0.1.40.1-local.1`，基础为上游正式 tag
[`v0.1.40.1`](https://github.com/Niko1221/Strata/releases/tag/v0.1.40.1)，
commit `82f46a8c8f475f001ad76d92f58f4a4f8ffb0253`。
版本分支 `local-v0.1.40.1`。

## 功能范围

保留 ModelScope 与 GitHub 文件加速两个可选下载功能，设置方式见
[下载源说明](LOCAL_MODELSCOPE.md)。2026-10-07 在原生 Responses 上新增
[JSON 与工具共存修订](RESPONSES_STRUCTURED_TOOLS.md)，并将 JSON Schema 校验依赖加入安装清单。
没有迁移旧版 Responses 实现、catalog 生成器、自定义服务版本提示或旧 Codex 协议补丁。
模板、推理引擎和功能配置仍沿用上游。
用户已有的客户端配置独立于这些源码补丁，部署后应按实际模型 ID、上下文和视觉能力核对。

v0.1.40.1 是 Python 服务热修订，使用 0.1.40 引擎；CMake 的 0.1.40 版本标记保持上游原值。
从 0.1.38 部署升级仍需要至少 0.1.40 引擎。首次验收在 CMD 固定来源：

```cmd
set "STRATA_PREBUILT_URL=https://github.com/Niko1221/Strata/releases/download/v0.1.40/"
```

安装器在 HEAD、下载和续传中使用同一 GitHub 适配器，保留上游 CUDA13、CUDA12、HIP
资产选择、版本判断及显式来源规则，不固定成旧版 NVIDIA 包。

## 本地验证

用户于 2026-10-07 反馈原候选真机测试没有大问题，发现自动审批请求的 JSON 与工具组合被拒绝。
随后用户应用本次 Responses 修订并反馈真机测试成功。本版本据此发布；该反馈不扩展为全部工具、
所有审批场景、长任务或性能指标均已验证。下表保留修订前的本地基线结果；修订测试见
[Responses 兼容说明](RESPONSES_STRUCTURED_TOOLS.md)。

验证日期 2026-10-06，Windows、Python 3.14.3、Codex CLI 0.158.0。

| 检查 | 结果 |
| --- | --- |
| serve 完整回归 | 452 项：443 通过、6 跳过、3 个计时测试初次失败；三项原样复测通过，slots 模块 30 项 OK（1 跳过） |
| tools 完整回归 | 474 项 OK（2 跳过），使用下述本地测试环境适配 |
| Codex cached/live/disabled | 三种模式均通过，每种三轮 HTTP；原生 Responses 与 MockEngine |
| Python 语法及 Git 差异检查 | compileall 与 git diff --check 通过 |

CLI 测试辅助脚本和 catalog 测试配置位于仓库外的本地维护目录，没有加入发布源码。
测试中的 function/custom 工具结果可正常回传；实际 shell 和 apply_patch 被受管策略及
只读沙箱阻止，因此不代表真实工具执行成功。Hosted web search 仍由上游原生逻辑跳过，
不能将可选搜索定义兼容宣称为内置搜索可用。

独立虚拟环境使用与当前测试 CPU 兼容的 NumPy 2.3.5；上游 requirements 对 Python 3.12+
固定的 2.5.3 曾无法在该 CPU 环境加载，仓库 requirements 没有修改。
GGUF 测试使用上游固定 llama.cpp commit `3cf03257f219afbe7334045ff7c6a06ac68c627d` 的 gguf-py。
这不等于上游完整依赖、引擎编译或真实权重已验收。

工具回归的 HIP 模拟引擎夹具只在本地辅助脚本中固定 AVX2 CPU，防止与本机检测不一致时
触发真实 ROCm 安装。上游测试文件和生产检测没有修改。本机 CPUID floor 返回空值，
真实 CPU 探测列为待真机检查的跳过项；另一个工具跳过项是 Windows symlink 权限。
初次 Windows 配置原子替换拒绝在单项和完整复测中均通过。
服务初次失败的三项涉及 0.15–0.3 秒窗口，独立原样复测和整个 slots 模块均通过；
保留初次失败日志，不将此次完整回归表述为首次全部通过。

此前相同 ModelScope 适配已实际读取 IQ3_S 首分片、视觉文件和 MTP 分片的前 8 字节，
并解析 MTP 索引。小范围读取不能证明完整镜像哈希、大文件续传或部署网络吞吐。
GitHub 示例加速源对固定 0.1.40 Windows 引擎 ZIP 和固定 llama.cpp 源码 ZIP 的前 8 字节
均返回 HTTP 206 和正确 Content-Range；CUDA12/HIP 资产路径在模拟回归中核对。

## 真机验收

1. 保留可用旧环境，为候选使用独立配置、引擎目录和明确的数据目录；升级不得覆盖旧配置。
2. 检查依赖导入、BUILD.json 和引擎启动日志，确认运行至少 0.1.40 引擎。
3. 首轮沿用 IQ3_S、65536、medium 和原视觉设置。检查模型元数据、文本/图像、JSON/SSE、
   unload 后重载、取消后下一请求、断连取消、错误状态和请求监控。
4. 用原生 Responses 完成实际文件读取、命令、apply_patch、两轮以上工具回传，检查退出码和
   文件变化；单独测试长任务和压缩。thinking、围栏或 inline code 中的工具示例应保持文本。
5. 实际测试 ModelScope 固定 revision、完整模型/视觉下载、MTP Range 和 tensor 哈希；
   核验 GitHub 下载资产、BUILD.json、续传与文件完整性。
6. 与旧版使用相同模型和请求比较 RAM/VRAM 峰值、首 token 延迟、prompt 和生成速度。
   没有真机结果前不宣称性能提升，也不为升级默认启用并行或其他实验参数。

旧版 v0.1.27 的用户反馈和 v0.1.38 的测试结果不作为本候选的真机验收结果。
