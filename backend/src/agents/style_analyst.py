"""
Style Analyst Agent — compares submitted code against the developer's personal patterns.

Uses two-stage ChromaDB retrieval (Ringer 2025) via query_similar_staged():
  Stage 1 — file-level summaries to find the most relevant files fast.
  Stage 2 — function-level chunks within those files for detailed comparison.

Then passes similar functions + fingerprint to Groq (Llama-3.3-70B) to generate
personalised style findings — deviations from THIS developer's patterns, not
generic best-practice violations.

Scoring (Defect A fix):
  overall_style_score is derived deterministically from findings, not the LLM scalar.
  Mapping (set once; do not retune to a target number):
    start at 100; subtract SEVERITY_PENALTY per non-error finding; floor at 0.
    high=25, medium=12, low=5.
  Invariant: more / severer named deviations ⇒ strictly lower score.

Direction (Defect B fix):
  Rate features in the fingerprint are frequencies of the repo's actual norm.
  Under-use of a rare feature (rate ≤ RARE_MAX) is NOT a deviation; over-use may be.
  Over-use of a common feature (rate ≥ COMMON_MIN) is NOT a deviation; missing may be.
"""
from __future__ import annotations

import json
import re
import time
from typing import Sequence

from dotenv import load_dotenv

from backend.src.core.models import StyleAnalysisOutput, StyleFinding

load_dotenv("backend/.env")

# ── Defect A — severity → score penalty (documented before re-measure) ───────
# Principle: one HIGH personal-pattern break costs a quarter of the 0–100 scale;
# MEDIUM ≈ half of HIGH; LOW is a small ding. Penalties stack; floor at 0.
# Error-category findings (rate-limit fallbacks) never penalize.
SEVERITY_PENALTY: dict[str, float] = {
    "high": 25.0,
    "medium": 12.0,
    "low": 5.0,
}
SCORE_BASE = 100.0

# ── Defect B — rate-feature direction thresholds ─────────────────────────────
RARE_MAX = 0.35     # rate ≤ this → under-use is the norm (do not flag "missing X")
COMMON_MIN = 0.65   # rate ≥ this → presence is the norm (do not flag "has X")

# Rate fingerprint keys + how "under-use" / "over-use" findings look in text.
# Driven by fingerprint values generally — not a docstring special-case.
_RATE_FEATURE_SPECS: list[dict] = [
    {
        "fp_key": "docstring_coverage",
        "categories": {"documentation", "docstring_coverage", "docs"},
        "under_patterns": (
            r"\bmissing\b.{0,40}\bdocstring",
            r"\blacks?\b.{0,40}\bdocstring",
            r"\bno docstring\b",
            r"\bwithout (a )?docstring\b",
            r"\bdocstring coverage\b.{0,40}\b(missing|no|lacks?|absent)",
        ),
        "over_patterns": (
            r"\bverbose docstring\b",
            r"\bexcessive docstring\b",
            r"\btoo (much|many|long).{0,20}\bdocstring",
            r"\bdocstring.{0,40}\b(verbose|excessive|unnecessary|over)",
            r"\bunnecessary docstring\b",
        ),
    },
    {
        "fp_key": "type_hint_usage",
        "categories": {"type_safety", "type_hints", "typing"},
        "under_patterns": (
            r"\bmissing\b.{0,40}\btype\s*hint",
            r"\bno type\s*hint",
            r"\bwithout type\s*hint",
            r"\blacks?\b.{0,40}\btype\s*hint",
            r"\buntyped\b",
        ),
        "over_patterns": (
            r"\bexcessive type\s*hint",
            r"\bunnecessary type\s*hint",
            r"\bover-?(use|typed)\b",
        ),
    },
    {
        "fp_key": "error_handling_rate",
        "categories": {"error_handling"},
        "under_patterns": (
            r"\bmissing\b.{0,40}\b(error handling|try|except)",
            r"\bno (error handling|try/except|try\s*/\s*except)",
            r"\blacks?\b.{0,40}\b(error handling|exception)",
            r"\bwithout (error handling|try)",
        ),
        "over_patterns": (
            r"\bunnecessary\b.{0,40}\b(try|except|error handling)",
            r"\bbroad try\b",
            r"\bover-?(use|ly).{0,20}\b(except|error handling)",
            r"\bexcessive\b.{0,40}\b(try|except|error handling)",
        ),
    },
    {
        "fp_key": "comprehension_ratio",
        "categories": {"style", "complexity", "comprehension"},
        "under_patterns": (
            r"\bmissing\b.{0,40}\bcomprehension",
            r"\bshould use (a )?(list |dict )?comprehension\b",
            r"\bprefer.{0,20}\bcomprehension\b",
        ),
        "over_patterns": (
            r"\bunnecessary\b.{0,40}\bcomprehension",
            r"\bexcessive\b.{0,40}\bcomprehension",
            r"\buses (a )?(list |dict |set )?comprehension\b",
            r"\bcomprehension.{0,40}\b(unnecessary|excessive|over)",
        ),
    },
    {
        "fp_key": "comment_density",
        "categories": {"documentation", "style", "comments"},
        "under_patterns": (
            r"\bmissing\b.{0,40}\bcomment",
            r"\bno comment",
            r"\blacks?\b.{0,40}\bcomment",
            r"\bwithout comment",
        ),
        "over_patterns": (
            r"\bexcessive\b.{0,40}\bcomment",
            r"\btoo many comment",
            r"\bverbose comment",
            r"\bunnecessary comment",
        ),
    },
]


def compute_style_score_from_findings(
    findings: Sequence[StyleFinding | dict],
) -> float:
    """
    Defect A: overall_style_score = f(findings), not a free LLM scalar.

    score = max(0, 100 − Σ penalty(severity)) for findings with category != "error".
    Unknown severities treated as medium.
    """
    total_penalty = 0.0
    for f in findings:
        if isinstance(f, dict):
            category = (f.get("category") or "").lower()
            severity = (f.get("severity") or "medium").lower()
        else:
            category = (f.category or "").lower()
            severity = (f.severity or "medium").lower()
        if category == "error":
            continue
        total_penalty += SEVERITY_PENALTY.get(severity, SEVERITY_PENALTY["medium"])
    return float(max(0.0, SCORE_BASE - total_penalty))


def _finding_text(f: StyleFinding | dict) -> str:
    if isinstance(f, dict):
        parts = [
            f.get("description") or "",
            f.get("fingerprint_value") or "",
            f.get("submitted_value") or "",
            f.get("category") or "",
        ]
    else:
        parts = [
            f.description or "",
            f.fingerprint_value or "",
            f.submitted_value or "",
            f.category or "",
        ]
    return " ".join(parts).lower()


def _finding_category(f: StyleFinding | dict) -> str:
    if isinstance(f, dict):
        return (f.get("category") or "").lower()
    return (f.category or "").lower()


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _direction_for_rate(rate: float) -> str:
    """Return 'rare' | 'common' | 'mid' for a fingerprint rate in [0, 1]."""
    if rate <= RARE_MAX:
        return "rare"
    if rate >= COMMON_MIN:
        return "common"
    return "mid"


def build_fingerprint_direction_guide(fingerprint: dict) -> str:
    """Human-readable direction rules for the LLM, driven by fingerprint rates."""
    if not fingerprint:
        return "(no fingerprint — do not invent personal-pattern deviations)"

    lines = [
        "FINGERPRINT DIRECTION (rates = how often THIS developer does X; not ideals):",
        f"  Thresholds: rare ≤ {RARE_MAX}; common ≥ {COMMON_MIN}.",
    ]
    for spec in _RATE_FEATURE_SPECS:
        key = spec["fp_key"]
        if key not in fingerprint:
            continue
        try:
            rate = float(fingerprint[key])
        except (TypeError, ValueError):
            continue
        direction = _direction_for_rate(rate)
        if direction == "rare":
            lines.append(
                f"  - {key}={rate:.3f} (RARE): under-use / missing is NORMAL — "
                f"do NOT flag absence of this. Only flag clear over-use."
            )
        elif direction == "common":
            lines.append(
                f"  - {key}={rate:.3f} (COMMON): presence is NORMAL — "
                f"flag missing/under-use; do NOT flag presence as a deviation."
            )
        else:
            lines.append(
                f"  - {key}={rate:.3f} (MID): only flag clear departures either way."
            )

    naming = fingerprint.get("naming_convention")
    if naming and naming != "unknown":
        lines.append(
            f"  - naming_convention={naming}: flag names that break this convention."
        )
    return "\n".join(lines)


def filter_findings_by_fingerprint_direction(
    findings: Sequence[StyleFinding],
    fingerprint: dict,
) -> list[StyleFinding]:
    """
    Defect B: drop findings that invert fingerprint direction.

    If a rate feature is RARE, drop under-use ("missing X") findings for that feature.
    If a rate feature is COMMON, drop over-use ("has / excessive X") findings.
    Empty fingerprint → no filtering. category=error always kept (honesty path).
    """
    if not fingerprint:
        return list(findings)

    kept: list[StyleFinding] = []
    for f in findings:
        if (f.category or "").lower() == "error":
            kept.append(f)
            continue

        text = _finding_text(f)
        cat = _finding_category(f)
        drop = False

        for spec in _RATE_FEATURE_SPECS:
            key = spec["fp_key"]
            if key not in fingerprint:
                continue
            try:
                rate = float(fingerprint[key])
            except (TypeError, ValueError):
                continue

            # Only apply to findings that look like they concern this feature
            cat_hit = cat in spec["categories"] or key.replace("_", " ") in text
            under = _matches_any(text, spec["under_patterns"])
            over = _matches_any(text, spec["over_patterns"])
            if not (cat_hit or under or over):
                continue

            direction = _direction_for_rate(rate)
            if direction == "rare" and under and not over:
                drop = True
                break
            if direction == "common" and over and not under:
                drop = True
                break

        if not drop:
            kept.append(f)
    return kept



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

    overall_style_score is computed from findings (Defect A), after direction
    filtering against fingerprint rates (Defect B). The LLM's overall_style_score
    field is ignored when present.
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

    direction_guide = build_fingerprint_direction_guide(fingerprint)

    # ── Groq LLM call ─────────────────────────────────────────────────────────
    from groq import Groq

    client = Groq()

    system_prompt = (
        "You are a Style Analyst for PersonaCR. You compare submitted code against a "
        "developer's personal coding patterns (NOT generic best practices).\n\n"
        "Your job: find where the submitted code DEVIATES from how this developer usually writes.\n\n"
        "FINGERPRINT DIRECTION (critical):\n"
        "Rate features are frequencies of what this developer ACTUALLY does — not ideals.\n"
        f"- If a rate is LOW (≤ {RARE_MAX}): the developer rarely does X. Do NOT flag "
        "missing/absence of X. Only flag clear over-use of X.\n"
        f"- If a rate is HIGH (≥ {COMMON_MIN}): the developer usually does X. Flag missing X. "
        "Do NOT flag presence of X as a deviation.\n"
        "- Mid-range: only flag clear departures in either direction.\n"
        "Deviation = departure from the repo's actual norm, in either direction.\n\n"
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
        "overall_style_score in the JSON is ignored by the system (score is computed from findings).\n"
        "Only report DEVIATIONS from personal patterns, not generic code quality issues. "
        "Do not report praise / consistency notes as findings."
    )

    user_prompt = (
        f"Developer's coding fingerprint:\n{json.dumps(fp_summary, indent=2, default=str)}\n\n"
        f"{direction_guide}\n\n"
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
            findings = filter_findings_by_fingerprint_direction(findings, fingerprint)
            score = compute_style_score_from_findings(findings)
            result = StyleAnalysisOutput(
                findings=findings,
                overall_style_score=score,
                similar_functions_found=similar_count,
            )
        else:
            result = StyleAnalysisOutput(
                findings=[],
                overall_style_score=SCORE_BASE,
                similar_functions_found=similar_count,
            )
    except Exception as e:
        from backend.src.core.metrics import maybe_record_groq_throttle

        maybe_record_groq_throttle(e)
        result = StyleAnalysisOutput(
            findings=[
                StyleFinding(
                    category="error",
                    severity="low",
                    description=f"Style analysis error: {str(e)[:100]}",
                )
            ],
            # Error findings do not penalize (honesty); neutral mid score on hard failure
            overall_style_score=50.0,
            similar_functions_found=similar_count,
        )

    elapsed = int((time.time() - start) * 1000)
    return result, elapsed
