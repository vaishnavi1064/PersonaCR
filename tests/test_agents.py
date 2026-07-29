"""Step 3 — Per-agent correctness (deterministic + mocked LLM; Groq marked)."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.src.agents.confidence_evaluator import evaluate_confidence
from backend.src.agents.defect_hunter import _ast_analysis, hunt_defects
from backend.src.agents.planner import _rules_based_plan, plan_review
from backend.src.core.models import (
    DefectFinding,
    DefectHunterOutput,
    QACheckerOutput,
    StyleAnalysisOutput,
    StyleFinding,
)


# ── Planner (rules path, no network) ─────────────────────────────────────────

class TestPlannerRules:
    def test_rules_plan_flags_missing_error_handling_and_docs(self):
        fp = {
            "error_handling_rate": 0.9,
            "avg_function_length": 10,
            "docstring_coverage": 0.8,
            "comment_density": 0.0,
        }
        code = "def add(a, b):\n    return a + b\n"
        plan = _rules_based_plan(code, "python", fp)
        assert plan is not None
        assert "error_handling" in plan.focus_areas
        assert "documentation" in plan.focus_areas

    def test_plan_review_uses_rules_fast_path_without_groq(self):
        fp = {
            "error_handling_rate": 0.9,
            "avg_function_length": 10,
            "docstring_coverage": 0.8,
            "comment_density": 0.0,
        }
        code = "def add(a, b):\n    return a + b\n"
        with patch("groq.Groq") as groq_cls:
            out, _ms = plan_review(code, "python", fp)
            groq_cls.assert_not_called()
        assert "error_handling" in out.focus_areas


# ── Defect Hunter AST (no network) ───────────────────────────────────────────

class TestDefectHunterAST:
    def test_catches_bare_except(self):
        code = "def f():\n    try:\n        1/0\n    except:\n        pass\n"
        findings = _ast_analysis(code, "python")
        assert any("Bare except" in f.description for f in findings)
        assert any(f.category == "bug" for f in findings)

    def test_catches_mutable_default(self):
        code = "def f(xs=[]):\n    xs.append(1)\n    return xs\n"
        findings = _ast_analysis(code, "python")
        assert any("Mutable default" in f.description for f in findings)

    def test_clean_code_has_no_ast_defects(self):
        code = (
            "def add(a: int, b: int) -> int:\n"
            '    """Add two ints."""\n'
            "    return a + b\n"
        )
        findings = _ast_analysis(code, "python")
        assert findings == []


# ── Confidence Evaluator (no network) ────────────────────────────────────────

class TestConfidenceEvaluator:
    def _qa(self, n_style=2, n_defect=2, style_ok=True, defect_ok=True):
        return QACheckerOutput(
            style_relevant=style_ok,
            defect_relevant=defect_ok,
            issues_flagged=[],
            filtered_style_findings=[
                StyleFinding(category="naming", severity="medium", description=f"s{i}")
                for i in range(n_style)
            ],
            filtered_defect_findings=[
                DefectFinding(severity="medium", description=f"d{i}", category="bug")
                for i in range(n_defect)
            ],
        )

    def test_high_evidence_is_confident(self):
        out, _ = evaluate_confidence(self._qa(), similar_functions_found=5, style_score=70, defect_score=70)
        assert out.is_confident is True
        assert out.confidence_score >= 0.7

    def test_no_retrieval_and_no_findings_is_not_confident(self):
        out, _ = evaluate_confidence(
            self._qa(n_style=0, n_defect=0),
            similar_functions_found=0,
            style_score=70,
            defect_score=70,
        )
        assert out.is_confident is False
        assert out.confidence_score < 0.7
        assert "No similar functions" in out.reason

    def test_zero_retrieval_can_still_hit_confidence_threshold(self):
        """
        Characterization: Factor 1 awards 0.0 for zero Chroma hits, but the
        other three factors alone sum to exactly 0.7 → is_confident=True.
        Loop 1 will NOT re-plan despite 'No similar functions' in the reason.
        """
        out, _ = evaluate_confidence(
            self._qa(n_style=2, n_defect=2),
            similar_functions_found=0,
            style_score=70,
            defect_score=70,
        )
        assert out.confidence_score == 0.7
        assert out.is_confident is True
        assert "No similar functions" in out.reason


# ── QA filtering logic with mocked Groq ──────────────────────────────────────

class TestQACheckerParsing:
    def test_filters_irrelevant_indices_from_mocked_llm(self):
        from backend.src.agents import qa_checker

        style = StyleAnalysisOutput(
            findings=[
                StyleFinding(category="naming", severity="low", description="real naming issue"),
                StyleFinding(category="imports", severity="low", description="hallucinated import"),
            ],
            overall_style_score=60,
            similar_functions_found=3,
        )
        defect = DefectHunterOutput(
            bugs=[DefectFinding(severity="high", description="bare except", category="bug")],
            code_smells=[],
            security_issues=[],
            defect_score=50,
        )

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            '{"style_relevant": true, "defect_relevant": true, '
            '"irrelevant_indices_style": [1], "irrelevant_indices_defect": [], '
            '"issues_flagged": ["style[1] hallucinated"]}'
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch("groq.Groq", return_value=mock_client):
            out, _ = qa_checker.check_quality("def f():\n    pass\n", style, defect)

        assert len(out.filtered_style_findings) == 1
        assert out.filtered_style_findings[0].description == "real naming issue"
        assert len(out.filtered_defect_findings) == 1


# ── Style Analyst parsing with mocked retrieval + Groq ───────────────────────

class TestStyleAnalystParsing:
    def test_parses_deviation_findings_from_mocked_llm(self):
        from backend.src.agents import style_analyst
        import backend.src.core.embedder as embedder_mod

        fp = {"type_hint_usage": 1.0, "docstring_coverage": 1.0, "naming_convention": "snake_case"}
        code = "def Add(a, b):\n    return a+b\n"  # violates typed+doc+snake fingerprint

        staged = {
            "files": [],
            "functions": [
                {
                    "source": "def add(a: int, b: int) -> int:\n    \"\"\"Add.\"\"\"\n    return a + b",
                    "metadata": {"function_name": "add", "file_path": "math_util.py"},
                    "distance": 0.1,
                }
            ],
        }
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            '{"findings":[{"category":"type_safety","severity":"high",'
            '"description":"Missing type hints vs fingerprint 100% typed",'
            '"fingerprint_value":"1.0","submitted_value":"0"}],'
            '"overall_style_score":40}'
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp

        with patch.object(
            embedder_mod, "query_similar_staged", return_value=staged
        ), patch("groq.Groq", return_value=mock_client):
            out, _ = style_analyst.analyze_style(
                code, "python", fp, "u", "r", focus_areas=["type_safety"]
            )

        assert out.similar_functions_found == 1
        assert len(out.findings) == 1
        assert out.findings[0].category == "type_safety"
        assert "type" in out.findings[0].description.lower()
        # Defect A: score derived from findings (one high → 100-25=75), LLM scalar ignored
        assert out.overall_style_score == 75.0


class TestStyleAnalystScoring:
    """Defect A/B unit tests — no Groq."""

    def test_score_tracks_severity_weighted_findings(self):
        from backend.src.agents.style_analyst import compute_style_score_from_findings

        high = StyleFinding(category="naming", severity="high", description="camelCase")
        med = StyleFinding(category="type_safety", severity="medium", description="no hints")
        low = StyleFinding(category="style", severity="low", description="minor")
        err = StyleFinding(category="error", severity="low", description="429")

        assert compute_style_score_from_findings([]) == 100.0
        assert compute_style_score_from_findings([high]) == 75.0
        assert compute_style_score_from_findings([high, med]) == 63.0
        assert compute_style_score_from_findings([high, med, low]) == 58.0
        # error findings must not penalize
        assert compute_style_score_from_findings([err]) == 100.0
        assert compute_style_score_from_findings([high, err]) == 75.0

    def test_more_findings_strictly_lower_score(self):
        from backend.src.agents.style_analyst import compute_style_score_from_findings

        a = StyleFinding(category="naming", severity="high", description="a")
        b = StyleFinding(category="type_safety", severity="low", description="b")
        s1 = compute_style_score_from_findings([a])
        s2 = compute_style_score_from_findings([a, b])
        assert s2 < s1

    def test_rare_docstring_missing_is_filtered(self):
        from backend.src.agents.style_analyst import (
            filter_findings_by_fingerprint_direction,
        )

        fp = {
            "docstring_coverage": 0.246,
            "type_hint_usage": 0.993,
            "error_handling_rate": 0.131,
            "comprehension_ratio": 0.016,
            "naming_convention": "snake_case",
        }
        findings = [
            StyleFinding(
                category="documentation",
                severity="high",
                description="The submitted code lacks a docstring",
                fingerprint_value="docstring_coverage: 0.246",
                submitted_value="no docstring",
            ),
            StyleFinding(
                category="naming",
                severity="high",
                description="mergeHeaders does not follow snake_case",
                fingerprint_value="snake_case",
                submitted_value="camelCase",
            ),
        ]
        kept = filter_findings_by_fingerprint_direction(findings, fp)
        assert len(kept) == 1
        assert kept[0].category == "naming"

    def test_common_type_hints_missing_kept(self):
        from backend.src.agents.style_analyst import (
            filter_findings_by_fingerprint_direction,
        )

        fp = {"type_hint_usage": 0.993, "docstring_coverage": 0.246}
        findings = [
            StyleFinding(
                category="type_safety",
                severity="high",
                description="Missing type hints vs fingerprint",
                fingerprint_value="0.993",
                submitted_value="0",
            )
        ]
        kept = filter_findings_by_fingerprint_direction(findings, fp)
        assert len(kept) == 1

    def test_empty_fingerprint_no_direction_filter(self):
        from backend.src.agents.style_analyst import (
            filter_findings_by_fingerprint_direction,
        )

        findings = [
            StyleFinding(
                category="documentation",
                severity="medium",
                description="missing docstring",
            )
        ]
        assert len(filter_findings_by_fingerprint_direction(findings, {})) == 1

    def test_rare_error_handling_underuse_paraphrase_dropped(self):
        from backend.src.agents.style_analyst import filter_style_findings

        fp = {
            "docstring_coverage": 0.246,
            "type_hint_usage": 0.993,
            "error_handling_rate": 0.131,
            "comprehension_ratio": 0.016,
            "naming_convention": "snake_case",
        }
        findings = [
            StyleFinding(
                category="error_handling",
                severity="medium",
                description=(
                    "The submitted code does not handle potential errors "
                    "when parsing the 'Set-Cookie' header."
                ),
                fingerprint_value="error_handling_rate: 0.131",
                submitted_value="no try/except",
            ),
            StyleFinding(
                category="naming",
                severity="high",
                description="mergeHeaders does not follow snake_case",
                fingerprint_value="snake_case",
                submitted_value="camelCase",
            ),
        ]
        kept = filter_style_findings(findings, fp)
        assert len(kept) == 1
        assert kept[0].category == "naming"

    def test_rare_relative_overuse_dropped_absolute_kept(self):
        from backend.src.agents.style_analyst import filter_style_findings

        fp = {"docstring_coverage": 0.246, "type_hint_usage": 0.993}
        relative = StyleFinding(
            category="documentation",
            severity="low",
            description=(
                "Docstring coverage is higher than average for this developer"
            ),
            fingerprint_value="0.246",
            submitted_value="1.0",
        )
        absolute = StyleFinding(
            category="documentation",
            severity="medium",
            description="Excessive docstring verbosity vs rare docstring habit",
            fingerprint_value="0.246",
            submitted_value="long module docstring on every function",
        )
        kept = filter_style_findings([relative, absolute], fp)
        assert len(kept) == 1
        assert "excessive" in kept[0].description.lower()

    def test_praise_and_generic_prior_suppressed(self):
        from backend.src.agents.style_analyst import filter_style_findings

        fp = {
            "docstring_coverage": 0.246,
            "type_hint_usage": 0.993,
            "error_handling_rate": 0.131,
            "naming_convention": "snake_case",
        }
        findings = [
            StyleFinding(
                category="naming",
                severity="low",
                description=(
                    "The submitted code's function name 'build_url' "
                    "follows the snake_case convention."
                ),
            ),
            StyleFinding(
                category="error_handling",
                severity="low",
                description=(
                    "No error handling, which is consistent with the "
                    "developer's error_handling_rate of 0.131"
                ),
            ),
            StyleFinding(
                category="naming",
                severity="low",
                description="The variable name 'rest' could be more descriptive.",
            ),
            StyleFinding(
                category="naming",
                severity="high",
                description="parseStatus uses camelCase not snake_case",
                fingerprint_value="snake_case",
                submitted_value="camelCase",
            ),
        ]
        kept = filter_style_findings(findings, fp)
        assert len(kept) == 1
        assert "camelCase" in kept[0].description

    def test_edge_case_handle_not_dropped_as_error_handling_underuse(self):
        """'does not handle None' is not fingerprint under-use of try/except."""
        from backend.src.agents.style_analyst import filter_style_findings

        fp = {"error_handling_rate": 0.131, "type_hint_usage": 0.993}
        findings = [
            StyleFinding(
                category="style",
                severity="medium",
                description=(
                    "The function does not handle the case where the input "
                    "URL is None or empty."
                ),
            )
        ]
        # Not praise / not rare-under-use of error_handling_rate → kept
        # (may still be a nit; suppress is for descriptive/runtime/simplify).
        kept = filter_style_findings(findings, fp)
        assert len(kept) == 1

class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_parallel_style_and_defect_overlap_in_time(self):
        from backend.src.agents import orchestrator
        from backend.src.core.models import (
            ConfidenceOutput,
            PlannerOutput,
            PseudoRefOutput,
            QualityGateResult,
            STSScores,
        )

        def slow_style(*_a, **_k):
            time.sleep(0.15)
            return (
                StyleAnalysisOutput(
                    findings=[StyleFinding(category="naming", severity="low", description="style-A")],
                    overall_style_score=70,
                    similar_functions_found=5,
                ),
                150,
            )

        def slow_defect(*_a, **_k):
            time.sleep(0.15)
            return (
                DefectHunterOutput(
                    bugs=[DefectFinding(severity="medium", description="defect-B", category="bug")],
                    code_smells=[],
                    security_issues=[],
                    defect_score=70,
                ),
                150,
            )

        def passthrough_qa(code, style_output, defect_output):
            all_d = defect_output.bugs + defect_output.code_smells + defect_output.security_issues
            return (
                QACheckerOutput(
                    style_relevant=True,
                    defect_relevant=True,
                    filtered_style_findings=style_output.findings,
                    filtered_defect_findings=all_d,
                ),
                1,
            )

        with patch.object(orchestrator, "plan_review", return_value=(
            PlannerOutput(focus_areas=["naming"], review_depth="standard", strategy_notes="t"),
            1,
        )), patch.object(orchestrator, "analyze_style", side_effect=slow_style), patch.object(
            orchestrator, "hunt_defects", side_effect=slow_defect
        ), patch.object(orchestrator, "check_quality", side_effect=passthrough_qa), patch.object(
            orchestrator, "evaluate_confidence", return_value=(
                ConfidenceOutput(confidence_score=0.9, is_confident=True, reason="ok", suggestion=""),
                1,
            )
        ), patch.object(orchestrator, "generate_pseudo_references", return_value=PseudoRefOutput(
            references=[], generation_time_ms=0
        )), patch.object(orchestrator, "compute_sts_scores", return_value=(
            STSScores(comprehensiveness=0.8, conciseness=0.8, relevance=0.8),
            1,
        )), patch.object(orchestrator, "evaluate_quality", return_value=(
            QualityGateResult(passed=True, should_re_review=False, reason="ok"),
            1,
        )):
            t0 = time.monotonic()
            result = await orchestrator.run_review(
                code="def f():\n    return 1\n",
                language="python",
                fingerprint={"type_hint_usage": 1.0},
                user_id="u",
                repo_name="r",
                max_iterations=1,
            )
            wall = time.monotonic() - t0

        descs = [i["description"] for i in result.issues]
        assert "style-A" in descs
        assert "defect-B" in descs
        # If strictly sequential, wall >= ~0.30s; parallel should be closer to 0.15s
        assert wall < 0.28, f"Style+Defect appear sequential (wall={wall:.3f}s)"

    @pytest.mark.asyncio
    async def test_aggregates_without_dropping_findings(self):
        from backend.src.agents import orchestrator
        from backend.src.core.models import (
            ConfidenceOutput,
            PlannerOutput,
            PseudoRefOutput,
            QualityGateResult,
            STSScores,
        )

        style = StyleAnalysisOutput(
            findings=[
                StyleFinding(category="naming", severity="low", description="keep-style-1"),
                StyleFinding(category="docs", severity="low", description="keep-style-2"),
            ],
            overall_style_score=60,
            similar_functions_found=5,
        )
        defect = DefectHunterOutput(
            bugs=[DefectFinding(severity="high", description="keep-defect-1", category="bug")],
            code_smells=[],
            security_issues=[],
            defect_score=50,
        )

        def passthrough_qa(code, style_output, defect_output):
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

        with patch.object(orchestrator, "plan_review", return_value=(
            PlannerOutput(focus_areas=[], review_depth="standard", strategy_notes="t"),
            1,
        )), patch.object(orchestrator, "analyze_style", return_value=(style, 1)), patch.object(
            orchestrator, "hunt_defects", return_value=(defect, 1)
        ), patch.object(orchestrator, "check_quality", side_effect=passthrough_qa), patch.object(
            orchestrator, "evaluate_confidence", return_value=(
                ConfidenceOutput(confidence_score=0.9, is_confident=True, reason="ok", suggestion=""),
                1,
            )
        ), patch.object(orchestrator, "generate_pseudo_references", return_value=PseudoRefOutput(
            references=[], generation_time_ms=0
        )), patch.object(orchestrator, "compute_sts_scores", return_value=(
            STSScores(comprehensiveness=0.9, conciseness=0.9, relevance=0.9),
            1,
        )), patch.object(orchestrator, "evaluate_quality", return_value=(
            QualityGateResult(passed=True, should_re_review=False, reason="ok"),
            1,
        )):
            result = await orchestrator.run_review(
                "def f():\n    return 1\n", "python", {}, "u", "r", max_iterations=1
            )

        descs = [i["description"] for i in result.issues]
        assert descs.count("keep-style-1") == 1
        assert descs.count("keep-style-2") == 1
        assert descs.count("keep-defect-1") == 1
        assert len(result.issues) == 3


# ── Live Groq smoke (excluded from fast runs) ────────────────────────────────

@pytest.mark.groq
def test_defect_hunter_live_catches_planted_bug():
    code = "def f(xs=[]):\n    try:\n        return xs\n    except:\n        return None\n"
    out, _ = hunt_defects(code, "python")
    texts = " ".join(f.description for f in out.bugs + out.code_smells)
    assert "Mutable default" in texts or "Bare except" in texts
