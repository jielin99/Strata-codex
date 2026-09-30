"""Small, dependency-free download source adapter shared by setup and MTP fetch.

Keep upstream Hugging Face URLs at call sites. Only opt-in downloads are rewritten;
non-model URLs and local paths pass through unchanged.
"""
import json
import os
from urllib.parse import quote, unquote, urlsplit


def model_url(url: str) -> str:
    if os.environ.get("STRATA_USE_MODELSCOPE") != "1":
        return url
    parts = urlsplit(url)
    if parts.hostname != "huggingface.co":
        return url
    path = parts.path.lstrip("/").split("/", 4)
    if len(path) != 5 or path[2] != "resolve":
        return url
    repo = "/".join(path[:2])
    overrides = json.loads(os.environ.get("STRATA_MODELSCOPE_REPOS", "{}"))
    if not isinstance(overrides, dict):
        raise ValueError("STRATA_MODELSCOPE_REPOS must be a JSON object")
    target = overrides.get(repo, repo)
    if not isinstance(target, str) or len(target.split("/")) != 2 or any(
            not p or p in (".", "..") for p in target.split("/")):
        raise ValueError(f"invalid ModelScope repository for {repo!r}")
    revision = "master" if path[3] == "main" else unquote(path[3])
    return (f"https://modelscope.cn/models/{quote(target, safe='/')}/resolve/"
            f"{quote(revision, safe='')}/{path[4]}")
