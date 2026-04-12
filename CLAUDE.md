# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PersonaCR** is a FastAPI backend that analyzes GitHub repositories to extract developer coding patterns and build "fingerprints" — structured profiles of a developer's code style. These fingerprints are embedded in a ChromaDB vector store and cached in Supabase.

## Commands

All commands assume you are working from the repo root (`D:\agentic_project`) with the virtual environment activated.

### Setup

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
cp .env.example .env             # then populate .env
```

### Run the server

```bash
uvicorn backend.src.main:app --reload --host 0.0.0.0 --port 8000
```

### Lint

```bash
pylint backend/src/
```

No tests exist yet. When adding them, use `pytest backend/tests/`.

## Architecture

### Pipeline (Layer 1)

The core flow for a `POST /api/analyze-repo` request:

```
analyze_routes.py
  → cache_manager.py     # Check Supabase for cached fingerprint; compare commit SHAs
  → github_ingestor.py   # Fetch repo via PyGithub; extract CodeChunks per function/method
  → pattern_extractor.py # Compute metrics (docstring coverage, naming style, complexity, etc.)
  → embedder.py          # Embed chunks with jinaai/jina-embeddings-v2-base-code; store in ChromaDB
  → cache_manager.py     # Persist FingerprintData to Supabase
```

### Key modules

| File | Responsibility |
|---|---|
| `backend/src/main.py` | FastAPI app init, CORS, router registration |
| `backend/src/core/github_ingestor.py` | GitHub API access; AST-based Python extraction; regex extraction for 10+ other languages |
| `backend/src/core/pattern_extractor.py` | Builds `FingerprintData` from `CodeChunk` list |
| `backend/src/core/embedder.py` | Lazy singleton for fastembed model and ChromaDB client; upsert/query operations |
| `backend/src/core/cache_manager.py` | Supabase read/write; staleness check via commit SHA |
| `backend/src/core/models.py` | All Pydantic models (`FingerprintData`, `CodeChunk`, `ReviewRequest`, etc.) |
| `backend/src/routes/analyze_routes.py` | `POST /api/analyze-repo` endpoint |
| `backend/src/db/supabase_rest.py` | Thin async HTTP client (httpx) for Supabase REST CRUD |

### Data stores

- **ChromaDB** — local persistent vector store at `backend/.chroma/` (gitignored); collection per GitHub username
- **Supabase** — caches serialized `FingerprintData` JSON; keyed by `github_username`; stores latest `commit_sha` for staleness detection

### Singleton pattern

`embedder.py` uses module-level `_model` and `_client` variables loaded on first call via `_get_model()` / `_get_client()`. The Jina embedding model (~500 MB) is downloaded once and reused across requests.

### Caching strategy

1. Check Supabase for an existing fingerprint for the username
2. Fetch the latest commit SHA from GitHub
3. If SHA matches → return cached fingerprint immediately ("fresh")
4. If SHA differs or no cache → re-ingest, re-embed, update Supabase ("stale" / new)
5. `force_refresh=true` in the request skips the SHA check

### Code extraction

- **Python:** AST (`ast.walk`) for top-level functions and class methods
- **Other languages (Java, JS/TS, Kotlin, Go, Rust, C/C++, C#, Ruby):** Regex on function/method signatures
- **Fallback:** Entire file treated as one chunk if no functions found (capped at 3000 chars)
- **File filters:** Skips `node_modules`, `.venv`, `__pycache__`, `dist`, `build`, lock files, minified files, and files > 200 KB

## Environment Variables

See `backend/.env.example`. Required:

```
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
```

Optional (used by planned features):
```
GITHUB_TOKEN          # PAT for higher GitHub API rate limits
GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET
GROQ_API_KEY
```

## Planned / Stub Features

The following are modelled in `models.py` but not yet implemented:
- Code review (`ReviewRequest` / `ReviewOutput`)
- Chat interface (`ChatRequest` / `ChatMessage`)
- Documentation generation (`DocRequest` / `DocResponse`)
- PDF report generation (reportlab in requirements)
- LLM integration (groq in requirements)
- MCP server (fastapi-mcp in requirements)
- Frontend (`frontend/` directory is empty)
