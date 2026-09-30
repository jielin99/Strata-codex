"""Build a Qwen3.8-Flash-Next Codex catalog from Strata deployment metadata.

Uses only the standard library. Does not download weights or change Codex config.
    python -m tools.codex_catalog --base-url http://127.0.0.1:8080/v1
    python -m tools.codex_catalog --config strata-iq2_xs.json
"""
import argparse
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs/codex-qwen3.8-flash-next.json"
NATIVE_CONTEXT = 262144


def positive_int(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def metadata_from_config(cfg):
    """Offline fallback: setup.py writes model_name, --max-context and vision."""
    if not isinstance(cfg, dict) or not isinstance(cfg.get("args"), list):
        raise ValueError("Strata config must be an object with an args array")
    args = cfg.get("args", [])
    try:
        context = int(args[args.index("--max-context") + 1])
    except (ValueError, IndexError, TypeError):
        raise ValueError("config is missing a valid --max-context; use the running /v1/models endpoint") from None
    return {"id": cfg.get("model_name"), "meta": {"n_ctx": context},
            "architecture": {"input_modalities": ["text", "image"] if cfg.get("vision") else ["text"]}}


def fetch_metadata(base_url, api_key=""):
    url = urllib.parse.urlsplit(base_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("base URL must be an HTTP(S) provider URL without embedded credentials, query or fragment")
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = urllib.request.Request(base_url.rstrip("/") + "/models", headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("model metadata exceeds 1 MiB")
    payload = json.loads(raw)
    models = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(models, list) or len(models) != 1:
        raise ValueError("expected exactly one loaded Strata model")
    return models[0]


def build_catalog(metadata, context_window=None, auto_compact=None):
    """Bind the researched profile to the actual model ID, context and modalities."""
    if not isinstance(metadata, dict) or not isinstance(metadata.get("meta"), dict) or not isinstance(metadata.get("architecture"), dict):
        raise ValueError("Strata metadata must include meta.n_ctx and architecture.input_modalities")
    slug = metadata.get("id")
    if not isinstance(slug, str) or not (slug == "qwen3.8-flash-next" or slug.startswith("qwen3.8-flash-next-")) or "coder" in slug:
        raise ValueError("this profile targets original qwen3.8-flash-next; Swift/Coder/other models need separate research")
    loaded_context = positive_int(metadata.get("meta", {}).get("n_ctx"), "deployment n_ctx")
    if loaded_context > NATIVE_CONTEXT:
        raise ValueError("context exceeds the researched native 262144 limit; extended-context deployments are not covered")
    context = loaded_context if context_window is None else positive_int(context_window, "context window")
    if context > loaded_context:
        raise ValueError("catalog context cannot exceed the deployment n_ctx")
    compact = context * 3 // 4 if auto_compact is None else positive_int(auto_compact, "auto compact limit")
    if compact <= 0 or compact > context * 9 // 10:
        raise ValueError("auto compact limit must be positive and at most 90% of the catalog context")
    modalities = metadata.get("architecture", {}).get("input_modalities")
    if not isinstance(modalities, list) or not modalities or "text" not in modalities or any(m not in ("text", "image") for m in modalities):
        raise ValueError("deployment must report text and optional image input modalities")
    catalog = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    model = catalog["models"][0]
    model.update(slug=slug, display_name=f"{slug} (Strata)",
                 description="Community Codex profile for original Qwen3.8-Flash-Next; bound to Strata deployment metadata",
                 context_window=context, max_context_window=context,
                 auto_compact_token_limit=compact,
                 input_modalities=[m for m in ("text", "image") if m in modalities])
    return catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--base-url", help="Strata provider URL ending in /v1 (default: LLM_BASE_URL or loopback)")
    source.add_argument("--config", type=Path, help="offline setup-generated Strata JSON config")
    parser.add_argument("--output", type=Path, default=ROOT / "logs/codex-models.json")
    parser.add_argument("--context-window", type=int, help="optional lower context cap")
    parser.add_argument("--auto-compact", type=int, help="default: 75%% of chosen context")
    args = parser.parse_args()
    try:
        if args.config:
            metadata = metadata_from_config(json.loads(args.config.read_text(encoding="utf-8-sig")))
        else:
            metadata = fetch_metadata(args.base_url or os.environ.get("LLM_BASE_URL") or "http://127.0.0.1:8080/v1",
                                      os.environ.get("LAN_API_KEY", ""))
        catalog = build_catalog(metadata, args.context_window, args.auto_compact)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Catalog generation failed: {error}\n")
    model = catalog["models"][0]
    print(f"Catalog: {args.output.resolve()}")
    print(f"LLM_MODEL={model['slug']}")
    print(f"LLM_CONTEXT_WINDOW={model['context_window']}")
    print(f"LLM_AUTO_COMPACT={model['auto_compact_token_limit']}")
    print(f"Input modalities: {', '.join(model['input_modalities'])}")
    print("Offline config read; verify against the running service before use." if args.config else
          "Live deployment metadata loaded; real model tool quality still requires validation.")


if __name__ == "__main__":
    main()
