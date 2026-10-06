"""
Numeric evidence for style findings: the repo's fingerprint value next to the
same metric measured on the submitted code (same extractor, so the numbers are
comparable). Deterministic — no LLM. A finding gets a metric only when both
sides were measured; otherwise it keeps its text-only evidence.
"""
from __future__ import annotations

import re
from typing import Any

from backend.src.core.github_ingestor import CodeChunk, _extract_generic_functions, _extract_python_functions
from backend.src.core.pattern_extractor import extract_fingerprint

# metric key → (label, kind)   kind: pct | number | lines | text
METRICS: dict[str, tuple[str, str]] = {
    "docstring_coverage": ("Docstrings", "pct"),
    "type_hint_usage": ("Type hints", "pct"),
    "error_handling_rate": ("Error handling", "pct"),
    "comment_density": ("Comment density", "pct"),
    "naming_convention": ("Naming", "text"),
    "avg_function_length": ("Function length", "lines"),
    "avg_complexity": ("Complexity (est.)", "number"),
    "comprehension_ratio": ("Comprehensions", "pct"),
}

# Style Analyst categories → metric
_CATEGORY_METRIC = {
    "documentation": "docstring_coverage", "docs": "docstring_coverage", "docstring_coverage": "docstring_coverage",
    "type_safety": "type_hint_usage", "type_hints": "type_hint_usage", "typing": "type_hint_usage",
    "error_handling": "error_handling_rate",
    "naming": "naming_convention",
    "complexity": "avg_complexity",
    "comments": "comment_density", "comment": "comment_density",
    "function_length": "avg_function_length", "length": "avg_function_length",
    "comprehension": "comprehension_ratio",
}

# Fallback for generic categories ("style"): keywords in the description
_KEYWORD_METRIC = [
    (re.compile(r"docstring|documentation|\bdoc comment", re.I), "docstring_coverage"),
    (re.compile(r"type\s*hint|annotation|untyped", re.I), "type_hint_usage"),
    (re.compile(r"error handling|exception|try\s*/?\s*except|try\s*/?\s*catch", re.I), "error_handling_rate"),
    (re.compile(r"snake_case|camelcase|pascalcase|naming convention|\bnames?\b", re.I), "naming_convention"),
    (re.compile(r"\bcomments?\b", re.I), "comment_density"),
    (re.compile(r"too long|function length|\blines? long|long function", re.I), "avg_function_length"),
    (re.compile(r"comprehension", re.I), "comprehension_ratio"),
    (re.compile(r"complex|nest", re.I), "avg_complexity"),
]


def measure_code(code: str, language: str) -> dict[str, Any]:
    """Fingerprint of the submitted code itself (empty dict if nothing measurable)."""
    if language == "python":
        chunks = _extract_python_functions(code, "submitted.py")
    else:
        chunks = _extract_generic_functions(code, "submitted", language)
    if not chunks and code.strip():
        # A snippet without a function definition: measure it as one unit
        chunks = [CodeChunk(file_path="submitted", language=language, function_name="snippet",
                            source=code, start_line=1, end_line=code.count("\n") + 1)]
    if not chunks:
        return {}
    fp = extract_fingerprint(chunks)
    # The extractor's convention guess defaults to snake_case on ties, and a bare
    # lowercase word ("process") is ambiguous; only count names that show a style.
    fp["naming_convention"] = _unambiguous_naming([c.function_name for c in chunks if c.function_name != "snippet"])
    return fp


def _unambiguous_naming(names: list[str]) -> str | None:
    votes = {"snake_case": 0, "camelCase": 0, "PascalCase": 0}
    for n in names:
        core = n.strip("_")
        if "_" in core and core == core.lower():
            votes["snake_case"] += 1
        elif "_" not in core and core[:1].islower() and any(ch.isupper() for ch in core[1:]):
            votes["camelCase"] += 1
        elif "_" not in core and core[:1].isupper() and any(ch.islower() for ch in core):
            votes["PascalCase"] += 1
    top = max(votes.values())
    winners = [k for k, v in votes.items() if v == top]
    # Mixed styles with no majority have no single convention
    return winners[0] if top > 0 and len(winners) == 1 else None


_DEF_NAME = re.compile(r"\b(?:def|function|func|fun|fn)\s+([A-Za-z_][A-Za-z0-9_]*)|^\s*(?:[\w<>\[\],]+\s+)+([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def naming_at_line(code: str, line: int | None) -> str | None:
    """Convention of the function defined on `line` (naming findings are about one name)."""
    if not line:
        return None
    lines = code.splitlines()
    if not 1 <= line <= len(lines):
        return None
    m = _DEF_NAME.search(lines[line - 1])
    name = m and (m.group(1) or m.group(2))
    return _unambiguous_naming([name]) if name else None


def metric_key_for(category: str, description: str) -> str | None:
    key = _CATEGORY_METRIC.get((category or "").lower())
    if key:
        return key
    for pattern, k in _KEYWORD_METRIC:
        if pattern.search(description or ""):
            return k
    return None


def style_metric(
    category: str,
    description: str,
    repo_fp: dict[str, Any],
    code_fp: dict[str, Any],
    *,
    code: str = "",
    line: int | None = None,
) -> dict[str, Any] | None:
    """{key, label, kind, repo_value, code_value} or None when either side wasn't measured."""
    key = metric_key_for(category, description)
    if key is None:
        return None
    repo_v, code_v = repo_fp.get(key), code_fp.get(key)
    if key == "naming_convention":
        code_v = naming_at_line(code, line) or code_v
    if repo_v is None or code_v is None or (key == "naming_convention" and "unknown" in (repo_v, code_v)):
        return None
    label, kind = METRICS[key]
    return {"key": key, "label": label, "kind": kind, "repo_value": repo_v, "code_value": code_v}
