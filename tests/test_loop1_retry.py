"""Loop 1 retries only when the agents' inputs change (mocked LLM, no live calls)."""
from __future__ import annotations

import pytest

import backend.src.agents.orchestrator as orch
import backend.src.core.embedder as embedder_mod
import backend.src.core.llm_client as llm
from backend.src.core.models import PlannerOutput, STSScores

CODE = "def f(xs=[]):\n    try:\n        return xs[0]\n    except:\n        return None\n"
FP = {"type_hint_usage": 1.0, "docstring_coverage": 1.0, "naming_convention": "snake_case"}

# Style returns no findings (score 100) and retrieval finds nothing, so the
# rules-based confidence lands below 0.7 and Loop 1 wants to retry.
REPLIES = {
    "You are a Style Analyst": '{"findings": []}',
    "You are a Defect Hunter": '{"bugs": [{"severity": "high", "description": "mutable default", '
                               '"category": "bug"}], "code_smells": [], "security_issues": [], '
                               '"defect_score": 60}',
    "You are a QA Checker": '{"style_relevant": true, "defect_relevant": true, '
                            '"irrelevant_indices_style": [], "irrelevant_indices_defect": [], '
                            '"issues_flagged": []}',
}


@pytest.fixture
def calls(monkeypatch):
    seen: list[str] = []

    def fake_provider(mdl, system, user, temperature, max_tokens):
        agent = next((k.split()[-1].lower() for k in REPLIES if system.startswith(k)), "other")
        seen.append(agent)
        reply = next((v for k, v in REPLIES.items() if system.startswith(k)), '{"references": []}')
        return reply, 50, 10, "end_turn"

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr(llm, "_complete_anthropic", fake_provider)
    monkeypatch.setattr(embedder_mod, "query_similar_staged",
                        lambda *a, **k: {"files": [], "functions": []})
    # Keep Loop 2 out of the picture: the quality gate passes.
    monkeypatch.setattr(orch, "compute_sts_scores",
                        lambda s, r: (STSScores(comprehensiveness=0.9, conciseness=0.9, relevance=0.9), 1))
    return seen


def _planner(monkeypatch, plans_by_call):
    received: list[dict] = []

    def fake_plan(code, language, fingerprint):
        received.append(dict(fingerprint))
        return plans_by_call[min(len(received), len(plans_by_call)) - 1], 0

    monkeypatch.setattr(orch, "plan_review", fake_plan)
    return received


def _review():
    return orch.review_code_sync(CODE, "python", FP, "some-owner", "some-repo")


def test_unchanged_plan_does_not_rerun_agents(calls, monkeypatch):
    same = PlannerOutput(focus_areas=["naming", "documentation"], review_depth="standard")
    _planner(monkeypatch, [same, same])

    r = _review()

    assert r.review_output["confidence"]["is_confident"] is False
    assert r.status == "low_confidence"
    assert r.iterations == 1
    assert calls.count("analyst") == 1 and calls.count("hunter") == 1 and calls.count("checker") == 1
    assert any(t.agent_name == "loop1_skip" for t in r.agent_trace)


def test_changed_plan_allows_retry_and_reuses_defect_output(calls, monkeypatch):
    first = PlannerOutput(focus_areas=["naming"], review_depth="standard")
    second = PlannerOutput(focus_areas=["documentation", "type_safety"], review_depth="thorough")
    received = _planner(monkeypatch, [first, second])

    r = _review()

    assert r.iterations == 2
    assert calls.count("analyst") == 2      # style re-ran with the new focus
    assert calls.count("checker") == 2      # QA re-ran on the new style output
    assert calls.count("hunter") == 1       # (code, language) unchanged → reused
    assert not any(t.agent_name == "loop1_skip" for t in r.agent_trace)
    # The retry's planner saw the confidence feedback and the previous focus.
    assert "_confidence_feedback" not in received[0]
    assert received[1]["_previous_focus"] == ["naming"]
    assert received[1]["_confidence_feedback"]
