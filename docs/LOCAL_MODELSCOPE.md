# ModelScope 和 GitHub 下载源

此候选基于上游 v0.1.40.1，只增加两种可选下载适配。默认仍使用上游的模型和文件来源。
服务接口、推理引擎与功能配置使用上游实现。验证范围见 [候选说明](CANDIDATE_v0.1.40.1.md)。

## CMD 中启用

```cmd
set "STRATA_USE_MODELSCOPE=1"
set "STRATA_GITHUB_MIRROR=https://gh-proxy.org/"
set "STRATA_PREBUILT_URL=https://github.com/Niko1221/Strata/releases/download/v0.1.40/"
START-HERE.bat
```

可分别启用两项功能。上面的 GitHub 前缀是示例，需使用部署网络可访问且支持这种规则的服务。
现有模型文件可按上游流程复用；下载成功不等于模型/引擎版本或镜像字节已经核验。

关闭时在 CMD 设置空值：

```cmd
set "STRATA_USE_MODELSCOPE="
set "STRATA_GITHUB_MIRROR="
```

Linux 同样使用对应环境变量，例如 `STRATA_USE_MODELSCOPE=1 ./setup.sh`。

## ModelScope 模型下载

`STRATA_USE_MODELSCOPE=1` 覆盖模型 GGUF、视觉 mmproj、MTP checkpoint 索引和 tensor Range。
适配器保留代码中的逻辑 HF URL，只在网络入口换源。

默认使用同名 ModelScope 仓库，将 HF main 和 40 位 commit hash 映射为源的 master；
两个平台的 commit ID 不假定互通，其他具名 revision 默认保留。
ModelScope 仓库不同或需要固定该源自己的 revision 时，在 CMD 使用 JSON 映射：

```cmd
set "STRATA_MODELSCOPE_REPOS={"ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF":"your-org/your-mirror"}"
set "STRATA_MODELSCOPE_REVISIONS={"ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF":"MODEL_SCOPE_COMMIT"}"
```

将示例值换成源仓库实际存在的名称和 revision。MTP 与视觉需要固定时分别添加对应原 HF 仓库名。
需要固定 ModelScope revision 不要求设置仓库重映射。

同时设置 ModelScope 开关与 HF_ENDPOINT 时，ModelScope 优先，适配器识别配置的 endpoint
及其路径前缀；不启用时保持上游 HF_ENDPOINT 行为。
HEAD、GET 和 Range 使用相同源，MTP 仍检查 HTTP 206、Content-Range 和固定 checkpoint 的
已知 SHA256。源 404 不切换 logical checkpoint 以关闭校验，不自动回到 HF 下载。
Range 响应忽略边界时拒绝读取整个权重分片。

源仓库必须包含同路径、同字节的模型文件，尤其 MTP offsets 来自 checkpoint。
普通模型文件继续使用上游完整性规则，不能仅凭 master 或下载完成证明与 HF 固定版本一致。
更换为不同内容的模型/源时使用独立目录，避免沿用已完成标记。

## GitHub 文件加速

`STRATA_GITHUB_MIRROR` 是 HTTPS URL 前缀。例如：

`https://github.com/Niko1221/Strata/releases/download/v0.1.40/strata-windows-x64.zip`

变为：

`https://gh-proxy.org/https://github.com/Niko1221/Strata/releases/download/v0.1.40/strata-windows-x64.zip`

它覆盖 GitHub 引擎 ZIP 与 llama.cpp 源码 ZIP 的 HEAD、GET 和断点续传，保留 NVIDIA CUDA13、
CUDA12 和 AMD HIP 的原生资产选择。自定义 STRATA_PREBUILT_URL 的 GitHub 地址同样适用。
本地路径、非 GitHub 地址和已经加速的 URL 不重复处理。

变量不代理 git clone/pull，也不改变系统或 Git 全局代理，不加速 Python、CUDA 或 PyPI 包。
GitHub mirror 与 ModelScope 独立，不能用其中一个代替另一项。

## 回归检查

```cmd
python -m unittest tools.test_model_source tools.test_github_source tools.test_mtp_fetch tools.test_setup_pins tools.test_setup_hotfix_tag
```

真实部署还应核验完整文件、MTP tensor 哈希、BUILD.json 和模型来源。
