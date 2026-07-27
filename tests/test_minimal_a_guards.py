"""Step 5 — minimal_a honesty guards (no Groq calls)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
MINIMAL_A = ROOT / "evals" / "minimal_a.py"


def _load_minimal_a():
    spec = importlib.util.spec_from_file_location("minimal_a_under_test", MINIMAL_A)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid executing main; load module body only
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ma():
    return _load_minimal_a()


class TestMinimalAHonestyGuards:
    def test_backoff_schedule_intact(self, ma):
        assert ma.BACKOFF_SLEEPS == (5, 15, 45, 90)
        assert ma.MAX_RETRIES == 4

    def test_count_style_findings_excludes_error_category(self, ma):
        result = SimpleNamespace(
            issues=[
                {"type": "style", "category": "naming", "description": "real"},
                {"type": "style", "category": "error", "description": "Style analysis error: 429"},
                {"type": "defect", "category": "bug", "description": "not style"},
                {"type": "style", "category": "documentation", "description": "real2"},
            ]
        )
        assert ma._count_style_findings(result) == 2

    def test_error_category_never_counted_as_real_finding_regression(self, ma):
        """
        Regression guard for the flat-1.0 corruption: a rate-limit fallback that
        emits category='error' must never contribute to n_style_findings.
        """
        poisoned = SimpleNamespace(
            issues=[
                {
                    "type": "style",
                    "category": "error",
                    "description": "Style analysis error: Rate limit",
                }
            ]
        )
        n = ma._count_style_findings(poisoned)
        assert n == 0, (
            "category='error' style issue was counted as a real finding — "
            "this reintroduces the flat-1.0 benchmark corruption"
        )

    def test_aggregate_excludes_throttled_cases(self, ma):
        per_pair = [
            {
                "id": "p1",
                "versions": {
                    "in_style": {
                        "personalized": {
                            "n_style_findings": 0,
                            "throttled": False,
                            "error": None,
                        },
                        "generic": {
                            "n_style_findings": 1,
                            "throttled": False,
                            "error": None,
                        },
                    },
                    "off_style": {
                        "personalized": {
                            "n_style_findings": 3,
                            "throttled": True,
                            "error": "429",
                        },
                        "generic": {
                            "n_style_findings": 2,
                            "throttled": False,
                            "error": None,
                        },
                    },
                },
            }
        ]
        agg = ma._aggregate(per_pair)
        assert "p1/off_style" in agg["throttled_excluded"]
        # Only in_style survived
        assert agg["personalized"]["n_in"] == 1
        assert agg["personalized"]["n_off"] == 0
        assert agg["personalized"]["avg_style_findings_in_style"] == 0.0
        assert agg["personalized"]["avg_style_findings_off_style"] is None

    def test_degenerate_detector_matches_collapse_pattern(self, ma):
        assert ma._is_degenerate(
            {"style_score": 50.0, "exec_ms": 100, "n_style_findings": 0}
        )
        assert not ma._is_degenerate(
            {"style_score": 50.0, "exec_ms": 100, "n_style_findings": 2}
        )


class TestMinimalARecommendation:
    def test_docs_note_blocked_not_broken(self, ma):
        """Harness structure present; quantitative result needs call budget — not a code fix."""
        src = MINIMAL_A.read_text(encoding="utf-8")
        assert "_count_style_findings" in src
        assert "BACKOFF_SLEEPS" in src
        assert "throttled_excluded" in src or "throttled_cases" in src
