"""
One-line repo summary, generated once per analysis and stored inside the
fingerprint (fingerprint_data.repo_summary) — no schema change needed.

Grounded: the model only sees the GitHub description, topics, the start of
the README, sample file paths and the language mix, and is told not to go
beyond them. One LLM call; any failure → None (the analysis still succeeds).
"""
from __future__ import annotations

import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from github import Github

logger = logging.getLogger(__name__)

README_CHARS = 3000
MAX_SUMMARY_CHARS = 200
_REFUSAL = re.compile(r"\b(i (?:can(?:no|')t|don't|do not) (?:know|determine|tell)|not enough information|insufficient information)\b", re.I)


def fetch_repo_context(repo_url: str, github_token: str | None = None) -> dict[str, Any]:
    """Description, topics and README start from GitHub; each part best-effort."""
    ctx: dict[str, Any] = {"description": "", "topics": [], "readme": ""}
    try:
        token = github_token or os.getenv("GITHUB_TOKEN")
        g = Github(token) if token else Github()
        owner, name = repo_url.rstrip("/").removesuffix(".git").split("/")[-2:]
        repo = g.get_repo(f"{owner}/{name}")
    except Exception as e:
        logger.warning("repo summary: could not open %s: %s", repo_url, e)
        return ctx
    for key, getter in (
        ("description", lambda: repo.description or ""),
        ("topics", lambda: list(repo.get_topics())),
        ("readme", lambda: repo.get_readme().decoded_content.decode("utf-8", errors="replace")[:README_CHARS]),
    ):
        try:
            ctx[key] = getter()
        except Exception:
            pass  # no README / topics is normal
    return ctx


def _file_sample(file_paths: list[str], limit: int = 30) -> list[str]:
    """Spread across the tree: shallow paths first, one per directory where possible."""
    seen_dirs: set[str] = set()
    picked: list[str] = []
    for p in sorted(set(file_paths), key=lambda p: (p.count("/"), p)):
        d = p.rsplit("/", 1)[0] if "/" in p else ""
        if d in seen_dirs and len(picked) < limit // 2:
            continue
        seen_dirs.add(d)
        picked.append(p)
        if len(picked) >= limit:
            break
    return picked


def clean_summary(text: str) -> str | None:
    """First sentence, one line, no quotes/markdown; None if empty or a refusal."""
    t = re.sub(r"\s+", " ", (text or "").strip().strip('"').strip("'").strip("`")).strip()
    t = re.sub(r"^(summary|one-line summary)\s*:\s*", "", t, flags=re.I).lstrip("#*- ").strip()
    if not t or _REFUSAL.search(t):
        return None
    first = re.split(r"(?<=[.!?])[\"'”’]?\s", t, maxsplit=1)[0].strip("\"'”’")
    if len(first) > MAX_SUMMARY_CHARS:
        first = first[: MAX_SUMMARY_CHARS - 1].rsplit(" ", 1)[0] + "…"
    return first


def build_prompt(repo_full_name: str, ctx: dict[str, Any], file_paths: list[str], languages: dict[str, int]) -> tuple[str, str]:
    system = (
        "You write a one-sentence summary of a software repository for a developer tool. "
        "Use ONLY the facts provided (description, topics, README excerpt, file paths, languages). "
        "Say what the code does or is for, plainly — no marketing words, no praise, no guesses about "
        "quality or popularity. At most 25 words. If the facts are thin, describe what the files "
        "show (e.g. 'A Java course assignment implementing …'). Output the sentence only."
    )
    langs = ", ".join(f"{k} ({v} functions)" for k, v in Counter(languages).most_common(4)) or "unknown"
    readme = (ctx.get("readme") or "").strip() or "(no README)"
    user = (
        f"Repository: {repo_full_name}\n"
        f"GitHub description: {ctx.get('description') or '(none)'}\n"
        f"Topics: {', '.join(ctx.get('topics') or []) or '(none)'}\n"
        f"Languages: {langs}\n"
        f"Sample files:\n" + "\n".join(f"  {p}" for p in _file_sample(file_paths)) + "\n\n"
        f"README (start):\n{readme}\n"
    )
    return system, user


def generate_repo_summary(
    repo_url: str,
    file_paths: list[str],
    languages: dict[str, int],
    github_token: str | None = None,
) -> dict[str, Any] | None:
    """{"text", "generated_at"} or None. One LLM call."""
    from backend.src.core.llm_client import complete

    full_name = "/".join(repo_url.rstrip("/").split("/")[-2:])
    ctx = fetch_repo_context(repo_url, github_token)
    system, user = build_prompt(full_name, ctx, file_paths, languages)
    try:
        raw = complete(system, user, temperature=0.2, max_tokens=120, caller="repo_summary")
    except Exception as e:
        logger.warning("repo summary failed for %s: %s", repo_url, str(e)[:200])
        return None
    text = clean_summary(raw)
    if text is None:
        return None
    return {"text": text, "generated_at": datetime.now(timezone.utc).isoformat()}
