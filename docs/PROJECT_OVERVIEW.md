# PersonaCR — Project Overview

> **One line:** PersonaCR measures how a GitHub repo is written (a ~30-feature style fingerprint) and reviews new code against that repo's own conventions with six cooperating agents.

The [README](../README.md) is the primary document: screenshots, architecture diagrams, evaluation, challenges, and limitations. This file is a code-level companion: where things live and what is (and isn't) built. It does not claim that personalized review beats generic review; the fair benchmark at N=14 is **inconclusive** (see README → Evaluation).

---

## 1. What it does (user perspective)

1. **Import a repo:** paste a public GitHub URL on the Repositories page. A background job on the RQ worker fetches the code, computes the fingerprint, indexes functions in ChromaDB and writes a one-line summary. The card and import dialog show the server's live stage; closing the tab doesn't stop it.
2. **Ask about the repo:** the Chat/Review Studio's "Ask" mode answers from the repo's fingerprint, recent saved reviews, retrieved code, this chat's last turns and earlier chats about the same repo.
3. **Review code:** "Review code" mode enqueues a review on the worker and polls it; results show a score, a confidence level, findings pinned to lines, and an agent trace.
4. **Repo detail:** Overview (summary, key conventions), Convention Atlas (every measured feature with its definition), the repo's chats and saved reviews.
5. **Dashboard:** saved reviews across all repos or one repo: score per review, findings by category, review quality, feedback-loop rates, time per agent.
6. **Guests:** Supabase anonymous sign-in; nothing is saved to Postgres.
7. **MCP:** API endpoints exposed as MCP tools at `/mcp` (Bearer token required).

---

## 2. End-to-end flows (current code)

### 2a. Analyze (background)

```
ReposPage / ImportRepoDialog → store/useRepoJobs.startAnalyze
  → lib/api/repos.ts::startAnalyzeJob → POST /api/analyze-jobs (Bearer JWT)
  → routes/analyze_routes.py::enqueue_analysis
      user from core/auth.py (token sub; guests → guest_<sub>)
      analysis_store.get_record (stale running record → failed, see core/liveness.py)
      job_store.create_job + analysis_store.start_record → core/analyze_queue.enqueue (on_failure hook)
  → workers/analyze_jobs.py::process_analyze_job (RQ worker, heartbeat every 15 s)
      core/analysis.py::run_analysis
        cache_manager.get_cached_fingerprint (SHA check; force_refresh skips)
        github_ingestor.ingest_repo            → CodeChunks (Python AST / regex for others)
        pattern_extractor.extract_fingerprint  → ~30 features
        embedder.embed_and_store               → temp collection → swap into place
        repo_summary.generate_repo_summary     → one LLM call
        cache_manager.save_fingerprint         → Postgres fingerprints (accounts only)
      _record_user_repo                          → user_repos (accounts only, uuid-guarded)
  ← UI polls GET /api/analyze-jobs/{id}; GET /api/repos merges the analysis record
```

The synchronous `POST /api/analyze-repo` runs the same `run_analysis` in the API process (fallback when the queue is unavailable).

### 2b. Review (worker)

```
ChatPage → lib/api/reviews.ts::reviewCode
  → POST /api/reviews → routes/review_routes.py::enqueue_review
      loads the repo's fingerprint (404 if never analyzed), job owner = token sub
  → workers/review_jobs.py::process_review_job (heartbeat every 15 s)
      agents/orchestrator.py::review_code_sync → run_review
        Layer 2 (max 2 iterations):
          planner.plan_review                 rules fast path (≥2 deviations) → else LLM
          style_analyst.analyze_style  ‖  defect_hunter.hunt_defects   (asyncio.gather)
          qa_checker.check_quality            LLM filter
          confidence_evaluator                rules; Loop 1 only if the re-plan differs
        Layer 3:
          pseudo_ref_gen → sts_scorer (MiniLM) → quality_gate; Loop 2 re-review
        any LLM failure → status degraded / error, no score
  ← UI polls GET /api/reviews/{id} (owner only) every 1.5 s
  → lib/db.ts::saveReview → user_reviews (signed-in users; RLS own rows; degraded/error not saved)
```

`POST /api/review` (synchronous) remains for API/MCP clients; the UI doesn't use it.

### 2c. Q&A

```
ChatPage (Ask) → lib/api/chats.ts::askQuestion → POST /api/chat
  → routes/chat_routes.py::ask_insights → agents/insights_agent.get_insights
      fingerprint (Postgres), last 5 saved reviews (accounts), ChromaDB snippets,
      chat_memory: this chat's last 8 turns + up to 3 earlier chats about the same repo (accounts)
      → one LLM call (core/llm_client)
```

---

## 3. Tech stack (verified in code)

| Component | Technology | Evidence |
|---|---|---|
| LLM | Claude via the Anthropic SDK (Haiku 4.5 test, Sonnet 5.5 deploy); Groq optional | `core/llm_client.py` (`LLM_PROVIDER`, `LLM_MODEL`); used by planner, style analyst, defect hunter, QA checker, pseudo-ref gen, insights, repo summary |
| Code embeddings | `jinaai/jina-embeddings-v2-base-code` (768-dim, fastembed/ONNX, CPU) | `core/embedder.py` `MODEL_NAME`; `MAX_EMBED_TOKENS` (2048, k8s 1024), `EMBED_BATCH_SIZE`, `EMBED_TOKEN_BUDGET` |
| Vector store | ChromaDB 1.5.7, cosine | `_get_client()`: `HttpClient` when `CHROMADB_URL` is set, else embedded `PersistentClient` |
| STS scoring | `all-MiniLM-L6-v2` via sentence-transformers (CPU torch in the image) | `evaluation/sts_scorer.py`; `backend/Dockerfile` installs torch from the CPU index |
| Static analysis | Python `ast` | `defect_hunter.py`, `pattern_extractor.py`, `github_ingestor.py` |
| API | FastAPI + Uvicorn, PyJWT | `main.py`, `core/auth.py` |
| Jobs | Redis + RQ (queues `reviews`, `analyze`) | `workers/worker.py`, `core/job_store.py`, `core/analysis_store.py`, `core/liveness.py`, `workers/failures.py` |
| Database / auth | Supabase Postgres (REST via httpx, service role) + Supabase Auth (GitHub OAuth, anonymous sign-in) | `db/supabase_rest.py`, `frontend/src/lib/supabase.ts`, `migrations/` |
| MCP | fastapi-mcp (mcp 1.x pinned) | `main.py` |
| Frontend | React 19, TypeScript, Vite, react-router 7, Zustand, Tailwind v4, Recharts, Framer Motion, CodeMirror | `frontend/package.json` |
| Infra | Docker, k8s manifests + Terraform (local minikube), nginx, Prometheus, Grafana, GitHub Actions | `k8s/`, `terraform/`, `observability/`, `.github/workflows/ci.yml` |

---

## 4. Components

### 4a. Agents (`backend/src/agents/`)

| Agent | LLM? | Role |
|---|---|---|
| Orchestrator | No | Mediator: sequence, parallel Style ‖ Defect, both loops, trace, degraded/error on LLM failure |
| Planner | Hybrid | Rules fast path when ≥2 fingerprint deviations are obvious; else LLM. Re-plans with the evaluator's or quality gate's feedback |
| Style Analyst | Yes | Fingerprint + two-stage retrieval (3 files → up to 8 functions, same language) + LLM; direction filter and non-deviation suppression |
| Defect Hunter | Yes | Phase 1 deterministic AST checks; phase 2 LLM semantic defects |
| QA Checker | Yes | Drops findings irrelevant to the submitted code |
| Confidence Evaluator | No | 4 hand-weighted rules (retrieval 0.3, QA 0.3, finding count 0.2, score sanity 0.2); threshold 0.7. A heuristic, not calibrated |
| Insights Agent | Yes | Grounded Q&A with repo-scoped chat memory |

### 4b. Retrieval (`core/embedder.py`)

Function-level and file-level chunks per repo; one collection per repository (`pcr-{repo}-{md5(owner__repo)[:16]}`), shared by everyone who analyzes it. `query_similar_staged()` is the retrieval used by the Style Analyst and Insights agent. Rebuilds go into `…-t…` and are swapped in only on success.

### 4c. Evaluation layer (`backend/src/evaluation/`)

Pseudo-references (AST + LLM) → MiniLM STS → comprehensiveness / conciseness / relevance → quality gate (comp ≥ 0.40, conc ≥ 0.30, rel ≥ 0.35) that can trigger Loop 2. Internal signals only.

### 4d. Persistence

Schema and RLS are versioned in `migrations/001`–`010` (see `migrations/README.md`).

| Table | Written by | RLS |
|---|---|---|
| `fingerprints` | backend `cache_manager.save_fingerprint` (service role) | service role only |
| `user_repos` | worker `_record_user_repo` (service role); `lib/db.ts::saveRepo` on the sync fallback | own rows only (`auth.uid() = user_id`) |
| `user_reviews` | `lib/db.ts::saveReview` (browser, user JWT) | own rows only |
| `user_chats` | `lib/db.ts` chat helpers (browser) | own rows only |
| `reviews`, `chat_messages`, `documentation`, `agent_traces` | nothing (legacy, empty) | locked (`010`) |

Redis holds job records (`personacr:job:*`) and per-user analysis records (`personacr:analysis:*`), 7-day TTL.

### 4e. Frontend (`frontend/src/`)

| Page | File | What it shows |
|---|---|---|
| Landing | `pages/LandingPage.tsx` | static marketing page |
| Login | `pages/LoginPage.tsx` | GitHub OAuth, Continue as Guest (anonymous sign-in) |
| Repositories | `pages/ReposPage.tsx` | repo cards, import dialog, live analysis status, Reanalyze |
| Repo detail | `pages/RepoDetailPage.tsx` | Overview, Convention Atlas, Chats, Reviews |
| Chat/Review Studio | `pages/ChatPage.tsx` | threads by repo, Ask / Review code, code panel with inline findings |
| Review | `pages/ReviewPage.tsx` | a saved review with its trace |
| Dashboard | `pages/DashboardPage.tsx` | all repos / one repo |
| Settings | `pages/SettingsPage.tsx` | account, theme, accent, feature status |

`lib/api/http.ts` attaches the Supabase access token to every API call; `lib/api/capabilities.ts` gates features that aren't built ("coming soon", never mock data).

### 4f. Evals (`evals/`)

- **Personalization benchmark** (`minimal_a*`, `shared_scale_metric.py`): 7 in/off-style pairs on `psf/requests`, fair shared-scale metric, N=14, inconclusive (Llama 3.3 70B on Groq, July 2026).
- **Defect Hunter eval** (`run_eval.py`, `compare_runs.py`, `test_set.json`): 19 Python snippets (15 seeded defects, 4 clean), keyword-scored; v1/v2 prompt results in `results/`.
- **Ops measurements** (`results/ops_measurements.json` + `results/ops_logs/`): memory, batches, timings, image size, minikube verification, each value with provenance.

---

## 5. Status

| Feature | Status |
|---|---|
| Background analysis with live stages, heartbeat recovery, build-aside index swap | **Built**, verified on minikube |
| ~30-feature fingerprint, Python AST + regex for 10 other languages | **Built** (approximations outside Python) |
| One-line repo summary | **Built** |
| Six-agent review on the worker, two loops, degraded/error handling | **Built** |
| Line-level findings + repo-vs-code style metrics | **Built** |
| Q&A with repo-scoped memory | **Built** |
| JWT auth on every `/api` route, RLS, guest anonymous sign-in | **Built**, live RLS test passed |
| Prometheus metrics + Grafana dashboard | **Built** (dev scale) |
| k8s manifests for local minikube | **Built** (single node, not HA) |
| Cloud deployment / live demo | **Not built** |
| PDF reports (`reportlab`), pylint integration, documentation generation, analytics API | **Not built** (dependencies or models exist without code paths) |
| Calibrated confidence | **Not built** (heuristic today) |

---

## 6. Known gaps & dead code

- **Unused Pydantic models** in `core/models.py` (no references outside the file): `ChatRequest`, `ChatMessage`, `IssueFound`, `ReviewScores`, `ReviewOutput`, `ReviewResponse`, `MonthlyScore`, `IssueCategory`, `AnalyticsResponse`, `DocRequest`, `DocContent`, `DocResponse`, `DocumentationOutput`, `FingerprintResponse`, `InsightsAgentInput`.
- **Unused function:** `embedder.query_similar()` (flat single-stage query); only `query_similar_staged()` is called.
- **Unused dependencies:** `reportlab`, `pylint`/`astroid` are in `requirements.txt` with no imports.
- **Outside the Docker image**, `requirements.txt` resolves CUDA torch on Linux (the image installs the CPU build first).
- **No end-to-end browser tests** in CI.
- See README → Limitations for product-level limits (benchmark, scale, guests).
