"""
A re-analysis builds the new vectors in a temporary collection and swaps it in
only when every chunk is in. A failed or killed build leaves the previous index
serving reviews — never a partial one (seen on minikube: 50/108 after a worker
restart mid-index).

Real embedded Chroma in a temp dir; the embedding model is faked.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import chromadb
import pytest
from chromadb.config import Settings

from tests.conftest import make_chunk
from tests.test_embed_batching import _FakeModel

pytestmark = pytest.mark.slow

OWNER, REPO = "acme", "api"


def _chunks(prefix: str, n: int) -> list:
    return [make_chunk(f"{prefix}_{i}", f"def {prefix}_{i}(x):\n    return x + {i}", start_line=i * 10 + 1)
            for i in range(n)]


@pytest.fixture
def emb(tmp_path, monkeypatch):
    import backend.src.core.embedder as emb

    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"), settings=Settings(anonymized_telemetry=False))
    model = _FakeModel()
    model.model.tokenizer.enable_truncation(emb.MAX_EMBED_TOKENS)
    monkeypatch.setattr(emb, "_get_client", lambda: client)
    monkeypatch.setattr(emb, "_get_model", lambda: model)
    emb._test_client, emb._test_model = client, model
    return emb


def _live(emb):
    return emb._test_client.get_collection(emb._collection_name(OWNER, REPO))


def _names(emb) -> list[str]:
    return sorted(emb._collection_names(emb._test_client))


def test_first_build_creates_the_live_collection(emb):
    out = emb.embed_and_store(_chunks("a", 5), OWNER, REPO, batch_size=2)
    assert out["chunks_embedded"] == 5 and _live(emb).count() == 5
    assert _names(emb) == [emb._collection_name(OWNER, REPO)]  # no temp/displaced leftovers


def test_rebuild_replaces_the_index_on_success(emb):
    emb.embed_and_store(_chunks("old", 4), OWNER, REPO)
    emb.embed_and_store(_chunks("new", 6), OWNER, REPO, batch_size=2)
    live = _live(emb)
    assert live.count() == 6
    assert all(m["function_name"].startswith("new_") for m in live.get()["metadatas"])
    assert live.metadata.get("hnsw:space") == "cosine"
    assert _names(emb) == [emb._collection_name(OWNER, REPO)]


def test_failed_rebuild_keeps_the_old_index(emb, monkeypatch):
    emb.embed_and_store(_chunks("old", 4), OWNER, REPO)
    real_embed, calls = emb._test_model.embed, {"n": 0}

    def flaky(texts, batch_size=256):
        calls["n"] += 1
        if calls["n"] == 2:  # dies after the first batch is already in
            raise RuntimeError("worker killed mid-index")
        return real_embed(texts, batch_size)

    monkeypatch.setattr(emb._test_model, "embed", flaky)
    with pytest.raises(RuntimeError, match="mid-index"):
        emb.embed_and_store(_chunks("new", 6), OWNER, REPO, batch_size=2)
    live = _live(emb)
    assert live.count() == 4
    assert all(m["function_name"].startswith("old_") for m in live.get()["metadatas"])
    assert _names(emb) == [emb._collection_name(OWNER, REPO)]  # half-built temp removed


def test_old_index_serves_while_the_new_one_builds(emb, monkeypatch):
    emb.embed_and_store(_chunks("old", 3), OWNER, REPO)
    real_embed, seen = emb._test_model.embed, []

    def watching(texts, batch_size=256):
        seen.append(_live(emb).count())  # what a review would query mid-build
        return real_embed(texts, batch_size)

    monkeypatch.setattr(emb._test_model, "embed", watching)
    emb.embed_and_store(_chunks("new", 6), OWNER, REPO, batch_size=2)
    assert seen == [3, 3, 3] and _live(emb).count() == 6


def test_leftovers_from_a_killed_build_are_cleaned_up(emb):
    emb.embed_and_store(_chunks("old", 2), OWNER, REPO)
    name = emb._collection_name(OWNER, REPO)
    emb._test_client.create_collection(f"{name}-tdeadbeef")  # process killed before cleanup
    emb._test_client.create_collection(f"{name}-ocafef00d")
    other = emb._test_client.create_collection("pcr-other-repo-0123456789abcdef")
    emb.embed_and_store(_chunks("new", 2), OWNER, REPO)
    assert _names(emb) == sorted([name, other.name])  # another repo's collection untouched


def test_temp_names_fit_chromas_63_char_limit(emb):
    longest = emb._collection_name("o" * 39, "r" * 100)
    assert len(f"{longest}-t12345678") <= 63


def test_failed_swap_restores_the_old_index():
    import backend.src.core.embedder as emb

    client, old, built = MagicMock(), MagicMock(), MagicMock()
    client.get_collection.return_value = old
    built.modify.side_effect = RuntimeError("rename failed")
    with pytest.raises(RuntimeError):
        emb._swap_in(client, built, "pcr-api-0123")
    renames = [c.kwargs["name"] for c in old.modify.call_args_list]
    assert renames[0].startswith("pcr-api-0123-o") and renames[-1] == "pcr-api-0123"
    client.delete_collection.assert_not_called()
