"""Run an installed Codex CLI against Strata's real HTTP/parser pipeline and a scripted engine.

No inference service or weights required. Only writes a marker under logs/codex-smoke.
    python -m serve.codex_smoke
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from serve.frontend import ChatTemplate
from serve.server import ByteTokenizer, MockEngine, Service, make_handler, Server
import threading

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--codex", default=shutil.which("codex"))
    ap.add_argument("--require-tool-success", action="store_true",
                    help="also require actual shell and apply_patch success (needs a writable Codex sandbox)")
    args = ap.parse_args()
    if not args.codex:
        ap.error("Codex CLI not found; install it or pass --codex PATH")
    workspace = ROOT / "logs" / "codex-smoke"
    workspace.mkdir(parents=True, exist_ok=True)
    cli_home = workspace / "cli-home"
    cli_home.mkdir(exist_ok=True)
    marker = workspace / "responses-smoke.txt"
    marker.unlink(missing_ok=True)
    tok = ByteTokenizer()
    shell = '<tool_call>\n<function=exec_command>\n<parameter=cmd>\nWrite-Output STRATA_SHELL_OK\n</parameter>\n</function>\n</tool_call>'
    patch = '<tool_call>\n<function=apply_patch>\n<parameter=input>\n*** Begin Patch\n*** Add File: responses-smoke.txt\n+STRATA_PATCH_OK\n*** End Patch\n</parameter>\n</function>\n</tool_call>'
    engine = MockEngine(tok, ["</think>\n\n" + shell, "</think>\n\n" + patch,
                              "</think>\n\nSTRATA_CODEX_OK"], max_context=262144)
    svc = Service(engine, tok, ChatTemplate(ROOT / "serve/chat_template.jinja"))
    svc.api_key = "strata-smoke-test"
    requests = []
    base_handler = make_handler(svc)

    class RecordingHandler(base_handler):
        def do_POST(self):
            # Inspect only the smoke request. Preserve bytes for the actual route.
            import io
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            req = json.loads(raw)
            requests.append(req)
            if len(requests) == 1:
                tools = []
                for tool in req.get("tools", []):
                    if tool.get("type") == "namespace":
                        tools.extend((f'{tool["name"]}.{t["name"]}', t) for t in tool.get("tools", []))
                    else:
                        tools.append((tool.get("name"), tool))
                print("Codex tools:", [(name, t.get("type")) for name, t in tools], flush=True)
                shell_name = next((name for name, _ in tools if name and name.split(".")[-1] == "exec_command"), None)
                patch_name = next((name for name, _ in tools if name and name.split(".")[-1] == "apply_patch"), None)
                if shell_name and patch_name:
                    scripts = ["</think>\n\n" + shell.replace("function=exec_command", f"function={shell_name}"),
                               "</think>\n\n" + patch.replace("function=apply_patch", f"function={patch_name}"), "</think>\n\nSTRATA_CODEX_OK"]
                    engine.scripts = [tok.encode(s, parse_special=True) + tok.encode("<|im_end|>", parse_special=True) for s in scripts]
            self.rfile = io.BytesIO(raw)
            super().do_POST()

    httpd = Server(("127.0.0.1", 0), RecordingHandler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    command = [args.codex, "exec", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
        "--ignore-user-config", "--sandbox", "workspace-write", "--cd", str(workspace), "--json",
        "-c", 'approval_policy="never"',
        "-c", 'model_provider=lan',
        "-c", 'model_providers.lan.name=LAN',
        "-c", f'model_providers.lan.base_url=http://127.0.0.1:{httpd.server_address[1]}/v1',
        "-c", 'model_providers.lan.env_key=LAN_API_KEY',
        "-c", 'model_providers.lan.requires_openai_auth=false',
        "-c", 'model_providers.lan.wire_api=responses',
        "-c", 'model_providers.lan.supports_websockets=false',
        "-c", 'model_providers.lan.stream_idle_timeout_ms=1800000',
        "-c", 'model_providers.lan.request_max_retries=0',
        "-c", 'model_providers.lan.stream_max_retries=0',
        "-c", 'model_context_window=65536', "-c", 'model_auto_compact_token_limit=60000',
        "-c", 'model_auto_compact_token_limit_scope=total',
        "-c", 'model_reasoning_effort=medium', "-c", 'plan_mode_reasoning_effort=medium',
        "-c", 'agents.enabled=false',
        "-c", 'web_search="disabled"',
        "-c", f"model_catalog_json='{(ROOT / 'docs/codex-models.json').as_posix()}'",
        "-m", "strata-local", "--disable", "apps",
        "Run the scripted local protocol test: echo STRATA_SHELL_OK, add responses-smoke.txt containing STRATA_PATCH_OK, and reply STRATA_CODEX_OK."]
    # Isolated home prevents smoke tests from reading user credentials/plugins or
    # changing their real configuration. The provider talks only to loopback.
    env = dict(os.environ, CODEX_HOME=str(cli_home), LAN_API_KEY=svc.api_key)
    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90)
        (workspace / "stdout.jsonl").write_text(result.stdout, encoding="utf-8")
        (workspace / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        print(result.stdout)
        if result.returncode:
            print(result.stderr)
        outputs = [item for req in requests for item in req.get("input", []) if isinstance(item, dict) and
                   item.get("type") in ("function_call_output", "custom_tool_call_output")]
        (workspace / "tool-results.json").write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
        assert result.returncode == 0, f"Codex exited {result.returncode}; see {workspace}"
        assert len(requests) >= 3, "Codex did not complete both tool rounds"
        assert any(i["type"] == "function_call_output" for i in outputs), "shell result was not replayed"
        assert any(i["type"] == "custom_tool_call_output" for i in outputs), "custom tool result was not replayed"
        assert "STRATA_CODEX_OK" in result.stdout, "Codex did not accept the final response"
        shell_ok = any("STRATA_SHELL_OK" in i.get("output", "") and "failed" not in i.get("output", "")
                       for i in outputs if isinstance(i.get("output"), str))
        patch_ok = marker.exists() and marker.read_text().strip() == "STRATA_PATCH_OK"
        if args.require_tool_success:
            assert shell_ok and patch_ok, f"tool execution failed; see {workspace / 'tool-results.json'}"
        print(f"PASS protocol: Codex accepted text, function/custom tools and {len(requests)} HTTP turns")
        print(f"Actual execution: shell={shell_ok}, apply_patch={patch_ok}; tool results: {workspace / 'tool-results.json'}")
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    main()
