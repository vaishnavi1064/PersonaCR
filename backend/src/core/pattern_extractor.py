"""
Pattern Extractor — analyzes a list of CodeChunks to build a developer's coding fingerprint.
Uses Python AST for Python files and heuristics for other languages.
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from statistics import mean


def _has_docstring(source: str) -> bool:
    """Check if a Python function has a docstring."""
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    return True
        return False
    except SyntaxError:
        return False


def _has_type_hints(source: str) -> bool:
    """Check if a Python function has type annotations."""
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_return = node.returns is not None
                has_args = any(arg.annotation is not None for arg in node.args.args)
                if has_return or has_args:
                    return True
        return False
    except SyntaxError:
        return ":" in source and "->" in source


def _has_error_handling(source: str) -> bool:
    """Detect try/except (Python) or try/catch (others)."""
    return bool(re.search(r"\btry\b", source) and re.search(r"\b(except|catch)\b", source))


def _detect_naming_style(names: list[str]) -> str:
    """Determine dominant naming convention from a list of function names."""
    snake = sum(1 for n in names if "_" in n and n == n.lower())
    camel = sum(1 for n in names if re.match(r"^[a-z][a-zA-Z0-9]+$", n) and "_" not in n)
    pascal = sum(1 for n in names if re.match(r"^[A-Z][a-zA-Z0-9]+$", n))

    if snake >= camel and snake >= pascal:
        return "snake_case"
    if camel >= pascal:
        return "camelCase"
    return "PascalCase"


def _estimate_complexity(source: str) -> int:
    """
    Estimate cyclomatic complexity via keyword counting.
    Each if/elif/for/while/and/or/case adds 1.
    """
    keywords = re.findall(
        r"\b(if|elif|else|for|while|and|or|case|catch|except|switch)\b", source
    )
    return 1 + len(keywords)


def _detect_patterns(source: str) -> list[str]:
    """Detect common design patterns in source code."""
    patterns = []
    if re.search(r"\breturn\b.+\n\s*(if|for|while|try)", source):
        patterns.append("early_return")
    if re.search(r"\.builder\(\)|Builder\(\)|\.build\(\)", source, re.IGNORECASE):
        patterns.append("builder")
    if re.search(r"getInstance\(\)|instance\s*=\s*None|_instance", source):
        patterns.append("singleton")
    if re.search(r"(raise|throw)\s+\w*(Error|Exception|Fault)", source):
        patterns.append("custom_exceptions")
    if re.search(r"@(staticmethod|classmethod|property)", source):
        patterns.append("decorators")
    return patterns


def extract_fingerprint(chunks: list) -> dict:
    """
    Build a coding fingerprint from a list of CodeChunks.

    Returns:
        dict with keys:
            avg_function_length, docstring_coverage, naming_style,
            error_handling_rate, type_hint_usage, avg_complexity,
            common_patterns, languages, total_functions
    """
    if not chunks:
        return {}

    function_lengths = []
    has_docstring_list = []
    has_type_hints_list = []
    has_error_handling_list = []
    complexity_scores = []
    function_names = []
    all_patterns: list[str] = []
    languages: list[str] = []

    for chunk in chunks:
        source = chunk.source
        lang = chunk.language
        name = chunk.function_name

        # Skip file-level chunks for per-function metrics
        if name == "__file__":
            continue

        lines = [l for l in source.splitlines() if l.strip()]
        function_lengths.append(len(lines))
        function_names.append(name)
        languages.append(lang)

        complexity_scores.append(_estimate_complexity(source))
        has_error_handling_list.append(_has_error_handling(source))

        if lang == "python":
            has_docstring_list.append(_has_docstring(source))
            has_type_hints_list.append(_has_type_hints(source))
        else:
            # Heuristic for other languages: JSDoc / Javadoc style comments
            has_docstring_list.append(bool(re.search(r"/\*\*|///", source)))
            has_type_hints_list.append(True)  # Java/TS are statically typed by default

        all_patterns.extend(_detect_patterns(source))

    total = len(function_lengths)
    if total == 0:
        return {}

    pattern_counts = Counter(all_patterns)
    lang_counts = Counter(languages)

    return {
        "avg_function_length": round(mean(function_lengths), 1),
        "max_function_length": max(function_lengths),
        "docstring_coverage": round(sum(has_docstring_list) / total, 3),
        "naming_style": _detect_naming_style(function_names),
        "error_handling_rate": round(sum(has_error_handling_list) / total, 3),
        "type_hint_usage": round(sum(has_type_hints_list) / total, 3),
        "avg_complexity": round(mean(complexity_scores), 2),
        "common_patterns": list(pattern_counts.keys()),
        "pattern_frequency": dict(pattern_counts),
        "languages": list(lang_counts.keys()),
        "language_distribution": dict(lang_counts),
        "total_functions": total,
    }
