"""An LLM failure must never yield a confident review or a normal score."""
from __future__ import annotations

import pytest

import backend.src.agents.orchestrator as orch
import backend.src.core.embedder as embedder_mod
import backend.src.core.llm_client as llm
from backend.src.core.models import STSScores

CODE = "def f(xs=[]):\n    try:\n        return xs[0]\n    except:\n        return None\n"
FP = {"error_handling_rate": 0.9, "avg_function_length": 10, "docstring_coverage": 0.8,
      "comment_density": 0.0, "type_hint_usage": 1.0, "naming_convention": "snake_case"}

OK_REPLIES = {
    "You are a Style Analyst": '{"findings": [{"category": "naming", "severity": "low", '
                               '"description": "camelCase vs snake_case fingerprint"}]}',
    "You are a Defect Hunter": '{"bugs": [{"severity": "high", "description": "mutable default", '
                               '"category": "bug"}], "code_smells": [], "security_issues": [], '
                               '"defect_score": 60}',
    "You are a QA Checker": '{"style_relevant": true, "defect_relevant": true, '
                            '"irrelevant_indices_style": [], "irrelevant_indices_defect": [], '
                            '"issues_flagged": []}',
}


@pytest.fixture
def pipeline(monkeypatch):
    """Real orchestrator + real llm_client.complete; only the provider call is faked."""
    calls: list[str] = []
    failing: set[str] = set()

    def fake_provider(mdl, system, user, temperature, max_tokens):
        agent = next((k for k in OK_REPLIES if system.startswith(k)), "other")
        calls.append(agent)
        if agent in failing or "*" in failing:
            raise llm.LLMError("Error code: 404 - model does not exist", provider="anthropic",
                               model=mdl, kind="not_found")
        return OK_REPLIES.get(agent, '{"references": []}'), 100, 20, "end_turn"

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr(llm, "_complete_anthropic", fake_provider)
    monkeypatch.setattr(embedder_mod, "query_similar_staged",
                        lambda *a, **k: {"files": [], "functions": []})
    monkeypatch.setattr(orch, "compute_sts_scores",
                        lambda sents, refs: (STSScores(comprehensiveness=0.9, conciseness=0.9, relevance=0.9), 1))
    return calls, failing


def _review():
    return orch.review_code_sync(CODE, "python", FP, "some-owner", "some-repo")


def test_all_llm_calls_failing_gives_error_status(pipeline):
    calls, failing = pipeline
    failing.add("*")

    r = _review()

    assert r.status == "error"
    assert r.overall_score is None
    conf = r.review_output["confidence"]
    assert conf["is_confident"] is False and conf["confidence_score"] == 0.0
    assert "LLM failure" in conf["reason"]
    assert "not_found" in r.review_output["degraded_reason"]
    assert r.review_output["llm_usage"]["calls"] == 0
    assert r.review_output["llm_usage"]["failures"]
    # No fabricated "analysis error" findings; AST findings (real) may remain.
    assert not any("error:" in (i.get("description") or "").lower() for i in r.issues)
    assert r.iterations == 1  # no Loop 1 / Loop 2 retries burning more calls


def test_one_agent_failing_gives_degraded_status(pipeline):
    calls, failing = pipeline
    failing.add("You are a Defect Hunter")

    r = _review()

    assert r.status == "degraded"
    assert r.overall_score is None
    assert r.review_output["confidence"]["is_confident"] is False
    usage = r.review_output["llm_usage"]
    assert usage["calls"] >= 1 and [f["caller"] for f in usage["failures"]] == ["defect"]
    assert r.iterations == 1


def test_healthy_llm_still_scores_normally(pipeline):
    r = _review()

    assert r.status not in ("degraded", "error")
    assert isinstance(r.overall_score, float)
    assert r.review_output["degraded_reason"] is None
    assert r.review_output["llm_usage"]["failures"] == []
    assert r.review_output["llm_usage"]["input_tokens"] > 0


def test_unexpected_client_error_still_degrades(pipeline, monkeypatch):
    """A non-API exception (e.g. SDK TypeError) must degrade, not score 85 'low_confidence'."""
    def boom(mdl, system, user, temperature, max_tokens):
        raise TypeError("Messages.create() got an unexpected keyword argument 'temperature'")

    monkeypatch.setattr(llm, "_complete_anthropic", boom)
    r = _review()

    assert r.status == "error"
    assert r.overall_score is None
    assert {f["kind"] for f in r.review_output["llm_usage"]["failures"]} == {"client"}
