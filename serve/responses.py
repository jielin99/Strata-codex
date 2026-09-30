"""Stateless Codex Responses compatibility over the existing Service boundary.

No engine, HTTP proxy, response database, or model-specific prompt implementation.
The only upstream integration is an import and POST route in server.py.
"""
from __future__ import annotations

import copy
import json
import threading
import time
import uuid

from serve.frontend import openai_to_messages

LOCAL_VERSION = "v0.1.27-local.3"
OPTIONAL_WEB_SEARCH_TYPES = frozenset(("web_search", "web_search_preview", "web_search_preview_2025_03_11"))
_notice_lock = threading.Lock()
_notice_sent = False


def _note_web_search_dropped():
    global _notice_sent
    with _notice_lock:
        if _notice_sent:
            return
        print("[strata] Responses: optional built-in web search unavailable; continuing with client tools "
              "(this notice only appears once per server run)", flush=True)
        _notice_sent = True


def _object(value, field):
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _array(value, field):
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _string(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value


def _content(value):
    if isinstance(value, str):
        return value
    out = []
    for p in _array(value, "content"):
        p = _object(p, "content part")
        kind = p.get("type")
        if kind in ("input_text", "output_text", "text", "summary_text", "reasoning_text"):
            out.append({"type": "text", "text": _string(p.get("text"), "text")})
        elif kind == "input_image" and isinstance(p.get("image_url"), str):
            out.append({"type": "input_image", "image_url": p["image_url"]})
        else:
            raise ValueError(f"unsupported content part {kind!r}; use text or an image_url")
    return out


def _text(value):
    content = _content(value)
    if isinstance(content, str):
        return content
    return "".join(p["text"] for p in content if p["type"] == "text")


def _tool_name(name, namespace=None):
    name = _string(name, "tool name")
    return f"{namespace}.{name}" if namespace else name


def _client_tools(definitions):
    """Keep executable client tools; optional OpenAI-hosted search is unavailable."""
    return [tool for value in _array(definitions, "tools")
            if (tool := _object(value, "tool")).get("type") not in OPTIONAL_WEB_SEARCH_TYPES]


def _tools(definitions):
    tools, names = [], {}

    def add(tool, namespace=None):
        tool = _object(tool, "tool")
        kind = tool.get("type")
        if kind == "namespace" and namespace is None:
            ns = _string(tool.get("name"), "namespace name")
            for child in _array(tool.get("tools"), "namespace tools"):
                add(child, ns)
            return
        if kind not in ("function", "custom"):
            raise ValueError(f"unsupported tool type {kind!r}; use function/custom tools")
        alias = _tool_name(tool.get("name"), namespace)
        if not alias or alias in names:
            raise ValueError(f"duplicate or empty tool name {alias!r}")
        names[alias] = {"name": tool["name"], "kind": kind, "namespace": namespace}
        description = tool.get("description", "")
        parameters = tool.get("parameters") or {"type": "object", "properties": {}}
        if kind == "custom":
            # Qwen's native tool parser accepts named parameters. Wrap freeform tools
            # in one string parameter and unwrap back to custom_tool_call on output.
            description += "\nPut the complete raw tool input in the input string parameter."
            if tool.get("format"):
                description += "\nInput format: " + json.dumps(tool["format"], ensure_ascii=False)
            parameters = {"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]}
        tools.append({"type": "function", "function": {"name": alias,
                      "description": description, "parameters": _object(parameters, "parameters")}})

    for tool in _array(definitions, "tools"):
        add(tool)
    return tools, names


def responses_to_chat(req):
    """Return a Chat-shaped request and tool identity map; reuse upstream normalization."""
    req = _object(req, "request")
    for key in ("previous_response_id", "conversation", "background", "store"):
        if req.get(key):
            raise ValueError(f"{key} is unsupported; send full input history with store=false")
    if req.get("strata_mcp"):
        raise ValueError("Responses tools are executed by the client; strata_mcp is unsupported")
    for key in ("stream", "parallel_tool_calls"):
        if key in req and not isinstance(req[key], bool):
            raise ValueError(f"{key} must be a boolean")
    reasoning = req.get("reasoning") or {}
    _object(reasoning, "reasoning")
    if reasoning.get("summary") not in (None, "auto", "concise", "detailed", "none"):
        raise ValueError("unsupported reasoning.summary")
    text = _object(req.get("text") or {}, "text")
    if _object(text.get("format") or {}, "text.format").get("type", "text") != "text":
        raise ValueError("structured text.format is unsupported by this compatibility endpoint")
    choice = req.get("tool_choice", "auto")
    if isinstance(choice, dict) and choice.get("type") in OPTIONAL_WEB_SEARCH_TYPES:
        raise ValueError("built-in web search execution is unsupported; use a client-side function/custom search tool")
    if choice not in ("auto", "none"):
        raise ValueError("tool_choice supports auto or none; forced tool use is unsupported")
    definitions = req.get("tools") or []
    client_tools = _client_tools(definitions)
    tools, names = _tools(client_tools)
    if choice == "none":
        tools = []
    messages = []
    if req.get("instructions"):
        messages.append({"role": "system", "content": _string(req["instructions"], "instructions")})
    if len(client_tools) != len(definitions):
        messages.append({"role": "system", "content":
            "Built-in web search is unavailable on this local server. Only the supplied client-side tools "
            "can be called. Do not claim to have searched the web without a successful search tool result."})
    items = req.get("input")
    if isinstance(items, str):
        items = [{"role": "user", "content": items}]
    for item in _array(items, "input"):
        item = _object(item, "input item")
        kind = item.get("type", "message")
        if kind == "message":
            role = item.get("role")
            if role not in ("system", "developer", "user", "assistant"):
                raise ValueError(f"unsupported message role {role!r}")
            content = _content(item.get("content"))
            if role == "assistant" and messages and messages[-1]["role"] == "assistant":
                old = messages[-1]["content"]
                messages[-1]["content"] = _text(old) + _text(content)
            else:
                messages.append({"role": role, "content": content})
        elif kind == "reasoning":
            # Local reasoning is plaintext. Foreign encrypted state cannot be decoded;
            # its summary is still useful when replaying a stateless transcript.
            content = item.get("content") or item.get("summary") or []
            value = _text(content)
            if value:
                if not messages or messages[-1]["role"] != "assistant":
                    messages.append({"role": "assistant", "content": ""})
                messages[-1]["reasoning_content"] = messages[-1].get("reasoning_content", "") + value
        elif kind in ("function_call", "custom_tool_call"):
            name = _tool_name(item.get("name"), item.get("namespace"))
            args = item.get("arguments", "{}") if kind == "function_call" else {"input": _string(item.get("input"), "tool input")}
            if not messages or messages[-1]["role"] != "assistant":
                messages.append({"role": "assistant", "content": ""})
            messages[-1].setdefault("tool_calls", []).append({"id": item.get("call_id"),
                "type": "function", "function": {"name": name, "arguments": args}})
        elif kind in ("function_call_output", "custom_tool_call_output"):
            content = _content(item.get("output"))
            # Codex also sends named, unpaired notifications with no call_id.
            # Keep their identity and contents as context, without inventing a pairing.
            if not item.get("call_id"):
                name = _tool_name(item.get("name", "tool"), item.get("namespace"))
                messages.append({"role": "user", "content": f"Tool notification ({name}):\n" + _text(content)})
            else:
                messages.append({"role": "tool", "tool_call_id": item["call_id"], "content": content})
        else:
            raise ValueError(f"unsupported input item {kind!r}")
    if not messages:
        raise ValueError("input must contain at least one message")
    # Upstream normalization downgrades late system messages for Qwen. Merge only
    # the initial instruction prefix so developer instructions retain their role.
    initial = []
    while messages and messages[0]["role"] in ("system", "developer"):
        initial.append(_text(messages.pop(0)["content"]))
    if initial:
        messages.insert(0, {"role": "system", "content": "\n".join(initial)})
    chat = dict(req, messages=messages, tools=tools)
    if "max_output_tokens" in req and req["max_output_tokens"] is not None:
        budget = req["max_output_tokens"]
        if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
            raise ValueError("max_output_tokens must be a positive integer")
        chat["max_completion_tokens"] = budget
    return chat, names


class ResponseStream:
    """Item lifecycle and SSE serialization, independent of HTTP and the engine."""
    def __init__(self, model, req, names):
        self.req, self.names, self.sequence = req, names, 0
        self.output, self.closed, self.calls = [], set(), {}
        self.finished_calls = set()
        self.current = None
        self.response = {"id": "resp_" + uuid.uuid4().hex[:24], "object": "response",
                         "created_at": int(time.time()), "status": "in_progress", "model": model,
                         "output": self.output, "error": None, "incomplete_details": None, "usage": None,
                         "store": False, "parallel_tool_calls": req.get("parallel_tool_calls", True),
                         "tools": _client_tools(req.get("tools") or []), "tool_choice": req.get("tool_choice", "auto"),
                         "instructions": req.get("instructions"), "reasoning": req.get("reasoning"),
                         "max_output_tokens": req.get("max_output_tokens"), "metadata": req.get("metadata") or {}}

    def event(self, kind, **data):
        value = {"type": kind, "sequence_number": self.sequence, **data}
        self.sequence += 1
        # Snapshot mutable items so added events and non-stream collection don't
        # accidentally observe final state in an earlier lifecycle event.
        return kind, copy.deepcopy(value)

    def refs(self, index):
        return {"item_id": self.output[index]["id"], "output_index": index}

    def add(self, item):
        index = len(self.output)
        self.output.append(item)
        return index, self.event("response.output_item.added", output_index=index, item=item)

    def close(self, index, incomplete=False):
        if index in self.closed:
            return
        self.closed.add(index)
        item = self.output[index]
        refs = self.refs(index)
        kind = item["type"]
        if kind == "message":
            part = item["content"][0]
            yield self.event("response.output_text.done", **refs, content_index=0, text=part["text"])
            yield self.event("response.content_part.done", **refs, content_index=0, part=part)
        elif kind == "reasoning":
            part = item["summary"][0]
            yield self.event("response.reasoning_summary_text.done", **refs, summary_index=0, text=part["text"])
            yield self.event("response.reasoning_summary_part.done", **refs, summary_index=0, part=part)
        elif kind == "function_call":
            yield self.event("response.function_call_arguments.done", **refs, name=item["name"], arguments=item["arguments"])
        else:
            yield self.event("response.custom_tool_call_input.done", **refs, input=item["input"])
        item["status"] = "incomplete" if incomplete else "completed"
        yield self.event("response.output_item.done", output_index=index, item=item)

    def text(self, kind, value):
        if not value:
            return
        if self.current is None or self.output[self.current]["type"] != kind or self.current in self.closed:
            if self.current is not None:
                yield from self.close(self.current)
            item = {"id": ("rs_" if kind == "reasoning" else "msg_") + uuid.uuid4().hex[:24],
                    "type": kind, "status": "in_progress"}
            if kind == "reasoning":
                item["summary"] = [{"type": "summary_text", "text": ""}]
            else:
                item.update(role="assistant", content=[{"type": "output_text", "text": "", "annotations": []}])
            self.current, added = self.add(item)
            yield added
            refs = self.refs(self.current)
            if kind == "reasoning":
                yield self.event("response.reasoning_summary_part.added", **refs, summary_index=0, part=item["summary"][0])
            else:
                yield self.event("response.content_part.added", **refs, content_index=0, part=item["content"][0])
        item, refs = self.output[self.current], self.refs(self.current)
        if kind == "reasoning":
            item["summary"][0]["text"] += value
            yield self.event("response.reasoning_summary_text.delta", **refs, summary_index=0, delta=value)
        else:
            item["content"][0]["text"] += value
            yield self.event("response.output_text.delta", **refs, content_index=0, delta=value)

    def tool(self, ev):
        call = ev.call
        if call.id not in self.calls:
            if ev.kind == "tool_args":
                raise ValueError("tool arguments arrived without a tool start")
            if self.current is not None:
                yield from self.close(self.current)
                self.current = None
            spec = self.names.get(call.name)
            if spec is None or self.req.get("tool_choice") == "none":
                raise ValueError(f"model called an unavailable tool {call.name!r}")
            if self.req.get("parallel_tool_calls") is False and self.calls:
                raise ValueError("model emitted multiple calls with parallel_tool_calls=false")
            custom = spec["kind"] == "custom"
            item = {"id": ("ctc_" if custom else "fc_") + uuid.uuid4().hex[:24],
                    "type": "custom_tool_call" if custom else "function_call", "status": "in_progress",
                    "call_id": call.id, "name": spec["name"], "input" if custom else "arguments": ""}
            if spec["namespace"]:
                item["namespace"] = spec["namespace"]
            index, added = self.add(item)
            self.calls[call.id] = index
            yield added
        index = self.calls[call.id]
        item, refs = self.output[index], self.refs(index)
        if index in self.closed:
            return
        if ev.kind == "tool_args" and item["type"] == "function_call":
            item["arguments"] += ev.text
            yield self.event("response.function_call_arguments.delta", **refs, delta=ev.text)
        elif ev.kind == "tool_args":
            yield None  # keep-alive while buffering custom input until the native parser finishes
        elif ev.kind == "tool_call":
            if item["type"] == "custom_tool_call":
                item["input"] = _string(call.arguments.get("input"), "custom tool input")
                yield self.event("response.custom_tool_call_input.delta", **refs, call_id=call.id, delta=item["input"])
            elif not item["arguments"]:
                item["arguments"] = json.dumps(call.arguments, ensure_ascii=False)
                yield self.event("response.function_call_arguments.delta", **refs, delta=item["arguments"])
            # Never emit an executable call with truncated/invalid JSON.
            if item["type"] == "function_call":
                _object(json.loads(item["arguments"]), "generated tool arguments")
            self.finished_calls.add(index)

    def events(self, run, prompt_tokens):
        yield self.event("response.created", response=self.response)
        yield self.event("response.in_progress", response=self.response)
        try:
            for kind, value in run:
                if kind == "ping":
                    yield None
                elif kind == "event":
                    if value.kind == "reasoning" and (self.req.get("reasoning") or {}).get("summary") == "none":
                        yield None
                        continue
                    if value.kind in ("content", "reasoning"):
                        yield from self.text("message" if value.kind == "content" else "reasoning", value.text)
                    else:
                        yield from self.tool(value)
                elif kind == "done":
                    truncated = value["finish"] != "stop"
                    unfinished = any(i not in self.finished_calls for i in self.calls.values())
                    # A truncated tool must not be handed to Codex as executable.
                    if unfinished or (truncated and self.calls):
                        raise ValueError("generation stopped before the tool call completed")
                    for index in range(len(self.output)):
                        yield from self.close(index, incomplete=truncated)
                    n = value["completion_tokens"]
                    cached = min(prompt_tokens, value.get("reused") or 0)
                    self.response["usage"] = {"input_tokens": prompt_tokens, "output_tokens": n,
                        "total_tokens": prompt_tokens + n, "input_tokens_details": {"cached_tokens": cached}}
                    self.response["status"] = "incomplete" if truncated else "completed"
                    if truncated:
                        self.response["incomplete_details"] = {"reason": "max_output_tokens" if value["finish"] == "length" else "interrupted"}
                    yield self.event("response.incomplete" if truncated else "response.completed", response=self.response)
                    return
            raise ValueError("engine stream ended without a completion")
        except (ValueError, RuntimeError) as e:
            self.response.update(status="failed", error={"code": "server_error", "message": str(e)})
            yield self.event("response.failed", response=self.response)
        finally:
            run.close()


def handle_responses(handler, svc, req):
    chat, names = responses_to_chat(req)
    if len(_client_tools(req.get("tools") or [])) != len(req.get("tools") or []):
        _note_web_search_dropped()
    chat = svc.with_shared(chat, "openai")
    messages, tools, kwargs = openai_to_messages(chat)
    budget = int(chat.get("max_completion_tokens") or chat.get("max_tokens") or 0)
    try:
        ids, thinking, budget = svc.prepare(messages, tools, kwargs, budget)
    except ValueError as e:
        if "context" in str(e) and ("exceeds" in str(e) or "leaves no room" in str(e)):
            return handler._json(400, {"error": {"type": "invalid_request_error",
                "code": "context_length_exceeded", "message": str(e)}})
        raise
    cancel = threading.Event()
    state = ResponseStream(svc.model, req, names)
    run = svc.run(ids, thinking, tools, budget, chat, cancel)
    events = state.events(run, len(ids))
    if not req.get("stream"):
        for _ in events:
            pass
        return handler._json(503 if state.response["status"] == "failed" else 200, state.response)
    try:
        handler._sse()
        for event in events:
            if event is None:
                handler.wfile.write(b": keep-alive\n\n")
            else:
                name, value = event
                handler.wfile.write(f"event: {name}\n".encode() + b"data: " +
                                    json.dumps(value, ensure_ascii=False).encode() + b"\n\n")
            handler.wfile.flush()
    except OSError:
        cancel.set()
    finally:
        events.close()
        run.close()
