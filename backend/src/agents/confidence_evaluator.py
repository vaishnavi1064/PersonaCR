"""
Confidence Evaluator Agent — rules-based scoring of review quality.

No LLM call — instant execution (~0ms).

This is Agentic Loop 1: if confidence_score < 0.7, the orchestrator sends the
review back to the Planner for a broader search / different focus strategy.

Key optimization from Latency-Aware Multi-Agent Architecture Search (2026):
keeping validators off the critical LLM path eliminates the most avoidable
latency in multi-agent pipelines.

Scoring breakdown (max 1.0):
  0.30 — ChromaDB retrieval quality (how many similar functions were found)
  0.30 — QA validation (are both agent outputs deemed relevant?)
  0.20 — Finding count sanity (did agents actually surface actionable findings?)
  0.20 — Score consistency (are style/defect scores in a sane range?)
"""
from __future__ import annotations

import time

from backend.src.core.models import ConfidenceOutput, QACheckerOutput


def evaluate_confidence(
    qa_output: QACheckerOutput,
    similar_functions_found: int,
    style_score: float,
    defect_score: float,
) -> tuple[ConfidenceOutput, int]:
    """
    Rules-based confidence scoring. No LLM call — instant execution.
    Returns (ConfidenceOutput, execution_time_ms).
    """
    start = time.time()

    score = 0.0
    reasons: list[str] = []
    suggestions: list[str] = []

    # ── Factor 1: ChromaDB retrieval quality (0–0.30) ────────────────────────
    if similar_functions_found >= 5:
        score += 0.3
    elif similar_functions_found >= 3:
        score += 0.2
        reasons.append(f"Only {similar_functions_found} similar functions found (want 5+)")
        suggestions.append("Broaden ChromaDB search or analyze more files")
    elif similar_functions_found >= 1:
        score += 0.1
        reasons.append(f"Only {similar_functions_found} similar function(s) — weak style comparison")
        suggestions.append("Broaden search radius significantly")
    else:
        reasons.append("No similar functions found — style comparison unreliable")
        suggestions.append("Ensure repo has been analyzed and contains matching language")

    # ── Factor 2: QA validation (0–0.30) ─────────────────────────────────────
    if qa_output.style_relevant and qa_output.defect_relevant:
        score += 0.3
    elif qa_output.style_relevant or qa_output.defect_relevant:
        score += 0.15
        reasons.append("QA flagged one agent's output as partially irrelevant")
    else:
        reasons.append("QA flagged both agents' outputs — review may be off-topic")
        suggestions.append("Re-run with more focused prompts")

    # ── Factor 3: Finding count sanity (0–0.20) ───────────────────────────────
    total_findings = (
        len(qa_output.filtered_style_findings) + len(qa_output.filtered_defect_findings)
    )
    if total_findings >= 2:
        score += 0.2
    elif total_findings >= 1:
        score += 0.1
        reasons.append("Very few findings — review may be incomplete")
    else:
        reasons.append("No findings after QA filtering — agents may have missed issues")
        suggestions.append("Re-plan with different focus areas")

    # ── Factor 4: Score consistency (0–0.20) ──────────────────────────────────
    if 20 <= style_score <= 95 and 20 <= defect_score <= 95:
        score += 0.2
    elif style_score in (0, 100) or defect_score in (0, 100):
        score += 0.05
        reasons.append("Extreme scores (0 or 100) suggest unreliable evaluation")
    else:
        score += 0.1

    score = round(min(score, 1.0), 2)
    is_confident = score >= 0.7

    reason = "; ".join(reasons) if reasons else "All confidence factors passed"
    suggestion = "; ".join(suggestions) if suggestions else ""

    result = ConfidenceOutput(
        confidence_score=score,
        is_confident=is_confident,
        reason=reason,
        suggestion=suggestion,
    )

    elapsed = int((time.time() - start) * 1000)
    return result, elapsed
