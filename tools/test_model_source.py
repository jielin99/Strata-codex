import io
import os
import json
import urllib.error
import unittest
from unittest.mock import patch

from tools.model_source import model_url, model_fallback_url
from tools import mtp_fetch


class ModelSourceTests(unittest.TestCase):
    def test_default_and_non_model_urls(self):
        url = "https://huggingface.co/Qwen/model/resolve/main/file.bin"
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(model_url(url), url)
        with patch.dict(os.environ, {"STRATA_USE_MODELSCOPE": "1"}, clear=True):
            for other in ("https://github.com/release.zip", "C:/models/file.gguf",
                          "https://huggingface.co/Qwen/model"):
                self.assertEqual(model_url(other), other)

    def test_source_and_repo_override(self):
        with patch.dict(os.environ, {"STRATA_USE_MODELSCOPE": "1"}, clear=True):
            self.assertEqual(model_url("https://huggingface.co/ISTA-DASLab/model/resolve/main/IQ2_XS/a.gguf"),
                             "https://modelscope.cn/models/ISTA-DASLab/model/resolve/master/IQ2_XS/a.gguf")
            os.environ["STRATA_MODELSCOPE_REPOS"] = '{"Qwen/model":"mirror/model"}'
            self.assertEqual(model_url("https://huggingface.co/Qwen/model/resolve/v2/a.bin"),
                             "https://modelscope.cn/models/mirror/model/resolve/v2/a.bin")

    def test_mtp_refuses_unbounded_or_wrong_range(self):
        class Response(io.BytesIO):
            status = 200
            headers = {}
            def read(self, *args):
                raise AssertionError("must reject before reading full shard")
        with patch("urllib.request.urlopen", return_value=Response()):
            with self.assertRaisesRegex(IOError, "range request not honoured"):
                mtp_fetch.get("https://example.com/shard", 0, 7, retries=1)

    def test_mtp_range_and_short_read(self):
        class Response(io.BytesIO):
            status = 206
            headers = {"Content-Range": "bytes 2-5/100"}
        with patch("urllib.request.urlopen", return_value=Response(b"1234")):
            self.assertEqual(mtp_fetch.get("https://example.com/shard", 2, 5, retries=1), b"1234")
        with patch("urllib.request.urlopen", return_value=Response(b"12")):
            with self.assertRaisesRegex(IOError, "short range"):
                mtp_fetch.get("https://example.com/shard", 2, 5, retries=1)

    def test_pinned_revision_and_endpoint_precedence(self):
        revision = "a" * 40
        url = f"https://hf.example/cache/Qwen/model/resolve/{revision}/file.bin"
        with patch.dict(os.environ, {"STRATA_USE_MODELSCOPE": "1", "HF_ENDPOINT": "https://hf.example/cache"}, clear=True):
            self.assertEqual(model_url(url), "https://modelscope.cn/models/Qwen/model/resolve/master/file.bin")
            os.environ["STRATA_MODELSCOPE_REVISIONS"] = json.dumps({"Qwen/model": "source-pin"})
            selected = model_url(url)
            self.assertEqual(selected, "https://modelscope.cn/models/Qwen/model/resolve/source-pin/file.bin")
            self.assertEqual(model_fallback_url(selected), selected)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(model_url(url), url)
            self.assertEqual(model_fallback_url(url), url.replace(revision, "main"))

    def test_invalid_source_revisions(self):
        url = "https://huggingface.co/Qwen/model/resolve/main/file.bin"
        for mapping in ([], {"Qwen/model": None}, {"Qwen/model": ""}, {"Qwen/model": ".."}):
            with self.subTest(mapping=mapping), patch.dict(os.environ, {
                    "STRATA_USE_MODELSCOPE": "1", "STRATA_MODELSCOPE_REVISIONS": json.dumps(mapping)}, clear=True):
                with self.assertRaises(ValueError):
                    model_url(url)

    def test_mtp_head_uses_source_without_disabling_pinned_hashes(self):
        repo = f"https://huggingface.co/Qwen/model/resolve/{'a' * 40}/"
        with patch.dict(os.environ, {"STRATA_USE_MODELSCOPE": "1"}, clear=True), \
                patch.object(mtp_fetch, "REPO", repo), patch.object(mtp_fetch, "PINNED", repo), \
                patch("urllib.request.urlopen", return_value=io.BytesIO()) as request:
            self.assertEqual(mtp_fetch.resolve_repo(), repo)
            self.assertTrue(mtp_fetch.pinned())
            self.assertEqual(request.call_args.args[0].full_url,
                             "https://modelscope.cn/models/Qwen/model/resolve/master/model.safetensors.index.json")
        error = urllib.error.HTTPError("https://modelscope.cn/missing", 404, "missing", {}, None)
        with patch.dict(os.environ, {"STRATA_USE_MODELSCOPE": "1"}, clear=True), \
                patch.object(mtp_fetch, "REPO", repo), patch.object(mtp_fetch, "PINNED", repo), \
                patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(urllib.error.HTTPError):
                mtp_fetch.resolve_repo()
            self.assertEqual(mtp_fetch.REPO, repo)
            self.assertTrue(mtp_fetch.pinned())


if __name__ == "__main__":
    unittest.main()
