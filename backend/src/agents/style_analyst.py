"""
Style Analyst Agent — compares submitted code against the developer's personal patterns.

Uses two-stage ChromaDB retrieval (Ringer 2025) via query_similar_staged():
  Stage 1 — file-level summaries to find the most relevant files fast.
  Stage 2 — function-level chunks within those files for detailed comparison.

Then passes similar functions + fingerprint to Groq (Llama-3.3-70B) to generate
personalised style findings — deviations from THIS developer's patterns, not
generic best-practice violations.
"""
from __future__ import annotations

import json
import re
import time

from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.src.core.models import StyleAnalysisOutput, StyleFinding


def analyze_style(
    code: str,
    language: str,
    fingerprint: dict,
    user_id: str,
    repo_name: str,
    focus_areas: list[str] | None = None,
) -> tuple[StyleAnalysisOutput, int]:
    """
    Compare submitted code against developer's personal patterns.
    Uses two-stage ChromaDB retrieval (Ringer 2025) + Groq LLM.
    Returns (StyleAnalysisOutput, execution_time_ms).
    """
    start = time.time()

    # ── Stage 1 & 2: Two-stage retrieval from ChromaDB ────────────────────────
    from backend.src.core.embedder import query_similar_staged

    staged = query_similar_staged(
        code=code,
        user_id=user_id,
        repo_name=repo_name,
        n_files=3,
        n_functions=8,
        language_filter=language,
    )

    similar_functions = staged.get("functions", [])
    similar_count = len(similar_functions)

    # Build similar code snippets for LLM context
    similar_snippets = ""
    for i, func in enumerate(similar_functions[:5]):
        src = func.get("source", "")[:500]
        meta = func.get("metadata", {})
        fname = meta.get("function_name", "unknown")
        fpath = meta.get("file_path", "unknown")
        similar_snippets += (
            f"\n--- Similar function {i + 1}: {fname} from {fpath} ---\n{src}\n"
        )

    # ── Build fingerprint summary (exclude large / unhelpful fields) ──────────
    fp_summary = {
        k: v
        for k, v in fingerprint.items()
        if k not in ("common_patterns", "pattern_frequency", "language_distribution", "languages")
    }

    focus_hint = ""
    if focus_areas:
        focus_hint = f"\nPay special attention to: {', '.join(focus_areas)}"

    # ── Groq LLM call ─────────────────────────────────────────────────────────
    from groq import Groq

    client = Groq()

    system_prompt = (
        "You are a Style Analyst for PersonaCR. You compare submitted code against a "
        "developer's personal coding patterns (NOT generic best practices).\n\n"
        "Your job: find where the submitted code DEVIATES from how this developer usually writes.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "findings": [\n'
        "    {\n"
        '      "category": "naming|error_handling|complexity|documentation|style|imports|type_safety",\n'
        '      "severity": "high|medium|low",\n'
        '      "description": "What deviates and how",\n'
        '      "fingerprint_value": "What the developer usually does",\n'
        '      "submitted_value": "What the submitted code does instead"\n'
        "    }\n"
        "  ],\n"
        '  "overall_style_score": 0-100\n'
        "}\n\n"
        "Score 100 = perfect match to developer's style. Score 0 = completely different style.\n"
        "Only report DEVIATIONS from personal patterns, not generic code quality issues."
    )

    user_prompt = (
        f"Developer's coding fingerprint:\n{json.dumps(fp_summary, indent=2, default=str)}\n\n"
        f"Similar functions from this developer's codebase:\n"
        f"{similar_snippets if similar_snippets else '(no similar functions found)'}\n\n"
        f"Submitted code ({language}):\n"
        f"```{language}\n{code[:3000]}\n```"
        f"{focus_hint}\n"
        "Compare the submitted code against this developer's patterns. Return JSON only."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        raw = response.choices[0].message.content.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            findings = [StyleFinding(**f) for f in data.get("findings", [])]
            score = float(data.get("overall_style_score", 50))
            result = StyleAnalysisOutput(
                findings=findings,
                overall_style_score=score,
                similar_functions_found=similar_count,
            )
        else:
            result = StyleAnalysisOutput(
                findings=[],
                overall_style_score=50.0,
                similar_functions_found=similar_count,
            )
    except Exception as e:
        result = StyleAnalysisOutput(
            findings=[
                StyleFinding(
                    category="error",
                    severity="low",
                    description=f"Style analysis error: {str(e)[:100]}",
                )
            ],
            overall_style_score=50.0,
            similar_functions_found=similar_count,
        )

    elapsed = int((time.time() - start) * 1000)
    return result, elapsed
