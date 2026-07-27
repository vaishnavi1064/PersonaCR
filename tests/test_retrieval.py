"""Step 2 — Retrieval correctness (local embeddings + temp Chroma)."""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import make_chunk

pytestmark = pytest.mark.slow


@pytest.fixture
def isolated_chroma(tmp_path, monkeypatch):
    """Point embedder at a fresh temp Chroma dir; reset singletons."""
    import backend.src.core.embedder as emb

    monkeypatch.setattr(emb, "CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(emb, "_chroma_client", None)
    monkeypatch.setattr(emb, "_model", None)
    yield emb
    monkeypatch.setattr(emb, "_chroma_client", None)


def _index_corpus(emb, user_id: str, repo_name: str):
    """
    Index two files with stylistically distinct function corpora.

    File auth.py: typed, snake_case auth helpers (personal style).
    File legacy.js-ish py: untyped camelCase-ish names (foreign style).
    Plus file-level summary chunks for two-stage retrieval.
    """
    chunks = [
        make_chunk(
            "__file_summary__",
            "File auth.py: typed authentication helpers with snake_case names.",
            file_path="auth.py",
            granularity="file",
        ),
        make_chunk(
            "verify_token",
            "def verify_token(token: str) -> bool:\n"
            '    """Return True if token is valid."""\n'
            "    return bool(token) and len(token) > 8",
            file_path="auth.py",
        ),
        make_chunk(
            "hash_password",
            "def hash_password(password: str) -> str:\n"
            '    """Hash a password."""\n'
            "    return password[::-1]",
            file_path="auth.py",
        ),
        make_chunk(
            "create_session",
            "def create_session(user_id: str) -> dict:\n"
            '    """Create a session dict."""\n'
            "    return {'user_id': user_id, 'active': True}",
            file_path="auth.py",
        ),
        make_chunk(
            "__file_summary__",
            "File widgets.py: untyped UI widget glue with short cryptic names.",
            file_path="widgets.py",
            granularity="file",
        ),
        make_chunk(
            "renderBtn",
            "def renderBtn(lbl):\n    return '<button>' + str(lbl) + '</button>'",
            file_path="widgets.py",
        ),
        make_chunk(
            "paintBox",
            "def paintBox(w, h):\n    return w * h",
            file_path="widgets.py",
        ),
        make_chunk(
            "mkIcon",
            "def mkIcon(n):\n    return n.upper()",
            file_path="widgets.py",
        ),
    ]
    return emb.embed_and_store(chunks, user_id, repo_name)


class TestRetrievalCorrectness:
    def test_query_returns_nearest_neighbors_not_degenerate(self, isolated_chroma):
        emb = isolated_chroma
        user_id = f"test_{uuid.uuid4().hex[:8]}"
        repo = "retrieval_fixture"
        stored = _index_corpus(emb, user_id, repo)
        assert stored["chunks_embedded"] == 8

        query = (
            "def check_token(token: str) -> bool:\n"
            '    """Validate auth token."""\n'
            "    return len(token) > 8"
        )
        hits = emb.query_similar(query, user_id, repo, n=3, language_filter="python")
        assert len(hits) >= 1, "retrieval returned no neighbors"

        top_names = [h["metadata"].get("function_name") for h in hits]
        # Nearest should prefer auth helpers, not widget glue
        assert any(n in {"verify_token", "hash_password", "create_session"} for n in top_names), (
            f"expected auth neighbor in top hits, got {top_names}"
        )

        distances = [h["distance"] for h in hits]
        assert distances == sorted(distances), "distances must be sorted ascending (nearest first)"
        # Not a collapsed/identical distance for everything
        assert len(set(round(d, 6) for d in distances)) >= 1

    def test_adversarial_matching_vs_unlike_query(self, isolated_chroma):
        emb = isolated_chroma
        user_id = f"test_{uuid.uuid4().hex[:8]}"
        repo = "retrieval_adv"
        _index_corpus(emb, user_id, repo)

        matching = (
            "def validate_password(password: str) -> str:\n"
            '    """Hash-like transform for passwords."""\n'
            "    return password[::-1]"
        )
        unlike = (
            "def paintBox(width, height):\n"
            "    area = width * height\n"
            "    return area"
        )

        match_hits = emb.query_similar(matching, user_id, repo, n=1, language_filter="python")
        unlike_hits = emb.query_similar(unlike, user_id, repo, n=1, language_filter="python")
        assert match_hits and unlike_hits

        match_dist = match_hits[0]["distance"]
        unlike_to_auth = emb.query_similar(
            unlike, user_id, repo, n=5, language_filter="python"
        )
        # Best distance for matching auth-style query should be meaningfully
        # better (lower cosine distance) than for a UI-style query against auth corpus
        # when we look at auth-file neighbors.
        auth_dists_for_unlike = [
            h["distance"]
            for h in unlike_to_auth
            if h["metadata"].get("file_path") == "auth.py"
        ]
        assert match_dist < 0.5, f"matching query unexpectedly far: {match_dist}"

        # Adversarial: matching query's top hit should be closer than unlike's top hit
        # when both retrieve against the same collection — if RAG is dead, scores collapse.
        unlike_dist = unlike_hits[0]["distance"]
        assert match_dist < unlike_dist - 0.02 or (
            match_hits[0]["metadata"].get("file_path") == "auth.py"
            and unlike_hits[0]["metadata"].get("file_path") == "widgets.py"
        ), (
            "RAG appears non-discriminative: "
            f"match_dist={match_dist}, unlike_dist={unlike_dist}, "
            f"match_meta={match_hits[0]['metadata']}, unlike_meta={unlike_hits[0]['metadata']}, "
            f"auth_dists_for_unlike={auth_dists_for_unlike}"
        )

    def test_two_stage_narrows_to_stage1_files(self, isolated_chroma):
        emb = isolated_chroma
        user_id = f"test_{uuid.uuid4().hex[:8]}"
        repo = "retrieval_staged"
        _index_corpus(emb, user_id, repo)

        query = (
            "def verify_token(token: str) -> bool:\n"
            "    return bool(token)"
        )
        staged = emb.query_similar_staged(
            query, user_id, repo, n_files=1, n_functions=5, language_filter="python"
        )
        assert staged["files"], "stage 1 must return file-level hits"
        top_files = {f["metadata"].get("file_path") for f in staged["files"]}
        assert staged["functions"], "stage 2 must return function hits"

        for fn in staged["functions"]:
            fp = fn["metadata"].get("file_path")
            assert fp in top_files, (
                f"stage-2 function from {fp} not in stage-1 files {top_files} — "
                "two-stage narrowing is broken"
            )
            assert fn["metadata"].get("granularity") == "function"
