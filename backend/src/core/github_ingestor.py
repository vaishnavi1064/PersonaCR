"""
GitHub Ingestor — pulls code files from a public GitHub repo via PyGithub.
Returns a list of CodeChunk objects ready for embedding and pattern extraction.
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field

from github import Github, GithubException
from dotenv import load_dotenv

load_dotenv("backend/.env")

# Extensions we care about
CODE_EXTENSIONS = {
    ".py", ".java", ".ts", ".tsx", ".js", ".jsx",
    ".kt", ".go", ".rs", ".cpp", ".c", ".cs", ".rb",
}

# Files/dirs to skip
SKIP_PATTERNS = re.compile(
    r"(node_modules|\.venv|venv|__pycache__|\.git|dist|build|"
    r"package-lock\.json|yarn\.lock|poetry\.lock|Pipfile\.lock|"
    r"\.min\.js|\.min\.css)"
)


@dataclass
class CodeChunk:
    """A single extracted function/method from a source file."""
    file_path: str
    language: str
    function_name: str
    source: str
    start_line: int
    end_line: int
    granularity: str = "function"   # "function" | "file" — Ringer (2025) two-stage retrieval
    metadata: dict = field(default_factory=dict)


def _detect_language(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    mapping = {
        ".py": "python", ".java": "java", ".ts": "typescript",
        ".tsx": "typescript", ".js": "javascript", ".jsx": "javascript",
        ".kt": "kotlin", ".go": "go", ".rs": "rust",
        ".cpp": "cpp", ".c": "c", ".cs": "csharp", ".rb": "ruby",
    }
    return mapping.get(ext, "unknown")


def _extract_python_functions(source: str, file_path: str) -> list[CodeChunk]:
    """Extract top-level and class-method functions from Python source."""
    chunks: list[CodeChunk] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return chunks

    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", start + 10)
            func_source = "\n".join(lines[start:end])
            chunks.append(CodeChunk(
                file_path=file_path,
                language="python",
                function_name=node.name,
                source=func_source,
                start_line=start + 1,
                end_line=end,
            ))
    return chunks


def _extract_generic_functions(source: str, file_path: str, language: str) -> list[CodeChunk]:
    """
    Regex-based extraction for non-Python files.
    Captures function/method definitions for Java, JS/TS, Kotlin, Go, etc.
    """
    chunks: list[CodeChunk] = []
    # Matches: optional modifiers + function/fun/def keyword + name + (...)
    pattern = re.compile(
        r"(?:(?:public|private|protected|static|async|override|suspend|func|fun)\s+)*"
        r"(?:function\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]{0,200}\)\s*(?::\s*\S+\s*)?\{",
        re.MULTILINE,
    )
    lines = source.splitlines()
    for match in pattern.finditer(source):
        name = match.group(1)
        if name in ("if", "for", "while", "switch", "catch", "try", "else"):
            continue
        start_char = match.start()
        start_line = source[:start_char].count("\n")
        # Grab up to 60 lines as the function body (heuristic)
        end_line = min(start_line + 60, len(lines) - 1)
        func_source = "\n".join(lines[start_line : end_line + 1])
        chunks.append(CodeChunk(
            file_path=file_path,
            language=language,
            function_name=name,
            source=func_source,
            start_line=start_line + 1,
            end_line=end_line + 1,
        ))
    return chunks


def _create_file_level_chunk(
    file_path: str,
    language: str,
    function_chunks: list[CodeChunk],
    source: str,
) -> CodeChunk:
    """
    Build a file-level summary chunk for Ringer-style two-stage retrieval.
    Content: file path + language + all extracted function signatures (first line each).
    Embedded alongside function-level chunks; queried first in Stage 1 retrieval.
    """
    signatures = []
    for chunk in function_chunks:
        sig = chunk.source.splitlines()[0].strip() if chunk.source else ""
        if sig:
            signatures.append(sig)

    summary_lines = [
        f"# File: {file_path}",
        f"# Language: {language}",
        f"# Functions ({len(signatures)}):",
    ] + [f"  {sig}" for sig in signatures[:50]]

    return CodeChunk(
        file_path=file_path,
        language=language,
        function_name="__file_summary__",
        source="\n".join(summary_lines)[:3000],
        start_line=1,
        end_line=source.count("\n") + 1,
        granularity="file",
    )


def ingest_repo(repo_url: str, github_token: str | None = None) -> tuple[list[CodeChunk], str]:
    """
    Pull all code files from a GitHub repo and extract functions.

    Args:
        repo_url: Full URL like https://github.com/owner/repo
        github_token: Optional PAT for higher rate limits (5000 req/hr vs 60)

    Returns:
        (list of CodeChunk, latest commit SHA on default branch)
    """
    token = github_token or os.getenv("GITHUB_TOKEN")
    g = Github(token) if token else Github()

    # Parse owner/repo from URL — strip .git suffix if present
    clean_url = repo_url.rstrip("/").removesuffix(".git")
    parts = clean_url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid repo URL: {repo_url}")
    owner, repo_name = parts[-2], parts[-1]

    try:
        repo = g.get_repo(f"{owner}/{repo_name}")
    except GithubException as e:
        raise ValueError(f"Could not access repo {owner}/{repo_name}: {e}") from e

    # Get latest commit SHA for cache validation
    default_branch = repo.default_branch
    latest_sha = repo.get_branch(default_branch).commit.sha

    chunks: list[CodeChunk] = []
    try:
        contents = repo.get_git_tree(latest_sha, recursive=True)
    except GithubException as e:
        raise ValueError(f"Could not read repo tree: {e}") from e

    for item in contents.tree:
        if item.type != "blob":
            continue
        path = item.path
        if SKIP_PATTERNS.search(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in CODE_EXTENSIONS:
            continue

        # Fetch file content
        try:
            file_content = repo.get_contents(path)
            if file_content.size > 200_000:  # skip files > 200KB
                continue
            source = file_content.decoded_content.decode("utf-8", errors="replace")
        except (GithubException, Exception):
            continue

        language = _detect_language(path)
        if language == "python":
            file_chunks = _extract_python_functions(source, path)
        else:
            file_chunks = _extract_generic_functions(source, path, language)

        if not file_chunks:
            # No functions found — treat whole file as a single file-level chunk
            file_chunks = [CodeChunk(
                file_path=path,
                language=language,
                function_name="__file__",
                source=source[:3000],
                start_line=1,
                end_line=source.count("\n") + 1,
                granularity="file",
            )]
        else:
            # Functions found — also add a file-level summary chunk (Ringer 2025)
            file_chunks.append(_create_file_level_chunk(path, language, file_chunks, source))

        chunks.extend(file_chunks)

    return chunks, latest_sha
