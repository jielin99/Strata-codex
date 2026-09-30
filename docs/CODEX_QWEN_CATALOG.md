# Qwen3.8-Flash-Next 的 Codex catalog

这是为 **原版 Qwen3.8-Flash-Next + Strata Responses 兼容层**整理的社区配置，
不是 Qwen 或 OpenAI 发布的官方 Codex catalog。研究日期：2026-09-30；
Strata 基础：`v0.1.27`；实际 CLI 验证：Codex `0.158.0`。

[静态模板](codex-qwen3.8-flash-next.json) 展示 32768 上下文、纯文本部署。
推荐用独立的 [生成工具](../tools/codex_catalog.py) 绑定实际部署信息，
而不是把理论能力直接写进客户端。该工具不改推理服务、setup 或 Codex 全局配置。

## 依据与字段选择

| 字段 | 选择与依据 |
| --- | --- |
| `slug` | 使用 Strata `/v1/models` 返回的实际 ID。setup 会附加量化后缀，例如 `qwen3.8-flash-next-iq2_xs`；不能只凭仓库标题猜名字。 |
| `context_window` | 使用服务返回的 `meta.n_ctx`，或显式选择更小的容量。Qwen 原生上限为 262144，不能将云端版本或扩展上下文的 1M 套到普通 Strata 部署。 |
| `max_context_window` | 等于选定部署容量，防止 Codex 的命令行上下文覆盖扩大到引擎容量之外。它在这里是部署保护上限，不是模型理论上限。 |
| `input_modalities` | 根据服务的 `architecture.input_modalities`；没有视觉模块只声明 `text`，加载后才声明 `image`。 |
| `default_reasoning_level` | `high`，对应 Qwen 的原生默认 `xhigh`。启动命令显式指定 `medium` 时，仍以命令为准。 |
| `supported_reasoning_levels` | `none / low / medium / high / xhigh`。`none` 经 Strata 关闭思考；`high` 与 `xhigh` 完全同档，不是五种不同强度。 |
| `supports_reasoning_summary_parameter` | `true`，由 Responses 兼容层支持；返回模型原始明文 thinking。不是 Qwen 单独提供的摘要模型或私有加密推理功能。 |
| `supports_reasoning_effort_updates` | **`false`**。Codex 此字段指 `configuration_update` 输入项；当前兼容层不支持它。普通请求的 `reasoning.effort` 可以调整，不应据此将本字段设为 true。 |
| `shell_type` | `unified_exec`，选择 Codex 函数工具；模型使用上游 Qwen 模板的 function/parameter 格式调用。 |
| `apply_patch_tool_type` | `freeform`，让 Codex 提供自定义补丁工具；适配层将原始文本包装为 Qwen 可接受的 `input` 字符串参数，再还原为 custom tool 事件。协议可行不等于真实模型每次都能正确生成补丁。 |
| `base_instructions` | 本 Fork 编写的简短编码助手指令，说明真实工具结果与 patch 参数；不是从其他模型复制的系统提示词。具体工具定义和 XML 格式仍由原模板提供。 |
| `auto_compact_token_limit` | 生成器默认取容量的 75%，允许显式调整到不超过 90%。75% 是社区运行策略，不是 Qwen 官方参数；Codex 0.158.0 会将压缩阈值限制在上下文的 90% 以内。 |
| `effective_context_window_percent` | 沿用 Codex 的 95% 输入预算策略；也不是模型原生能力。Codex 的本地 token 估算不保证与 Qwen tokenizer 完全相同，服务端仍执行真实容量校验。 |
| `truncation_policy` | 10000 bytes 的工具输出预算，沿用 Codex fallback 的客户端策略，避免工具输出迅速占满上下文。可按任务调整。 |
| 云端/实验能力 | verbosity、原始图像 detail、搜索、实验上下文、Responses Lite 均关闭；不声明当前服务没有实现的能力。`web_search=disabled` 和 `supports_websockets=false` 仍由启动参数明确设置。 |

研究来源：

- [Qwen 官方模型卡](https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/de4b8e4d43b917e7706784d8bb445c9af86a3540/README.md)：原生上下文、视觉、thinking 默认和原生推理档位；[模型配置](https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/de4b8e4d43b917e7706784d8bb445c9af86a3540/config.json) 的 `text_config.max_position_embeddings` 为 262144。此次核验的 revision 为 `de4b8e4d43b917e7706784d8bb445c9af86a3540`。
- [Strata v0.1.27 setup](https://github.com/Niko1221/Strata/blob/v0.1.27/setup.py)：生成带量化后缀的模型 ID、部署上下文与视觉配置。
- [Strata 请求转换](https://github.com/Niko1221/Strata/blob/v0.1.27/serve/frontend.py) 与 [原模板](https://github.com/Niko1221/Strata/blob/v0.1.27/serve/chat_template.jinja)：thinking 档位映射和函数调用格式。
- [Codex 0.158.0 ModelInfo](https://github.com/openai/codex/blob/rust-v0.158.0/codex-rs/protocol/src/openai_models.rs)：JSON 字段含义，特别是上下文保护上限和配置更新能力。
- [Codex 0.158.0 fallback](https://github.com/openai/codex/blob/rust-v0.158.0/codex-rs/models-manager/src/model_info.rs)：未知模型的 warning、缺省 patch 工具和默认预算。
- [OpenAI Docs 配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)：`model_catalog_json`、命令行模型与上下文覆盖。

Qwen 官方的采样建议属于推理服务参数，不是 catalog 字段，因此不把 temperature、
top_p 等伪造为模型元数据。原版的研究结果也不自动覆盖 Swift 和 Coder 变体。

## 按实际部署生成

先启动 Strata，在 Windows CMD 中设置地址及 `LAN_API_KEY`（有认证时必须匹配），执行：

```bat
set "LLM_BASE_URL=http://127.0.0.1:8080/v1"
python -m tools.codex_catalog --base-url "%LLM_BASE_URL%" --output "logs\codex-models.json"
```

工具读取 `/v1/models`，生成一个对应当前模型的条目，并打印 `LLM_MODEL`、
`LLM_CONTEXT_WINDOW` 和 `LLM_AUTO_COMPACT`。将这些值设置到 CMD 环境变量，
将 `LLM_MODEL_CATALOG` 设为输出文件的**绝对路径**，再使用 [启动命令](LOCAL_FORK.md#接入-codex)。

若要提前规划、更小的客户端上下文或保持已有压缩阈值：

```bat
python -m tools.codex_catalog --base-url "%LLM_BASE_URL%" --context-window 32768 --auto-compact 24000 --output "logs\codex-models.json"
```

服务暂未启动时，也可从 setup 生成的 JSON 离线读取：

```bat
python -m tools.codex_catalog --config "strata-iq2_xs.json" --output "logs\codex-models.json"
```

离线模式反映配置意图，不能证明引擎已启动或视觉加载成功；部署后优先重新读取服务。
切换量化版本、引擎上下文或视觉设置后重新生成，并重启 Codex 加载 catalog。
生成文件默认在不上传的 `logs/`；API key 只用于请求认证，不写入文件。

工具会拒绝 Swift/Coder/其他模型、缺失部署元数据、超出部署容量和超过原生 262144
的上下文。模型 ID 是部署声明，不是权重哈希校验；使用原版模型仍由实际部署负责。

## 验证边界

已验证生成器的模型 ID、上下文上限、视觉开关、推理映射和错误拒绝；
真实 Codex CLI 0.158.0 加载生成的 Qwen 条目后，通过三轮 HTTP 协议联调，
没有对选定 Qwen ID 使用 fallback metadata。服务和解析器真实，推理引擎为 MockEngine。
当前受管环境仍阻止嵌套 Codex 的 shell/patch 写入，真实权重的工具成功率、
长任务及本地压缩质量没有验证。这是一份有来源依据的适配配置，不是效果保证。

若仍有 `Unknown model ...`，先检查警告中的具体 ID 是否等于本次 `LLM_MODEL`。
测试环境还可能出现其他内部模型 ID 的 warning；不要伪造同名条目来隐藏它。
主模型没有 warning 也不等同于真实模型能力全部验证通过。
