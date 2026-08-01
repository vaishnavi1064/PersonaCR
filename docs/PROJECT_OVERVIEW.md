# PersonaCR — Project Overview

> **One-line pitch:** A multi-agent AI system that learns a developer's personal coding style from their GitHub repos, then reviews new code against those patterns instead of generic rules.

---

## 1. What It Does (User Perspective)

1. **Analyze a repo** — User pastes a GitHub URL. The system ingests the code, extracts a 30-feature "coding fingerprint," embeds functions into a vector store, and caches the result.
2. **Review code** — User pastes a code snippet. Six AI agents compare it against the fingerprint and return personalized style deviations, bugs, and quality scores.
3. **Ask questions** — User asks free-form questions about their analyzed repos. An Insights Agent answers grounded in fingerprints, past reviews, and code snippets from ChromaDB.
4. **Dashboard** — Historical review scores, issue breakdown, CRScore quality metrics, per-agent latency, and agentic-loop health rates.
5. **MCP integration** — Any MCP-compatible tool (Claude Desktop, Cursor, VS Code Copilot) can call PersonaCR's endpoints as tools directly in the editor.

---

## 2. How It Works — End-to-End Data Flow

### 2a. Analyze Flow

```
User pastes GitHub URL
  → frontend/src/pages/ChatPage.tsx (L297-343) detects GH_REGEX
  → frontend/src/lib/api.ts::analyzeRepo() → POST /api/analyze-repo
  → backend/src/routes/analyze_routes.py::analyze_repo()
    → backend/src/core/cache_manager.py::get_cached_fingerprint()  [check Supabase cache]
    → backend/src/core/github_ingestor.py::ingest_repo()           [PyGithub → CodeChunks]
    → backend/src/core/pattern_extractor.py::extract_fingerprint() [AST → 30 features]
    → backend/src/core/embedder.py::embed_and_store()              [Jina v2 → ChromaDB]
    → backend/src/core/cache_manager.py::save_fingerprint()        [→ Supabase]
  → Response: fingerprint data, num_functions, cache_status
  → frontend/src/lib/db.ts::saveRepo()                            [→ Supabase user_repos]
```

### 2b. Review Flow

```
User pastes code snippet
  → frontend/src/pages/ChatPage.tsx (L345-370) detects isCodeSnippet()
  → frontend/src/lib/api.ts::reviewCode() → POST /api/review
  → backend/src/routes/review_routes.py::review_code()
    → cache_manager.get_cached_fingerprint()            [load fingerprint from Supabase]
    → backend/src/agents/orchestrator.py::review_code_sync() → run_review()

      ┌─ LAYER 2 (while loop, max 2 iterations) ──────────────────────────┐
      │ Step 1: planner.py::plan_review()          [rules-based → LLM]    │
      │ Step 2: PARALLEL via asyncio.gather():                             │
      │         style_analyst.py::analyze_style()  [ChromaDB + Groq LLM]  │
      │         defect_hunter.py::hunt_defects()   [AST + Groq LLM]       │
      │ Step 3: qa_checker.py::check_quality()     [Groq LLM]             │
      │ Step 4: confidence_evaluator.py::evaluate_confidence() [rules]    │
      │                                                                    │
      │ AGENTIC LOOP 1: if confidence < 0.70 → re-plan (back to Step 1)  │
      └────────────────────────────────────────────────────────────────────┘

      ┌─ LAYER 3 (after Loop 1 settles) ──────────────────────────────────┐
      │ pseudo_ref_gen.py::generate_pseudo_references() [AST + Groq LLM]  │
      │ sts_scorer.py::compute_sts_scores()             [MiniLM cosine]   │
      │ quality_gate.py::evaluate_quality()             [rules-based]     │
      │                                                                    │
      │ AGENTIC LOOP 2: if quality gate fails → re-run full Layer 2+3    │
      └────────────────────────────────────────────────────────────────────┘

  → Response: overall_score, status, issues[], agent_trace[], quality_scores
  → frontend/src/lib/db.ts::saveReview()           [→ Supabase user_reviews]
```

### 2c. Chat / Q&A Flow

```
User asks free-form question
  → frontend/src/pages/ChatPage.tsx (L372-389) — neither GH URL nor code
  → frontend/src/lib/api.ts::chatWithInsights() → POST /api/chat
  → backend/src/routes/chat_routes.py::ask_insights()
    → backend/src/agents/insights_agent.py::get_insights()
      → Loads fingerprints from Supabase (fingerprints table)
      → Loads recent reviews from Supabase (user_reviews table)
      → Optionally retrieves code from ChromaDB (if question has code keywords)
      → Groq LLM call with grounded context
  → Response: answer, repos_used, code_chunks_retrieved
```

---

## 3. Tech Stack (Verified)

| Component | Technology | Evidence |
|---|---|---|
| **LLM** | Groq — Llama 3.3 70B | `backend/src/agents/planner.py:129`, `style_analyst.py:114`, `defect_hunter.py:160`, `qa_checker.py:92`, `pseudo_ref_gen.py:152`, `insights_agent.py:253` — all use `model="llama-3.3-70b-versatile"` |
| **Code embeddings** | Jina v2 base code (768-dim, ONNX via fastembed) | `backend/src/core/embedder.py:26` — `MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"`, loaded via `fastembed.TextEmbedding` (L17, L37) |
| **Vector store** | ChromaDB (persistent, cosine) | `backend/src/core/embedder.py:46` — `PersistentClient`, L127 `hnsw:space: cosine` |
| **STS scoring** | all-MiniLM-L6-v2 (sentence-transformers) | `backend/src/evaluation/sts_scorer.py:33` — `SentenceTransformer("all-MiniLM-L6-v2")` |
| **Static analysis** | Python `ast` module | `backend/src/agents/defect_hunter.py:42` — `ast.parse(code)`, `pattern_extractor.py:59` |
| **Backend** | FastAPI + Uvicorn | `backend/src/main.py:3` — `from fastapi import FastAPI`, `requirements.txt:2-3` |
| **MCP server** | fastapi-mcp | `backend/src/main.py:57` — `from fastapi_mcp import FastApiMCP`, `requirements.txt:29` |
| **Database** | Supabase PostgreSQL (REST API via httpx) | `backend/src/db/supabase_rest.py:16-33` — raw HTTP client, `backend/.env:1` |
| **Repo access** | PyGithub | `backend/src/core/github_ingestor.py:12`, `requirements.txt:9` |
| **Frontend** | React 19 + TypeScript + Vite 8 | `frontend/package.json:16-17,36` |
| **Routing** | react-router-dom v7 | `frontend/package.json:18` |
| **State mgmt** | Zustand (persisted) | `frontend/package.json:20`, `frontend/src/store/useStore.ts:1` |
| **Charts** | Recharts | `frontend/package.json:19` |
| **Animations** | Framer Motion | `frontend/package.json:14` |
| **Styling** | TailwindCSS v4 | `frontend/package.json:24,33` |
| **Auth** | Supabase Auth (GitHub OAuth, implicit flow) | `frontend/src/lib/supabase.ts:14-20` |
| **Icons** | Lucide React | `frontend/package.json:15` |
| **PDF reports** | ReportLab (listed in requirements.txt) | `backend/requirements.txt:26` — **listed but NEVER imported anywhere in source** |
| **pylint** | Listed in requirements.txt | `backend/requirements.txt:19` — **listed but NEVER called in source** (only referenced as string in `models.py:261`) |

---

## 4. Components — Detailed Breakdown

### 4a. Agents (`backend/src/agents/`)

| Agent | File | LLM? | Role |
|---|---|---|---|
| **Orchestrator** | `orchestrator.py` (428 lines) | No | Wires all agents, manages both agentic loops, parallel execution via `asyncio.gather` |
| **Planner** | `planner.py` (157 lines) | Hybrid | Rules-based fast path first (≥2 deviations → no LLM); falls back to Groq for complex cases |
| **Style Analyst** | `style_analyst.py` (155 lines) | Yes | Two-stage ChromaDB retrieval + Groq LLM to find deviations from developer's personal patterns |
| **Defect Hunter** | `defect_hunter.py` (203 lines) | Yes | Phase 1: Python AST analysis (instant); Phase 2: Groq LLM for semantic bugs. Merged output |
| **QA Checker** | `qa_checker.py` (149 lines) | Yes | Validates Style + Defect outputs are relevant to submitted code. Filters hallucinated findings |
| **Confidence Evaluator** | `confidence_evaluator.py` (104 lines) | No | Rules-based scoring (4 factors, max 1.0). Triggers Loop 1 if < 0.70 |
| **Insights Agent** | `insights_agent.py` (280 lines) | Yes | Answers Q&A grounded in fingerprints + reviews + optional ChromaDB code retrieval |

### 4b. RAG Pipeline (`backend/src/core/embedder.py`)

- **What gets embedded:** Every function extracted by `github_ingestor.py` + a file-level summary chunk per file (Ringer 2025 two-stage pattern)
- **Model:** `jinaai/jina-embeddings-v2-base-code` via fastembed (ONNX), 768-dim vectors
- **Vector store:** ChromaDB persistent client at `backend/.chroma/`, cosine distance
- **Collection naming:** `pcr-{sanitized_repo}-{md5_hash[:16]}` per user+repo
- **Retrieval — `query_similar_staged()`** (L216-319):
  - Stage 1: Query file-level chunks (`granularity="file"`) → top N file paths
  - Stage 2: Query function-level chunks (`granularity="function"`) within those files
- **Retrieval — `query_similar()`** (L158-213): Flat single-stage query (used nowhere in current code — only `query_similar_staged` is called)

### 4c. Evaluation Pipeline (`backend/src/evaluation/`)

| Component | File | Role |
|---|---|---|
| **Pseudo-Reference Generator** | `pseudo_ref_gen.py` | AST-based refs (instant) + Groq LLM refs. Combined list of "things a good review should mention" |
| **STS Scorer** | `sts_scorer.py` | Encodes review sentences + pseudo-refs with MiniLM, computes pairwise cosine similarity. Produces comprehensiveness (recall), conciseness (precision), relevance (F1) |
| **Quality Gate** | `quality_gate.py` | Rules-based pass/fail: comp ≥ 0.40, conc ≥ 0.30, rel ≥ 0.35. Sets `should_re_review` flag |

### 4d. Persistence (Supabase PostgreSQL)

**Tables inferred from code** (no migration files exist — schema is defined in Supabase dashboard):

| Table | Read by | Written by | Key columns (from code) |
|---|---|---|---|
| `fingerprints` | `cache_manager.py`, `insights_agent.py`, `review_routes.py` | `cache_manager.py` | `id`, `user_id` (UUID), `repo_url`, `repo_name`, `fingerprint_data` (jsonb), `num_functions`, `languages` (text[]), `last_commit_sha`, `updated_at` |
| `user_reviews` | `insights_agent.py`, `frontend/lib/db.ts` | `frontend/lib/db.ts::saveReview()` | `id`, `user_id`, `repo_url`, `repo_name`, `submitted_code`, `overall_score`, `style_score`, `defect_score`, `comprehensiveness`, `conciseness`, `relevance`, `issues_count`, `issues` (jsonb), `status`, `agent_trace` (jsonb), `iterations`, `created_at` |
| `user_repos` | `frontend/lib/db.ts::fetchRepos()`, `getUserAnalyzedRepos()` | `frontend/lib/db.ts::saveRepo()` | `id`, `user_id`, `repo_url`, `repo_name`, `functions_count`, `languages` (text[]), `analyzed_at` |
| `user_chats` | `frontend/lib/db.ts` (load/save) | `frontend/lib/db.ts` (create/update) | `id`, `user_id`, `title`, `messages` (jsonb), `starred`, `last_repo_url`, `primary_repo_url`, `selected_repos` (jsonb), `updated_at` |

**Note:** Backend writes to `fingerprints` via REST (`supabase_rest.py`). Frontend writes to `user_reviews`, `user_repos`, `user_chats` via the Supabase JS client directly. No backend route writes reviews or repos — that's all frontend-side.

### 4e. MCP Server (`backend/src/main.py:57-71`)

- Uses `fastapi-mcp` to auto-convert all FastAPI endpoints to MCP tools
- Mounted at `/mcp` (SSE endpoint)
- **Exposed tools** (from `mcp_config_examples.json`):
  - `analyze_repo` — POST `/api/analyze-repo`
  - `review_code` — POST `/api/review`
  - `ask_insights` — POST `/api/chat`
  - `health_check` — GET `/health`
  - `cleanup_guest` — DELETE `/api/cleanup-guest/{session_id}`
- Config examples provided for Claude Desktop, Cursor, VS Code Copilot, and production remote

### 4f. Frontend (`frontend/src/`)

**Pages:**

| Page | File | Description |
|---|---|---|
| Landing | `pages/LandingPage.tsx` | Marketing page with 9 sections: ticker, nav, hero, product showcase, how-it-works, bento features, stats, CTA, footer |
| Login | `pages/LoginPage.tsx` (627 lines) | GitHub OAuth + guest mode. Animated fingerprint SVG visual. OAuth callback handler parses URL hash |
| Chat | `pages/ChatPage.tsx` (436 lines) | Main interaction: sidebar + repo selector + message list + input. Routes input to analyze/review/Q&A based on content detection |
| Dashboard | `pages/DashboardPage.tsx` (161 lines) | Summary cards, quality trend chart, issue breakdown, CRScore card, agent latency chart, loop health card, review history table |

**Key components:**
- `chat/RepoSelector.tsx` — Multi-repo selection panel with primary repo indicator
- `chat/FingerprintCard.tsx` — Rendered card for analyze results
- `chat/ReviewResult.tsx` — Rendered card for review results with issues and scores
- `chat/AgentTrace.tsx` — Expandable agent execution timeline
- `dashboard/CRScoreCard.tsx`, `AgentLatencyChart.tsx`, `LoopHealthCard.tsx` — Advanced metrics

**State:** Zustand store with localStorage persistence (`useStore.ts`). Persists theme, accent, chats, selected repos, guest session. Messages are NOT persisted in localStorage — fetched from Supabase on load.

**Auth modes:**
- **GitHub OAuth** — Full Supabase auth, data persisted across sessions
- **Guest mode** — Random `guest_` UUID, ChromaDB collections cleaned on tab close via `sendBeacon`, no Supabase persistence for chats

### 4g. Evals (`evals/`)

- **Test set:** 19 labeled Python snippets (15 with defects, 4 clean) in `test_set.json`
- **Runner:** `run_eval.py` — runs each snippet through `hunt_defects()` directly, measures catch-rate and false-positive rate
- **Comparator:** `compare_runs.py` — compares two versioned runs for prompt regression detection
- **Results:** `eval_v1.json` and `eval_v2.json` exist in `results/`

---

## 5. Current Status

| Feature | Status | Evidence |
|---|---|---|
| GitHub repo ingestion (PyGithub) | **Built** | `github_ingestor.py` — full implementation, Python AST + regex for other langs |
| 30-feature fingerprint extraction | **Built** | `pattern_extractor.py` — all 30 Ghaleb MSR 2026 features computed (L443-483) |
| Jina code embeddings + ChromaDB | **Built** | `embedder.py` — `embed_and_store()`, `query_similar_staged()` fully wired |
| Two-stage retrieval (Ringer 2025) | **Built** | `embedder.py:216-319` — file-level then function-level |
| Supabase fingerprint caching | **Built** | `cache_manager.py` — SHA-based staleness detection |
| Planner (hybrid rules + LLM) | **Built** | `planner.py` — rules fast-path L22-73, Groq fallback L88-156 |
| Style Analyst (ChromaDB + LLM) | **Built** | `style_analyst.py` — two-stage retrieval + Groq comparison |
| Defect Hunter (AST + LLM) | **Built** | `defect_hunter.py` — AST phase L25-111, Groq phase L124-187, merged L189-198 |
| QA Checker (hallucination filter) | **Built** | `qa_checker.py` — LLM validates + filters irrelevant findings |
| Confidence Evaluator (rules) | **Built** | `confidence_evaluator.py` — 4-factor scoring, threshold 0.70 |
| Agentic Loop 1 (confidence re-plan) | **Built** | `orchestrator.py:78-181` — while loop with break on confidence |
| Agentic Loop 2 (quality gate re-review) | **Built** | `orchestrator.py:251-380` — re-runs full Layer 2+3 |
| Parallel Style + Defect execution | **Built** | `orchestrator.py:93-106` — `asyncio.gather()` |
| CRScore pseudo-reference generation | **Built** | `pseudo_ref_gen.py` — AST + LLM sources |
| STS scoring (MiniLM) | **Built** | `sts_scorer.py` — pairwise cosine, comp/conc/rel metrics |
| Quality gate | **Built** | `quality_gate.py` — threshold-based pass/fail |
| MCP server | **Built** | `main.py:57-71` — fastapi-mcp, mounted at `/mcp` |
| Insights / Q&A agent | **Built** | `insights_agent.py` — grounded in fingerprints + reviews + ChromaDB |
| Frontend chat interface | **Built** | `ChatPage.tsx` — input routing, message persistence, repo selection |
| Frontend dashboard | **Built** | `DashboardPage.tsx` — 7 dashboard components with advanced metrics |
| Frontend landing page | **Built** | `LandingPage.tsx` — 9 marketing sections |
| GitHub OAuth + guest mode | **Built** | `LoginPage.tsx`, `supabase.ts`, `useStore.ts` — full OAuth flow + guest fallback |
| Defect Hunter eval harness | **Built** | `evals/run_eval.py` — 19-case test set, catch-rate + FP measurement |
| Prompt regression testing | **Built** | `evals/compare_runs.py` — v1 vs v2 comparison with per-case regression detection |
| PDF report generation | **Planned** | `requirements.txt:26` lists `reportlab` but no import exists anywhere in source |
| pylint integration | **Planned** | `requirements.txt:19` lists `pylint`, `models.py:261` references `"pylint"` as a source type, but no code actually calls pylint |
| Documentation generation | **Planned** | `models.py:161-176` defines `DocRequest`, `DocContent`, `DocResponse`, `DocumentationOutput` (L250-254) — no route or agent implements this |
| Analytics API endpoint | **Planned** | `models.py:136-157` defines `MonthlyScore`, `IssueCategory`, `AnalyticsResponse` — no backend route serves these; dashboard computes stats client-side |
| Job status tracking | **Built** | Async review via Redis/RQ: `POST /api/reviews` + `GET /api/reviews/{job_id}` wire `StatusResponse`; sync `POST /api/review` retained |
| Report generation endpoint | **Built** | `GET /api/reviews/{job_id}/report` returns `ReportResponse` when job completed |
| Old ChatRequest/ChatMessage models | **Planned** | `models.py:63-78` defines `ChatRequest` and `ChatMessage` — not used by any route (replaced by `InsightsChatRequest`) |

---

## 6. Known Gaps & Dead Code

### Unused Pydantic Models (dead code)

| Model | File:Line | Notes |
|---|---|---|
| `ChatRequest` | `models.py:63` | Not imported or used anywhere — superseded by `InsightsChatRequest` |
| `ChatMessage` (backend) | `models.py:71` | Not imported or used anywhere — frontend has its own `ChatMessage` type |
| `IssueFound` | `models.py:90` | Not imported or used anywhere |
| `ReviewScores` | `models.py:97` | Not imported or used anywhere |
| `ReviewOutput` | `models.py:104` | Not imported or used anywhere |
| `ReviewResponse` | `models.py:114` | Not imported or used anywhere |
| `MonthlyScore` | `models.py:136` | Not imported or used anywhere |
| `IssueCategory` | `models.py:142` | Not imported or used anywhere |
| `AnalyticsResponse` | `models.py:148` | Not imported or used anywhere |
| `DocRequest` | `models.py:161` | Not imported or used anywhere |
| `DocContent` | `models.py:166` | Not imported or used anywhere |
| `DocResponse` | `models.py:172` | Not imported or used anywhere |
| `DocumentationOutput` | `models.py:250` | Not imported or used anywhere |
| `FingerprintResponse` | `models.py:52` | Not imported or used anywhere — routes return raw dicts |
| `InsightsAgentInput` | `models.py:301` | Not imported or used anywhere |

### Frontend Stubs (empty files)

| File | Content |
|---|---|
| `frontend/src/hooks/useTheme.ts` | `// useTheme — stub (to be implemented)` |
| `frontend/src/hooks/useInView.ts` | `// useInView — stub (to be implemented)` |
| `frontend/src/components/ui/Card.tsx` | `// Card — stub (to be implemented)` |
| `frontend/src/components/ui/Button.tsx` | `// Button — stub (to be implemented)` |
| `frontend/src/components/ui/Badge.tsx` | `// Badge — stub (to be implemented)` |

### Unused Function

| Function | File:Line | Notes |
|---|---|---|
| `query_similar()` | `embedder.py:158-213` | Flat single-stage query — only `query_similar_staged()` is used by `style_analyst.py` and `insights_agent.py` |

### Dependency Gaps

| Dependency | File | Issue |
|---|---|---|
| `reportlab` | `requirements.txt:26` | Listed but never imported — no PDF generation code exists |
| `pylint` + `astroid` | `requirements.txt:19-20` | Listed but never imported — pseudo-ref model references `"pylint"` as a source string but no pylint analysis runs |
| `sentence-transformers` | `sts_scorer.py:32` | Used at runtime but NOT listed in `requirements.txt` — comment on L23 says "no extra install" which is incorrect |
| `numpy` | `sts_scorer.py:20` | Used at runtime but NOT listed in `requirements.txt` (transitive dep of sentence-transformers) |

### Schema Gap

- No SQL migration files exist. The Supabase schema is managed entirely through the Supabase dashboard. Column types are inferred from code usage, not from a source-controlled definition.

---

## 7. Open Questions

1. **`sentence-transformers` and `numpy` are not in `requirements.txt`** — the STS scorer imports `sentence_transformers` and `numpy` at runtime. The comment on `requirements.txt:23` says "no extra install" but this seems incorrect; `sentence-transformers` is a separate pip package. Is this installed implicitly by another dependency, or is it a missing requirement?

2. **Backend writes fingerprints but frontend writes reviews** — `saveReview()` in `frontend/src/lib/db.ts:82` writes directly to Supabase via the JS client, while fingerprints are written by the backend via `supabase_rest.py`. This split means the backend never records reviews. Is this intentional? The Supabase RLS policy implications are unclear.

3. **16 Pydantic models defined but never used** — `models.py` contains models for documentation generation, analytics, reports, job status, and old chat types that no route or agent references. Are these planned features, or should they be cleaned up?
