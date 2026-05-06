"""
Insights Agent — answers natural-language questions about the user's analyzed repos.

Read-only agent: loads fingerprints, reviews, and optionally retrieves code snippets
from ChromaDB, then calls Groq to generate a grounded answer.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv("backend/.env")

from backend.src.core.models import InsightsAgentOutput
from backend.src.db.supabase_rest import SupabaseREST

logger = logging.getLogger(__name__)

# Keywords that trigger ChromaDB code retrieval
CODE_KEYWORDS = re.compile(
    r"\b(function|code|implementation|example|pattern|show me|find|where|class|method|import|variable)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are PersonaCR's Insights Agent. You answer the user's questions about
their analyzed code repositories using ONLY the data provided in the
context below.

Rules:
1. If the answer is in the data, give a clear, specific answer with numbers/examples.
2. If the answer is NOT in the data, say "I don't have that information" — do
   NOT guess, do NOT invent statistics, do NOT make up function names or code.
3. If the user asks about a repo not in the selected list, say so and suggest
   they select it from the panel above.
4. Be concise — a paragraph or two, not an essay. Use bullet points for lists.
5. Never recommend re-running analysis or reviews; you are a read-only assistant.

Context:
{context_block}"""


def _extract_owner_from_url(repo_url: str) -> str:
    """Extract the GitHub owner from a repo URL (matches review_routes.py pattern)."""
    parts = repo_url.rstrip("/").split("/")
    if len(parts) >= 2:
        return parts[-2]
    return "unknown"


def _extract_repo_name_from_url(repo_url: str) -> str:
    """Extract the repo name from a URL."""
    return repo_url.rstrip("/").removesuffix(".git").split("/")[-1]


def _load_fingerprint(db: SupabaseREST, repo_url: str) -> dict[str, Any] | None:
    """Load fingerprint data for a repo from Supabase."""
    try:
        row = db.select_one(
            "fingerprints",
            filters={"repo_url": repo_url.rstrip("/")},
            select="repo_name,fingerprint_data,num_functions,languages",
        )
        if not row:
            return None
        fp_data = row.get("fingerprint_data", {})
        if isinstance(fp_data, str):
            try:
                fp_data = json.loads(fp_data)
            except (json.JSONDecodeError, TypeError):
                fp_data = {}
        return {
            "repo_name": row.get("repo_name", ""),
            "fingerprint_data": fp_data,
            "num_functions": row.get("num_functions", 0),
            "languages": row.get("languages", []),
        }
    except Exception as e:
        logger.warning("Failed to load fingerprint for %s: %s", repo_url, e)
        return None


def _load_recent_reviews(
    db: SupabaseREST, repo_url: str, user_id: str, limit: int = 5
) -> list[dict[str, Any]]:
    """Load the most recent reviews for a repo from Supabase."""
    try:
        rows = db.select_many(
            "user_reviews",
            filters={"user_id": user_id, "repo_url": repo_url.rstrip("/")},
            select="overall_score,style_score,defect_score,issues_count,issues,status,created_at",
            order="created_at.desc",
            limit=limit,
        )
        return rows
    except Exception as e:
        logger.warning("Failed to load reviews for %s: %s", repo_url, e)
        return []


def _summarize_fingerprint(fp_data: dict[str, Any]) -> str:
    """Create a concise summary of key fingerprint features."""
    lines = []
    key_fields = [
        ("avg_function_length", "Avg function length", "{:.1f} lines"),
        ("docstring_coverage", "Docstring coverage", "{:.0%}"),
        ("error_handling_rate", "Error handling rate", "{:.0%}"),
        ("naming_convention", "Naming convention", "{}"),
        ("type_hint_usage", "Type hint usage", "{:.0%}"),
        ("avg_complexity", "Avg complexity", "{:.1f}"),
        ("comment_density", "Comment density", "{:.2%}"),
        ("total_functions", "Total functions", "{}"),
        ("avg_line_length", "Avg line length", "{:.0f} chars"),
    ]
    for field, label, fmt in key_fields:
        val = fp_data.get(field)
        if val is not None:
            try:
                lines.append(f"  - {label}: {fmt.format(val)}")
            except (ValueError, TypeError):
                lines.append(f"  - {label}: {val}")
    return "\n".join(lines) if lines else "  (no fingerprint data available)"


def _summarize_reviews(reviews: list[dict[str, Any]]) -> str:
    """Create a concise summary of recent reviews."""
    if not reviews:
        return "  (no reviews found)"
    lines = []
    for i, rev in enumerate(reviews[:5], 1):
        score = rev.get("overall_score", 0)
        status = rev.get("status", "unknown")
        issues_count = rev.get("issues_count", 0)
        date = rev.get("created_at", "")[:10]
        lines.append(f"  Review {i} ({date}): score={score:.1f}, status={status}, issues={issues_count}")

        # Top 3 issue descriptions
        issues = rev.get("issues", [])
        if isinstance(issues, str):
            try:
                issues = json.loads(issues)
            except (json.JSONDecodeError, TypeError):
                issues = []
        if isinstance(issues, list):
            for issue in issues[:3]:
                desc = issue.get("description", "") if isinstance(issue, dict) else str(issue)
                if desc:
                    lines.append(f"    - {desc[:120]}")
    return "\n".join(lines)


def _retrieve_code_snippets(
    question: str, user_id: str, repo_name: str, n_snippets: int = 3
) -> list[dict[str, Any]]:
    """Optionally retrieve code snippets from ChromaDB if question is code-relevant."""
    try:
        from backend.src.core.embedder import query_similar_staged

        staged = query_similar_staged(
            code=question,
            user_id=user_id,
            repo_name=repo_name,
            n_files=2,
            n_functions=n_snippets,
        )
        return staged.get("functions", [])
    except Exception as e:
        logger.warning("ChromaDB retrieval failed for %s/%s: %s", user_id, repo_name, e)
        return []


def get_insights(
    question: str,
    selected_repo_urls: list[str],
    user_id: str,
) -> InsightsAgentOutput:
    """
    Answer a natural-language question about the user's repos.

    Args:
        question: The user's free-form question
        selected_repo_urls: List of repo URLs to use as context
        user_id: Supabase user ID (for review lookups)

    Returns:
        InsightsAgentOutput with answer, repos_used, and code_chunks_retrieved
    """
    start = time.time()
    db = SupabaseREST()

    should_retrieve_code = bool(CODE_KEYWORDS.search(question))
    context_parts: list[str] = []
    repos_used: list[str] = []
    total_code_chunks = 0

    for repo_url in selected_repo_urls:
        repo_url_clean = repo_url.rstrip("/")
        owner = _extract_owner_from_url(repo_url_clean)
        repo_name = _extract_repo_name_from_url(repo_url_clean)

        # Load fingerprint
        fp = _load_fingerprint(db, repo_url_clean)
        if not fp:
            context_parts.append(f"\n## {repo_name}\n  (no fingerprint data — repo may not be analyzed yet)")
            continue

        repos_used.append(repo_url_clean)
        fp_summary = _summarize_fingerprint(fp.get("fingerprint_data", {}))

        # Load recent reviews
        reviews = _load_recent_reviews(db, repo_url_clean, user_id, limit=5)
        review_summary = _summarize_reviews(reviews)

        section = f"\n## {repo_name}\n"
        section += f"Languages: {', '.join(fp.get('languages', [])) or 'unknown'}\n"
        section += f"Functions analyzed: {fp.get('num_functions', 0)}\n\n"
        section += f"### Coding Fingerprint\n{fp_summary}\n\n"
        section += f"### Recent Reviews ({len(reviews)} found)\n{review_summary}\n"

        # Optionally retrieve code snippets
        if should_retrieve_code:
            snippets = _retrieve_code_snippets(question, owner, repo_name, n_snippets=3)
            if snippets:
                total_code_chunks += len(snippets)
                section += f"\n### Relevant Code Snippets ({len(snippets)} found)\n"
                for j, s in enumerate(snippets[:3], 1):
                    src = s.get("source", "")[:400]
                    meta = s.get("metadata", {})
                    fname = meta.get("function_name", "unknown")
                    fpath = meta.get("file_path", "unknown")
                    section += f"\n--- Snippet {j}: {fname} from {fpath} ---\n{src}\n"

        context_parts.append(section)

    if not repos_used:
        return InsightsAgentOutput(
            answer="I don't have fingerprint data for the selected repo(s). They may not have been analyzed yet — try selecting a repo that has been analyzed.",
            repos_used=[],
            code_chunks_retrieved=0,
        )

    context_block = "\n".join(context_parts)

    # Call Groq LLM
    try:
        from groq import Groq

        client = Groq()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.format(context_block=context_block)},
                {"role": "user", "content": question},
            ],
            temperature=0.2,
            max_tokens=1000,
        )
        answer = response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("Groq call failed in insights_agent")
        answer = "I ran into an error processing that. Try again?"

    elapsed = int((time.time() - start) * 1000)
    logger.info(
        "Insights agent completed in %dms — repos=%d, code_chunks=%d",
        elapsed,
        len(repos_used),
        total_code_chunks,
    )

    return InsightsAgentOutput(
        answer=answer,
        repos_used=repos_used,
        code_chunks_retrieved=total_code_chunks,
    )
