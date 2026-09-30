import unittest

from tools.codex_catalog import build_catalog, metadata_from_config
from serve.frontend import effort_kwargs


def metadata(context=65536, model="qwen3.8-flash-next-iq3_s", modalities=None):
    return {"id": model, "meta": {"n_ctx": context},
            "architecture": {"input_modalities": ["text"] if modalities is None else modalities}}


class CatalogTests(unittest.TestCase):
    def test_deployment_cap_and_vision(self):
        model = build_catalog(metadata(modalities=["image", "text"]))["models"][0]
        self.assertEqual(model["slug"], "qwen3.8-flash-next-iq3_s")
        self.assertEqual((model["context_window"], model["max_context_window"]), (65536, 65536))
        self.assertEqual(model["input_modalities"], ["text", "image"])
        self.assertEqual(model["auto_compact_token_limit"], 49152)
        self.assertFalse(model["supports_reasoning_effort_updates"])  # configuration_update is unsupported
        lower = build_catalog(metadata(), 32768, 24000)["models"][0]
        self.assertEqual((lower["context_window"], lower["max_context_window"]), (32768, 32768))
        self.assertEqual(lower["input_modalities"], ["text"])

    def test_refuse_unresearched_or_oversized_deployments(self):
        for model in ("swift-1.5-iq2_xs", "qwen3.8-flash-next-coder-iq1_m", "gpt-5", "strata-local"):
            with self.subTest(model=model), self.assertRaises(ValueError):
                build_catalog(metadata(model=model))
        for context in (0, -1, True, 1000000):
            with self.subTest(context=context), self.assertRaises(ValueError):
                build_catalog(metadata(context=context))
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            build_catalog(metadata(32768), 65536)
        with self.assertRaisesRegex(ValueError, "90%"):
            build_catalog(metadata(), auto_compact=65536)
        with self.assertRaises(ValueError):
            build_catalog(metadata(modalities=["text", "audio"]))
        for malformed in (None, {}, {"id": "qwen3.8-flash-next", "meta": None, "architecture": {}}):
            with self.subTest(metadata=malformed), self.assertRaises(ValueError):
                build_catalog(malformed)

    def test_config_reads_setup_arguments_and_requires_context(self):
        cfg = {"model_name": "qwen3.8-flash-next-iq3_s", "args": ["--max-context", "131072"], "vision": {"path": "mmproj"}}
        model = build_catalog(metadata_from_config(cfg))["models"][0]
        self.assertEqual(model["context_window"], 131072)
        self.assertEqual(model["input_modalities"], ["text", "image"])
        with self.assertRaisesRegex(ValueError, "max-context"):
            metadata_from_config({"model_name": "qwen3.8-flash-next", "args": []})

    def test_advertised_efforts_match_the_native_template(self):
        model = build_catalog(metadata())["models"][0]
        mapping = {preset["effort"]: effort_kwargs(preset["effort"]) for preset in model["supported_reasoning_levels"]}
        self.assertEqual(mapping["none"], {"enable_thinking": False})
        self.assertEqual(mapping["low"], {"reasoning_effort": "low"})
        self.assertEqual(mapping["medium"], {"reasoning_effort": "medium"})
        self.assertEqual(mapping["high"], mapping["xhigh"])
        self.assertEqual(mapping[model["default_reasoning_level"]], {"reasoning_effort": "medium"})


if __name__ == "__main__":
    unittest.main()
