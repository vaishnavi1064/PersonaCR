"""Embedding memory bounds — chunk-count and token-budget batching in embed_and_store."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.conftest import make_chunk


class _FakeTokenizer:
    """1 token per whitespace word, honoring enable_truncation like HF tokenizers."""

    def __init__(self) -> None:
        self.max_length: int | None = None

    def enable_truncation(self, max_length: int) -> None:
        self.max_length = max_length

    def encode_batch(self, texts):
        out = []
        for t in texts:
            n = len(t.split())
            if self.max_length is not None:
                n = min(n, self.max_length)
            out.append(SimpleNamespace(ids=[0] * n))
        return out


class _FakeModel:
    def __init__(self) -> None:
        self.model = SimpleNamespace(tokenizer=_FakeTokenizer())
        self.calls: list[list[str]] = []

    def embed(self, texts, batch_size=256):
        texts = list(texts)
        self.calls.append(texts)
        return iter([[0.0, 1.0, 0.0]] * len(texts))


@pytest.fixture
def emb(monkeypatch):
    import backend.src.core.embedder as emb

    model = _FakeModel()
    model.model.tokenizer.enable_truncation(emb.MAX_EMBED_TOKENS)
    collection = MagicMock(name="collection")
    client = MagicMock(name="client")
    client.create_collection.return_value = collection
    monkeypatch.setattr(emb, "_get_model", lambda: model)
    monkeypatch.setattr(emb, "_get_client", lambda: client)
    emb._fake = SimpleNamespace(model=model, collection=collection)
    yield emb
    del emb._fake


def _chunks(n: int, words: int, prefix: str = "f"):
    body = " ".join(["tok"] * words)
    return [make_chunk(f"{prefix}{i}", body, file_path=f"m{i}.py") for i in range(n)]


def test_large_input_is_split_into_bounded_batches(emb, monkeypatch):
    monkeypatch.setattr(emb, "EMBED_TOKEN_BUDGET", 10_000)
    chunks = _chunks(100, words=10)

    out = emb.embed_and_store(chunks, "u", "repo", batch_size=32)

    sizes = [len(c) for c in emb._fake.model.calls]
    assert sizes == [32, 32, 32, 4]
    assert out == {"collection": out["collection"], "chunks_embedded": 100, "batches": 4}
    # One Chroma upsert per batch, every chunk stored exactly once, in order.
    adds = emb._fake.collection.add.call_args_list
    assert len(adds) == 4
    ids = [i for call in adds for i in call.kwargs["ids"]]
    assert ids == [emb._chunk_id(c) for c in chunks]


def test_env_default_batch_size_is_used(emb, monkeypatch):
    monkeypatch.setattr(emb, "EMBED_BATCH_SIZE", 8)
    monkeypatch.setattr(emb, "EMBED_TOKEN_BUDGET", 10_000)

    emb.embed_and_store(_chunks(20, words=5), "u", "repo")

    assert [len(c) for c in emb._fake.model.calls] == [8, 8, 4]


def test_token_budget_splits_long_texts(emb, monkeypatch):
    """len(batch) × longest tokens must stay ≤ budget, so long files get small batches."""
    monkeypatch.setattr(emb, "EMBED_TOKEN_BUDGET", 2048)
    short = _chunks(6, words=100, prefix="s")       # 100 tokens each
    long_ = _chunks(3, words=1500, prefix="l")      # 1500 tokens each
    chunks = short + long_ + short[:2]

    emb.embed_and_store(chunks, "u", "repo", batch_size=32)

    tok = emb._fake.model.model.tokenizer
    for batch in emb._fake.model.calls:
        counts = [len(e.ids) for e in tok.encode_batch(batch)]
        assert len(batch) * max(counts) <= 2048 or len(batch) == 1
    assert sum(len(c) for c in emb._fake.model.calls) == len(chunks)


def test_text_over_cap_is_truncated_and_embedded_alone(emb, monkeypatch):
    monkeypatch.setattr(emb, "EMBED_TOKEN_BUDGET", 2048)
    huge = _chunks(1, words=50_000, prefix="h")
    chunks = _chunks(4, words=10) + huge

    emb.embed_and_store(chunks, "u", "repo", batch_size=32)

    calls = emb._fake.model.calls
    assert len(calls[-1]) == 1  # the huge file gets its own batch
    tok = emb._fake.model.model.tokenizer
    assert len(tok.encode_batch(calls[-1])[0].ids) == emb.MAX_EMBED_TOKENS


def test_budget_batches_helper_preserves_order():
    from backend.src.core.embedder import _token_budget_batches

    assert _token_budget_batches([10, 10, 900, 10, 10], max_items=32, token_budget=1000) == [
        [0, 1],
        [2],
        [3, 4],
    ]
    assert _token_budget_batches([], max_items=4, token_budget=100) == []
