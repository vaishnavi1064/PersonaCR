"""
Defect Hunter Agent — finds bugs, code smells, and security issues.

Two-phase approach:
  Phase 1 — Local AST analysis (Python only, instant, no LLM).
  Phase 2 — Groq LLM semantic analysis for logic errors, edge cases, security.

Runs IN PARALLEL with Style Analyst (RevAgent pattern, 2025) via asyncio.gather
in the orchestrator — no sequential dependency between them.
"""
from __future__ import annotations

import ast
import json
import re
import time

from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.src.core.models import DefectFinding, DefectHunterOutput


def _ast_analysis(code: str, language: str) -> list[DefectFinding]:
    """
    Local static analysis. Instant, no LLM call.
    Full AST coverage for Python; basic regex checks for other languages.
    """
    findings: list[DefectFinding] = []

    if language != "python":
        if re.search(r"\bcatch\s*\(\s*Exception\b", code):
            findings.append(DefectFinding(
                severity="medium",
                description="Catches generic Exception — use specific exception types",
                category="smell",
            ))
        return findings

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [DefectFinding(severity="critical", description=f"Syntax error: {e}", category="bug")]

    for node in ast.walk(tree):
        # Bare except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(DefectFinding(
                severity="high",
                description="Bare except clause — catches all exceptions including KeyboardInterrupt",
                line_hint=f"line {node.lineno}" if hasattr(node, "lineno") else "",
                category="bug",
            ))

        # Mutable default argument
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    findings.append(DefectFinding(
                        severity="high",
                        description=(
                            f"Mutable default argument in function '{node.name}' "
                            "— use None and initialize inside"
                        ),
                        line_hint=f"line {node.lineno}",
                        category="bug",
                    ))

            # Inconsistent return statements (some paths return None)
            returns = [n for n in ast.walk(node) if isinstance(n, ast.Return)]
            if returns and any(r.value is None for r in returns):
                findings.append(DefectFinding(
                    severity="low",
                    description=(
                        f"Function '{node.name}' has inconsistent return statements "
                        "— some paths return None"
                    ),
                    line_hint=f"line {node.lineno}",
                    category="smell",
                ))

        # Deeply nested conditionals (>3 levels of nesting inside one If)
        if isinstance(node, ast.If):
            depth = sum(1 for child in ast.walk(node) if isinstance(child, ast.If))
            if depth > 3:
                findings.append(DefectFinding(
                    severity="medium",
                    description=(
                        "Deeply nested conditionals (>3 levels) "
                        "— consider early returns or guard clauses"
                    ),
                    line_hint=f"line {node.lineno}" if hasattr(node, "lineno") else "",
                    category="complexity",
                ))

    # Multiple module-level variables before first function definition
    if re.search(r"^[a-zA-Z_]\w*\s*=\s*", code, re.MULTILINE) and "def " in code:
        globals_before_def = code.split("def ")[0]
        assignments = re.findall(r"^([a-zA-Z_]\w*)\s*=", globals_before_def, re.MULTILINE)
        if len(assignments) > 3:
            findings.append(DefectFinding(
                severity="medium",
                description=(
                    f"Multiple module-level variables ({len(assignments)}) "
                    "— consider encapsulating in a class or config"
                ),
                category="smell",
            ))

    return findings


def hunt_defects(code: str, language: str) -> tuple[DefectHunterOutput, int]:
    """
    Main entry point. Combines AST analysis + LLM semantic analysis.
    Returns (DefectHunterOutput, execution_time_ms).
    """
    start = time.time()

    # ── Phase 1: local AST (instant) ─────────────────────────────────────────
    ast_findings = _ast_analysis(code, language)

    # ── Phase 2: Groq LLM semantic analysis ──────────────────────────────────
    from groq import Groq

    client = Groq()

    ast_context = ""
    if ast_findings:
        ast_context = "\nStatic analysis already found:\n" + "\n".join(
            f"- [{f.severity}] {f.description}" for f in ast_findings
        ) + "\nDo NOT repeat these. Find ADDITIONAL issues only."

    system_prompt = (
        "You are a Defect Hunter for PersonaCR. Find bugs, code smells, and security issues "
        "in the submitted code.\n\n"
        "Focus on: logic errors, edge cases, null/None risks, resource leaks, "
        "security vulnerabilities, and code smells.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "bugs": [{"severity": "critical|high|medium|low", "description": "...", "line_hint": "line N", "category": "bug"}],\n'
        '  "code_smells": [{"severity": "...", "description": "...", "line_hint": "...", "category": "smell"}],\n'
        '  "security_issues": [{"severity": "...", "description": "...", "line_hint": "...", "category": "security"}],\n'
        '  "defect_score": 0-100\n'
        "}\n\n"
        "Score 100 = no defects found. Score 0 = critical bugs. "
        "Be specific — cite line numbers where possible."
    )

    user_prompt = (
        f"Code to analyze ({language}):\n"
        f"```{language}\n{code[:3000]}\n```"
        f"{ast_context}\n"
        "Find bugs, code smells, and security issues. Return JSON only."
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
            llm_bugs = [DefectFinding(**b) for b in data.get("bugs", [])]
            llm_smells = [DefectFinding(**s) for s in data.get("code_smells", [])]
            llm_security = [DefectFinding(**s) for s in data.get("security_issues", [])]
            defect_score = float(data.get("defect_score", 70))
        else:
            llm_bugs, llm_smells, llm_security = [], [], []
            defect_score = 70.0
    except Exception as e:
        llm_bugs = [DefectFinding(
            severity="low",
            description=f"LLM analysis error: {str(e)[:100]}",
            category="bug",
        )]
        llm_smells, llm_security = [], []
        defect_score = 70.0

    # ── Merge AST + LLM findings ──────────────────────────────────────────────
    all_bugs = [f for f in ast_findings if f.category == "bug"] + llm_bugs
    all_smells = [f for f in ast_findings if f.category in ("smell", "complexity")] + llm_smells
    all_security = [f for f in ast_findings if f.category == "security"] + llm_security

    result = DefectHunterOutput(
        bugs=all_bugs,
        code_smells=all_smells,
        security_issues=all_security,
        defect_score=defect_score,
    )

    elapsed = int((time.time() - start) * 1000)
    return result, elapsed
