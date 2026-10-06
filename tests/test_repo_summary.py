"""One-line repo summary, generated at analysis and stored with the fingerprint. LLM mocked."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.src.core import analysis as analysis_mod
from backend.src.core import repo_summary as rs
from backend.src.core.llm_client import LLMError
from tests.conftest import make_chunk

REPO = "https://github.com/acme/api"
CTX = {"description": "HTTP API for orders", "topics": ["fastapi", "orders"], "readme": "# Orders API\nServes order data."}


@pytest.mark.parametrize("raw,expected", [
    ("A FastAPI service that serves order data.", "A FastAPI service that serves order data."),
    ('"Summary: A CLI tool for X." Extra sentence here.', "A CLI tool for X."),
    ("  # A library\n for parsing  dates. ", "A library for parsing dates."),
    ("I cannot determine what this repo does.", None),
    ("", None),
])
def test_clean_summary(raw, expected):
    assert rs.clean_summary(raw) == expected


def test_long_summary_is_trimmed_on_a_word():
    out = rs.clean_summary("word " * 80)
    assert out is not None and len(out) <= rs.MAX_SUMMARY_CHARS and out.endswith("…")


def test_prompt_is_grounded_in_provided_facts():
    system, user = rs.build_prompt("acme/api", CTX, ["app/main.py", "app/routes/orders.py", "tests/test_x.py"], {"python": 40})
    assert "ONLY the facts provided" in system and "no marketing" in system
    for fact in ("acme/api", "HTTP API for orders", "fastapi", "python (40 functions)", "app/main.py", "Serves order data."):
        assert fact in user


def test_generate_makes_one_call_and_returns_text(monkeypatch):
    monkeypatch.setattr(rs, "fetch_repo_context", lambda url, token=None: CTX)
    calls = []

    def fake_complete(system, user, **kw):
        calls.append(kw.get("caller"))
        return "An HTTP API that serves order data."

    monkeypatch.setattr("backend.src.core.llm_client.complete", fake_complete)
    out = rs.generate_repo_summary(REPO, ["app/main.py"], {"python": 3})
    assert out["text"] == "An HTTP API that serves order data." and out["generated_at"]
    assert calls == ["repo_summary"]


def test_llm_failure_gives_none(monkeypatch):
    monkeypatch.setattr(rs, "fetch_repo_context", lambda url, token=None: CTX)

    def boom(*a, **k):
        raise LLMError("429 Too Many Requests", provider="anthropic", model="m", kind="rate_limit")

    monkeypatch.setattr("backend.src.core.llm_client.complete", boom)
    assert rs.generate_repo_summary(REPO, [], {}) is None


@pytest.fixture
def pipeline(monkeypatch):
    monkeypatch.setattr(analysis_mod, "SupabaseREST", MagicMock())
    monkeypatch.setattr(analysis_mod, "get_cached_fingerprint", lambda *a, **k: None)
    monkeypatch.setattr(analysis_mod, "embed_and_store", lambda *a, **k: {"collection": "c", "chunks_embedded": 1})
    saved = MagicMock()
    monkeypatch.setattr(analysis_mod, "save_fingerprint", saved)
    monkeypatch.setattr(analysis_mod, "ingest_repo", lambda url, token=None, **_: (
        [make_chunk("f", "def f(x: int) -> int:\n    return x", file_path="app/main.py")], "sha1"))
    return saved


def test_analysis_stores_summary_with_the_fingerprint(pipeline, monkeypatch):
    seen = {}

    def fake_generate(url, paths, langs, token=None):
        seen.update(url=url, paths=paths, langs=langs)
        return {"text": "An HTTP API.", "generated_at": "2026-10-06T00:00:00+00:00"}

    monkeypatch.setattr(analysis_mod, "generate_repo_summary", fake_generate)
    stages = []
    out = analysis_mod.run_analysis(REPO, user_id="3f2b8c1e-9a4d-4e57-8b1a-2c6d9e0f1a2b", force_refresh=True,
                                    on_stage=lambda s, p, m: stages.append(s))
    assert out["fingerprint"]["repo_summary"] == "An HTTP API."
    assert seen == {"url": REPO, "paths": ["app/main.py"], "langs": {"python": 1}}
    assert stages.index("summary") < stages.index("save")
    saved_fp = pipeline.call_args.args[3]
    assert saved_fp["repo_summary"] == "An HTTP API."  # persisted inside fingerprint_data


def test_analysis_survives_summary_failure(pipeline, monkeypatch):
    monkeypatch.setattr(analysis_mod, "generate_repo_summary", lambda *a, **k: None)
    out = analysis_mod.run_analysis(REPO, force_refresh=True)
    assert out["fingerprint"]["repo_summary"] is None
    pipeline.assert_called_once()


def test_cache_hit_does_not_regenerate(monkeypatch):
    monkeypatch.setattr(analysis_mod, "SupabaseREST", MagicMock())
    monkeypatch.setattr(analysis_mod, "get_cached_fingerprint", lambda *a, **k: {
        "_cache_status": "fresh", "fingerprint_data": {"repo_summary": "Old summary."}, "num_functions": 1})
    gen = MagicMock()
    monkeypatch.setattr(analysis_mod, "generate_repo_summary", gen)
    out = analysis_mod.run_analysis(REPO)
    assert out["fingerprint"]["repo_summary"] == "Old summary."
    gen.assert_not_called()


def test_summary_kept_out_of_the_style_prompt_but_in_insights():
    import inspect

    from backend.src.agents import insights_agent, style_analyst

    assert '"repo_summary"' in inspect.getsource(style_analyst.analyze_style)
    assert "What the repo is: An HTTP API." in insights_agent._summarize_fingerprint({"repo_summary": "An HTTP API."})
