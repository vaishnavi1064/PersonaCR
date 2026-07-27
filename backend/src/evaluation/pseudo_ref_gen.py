"""
Pseudo-Reference Generator — Layer 3 evaluation.

Generates "things a good review should mention" without needing human-written
reference reviews. Combines two complementary sources:

  1. AST static analysis — instant, deterministic, high-precision findings
  2. Groq LLM claims    — semantic, catches what AST misses

Based on CRScore (NAACL 2025): pseudo-references from LLMs + code analysis
tools create reliable evaluation signals without gold-standard human reviews.
"""
from __future__ import annotations

import ast
import json
import re
import time

from dotenv import load_dotenv

from backend.src.core.models import PseudoReference, PseudoRefOutput

load_dotenv("backend/.env")


# ── AST-based pseudo-references ───────────────────────────────────────────────

def _ast_pseudo_refs(code: str, language: str) -> list[PseudoReference]:
    """
    Generate pseudo-references from static analysis.
    These are concrete, verifiable findings — no LLM needed, instant execution.
    """
    refs: list[PseudoReference] = []

    if language != "python":
        if not re.search(r'\b(try|catch|except)\b', code):
            refs.append(PseudoReference(
                text="Code lacks error handling",
                source="ast", category="bug",
            ))
        if len(code.splitlines()) > 50:
            refs.append(PseudoReference(
                text="Long code block could benefit from decomposition",
                source="ast", category="complexity",
            ))
        return refs

    try:
        tree = ast.parse(code)
    except SyntaxError:
        refs.append(PseudoReference(
            text="Code has syntax errors",
            source="ast", category="bug",
        ))
        return refs

    functions = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    # Missing docstrings
    for func in functions:
        has_docstring = (
            func.body
            and isinstance(func.body[0], ast.Expr)
            and isinstance(func.body[0].value, (ast.Constant, ast.Str))
        )
        if not has_docstring:
            refs.append(PseudoReference(
                text=f"Function '{func.name}' lacks a docstring",
                source="ast", category="documentation",
            ))

    # Bare except clauses
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            refs.append(PseudoReference(
                text="Bare except clause should specify exception type",
                source="ast", category="bug",
            ))

    # No error handling at all
    has_try = any(isinstance(n, ast.Try) for n in ast.walk(tree))
    if not has_try and functions:
        refs.append(PseudoReference(
            text="No error handling found — consider adding try/except for robustness",
            source="ast", category="bug",
        ))

    # Missing return type annotations
    for func in functions:
        if func.returns is None:
            refs.append(PseudoReference(
                text=f"Function '{func.name}' lacks return type annotation",
                source="ast", category="style",
            ))

    # High conditional/loop complexity (simple nesting heuristic)
    for func in functions:
        nest_count = sum(
            1 for n in ast.walk(func)
            if isinstance(n, (ast.If, ast.For, ast.While))
        )
        if nest_count > 4:
            refs.append(PseudoReference(
                text=f"Function '{func.name}' has high conditional/loop complexity — consider refactoring",
                source="ast", category="complexity",
            ))

    # Mutable default arguments
    for func in functions:
        for default in func.args.defaults + func.args.kw_defaults:
            if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                refs.append(PseudoReference(
                    text=f"Function '{func.name}' uses mutable default argument",
                    source="ast", category="bug",
                ))

    return refs


# ── LLM-based pseudo-references ───────────────────────────────────────────────

def _llm_pseudo_refs(code: str, language: str) -> list[PseudoReference]:
    """
    Generate pseudo-references using Groq LLM.
    Asks: what claims, issues, and improvements should a good review mention?
    """
    from groq import Groq

    client = Groq()

    system_prompt = (
        "You are generating pseudo-references for evaluating a code review.\n"
        "List the things that a GOOD code review should mention about this code.\n"
        "Include: bugs, code smells, style issues, security concerns, missing documentation,\n"
        "complexity problems, and potential improvements.\n\n"
        "Return ONLY a JSON array of strings. Each string is one thing a review should mention.\n"
        'Example: ["Missing error handling for null input", "Function is too long at 60 lines", '
        '"Variable name \'x\' is unclear"]\n\n'
        "Be specific to THIS code. Don't generate generic advice."
    )

    user_prompt = (
        f"Code ({language}):\n```{language}\n{code[:2500]}\n```\n\n"
        "List what a good review should mention. Return JSON array of strings only."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
        )
        raw = response.choices[0].message.content.strip()
        json_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if json_match:
            items = json.loads(json_match.group())
            return [
                PseudoReference(text=str(item), source="llm", category="general")
                for item in items[:15]
            ]
    except Exception:
        pass

    return []


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_pseudo_references(code: str, language: str) -> PseudoRefOutput:
    """
    Combine AST + LLM pseudo-references into a single output.

    AST runs first (instant), then LLM call enriches with semantic findings.
    The two sources are complementary: AST catches structural issues precisely,
    LLM catches intent-level and semantic issues AST cannot see.
    """
    start = time.time()

    ast_refs = _ast_pseudo_refs(code, language)
    llm_refs = _llm_pseudo_refs(code, language)

    all_refs = ast_refs + llm_refs

    elapsed = int((time.time() - start) * 1000)
    return PseudoRefOutput(references=all_refs, generation_time_ms=elapsed)
