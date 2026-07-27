"""
Minimal-A Setup Script — Phase 1 & 2
======================================
Phase 1: Ingest psf/requests (core package only), embed into ChromaDB,
         compute fingerprint, verify retrieval is live.
Phase 2: Print the actual style fingerprint so test pairs can be grounded
         in real conventions.

Run once from repo root:
    backend\\.venv\\Scripts\\python.exe evals\\minimal_a_setup.py

Produces:
    evals/results/minimal_a_fingerprint.json   — full fingerprint + summary
    (ChromaDB collection persisted to backend/.chroma)
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from backend.src.core.github_ingestor import ingest_repo
from backend.src.core.pattern_extractor import extract_fingerprint
from backend.src.core.embedder import embed_and_store, query_similar_staged

HERE = Path(__file__).parent
RESULTS_DIR = HERE / "results"

# ── Constants for this experiment ────────────────────────────────────────────
REPO_URL   = "https://github.com/psf/requests"
USER_ID    = "eval-requests-user"
REPO_NAME  = "requests"

# Limit ingestion to the core package only (src/requests/*.py)
# to keep the embedding set to ~200-400 functions, not the full repo+tests.
CORE_PATH_PREFIX = "src/requests"


def main() -> None:
    github_token = os.getenv("GITHUB_TOKEN")

    # ── Phase 1a: Ingest ─────────────────────────────────────────────────────
    print(f"Ingesting {REPO_URL} ...")
    all_chunks, sha = ingest_repo(REPO_URL, github_token=github_token)

    # Filter to core package only
    core_chunks = [
        c for c in all_chunks
        if c.file_path.startswith(CORE_PATH_PREFIX) or
           c.file_path.startswith("requests/")   # flat layout fallback
    ]
    if not core_chunks:
        # Repo may use a flat layout — keep all .py chunks (no tests)
        core_chunks = [
            c for c in all_chunks
            if c.language == "python"
            and "test" not in c.file_path.lower()
            and "docs" not in c.file_path.lower()
        ]

    func_chunks = [c for c in core_chunks if c.function_name not in ("__file__", "__file_summary__")]
    print(f"  Total chunks ingested (core): {len(core_chunks)}")
    print(f"  Function-level chunks:        {len(func_chunks)}")

    if len(func_chunks) < 10:
        print("ERROR: Too few functions extracted. Check repo layout or CORE_PATH_PREFIX.")
        sys.exit(1)

    # ── Phase 1b: Compute fingerprint ────────────────────────────────────────
    fingerprint = extract_fingerprint(func_chunks)
    print(f"\nFingerprint computed ({len(fingerprint)} features).")

    # ── Phase 1c: Embed into ChromaDB ────────────────────────────────────────
    print(f"Embedding {len(core_chunks)} chunks into ChromaDB (user={USER_ID}, repo={REPO_NAME})...")
    embed_result = embed_and_store(core_chunks, user_id=USER_ID, repo_name=REPO_NAME)
    print(f"  Stored in collection: {embed_result['collection']}")
    print(f"  Chunks embedded:      {embed_result['chunks_embedded']}")

    # ── Phase 1d: VERIFY retrieval is live ───────────────────────────────────
    print("\nVerifying retrieval is live...")
    sample_query = "def get(url, params=None, **kwargs):\n    return request('GET', url, params=params, **kwargs)\n"
    results = query_similar_staged(
        code=sample_query,
        user_id=USER_ID,
        repo_name=REPO_NAME,
        n_files=3,
        n_functions=5,
        language_filter="python",
    )

    files_found    = len(results.get("files", []))
    funcs_found    = len(results.get("functions", []))
    print(f"  Stage 1 (file-level): {files_found} results")
    print(f"  Stage 2 (func-level): {funcs_found} results")

    if files_found == 0 and funcs_found == 0:
        print("\nSTOP: Retrieval returned EMPTY results. Embedding may have failed.")
        print("Collection info:", embed_result)
        sys.exit(1)

    print("\nRetrieval confirmed LIVE. Sample matches:")
    for r in results.get("functions", [])[:3]:
        meta = r.get("metadata", {})
        dist = r.get("distance", "?")
        print(f"  [{dist:.3f}] {meta.get('function_name','?')} @ {meta.get('file_path','?')}")

    # ── Phase 2: Style summary ───────────────────────────────────────────────
    print("\n=== requests style fingerprint ===")
    summary_fields = [
        ("naming_convention",     "Naming"),
        ("docstring_coverage",    "Docstring coverage"),
        ("type_hint_usage",       "Type hint usage"),
        ("error_handling_rate",   "Error handling rate"),
        ("avg_function_length",   "Avg function length (lines)"),
        ("comment_density",       "Comment density"),
        ("comprehension_ratio",   "Comprehension ratio"),
        ("indentation_consistency","Indentation consistency"),
        ("primary_indent_depth",  "Primary indent depth"),
        ("for_to_while_ratio",    "For-to-while ratio"),
    ]
    for key, label in summary_fields:
        print(f"  {label:<30} {fingerprint.get(key, 'N/A')}")

    # ── Save ─────────────────────────────────────────────────────────────────
    RESULTS_DIR.mkdir(exist_ok=True)
    out = {
        "repo_url":      REPO_URL,
        "commit_sha":    sha,
        "user_id":       USER_ID,
        "repo_name":     REPO_NAME,
        "collection":    embed_result["collection"],
        "chunks_embedded": embed_result["chunks_embedded"],
        "func_chunks_count": len(func_chunks),
        "retrieval_verified": (files_found + funcs_found) > 0,
        "retrieval_files": files_found,
        "retrieval_funcs": funcs_found,
        "fingerprint":   fingerprint,
    }
    out_path = RESULTS_DIR / "minimal_a_fingerprint.json"
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved -> {out_path}")
    print("\nPhase 1+2 complete. Retrieval is LIVE. Proceed to minimal_a.py.")


if __name__ == "__main__":
    main()
