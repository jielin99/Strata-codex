"""Responses structured text plus client tools, through the native HTTP/parser path (no GPU)."""
import json
import unittest
from unittest.mock import patch

from serve import structured
from serve.frontend import Event, ToolCall
from serve.responses import Assembler
from serve.server import MockEngine
from serve.test_responses import Server, TOOLS
from serve.test_server import CallingEngine


FORMAT = {"type": "json_schema", "name": "review", "strict": True, "schema": {
    "type": "object", "properties": {"decision": {"type": "string", "enum": ["allow", "deny"]}},
    "required": ["decision"], "additionalProperties": False}}
ANSWER = '{"decision":"deny"}'
CALL = ('<tool_call>\n<function=exec_command>\n<parameter=cmd>\ndir\n</parameter>\n'
        '</function>\n</tool_call>')


class StructuredTools(Server):
    def scripts(self, *texts):
        self.engine = self.svc.engine = MockEngine(self.tok, list(texts), max_context=16384)

    def request(self, stream=False, **extra):
        return self.post({"model": "qwen3.8-flash-next-iq3_s", "input": "Review this action.",
                          "tools": TOOLS, "text": {"format": FORMAT}, "stream": stream,
                          "reasoning": {"effort": "none"}, **extra})

    def result(self, reply):
        if isinstance(reply, list):
            self.assertEqual([e["sequence_number"] for e in reply], list(range(len(reply))))
            return reply[-1]["response"]
        return reply

    def assert_failed(self, stream, code, reply):
        if stream:
            self.assertEqual(code, 200)
            self.assertEqual(reply[-1]["type"], "response.failed")
            self.assertFalse(any(e["type"] in ("response.output_text.delta",
                                               "response.function_call_arguments.done",
                                               "response.custom_tool_call_input.done",
                                               "response.completed") for e in reply))
        else:
            self.assertEqual(code, 502, reply)
        self.assertEqual(self.result(reply)["error"]["code"], "structured_output_failed")

    def test_direct_answer_with_optional_tools(self):
        for stream in (False, True):
            for fmt in (FORMAT, {"type": "json_object"}):
                with self.subTest(stream=stream, format=fmt["type"]):
                    self.scripts(ANSWER)
                    code, reply = self.request(stream, text={"format": fmt})
                    self.assertEqual(code, 200, reply)
                    r = self.result(reply)
                    self.assertEqual(r["status"], "completed")
                    self.assertEqual(r["output"][0]["content"][0]["text"], ANSWER)
                    self.assertIn("normal tool-call format", self.tok.decode(self.engine.last_prompt))

    def test_function_round_trip_with_reasoning_and_schema(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                self.scripts("Check first.</think>\n\n" + CALL, "Decide.</think>\n\n" + ANSWER)
                opts = {"reasoning": {"effort": "medium"}, "include": ["reasoning.encrypted_content"]}
                code, reply = self.request(stream, **opts)
                self.assertEqual(code, 200, reply)
                first = self.result(reply)
                self.assertEqual(first["status"], "completed")
                self.assertEqual([o["type"] for o in first["output"]], ["reasoning", "function_call"])
                call = first["output"][-1]
                self.assertEqual(json.loads(call["arguments"]), {"cmd": "dir"})
                self.assertEqual(call["status"], "completed")
                if stream:
                    self.assertFalse(any(e["type"] == "response.output_text.delta" for e in reply))
                    added = next(e for e in reply if e["type"] == "response.output_item.added"
                                 and e["item"]["type"] == "function_call")
                    self.assertEqual(added["item"]["arguments"], "")
                history = [{"role": "user", "content": "Review this action."}, *first["output"],
                           {"type": "function_call_output", "call_id": call["call_id"], "output": "file.txt"}]
                code, reply = self.request(stream, input=history, **opts)
                self.assertEqual(code, 200, reply)
                self.assertEqual(self.result(reply)["output"][-1]["content"][0]["text"], ANSWER)
                self.assertIn("<tool_response>\nfile.txt\n</tool_response>", self.tok.decode(self.engine.last_prompt))

    def test_namespace_custom_parallel_calls_and_replay(self):
        tools = [{"type": "namespace", "name": "files", "tools": [{**TOOLS[0], "name": "read"}]},
                 {"type": "custom", "name": "inspect", "description": "Inspect text."}]
        script = CALL.replace("exec_command", "files.read") + '\n' + (
            '<tool_call>\n<function=inspect>\n<parameter=input>\nraw text\n</parameter>\n'
            '</function>\n</tool_call>')
        for stream in (False, True):
            self.scripts(script, ANSWER)
            code, reply = self.request(stream, tools=tools)
            self.assertEqual(code, 200, reply)
            ns, custom = self.result(reply)["output"]
            self.assertEqual((ns["namespace"], ns["name"]), ("files", "read"))
            self.assertEqual((custom["type"], custom["input"]), ("custom_tool_call", "raw text"))
            history = [{"role": "user", "content": "Review."}, ns, custom,
                       {"type": "function_call_output", "call_id": ns["call_id"], "output": "one"},
                       {"type": "custom_tool_call_output", "call_id": custom["call_id"], "output": "two"}]
            code, reply = self.request(stream, tools=tools, input=history)
            self.assertEqual(code, 200, reply)
            self.assertEqual(self.result(reply)["output"][-1]["content"][0]["text"], ANSWER)

    def test_mixed_valid_text_preserves_order(self):
        for stream in (False, True):
            self.scripts(ANSWER + '\n' + CALL + '\n' + ANSWER)
            code, reply = self.request(stream)
            self.assertEqual(code, 200, reply)
            out = self.result(reply)["output"]
            self.assertEqual([o["type"] for o in out], ["message", "function_call", "message"])
            self.assertEqual(out[0]["content"][0]["text"], ANSWER)
            self.assertEqual(out[2]["content"][0]["text"], ANSWER)

    def test_invalid_text_cannot_hide_behind_a_tool_call(self):
        for script in ('Checking.\n' + CALL, CALL + '\nChecking.', CALL + '\n{"decision":"maybe"}'):
            for stream in (False, True):
                with self.subTest(script=script, stream=stream):
                    self.scripts(script)
                    self.assert_failed(stream, *self.request(stream))

    def test_invalid_answers_and_empty_outputs_fail(self):
        for script in ('', ' ', '{}', '{"decision":1}', '{"decision":"maybe"}',
                       '{"decision":"deny","extra":1}', '{"decision":"allow","decision":"deny"}',
                       '```json\n' + ANSWER + '\n```', ANSWER + ANSWER,
                       'Explanation. ' + ANSWER, '{"decision":NaN}'):
            for stream in (False, True):
                with self.subTest(script=script, stream=stream):
                    self.scripts(script)
                    self.assert_failed(stream, *self.request(stream))

    def test_token_limits_are_incomplete_without_unvalidated_text(self):
        for script, limit in ((ANSWER, 5), (CALL, CALL.index("dir") + 1)):
            for stream in (False, True):
                with self.subTest(script=script, stream=stream):
                    self.scripts(script)
                    code, reply = self.request(stream, max_output_tokens=limit)
                    self.assertEqual(code, 200, reply)
                    r = self.result(reply)
                    self.assertEqual(r["status"], "incomplete")
                    self.assertEqual(r["incomplete_details"], {"reason": "max_output_tokens"})
                    self.assertFalse(any(o["type"] == "message" for o in r["output"]))
                    if script == CALL:
                        self.assertEqual(r["output"][-1]["status"], "incomplete")
                    if stream:
                        self.assertEqual(reply[-1]["type"], "response.incomplete")

    def test_none_and_hosted_tools_do_not_block_json(self):
        for extra in ({"tool_choice": "none"}, {"tools": [{"type": "web_search"}]}):
            self.scripts(ANSWER)
            code, reply = self.request(**extra)
            self.assertEqual(code, 200, reply)
            self.assertNotIn("normal tool-call format", self.tok.decode(self.engine.last_prompt))

    def test_forced_tool_choices_use_native_engine_prefix(self):
        tools = [{**TOOLS[0], "name": "search"}]
        for choice in ("required", {"type": "function", "name": "search"}):
            for effort in ("none", "medium"):
                for stream in (False, True):
                    with self.subTest(choice=choice, effort=effort, stream=stream):
                        self.engine = self.svc.engine = CallingEngine(self.tok)
                        code, reply = self.request(stream, tools=tools, tool_choice=choice,
                                                   reasoning={"effort": effort})
                        self.assertEqual(code, 200, reply)
                        self.assertEqual(self.result(reply)["output"][-1]["name"], "search")

    def test_unavailable_choices_are_request_errors(self):
        with patch.object(self.svc, "load") as load:
            for choice in ({"type": "function", "name": "missing"}, {"type": "web_search"},
                           {"type": "allowed_tools", "tools": []}, "unknown"):
                code, reply = self.request(tool_choice=choice)
                self.assertEqual(code, 400, reply)
                self.assertEqual(reply["error"]["param"], "tool_choice")
            code, _ = self.request(tools=[], tool_choice="required")
            self.assertEqual(code, 400)
            load.assert_not_called()

    def test_forced_namespace_and_custom_tools(self):
        cases = [
            ([{"type": "namespace", "name": "files", "tools": [{**TOOLS[0], "name": "read"}]}],
             {"type": "function", "namespace": "files", "name": "read"},
             '<parameter=cmd>\ndir\n</parameter>\n</function>\n</tool_call>', "function_call"),
            ([{"type": "custom", "name": "inspect"}], {"type": "custom", "name": "inspect"},
             '<parameter=input>\nraw text\n</parameter>\n</function>\n</tool_call>', "custom_tool_call"),
        ]
        for tools, choice, script, kind in cases:
            for stream in (False, True):
                with self.subTest(choice=choice, stream=stream):
                    self.scripts(script)             # the forced opening is already in the prompt
                    code, reply = self.request(stream, tools=tools, tool_choice=choice)
                    self.assertEqual(code, 200, reply)
                    call, = self.result(reply)["output"]
                    self.assertEqual((call["type"], call["name"]), (kind, choice["name"]))
                    self.assertEqual(call.get("namespace"), choice.get("namespace"))

    def test_local_schema_references_are_validated(self):
        schema = {"type": "object", "$defs": {"decision": {"enum": ["allow", "deny"]}},
                  "properties": {"decision": {"$ref": "#/$defs/decision"}},
                  "required": ["decision"], "additionalProperties": False}
        for stream in (False, True):
            self.scripts(ANSWER)
            code, reply = self.request(stream, text={"format": {**FORMAT, "schema": schema}})
            self.assertEqual(code, 200, reply)
            self.scripts('{"decision":"maybe"}')
            self.assert_failed(stream, *self.request(stream, text={"format": {**FORMAT, "schema": schema}}))

    def test_parallel_false_rejects_multiple_calls(self):
        for stream in (False, True):
            self.scripts(CALL + '\n' + CALL)
            self.assert_failed(stream, *self.request(stream, parallel_tool_calls=False))

    def test_strict_missing_dependency_and_bad_schema_fail_before_load(self):
        with patch.object(structured, "_jsonschema", False), patch.object(self.svc, "load") as load:
            code, reply = self.request()
            self.assertEqual(code, 400, reply)
            self.assertIn("requires jsonschema", reply["error"]["message"])
            load.assert_not_called()
        with patch.object(self.svc, "load") as load:
            for schema in ({"type": "object", "properties": {"x": {"type": "not-a-type"}}},
                           {"type": "object", "$ref": "https://example.com/schema"}):
                code, reply = self.request(text={"format": {**FORMAT, "schema": schema}})
                self.assertEqual(code, 400, reply)
            load.assert_not_called()


class AssemblerEdges(unittest.TestCase):
    def test_unknown_tool_cannot_bypass_validation(self):
        asm = Assembler({}, "m", 0, {}, False, True)
        asm.feed(Event("tool_call", call=ToolCall("invented", {})))
        with self.assertRaisesRegex(structured.StructuredOutputError, "unknown tool"):
            asm.finish({"finish": "stop"})

    def test_unfinished_call_without_token_limit_is_not_completed(self):
        asm = Assembler({}, "m", 0, {"exec_command": (None, "exec_command", "function")}, False, True)
        asm.feed(Event("tool_start", call=ToolCall("exec_command", {})))
        with self.assertRaisesRegex(structured.StructuredOutputError, "unfinished tool call"):
            asm.finish({"finish": "stop"})

    def test_required_and_named_choices_cannot_succeed_without_call(self):
        for choice in ("required", {"type": "function", "name": "exec_command"}):
            asm = Assembler({"tool_choice": choice}, "m", 0, {}, False, True)
            asm.feed(Event("content", text=ANSWER))
            with self.assertRaises(structured.StructuredOutputError):
                asm.finish({"finish": "stop"})


if __name__ == "__main__":
    unittest.main()
