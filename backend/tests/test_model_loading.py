import sys
import types

from engines import tier2_embedding


def _install_fake_library(monkeypatch, cached):
    calls = []

    class FakeModel:
        def __init__(self, name, local_files_only=False):
            calls.append(local_files_only)
            if local_files_only and not cached:
                raise OSError("model not cached")

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setattr(tier2_embedding, "_model", None)
    return calls


def test_cached_model_does_not_touch_network(monkeypatch):
    calls = _install_fake_library(monkeypatch, cached=True)
    tier2_embedding._get_model()
    assert calls == [True]


def test_missing_model_is_downloaded_once(monkeypatch):
    calls = _install_fake_library(monkeypatch, cached=False)
    tier2_embedding._get_model()
    assert calls == [True, False]


def test_hub_telemetry_is_disabled():
    import os

    assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
