import io
import os
import unittest
from unittest.mock import patch

from tools.model_source import model_url
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
            with self.assertRaisesRegex(IOError, "byte range"):
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


if __name__ == "__main__":
    unittest.main()
