# PersonaCR — Personalized Multi-Agent Code Review

Every code review tool today reviews against generic best practices. PersonaCR learns how **you** write code, then reviews new code against **your** patterns.

PersonaCR is a research-grounded, multi-agent AI system that builds a developer-specific coding fingerprint from their GitHub repositories and reviews submitted code against those personal patterns using 6 specialized AI agents with ML-based quality evaluation.

## The Problem

- 84% of developers use AI coding tools in 2026, and 22% of merged code is now AI-authored
- AI-assisted code increases defect rates by ~1.7x because it doesn't match team conventions
- Every existing tool (CodeRabbit, Copilot Review, SonarQube) reviews against universal standards
- No tool knows that your team uses builder patterns, your codebase prefers early returns, or your senior developer's error handling style uses custom exceptions

## How It Works

PersonaCR operates in three layers:

**Layer 1 — Fingerprint Extraction** ingests a GitHub repository and builds a quantified coding profile: 30 features including function length distribution, error handling rate, naming conventions, docstring coverage, comment density, conditional complexity, indentation consistency, and import patterns. Each function is embedded using code-specific vectors and stored in ChromaDB with file-level and function-level granularity for two-stage retrieval.

**Layer 2 — Multi-Agent Review** uses 6 specialized agents orchestrated with parallel execution and autonomous decision loops:

| Agent | Role | Execution |
|---|---|---|
| Planner | Analyzes code characteristics against fingerprint, decides review strategy | Hybrid: rules-based fast path + LLM fallback |
| Style Analyst | Queries ChromaDB for similar functions, compares against personal patterns | Parallel with Defect Hunter |
| Defect Hunter | AST static analysis + LLM semantic bug detection | Parallel with Style Analyst |
| QA Checker | Validates agent outputs are relevant, filters hallucinated findings | Sequential after parallel agents |
| Confidence Evaluator | Checks evidence sufficiency, triggers re-planning if weak | Rules-based, no LLM (instant) |
| Orchestrator | Connects all agents, manages parallel execution and agentic loops | asyncio.gather for parallelism |

The system has two autonomous decision loops:

- **Agentic Loop 1 (Confidence):** If the Confidence Evaluator determines insufficient evidence (fewer than 5 similar functions from ChromaDB), it sends the review back to the Planner for re-planning with broader retrieval parameters
- **Agentic Loop 2 (Quality Gate):** If the ML evaluation scores the review below quality thresholds, the entire review is re-run with adjusted focus areas

**Layer 3 — ML Evaluation** scores the review's own quality using a CRScore-inspired pipeline:

1. Generates pseudo-references ("things a good review should mention") from AST analysis + LLM claims
2. Computes semantic textual similarity between review sentences and pseudo-references using all-MiniLM-L6-v2
3. Produces three scores: comprehensiveness (did the review cover important issues?), conciseness (is it efficient?), relevance (harmonic mean)
4. Quality gate makes pass/fail decision — triggers Agentic Loop 2 if below threshold

**MCP Server** exposes PersonaCR as a tool for Claude Code, Cursor, and VS Code via the Model Context Protocol. Any AI coding assistant can request personalized reviews directly in the editor.

## Architecture

```
GitHub Repo URL
      │
      ▼
┌─────────────────────────────────────┐
│  Layer 1 — Fingerprint Extraction   │
│  PyGithub → AST → Jina Embeddings  │
│  → ChromaDB (file + function level) │
│  → Supabase cache                   │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│  Layer 2 — Multi-Agent Orchestrator │
│                                     │
│  Planner ──→ ┌─ Style Analyst ──┐  │
│              │  (parallel)       │  │
│              └─ Defect Hunter ──┘  │
│                      │              │
│              QA Checker             │
│                      │              │
│         Confidence Evaluator        │
│          ↺ Agentic Loop 1          │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│  Layer 3 — ML Evaluation            │
│  Pseudo-Ref Gen → STS Scorer        │
│  → Quality Gate                     │
│    ↺ Agentic Loop 2                │
└─────────────────────────────────────┘
      │
      ▼
   Review Result + Quality Scores
   (JSON API / MCP Server)
```

## Performance

Tested against real GitHub repositories with the full pipeline:

| Metric | Value |
|---|---|
| Total end-to-end latency | ~8.5 seconds |
| Style + Defect parallel execution | 1810ms wall-clock (saved ~1745ms vs serial) |
| STS scorer (warm) | 69ms (99.2% reduction from cold start via model preloading) |
| Layer 3 overhead | ~1.1 seconds (20% of total pipeline) |
| Agentic Loop 1 trigger rate | Confidence threshold 0.70 |
| Quality gate pass rate | Relevance > 0.35 threshold |
| Pseudo-references per review | ~10 (AST + LLM combined) |
| Infrastructure cost | $0 |

## Tech Stack

| Component | Technology | Why This Choice |
|---|---|---|
| LLM (all agents) | Groq — Llama 3.3 70B | Free tier, 300+ tok/sec, no credit card needed |
| Code embeddings | Jina v2 base code (local, 768-dim) | Code-specific model trained on 150M+ coding pairs, 30 languages |
| Vector store | ChromaDB (persistent) | Metadata-filtered retrieval, persistent storage, file+function granularity |
| STS scoring | all-MiniLM-L6-v2 (local, 80MB) | Sentence-level semantic similarity for CRScore evaluation |
| Static analysis | Python AST + pylint | Zero-latency local analysis for pseudo-reference generation |
| Backend API | FastAPI | Production-grade, async support, auto-generated OpenAPI spec |
| MCP server | fastapi-mcp | Auto-converts FastAPI endpoints to MCP tools (4 lines of code) |
| Database | Supabase PostgreSQL | Cloud persistence for fingerprints, reviews, agent traces |
| Repo access | PyGithub | GitHub API integration for code ingestion |
| PDF reports | ReportLab | Styled review reports |

## Research Foundation

This project is grounded in 9 peer-reviewed papers from EMNLP, NAACL, ACL, MSR, and IEEE venues. No existing paper combines personalized code style learning with multi-agent automated code review — PersonaCR fills this gap.

See [research/RELATED_WORK.md](research/RELATED_WORK.md) for the complete research mapping showing exactly how each paper influenced the implementation.

| Paper | Venue | What It Grounds in PersonaCR |
|---|---|---|
| CodeAgent (Tang et al.) | EMNLP 2024 | Multi-agent architecture, QA Checker design |
| CRScore (Naik et al.) | NAACL 2025 | Layer 3 pseudo-reference generation, STS scoring, quality dimensions |
| MPCODER (Dai et al.) | ACL 2024 | Per-developer coding style learning concept |
| RevAgent (Li et al.) | November 2025 | Parallel category-specific agents + critic pattern |
| Latency-Aware MAS | January 2026 | Critical path optimization, hybrid planner, capped agentic loops |
| Multi-Agent Design (Google) | February 2025 | Hybrid orchestrator topology, prompt > model insight |
| Ghaleb et al. | MSR 2026 | 30-feature fingerprint engineering (53 features → our 30 selected) |
| Ringer et al. | Computer Standards & Interfaces 2025 | File + function level multi-granularity storage in ChromaDB |
| Ericsson LLM + Static Analysis | July 2025 | Industry validation of LLM + static analyzer combination |

## MCP Integration

PersonaCR is exposed as an MCP server. Connect from any MCP-compatible tool:

```json
{
  "mcpServers": {
    "personacr": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp"]
    }
  }
}
```

Available MCP tools:

- `analyze_repo` — Build a coding fingerprint from a GitHub repository
- `review_code` — Submit code for personalized review against a fingerprint
- `health_check` — Check server status

## Quick Start

```bash
# Clone
git clone https://github.com/vaishnavi1064/PersonaCR.git
cd PersonaCR

# Install dependencies
cd backend
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Add your GROQ_API_KEY and SUPABASE_URL/KEY to .env

# Run
uvicorn backend.src.main:app --reload --port 8000

# API docs
open http://localhost:8000/docs
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | /api/analyze-repo | Analyze a GitHub repo to build a coding fingerprint |
| POST | /api/review | Submit code for personalized multi-agent review |
| GET | /health | Server health check |
| GET | /mcp | MCP server endpoint (SSE stream for AI tool integration) |

## Example Review Output

```json
{
  "overall_score": 80.0,
  "status": "passed",
  "iterations": 1,
  "issues_count": 5,
  "quality_scores": {
    "comprehensiveness": 0.80,
    "conciseness": 0.667,
    "relevance": 0.727
  },
  "quality_gate_passed": true,
  "issues": [
    {
      "type": "style",
      "category": "documentation",
      "severity": "medium",
      "description": "Missing docstring — your fingerprint shows 70% docstring coverage"
    }
  ]
}
```

## Project Structure

```
PersonaCR/
├── backend/
│   ├── src/
│   │   ├── agents/
│   │   │   ├── orchestrator.py         — Multi-agent brain with parallel execution
│   │   │   ├── planner.py              — Hybrid rules-based + LLM review planner
│   │   │   ├── style_analyst.py        — ChromaDB retrieval + pattern comparison
│   │   │   ├── defect_hunter.py        — AST + LLM bug/smell detection
│   │   │   ├── qa_checker.py           — Prompt drift guard (CodeAgent-inspired)
│   │   │   └── confidence_evaluator.py — Rules-based evidence checker
│   │   ├── evaluation/
│   │   │   ├── pseudo_ref_gen.py       — CRScore-inspired pseudo-reference generator
│   │   │   ├── sts_scorer.py           — MiniLM semantic similarity scorer
│   │   │   └── quality_gate.py         — Pass/fail quality decision
│   │   ├── core/
│   │   │   ├── models.py               — Pydantic models (Layer 1, 2, 3)
│   │   │   ├── github_ingestor.py      — PyGithub repo ingestion
│   │   │   ├── pattern_extractor.py    — 30-feature fingerprint via AST
│   │   │   ├── embedder.py             — Jina code embeddings + ChromaDB
│   │   │   └── cache_manager.py        — Supabase fingerprint cache
│   │   ├── db/
│   │   │   └── supabase_rest.py        — Supabase PostgreSQL client
│   │   ├── routes/
│   │   │   ├── review_routes.py        — POST /api/review
│   │   │   └── analyze_routes.py       — POST /api/analyze-repo
│   │   └── main.py                     — FastAPI app + MCP server
│   ├── requirements.txt
│   └── mcp_config_examples.json
├── research/
│   └── RELATED_WORK.md                 — Paper citations + implementation mapping
├── CLAUDE.md                           — AI assistant context file
└── README.md
```

## Author

**Vaishnavi Chaughule** — MS Computer Science, Northeastern University (Seattle)

- GitHub: [vaishnavi1064](https://github.com/vaishnavi1064)
- LinkedIn: [Vaishnavi Chaughule](https://linkedin.com/in/vaishnavi-chaughule)
