"""
Quality Gate — Layer 3 evaluation.

Makes the pass/fail decision on a review based on STS scores and triggers
Agentic Loop 2 (re-review) when quality is insufficient.

Rules-based, no LLM call — instant execution (~0ms), same design philosophy
as the Confidence Evaluator in Layer 2.

Thresholds calibrated from CRScore (NAACL 2025) findings:
  comp  ≥ 0.40  — review covers at least 40% of expected issues (recall)
  conc  ≥ 0.30  — at least 30% of review sentences are on-topic (precision)
  rel   ≥ 0.35  — harmonic mean above 0.35 (overall quality floor)
"""
from __future__ import annotations

import time

from backend.src.core.models import QualityGateResult, STSScores


def evaluate_quality(
    sts_scores: STSScores,
    comp_threshold: float = 0.4,
    conc_threshold: float = 0.3,
    rel_threshold: float = 0.35,
) -> tuple[QualityGateResult, int]:
    """
    Quality gate decision. Rules-based, instant.

    Args:
        sts_scores:      output of compute_sts_scores()
        comp_threshold:  minimum comprehensiveness (recall-like)
        conc_threshold:  minimum conciseness (precision-like)
        rel_threshold:   minimum relevance (F1-like harmonic mean)

    Returns:
        (QualityGateResult, execution_time_ms)
    """
    start = time.time()

    reasons: list[str] = []

    comp_pass = sts_scores.comprehensiveness >= comp_threshold
    conc_pass = sts_scores.conciseness >= conc_threshold
    rel_pass  = sts_scores.relevance >= rel_threshold

    if not comp_pass:
        reasons.append(
            f"Comprehensiveness {sts_scores.comprehensiveness:.2f} below threshold {comp_threshold}"
            f" — review missed important issues"
        )
    if not conc_pass:
        reasons.append(
            f"Conciseness {sts_scores.conciseness:.2f} below threshold {conc_threshold}"
            f" — review contains too much irrelevant content"
        )
    if not rel_pass:
        reasons.append(
            f"Relevance {sts_scores.relevance:.2f} below threshold {rel_threshold}"
            f" — review quality below acceptable level"
        )

    passed = comp_pass and conc_pass and rel_pass

    result = QualityGateResult(
        passed=passed,
        comprehensiveness=sts_scores.comprehensiveness,
        conciseness=sts_scores.conciseness,
        relevance=sts_scores.relevance,
        reason="; ".join(reasons) if reasons else "All quality dimensions passed",
        should_re_review=not passed,
    )

    elapsed = int((time.time() - start) * 1000)
    return result, elapsed
