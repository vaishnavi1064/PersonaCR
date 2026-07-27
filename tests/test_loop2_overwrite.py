"""Step 4a — Loop 2 destructive overwrite (expected FAIL until fixed)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.src.core.models import (
    ConfidenceOutput,
    DefectFinding,
    DefectHunterOutput,
    PlannerOutput,
    PseudoRefOutput,
    QACheckerOutput,
    QualityGateResult,
    STSScores,
    StyleAnalysisOutput,
    StyleFinding,
)


@pytest.mark.asyncio
async def test_loop2_preserves_first_pass_findings_when_rereview_empty():
    """
    Contract: if first pass produces valid findings and Loop 2 re-review
    returns empty/failed findings, the returned ReviewResult.issues must
    still contain the first-pass findings (merge or rollback).

    Current orchestrator overwrites all_issues at Loop 2 (orchestrator.py
    ~L340). This test is expected to FAIL until that is fixed.
    """
    from backend.src.agents import orchestrator

    first_style = StyleAnalysisOutput(
        findings=[
            StyleFinding(
                category="type_safety",
                severity="high",
                description="FIRST_PASS_VALID_FINDING",
                fingerprint_value="1.0",
                submitted_value="0",
            )
        ],
        overall_style_score=55,
        similar_functions_found=5,
    )
    empty_style = StyleAnalysisOutput(
        findings=[],
        overall_style_score=50,
        similar_functions_found=0,
    )
    empty_defect = DefectHunterOutput(
        bugs=[], code_smells=[], security_issues=[], defect_score=80
    )

    call_count = {"style": 0, "defect": 0, "gate": 0}

    def style_side_effect(*_a, **_k):
        call_count["style"] += 1
        if call_count["style"] == 1:
            return first_style, 10
        return empty_style, 10

    def defect_side_effect(*_a, **_k):
        call_count["defect"] += 1
        return empty_defect, 10

    def qa_passthrough(code, style_output, defect_output):
        all_d = defect_output.bugs + defect_output.code_smells + defect_output.security_issues
        return (
            QACheckerOutput(
                style_relevant=True,
                defect_relevant=True,
                filtered_style_findings=list(style_output.findings),
                filtered_defect_findings=list(all_d),
            ),
            1,
        )

    def gate_side_effect(*_a, **_k):
        call_count["gate"] += 1
        if call_count["gate"] == 1:
            # Fail gate → trigger Loop 2
            return (
                QualityGateResult(
                    passed=False,
                    should_re_review=True,
                    reason="relevance below threshold",
                    comprehensiveness=0.1,
                    conciseness=0.1,
                    relevance=0.1,
                ),
                1,
            )
        # Second evaluation after empty re-review
        return (
            QualityGateResult(
                passed=False,
                should_re_review=False,
                reason="still failing",
                comprehensiveness=0.1,
                conciseness=0.1,
                relevance=0.1,
            ),
            1,
        )

    with patch.object(orchestrator, "plan_review", return_value=(
        PlannerOutput(focus_areas=["type_safety"], review_depth="standard", strategy_notes="t"),
        1,
    )), patch.object(orchestrator, "analyze_style", side_effect=style_side_effect), patch.object(
        orchestrator, "hunt_defects", side_effect=defect_side_effect
    ), patch.object(orchestrator, "check_quality", side_effect=qa_passthrough), patch.object(
        orchestrator, "evaluate_confidence", return_value=(
            ConfidenceOutput(confidence_score=0.95, is_confident=True, reason="ok", suggestion=""),
            1,
        )
    ), patch.object(orchestrator, "generate_pseudo_references", return_value=PseudoRefOutput(
        references=[], generation_time_ms=0
    )), patch.object(orchestrator, "compute_sts_scores", return_value=(
        STSScores(comprehensiveness=0.1, conciseness=0.1, relevance=0.1),
        1,
    )), patch.object(orchestrator, "evaluate_quality", side_effect=gate_side_effect):
        result = await orchestrator.run_review(
            code="def Add(a,b):\n    return a+b\n",
            language="python",
            fingerprint={"type_hint_usage": 1.0},
            user_id="u",
            repo_name="r",
            max_iterations=2,
        )

    assert call_count["style"] >= 2, "Loop 2 must re-run style analyst"
    assert call_count["gate"] >= 2, "Loop 2 must re-evaluate quality gate"

    descs = [i.get("description") for i in result.issues]
    assert "FIRST_PASS_VALID_FINDING" in descs, (
        "Loop 2 destructive overwrite: first-pass findings lost after empty re-review. "
        f"Returned issues={result.issues!r}. "
        "Overwrite site: backend/src/agents/orchestrator.py (~all_issues = [] in Loop 2)."
    )
