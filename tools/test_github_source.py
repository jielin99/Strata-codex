import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import setup
from tools.github_source import github_url


class GithubSourceTests(unittest.TestCase):
    def test_opt_in_and_independent_model_source(self):
        url = setup.PREBUILT_URL + setup.PREBUILT_ASSET
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(github_url(url), url)
        with patch.dict(os.environ, {"STRATA_GITHUB_MIRROR": "https://mirror.example/prefix/"}, clear=True):
            self.assertEqual(github_url(url), "https://mirror.example/prefix/" + url)
            self.assertEqual(github_url(setup.LLAMA_CPP_ZIP), "https://mirror.example/prefix/" + setup.LLAMA_CPP_ZIP)
            for other in ("https://modelscope.cn/models/file", "https://huggingface.co/file",
                          "https://pypi.org/file", "https://github.com.evil.example/file",
                          "https://mirror.example/https://github.com/file", "F:/engine/", "file:///F:/engine.zip"):
                self.assertEqual(github_url(other), other)

    def test_reject_bad_prefix(self):
        for prefix in ("socks5://localhost:7890", "http://mirror.example", "https://",
                       "https://user:pass@mirror.example", "https://mirror.example/?q=1",
                       "https://mirror.example/#a", "https://mirror.example/https://github.com/"):
            with self.subTest(prefix=prefix), patch.dict(os.environ, {"STRATA_GITHUB_MIRROR": prefix}):
                with self.assertRaises(ValueError):
                    github_url(setup.LLAMA_CPP_ZIP)

    def test_download_routes_head_and_resumed_get(self):
        class Response(io.BytesIO):
            status = 206
            headers = {"Content-Length": "6", "Content-Range": "bytes 2-5/6"}
        seen = []
        def open_url(req, **kwargs):
            seen.append(req)
            return Response(b"cdef")
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
                "STRATA_GITHUB_MIRROR": "https://mirror.example/"}), patch("urllib.request.urlopen", side_effect=open_url):
            dest = Path(folder) / "engine.zip"
            dest.with_suffix(".zip.part").write_bytes(b"ab")
            setup.download(setup.PREBUILT_URL + setup.PREBUILT_ASSET, dest)
            self.assertEqual(dest.read_bytes(), b"abcdef")
            self.assertTrue(setup.done(dest))
            self.assertEqual([r.get_method() for r in seen], ["HEAD", "GET"])
            self.assertTrue(all(r.full_url.startswith("https://mirror.example/https://github.com/") for r in seen))
            self.assertEqual(seen[1].get_header("Range"), "bytes=2-")
            setup.download(setup.PREBUILT_URL + setup.PREBUILT_ASSET, dest)
            self.assertEqual(len(seen), 2)  # completed files never contact the mirror

    def test_prebuilt_availability_probe_uses_mirror(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup, "ROOT", Path(folder)), patch.dict(os.environ, {
                "STRATA_GITHUB_MIRROR": "https://mirror.example/"}), patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")) as request:
            self.assertIsNone(setup.get_prebuilt(setup.PREBUILT_URL, {"arch": 89}, "none"))
            self.assertEqual(request.call_args.args[0].full_url,
                             "https://mirror.example/" + setup.PREBUILT_URL + setup.PREBUILT_ASSET)


if __name__ == "__main__":
    unittest.main()
