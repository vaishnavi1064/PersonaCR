"""
Planner Agent — decides the review strategy before any review agents run.

Hybrid approach (Latency-Aware Multi-Agent Architecture Search, 2026):
- Rules-based fast path first: no LLM call when deviations are obvious.
- LLM slow path (Groq / Llama-3.3-70B) only for complex/ambiguous cases.
  Reducing serial LLM calls on the critical path is the #1 latency lever.
"""
from __future__ import annotations

import json
import re
import time

from dotenv import load_dotenv

from backend.src.core.models import PlannerOutput

load_dotenv("backend/.env")


def _rules_based_plan(code: str, language: str, fingerprint: dict) -> PlannerOutput | None:
    """
    Fast path: if the code is simple and deviations are obvious from the
    fingerprint, return a plan without calling the LLM.
    Returns None if the code is too complex for rules-based planning.
    """
    lines = [line for line in code.strip().splitlines() if line.strip()]
    num_lines = len(lines)

    has_try = bool(re.search(r"\b(try|except|catch|finally)\b", code))
    has_loops = bool(re.search(r"\b(for|while)\b", code))  # noqa: F841 — used implicitly in strategy
    has_conditionals = bool(re.search(r"\b(if|elif|else|switch)\b", code))  # noqa: F841

    focus_areas: list[str] = []
    priority_issues: list[str] = []

    fp_error_rate = fingerprint.get("error_handling_rate", 0)
    fp_avg_length = fingerprint.get("avg_function_length", 15)
    fp_docstring = fingerprint.get("docstring_coverage", 0)
    fp_comment_density = fingerprint.get("comment_density", 0)

    if fp_error_rate > 0.5 and not has_try:
        focus_areas.append("error_handling")
        priority_issues.append(
            f"Fingerprint shows {fp_error_rate:.0%} error handling but submitted code has none"
        )

    if num_lines > fp_avg_length * 2.5:
        focus_areas.append("complexity")
        priority_issues.append(
            f"Code is {num_lines} lines, fingerprint avg is {fp_avg_length:.0f}"
        )

    if fp_docstring > 0.3 and not re.search(r'("""|\'\'\'|/\*\*|///)', code):
        focus_areas.append("documentation")
        priority_issues.append(
            f"Fingerprint shows {fp_docstring:.0%} docstring coverage but submitted code has none"
        )

    if fp_comment_density > 0.05 and code.count("#") + code.count("//") == 0:
        focus_areas.append("comments")

    if len(focus_areas) >= 2:
        return PlannerOutput(
            focus_areas=focus_areas[:5],
            review_depth="thorough" if num_lines > 50 else "standard",
            strategy_notes=f"Rules-based plan: {len(focus_areas)} deviations detected from fingerprint",
            should_split=num_lines > 80,
            priority_issues=priority_issues[:3],
        )

    return None


def plan_review(code: str, language: str, fingerprint: dict) -> tuple[PlannerOutput, int]:
    """
    Main entry point. Returns (PlannerOutput, execution_time_ms).
    Uses rules-based fast path first, falls back to LLM.
    """
    start = time.time()

    rules_plan = _rules_based_plan(code, language, fingerprint)
    if rules_plan is not None:
        elapsed = int((time.time() - start) * 1000)
        return rules_plan, elapsed

    # ── Slow path: Groq LLM ──────────────────────────────────────────────────
    from groq import Groq  # imported lazily — only when needed

    client = Groq()

    fp_summary = json.dumps(
        {
            k: v
            for k, v in fingerprint.items()
            if k not in ("common_patterns", "pattern_frequency", "language_distribution")
        },
        indent=2,
        default=str,
    )

    system_prompt = (
        "You are a code review planner for PersonaCR. Given a developer's coding fingerprint "
        "and new code to review, decide the review strategy.\n\n"
        "Compare the submitted code against the fingerprint and identify likely deviations.\n\n"
        "Return ONLY valid JSON with this exact structure:\n"
        "{\n"
        '  "focus_areas": ["area1", "area2"],\n'
        '  "review_depth": "thorough" or "standard" or "quick",\n'
        '  "strategy_notes": "Brief reasoning",\n'
        '  "should_split": true or false,\n'
        '  "priority_issues": ["issue1", "issue2", "issue3"]\n'
        "}\n\n"
        "Valid focus areas: error_handling, naming, complexity, documentation, "
        "style, security, type_safety, imports"
    )

    user_prompt = (
        f"Developer fingerprint:\n{fp_summary}\n\n"
        f"Submitted code ({language}, {len(code.splitlines())} lines):\n"
        f"```{language}\n{code[:3000]}\n```\n\n"
        "Analyze deviations between the submitted code and the developer's usual patterns. "
        "Return JSON only."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            result = PlannerOutput(**data)
        else:
            result = PlannerOutput(
                focus_areas=["style", "error_handling"],
                review_depth="standard",
                strategy_notes="LLM response parsing failed, using defaults",
            )
    except Exception as e:
        from backend.src.core.metrics import maybe_record_groq_throttle

        maybe_record_groq_throttle(e)
        result = PlannerOutput(
            focus_areas=["style", "error_handling"],
            review_depth="standard",
            strategy_notes=f"Planner error: {str(e)[:100]}",
        )

    elapsed = int((time.time() - start) * 1000)
    return result, elapsed
