"""Tests for knowledge/embedding.py: loading the embedding model never asks the Hugging Face Hub.

The real model is never loaded here: a stand-in `sentence_transformers`
module records whether the Hub's offline flag was on when the model was built.
"""

import sys
import types
import unittest
from unittest.mock import patch

from knowledge import embedding

try:
    from huggingface_hub import constants as hub_constants
except ImportError:  # the tests otherwise run without the model's libraries
    hub_constants = None


def fake_sentence_transformers(cached: bool, calls: list) -> types.ModuleType:
    """A `sentence_transformers` module whose SentenceTransformer notes each call and the offline flag."""

    class SentenceTransformer:
        def __init__(self, name, revision=None, local_files_only=False):
            calls.append({"local_files_only": local_files_only, "offline": hub_constants.HF_HUB_OFFLINE})
            if local_files_only and not cached:
                raise OSError("not in the cache")
            self.max_seq_length = None

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = SentenceTransformer
    return module


@unittest.skipIf(hub_constants is None, "huggingface_hub is not installed")
class HubOfflineTests(unittest.TestCase):
    def setUp(self):
        embedding.load_model.cache_clear()
        self.addCleanup(embedding.load_model.cache_clear)
        self.before = hub_constants.HF_HUB_OFFLINE
        hub_constants.HF_HUB_OFFLINE = False
        self.addCleanup(setattr, hub_constants, "HF_HUB_OFFLINE", self.before)

    def load(self, cached: bool) -> list:
        calls: list = []
        with patch.dict(sys.modules, {"sentence_transformers": fake_sentence_transformers(cached, calls)}):
            embedding.load_model("test/model", "rev")
        return calls

    def test_cached_model_loads_with_the_hub_offline(self):
        calls = self.load(cached=True)
        self.assertEqual(calls, [{"local_files_only": True, "offline": True}])

    def test_offline_flag_is_restored_after_loading(self):
        self.load(cached=True)
        self.assertFalse(hub_constants.HF_HUB_OFFLINE)

    def test_missing_model_is_still_downloaded_online(self):
        calls = self.load(cached=False)
        self.assertEqual(calls, [{"local_files_only": True, "offline": True},
                                 {"local_files_only": False, "offline": False}])

    def test_flag_restored_when_loading_fails(self):
        with self.assertRaises(RuntimeError):
            with embedding.hub_offline():
                self.assertTrue(hub_constants.HF_HUB_OFFLINE)
                raise RuntimeError("load failed")
        self.assertFalse(hub_constants.HF_HUB_OFFLINE)


if __name__ == "__main__":
    unittest.main()
