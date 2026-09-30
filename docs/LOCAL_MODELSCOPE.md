# ModelScope 本地补丁

默认下载行为仍为 Hugging Face。PowerShell 启用：

```powershell
$env:STRATA_USE_MODELSCOPE = "1"
./START-HERE.bat
```

Linux/macOS：`STRATA_USE_MODELSCOPE=1 ./setup.sh`。
同一开关覆盖 setup 的模型 GGUF、视觉 mmproj 和 MTP 权重及索引下载。
GitHub、CUDA、pip 下载不受此开关影响。

使用同名 ModelScope 仓库，将 Hugging Face `main` 映射到 ModelScope `master`。
如果镜像仓库不同，可设置 JSON 映射（Hugging Face repo → ModelScope repo）：

```powershell
$env:STRATA_MODELSCOPE_REPOS = '{"ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF":"your-org/your-mirror"}'
```

镜像必须包含同路径、同字节内容的文件，尤其 MTP 会复用已保存的 tensor byte offsets。
不自动回退到 Hugging Face；源错误会沿用现有下载错误提示。
已完成的下载保持现有跳过行为；切换到不同内容的仓库时应使用新模型/MTP目录。
MTP 对 Range 响应检查 HTTP 206 和 Content-Range，避免镜像忽略 Range 时下载整个权重分片。

适配集中在 `tools/model_source.py`，上游只需保留 setup 下载入口和 MTP get 入口的各一处调用。
验证：`python -m unittest tools.test_model_source -v`。
