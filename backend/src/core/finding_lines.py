"""
Resolve the 1-based line a finding refers to in the submitted code.

Order of trust:
  "ast"      — static analysis (AST / regex match position): exact
  "evidence" — the agent quoted the code; we found that text in the submission
               (corrects LLM line numbers that are off — they often are)
  "stated"   — only the agent's number, in range but unverified
  None       — nothing usable; the UI says "line n/a" instead of guessing
"""
from __future__ import annotations

import re

_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s).strip()


def parse_line_hint(hint: str | None) -> int | None:
    if not hint:
        return None
    m = re.search(r"\b(?:lines?|l)\s*:?\s*(\d+)", hint, re.I) or re.fullmatch(r"\s*(\d+)\s*", hint)
    return int(m.group(1)) if m and int(m.group(1)) > 0 else None


def find_evidence(code_lines: list[str], evidence: str, near: int | None = None) -> int | None:
    """Line containing the quoted code (first non-blank line of it); nearest to `near` if several."""
    first = next((ln for ln in evidence.splitlines() if ln.strip()), "")
    needle = _norm(first).strip("`")
    if len(needle) < 3:  # too short to identify a line ("x", ")", …)
        return None
    hits = [i + 1 for i, ln in enumerate(code_lines) if needle in _norm(ln)]
    if not hits:
        return None
    if near is None:
        return hits[0]
    return min(hits, key=lambda n: abs(n - near))


def resolve_line(
    code: str,
    *,
    line: int | None = None,
    evidence: str = "",
    line_hint: str = "",
    source: str = "",
) -> tuple[int | None, str | None]:
    """Return (line, source). See module docstring for the trust order."""
    code_lines = code.splitlines()
    n = len(code_lines)
    stated = line or parse_line_hint(line_hint)

    if source == "ast" and stated and 1 <= stated <= n:
        return stated, "ast"
    if evidence:
        found = find_evidence(code_lines, evidence, near=stated)
        if found:
            return found, "evidence"
    if stated and 1 <= stated <= n:
        return stated, "stated"
    return None, None


def line_of_offset(code: str, offset: int) -> int:
    return code.count("\n", 0, offset) + 1
