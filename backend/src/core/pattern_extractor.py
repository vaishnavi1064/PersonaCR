"""
Pattern Extractor — analyzes a list of CodeChunks to build a developer's coding fingerprint.

Features:
- Original baseline: avg/max function length, docstring coverage, naming convention,
  error handling rate, type hint usage, complexity, common design patterns
- Ghaleb MSR 2026 (arxiv 2601.17406): comment density, inline comment ratio,
  comment-to-code ratio, conditional density, loop density, for-to-while ratio,
  comprehension ratio, change-concentration Gini, indentation consistency,
  line length statistics (avg/max/std/over-80/over-120), import density,
  wildcard import ratio
"""
from __future__ import annotations

import ast
import re
from collections import Counter
from statistics import mean
from statistics import stdev as _stdev


# ── Original helpers ──────────────────────────────────────────────────────────

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


def _detect_naming_convention(names: list[str]) -> str:
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


# ── Ghaleb MSR 2026 helpers ───────────────────────────────────────────────────

def _comment_stats(source: str, language: str) -> dict:
    """
    Analyze comment patterns in a single function.

    Returns:
        density        — comment_lines / total_lines
        inline_count   — comments sharing a line with code
        block_count    — whole-line comments
        code_lines     — non-empty, non-pure-comment lines
    """
    lines = source.splitlines()
    if not lines:
        return {"density": 0.0, "inline_count": 0, "block_count": 0, "code_lines": 0}

    inline_count = 0
    block_count = 0
    code_lines = 0

    if language == "python":
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("#", '"""', "'''")):
                block_count += 1
            elif "#" in line or '"""' in line or "'''" in line:
                inline_count += 1
                code_lines += 1
            elif stripped:
                code_lines += 1
    else:
        in_block = False
        for line in lines:
            stripped = line.strip()
            if in_block:
                block_count += 1
                if "*/" in stripped:
                    in_block = False
            elif stripped.startswith("/*"):
                block_count += 1
                in_block = "*/" not in stripped
            elif stripped.startswith("//"):
                block_count += 1
            elif stripped and ("//" in line or "/*" in line):
                inline_count += 1
                code_lines += 1
            elif stripped:
                code_lines += 1

    total = len(lines)
    density = (inline_count + block_count) / total if total > 0 else 0.0
    return {
        "density": round(density, 3),
        "inline_count": inline_count,
        "block_count": block_count,
        "code_lines": code_lines,
    }


def _conditional_stats(source: str) -> dict:
    """Returns conditional keyword count and density (count / total_lines)."""
    lines = source.splitlines()
    if not lines:
        return {"count": 0, "density": 0.0}
    count = len(re.findall(r"\b(if|elif|else|switch|case|unless|when)\b", source))
    return {"count": count, "density": round(count / len(lines), 3)}


def _loop_stats(source: str) -> dict:
    """Returns for_count, while_count, and loop density."""
    lines = source.splitlines()
    if not lines:
        return {"for_count": 0, "while_count": 0, "density": 0.0}
    for_count = len(re.findall(r"\b(for|foreach)\b", source))
    while_count = len(re.findall(r"\b(while|until|do)\b", source))
    total_loops = for_count + while_count
    density = round(total_loops / len(lines), 3)
    return {"for_count": for_count, "while_count": while_count, "density": density}


def _comprehension_ratio(source: str, language: str) -> float:
    """
    Python only: list/dict/set comprehensions / (comprehensions + explicit for loops).
    Measures preference for functional-style iteration.
    """
    if language != "python":
        return 0.0
    try:
        tree = ast.parse(source)
        comprehensions = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp))
        )
        for_loops = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.For, ast.AsyncFor))
        )
        total = comprehensions + for_loops
        return round(comprehensions / total, 3) if total > 0 else 0.0
    except SyntaxError:
        return 0.0


def _gini_coefficient(values: list[int | float]) -> float:
    """
    Gini coefficient of a distribution. 0 = perfectly equal, 1 = maximally concentrated.
    Applied to function lengths: measures whether code is concentrated in a few long
    functions or evenly distributed (Ghaleb MSR 2026: change-concentration Gini).
    """
    if len(values) < 2:
        return 0.0
    sorted_vals = sorted(float(v) for v in values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    weighted = sum((i + 1) * v for i, v in enumerate(sorted_vals))
    return round((2 * weighted / (n * total)) - (n + 1) / n, 3)


def _indentation_stats(source: str) -> dict:
    """
    Returns indentation style and average indent depth.
    style = 'spaces' | 'tabs' | 'mixed'
    """
    tab_lines = 0
    space_lines = 0
    indent_widths: list[int] = []

    for line in source.splitlines():
        if not line.strip():
            continue
        if line.startswith("\t"):
            tab_lines += 1
        elif line.startswith(" "):
            space_lines += 1
            width = len(line) - len(line.lstrip(" "))
            indent_widths.append(width)

    if tab_lines > space_lines:
        style = "tabs"
    elif space_lines > tab_lines:
        style = "spaces"
    elif tab_lines == 0 and space_lines == 0:
        style = "spaces"
    else:
        style = "mixed"

    avg_depth = round(mean(indent_widths), 1) if indent_widths else 0.0
    return {"style": style, "avg_depth": avg_depth}


def _line_length_stats(source: str) -> dict:
    """Returns avg, max, std, lines_over_80, lines_over_120 (all as ratios 0–1)."""
    lines = [line for line in source.splitlines() if line.strip()]
    if not lines:
        return {"avg": 0.0, "max": 0, "std": 0.0, "over_80": 0.0, "over_120": 0.0}
    lengths = [len(line) for line in lines]
    n = len(lengths)
    avg = round(mean(lengths), 1)
    mx = max(lengths)
    std = round(_stdev(lengths), 1) if n >= 2 else 0.0
    over_80 = round(sum(1 for ll in lengths if ll > 80) / n, 3)
    over_120 = round(sum(1 for ll in lengths if ll > 120) / n, 3)
    return {"avg": avg, "max": mx, "std": std, "over_80": over_80, "over_120": over_120}


def _import_stats(chunks: list) -> dict:
    """
    Compute import_density and wildcard_import_ratio across all non-summary chunks.
    wildcard_import_ratio = 'from x import *' / total import statements.
    """
    total_lines = 0
    import_count = 0
    wildcard_count = 0
    import_re = re.compile(
        r"^\s*(import |from \S+ import |#include |require\(|using )",
        re.MULTILINE,
    )
    wildcard_re = re.compile(
        r"^\s*from \S+ import \s*\*|^\s*import \s*\*",
        re.MULTILINE,
    )
    for chunk in chunks:
        if getattr(chunk, "function_name", "") == "__file_summary__":
            continue
        lines = chunk.source.splitlines()
        total_lines += len(lines)
        import_count += len(import_re.findall(chunk.source))
        wildcard_count += len(wildcard_re.findall(chunk.source))

    density = round(import_count / total_lines, 3) if total_lines > 0 else 0.0
    wildcard_ratio = round(wildcard_count / import_count, 3) if import_count > 0 else 0.0
    return {"density": density, "wildcard_ratio": wildcard_ratio}


# ── Main extractor ────────────────────────────────────────────────────────────

def extract_fingerprint(chunks: list) -> dict:
    """
    Build a coding fingerprint from a list of CodeChunks.

    Returns a dict with all original + Ghaleb MSR 2026 features.
    File-level chunks (__file__, __file_summary__) are excluded from
    per-function metrics but included in import stats.
    """
    if not chunks:
        return {}

    # Per-function accumulators — original
    function_lengths: list[int] = []
    has_docstring_list: list[bool] = []
    has_type_hints_list: list[bool] = []
    has_error_handling_list: list[bool] = []
    complexity_scores: list[int] = []
    function_names: list[str] = []
    all_patterns: list[str] = []
    languages: list[str] = []

    # Per-function accumulators — Ghaleb MSR 2026
    comment_densities: list[float] = []
    total_inline_comments = 0
    total_block_comments = 0
    total_code_lines = 0
    total_comment_lines_all = 0

    conditional_densities: list[float] = []
    total_conditionals = 0

    loop_densities: list[float] = []
    total_for_loops = 0
    total_while_loops = 0

    comprehension_ratios: list[float] = []

    indent_styles: list[str] = []
    indent_depths: list[float] = []

    line_avgs: list[float] = []
    line_maxes: list[int] = []
    line_stds: list[float] = []
    lines_over_80_rates: list[float] = []
    lines_over_120_rates: list[float] = []

    for chunk in chunks:
        source = chunk.source
        lang = chunk.language
        name = chunk.function_name

        # Skip file-level chunks for per-function metrics
        if name in ("__file__", "__file_summary__"):
            continue

        lines = [line for line in source.splitlines() if line.strip()]
        if not lines:
            continue

        function_lengths.append(len(lines))
        function_names.append(name)
        languages.append(lang)

        complexity_scores.append(_estimate_complexity(source))
        has_error_handling_list.append(_has_error_handling(source))

        if lang == "python":
            has_docstring_list.append(_has_docstring(source))
            has_type_hints_list.append(_has_type_hints(source))
        else:
            has_docstring_list.append(bool(re.search(r"/\*\*|///", source)))
            has_type_hints_list.append(True)

        all_patterns.extend(_detect_patterns(source))

        # Comments
        cs = _comment_stats(source, lang)
        comment_densities.append(cs["density"])
        total_inline_comments += cs["inline_count"]
        total_block_comments += cs["block_count"]
        total_code_lines += cs["code_lines"]
        total_comment_lines_all += cs["inline_count"] + cs["block_count"]

        # Conditionals
        cond = _conditional_stats(source)
        conditional_densities.append(cond["density"])
        total_conditionals += cond["count"]

        # Loops
        lp = _loop_stats(source)
        loop_densities.append(lp["density"])
        total_for_loops += lp["for_count"]
        total_while_loops += lp["while_count"]

        # Comprehensions (Python only)
        if lang == "python":
            comprehension_ratios.append(_comprehension_ratio(source, lang))

        # Indentation
        ind = _indentation_stats(source)
        indent_styles.append(ind["style"])
        if ind["avg_depth"] > 0:
            indent_depths.append(ind["avg_depth"])

        # Line lengths
        ll = _line_length_stats(source)
        line_avgs.append(ll["avg"])
        line_maxes.append(ll["max"])
        line_stds.append(ll["std"])
        lines_over_80_rates.append(ll["over_80"])
        lines_over_120_rates.append(ll["over_120"])

    total = len(function_lengths)
    if total == 0:
        return {}

    pattern_counts = Counter(all_patterns)
    lang_counts = Counter(languages)

    # Derived aggregate metrics
    total_comments = total_inline_comments + total_block_comments
    inline_comment_ratio = (
        round(total_inline_comments / total_comments, 3) if total_comments > 0 else 0.0
    )
    comment_to_code_ratio = (
        round(total_comment_lines_all / total_code_lines, 3) if total_code_lines > 0 else 0.0
    )

    total_loops = total_for_loops + total_while_loops
    for_to_while_ratio = (
        round(total_for_loops / total_loops, 3) if total_loops > 0 else 0.0
    )

    dominant_indent = (
        Counter(indent_styles).most_common(1)[0][0] if indent_styles else "spaces"
    )
    indentation_consistency = (
        round(sum(1 for s in indent_styles if s == dominant_indent) / len(indent_styles), 3)
        if indent_styles else 1.0
    )

    imp = _import_stats(chunks)

    return {
        # ── Original features ────────────────────────────────────────────────
        "avg_function_length": round(mean(function_lengths), 1),
        "max_function_length": max(function_lengths),
        "docstring_coverage": round(sum(has_docstring_list) / total, 3),
        "naming_convention": _detect_naming_convention(function_names),
        "error_handling_rate": round(sum(has_error_handling_list) / total, 3),
        "type_hint_usage": round(sum(has_type_hints_list) / total, 3),
        "avg_complexity": round(mean(complexity_scores), 2),
        "common_patterns": list(pattern_counts.keys()),
        "pattern_frequency": dict(pattern_counts),
        "languages": list(lang_counts.keys()),
        "language_distribution": dict(lang_counts),
        "total_functions": total,
        # ── Ghaleb MSR 2026 — comment features ──────────────────────────────
        "comment_density": round(mean(comment_densities), 3) if comment_densities else 0.0,
        "inline_comment_ratio": inline_comment_ratio,
        "comment_to_code_ratio": comment_to_code_ratio,
        # ── Ghaleb MSR 2026 — conditional features ──────────────────────────
        "conditional_density": round(mean(conditional_densities), 3) if conditional_densities else 0.0,
        "conditionals_per_100_lines": round(
            mean(conditional_densities) * 100, 2
        ) if conditional_densities else 0.0,
        # ── Ghaleb MSR 2026 — loop features ─────────────────────────────────
        "loop_density": round(mean(loop_densities), 3) if loop_densities else 0.0,
        "for_to_while_ratio": for_to_while_ratio,
        # ── Ghaleb MSR 2026 — style features ────────────────────────────────
        "comprehension_ratio": round(mean(comprehension_ratios), 3) if comprehension_ratios else 0.0,
        "change_concentration_gini": _gini_coefficient(function_lengths),
        # ── Ghaleb MSR 2026 — indentation features ──────────────────────────
        "indentation_consistency": indentation_consistency,
        "primary_indent_depth": round(mean(indent_depths), 1) if indent_depths else 0.0,
        # ── Ghaleb MSR 2026 — line length features ──────────────────────────
        "avg_line_length": round(mean(line_avgs), 1) if line_avgs else 0.0,
        "max_line_length": max(line_maxes) if line_maxes else 0,
        "std_line_length": round(mean(line_stds), 1) if line_stds else 0.0,
        "lines_over_80": round(mean(lines_over_80_rates), 3) if lines_over_80_rates else 0.0,
        "lines_over_120": round(mean(lines_over_120_rates), 3) if lines_over_120_rates else 0.0,
        # ── Ghaleb MSR 2026 — import features ───────────────────────────────
        "import_density": imp["density"],
        "wildcard_import_ratio": imp["wildcard_ratio"],
    }
