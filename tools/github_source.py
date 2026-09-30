"""Opt-in URL-prefix acceleration for public GitHub setup downloads."""
import os
from urllib.parse import urlsplit


def github_url(url):
    prefix = os.environ.get("STRATA_GITHUB_MIRROR", "").strip()
    source = urlsplit(url)
    if not prefix or source.scheme != "https" or source.hostname != "github.com":
        return url
    mirror = urlsplit(prefix)
    if (mirror.scheme != "https" or not mirror.hostname or mirror.username or mirror.password
            or mirror.query or mirror.fragment or "https://" in mirror.path
            or source.username or source.password):
        raise ValueError("STRATA_GITHUB_MIRROR must be an HTTPS prefix, e.g. https://gh-proxy.org/")
    return prefix.rstrip("/") + "/" + url
