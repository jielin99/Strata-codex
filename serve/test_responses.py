"""Protocol tests over HTTP and the real shared parser/MockEngine (no model/GPU)."""
import json
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from serve.frontend import ChatTemplate, Event, ToolCall
from serve.responses import ResponseStream, responses_to_chat
from serve.server import ByteTokenizer, EngineDied, MockEngine, Service, serve

ROOT = Path(__file__).resolve().parents[1]
FUNCTION = {"type": "function", "name": "exec_command", "parameters": {
    "type": "object", "properties": {"cmd": {"type": "string"}}}}
CUSTOM = {"type": "custom", "name": "apply_patch", "format": {"type": "text"}}


def call(name, parameter, value):
    return f"<tool_call>\n<function={name}>\n<parameter={parameter}>\n{value}\n</parameter>\n</function>\n</tool_call>"


class ResponsesHTTP(unittest.TestCase):
    def start(self, script="</think>\n\n你好", engine_type=MockEngine, **svc_options):
        tok = ByteTokenizer()
        self.engine = engine_type(tok, script, max_context=65536)
        self.svc = Service(self.engine, tok, ChatTemplate(ROOT / "serve/chat_template.jinja"))
        for key, value in svc_options.items():
            setattr(self.svc, key, value)
        self.httpd = serve(self.svc, port=0)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def post(self, body, path="/v1/responses", headers=None):
        body = {"model": "local", "input": "hello", "store": False, **body}
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as e:
            response = e
        with response as r:
            raw = r.read().decode()
            if "text/event-stream" in r.headers.get("Content-Type", ""):
                return r.status, [json.loads(line[6:]) for line in raw.splitlines() if line.startswith("data: ")]
            return r.status, json.loads(raw)

    def test_text_reasoning_lifecycle_usage_and_non_stream(self):
        self.start("先思考</think>\n\n你好😀")
        for stream in (False, True):
            status, result = self.post({"stream": stream})
            self.assertEqual(status, 200)
            if stream:
                types = [e["type"] for e in result]
                self.assertEqual(types[:2], ["response.created", "response.in_progress"])
                self.assertEqual(types[-1], "response.completed")
                self.assertEqual([e["sequence_number"] for e in result], list(range(len(result))))
                self.assertEqual(result[0]["response"]["output"], [])
                self.assertIn("response.reasoning_summary_text.done", types)
                self.assertIn("response.content_part.done", types)
                final = result[-1]["response"]
                self.assertEqual([e["item"] for e in result if e["type"] == "response.output_item.done"], final["output"])
                self.assertEqual("".join(e["delta"] for e in result if e["type"] == "response.output_text.delta"), "你好😀")
            else:
                final = result
            self.assertEqual(final["status"], "completed")
            self.assertEqual(final["output"][0]["summary"][0]["text"], "先思考")
            self.assertEqual(final["output"][1]["content"][0]["text"], "你好😀")
            usage = final["usage"]
            self.assertEqual(usage["total_tokens"], usage["input_tokens"] + usage["output_tokens"])

    def test_function_custom_namespace_and_history(self):
        patch_text = '*** Begin Patch\n*** Add File: x\n+中文\\"😀\n*** End Patch'
        self.start(["think</think>\n\n" + call("functions.exec_command", "cmd", "echo 中文") +
                    call("apply_patch", "input", patch_text), "</think>\n\n完成"])
        tools = [{"type": "namespace", "name": "functions", "tools": [FUNCTION]}, CUSTOM]
        _, events = self.post({"stream": True, "tools": tools})
        final = events[-1]["response"]
        functions = [i for i in final["output"] if i["type"] == "function_call"]
        custom = [i for i in final["output"] if i["type"] == "custom_tool_call"]
        self.assertEqual(functions[0]["namespace"], "functions")
        self.assertEqual(functions[0]["name"], "exec_command")
        self.assertEqual(json.loads(functions[0]["arguments"]), {"cmd": "echo 中文"})
        self.assertEqual(custom[0]["input"], patch_text)
        arguments = "".join(e["delta"] for e in events if e["type"] == "response.function_call_arguments.delta")
        self.assertEqual(arguments, functions[0]["arguments"])
        self.assertIn("response.custom_tool_call_input.done", [e["type"] for e in events])
        history = [{"role": "user", "content": "run"}] + final["output"] + [
            {"type": "function_call_output", "call_id": functions[0]["call_id"], "output": "shell done"},
            {"type": "custom_tool_call_output", "call_id": custom[0]["call_id"], "output": [
                {"type": "input_text", "text": "patch done"}]}]
        status, answer = self.post({"input": history, "tools": tools})
        self.assertEqual(status, 200, answer)
        prompt = self.svc.tok.decode(self.engine.last_prompt)
        for value in ("shell done", "patch done", "echo 中文", "*** Begin Patch"):
            self.assertIn(value, prompt)
        self.assertEqual(answer["output"][0]["content"][0]["text"], "完成")

    def test_budget_incomplete_and_validation(self):
        self.start("x" * 50)
        status, result = self.post({"stream": True, "max_output_tokens": 5, "reasoning": {"effort": "none"}})
        self.assertEqual(status, 200)
        self.assertEqual(result[-1]["type"], "response.incomplete")
        self.assertEqual(result[-1]["response"]["incomplete_details"]["reason"], "max_output_tokens")
        self.assertEqual(result[-1]["response"]["usage"]["output_tokens"], 5)
        for data in ({"previous_response_id": "resp_old"}, {"store": True}, {"background": True},
                     {"max_output_tokens": -1}, {"max_output_tokens": "5"}, {"tools": [{"type": "web_search"}]},
                     {"input": [{"type": "item_reference", "id": "abc"}]}, {"text": {"format": "bad"}},
                     {"tool_choice": "required"}, {"input": 123}):
            with self.subTest(data=data):
                code, body = self.post(data)
                self.assertEqual(code, 400, body)
                self.assertEqual(body["error"]["type"], "invalid_request_error")

    def test_auth_and_path_normalization(self):
        self.start(api_key="secret")
        self.assertEqual(self.post({})[0], 401)
        status, result = self.post({}, path="/v1/responses/?beta=true", headers={"Authorization": "Bearer secret"})
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "completed")

    def test_reasoning_none_tool_none_and_context_error(self):
        self.start("thinking</think>\n\ntext")
        status, result = self.post({"reasoning": {"summary": "none"}, "tools": [FUNCTION], "tool_choice": "none"})
        self.assertEqual(status, 200)
        self.assertEqual([i["type"] for i in result["output"]], ["message"])
        prompt = self.svc.tok.decode(self.engine.last_prompt)
        self.assertNotIn("exec_command", prompt)
        status, result = self.post({"input": "x" * 65536})
        self.assertEqual(status, 400)
        self.assertEqual(result["error"]["code"], "context_length_exceeded")

    def test_shared_defaults_request_sampling_and_budget(self):
        class Recording(MockEngine):
            def generate(self, ids, budget, sampling, cancel, **kwargs):
                self.sampling, self.budget = sampling, budget
                yield from super().generate(ids, budget, sampling, cancel, **kwargs)
        self.start("answer", engine_type=Recording)
        self.svc.shared = {"temperature": 0.9, "reasoning_effort": "none", "max_tokens": 100}
        status, result = self.post({"temperature": 0.2, "top_p": 0.8, "max_output_tokens": 10})
        self.assertEqual(status, 200)
        self.assertEqual(self.engine.budget, 10)
        self.assertEqual(self.engine.sampling["temperature"], 0.2)
        self.assertEqual(self.engine.sampling["top_p"], 0.8)
        self.assertEqual(result["output"][0]["type"], "message")

    def test_engine_failure_sse_and_json(self):
        class Dying(MockEngine):
            def generate(self, *args, **kwargs):
                yield self.tok.encode("x")[0]
                raise EngineDied("test engine failure")
        self.start(engine_type=Dying)
        status, events = self.post({"stream": True})
        self.assertEqual(status, 200)
        self.assertEqual(events[-1]["type"], "response.failed")
        self.assertIn("test engine failure", events[-1]["response"]["error"]["message"])
        self.assertEqual(self.post({})[0], 503)
        self.assertFalse(self.svc.status["busy"])

    def test_disconnect_releases_engine(self):
        class Slow(MockEngine):
            def generate(self, *args, **kwargs):
                self.delay = 0.002
                yield from super().generate(*args, **kwargs)
        self.start("x" * 3000, engine_type=Slow)
        sock = socket.create_connection(self.httpd.server_address, timeout=5)
        body = json.dumps({"input": "hi", "stream": True, "reasoning": {"effort": "none"}}).encode()
        sock.sendall(b"POST /v1/responses HTTP/1.0\r\nContent-Type: application/json\r\nContent-Length: " +
                     str(len(body)).encode() + b"\r\n\r\n" + body)
        sock.recv(4096)
        sock.close()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and (not self.svc.totals["requests"] or self.svc.status["busy"]):
            time.sleep(0.02)
        self.assertFalse(self.svc.status["busy"])
        self.assertLess(self.svc.totals["output_tokens"], 3000)


class ResponsesAdapter(unittest.TestCase):
    def test_initial_instructions_notifications_and_images(self):
        chat, _ = responses_to_chat({"instructions": "system", "input": [
            {"role": "developer", "content": [{"type": "input_text", "text": "developer"}]},
            {"role": "user", "content": [{"type": "input_text", "text": "see"},
                {"type": "input_image", "image_url": "data:image/png;base64,abc"}]},
            {"type": "function_call_output", "name": "notify", "namespace": "slack", "output": "Alice"}]})
        self.assertEqual(chat["messages"][0], {"role": "system", "content": "system\ndeveloper"})
        self.assertEqual(chat["messages"][1]["content"][1]["type"], "input_image")
        self.assertIn("slack.notify", chat["messages"][2]["content"])

    def test_no_executable_done_on_truncated_tool(self):
        req = {"tools": [FUNCTION]}
        _, names = responses_to_chat({**req, "input": "hi"})
        state = ResponseStream("local", req, names)
        tc = ToolCall("exec_command", {"cmd": "partial"})
        def run():
            yield "event", Event("tool_start", call=tc)
            yield "event", Event("tool_args", '{"cmd":"partial"}', call=tc)
            yield "event", Event("tool_call", call=tc)
            yield "done", {"finish": "length", "completion_tokens": 30}
        events = [e[1] for e in state.events(run(), 10) if e is not None]
        self.assertEqual(events[-1]["type"], "response.failed")
        self.assertNotIn("response.output_item.done", [e["type"] for e in events])


if __name__ == "__main__":
    unittest.main()
