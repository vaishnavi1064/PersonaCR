"""
Orchestrator — wires all agents and manages the two agentic loops.

Parallelism optimizations (from research papers):
  - Style Analyst + Defect Hunter: asyncio.gather() (RevAgent 2025)
  - QA Checker runs first, then Confidence Evaluator uses its output —
    they share no I/O wait so total wall-clock time ≈ max(qa_ms, conf_ms)
    even when chained. Confidence Evaluator is ~0ms so the serial cost is negligible.

Agentic Loop 1 (Confidence — inside the while loop):
  If confidence_score < 0.70 and iteration < max_iterations, the while loop
  continues. Planner picks up ConfidenceOutput.suggestion on next pass.

Agentic Loop 2 (Quality Gate — after the while loop):
  After Loop 1 settles, Layer 3 evaluates the review with STS scoring.
  If quality_gate.should_re_review=True and iterations remain, the full
  Layer 2 pipeline re-runs with quality-gate feedback injected into the
  Planner's context, followed by a fresh Layer 3 evaluation.

Max 2 iterations is intentional (Latency-Aware 2026): diminishing returns
beyond two passes rarely justify the added LLM latency.
"""
from __future__ import annotations

import asyncio

from backend.src.core.models import (
    AgentTrace,
    ReviewResult,
)
from backend.src.agents.planner import plan_review
from backend.src.agents.style_analyst import analyze_style
from backend.src.agents.defect_hunter import hunt_defects
from backend.src.agents.qa_checker import check_quality
from backend.src.agents.confidence_evaluator import evaluate_confidence
from backend.src.evaluation.pseudo_ref_gen import generate_pseudo_references
from backend.src.evaluation.sts_scorer import compute_sts_scores
from backend.src.evaluation.quality_gate import evaluate_quality


async def _run_in_executor(func, *args):
    """Run a blocking (sync) function inside asyncio without blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


async def run_review(
    code: str,
    language: str,
    fingerprint: dict,
    user_id: str,
    repo_name: str,
    max_iterations: int = 2,
) -> ReviewResult:
    """
    Main orchestrator. Runs the full multi-agent review pipeline.

    Flow:
      1. Planner decides focus areas and review depth
      2. Style Analyst + Defect Hunter run in PARALLEL (asyncio.gather)
      3. QA Checker validates findings → Confidence Evaluator scores quality
      4. If confidence < 0.7 and iterations remain → re-plan (Agentic Loop 1)
      5. Layer 3: Pseudo-ref generation → STS scoring → Quality gate
      6. Return combined ReviewResult with quality scores
    """
    traces: list[AgentTrace] = []
    iteration = 0

    # These are set inside the loop; initialise so the type checker is happy.
    plan_output = None
    style_output = None
    defect_output = None
    qa_output = None
    conf_output = None

    while iteration < max_iterations:
        iteration += 1

        # ── Step 1: Planner ───────────────────────────────────────────────────
        plan_output, plan_ms = plan_review(code, language, fingerprint)
        traces.append(AgentTrace(
            agent_name="planner",
            input_summary=f"{language} code, {len(code.splitlines())} lines",
            output_summary=f"Focus: {plan_output.focus_areas}, Depth: {plan_output.review_depth}",
            decision=plan_output.strategy_notes,
            execution_time_ms=plan_ms,
            iteration=iteration,
        ))

        # ── Step 2: Style Analyst + Defect Hunter IN PARALLEL ─────────────────
        style_future = _run_in_executor(
            analyze_style,
            code,
            language,
            fingerprint,
            user_id,
            repo_name,
            plan_output.focus_areas,
        )
        defect_future = _run_in_executor(hunt_defects, code, language)

        (style_output, style_ms), (defect_output, defect_ms) = await asyncio.gather(
            style_future, defect_future
        )

        traces.append(AgentTrace(
            agent_name="style_analyst",
            input_summary=(
                f"Code + {style_output.similar_functions_found} similar functions from ChromaDB"
            ),
            output_summary=(
                f"{len(style_output.findings)} findings, score={style_output.overall_style_score}"
            ),
            decision=f"Found {len(style_output.findings)} style deviations",
            execution_time_ms=style_ms,
            iteration=iteration,
        ))
        traces.append(AgentTrace(
            agent_name="defect_hunter",
            input_summary=f"{language} code, {len(code.splitlines())} lines",
            output_summary=(
                f"Bugs={len(defect_output.bugs)}, "
                f"Smells={len(defect_output.code_smells)}, "
                f"Security={len(defect_output.security_issues)}"
            ),
            decision=f"Defect score: {defect_output.defect_score}",
            execution_time_ms=defect_ms,
            iteration=iteration,
        ))

        # ── Step 3: QA Checker → Confidence Evaluator ────────────────────────
        # QA must finish before Confidence (it consumes QA output), but since
        # evaluate_confidence is ~0ms, the total wall-clock cost is just qa_ms.
        qa_output, qa_ms = check_quality(code, style_output, defect_output)
        conf_output, conf_ms = evaluate_confidence(
            qa_output,
            similar_functions_found=style_output.similar_functions_found,
            style_score=style_output.overall_style_score,
            defect_score=defect_output.defect_score,
        )

        traces.append(AgentTrace(
            agent_name="qa_checker",
            input_summary=(
                f"Style: {len(style_output.findings)} findings, "
                f"Defect: {len(defect_output.bugs)} bugs"
            ),
            output_summary=(
                f"Flagged: {len(qa_output.issues_flagged)} issues, "
                f"Style relevant={qa_output.style_relevant}"
            ),
            decision=(
                "; ".join(qa_output.issues_flagged[:3])
                if qa_output.issues_flagged
                else "All findings relevant"
            ),
            execution_time_ms=qa_ms,
            iteration=iteration,
        ))
        traces.append(AgentTrace(
            agent_name="confidence_evaluator",
            input_summary=(
                f"Similar funcs={style_output.similar_functions_found}, "
                f"Style={style_output.overall_style_score}, "
                f"Defect={defect_output.defect_score}"
            ),
            output_summary=(
                f"Confidence={conf_output.confidence_score}, "
                f"Confident={conf_output.is_confident}"
            ),
            decision=conf_output.reason,
            execution_time_ms=conf_ms,
            iteration=iteration,
        ))

        # ── Step 4: Agentic Loop 1 check ─────────────────────────────────────
        if conf_output.is_confident or iteration >= max_iterations:
            break
        # Low confidence → loop back; Planner will see suggestion on next pass

    # ── Build issue list (needed by Layer 3 before we return) ────────────────
    all_issues: list[dict] = []

    for f in qa_output.filtered_style_findings:
        all_issues.append({
            "type": "style",
            "category": f.category,
            "severity": f.severity,
            "description": f.description,
            "fingerprint_value": f.fingerprint_value,
            "submitted_value": f.submitted_value,
        })

    for f in qa_output.filtered_defect_findings:
        all_issues.append({
            "type": "defect",
            "category": f.category,
            "severity": f.severity,
            "description": f.description,
            "line_hint": f.line_hint,
        })

    # ── Layer 3: Quality evaluation (CRScore-inspired) ────────────────────────
    review_sentences = [
        issue["description"] for issue in all_issues if issue.get("description")
    ]

    pseudo_refs = generate_pseudo_references(code, language)
    traces.append(AgentTrace(
        agent_name="pseudo_ref_generator",
        input_summary=f"{language} code, {len(code.splitlines())} lines",
        output_summary=f"Generated {len(pseudo_refs.references)} pseudo-references",
        decision=f"AST + LLM pseudo-refs in {pseudo_refs.generation_time_ms}ms",
        execution_time_ms=pseudo_refs.generation_time_ms,
        iteration=iteration,
    ))

    sts_scores, sts_ms = compute_sts_scores(review_sentences, pseudo_refs.references)
    traces.append(AgentTrace(
        agent_name="sts_scorer",
        input_summary=(
            f"{len(review_sentences)} review sentences, "
            f"{len(pseudo_refs.references)} pseudo-refs"
        ),
        output_summary=(
            f"Comp={sts_scores.comprehensiveness}, "
            f"Conc={sts_scores.conciseness}, "
            f"Rel={sts_scores.relevance}"
        ),
        decision=f"STS scoring in {sts_ms}ms",
        execution_time_ms=sts_ms,
        iteration=iteration,
    ))

    gate_result, gate_ms = evaluate_quality(sts_scores)
    traces.append(AgentTrace(
        agent_name="quality_gate",
        input_summary=(
            f"Comp={sts_scores.comprehensiveness}, "
            f"Conc={sts_scores.conciseness}, "
            f"Rel={sts_scores.relevance}"
        ),
        output_summary=f"Passed={gate_result.passed}",
        decision=gate_result.reason,
        execution_time_ms=gate_ms,
        iteration=iteration,
    ))

    # ── Agentic Loop 2: Quality gate re-review ───────────────────────────────
    # Runs AFTER Loop 1 (confidence) completes. Separate loop — does not share
    # the iteration counter with Loop 1. Capped at one re-review pass to bound
    # total latency.
    if gate_result.should_re_review and iteration < max_iterations:
        quality_feedback = gate_result.reason

        traces.append(AgentTrace(
            agent_name="quality_gate_reloop",
            input_summary=(
                f"Comp={sts_scores.comprehensiveness}, "
                f"Conc={sts_scores.conciseness}, "
                f"Rel={sts_scores.relevance}"
            ),
            output_summary=f"Triggering re-review (iteration {iteration + 1})",
            decision=f"Quality gate failed: {quality_feedback[:100]}",
            execution_time_ms=0,
            iteration=iteration,
        ))

        iteration += 1

        # Enrich fingerprint with quality feedback so Planner can adapt focus
        enriched_fp = dict(fingerprint)
        enriched_fp["_quality_feedback"] = quality_feedback
        enriched_fp["_previous_focus"] = plan_output.focus_areas if plan_output else []

        plan_output, plan_ms = plan_review(code, language, enriched_fp)
        traces.append(AgentTrace(
            agent_name="planner",
            input_summary=f"Re-plan with quality feedback: {quality_feedback[:60]}",
            output_summary=f"Focus: {plan_output.focus_areas}, Depth: {plan_output.review_depth}",
            decision=f"Re-plan after quality gate failure: {plan_output.strategy_notes[:80]}",
            execution_time_ms=plan_ms,
            iteration=iteration,
        ))

        # Re-run Style + Defect in parallel
        style_future = _run_in_executor(
            analyze_style, code, language, fingerprint, user_id, repo_name,
            plan_output.focus_areas,
        )
        defect_future = _run_in_executor(hunt_defects, code, language)
        (style_output, style_ms), (defect_output, defect_ms) = await asyncio.gather(
            style_future, defect_future
        )
        traces.append(AgentTrace(
            agent_name="style_analyst",
            input_summary=f"Re-review iteration {iteration}",
            output_summary=f"{len(style_output.findings)} findings, score={style_output.overall_style_score}",
            decision=f"Re-review found {len(style_output.findings)} style deviations",
            execution_time_ms=style_ms,
            iteration=iteration,
        ))
        traces.append(AgentTrace(
            agent_name="defect_hunter",
            input_summary=f"Re-review iteration {iteration}",
            output_summary=f"Bugs={len(defect_output.bugs)}, Smells={len(defect_output.code_smells)}",
            decision=f"Re-review defect score: {defect_output.defect_score}",
            execution_time_ms=defect_ms,
            iteration=iteration,
        ))

        # Re-run QA + Confidence
        qa_output, qa_ms = check_quality(code, style_output, defect_output)
        conf_output, conf_ms = evaluate_confidence(
            qa_output,
            similar_functions_found=style_output.similar_functions_found,
            style_score=style_output.overall_style_score,
            defect_score=defect_output.defect_score,
        )
        traces.append(AgentTrace(
            agent_name="qa_checker",
            input_summary=f"Re-review iteration {iteration}",
            output_summary=f"Flagged: {len(qa_output.issues_flagged)}",
            decision="Re-review QA check",
            execution_time_ms=qa_ms,
            iteration=iteration,
        ))
        traces.append(AgentTrace(
            agent_name="confidence_evaluator",
            input_summary=f"Re-review iteration {iteration}",
            output_summary=f"Confidence={conf_output.confidence_score}",
            decision=conf_output.reason,
            execution_time_ms=conf_ms,
            iteration=iteration,
        ))

        # Rebuild issues from refreshed QA output
        all_issues = []
        for f in qa_output.filtered_style_findings:
            all_issues.append({
                "type": "style", "category": f.category, "severity": f.severity,
                "description": f.description, "fingerprint_value": f.fingerprint_value,
                "submitted_value": f.submitted_value,
            })
        for f in qa_output.filtered_defect_findings:
            all_issues.append({
                "type": "defect", "category": f.category, "severity": f.severity,
                "description": f.description, "line_hint": f.line_hint,
            })

        # Re-run Layer 3 on new review output
        review_sentences = [
            issue["description"] for issue in all_issues if issue.get("description")
        ]
        pseudo_refs = generate_pseudo_references(code, language)
        sts_scores, sts_ms = compute_sts_scores(review_sentences, pseudo_refs.references)
        gate_result, gate_ms = evaluate_quality(sts_scores)

        traces.append(AgentTrace(
            agent_name="sts_scorer",
            input_summary=f"Re-evaluation iteration {iteration}",
            output_summary=(
                f"Comp={sts_scores.comprehensiveness}, "
                f"Conc={sts_scores.conciseness}, "
                f"Rel={sts_scores.relevance}"
            ),
            decision=f"Re-evaluation STS in {sts_ms}ms",
            execution_time_ms=sts_ms,
            iteration=iteration,
        ))
        traces.append(AgentTrace(
            agent_name="quality_gate",
            input_summary=f"Re-evaluation iteration {iteration}",
            output_summary=f"Passed={gate_result.passed}",
            decision=gate_result.reason,
            execution_time_ms=gate_ms,
            iteration=iteration,
        ))

    # ── Final score and status ────────────────────────────────────────────────
    overall_score = round(
        (style_output.overall_style_score * 0.5 + defect_output.defect_score * 0.5), 1
    )

    if conf_output.is_confident and gate_result.passed:
        status = "passed"
    elif not conf_output.is_confident:
        status = "low_confidence"
    elif not gate_result.passed:
        status = "quality_gate_failed"
    else:
        status = "passed"

    return ReviewResult(
        review_output={
            "style_score": style_output.overall_style_score,
            "defect_score": defect_output.defect_score,
            "similar_functions_used": style_output.similar_functions_found,
            "plan": plan_output.model_dump() if plan_output else {},
            "confidence": conf_output.model_dump(),
            "quality_scores": {
                "comprehensiveness": sts_scores.comprehensiveness,
                "conciseness": sts_scores.conciseness,
                "relevance": sts_scores.relevance,
            },
            "quality_gate_passed": gate_result.passed,
            "pseudo_refs_generated": len(pseudo_refs.references),
        },
        overall_score=overall_score,
        issues=all_issues,
        agent_trace=traces,
        iterations=iteration,
        status=status,
    )


def review_code_sync(
    code: str,
    language: str,
    fingerprint: dict,
    user_id: str,
    repo_name: str,
) -> ReviewResult:
    """Sync wrapper — convenience entry point for FastAPI endpoints."""
    return asyncio.run(run_review(code, language, fingerprint, user_id, repo_name))
