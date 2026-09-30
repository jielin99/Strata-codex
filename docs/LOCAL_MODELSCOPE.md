# ModelScope 本地补丁

默认下载行为仍为 Hugging Face。PowerShell 启用：

```powershell
$env:STRATA_USE_MODELSCOPE = "1"
./START-HERE.bat
```

Linux/macOS：`STRATA_USE_MODELSCOPE=1 ./setup.sh`。
同一开关覆盖 setup 的模型 GGUF、视觉 mmproj 和 MTP 权重及索引下载。
GitHub、CUDA、pip 下载不受此开关影响。

## GitHub 文件下载加速

GitHub 引擎 ZIP 和 llama.cpp 源码 ZIP 可以单独设置下载加速前缀。
与 ModelScope 开关一起使用（PowerShell）：

```powershell
$env:STRATA_USE_MODELSCOPE = "1"
$env:STRATA_GITHUB_MIRROR = "https://gh-proxy.org/"
./START-HERE.bat --setup --host 0.0.0.0
```

CMD：

```bat
set "STRATA_USE_MODELSCOPE=1"
set "STRATA_GITHUB_MIRROR=https://gh-proxy.org/"
START-HERE.bat --setup --host 0.0.0.0
```

这是 URL 前缀加速：例如
`https://github.com/Niko1221/Strata/releases/latest/download/strata-windows-x64.zip`
变为
`https://gh-proxy.org/https://github.com/Niko1221/Strata/releases/latest/download/strata-windows-x64.zip`。
前缀规则见 [GH-Proxy 自有说明](https://gh-proxy.com/docs/github-accelerator)。
也可换成支持相同规则的 `https://gh-proxy.com/` 或 `https://ghfast.top/`。
不填写完整 GitHub 文件地址，不设置 SOCKS/系统代理，也不修改 Git 全局配置。
未设置时仍直连；自定义 `STRATA_PREBUILT_URL` 的 GitHub 地址同样生效，已加速的
地址和本地文件不重复处理。下载前的引擎 HEAD 探测、下载和断点续传共用这个入口。

2026-10-01 检查：上述三个前缀均返回选定 `v0.1.27` 引擎和固定 commit
llama.cpp 源码 ZIP 的前 8 字节；`gh-proxy.org` / `gh-proxy.com` 对两者
返回 HTTP 206 和正确 Content-Range。仅验证小范围读取，没有完整文件哈希或
中国大陆网络吞吐测试；这些是第三方加速服务，速度和可用性以部署网络为准。
pip/CUDA 包、Python 安装和 git clone/pull 不由这个变量加速。

若还需要下载本社区仓库代码，可手动使用加速地址克隆指定版本分支：

```powershell
git clone --branch local-v0.1.27 https://gh-proxy.org/https://github.com/jielin99/Strata-codex.git Strata
git -C Strata remote set-url origin https://github.com/jielin99/Strata-codex.git
```

这只通过加速站读取公开仓库，随后恢复正常 origin 地址。已有仓库可以只对
一次 fetch 加速，随后正常合并这次取回的分支：

```powershell
git -c 'url.https://gh-proxy.org/https://github.com/.insteadOf=https://github.com/' fetch origin local-v0.1.27
git merge --ff-only origin/local-v0.1.27
```

前提是 origin 已指向本社区仓库，当前就在对应版本分支且没有需要保留的未提交修改。
这些命令不改全局 Git 配置；下载加速也不会更换所选版本。

关闭：PowerShell `Remove-Item Env:STRATA_GITHUB_MIRROR`；CMD
`set "STRATA_GITHUB_MIRROR="`。更换前缀后重试；已经下载完成的文件继续跳过。
测试：`python -m unittest tools.test_github_source -v`。

## 仓库映射

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
