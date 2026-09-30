"""Chroma client selection — CHROMADB_URL → HttpClient, unset → embedded PersistentClient."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def emb(tmp_path, monkeypatch):
    """Reset the client singleton and mock both chromadb constructors."""
    import backend.src.core.embedder as emb

    monkeypatch.setattr(emb, "CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(emb, "_chroma_client", None)
    monkeypatch.setattr(emb.chromadb, "HttpClient", MagicMock(name="HttpClient"))
    monkeypatch.setattr(emb.chromadb, "PersistentClient", MagicMock(name="PersistentClient"))
    yield emb
    monkeypatch.setattr(emb, "_chroma_client", None)


def test_chromadb_url_selects_http_client(emb, monkeypatch):
    monkeypatch.setenv("CHROMADB_URL", "http://chromadb:8000")

    client = emb._get_client()

    emb.chromadb.PersistentClient.assert_not_called()
    emb.chromadb.HttpClient.assert_called_once()
    kwargs = emb.chromadb.HttpClient.call_args.kwargs
    assert (kwargs["host"], kwargs["port"], kwargs["ssl"]) == ("chromadb", 8000, False)
    assert client is emb.chromadb.HttpClient.return_value


def test_chromadb_url_https_default_port(emb, monkeypatch):
    monkeypatch.setenv("CHROMADB_URL", "https://chroma.example.com")

    emb._get_client()

    kwargs = emb.chromadb.HttpClient.call_args.kwargs
    assert (kwargs["host"], kwargs["port"], kwargs["ssl"]) == ("chroma.example.com", 443, True)


def test_no_chromadb_url_selects_embedded_client(emb, monkeypatch):
    monkeypatch.delenv("CHROMADB_URL", raising=False)

    client = emb._get_client()

    emb.chromadb.HttpClient.assert_not_called()
    emb.chromadb.PersistentClient.assert_called_once()
    assert emb.chromadb.PersistentClient.call_args.kwargs["path"] == emb.CHROMA_DIR
    assert client is emb.chromadb.PersistentClient.return_value


def test_chromadb_url_without_host_raises(emb, monkeypatch):
    monkeypatch.setenv("CHROMADB_URL", "chromadb:8000")  # no scheme → no hostname

    with pytest.raises(ValueError, match="no host"):
        emb._get_client()
