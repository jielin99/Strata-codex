"""Small, dependency-free download source adapter shared by setup and MTP fetch.

Keep upstream Hugging Face URLs at call sites. Only opt-in downloads are rewritten;
non-model URLs and local paths pass through unchanged.
"""
import json
import os
import re
from urllib.parse import quote, unquote, urlsplit


def model_url(url: str) -> str:
    if os.environ.get("STRATA_USE_MODELSCOPE") != "1":
        return url
    parts = urlsplit(url)
    endpoint = urlsplit((os.environ.get("HF_ENDPOINT") or "https://huggingface.co").rstrip("/"))
    path_text = parts.path
    if parts.hostname == "huggingface.co":
        pass
    elif (parts.scheme, parts.netloc) == (endpoint.scheme, endpoint.netloc):
        prefix = endpoint.path.rstrip("/") + "/"
        if not path_text.startswith(prefix):
            return url
        path_text = path_text[len(prefix):]
    else:
        return url
    path = path_text.lstrip("/").split("/", 4)
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
    revisions = json.loads(os.environ.get("STRATA_MODELSCOPE_REVISIONS", "{}"))
    if not isinstance(revisions, dict):
        raise ValueError("STRATA_MODELSCOPE_REVISIONS must be a JSON object")
    logical_revision = unquote(path[3])
    # HF and ModelScope commit IDs belong to different repositories. The source's
    # master is the default; MTP still checks the logical pinned checkpoint's hashes.
    revision = revisions.get(repo, "master" if logical_revision == "main" or
                             re.fullmatch(r"[0-9a-fA-F]{40}", logical_revision) else logical_revision)
    if not isinstance(revision, str) or not revision or revision in (".", ".."):
        raise ValueError(f"invalid ModelScope revision for {repo!r}")
    return (f"https://modelscope.cn/models/{quote(target, safe='/')}/resolve/"
            f"{quote(revision, safe='')}/{path[4]}")


def model_fallback_url(url: str) -> str:
    """Only HF revisions fall back to main; a selected ModelScope revision stays selected."""
    if urlsplit(url).hostname == "modelscope.cn":
        return url
    return re.sub(r"^(https?://[^/]+/.+?/resolve/)[0-9a-fA-F]{40}/", r"\1main/", url, count=1)
