# Responses JSON 与客户端工具兼容

本修订基于 v0.1.40.1 的原生 `serve/responses.py`、`serve/server.py` 和 `serve/structured.py`。
解决 `a JSON text.format with tools is not supported`，没有恢复旧版整套 Responses 补丁。
随 `v0.1.40.1-local.1` 发布。用户应用更新后反馈真机测试成功；未提供逐项测试日志，
因此不扩展为所有工具或审批场景、长任务和性能均已验证。

## 协议依据

核对日期：2026-10-07，使用 OpenAI 官方资料：

- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)：
  `text.format` 约束回答文本；`json_schema` 与只保证 JSON 对象的 `json_object` 不同。
  达到输出上限时应检查 `incomplete`，不能把它当作完整结构化回答。
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)：
  工具调用和回答文本是不同的输出项；客户端执行工具后，以对应 `call_id` 回传结果，再继续请求。
  `auto`、`none`、`required` 和指定工具的选择语义不同，`parallel_tool_calls=false` 限制至多一个调用。
- [Responses streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events)：
  保留输出项、参数增量、完成事件的顺序及关联 ID；响应结束区分 completed、incomplete 和 failed。

## 本地实现

`json_schema` / `json_object` 可与 function、namespace、custom 客户端工具共存：

1. 模型可直接返回符合格式的回答，也可先返回工具调用。纯工具轮无需生成虚假的空 JSON 回答。
2. 客户端回传工具结果后，下一轮仍保留原来的格式要求。服务端不替客户端执行这些工具。
3. 一轮同时包含文字和工具时，每段回答文字都要独立通过校验；有工具不意味着可以绕过文字校验。
   流式输出可先发送初始 reasoning；从正文或工具开始，缓存后续事件，校验通过后按原顺序交付。
4. 结构化回答必须完整解析为一个 JSON 对象，不截取围栏、说明文字或多个对象中的第一个对象。
   非法 JSON、重复键、非有限数、Schema 违规、无回答且无工具均返回 `structured_output_failed`。
   非流式为 HTTP 502；已开始的 SSE 返回 `response.failed`，不交付该轮缓存中的工具或无效正文。
5. 达到 `max_output_tokens` 返回 `response.incomplete` 和原因，不释放未校验正文；未结束的工具项标记
   incomplete。非 token 上限导致的未结束工具调用返回错误。客户端必须检查响应和工具项状态。
6. 复用原生强制工具前缀处理 `required` 和指定 function/custom（含 namespace）；不支持的选择方式
   或不存在的工具返回 400，不静默改成 auto。结构化响应在交付前再次检查指定工具、调用数量和工具名。

## 安装与已有部署升级

新安装通过 requirements.txt 安装固定版本的 `jsonschema` 及其依赖。已有部署在 Strata 目录下的 CMD 执行：

```cmd
.venv\Scripts\python.exe -m pip install "jsonschema==4.26.0"
```

更新源码和依赖后重启服务。无需重下载模型、重编译引擎或调整现有 Codex 启动 BAT。
`strict: true` 缺少校验器时明确返回请求错误；非 strict 请求保留上游的对象级降级行为。

## 验证与边界

2026-10-07 本地结果（Windows、Python 3.14.3、Codex CLI 0.158.0）：

| 检查 | 结果 |
| --- | --- |
| 新增协议回归与安装依赖回归 | 22 项通过（17 项协议、5 项安装） |
| 完整服务端回归 | 466 项：457 通过、6 跳过、3 个 slots 计时失败；原样单独复测 slots 30 项 OK，1 跳过 |
| 实际 Codex CLI 普通模式 | function/custom 工具与最终文本，3 轮 HTTP 协议通过 |
| 实际 Codex CLI `--output-schema` | 每轮均携带 tools 与 strict JSON Schema，3 轮通过，最终 JSON 被客户端接受 |
| 静态检查 | Python 编译、git diff --check、测试环境 pip check 通过 |

完整回归开始后又补充了 3 个边界用例，已包含在最终的 17 项协议回归中；完整回归首次计数为 466。
slots 的失败涉及 0.3 秒静默窗口和 1 秒阶段超时；保留首次结果，不将整套表述为首次全部通过。
测试环境沿用候选的 NumPy 2.3.5 CPU 兼容设置，生产 NumPy pin 没有修改。
两组 CLI 测试均使用 MockEngine；受管环境中的实际 shell/patch 未执行成功，不能视为真实工具执行通过。

回归命令（使用安装依赖后的 Python）：

```cmd
.venv\Scripts\python.exe -m unittest serve.test_responses serve.test_responses_structured serve.test_structured -v
.venv\Scripts\python.exe -m unittest tools.test_setup_pins.Requirements -v
```

测试覆盖 JSON/SSE、直接回答、工具多轮回传、function/custom/namespace、混合输出、强制工具、
parallel=false、缺失依赖、错误 Schema、输出上限和非法模型输出。测试引擎为 MockEngine，不能证明
Qwen 真机审批结论的准确性。用户另外反馈了本修订真机测试成功；其他部署仍应核验实际审批行为。

仍使用提示词加生成后校验，不是语法约束解码；没有隐藏重试或默认批准。
本次支持范围不是完整 OpenAI API：未增加 hosted tools、allowed_tools、服务端会话存储、函数参数的
strict Schema 校验或原生 refusal 信号。普通拒绝文字不会被猜测成 refusal 或合成为审批结论。
Chat Completions 的 JSON 与工具/MCP 共存限制仍保留；其原有 JSON 文本提取行为也保持不变。
