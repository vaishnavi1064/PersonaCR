"""One identity per repo: fingerprint save (UUID-safe) and Chroma collection (repo-scoped)."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from backend.src.core.repo_identity import as_uuid_or_none, repo_identity
from tests.conftest import make_chunk

REPO_URL = "https://github.com/some-owner/some-repo"


# ── repo_identity / as_uuid_or_none ──────────────────────────────────────────

@pytest.mark.parametrize(
    "url",
    [REPO_URL, REPO_URL + "/", REPO_URL + ".git", REPO_URL + ".git/"],
)
def test_repo_identity_normalizes(url):
    assert repo_identity(url) == ("some-owner", "some-repo")


def test_repo_identity_rejects_garbage():
    with pytest.raises(ValueError):
        repo_identity("not-a-url")


def test_as_uuid_or_none():
    u = str(uuid.uuid4())
    assert as_uuid_or_none(u) == u
    for bad in (None, "", "anonymous", "guest_abc123", "vaishnavi1064"):
        assert as_uuid_or_none(bad) is None


# ── save_fingerprint never sends a non-UUID user_id ──────────────────────────

def _fake_db():
    db = MagicMock()
    db.select_one.return_value = None
    db.insert.side_effect = lambda table, payload: payload
    return db


@pytest.mark.parametrize("user_id", ["vaishnavi1064", "guest_abc123", "anonymous"])
def test_non_uuid_user_id_saves_with_null(user_id):
    from backend.src.core.cache_manager import save_fingerprint

    db = _fake_db()
    save_fingerprint(db, REPO_URL, "some-repo", {"languages": ["python"]}, "sha", user_id)

    payload = db.insert.call_args.args[1]
    assert payload["user_id"] is None
    assert payload["repo_url"] == REPO_URL


def test_uuid_user_id_is_kept():
    from backend.src.core.cache_manager import save_fingerprint

    db = _fake_db()
    uid = str(uuid.uuid4())
    save_fingerprint(db, REPO_URL, "some-repo", {"languages": ["python"]}, "sha", uid)

    assert db.insert.call_args.args[1]["user_id"] == uid


# ── analyze as user A → review path as user B hits the same collection ───────

@pytest.fixture
def isolated_chroma(tmp_path, monkeypatch):
    import backend.src.core.embedder as emb

    monkeypatch.delenv("CHROMADB_URL", raising=False)
    monkeypatch.setattr(emb, "CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(emb, "_chroma_client", None)
    yield emb
    monkeypatch.setattr(emb, "_chroma_client", None)


@pytest.mark.slow
def test_analyze_as_user_a_review_as_user_b_shares_collection(isolated_chroma, monkeypatch):
    import backend.src.routes.analyze_routes as ar
    import backend.src.core.analysis as analysis_mod
    from backend.src.routes.review_routes import _parse_repo

    emb = isolated_chroma
    chunks = [
        make_chunk("parse_header", "def parse_header(raw: str) -> dict:\n    return dict(x.split(':') for x in raw.splitlines())", file_path="h.py"),
        make_chunk("merge_headers", "def merge_headers(a: dict, b: dict) -> dict:\n    return {**a, **b}", file_path="h.py"),
        make_chunk("__file_summary__", "File h.py: header helpers", file_path="h.py", granularity="file"),
    ]
    monkeypatch.setattr(analysis_mod, "ingest_repo", lambda url, token=None, **_: (chunks, "sha123"))
    monkeypatch.setattr(analysis_mod, "get_cached_fingerprint", lambda *a, **k: None)
    monkeypatch.setattr(analysis_mod, "save_fingerprint", MagicMock())
    monkeypatch.setattr(analysis_mod, "SupabaseREST", MagicMock())

    user_a = str(uuid.uuid4())
    from backend.src.core.auth import AuthUser

    out = ar.analyze_repo(ar.AnalyzeRequest(repo_url=REPO_URL, force_refresh=True), AuthUser(user_a, False))
    assert out["embedding"]["status"] == "ok"

    # Review path (any caller — here "user B") derives the namespace from the repo URL.
    _, namespace, repo_name = _parse_repo(REPO_URL)
    staged = emb.query_similar_staged(
        "def combine(h1: dict, h2: dict) -> dict:\n    return {**h1, **h2}",
        namespace, repo_name, n_files=1, n_functions=2, language_filter="python",
    )
    assert out["embedding"]["collection"] == emb._collection_name(namespace, repo_name)
    assert len(staged["functions"]) > 0

    # Collection metadata records who built it (for guest cleanup), not the namespace.
    meta = emb._get_client().get_collection(out["embedding"]["collection"]).metadata
    assert meta["analyzed_by"] == user_a and meta["user_id"] == "some-owner"


@pytest.mark.slow
def test_guest_cleanup_removes_collection_the_guest_built(isolated_chroma):
    emb = isolated_chroma
    chunks = [make_chunk("f", "def f(x: int) -> int:\n    return x + 1", file_path="a.py")]
    emb.embed_and_store(chunks, "some-owner", "some-repo", analyzed_by="guest_abc123")
    emb.embed_and_store(chunks, "other-owner", "other-repo", analyzed_by=str(uuid.uuid4()))

    assert emb.delete_guest_collections("guest_abc123") == 1
    names = {c.name for c in emb._get_client().list_collections()}
    assert names == {emb._collection_name("other-owner", "other-repo")}
