import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.domain.search import semantic


class SemanticRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_allow_remote_download = (
            semantic.settings.search_semantic_allow_remote_download
        )
        semantic._load_bge_m3_model.cache_clear()

    def tearDown(self) -> None:
        semantic.settings.search_semantic_allow_remote_download = (
            self.original_allow_remote_download
        )
        semantic._load_bge_m3_model.cache_clear()

    def test_skips_uncached_model_when_remote_download_is_disabled(self) -> None:
        semantic.settings.search_semantic_allow_remote_download = False

        with patch.object(semantic, "BGEM3FlagModel") as model_cls, patch.object(
            semantic,
            "_is_model_cached_locally",
            return_value=False,
        ):
            result = semantic._load_bge_m3_model("BAAI/bge-m3", use_fp16=False)

        self.assertIsNone(result)
        model_cls.assert_not_called()

    def test_uses_cached_model_when_remote_download_is_disabled(self) -> None:
        semantic.settings.search_semantic_allow_remote_download = False
        sentinel = object()

        with patch.object(semantic, "BGEM3FlagModel", return_value=sentinel) as model_cls, patch.object(
            semantic,
            "_is_model_cached_locally",
            return_value=True,
        ):
            result = semantic._load_bge_m3_model("BAAI/bge-m3", use_fp16=False)

        self.assertIs(result, sentinel)
        model_cls.assert_called_once_with("BAAI/bge-m3", use_fp16=False)

    def test_detects_huggingface_snapshot_cache(self) -> None:
        with TemporaryDirectory() as tmpdir:
            snapshots_dir = (
                Path(tmpdir)
                / "models--BAAI--bge-m3"
                / "snapshots"
                / "snapshot-1"
            )
            snapshots_dir.mkdir(parents=True)

            with patch.object(
                semantic,
                "_iter_huggingface_cache_roots",
                return_value=(Path(tmpdir),),
            ):
                self.assertTrue(semantic._is_model_cached_locally("BAAI/bge-m3"))


if __name__ == "__main__":
    unittest.main()
