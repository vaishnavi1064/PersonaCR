"""
Turn agent findings into the issue dicts a review returns — with a resolved
integer line (core.finding_lines) and, for style findings, numeric repo-vs-code
evidence (core.style_metrics). Used for the first pass and the Loop 2 re-review.
"""
from __future__ import annotations

from typing import Any

from backend.src.core.finding_lines import resolve_line
from backend.src.core.models import DefectFinding, StyleFinding
from backend.src.core.style_metrics import style_metric


def style_issue(f: StyleFinding, code: str, repo_fp: dict[str, Any], code_fp: dict[str, Any]) -> dict[str, Any]:
    line, source = resolve_line(code, line=f.line, evidence=f.evidence, source=f.line_source)
    return {
        "type": "style",
        "category": f.category,
        "severity": f.severity,
        "description": f.description,
        "fingerprint_value": f.fingerprint_value,
        "submitted_value": f.submitted_value,
        "line": line,
        "line_source": source,
        "metric": style_metric(f.category, f.description, repo_fp, code_fp, code=code, line=line),
    }


def defect_issue(f: DefectFinding, code: str) -> dict[str, Any]:
    line, source = resolve_line(code, line=f.line, evidence=f.evidence, line_hint=f.line_hint, source=f.line_source)
    return {
        "type": "defect",
        "category": f.category,
        "severity": f.severity,
        "description": f.description,
        "line_hint": f.line_hint,
        "line": line,
        "line_source": source,
    }


def build_issues(
    style: list[StyleFinding],
    defects: list[DefectFinding],
    code: str,
    repo_fp: dict[str, Any],
    code_fp: dict[str, Any],
) -> list[dict[str, Any]]:
    return [style_issue(f, code, repo_fp, code_fp) for f in style] + [defect_issue(f, code) for f in defects]
