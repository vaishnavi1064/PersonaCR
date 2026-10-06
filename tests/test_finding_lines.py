"""
Integer line numbers on every finding (verified against the code) and numeric
repo-vs-code style metrics. No LLM calls.
"""
from __future__ import annotations

import pytest

from backend.src.agents.defect_hunter import _ast_analysis
from backend.src.core.finding_lines import resolve_line
from backend.src.core.issues import build_issues, defect_issue, style_issue
from backend.src.core.models import DefectFinding, StyleFinding
from backend.src.core.style_metrics import measure_code, metric_key_for, style_metric

CODE = "\n".join([
    "def load_config(path):",       # 1
    "    f = open(path)",           # 2
    "    try:",                     # 3
    "        data = f.read()",      # 4
    "    except:",                  # 5
    "        pass",                 # 6
    "    return eval(data)",        # 7
])


# ── resolve_line ──────────────────────────────────────────────────────────────

def test_evidence_corrects_a_wrong_llm_line():
    # The real failure seen in slice 3: eval() reported on line 5
    assert resolve_line(CODE, line=5, evidence="return eval(data)") == (7, "evidence")


def test_evidence_whitespace_insensitive_and_nearest_match():
    code = "x = 1\ny = f(x)\nz = 2\ny = f(x)\n"
    assert resolve_line(code, line=4, evidence="  y =  f(x) ") == (4, "evidence")
    assert resolve_line(code, line=1, evidence="y = f(x)") == (2, "evidence")


def test_stated_line_kept_when_unverifiable_but_in_range():
    assert resolve_line(CODE, line=3, evidence="something not in the code") == (3, "stated")
    assert resolve_line(CODE, line_hint="line 6") == (6, "stated")


@pytest.mark.parametrize("kw", [{"line": 99}, {"line": None}, {"line_hint": "near the top"}, {"evidence": ")"}])
def test_no_usable_line_is_none_not_a_guess(kw):
    assert resolve_line(CODE, **kw) == (None, None)


def test_ast_lines_are_exact():
    assert resolve_line(CODE, line=5, source="ast") == (5, "ast")


def test_bad_llm_line_values_never_drop_a_finding():
    f = DefectFinding(description="x", line="line 7", evidence=None)
    assert f.line == 7 and f.evidence == ""
    assert DefectFinding(description="x", line="somewhere").line is None
    assert StyleFinding(description="x", line=0).line is None


# ── AST findings carry exact integer lines ────────────────────────────────────

def test_ast_findings_get_lines_through_hunt_pipeline():
    issues = [defect_issue(f, CODE) for f in _ast_analysis(CODE, "python")]
    bare = next(i for i in issues if "Bare except" in i["description"])
    assert bare["line"] == 5 and bare["line_source"] in ("ast", "stated")


def test_non_python_regex_finding_has_line():
    java = "class A {\n  void f() {\n    try { g(); }\n    catch (Exception e) { }\n  }\n}"
    f = _ast_analysis(java, "java")[0]
    assert f.line == 4 and f.line_source == "ast"


# ── style metrics ─────────────────────────────────────────────────────────────

def test_measure_code_python():
    fp = measure_code(CODE, "python")
    assert fp["docstring_coverage"] == 0.0
    assert fp["type_hint_usage"] == 0.0
    assert fp["error_handling_rate"] == 1.0
    assert fp["naming_convention"] == "snake_case"


def test_ambiguous_names_give_no_naming_metric():
    fp = measure_code("def process(x):\n    return x", "python")
    assert fp["naming_convention"] is None  # "process" fits snake_case and camelCase
    assert style_metric("naming", "Naming deviates", {"naming_convention": "snake_case"}, fp) is None


@pytest.mark.parametrize("category,description,key", [
    ("documentation", "Missing docstring", "docstring_coverage"),
    ("type_safety", "No annotations", "type_hint_usage"),
    ("error_handling", "No try/except", "error_handling_rate"),
    ("naming", "camelCase name", "naming_convention"),
    ("style", "Function is too long compared to your usual length", "avg_function_length"),
    ("style", "Missing type hints on parameters", "type_hint_usage"),
    ("imports", "Wildcard import", None),
])
def test_metric_key_for(category, description, key):
    assert metric_key_for(category, description) == key


def test_style_issue_has_repo_vs_code_numbers():
    repo_fp = {"docstring_coverage": 0.79, "type_hint_usage": None}
    code_fp = measure_code(CODE, "python")
    f = StyleFinding(category="documentation", severity="medium", description="Missing docstring", line=1,
                     evidence="def load_config(path):")
    issue = style_issue(f, CODE, repo_fp, code_fp)
    assert issue["line"] == 1 and issue["line_source"] == "evidence"
    assert issue["metric"] == {"key": "docstring_coverage", "label": "Docstrings", "kind": "pct",
                               "repo_value": 0.79, "code_value": 0.0}
    # Repo side not measured (e.g. Java repo type hints) → no numbers, text evidence only
    t = style_issue(StyleFinding(category="type_safety", description="No type hints"), CODE, repo_fp, code_fp)
    assert t["metric"] is None and t["line"] is None


def test_build_issues_shape():
    issues = build_issues(
        [StyleFinding(category="naming", description="x", line=1, evidence="def load_config(path):")],
        [DefectFinding(category="security", severity="critical", description="eval", line=5, evidence="eval(data)")],
        CODE, {"naming_convention": "camelCase"}, measure_code(CODE, "python"),
    )
    assert [(i["type"], i["line"], i["line_source"]) for i in issues] == [("style", 1, "evidence"), ("defect", 7, "evidence")]
    assert issues[0]["metric"]["repo_value"] == "camelCase" and issues[0]["metric"]["code_value"] == "snake_case"


def test_naming_metric_uses_the_named_function_and_ties_are_unknown():
    code = "def load_config(p):\n    return p\n\ndef CountItems(xs):\n    return len(xs)"
    fp = measure_code(code, "python")
    assert fp["naming_convention"] is None  # one snake_case, one PascalCase — no majority
    f = StyleFinding(category="naming", description="PascalCase instead of snake_case", line=4, evidence="def CountItems(xs):")
    m = style_issue(f, code, {"naming_convention": "snake_case"}, fp)["metric"]
    assert (m["repo_value"], m["code_value"]) == ("snake_case", "PascalCase")
