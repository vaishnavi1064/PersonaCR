"""No silent retrieval failures: warnings on missing collections, retrieval_examples in results."""
from __future__ import annotations

import logging
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.conftest import make_chunk

REPO_URL = "https://github.com/some-owner/some-repo"


@pytest.fixture
def isolated_chroma(tmp_path, monkeypatch):
    import backend.src.core.embedder as emb

    monkeypatch.delenv("CHROMADB_URL", raising=False)
    monkeypatch.setattr(emb, "CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(emb, "_chroma_client", None)
    yield emb
    monkeypatch.setattr(emb, "_chroma_client", None)


@pytest.mark.slow
def test_missing_collection_logs_warning(isolated_chroma, caplog):
    emb = isolated_chroma
    with caplog.at_level(logging.WARNING, logger="backend.src.core.embedder"):
        out = emb.query_similar_staged("def f(): pass", "nobody", "nothing")
    assert out == {"files": [], "functions": []}
    assert any("No Chroma collection" in r.message and "0 examples" in r.message for r in caplog.records)


@pytest.mark.slow
def test_analyze_as_user_a_review_as_user_b_has_retrieval_examples(isolated_chroma, monkeypatch):
    """End to end through analyze_repo + Style Analyst retrieval (LLM mocked)."""
    import backend.src.agents.style_analyst as sa
    import backend.src.routes.analyze_routes as ar
    import backend.src.core.analysis as analysis_mod
    from backend.src.routes.review_routes import _parse_repo

    chunks = [
        make_chunk("merge_headers", "def merge_headers(a: dict, b: dict) -> dict:\n    return {**a, **b}", file_path="h.py"),
        make_chunk("parse_header", "def parse_header(raw: str) -> dict:\n    return dict(x.split(':') for x in raw.splitlines())", file_path="h.py"),
        make_chunk("__file_summary__", "File h.py: header helpers", file_path="h.py", granularity="file"),
    ]
    monkeypatch.setattr(analysis_mod, "ingest_repo", lambda url, token=None, **_: (chunks, "sha123"))
    monkeypatch.setattr(analysis_mod, "get_cached_fingerprint", lambda *a, **k: None)
    monkeypatch.setattr(analysis_mod, "save_fingerprint", MagicMock())
    monkeypatch.setattr(analysis_mod, "SupabaseREST", MagicMock())
    from backend.src.core.auth import AuthUser

    ar.analyze_repo(ar.AnalyzeRequest(repo_url=REPO_URL, force_refresh=True), AuthUser(str(uuid.uuid4()), False))

    # A different caller ("user B") reviews: the review path derives identity from the URL.
    import backend.src.core.llm_client as llm_client

    # analyze_style imports complete() at call time, so patching the module attribute works.
    monkeypatch.setattr(llm_client, "complete", lambda *a, **k: '{"findings": []}')
    _, namespace, repo_name = _parse_repo(REPO_URL)
    style_output, _ = sa.analyze_style(
        "def combine(h1: dict, h2: dict) -> dict:\n    return {**h1, **h2}",
        "python", {}, namespace, repo_name,
    )
    assert style_output.similar_functions_found > 0  # → review_output["retrieval_examples"]


def test_worker_result_exposes_retrieval_examples(monkeypatch):
    import backend.src.agents.orchestrator as orch
    import backend.src.workers.review_jobs as rj

    review = SimpleNamespace(
        overall_score=90.0, status="passed", iterations=1, issues=[],
        review_output={"retrieval_examples": 5, "similar_functions_used": 5}, agent_trace=[],
    )
    monkeypatch.setattr(orch, "review_code_sync", MagicMock(return_value=review))
    store: dict = {}
    monkeypatch.setattr(rj.job_store, "update_job", lambda job_id, **kw: store.update(kw))

    result = rj.process_review_job(
        "job-1", {"repo_url": REPO_URL, "code": "x = 1", "fingerprint": {"total_functions": 1}},
    )

    assert result["retrieval_examples"] == 5
    # review_code_sync got the repo-derived namespace, not a user id
    args = orch.review_code_sync.call_args.args
    assert args[3:5] == ("some-owner", "some-repo")
