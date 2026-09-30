# Strata 本地兼容版本

版本：`v0.1.27-local.1`。基于上游正式发布 `v0.1.27`，commit
`a79080535d1b2a71a3419a0d97d8e7dca194b0f1`，本地分支 `local-v0.1.27`。
2026-09-30 核验 [上游 latest release](https://github.com/Niko1221/Strata/releases/latest)
仍指向这个 tag。本社区 Fork：[jielin99/Strata-codex](https://github.com/jielin99/Strata-codex)。

## 两个独立补丁

1. `feat: support opt-in ModelScope downloads`：两个下载入口共用
   `tools/model_source.py`。使用方式见 [LOCAL_MODELSCOPE.md](LOCAL_MODELSCOPE.md)。
2. `feat: add Codex-compatible Responses API`：新增 `serve/responses.py`，
   复用 `Service.prepare/run`、原有模板、工具解析、推理队列、缓存、采样和取消。
   `serve/server.py` 只有导入、路由、协议列表和本地版本提示几处改动。

## 接入 Codex

先按现有流程启动真实 Strata 模型，确认 `http://127.0.0.1:8080/health` 正常。
使用 Windows **CMD** 的环境变量和 `codex -c ...` 参数启动，无需创建 TOML
配置文件或 profile。以下设置是本次启动的命令行覆盖，不写入 Codex 全局配置。
先在同一个 CMD 窗口设置变量；示例上下文需按真实引擎容量调整：

```bat
set "LLM_BASE_URL=http://127.0.0.1:8080/v1"
set "LLM_MODEL=qwen3.8-flash-next-iq3_s"
set "LLM_CONTEXT_WINDOW=65536"
set "LLM_AUTO_COMPACT=49152"
set "LLM_REASONING=medium"
set "LLM_PLAN_REASONING=medium"
set "LLM_MODEL_CATALOG=F:\Tmp\Strata\docs\codex-qwen3.8-flash-next.json"
```

上面使用 [Qwen 专用静态模板](codex-qwen3.8-flash-next.json)，对应原版 IQ3_S、64K、medium 推理、纯文本部署。
推荐按 [Qwen catalog 研究与生成说明](CODEX_QWEN_CATALOG.md) 从实际 `/v1/models`
生成部署专用文件，再将模型名、上下文、压缩阈值和 catalog 绝对路径设为工具打印的值。
`LAN_API_KEY` 设置为 Strata 启动时的 API key；服务未设置 API key 时，
可以在 CMD 中用 `set "LAN_API_KEY=strata-local"` 提供占位值。
不要将真实密钥写入公开脚本或仓库。

```bat
codex ^
  -c model_provider=lan ^
  -c "model_providers.lan.name=LAN" ^
  -c "model_providers.lan.base_url=%LLM_BASE_URL%" ^
  -c "model_providers.lan.env_key=LAN_API_KEY" ^
  -c "model_providers.lan.requires_openai_auth=false" ^
  -c "model_providers.lan.wire_api=responses" ^
  -c "model_providers.lan.supports_websockets=false" ^
  -c "model_providers.lan.stream_idle_timeout_ms=1800000" ^
  -c "model_context_window=%LLM_CONTEXT_WINDOW%" ^
  -c "model_auto_compact_token_limit=%LLM_AUTO_COMPACT%" ^
  -c "model_auto_compact_token_limit_scope=total" ^
  -c "model_reasoning_effort=%LLM_REASONING%" ^
  -c "plan_mode_reasoning_effort=%LLM_PLAN_REASONING%" ^
  -c "agents.enabled=false" ^
  -c "web_search=disabled" ^
  -c "model_catalog_json='%LLM_MODEL_CATALOG%'" ^
  -m "%LLM_MODEL%" ^
  --sandbox danger-full-access ^
  --ask-for-approval never ^
  --disable apps
```

`^` 是 CMD 的续行符，后面不能有空格；`%变量%` 同样是 CMD 语法。
可将命令保存为本机 `.cmd` 或 `.bat`，在需要操作的项目目录运行。
示例保留 `danger-full-access`、不请求审批、禁用 apps 的启动偏好。
需要调整或了解的项目：

- `base_url` 指向实际 Strata 的 `/v1`；`wire_api="responses"`。
- 关闭 WebSocket；本实现提供 HTTP SSE。
- `web_search="disabled"`：Strata 不执行 OpenAI 云端搜索工具。
- `model_catalog_json` 通过 `-c` 指定 JSON 文件，不需要 TOML 配置文件。
  `LLM_MODEL` 应与 catalog 的 `slug` 一致；setup 的实际模型 ID 通常含量化后缀。
  服务端仍只调用当前已加载模型。静态模板不自动适配 Swift/Coder；不要仅换名字套用。
  Catalog 为本地模型提供 `apply_patch_tool_type="freeform"`，避免未知模型的
  Codex fallback metadata 不提供自定义 `apply_patch`。
- Catalog 是依据 Qwen、Strata 和 Codex 公开资料整理的社区配置，
  包含本 Fork 编写的 `base_instructions`，不是厂商提供的官方能力文件。
- `model_context_window`、catalog 的 `context_window` 和 `max_context_window` 不得超过真实引擎设置。
  默认示例为 65536，提前在 49152 tokens 压缩，给下一次回复留出空间。
  生成工具自动读取已加载的视觉能力；无视觉模块时只声明 `text`。
- `env_key=LAN_API_KEY` 对应同名环境变量；其值通过 Bearer 认证发送。

命令行覆盖见 [官方高级配置](https://learn.chatgpt.com/docs/config-file/config-advanced)，
参数含义见 [官方配置参考](https://developers.openai.com/codex/config-reference/)。
不同 Codex 版本的 catalog 字段可能变化，更新 CLI 后可先运行下面的 smoke test。

## 支持范围

`POST /v1/responses` 支持 JSON 和带序号的 SSE：

- `input` 字符串、message（含 input/output text 和 image_url）、instructions。
- function_call/function_call_output、custom_tool_call/custom_tool_call_output，
  工具命名空间，多个函数调用，完整历史回传。
- reasoning effort 复用上游映射。原模型的明文 thinking 通过 reasoning summary
  item/events 返回；不是额外调用模型生成的摘要。`summary="none"` 可关闭这部分输出。
  外部 reasoning 的加密内容无法解密，历史中只利用可读 content/summary。
- Codex 无 call_id 的通知型输出转为带工具名的上下文，不虚构工具配对。
- max_output_tokens、上游已有的采样参数及共享默认值；请求显式值优先。
- item/content/arguments 的 added、delta、done，以及 completed/incomplete/failed。
  input/output/total tokens 和 cached input counts 来自原服务；不虚报独立 reasoning token 数。
- 超出上下文返回 `context_length_exceeded`；断线关闭生成器并取消推理。
  等待引擎/生成自定义工具时发送 keep-alive。

普通函数参数可以增量流式传输。自定义工具在原解析器完成调用后才解包 raw input；
生成期间仍有心跳。工具 `output_item.done` 等到正常结束才发出，避免 Codex 执行
因 token 预算耗尽而截断的调用。`parallel_tool_calls=false` 时多个调用会报错。
工具严格 schema 和自定义 grammar 由本地模型按提示尽力遵守，不提供 constrained decoding。

这是无状态 Codex 兼容层：每轮发送完整 input，使用 `store=false`。
不支持服务器会话存储、previous_response_id、background、云端内置工具、
强制 tool_choice、JSON Schema 输出、文件上传引用、音频或 Responses WebSocket。
这些功能请求会明确拒绝，未知 input/tool 类型不会被静默丢弃。
`GET /v1/responses/<id>` 与 `/v1/responses/compact` 没有实现；
Codex 本地压缩通过普通 Responses 对话进行，仍受真实上下文容量限制。

实现依据：[官方 function calling](https://developers.openai.com/api/docs/guides/function-calling)、
[流式事件参考](https://platform.openai.com/docs/api-reference/responses-streaming/response/refusal?lang=python)、
[Codex SSE consumer](https://github.com/openai/codex/blob/main/codex-rs/codex-api/src/sse/responses.rs)、
[Codex items](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/models.rs)、
[Codex model catalog](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/openai_models.rs)。
资料核验日期为 2026-09-30，实际 CLI 联调版本为 0.158.0。

## 验证

```powershell
python -m unittest serve.test_responses serve.test_server serve.test_mcp serve.test_detok tools.test_model_source tools.test_codex_catalog -q
python -m serve.codex_smoke
# 允许工具执行的本机环境还应验证实际 echo 和文件修改成功：
python -m serve.codex_smoke --require-tool-success
```

MockEngine 覆盖协议及原有推理前端，无需 GPU。
Smoke test 启动真实 Strata HTTP 层，使用脚本化引擎，由安装的真实 Codex CLI
消费 SSE，执行函数工具、自定义 apply_patch，并回传工具结果到下一轮。
测试从 HTTP 层的部署元数据生成 Qwen catalog，使用 `-c` 定义 LAN provider，不使用 profile。
其隔离运行目录、标记文件和诊断保存在 `logs/codex-smoke/`，不访问真实 Codex 凭据。
默认区分协议成功与实际工具执行成功；只读沙箱下工具错误回传也能验证多轮协议。
目前协议链路已验证，当前受管运行环境阻止嵌套 Codex 的实际 shell/patch 执行；
真实 GPU 模型的工具选择质量、真实工具执行与长任务压缩还需要在实际部署环境验证。

本次最终回归：80 项，OK（3 项依上游条件跳过）；`git diff --check` 与 Python
语法编译通过。命令行 provider 参数及 catalog 已由 Codex CLI 0.158.0 加载验证，
三轮 HTTP 协议 smoke test 通过。
Qwen catalog 修订另有 4 项生成器测试通过，且与 10 项 Responses 回归联合验证通过；
字段来源与真实模型验证边界见 [Qwen catalog 说明](CODEX_QWEN_CATALOG.md)。

ModelScope 已核验四个同名仓库及主要文件地址，并实际读取 Qwen safetensors 索引和
MTP 分片的 8 字节 Range；未下载数十 GB 权重或比较完整镜像哈希。

## 版本与引擎

本 Fork 的功能补丁基于上游正式发布 tag，保持独立提交。
上游提供原生 Responses 后，会验证兼容性并移除临时适配层。

注意 setup 的上游预编译 engine 默认 URL 指向 latest；若需要完全固定引擎版本，启动前设置：

```powershell
$env:STRATA_PREBUILT_URL = "https://github.com/Niko1221/Strata/releases/download/v0.1.27/"
```

这仍使用上游已有配置机制，不新增引擎分支。
